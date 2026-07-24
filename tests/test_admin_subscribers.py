"""Owner-only subscriber administration surface.

Covers the authorization contract (401/403/200 keyed on the immutable
canonical users.id, never email), the privacy contract (Paddle identifiers
masked, owner id never returned, no private caching), and the read-model
logic (summary counts + Paddle→display status mapping).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.app import app
from src.api import deps
from src.repositories import admin_subscribers_repo as repo

_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

class _FakeUser:
    def __init__(self, uid: int):
        self.id = uid


@pytest.fixture
def client():
    return TestClient(app)


def _auth_as(monkeypatch, email: str):
    """Make get_current_user return an authenticated (non-env) user."""
    monkeypatch.setattr(deps, "get_current_user", lambda request: {"email": email, "role": "user"})


def _resolve_id(monkeypatch, email_to_id: dict):
    """Wire the canonical-id resolution used by require_owner/is_owner."""
    monkeypatch.setattr("src.db.is_db_available", lambda: True)

    def fake_get_user_by_email(email):
        uid = email_to_id.get(email)
        return _FakeUser(uid) if uid is not None else None

    monkeypatch.setattr(
        "src.repositories.users_repo.get_user_by_email", fake_get_user_by_email
    )


def _snapshot(rows):
    return {
        "rows": rows,
        "truncated": False,
        "generated_at": datetime.now(_UTC),
        "usage_available": True,
    }


def _row(**kw):
    base = {
        "user_id": 1,
        "email": "a@x.com",
        "role": "user",
        "name": None,
        "user_created_at": datetime.now(_UTC),
        "last_login_at": datetime.now(_UTC),
        "plan": None,
        "status": None,
        "billing_cycle": None,
        "paddle_customer_id": None,
        "paddle_subscription_id": None,
        "current_period_start": None,
        "current_period_end": None,
        "cancel_at": None,
        "canceled_at": None,
        "past_due_since": None,
        "sub_created_at": None,
        "last_billing_sync": None,
        "usage": {"ai_messages": None, "saved_jobs": None, "cv_documents": None, "other_documents": None},
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Authorization contract
# ---------------------------------------------------------------------------

def test_unauthenticated_returns_401(client, monkeypatch):
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    # No cookie, real get_current_user → 401.
    r = client.get("/api/v1/admin/subscribers/summary")
    assert r.status_code == 401
    r2 = client.get("/api/v1/admin/subscribers")
    assert r2.status_code == 401


def test_authenticated_non_owner_returns_403(client, monkeypatch):
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _auth_as(monkeypatch, "user@x.com")
    _resolve_id(monkeypatch, {"user@x.com": 7})  # id 7 != owner 42
    assert client.get("/api/v1/admin/subscribers/summary").status_code == 403
    assert client.get("/api/v1/admin/subscribers").status_code == 403


def test_owner_returns_200(client, monkeypatch):
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _auth_as(monkeypatch, "owner@x.com")
    _resolve_id(monkeypatch, {"owner@x.com": 42})
    monkeypatch.setattr(repo, "fetch_snapshot", lambda *a, **k: _snapshot([]))
    monkeypatch.setattr("src.repositories.audit_repo.write_audit_log", lambda *a, **k: None)
    assert client.get("/api/v1/admin/subscribers/summary").status_code == 200
    assert client.get("/api/v1/admin/subscribers").status_code == 200


def test_owner_unconfigured_fails_closed(client, monkeypatch):
    """When RICO_OWNER_USER_ID is unset, nobody is the owner (403, not 200)."""
    monkeypatch.delenv("RICO_OWNER_USER_ID", raising=False)
    _auth_as(monkeypatch, "owner@x.com")
    _resolve_id(monkeypatch, {"owner@x.com": 42})
    assert client.get("/api/v1/admin/subscribers/summary").status_code == 403


def test_email_is_not_the_authorization_key(monkeypatch):
    """The owner's email with a NON-matching canonical id must not authorize."""
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _resolve_id(monkeypatch, {"owner@x.com": 99})  # right email, wrong id
    assert deps.is_owner({"email": "owner@x.com", "role": "user"}) is False
    # A different email whose id matches DOES authorize (id is the key).
    _resolve_id(monkeypatch, {"someone@x.com": 42})
    assert deps.is_owner({"email": "someone@x.com", "role": "user"}) is True


def test_require_owner_unauthenticated_raises_401(monkeypatch):
    def _raise(_request):
        raise HTTPException(status_code=401, detail="nope")

    monkeypatch.setattr(deps, "get_current_user", _raise)
    with pytest.raises(HTTPException) as exc:
        deps.require_owner(object())
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Privacy contract
# ---------------------------------------------------------------------------

def test_paddle_identifiers_are_masked_and_owner_id_absent(client, monkeypatch):
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _auth_as(monkeypatch, "owner@x.com")
    _resolve_id(monkeypatch, {"owner@x.com": 42})
    monkeypatch.setattr("src.repositories.audit_repo.write_audit_log", lambda *a, **k: None)

    full_customer = "ctm_01hzzzzzzzzzzzzzzzzzzzzzzz"
    full_sub = "sub_01hyyyyyyyyyyyyyyyyyyyyyyy"
    rows = [
        _row(
            user_id=42,
            email="owner@x.com",
            status="active",
            plan="pro",
            paddle_customer_id=full_customer,
            paddle_subscription_id=full_sub,
            current_period_end=datetime.now(_UTC) + timedelta(days=20),
        )
    ]
    monkeypatch.setattr(repo, "fetch_snapshot", lambda *a, **k: _snapshot(rows))

    r = client.get("/api/v1/admin/subscribers")
    assert r.status_code == 200
    body = r.text
    # Full Paddle identifiers never leak.
    assert full_customer not in body
    assert full_sub not in body
    # The owner's canonical id (42) is never returned as a usable value.
    sub = r.json()["subscribers"][0]
    assert sub["paddle_subscription_ref"] and "…" in sub["paddle_subscription_ref"]
    # A short (2-digit) id is masked in full; longer ids keep only the last 2.
    assert sub["user_id_masked"] == "••"
    assert "42" not in (sub["user_id_masked"] or "")


def test_private_responses_are_not_cacheable(client, monkeypatch):
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _auth_as(monkeypatch, "owner@x.com")
    _resolve_id(monkeypatch, {"owner@x.com": 42})
    monkeypatch.setattr(repo, "fetch_snapshot", lambda *a, **k: _snapshot([]))
    monkeypatch.setattr("src.repositories.audit_repo.write_audit_log", lambda *a, **k: None)

    for path in ("/api/v1/admin/subscribers", "/api/v1/admin/subscribers/summary"):
        r = client.get(path)
        cc = r.headers.get("cache-control", "").lower()
        assert "no-store" in cc


# ---------------------------------------------------------------------------
# Summary counts + status mapping (pure read-model logic)
# ---------------------------------------------------------------------------

def _now():
    return datetime(2026, 7, 24, 12, 0, tzinfo=_UTC)


def test_summary_counts_are_correct():
    now = _now()
    rows = [
        _row(user_id=1, status="active", current_period_end=now + timedelta(days=10), sub_created_at=now),
        _row(user_id=2, status="active", cancel_at=now + timedelta(days=5),
             current_period_end=now + timedelta(days=5), sub_created_at=now - timedelta(days=90)),
        _row(user_id=3, status="past_due", past_due_since=now - timedelta(days=2),
             current_period_end=now + timedelta(days=1)),
        _row(user_id=4, status="past_due", past_due_since=now - timedelta(days=30)),
        _row(user_id=5, status=None),
        _row(user_id=6, status="canceled", canceled_at=now - timedelta(days=1),
             sub_created_at=now - timedelta(days=40)),  # subscribed last month, canceled this month
        _row(user_id=7, status="inactive"),
    ]
    s = repo.summarize(rows, now)
    assert s["total_users"] == 7
    assert s["active_subscribers"] == 2          # rows 1, 2
    assert s["canceling_subscribers"] == 1       # row 2 (active + cancel_at)
    assert s["past_due_subscribers"] == 1        # row 3 (within grace)
    assert s["payment_failed_subscribers"] == 1  # row 4 (grace expired)
    assert s["canceled_subscribers"] == 1        # row 6
    assert s["expired_subscribers"] == 1         # row 7
    # Free = not paying: rows 4 (grace expired), 5 (none), 6 (canceled), 7 (inactive)
    assert s["free_users"] == 4
    assert s["new_subscriptions_this_month"] == 1  # only row 1 created this month
    assert s["cancellations_this_month"] == 1      # row 6 canceled this month
    assert s["approximate_mrr_usd"] == pytest.approx(2 * 21.50)
    assert s["mrr_is_approximate"] is True


@pytest.mark.parametrize(
    "row_kwargs, expected",
    [
        ({"status": None}, "free"),
        ({"status": "active", "current_period_end": _now() + timedelta(days=5)}, "active"),
        ({"status": "active", "cancel_at": _now() + timedelta(days=5),
          "current_period_end": _now() + timedelta(days=5)}, "canceling"),
        ({"status": "trialing"}, "trialing"),
        ({"status": "past_due", "past_due_since": _now() - timedelta(days=1)}, "past_due"),
        ({"status": "past_due", "past_due_since": _now() - timedelta(days=30)}, "payment_failed"),
        ({"status": "canceled"}, "canceled"),
        ({"status": "inactive"}, "expired"),
        ({"status": "active", "current_period_end": _now() - timedelta(days=1)}, "needs_reconciliation"),
        ({"status": "weird_unknown_status"}, "needs_reconciliation"),
    ],
)
def test_status_mapping(row_kwargs, expected):
    assert repo.derive_status_label(_row(**row_kwargs), _now()) == expected


def test_filter_and_search():
    now = _now()
    rows = [
        _row(user_id=1, email="alice@x.com", name="Alice", status="active",
             current_period_end=now + timedelta(days=5)),
        _row(user_id=2, email="bob@x.com", name="Bob", status="canceled"),
        _row(user_id=3, email="carol@x.com", name=None, status="past_due",
             past_due_since=now - timedelta(days=30)),
    ]
    assert [r["email"] for r in repo.filter_and_search(rows, "active", "", now)] == ["alice@x.com"]
    assert [r["email"] for r in repo.filter_and_search(rows, "payment_failed", "", now)] == ["carol@x.com"]
    # Search matches name OR email, case-insensitively.
    assert [r["email"] for r in repo.filter_and_search(rows, "all", "BOB", now)] == ["bob@x.com"]
    assert [r["email"] for r in repo.filter_and_search(rows, "all", "carol", now)] == ["carol@x.com"]
    # Unknown filter degrades to "all".
    assert len(repo.filter_and_search(rows, "bogus", "", now)) == 3

"""Tests for SubscriptionRepository (Phase 1) and the /me DB-backed path.

DB is mocked throughout — no live Neon connection required.
The existing TestCurrentSubscription in test_subscription_api.py covers the
Free/INACTIVE fallback when DB is unavailable; this suite covers:
  - get_subscription returns None / row correctly
  - upsert_subscription builds the right SQL
  - event_already_processed / record_subscription_event idempotency
  - /me returns correct tier+entitlements when DB has an active subscription
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ── helpers ───────────────────────────────────────────────────────────────────

def _fake_row(**overrides) -> dict:
    base = {
        "user_id": "alice@rico.ai",
        "plan": "pro",
        "status": "active",
        "paddle_customer_id": "ctm_test",
        "paddle_subscription_id": "sub_test",
        "current_period_start": None,
        "current_period_end": None,
        "created_at": None,
        "updated_at": None,
        "cancel_at": None,
        "canceled_at": None,
        "monthly_ai_message_limit": None,
        "saved_jobs_limit": None,
        "profile_optimization_limit": None,
        "premium_recommendations_enabled": False,
        "application_automation_enabled": False,
    }
    base.update(overrides)
    return base


def _mock_db_with_row(row):
    """Return a RicoDB mock for the conn = db.connect() / with conn.cursor() as cur: pattern."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = row

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_db = MagicMock()
    mock_db.available = True
    mock_db.connect.return_value = mock_conn
    return mock_db


@pytest.fixture(scope="module")
def auth_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "alice@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


# ── get_subscription ──────────────────────────────────────────────────────────

class TestGetSubscription:
    def test_returns_none_when_db_unavailable(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: None)
        assert repo.get_subscription("alice@rico.ai") is None

    def test_returns_none_when_no_record(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: _mock_db_with_row(None))
        assert repo.get_subscription("alice@rico.ai") is None

    def test_returns_dict_when_record_exists(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: _mock_db_with_row(_fake_row()))
        result = repo.get_subscription("alice@rico.ai")
        assert result is not None
        assert result["plan"] == "pro"
        assert result["status"] == "active"
        assert result["paddle_customer_id"] == "ctm_test"

    def test_returns_none_on_db_exception(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        bad_db = MagicMock()
        bad_db.available = True
        bad_db.connect.side_effect = Exception("connection refused")
        monkeypatch.setattr(repo, "_db", lambda: bad_db)
        assert repo.get_subscription("alice@rico.ai") is None

    def test_returns_premium_row(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "_db",
            lambda: _mock_db_with_row(_fake_row(plan="premium", status="active")),
        )
        result = repo.get_subscription("alice@rico.ai")
        assert result["plan"] == "premium"


# ── event idempotency ─────────────────────────────────────────────────────────

class TestEventIdempotency:
    def test_returns_false_when_db_unavailable(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: None)
        assert repo.event_already_processed("evt_123") is False

    def test_returns_false_when_event_not_found(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: _mock_db_with_row(None))
        assert repo.event_already_processed("evt_123") is False

    def test_returns_true_when_event_processed(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: _mock_db_with_row({"status": "processed"}))
        assert repo.event_already_processed("evt_123") is True

    def test_returns_false_when_event_pending(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: _mock_db_with_row({"status": "pending"}))
        assert repo.event_already_processed("evt_123") is False

    def test_returns_false_on_db_exception(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        bad_db = MagicMock()
        bad_db.available = True
        bad_db.connect.side_effect = Exception("timeout")
        monkeypatch.setattr(repo, "_db", lambda: bad_db)
        assert repo.event_already_processed("evt_123") is False


class TestGetSubscriptionEventStatus:
    def test_returns_none_when_db_unavailable(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: None)
        assert repo.get_subscription_event_status("evt_123") is None

    def test_returns_none_when_event_missing(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: _mock_db_with_row(None))
        assert repo.get_subscription_event_status("evt_123") is None

    @pytest.mark.parametrize("status", ["processed", "pending", "failed"])
    def test_returns_existing_status(self, monkeypatch, status):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db", lambda: _mock_db_with_row({"status": status}))
        assert repo.get_subscription_event_status("evt_123") == status

    def test_returns_none_on_db_exception(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        bad_db = MagicMock()
        bad_db.available = True
        bad_db.connect.side_effect = Exception("timeout")
        monkeypatch.setattr(repo, "_db", lambda: bad_db)
        assert repo.get_subscription_event_status("evt_123") is None


# ── /me endpoint: Free fallback ───────────────────────────────────────────────

class TestMeEndpointFreeFallback:
    def test_returns_free_inactive_when_no_db_subscription(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "get_subscription", lambda uid: None)

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is False
        assert body["plan"] is None
        assert body["subscription"]["user_id"] == "alice@rico.ai"
        assert body["subscription"]["plan"] == "free"
        assert body["subscription"]["subscription_status"] == "inactive"
        assert body["subscription"]["entitlements"]["monthly_ai_message_limit"] == 50
        assert body["subscription"]["entitlements"]["premium_recommendations_enabled"] is False


# ── /me endpoint: DB-backed active subscriptions ─────────────────────────────

class TestMeEndpointDbBacked:
    def test_returns_active_pro_from_db(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="pro", status="active"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is True
        assert body["subscription"]["plan"] == "pro"
        assert body["subscription"]["subscription_status"] == "active"
        assert body["subscription"]["paddle_customer_id"] == "ctm_test"
        assert body["plan"]["price_monthly"] == 29
        assert body["plan"]["currency"] == "AED"
        assert body["subscription"]["entitlements"]["monthly_ai_message_limit"] == 300
        assert body["subscription"]["entitlements"]["saved_jobs_limit"] == 100
        assert body["subscription"]["entitlements"]["premium_recommendations_enabled"] is False

    def test_returns_active_premium_from_db(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="premium", status="active"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is True
        assert body["subscription"]["plan"] == "premium"
        assert body["plan"]["price_monthly"] == 49
        assert body["subscription"]["entitlements"]["monthly_ai_message_limit"] == 1500
        assert body["subscription"]["entitlements"]["saved_jobs_limit"] is None
        assert body["subscription"]["entitlements"]["premium_recommendations_enabled"] is True
        assert body["subscription"]["entitlements"]["application_automation_enabled"] is True

    def test_is_active_false_when_subscription_canceled(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="pro", status="canceled"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is False
        assert body["subscription"]["plan"] == "pro"
        assert body["subscription"]["subscription_status"] == "canceled"

    def test_is_active_false_when_subscription_past_due(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="pro", status="past_due"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is False
        assert body["subscription"]["subscription_status"] == "past_due"

    def test_falls_back_to_free_on_unknown_plan_in_db(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="enterprise", status="active"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["subscription"]["plan"] == "free"
        assert body["is_active"] is False

    def test_canceled_pro_uses_free_entitlements(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="pro", status="canceled"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is False
        ent = body["subscription"]["entitlements"]
        assert ent["monthly_ai_message_limit"] == 50
        assert ent["saved_jobs_limit"] == 10
        assert ent["premium_recommendations_enabled"] is False

    def test_past_due_pro_uses_free_entitlements(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="pro", status="past_due"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is False
        ent = body["subscription"]["entitlements"]
        assert ent["monthly_ai_message_limit"] == 50

    def test_canceled_premium_uses_free_entitlements(self, auth_client, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(plan="premium", status="canceled"),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is False
        ent = body["subscription"]["entitlements"]
        assert ent["monthly_ai_message_limit"] == 50
        assert ent["application_automation_enabled"] is False


# ── record_subscription_event: insert vs duplicate ───────────────────────────

class TestRecordSubscriptionEvent:
    def _make_transaction_mock(self, rowcount: int):
        """Build a _db_transaction context manager mock that yields a conn with cursor rowcount."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = rowcount

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        from contextlib import contextmanager

        @contextmanager
        def fake_transaction():
            yield mock_conn

        return fake_transaction

    def test_returns_true_on_fresh_insert(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db_transaction", self._make_transaction_mock(rowcount=1))
        result = repo.record_subscription_event("evt_new", "transaction.completed")
        assert result is True

    def test_returns_false_on_duplicate(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db_transaction", self._make_transaction_mock(rowcount=0))
        result = repo.record_subscription_event("evt_dup", "transaction.completed")
        assert result is False

    def test_returns_false_when_db_unavailable(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        from contextlib import contextmanager

        @contextmanager
        def no_db():
            yield None

        monkeypatch.setattr(repo, "_db_transaction", no_db)
        result = repo.record_subscription_event("evt_any", "transaction.completed")
        assert result is False

    def test_returns_false_on_db_exception(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        from contextlib import contextmanager

        @contextmanager
        def exploding():
            raise Exception("db down")
            yield  # noqa: unreachable

        monkeypatch.setattr(repo, "_db_transaction", exploding)
        result = repo.record_subscription_event("evt_err", "transaction.completed")
        assert result is False

    def test_returns_true_when_reclaiming_failed_event(self, monkeypatch):
        # ON CONFLICT DO UPDATE WHERE status='failed' fires → rowcount=1 → re-claim succeeds
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db_transaction", self._make_transaction_mock(rowcount=1))
        result = repo.record_subscription_event("evt_retry", "transaction.completed")
        assert result is True

    def test_returns_false_when_event_is_in_progress(self, monkeypatch):
        # Another worker holds status='pending' → DO UPDATE WHERE condition is false → rowcount=0
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(repo, "_db_transaction", self._make_transaction_mock(rowcount=0))
        result = repo.record_subscription_event("evt_inprog", "transaction.completed")
        assert result is False


class TestUpsertSubscriptionOverrides:
    def test_entitlement_override_params_default_to_none(self, monkeypatch):
        import src.repositories.subscription_repo as repo

        executed: list = []
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = _fake_row()
        mock_cursor.execute.side_effect = lambda sql, params: executed.append(params)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        from contextlib import contextmanager

        @contextmanager
        def fake_transaction():
            yield mock_conn

        monkeypatch.setattr(repo, "_db_transaction", fake_transaction)

        result = repo.upsert_subscription("alice@rico.ai", plan="pro", status="active")

        assert result is not None
        params = executed[0]
        assert params[-5:] == (None, None, None, None, None)


# ── update_subscription_event_status ─────────────────────────────────────────

class TestUpdateSubscriptionEventStatus:
    def _make_capture_mock(self):
        """Return (fake_transaction, executed_params_list)."""
        executed: list = []

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.execute.side_effect = lambda sql, params: executed.append(params)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        from contextlib import contextmanager

        @contextmanager
        def fake_transaction():
            yield mock_conn

        return fake_transaction, executed

    def test_updates_to_processed(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        txn, executed = self._make_capture_mock()
        monkeypatch.setattr(repo, "_db_transaction", txn)
        result = repo.update_subscription_event_status("evt_123", "processed")
        assert result is True
        assert executed[0] == ("processed", None, "evt_123")

    def test_updates_to_failed_with_error_detail(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        txn, executed = self._make_capture_mock()
        monkeypatch.setattr(repo, "_db_transaction", txn)
        result = repo.update_subscription_event_status("evt_err", "failed", error_detail="DB timeout")
        assert result is True
        assert executed[0] == ("failed", "DB timeout", "evt_err")

    def test_no_op_when_db_unavailable(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        from contextlib import contextmanager

        @contextmanager
        def no_db():
            yield None

        monkeypatch.setattr(repo, "_db_transaction", no_db)
        assert repo.update_subscription_event_status("evt_any", "processed") is False

    def test_no_op_on_db_exception(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        from contextlib import contextmanager

        @contextmanager
        def exploding():
            raise Exception("network error")
            yield  # noqa: unreachable

        monkeypatch.setattr(repo, "_db_transaction", exploding)
        assert repo.update_subscription_event_status("evt_any", "processed") is False

    def test_returns_false_when_no_event_row_updated(self, monkeypatch):
        import src.repositories.subscription_repo as repo
        txn, _ = self._make_capture_mock()

        from contextlib import contextmanager

        @contextmanager
        def fake_transaction():
            with txn() as conn:
                cur_cm = conn.cursor.return_value
                cur = cur_cm.__enter__()
                cur.rowcount = 0
                yield conn

        monkeypatch.setattr(repo, "_db_transaction", fake_transaction)
        assert repo.update_subscription_event_status("evt_missing", "processed") is False


# ── DB entitlement columns do not override plan definitions by default ─────────

class TestDbEntitlementsNotUsedByDefault:
    def test_db_entitlements_ignored_for_active_pro(self, auth_client, monkeypatch):
        """DB entitlement columns are ignored; plan definitions are used."""
        import src.repositories.subscription_repo as repo
        # Simulate DB having different entitlement values than plan definition
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(
                plan="pro",
                status="active",
                monthly_ai_message_limit=999,  # Different from plan definition (300)
                saved_jobs_limit=888,  # Different from plan definition (100)
            ),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        # Should use plan definition values, not DB values
        assert body["subscription"]["entitlements"]["monthly_ai_message_limit"] == 300
        assert body["subscription"]["entitlements"]["saved_jobs_limit"] == 100

    def test_db_entitlements_ignored_for_active_premium(self, auth_client, monkeypatch):
        """DB entitlement columns are ignored; plan definitions are used."""
        import src.repositories.subscription_repo as repo
        monkeypatch.setattr(
            repo, "get_subscription",
            lambda uid: _fake_row(
                plan="premium",
                status="active",
                monthly_ai_message_limit=5000,  # Different from plan definition (1500)
                premium_recommendations_enabled=False,  # Different from plan definition (True)
            ),
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        # Should use plan definition values, not DB values
        assert body["subscription"]["entitlements"]["monthly_ai_message_limit"] == 1500
        assert body["subscription"]["entitlements"]["premium_recommendations_enabled"] is True


# ── subscription_events status defaults to pending ───────────────────────────────

class TestSubscriptionEventsDefaultStatus:
    def _make_capture_mock(self):
        """Return (fake_transaction, executed_sql_list)."""
        executed: list = []

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1  # Simulate successful insert
        mock_cursor.execute.side_effect = lambda sql, params: executed.append(sql)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        from contextlib import contextmanager

        @contextmanager
        def fake_transaction():
            yield mock_conn

        return fake_transaction, executed

    def test_new_event_inserted_with_pending_status(self, monkeypatch):
        """New subscription_events rows default to status='pending'."""
        import src.repositories.subscription_repo as repo
        txn, executed = self._make_capture_mock()
        monkeypatch.setattr(repo, "_db_transaction", txn)
        repo.record_subscription_event("evt_new", "transaction.completed")

        # Check that the INSERT uses DEFAULT 'pending' for status column
        insert_sql = executed[0]
        assert "status" in insert_sql  # status column should be in the INSERT
        assert "'pending'" in insert_sql  # default value should be 'pending'

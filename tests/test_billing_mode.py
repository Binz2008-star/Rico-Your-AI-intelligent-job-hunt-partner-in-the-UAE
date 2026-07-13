"""Tests for BILLING_MODE guard and admin subscription activation."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def user_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "bob@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


@pytest.fixture(scope="module")
def admin_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "admin@rico.ai", "role": "admin"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


# ── Billing mode helper unit tests ────────────────────────────────────────────

class TestBillingModeHelpers:
    def test_manual_is_default(self, monkeypatch):
        monkeypatch.delenv("BILLING_MODE", raising=False)
        from src.billing_mode import is_manual_billing_mode, is_paddle_billing_mode
        assert is_manual_billing_mode() is True
        assert is_paddle_billing_mode() is False

    def test_explicit_manual(self, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "manual")
        from importlib import reload
        import src.billing_mode as bm
        reload(bm)
        assert bm.is_manual_billing_mode() is True
        assert bm.is_paddle_billing_mode() is False

    def test_explicit_paddle(self, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "paddle")
        from importlib import reload
        import src.billing_mode as bm
        reload(bm)
        assert bm.is_manual_billing_mode() is False
        assert bm.is_paddle_billing_mode() is True


# ── Admin subscription activation ─────────────────────────────────────────────

class TestAdminSubscriptionActivation:
    def _mock_user(self, monkeypatch, email: str = "target@rico.ai"):
        from src.repositories.users_repo import User

        fake_user = User(
            id=42,
            email=email,
            password_hash="x",
            role="user",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            last_login_at=None,
        )
        monkeypatch.setattr(
            "src.repositories.users_repo.get_user_by_email",
            lambda e: fake_user if e == email else None,
        )
        return fake_user

    def _mock_upsert(self, monkeypatch):
        calls: list = []

        def fake_upsert(db_module, *, user_id, plan, status, **kwargs):
            calls.append({"user_id": user_id, "plan": plan, "status": status, **kwargs})
            return {"user_id": user_id, "plan": plan, "status": status}

        monkeypatch.setattr(
            "src.repositories.paddle_repo.upsert_paddle_subscription",
            fake_upsert,
        )
        return calls

    def test_admin_can_activate_pro_subscription(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: True)
        self._mock_user(monkeypatch)
        calls = self._mock_upsert(monkeypatch)

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={
                "email": "target@rico.ai",
                "plan": "pro",
                "duration_days": 30,
                "payment_reference": "ref_001",
            },
        )

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["email"] == "target@rico.ai"
        assert body["plan"] == "pro"
        assert body["status"] == "active"
        assert body["expires_at"] is not None
        assert len(calls) == 1
        assert calls[0]["plan"] == "pro"
        assert calls[0]["status"] == "active"

    def test_admin_rejects_premium_plan(self, admin_client, monkeypatch):
        """Single-plan scope: 'premium' is not a valid activation target."""
        self._mock_user(monkeypatch)

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "premium", "duration_days": 90},
        )

        assert r.status_code == 422

    def test_non_admin_cannot_activate(self, user_client, monkeypatch):
        self._mock_user(monkeypatch)

        r = user_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 403

    def test_unauthenticated_cannot_activate(self, client, monkeypatch):
        r = client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 401

    def test_unknown_user_returns_404(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: True)
        monkeypatch.setattr(
            "src.repositories.users_repo.get_user_by_email",
            lambda e: None,
        )

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "ghost@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 404

    def test_invalid_duration_rejected(self, admin_client, monkeypatch):
        self._mock_user(monkeypatch)

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 0},
        )

        assert r.status_code == 422

    def test_db_unavailable_returns_503(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: False)

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 503
        assert "database unavailable" in r.json()["detail"].lower()

    def test_upsert_failure_returns_503(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: True)
        self._mock_user(monkeypatch)
        monkeypatch.setattr(
            "src.repositories.paddle_repo.upsert_paddle_subscription",
            lambda *a, **kw: None,
        )

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 503


# ── Pricing validation ─────────────────────────────────────────────────────────

class TestPricingValues:
    def test_rico_monthly_price_is_79_aed_by_default(self, monkeypatch):
        monkeypatch.delenv("RICO_PRO_PRICE_AED", raising=False)

        from fastapi.testclient import TestClient
        from src.api.app import app

        with TestClient(app) as c:
            plans = c.get("/api/v1/subscription/plans").json()["plans"]

        assert len(plans) == 1
        assert plans[0]["price_monthly"] == 79
        assert plans[0]["currency"] == "AED"
        assert plans[0]["name"] == "Rico Monthly"

    def test_rico_monthly_is_popular_flag(self):
        from fastapi.testclient import TestClient
        from src.api.app import app

        with TestClient(app) as c:
            plans = c.get("/api/v1/subscription/plans").json()["plans"]

        assert plans[0]["is_popular"] is True

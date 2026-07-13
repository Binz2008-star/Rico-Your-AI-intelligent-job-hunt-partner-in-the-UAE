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


# ── Manual mode blocks Paddle checkout ────────────────────────────────────────

class TestManualModeBlocksCheckout:
    def test_checkout_returns_whatsapp_redirect_in_manual_mode(self, user_client, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "manual")
        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")
        monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_test_pro")

        r = user_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "manual"
        assert body["status"] == "manual"

    def test_portal_returns_403_in_manual_mode(self, user_client, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "manual")
        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")

        r = user_client.post("/api/v1/subscription/portal")

        assert r.status_code == 403
        detail = r.json()["detail"].lower()
        assert "online checkout is not enabled" in detail

    def test_checkout_passes_in_paddle_mode(self, user_client, monkeypatch):
        calls: list = []

        def fake_create_transaction_checkout(**kwargs):
            calls.append(kwargs)
            return "https://checkout.paddle.com/c/pay/txn_test_ok"

        monkeypatch.setenv("BILLING_MODE", "paddle")
        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")
        monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_pro_test")
        monkeypatch.setattr(
            "src.services.paddle_client.create_transaction_checkout",
            fake_create_transaction_checkout,
        )

        r = user_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        assert r.json()["checkout_url"] == "https://checkout.paddle.com/c/pay/txn_test_ok"
        assert r.json()["provider"] == "paddle"
        assert len(calls) == 1

    def test_premium_checkout_returns_whatsapp_redirect_in_manual_mode(self, user_client, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "manual")
        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")
        monkeypatch.setenv("PADDLE_PREMIUM_PRICE_ID", "pri_test_premium")

        r = user_client.post("/api/v1/subscription/checkout", json={"plan": "premium"})

        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "manual"
        assert body["status"] == "manual"

    def test_checkout_requires_auth(self, client, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "manual")

        r = client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 401


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

        def fake_upsert(user_id, *, plan, status, **kwargs):
            calls.append({"user_id": user_id, "plan": plan, "status": status, **kwargs})
            return {"user_id": user_id, "plan": plan, "status": status}

        monkeypatch.setattr(
            "src.repositories.subscription_repo.upsert_subscription",
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

    def test_admin_can_activate_premium_subscription(self, admin_client, monkeypatch):
        monkeypatch.setattr("src.db.is_db_available", lambda: True)
        self._mock_user(monkeypatch)
        self._mock_upsert(monkeypatch)

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "premium", "duration_days": 90},
        )

        assert r.status_code == 200
        assert r.json()["plan"] == "premium"

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
            "src.repositories.subscription_repo.upsert_subscription",
            lambda *a, **kw: None,
        )

        r = admin_client.post(
            "/api/v1/admin/subscriptions/activate",
            json={"email": "target@rico.ai", "plan": "pro", "duration_days": 30},
        )

        assert r.status_code == 503


# ── Pricing validation ─────────────────────────────────────────────────────────

class TestPricingValues:
    def test_pro_price_is_29_by_default(self, monkeypatch):
        monkeypatch.delenv("RICO_PRO_PRICE_AED", raising=False)
        monkeypatch.delenv("RICO_PREMIUM_PRICE_AED", raising=False)

        r = __import__("fastapi.testclient", fromlist=["TestClient"])
        from fastapi.testclient import TestClient
        from src.api.app import app

        with TestClient(app) as c:
            plans = c.get("/api/v1/subscription/plans").json()["plans"]

        pro = next(p for p in plans if p["plan"] == "pro")
        premium = next(p for p in plans if p["plan"] == "premium")
        assert pro["price_monthly"] == 29
        assert premium["price_monthly"] == 49

    def test_pro_is_popular_flag(self, monkeypatch):
        from fastapi.testclient import TestClient
        from src.api.app import app

        with TestClient(app) as c:
            plans = c.get("/api/v1/subscription/plans").json()["plans"]

        pro = next(p for p in plans if p["plan"] == "pro")
        premium = next(p for p in plans if p["plan"] == "premium")
        assert pro["is_popular"] is True
        assert premium["is_popular"] is False

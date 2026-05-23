from __future__ import annotations

import os
import sys

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
def auth_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "alice@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _plan_by_name(plans: list[dict], plan: str) -> dict:
    return next(item for item in plans if item["plan"] == plan)


class TestSubscriptionPlans:
    def test_plans_endpoint_returns_two_paid_plans(self, client):
        r = client.get("/api/v1/subscription/plans")

        assert r.status_code == 200
        plans = r.json()["plans"]
        assert [plan["plan"] for plan in plans] == ["pro", "premium"]
        assert [plan["price_monthly"] for plan in plans] == [50, 150]
        assert all(plan["currency"] == "AED" for plan in plans)

    def test_pro_entitlement_shape(self, client):
        plans = client.get("/api/v1/subscription/plans").json()["plans"]
        entitlements = _plan_by_name(plans, "pro")["entitlements"]

        assert entitlements == {
            "monthly_ai_message_limit": 300,
            "saved_jobs_limit": 100,
            "profile_optimization_limit": 20,
            "premium_recommendations_enabled": False,
            "application_automation_enabled": False,
        }

    def test_premium_entitlement_shape(self, client):
        plans = client.get("/api/v1/subscription/plans").json()["plans"]
        entitlements = _plan_by_name(plans, "premium")["entitlements"]

        assert entitlements == {
            "monthly_ai_message_limit": 1500,
            "saved_jobs_limit": None,
            "profile_optimization_limit": 100,
            "premium_recommendations_enabled": True,
            "application_automation_enabled": True,
        }


class TestCurrentSubscription:
    def test_current_user_subscription_endpoint_defaults_to_free_inactive(self, auth_client):
        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is False
        assert body["plan"] is None
        assert body["subscription"]["user_id"] == "alice@rico.ai"
        assert body["subscription"]["plan"] == "free"
        assert body["subscription"]["subscription_status"] == "inactive"
        assert body["subscription"]["entitlements"]["premium_recommendations_enabled"] is False
        assert body["subscription"]["entitlements"]["application_automation_enabled"] is False


class TestSubscriptionCheckout:
    def test_checkout_returns_mock_url_without_stripe_env(self, auth_client, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_PRO_MONTHLY", raising=False)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "mock"
        assert body["status"] == "mock"
        assert body["plan"] == "pro"
        assert "checkout_url" in body
        assert "plan=pro" in body["checkout_url"]
        assert "alice@rico.ai" not in body["checkout_url"]
        assert "STRIPE" not in body["checkout_url"]

    def test_checkout_rejects_free_plan(self, auth_client):
        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "free"})

        assert r.status_code == 422


class TestSubscriptionWebhook:
    def test_webhook_basic_handling_without_stripe_secret(self, client, monkeypatch):
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

        r = client.post(
            "/api/v1/subscription/webhook",
            json={
                "id": "evt_test_123",
                "type": "checkout.session.completed",
                "data": {"object": {"customer": "cus_test"}},
            },
        )

        assert r.status_code == 200
        assert r.json() == {
            "received": True,
            "provider": "stripe",
            "event_type": "checkout.session.completed",
            "processed": True,
            "mock": True,
        }

    def test_webhook_validates_required_event_shape(self, client):
        r = client.post("/api/v1/subscription/webhook", json={"type": "checkout.session.completed"})

        assert r.status_code == 422

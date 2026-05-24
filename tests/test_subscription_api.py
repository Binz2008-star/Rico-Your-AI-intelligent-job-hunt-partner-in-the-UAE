from __future__ import annotations

import os
import sys
from types import SimpleNamespace

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


def _fake_stripe(calls: list[dict], checkout_url: str):
    class FakeSession:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return {"url": checkout_url}

    return SimpleNamespace(api_key=None, checkout=SimpleNamespace(Session=FakeSession))


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
        monkeypatch.delenv("STRIPE_PRO_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_PRO", raising=False)

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

    def test_checkout_creates_real_stripe_session_when_env_exists(self, auth_client, monkeypatch):
        calls = []

        fake_stripe = _fake_stripe(calls, "https://checkout.stripe.com/c/pay/cs_test_123")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_safe")
        monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_1TaF8vDjGoun5ROblbcE7iIU")
        monkeypatch.setenv("FRONTEND_URL", "https://ricohunt.com")
        monkeypatch.setattr("src.subscription_plans._load_stripe", lambda: fake_stripe)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        body = r.json()
        assert body == {
            "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_123",
            "provider": "stripe",
            "plan": "pro",
            "status": "ready",
        }
        assert fake_stripe.api_key == "sk_test_safe"
        assert calls[0]["mode"] == "subscription"
        assert calls[0]["line_items"] == [{"price": "price_1TaF8vDjGoun5ROblbcE7iIU", "quantity": 1}]
        assert calls[0]["customer_email"] == "alice@rico.ai"
        assert calls[0]["metadata"] == {"user_id": "alice@rico.ai", "plan": "pro"}
        assert calls[0]["success_url"] == "https://ricohunt.com/subscription/success?session_id={CHECKOUT_SESSION_ID}"

    def test_checkout_uses_premium_stripe_price_id(self, auth_client, monkeypatch):
        calls = []

        fake_stripe = _fake_stripe(calls, "https://checkout.stripe.com/c/pay/cs_test_premium")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_safe")
        monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_1TaF9bDjGoun5RObstpVAVSs")
        monkeypatch.setattr("src.subscription_plans._load_stripe", lambda: fake_stripe)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "premium"})

        assert r.status_code == 200
        assert r.json()["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_premium"
        assert calls[0]["line_items"] == [{"price": "price_1TaF9bDjGoun5RObstpVAVSs", "quantity": 1}]

    def test_checkout_falls_back_to_legacy_pro_price_env(self, auth_client, monkeypatch):
        calls = []

        fake_stripe = _fake_stripe(calls, "https://checkout.stripe.com/c/pay/cs_test_pro_legacy")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_safe")
        monkeypatch.delenv("STRIPE_PRO_PRICE_ID", raising=False)
        monkeypatch.setenv("STRIPE_PRICE_PRO", "price_legacy_pro")
        monkeypatch.setattr("src.subscription_plans._load_stripe", lambda: fake_stripe)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        assert r.json()["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_pro_legacy"
        assert calls[0]["line_items"] == [{"price": "price_legacy_pro", "quantity": 1}]

    def test_checkout_falls_back_to_legacy_premium_price_env(self, auth_client, monkeypatch):
        calls = []

        fake_stripe = _fake_stripe(calls, "https://checkout.stripe.com/c/pay/cs_test_premium_legacy")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_safe")
        monkeypatch.delenv("STRIPE_PREMIUM_PRICE_ID", raising=False)
        monkeypatch.setenv("STRIPE_PRICE_PREMIUM", "price_legacy_premium")
        monkeypatch.setattr("src.subscription_plans._load_stripe", lambda: fake_stripe)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "premium"})

        assert r.status_code == 200
        assert r.json()["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_premium_legacy"
        assert calls[0]["line_items"] == [{"price": "price_legacy_premium", "quantity": 1}]

    def test_checkout_prefers_new_price_env_over_legacy_env(self, auth_client, monkeypatch):
        calls = []

        fake_stripe = _fake_stripe(calls, "https://checkout.stripe.com/c/pay/cs_test_preferred")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_safe")
        monkeypatch.setenv("STRIPE_PRO_PRICE_ID", "price_new_pro")
        monkeypatch.setenv("STRIPE_PRICE_PRO", "price_legacy_pro")
        monkeypatch.setattr("src.subscription_plans._load_stripe", lambda: fake_stripe)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        assert calls[0]["line_items"] == [{"price": "price_new_pro", "quantity": 1}]

    def test_checkout_returns_mock_when_secret_exists_but_price_missing(self, auth_client, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_safe")
        monkeypatch.delenv("STRIPE_PRO_PRICE_ID", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_PRO", raising=False)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        assert r.json()["provider"] == "mock"
        assert r.json()["checkout_url"] == "https://checkout.ricohunt.com/mock?plan=pro"

    def test_checkout_rejects_free_plan(self, auth_client):
        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "free"})

        assert r.status_code == 422


class TestCustomerPortal:
    def test_portal_returns_mock_without_stripe_secret(self, auth_client, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

        r = auth_client.post("/api/v1/subscription/portal")

        assert r.status_code == 200
        assert r.json() == {
            "checkout_url": "",
            "provider": "mock",
            "plan": "free",
            "status": "mock",
        }


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

    def test_webhook_verifies_stripe_signature_when_secret_exists(self, client, monkeypatch):
        calls = []

        class FakeWebhook:
            @staticmethod
            def construct_event(payload, signature, secret):
                calls.append((payload, signature, secret))
                return {
                    "id": "evt_verified",
                    "type": "customer.subscription.updated",
                    "data": {"object": {"id": "sub_test"}},
                }

        fake_stripe = SimpleNamespace(Webhook=FakeWebhook)
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_safe")
        monkeypatch.setattr("src.subscription_plans._load_stripe", lambda: fake_stripe)
        monkeypatch.setattr(
            "src.services.subscription_webhook_service.process_stripe_event",
            lambda **kwargs: True,
        )

        r = client.post(
            "/api/v1/subscription/webhook",
            headers={"stripe-signature": "t=123,v1=safe"},
            json={
                "id": "evt_raw",
                "type": "customer.subscription.updated",
                "data": {"object": {"id": "sub_test"}},
            },
        )

        assert r.status_code == 200
        assert r.json() == {
            "received": True,
            "provider": "stripe",
            "event_type": "customer.subscription.updated",
            "processed": True,
            "mock": False,
        }
        assert calls[0][1] == "t=123,v1=safe"
        assert calls[0][2] == "whsec_safe"

    def test_webhook_requires_signature_when_secret_exists(self, client, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_safe")

        r = client.post(
            "/api/v1/subscription/webhook",
            json={
                "id": "evt_raw",
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_test"}},
            },
        )

        assert r.status_code == 400
        assert r.json()["detail"] == "Stripe webhook signature is required"

    def test_webhook_validates_required_event_shape(self, client):
        r = client.post("/api/v1/subscription/webhook", json={"type": "checkout.session.completed"})

        assert r.status_code == 422

    def test_webhook_processing_error_returns_retryable_500(self, client, monkeypatch):
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        monkeypatch.setattr(
            "src.api.routers.subscription.handle_subscription_webhook",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
        )

        r = client.post(
            "/api/v1/subscription/webhook",
            json={
                "id": "evt_retryable",
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_test"}},
            },
        )

        assert r.status_code == 500
        assert r.json()["detail"] == "Stripe webhook processing failed"

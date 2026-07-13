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
        assert [plan["price_monthly"] for plan in plans] == [29, 49]
        assert all(plan["currency"] == "AED" for plan in plans)

    def test_pro_entitlement_shape(self, client):
        plans = client.get("/api/v1/subscription/plans").json()["plans"]
        entitlements = _plan_by_name(plans, "pro")["entitlements"]

        assert entitlements == {
            "monthly_ai_message_limit": 300,
            "saved_jobs_limit": 100,
            "profile_optimization_limit": 20,
            "cv_storage_limit": 5,
            "other_document_limit": 10,
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
            "cv_storage_limit": None,
            "other_document_limit": None,
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
    @pytest.fixture(autouse=True)
    def paddle_mode(self, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "paddle")

    def test_checkout_returns_503_without_paddle_env(self, auth_client, monkeypatch):
        monkeypatch.delenv("PADDLE_API_KEY", raising=False)
        monkeypatch.delenv("PADDLE_PRO_PRICE_ID", raising=False)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 503
        assert "not available" in r.json()["detail"].lower()

    def test_checkout_creates_real_paddle_transaction_when_env_exists(self, auth_client, monkeypatch):
        calls = []

        def fake_create_transaction_checkout(**kwargs):
            calls.append(kwargs)
            return "https://checkout.paddle.com/c/pay/txn_test_123"

        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")
        monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_01hxpro")
        monkeypatch.setenv("FRONTEND_URL", "https://ricohunt.com")
        monkeypatch.setattr(
            "src.services.paddle_client.create_transaction_checkout",
            fake_create_transaction_checkout,
        )

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 200
        body = r.json()
        assert body == {
            "checkout_url": "https://checkout.paddle.com/c/pay/txn_test_123",
            "provider": "paddle",
            "plan": "pro",
            "status": "ready",
        }
        assert calls[0]["price_id"] == "pri_01hxpro"
        assert calls[0]["user_id"] == "alice@rico.ai"
        assert calls[0]["plan"] == "pro"
        assert calls[0]["success_url"] == "https://ricohunt.com/subscription/success?session_id={CHECKOUT_SESSION_ID}"

    def test_checkout_uses_premium_paddle_price_id(self, auth_client, monkeypatch):
        calls = []

        def fake_create_transaction_checkout(**kwargs):
            calls.append(kwargs)
            return "https://checkout.paddle.com/c/pay/txn_test_premium"

        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")
        monkeypatch.setenv("PADDLE_PREMIUM_PRICE_ID", "pri_01hxpremium")
        monkeypatch.setattr(
            "src.services.paddle_client.create_transaction_checkout",
            fake_create_transaction_checkout,
        )

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "premium"})

        assert r.status_code == 200
        assert r.json()["checkout_url"] == "https://checkout.paddle.com/c/pay/txn_test_premium"
        assert calls[0]["price_id"] == "pri_01hxpremium"

    def test_checkout_returns_503_when_key_exists_but_price_missing(self, auth_client, monkeypatch):
        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")
        monkeypatch.delenv("PADDLE_PRO_PRICE_ID", raising=False)

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 503
        assert "not available" in r.json()["detail"].lower()

    def test_checkout_returns_502_when_paddle_request_fails(self, auth_client, monkeypatch):
        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")
        monkeypatch.setenv("PADDLE_PRO_PRICE_ID", "pri_01hxpro")
        monkeypatch.setattr(
            "src.services.paddle_client.create_transaction_checkout",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Paddle transaction request failed (status 400)")),
        )

        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})

        assert r.status_code == 502

    def test_checkout_rejects_free_plan(self, auth_client):
        r = auth_client.post("/api/v1/subscription/checkout", json={"plan": "free"})

        assert r.status_code == 422


class TestCustomerPortal:
    @pytest.fixture(autouse=True)
    def paddle_mode(self, monkeypatch):
        monkeypatch.setenv("BILLING_MODE", "paddle")

    def test_portal_not_yet_available_in_paddle_mode(self, auth_client, monkeypatch):
        monkeypatch.setenv("PADDLE_API_KEY", "pdl_test_safe")

        r = auth_client.post("/api/v1/subscription/portal")

        assert r.status_code == 501


class TestSubscriptionWebhook:
    def test_webhook_basic_handling_without_paddle_secret(self, client, monkeypatch):
        monkeypatch.delenv("PADDLE_WEBHOOK_SECRET", raising=False)

        r = client.post(
            "/api/v1/subscription/webhook",
            json={
                "id": "evt_test_123",
                "type": "transaction.completed",
                "data": {"customer_id": "ctm_test"},
            },
        )

        assert r.status_code == 200
        assert r.json() == {
            "received": True,
            "provider": "paddle",
            "event_type": "transaction.completed",
            "processed": True,
            "mock": True,
        }

    def test_webhook_verifies_paddle_signature_when_secret_exists(self, client, monkeypatch):
        calls = []

        monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_safe")
        monkeypatch.setattr(
            "src.services.paddle_client.verify_webhook_signature",
            lambda body, sig, secret: calls.append((body, sig, secret)) or True,
        )
        monkeypatch.setattr(
            "src.services.subscription_webhook_service.process_paddle_event",
            lambda **kwargs: True,
        )

        r = client.post(
            "/api/v1/subscription/webhook",
            headers={"paddle-signature": "ts=123;h1=safe"},
            json={
                "event_id": "evt_verified",
                "event_type": "subscription.updated",
                "data": {"id": "sub_test"},
            },
        )

        assert r.status_code == 200
        assert r.json() == {
            "received": True,
            "provider": "paddle",
            "event_type": "subscription.updated",
            "processed": True,
            "mock": False,
        }
        assert calls[0][1] == "ts=123;h1=safe"
        assert calls[0][2] == "pdl_ntfset_safe"

    def test_webhook_rejects_invalid_signature(self, client, monkeypatch):
        monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_safe")
        monkeypatch.setattr(
            "src.services.paddle_client.verify_webhook_signature",
            lambda body, sig, secret: False,
        )

        r = client.post(
            "/api/v1/subscription/webhook",
            headers={"paddle-signature": "ts=123;h1=bad"},
            json={
                "event_id": "evt_raw",
                "event_type": "transaction.completed",
                "data": {"id": "txn_test"},
            },
        )

        assert r.status_code == 400
        assert r.json()["detail"] == "Paddle webhook signature verification failed"

    def test_webhook_requires_signature_when_secret_exists(self, client, monkeypatch):
        monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfset_safe")

        r = client.post(
            "/api/v1/subscription/webhook",
            json={
                "id": "evt_raw",
                "type": "transaction.completed",
                "data": {"id": "txn_test"},
            },
        )

        assert r.status_code == 400
        assert r.json()["detail"] == "Paddle webhook signature is required"

    def test_webhook_validates_required_event_shape(self, client):
        r = client.post("/api/v1/subscription/webhook", json={"type": "transaction.completed"})

        assert r.status_code == 422

    def test_webhook_processing_error_returns_retryable_500(self, client, monkeypatch):
        monkeypatch.delenv("PADDLE_WEBHOOK_SECRET", raising=False)
        monkeypatch.setattr(
            "src.api.routers.subscription.handle_subscription_webhook",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
        )

        r = client.post(
            "/api/v1/subscription/webhook",
            json={
                "id": "evt_retryable",
                "type": "transaction.completed",
                "data": {"id": "txn_test"},
            },
        )

        assert r.status_code == 500
        assert r.json()["detail"] == "Paddle webhook processing failed"

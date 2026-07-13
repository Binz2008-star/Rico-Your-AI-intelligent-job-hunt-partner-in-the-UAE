"""Tests for the read-only /api/v1/subscription/* endpoints (plans, me).

Checkout, portal, and webhook processing moved to /api/v1/billing/paddle/*
(see src/api/routers/paddle_billing.py) and are covered in
tests/test_paddle_billing.py — this file only covers the plan catalog and
current-user status, both backed by src.subscription_plans (Paddle-sourced).
"""
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


class TestSubscriptionPlans:
    def test_plans_endpoint_returns_single_plan(self, client):
        r = client.get("/api/v1/subscription/plans")

        assert r.status_code == 200
        plans = r.json()["plans"]
        assert [plan["plan"] for plan in plans] == ["pro"]
        assert [plan["price_monthly"] for plan in plans] == [79]
        assert all(plan["currency"] == "AED" for plan in plans)

    def test_rico_monthly_entitlement_shape(self, client):
        plans = client.get("/api/v1/subscription/plans").json()["plans"]
        entitlements = plans[0]["entitlements"]

        assert entitlements == {
            "monthly_ai_message_limit": 300,
            "saved_jobs_limit": 100,
            "profile_optimization_limit": 20,
            "cv_storage_limit": 5,
            "other_document_limit": 10,
            "premium_recommendations_enabled": False,
            "application_automation_enabled": False,
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

    def test_me_reflects_paddle_backed_active_subscription(self, auth_client, monkeypatch):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        row = {
            "user_id": "alice@rico.ai",
            "plan": "pro",
            "status": "active",
            "paddle_customer_id": "ctm_test",
            "paddle_subscription_id": "sub_test",
            "current_period_start": now - timedelta(days=1),
            "current_period_end": now + timedelta(days=29),
            "past_due_since": None,
            "cancel_at": None,
            "canceled_at": None,
        }
        monkeypatch.setattr(
            "src.repositories.paddle_repo.get_paddle_subscription_by_user",
            lambda db_module, user_id: row,
        )

        r = auth_client.get("/api/v1/subscription/me")

        assert r.status_code == 200
        body = r.json()
        assert body["is_active"] is True
        assert body["subscription"]["plan"] == "pro"
        assert body["subscription"]["subscription_status"] == "active"
        assert body["subscription"]["paddle_customer_id"] == "ctm_test"
        assert body["plan"]["price_monthly"] == 79
        assert body["subscription"]["entitlements"]["monthly_ai_message_limit"] == 300

    def test_me_requires_auth(self, client):
        r = client.get("/api/v1/subscription/me")

        assert r.status_code == 401

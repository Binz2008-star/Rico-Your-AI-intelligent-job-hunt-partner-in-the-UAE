"""Regression: /api/v1/subscription/intent bounds anonymous writes.

The endpoint is unauthenticated by design (it logs upgrade intent for both
guests and users). Before this fix it had no rate limit and the body fields had
no length caps, so an anonymous client could flood subscription_intents with
arbitrarily large rows. This test pins the length caps (the storage-flood
defense); the rate limit is applied via @limiter.limit(LIMIT_INTENT).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from src.api.app import app

    return TestClient(app, raise_server_exceptions=False)


def test_oversized_plan_is_rejected(client):
    r = client.post(
        "/api/v1/subscription/intent",
        json={"plan": "x" * 65, "billing_mode": "manual", "source_page": "/subscription"},
    )
    assert r.status_code == 422


def test_oversized_source_page_is_rejected(client):
    r = client.post(
        "/api/v1/subscription/intent",
        json={"plan": "pro", "source_page": "y" * 300},
    )
    assert r.status_code == 422


def test_oversized_billing_mode_is_rejected(client):
    r = client.post(
        "/api/v1/subscription/intent",
        json={"plan": "pro", "billing_mode": "z" * 33},
    )
    assert r.status_code == 422


def test_valid_intent_is_recorded(client):
    with patch(
        "src.api.routers.subscription.record_subscription_intent", return_value=True
    ) as rec:
        r = client.post(
            "/api/v1/subscription/intent",
            json={"plan": "pro", "billing_mode": "manual", "source_page": "/subscription"},
        )
    assert r.status_code == 200
    assert r.json()["recorded"] is True
    rec.assert_called_once()

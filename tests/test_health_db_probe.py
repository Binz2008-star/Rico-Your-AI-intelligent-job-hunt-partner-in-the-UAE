"""Regression tests for the /health and /ready DB connectivity probe.

A configured-but-unreachable database means a production platform is NOT ready;
a missing DATABASE_URL (JSON-store/local mode) is a supported configuration.
/health always stays HTTP 200 (liveness) but flips status to degraded in
production; /ready returns 503 in production when the DB is unavailable.
"""
from unittest.mock import patch

import pytest

from src.api import app as api_app


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    return TestClient(api_app.app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "db_state,prod,expected_status,expected_health",
    [
        # (probe result, is_production, /ready status, /health status field)
        ("ok", True, 200, "ok"),
        ("disabled", True, 200, "ok"),
        ("unavailable", False, 200, "ok"),
        ("unavailable", True, 503, "degraded"),
    ],
)
def test_ready_and_health_db_probe(client, db_state, prod, expected_status, expected_health):
    with (
        patch("src.api.app._probe_db", return_value=db_state),
        patch("src.api.app._is_production_deploy", return_value=prod),
        patch(
            "src.rico_openai_runtime.get_readiness",
            return_value={"ready": True, "provider": "deepseek"},
        ),
        # /health flips to "degraded" when the reasoning provider is down too —
        # pin it healthy so the DB probe is the only signal under test.
        patch(
            "src.rico_openai_runtime.get_reasoning_health",
            return_value={"provider": "deepseek", "degraded": False},
        ),
    ):
        ready = client.get("/ready")
        health = client.get("/health")

    assert ready.status_code == expected_status
    assert ready.json()["db"] == db_state
    assert health.status_code == 200, "health must never return non-200 (liveness)"
    assert health.json()["db"] == db_state
    assert health.json()["status"] == expected_health


def test_ready_still_honors_reasoning_readiness(client):
    with (
        patch("src.api.app._probe_db", return_value="ok"),
        patch("src.api.app._is_production_deploy", return_value=True),
        patch(
            "src.rico_openai_runtime.get_readiness",
            return_value={"ready": False, "reasons": ["not_configured"]},
        ),
    ):
        ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["ready"] is False

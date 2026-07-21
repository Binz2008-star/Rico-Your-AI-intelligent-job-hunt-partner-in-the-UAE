"""MEDIUM-3 (security audit refresh 2026-07-21): rate-limit coverage.

Pins that previously-uncovered routes now enforce the shared LIMIT_PROFILE
("20/minute") ceiling: GET /api/v1/me and the two /api/v1/onboarding/* routes.
Pre-fix these carried no @limiter.limit, so the 21st request in a window still
returned a non-429 status — the assertions below would fail.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# LIMIT_PROFILE == "20/minute": the 21st request in the window must be 429.
_LIMIT = 20


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Clear limiter counters before each test so windows don't bleed across."""
    from src.api.rate_limit import limiter
    try:
        limiter._storage.reset()
    except Exception:
        pass
    yield


@pytest.fixture(scope="module")
def client():
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


def _hammer(client: TestClient, method: str, path: str, **kw) -> list[int]:
    return [client.request(method, path, **kw).status_code for _ in range(_LIMIT + 1)]


def test_me_enforces_profile_rate_limit(client):
    statuses = _hammer(client, "GET", "/api/v1/me")
    assert 429 not in statuses[:_LIMIT], statuses      # first 20 under the ceiling
    assert statuses[_LIMIT] == 429, statuses           # 21st trips it


def test_onboarding_status_enforces_profile_rate_limit(client):
    # Limiter fires around the handler regardless of the (unauth) 401 body.
    statuses = _hammer(client, "GET", "/api/v1/onboarding/status")
    assert 429 not in statuses[:_LIMIT], statuses
    assert statuses[_LIMIT] == 429, statuses


def test_onboarding_submit_enforces_profile_rate_limit(client):
    statuses = _hammer(client, "POST", "/api/v1/onboarding/submit", json={})
    assert 429 not in statuses[:_LIMIT], statuses
    assert statuses[_LIMIT] == 429, statuses

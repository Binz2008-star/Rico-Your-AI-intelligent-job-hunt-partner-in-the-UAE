"""#1077 — the user-callable paid-provider smoke probe is REMOVED.

`GET /api/v1/rico/openai-smoke` let every authenticated self-signup account
trigger real OpenAI/DeepSeek calls (walking the fallback chain) through a
GET, on the ordinary chat rate limit, outside any plan accounting, and it
returned provider/model/error-detail diagnostics to the caller. The issue's
preferred remediation is removal, so these tests pin:

* the route is gone for every method and auth state (404 — never a provider
  call);
* the free public liveness route stays cheap: answering it can never invoke
  a provider request;
* the router module no longer even imports the paid-call helper, so the
  probe cannot silently return.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from src.api.rate_limit import limiter

    limiter.reset()
    yield


@pytest.fixture
def client():
    return TestClient(app)


class TestPaidProbeRemoved:
    URL = "/api/v1/rico/openai-smoke"

    def test_get_is_404_for_unauthenticated(self, client):
        assert client.get(self.URL).status_code == 404

    def test_get_is_404_for_authenticated(self, client):
        with patch(
            "src.api.deps.get_current_user",
            return_value={"email": "user@example.com", "role": "user"},
        ):
            assert client.get(self.URL).status_code == 404

    def test_no_method_reaches_a_provider(self, client):
        """No verb resurrects the probe, and no request to it can produce a
        provider call — the paid helper would explode if touched."""
        with patch(
            "src.rico_openai_runtime.call_openai_minimal",
            side_effect=AssertionError("provider call attempted via removed probe"),
        ):
            for method in ("get", "post", "put", "delete"):
                r = getattr(client, method)(self.URL)
                assert r.status_code in (404, 405)

    def test_router_module_no_longer_imports_paid_helper(self):
        import src.api.routers.rico_chat as chat_module

        assert not hasattr(chat_module, "rico_openai_smoke")
        assert not hasattr(chat_module, "call_openai_minimal")


class TestPublicHealthStaysCheap:
    URL = "/api/v1/rico/health/ai-provider"

    def test_public_health_never_calls_a_provider(self, client):
        with patch(
            "src.rico_openai_runtime.call_openai_minimal",
            side_effect=AssertionError("public health must not call providers"),
        ):
            r = client.get(self.URL)
        assert r.status_code == 200

    def test_public_health_exposes_no_error_detail_or_model_chain(self, client):
        r = client.get(self.URL)
        assert r.status_code == 200
        body = r.json()
        assert "error_detail" not in body
        assert "fallback_model" not in body

"""Core-path contracts through the REAL wrappers (DEC-20260721-001 slice 3).

Lesson generalized from the 2026-07-18 production save outage (#1166 → #1169):
endpoint tests that patch the router's OWN wrapper make router↔wrapper kwarg
drift invisible to CI — the endpoint passed `clear_fields=`, the wrapper
didn't accept it, and every live save 503'd while tests stayed green. The
existing chat endpoint tests have the same shape: they patch
``chat_service.send_message`` itself, and the actions endpoint tests patch
around ``agent_runtime``.

These tests close that class for the chat and save/apply action paths: the
HTTP route runs the REAL wrapper chain, with patches only one layer DOWN
(policy/gate/repo edges, or nothing at all for the dry-run action path), so
any signature drift fails HERE first, not in production.

Search-path note: the deep search chain (process_message → duplicate guard →
provider cascade) already runs through the real code in
tests/unit/test_operation_duplicate_guard.py and the postgres ownership
suite; this file pins the transport contract that feeds it
(operation_id/language propagating from the route into the pipeline).
"""
from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.services.subscription_gating import GateCheck

_USER = "alice@rico.ai"


@pytest.fixture()
def auth_client():
    """Authenticated client with a valid JWT cookie (same recipe as
    tests/test_rico_routes.py — identity from the JWT, never the body)."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": _USER, "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _gate_allow() -> GateCheck:
    return GateCheck(
        allowed=True,
        feature="monthly_ai_message_limit",
        usage=1,
        limit=300,
        remaining=299,
        plan="pro",
        message="ok",
    )


# ── Chat: route → REAL chat_service.send_message → captured legacy layer ──────

class TestChatThroughRealServiceWrapper:
    """POST /api/v1/rico/chat runs the real ``chat_service.send_message``;
    only the layer BELOW it (``_legacy_send_message``) is a capturing spy.
    Any kwarg drift between the router call
    (ctx=/message=/operation_id=/language=) and the service signature — or
    between the service and its legacy dispatch — fails here first."""

    @staticmethod
    def _spy(captured: dict):
        def _capture(ctx, message, operation_id=None, language=None):
            captured["user_id"] = ctx.user_id
            captured["auth_type"] = ctx.auth_type
            captured["message"] = message
            captured["operation_id"] = operation_id
            captured["language"] = language
            return {
                "type": "text_reply",
                "message": "real-wrapper reply",
                "response_source": "keyword",
            }
        return _capture

    def _post(self, auth_client, payload: dict, captured: dict):
        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request") as mock_policy,
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=_gate_allow()),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.services.chat_service._intent_router") as mock_router,
            patch("src.services.chat_service._legacy_send_message", side_effect=self._spy(captured)),
        ):
            mock_policy.return_value = MagicMock(route="chat")
            mock_router.route.return_value = MagicMock(should_use_ai=False)
            return auth_client.post("/api/v1/rico/chat", json=payload)

    def test_full_payload_binds_through_the_real_wrapper(self, auth_client):
        captured: dict[str, Any] = {}
        r = self._post(
            auth_client,
            {
                "message": "find me hse manager jobs in dubai",
                "operation_id": "op_realwrapper_0001",
                "language": "ar",
            },
            captured,
        )
        assert r.status_code == 200, f"real-wrapper chat contract broke: {r.status_code}: {r.text}"
        # Identity comes from the JWT, through the real ctx factory.
        assert captured["user_id"] == _USER
        assert captured["auth_type"] == "authenticated"
        # The transport contract the duplicate-execution guard depends on:
        # operation_id and language must SURVIVE router → service → dispatch.
        assert captured["operation_id"] == "op_realwrapper_0001"
        assert captured["language"] == "ar"
        assert captured["message"] == "find me hse manager jobs in dubai"
        assert r.json().get("message") == "real-wrapper reply"

    def test_minimal_payload_binds_with_optional_fields_defaulted(self, auth_client):
        captured: dict[str, Any] = {}
        r = self._post(auth_client, {"message": "hello rico"}, captured)
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert captured["operation_id"] is None
        assert captured["language"] is None

    def test_unauthenticated_chat_still_rejected_on_the_real_path(self, auth_client):
        from fastapi.testclient import TestClient
        from src.api.app import app
        anon = TestClient(app, raise_server_exceptions=False)
        captured: dict[str, Any] = {}
        with patch("src.services.chat_service._legacy_send_message", side_effect=self._spy(captured)):
            r = anon.post("/api/v1/rico/chat", json={"message": "hi"})
        assert r.status_code == 401
        assert captured == {}  # never reached the pipeline


# ── Actions: route → REAL agent_runtime.handle_action (no runtime mocks) ─────

class TestActionsThroughRealRuntime:
    """POST /api/v1/actions/run executes the REAL ``agent_runtime`` — nothing
    on the action path is patched. ``dry_run=true`` is the runtime's own
    log-only mode (no side effects, no audit write), which makes the full
    router → runtime → registry chain safely executable in CI: any kwarg
    drift in the router's ``handle_action(...)`` call, and any break in the
    ActionResult → ActionResponse serialization contract, fails here."""

    def _run(self, auth_client, body: dict):
        return auth_client.post("/api/v1/actions/run", json=body)

    @pytest.mark.parametrize("action", ["save", "skip", "why"])
    def test_dry_run_actions_execute_through_the_real_runtime(self, auth_client, action):
        r = self._run(
            auth_client,
            {
                "action": action,
                "job_key": "a1b2c3d4e5f60718",
                "job": {"title": "HSE Manager", "company": "Synthetic Co"},
                "dry_run": True,
            },
        )
        assert r.status_code == 200, f"real-runtime {action} contract broke: {r.status_code}: {r.text}"
        data = r.json()
        assert data["dry_run"] is True
        assert data["action"] == action
        # Identity is stamped from the JWT by the router, not the body.
        assert data["user_id"] == _USER
        # Serialization contract: every ActionResponse field is present.
        for field in ("ok", "message", "job_key", "source", "data", "confidence"):
            assert field in data, f"ActionResponse field {field} missing"

    def test_unknown_action_is_a_controlled_refusal_not_a_500(self, auth_client):
        r = self._run(
            auth_client,
            {"action": "definitely_not_a_tool", "job_key": "aa11bb22cc33dd44", "dry_run": True},
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert r.json()["ok"] is False

    def test_client_cannot_smuggle_the_approval_sentinel(self, auth_client):
        """The router strips ``_approved`` from the job payload before the
        REAL runtime sees it — the sentinel is reserved for the validated
        /actions/execute path. Run in dry_run so nothing executes either way."""
        r = self._run(
            auth_client,
            {
                "action": "why",
                "job_key": "ff00ff00ff00ff00",
                "job": {"title": "X", "_approved": True},
                "dry_run": True,
            },
        )
        assert r.status_code == 200
        assert r.json()["dry_run"] is True

    def test_unauthenticated_action_rejected(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        anon = TestClient(app, raise_server_exceptions=False)
        r = anon.post(
            "/api/v1/actions/run",
            json={"action": "save", "job_key": "aa11bb22cc33dd44", "dry_run": True},
        )
        assert r.status_code == 401

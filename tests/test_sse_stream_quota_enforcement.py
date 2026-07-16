"""
SSE chat quota + policy enforcement (#1078).

The production `/command` UI streams first, so the streaming routes — not just
the JSON route — must:
  * run the canonical policy gateway + AI-message entitlement gate (a capped
    user is refused and the provider is never called);
  * record the user turn BEFORE the provider call so monthly usage survives a
    mid-stream disconnect / provider error;
  * apply the registered-email anti-dodge cap on the public stream so a capped
    user cannot get unlimited AI by routing through /chat/stream/public.

These lock the transport-independent contract: JSON and SSE share one preflight
(`chat_service.run_chat_preflight`) and one transport decision
(`chat_service.should_stream_ai`); streaming changes only how the reply is sent.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.schemas.chat import RicoSessionContext
from src.services.subscription_gating import GateCheck


def _gate(allowed: bool, *, remaining: int = 0, limit: int = 300) -> GateCheck:
    return GateCheck(
        allowed=allowed,
        feature="monthly_ai_message_limit",
        usage=limit - remaining,
        limit=limit,
        remaining=remaining,
        plan="free",
        message="limit reached" if not allowed else "ok",
    )


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from src.api.rate_limit import limiter

    limiter.reset()
    yield


# ── Shared preflight (transport-independent) ──────────────────────────────────


class TestSharedPreflight:
    def test_blocked_gate_yields_subscription_limit_terminal(self) -> None:
        ctx = RicoSessionContext.for_authenticated("capped@example.com")
        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request", return_value=MagicMock(route="chat")),
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=_gate(False)),
        ):
            from src.services import chat_service

            pre = chat_service.run_chat_preflight(ctx, "hello")
        assert pre.terminal is not None
        assert pre.terminal["type"] == "subscription_limit"

    def test_allowed_gate_yields_no_terminal(self) -> None:
        ctx = RicoSessionContext.for_authenticated("ok@example.com")
        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request", return_value=MagicMock(route="chat")),
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=_gate(True, remaining=100)),
        ):
            from src.services import chat_service

            pre = chat_service.run_chat_preflight(ctx, "hello")
        assert pre.terminal is None
        assert pre.gate is not None and pre.gate.allowed

    def test_public_context_is_not_per_user_capped(self) -> None:
        # check_ai_message_allowed returns None for public contexts.
        ctx = RicoSessionContext.for_public("web-ssetest0001")
        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request", return_value=MagicMock(route="chat")),
        ):
            from src.services import chat_service

            pre = chat_service.run_chat_preflight(ctx, "hello")
        assert pre.terminal is None
        assert pre.gate is None

    def test_should_stream_ai_false_for_document_action(self) -> None:
        ctx = RicoSessionContext.for_authenticated("u@example.com")
        with patch("src.rico_chat_api.RicoChatAPI.is_document_action_message", return_value=True):
            from src.services import chat_service

            assert chat_service.should_stream_ai(ctx, "summarize this document", None) is False

    def test_should_stream_ai_true_for_conversational(self) -> None:
        ctx = RicoSessionContext.for_authenticated("u@example.com")
        with (
            patch("src.rico_chat_api.RicoChatAPI.is_document_action_message", return_value=False),
            patch("src.rico.intent.gates.is_explicit_job_listing_request", return_value=False),
            patch("src.services.chat_service._intent_router") as router,
        ):
            router.route.return_value = MagicMock(should_use_ai=True)
            from src.services import chat_service

            assert chat_service.should_stream_ai(ctx, "tell me a joke", None) is True


# ── Authenticated SSE route ───────────────────────────────────────────────────


class TestAuthenticatedStreamEnforcement:
    def test_capped_user_gets_limit_event_and_no_provider_call(self, client) -> None:
        provider = MagicMock(side_effect=AssertionError("provider must not run for a capped user"))
        with (
            patch("src.api.routers.rico_chat.get_current_user", return_value={"email": "capped@example.com"}),
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request", return_value=MagicMock(route="chat")),
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=_gate(False)),
            patch("src.rico_openai_runtime.call_openai_stream", provider),
        ):
            res = client.post("/api/v1/rico/chat/stream", json={"message": "hello there"})
        assert res.status_code == 200
        assert "subscription_limit" in res.text
        provider.assert_not_called()

    def test_streaming_path_records_exactly_one_user_turn(self, client) -> None:
        def _stream(*_a, **_k):
            yield "Hi "
            yield "there"

        with (
            patch("src.api.routers.rico_chat.get_current_user", return_value={"email": "u@example.com"}),
            patch("src.services.chat_service.run_chat_preflight", return_value=_allowed_preflight()),
            patch("src.services.chat_service.should_stream_ai", return_value=True),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.rico_chat_api.RicoChatAPI._build_openai_context", return_value={}),
            patch("src.rico_chat_api.RicoChatAPI._append_chat") as mock_append,
            patch("src.rico_openai_runtime.call_openai_stream", _stream),
        ):
            res = client.post("/api/v1/rico/chat/stream", json={"message": "tell me a joke"})
        assert res.status_code == 200
        assert "Hi there" in res.text  # tokens actually streamed
        user_turns = [c for c in mock_append.call_args_list if len(c.args) >= 2 and c.args[1] == "user"]
        assert len(user_turns) == 1, f"expected exactly one recorded user turn, got {user_turns}"

    def test_user_turn_recorded_even_when_provider_errors_midstream(self, client) -> None:
        # Simulates an aborted/failed stream: the user turn (usage) must already be
        # durable before the provider produced its full reply.
        def _stream(*_a, **_k):
            yield "partial"
            raise RuntimeError("provider blew up mid-stream")

        with (
            patch("src.api.routers.rico_chat.get_current_user", return_value={"email": "u@example.com"}),
            patch("src.services.chat_service.run_chat_preflight", return_value=_allowed_preflight()),
            patch("src.services.chat_service.should_stream_ai", return_value=True),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.rico_chat_api.RicoChatAPI._build_openai_context", return_value={}),
            patch("src.rico_chat_api.RicoChatAPI._append_chat") as mock_append,
            patch("src.rico_openai_runtime.call_openai_stream", _stream),
        ):
            res = client.post("/api/v1/rico/chat/stream", json={"message": "tell me a joke"})
        assert res.status_code == 200
        assert "partial" in res.text  # streamed before the error
        user_turns = [c for c in mock_append.call_args_list if len(c.args) >= 2 and c.args[1] == "user"]
        assert len(user_turns) == 1, "usage (user turn) must be recorded before the provider completes"


# ── Public SSE route: anti-dodge ──────────────────────────────────────────────


class TestPublicStreamAntiDodge:
    def test_registered_email_over_cap_blocked_no_provider(self, client) -> None:
        provider = MagicMock(side_effect=AssertionError("provider must not run for a capped dodge"))
        registered = MagicMock(email="reg@example.com")
        with (
            patch("src.repositories.users_repo.get_user_by_email", return_value=registered),
            patch("src.services.subscription_gating.check_ai_message_allowed_for_user", return_value=_gate(False)),
            patch("src.rico_openai_runtime.call_openai_stream", provider),
        ):
            res = client.post(
                "/api/v1/rico/chat/stream/public",
                json={"message": "hi", "email": "reg@example.com"},
            )
        assert res.status_code == 200
        assert "subscription_limit" in res.text
        provider.assert_not_called()

    def test_registered_email_cap_is_not_reset_by_session_rotation(self, client) -> None:
        # The anti-dodge cap is keyed on the registered email, not the client
        # session id — a fresh session cannot reset it.
        provider = MagicMock(side_effect=AssertionError("provider must not run for a capped dodge"))
        registered = MagicMock(email="reg@example.com")
        with (
            patch("src.repositories.users_repo.get_user_by_email", return_value=registered),
            patch("src.services.subscription_gating.check_ai_message_allowed_for_user", return_value=_gate(False)),
            patch("src.rico_openai_runtime.call_openai_stream", provider),
        ):
            for sid in ("web-rotation0001", "web-rotation0002"):
                res = client.post(
                    "/api/v1/rico/chat/stream/public",
                    json={"message": "hi", "email": "reg@example.com", "session_id": sid},
                )
                assert "subscription_limit" in res.text
        provider.assert_not_called()


def _allowed_preflight():
    """A preflight result that permits streaming (gate allowed, no terminal)."""
    from src.services.chat_service import ChatPreflight

    return ChatPreflight(terminal=None, gate=_gate(True, remaining=100))

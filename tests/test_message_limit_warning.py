"""Tests for messages_remaining injection in chat_service.send_message."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.chat import RicoSessionContext
from src.services.subscription_gating import GateCheck


def _make_ctx(user_id: str = "user-abc") -> RicoSessionContext:
    return RicoSessionContext(
        user_id=user_id,
        auth_type="authenticated",
        session_id="sess-1",
    )


def _make_gate(remaining: int, limit: int = 50, allowed: bool = True) -> GateCheck:
    return GateCheck(
        allowed=allowed,
        feature="monthly_ai_message_limit",
        usage=limit - remaining,
        limit=limit,
        remaining=remaining,
        plan="free",
        message="ok",
    )


def _legacy_response() -> dict[str, Any]:
    return {"type": "text_reply", "message": "Here are your jobs.", "response_source": "keyword"}


def _ai_response() -> dict[str, Any]:
    return {"type": "ai_reply", "message": "AI response.", "response_source": "ai_router"}


# Deferred imports in send_message are patched at their canonical module path.
_PATCHES_BASE = [
    ("src.services.operation_state.is_status_followup", False),
    ("src.services.operation_state.build_status_response", None),
]


class TestMessagesRemainingInjection:
    """messages_remaining must appear in responses only when ≤10 remain."""

    @pytest.mark.parametrize("remaining", [10, 5, 3, 1, 0])
    def test_injects_when_at_or_below_threshold(self, remaining: int) -> None:
        ctx = _make_ctx()
        gate = _make_gate(remaining=remaining)

        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request") as mock_policy,
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=gate),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.services.chat_service._intent_router") as mock_router,
            patch("src.services.chat_service._legacy_send_message", return_value=_legacy_response()),
        ):
            mock_policy.return_value = MagicMock(route="chat")
            mock_router.route.return_value = MagicMock(should_use_ai=False)

            from src.services import chat_service
            result = chat_service.send_message(ctx, "find jobs")

        assert "messages_remaining" in result, (
            f"Expected messages_remaining in response when {remaining} remain"
        )
        assert result["messages_remaining"] == remaining
        assert result.get("messages_limit") == 50

    @pytest.mark.parametrize("remaining", [11, 20, 49, 50])
    def test_does_not_inject_above_threshold(self, remaining: int) -> None:
        ctx = _make_ctx()
        gate = _make_gate(remaining=remaining)

        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request") as mock_policy,
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=gate),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.services.chat_service._intent_router") as mock_router,
            patch("src.services.chat_service._legacy_send_message", return_value=_legacy_response()),
        ):
            mock_policy.return_value = MagicMock(route="chat")
            mock_router.route.return_value = MagicMock(should_use_ai=False)

            from src.services import chat_service
            result = chat_service.send_message(ctx, "find jobs")

        assert "messages_remaining" not in result, (
            f"Should NOT inject messages_remaining when {remaining} remain (above threshold)"
        )

    def test_does_not_inject_for_unauthenticated(self) -> None:
        """Public sessions return gate=None; must never receive messages_remaining."""
        ctx = RicoSessionContext(
            user_id="pub-session-1",
            auth_type="public",
            session_id="sess-pub",
        )

        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request") as mock_policy,
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.services.chat_service._intent_router") as mock_router,
            patch("src.services.chat_service._legacy_send_message", return_value=_legacy_response()),
        ):
            mock_policy.return_value = MagicMock(route="chat")
            mock_router.route.return_value = MagicMock(should_use_ai=False)

            from src.services import chat_service
            result = chat_service.send_message(ctx, "find jobs")

        assert "messages_remaining" not in result

    def test_injects_into_ai_dict_response(self) -> None:
        """AI-routed dict responses must receive the same warning metadata."""
        ctx = _make_ctx()
        gate = _make_gate(remaining=4)

        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request") as mock_policy,
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=gate),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.services.chat_service._intent_router") as mock_router,
            patch("src.services.chat_service._legacy_send_message") as mock_legacy,
            patch("src.services.chat_service._conversational_ai_reply", return_value=_ai_response()) as mock_ai,
        ):
            mock_policy.return_value = MagicMock(route="chat")
            mock_router.route.return_value = MagicMock(should_use_ai=True)

            from src.services import chat_service
            result = chat_service.send_message(ctx, "help me plan my career")

        mock_ai.assert_called_once()
        mock_legacy.assert_not_called()
        assert result["messages_remaining"] == 4
        assert result["messages_limit"] == 50

    def test_ai_non_dict_response_is_returned_without_injection_crash(self) -> None:
        """Streaming/non-dict AI responses must not be mutated with dict keys."""
        ctx = _make_ctx()
        gate = _make_gate(remaining=4)
        streaming_response = object()

        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request") as mock_policy,
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=gate),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.services.chat_service._intent_router") as mock_router,
            patch("src.services.chat_service._legacy_send_message") as mock_legacy,
            patch("src.services.chat_service._conversational_ai_reply", return_value=streaming_response) as mock_ai,
        ):
            mock_policy.return_value = MagicMock(route="chat")
            mock_router.route.return_value = MagicMock(should_use_ai=True)

            from src.services import chat_service
            result = chat_service.send_message(ctx, "help me plan my career")

        mock_ai.assert_called_once()
        mock_legacy.assert_not_called()
        assert result is streaming_response

    def test_blocked_gate_returns_limit_response_not_chat(self) -> None:
        """When gate.allowed=False the limit error is returned directly."""
        ctx = _make_ctx()
        gate = _make_gate(remaining=0, allowed=False)

        with (
            patch("src.services.operation_state.is_status_followup", return_value=False),
            patch("src.services.operation_state.build_status_response", return_value=None),
            patch("src.rico.policy.classify_request") as mock_policy,
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=gate),
        ):
            mock_policy.return_value = MagicMock(route="chat")

            from src.services import chat_service
            result = chat_service.send_message(ctx, "find jobs")

        assert result["type"] == "subscription_limit"
        assert "messages_remaining" not in result

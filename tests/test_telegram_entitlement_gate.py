"""Regression tests for the Telegram AI-message entitlement gate.

A Telegram chat bound to a registered web account must be held to the same
AI-message cap as the web surface (billing-bypass fix). Native Telegram-only
chats (no web account) have no subscription relationship and are not gated.
"""
from unittest.mock import MagicMock, patch

import pytest


_COUNTER = [1000]


def _update(text: str, chat_id: str = "123456789", username: str = "joe"):
    # Unique update_id per call: the module-level duplicate-update guard treats
    # repeated ids as retries and silently skips them.
    _COUNTER[0] += 1
    return {
        "update_id": _COUNTER[0],
        "message": {
            "message_id": _COUNTER[0],
            "chat": {"id": chat_id},
            "from": {"id": chat_id, "username": username},
            "text": text,
        },
    }


class TestResolveRegisteredUser:
    def test_returns_bound_user(self):
        with patch(
            "src.repositories.profile_repo.find_registered_user_by_telegram_chat_id",
            return_value="user@example.com",
        ):
            from src.rico_telegram_webhook import _resolve_registered_user

            assert _resolve_registered_user("123456789") == "user@example.com"

    def test_returns_none_when_no_binding(self):
        with patch(
            "src.repositories.profile_repo.find_registered_user_by_telegram_chat_id",
            return_value=None,
        ):
            from src.rico_telegram_webhook import _resolve_registered_user

            assert _resolve_registered_user("123456789") is None

    def test_never_raises(self):
        with patch(
            "src.repositories.profile_repo.find_registered_user_by_telegram_chat_id",
            side_effect=Exception("db down"),
        ):
            from src.rico_telegram_webhook import _resolve_registered_user

            assert _resolve_registered_user("123456789") is None


class TestGateTelegramAi:
    def test_returns_message_when_capped(self):
        from src.services.subscription_gating import GateCheck

        gate = GateCheck(
            allowed=False,
            feature="monthly_ai_message_limit",
            usage=10,
            limit=10,
            remaining=0,
            plan="free",
            message="You've used your free AI messages for today.",
        )
        with patch(
            "src.services.subscription_gating.check_ai_message_allowed_for_user",
            return_value=gate,
        ):
            from src.rico_telegram_webhook import _gate_telegram_ai

            assert _gate_telegram_ai("user@example.com") == gate.message

    def test_returns_none_when_allowed(self):
        from src.services.subscription_gating import GateCheck

        gate = GateCheck(
            allowed=True,
            feature="monthly_ai_message_limit",
            usage=1,
            limit=10,
            remaining=9,
            plan="free",
            message="9 remaining",
        )
        with patch(
            "src.services.subscription_gating.check_ai_message_allowed_for_user",
            return_value=gate,
        ):
            from src.rico_telegram_webhook import _gate_telegram_ai

            assert _gate_telegram_ai("user@example.com") is None

    def test_fails_closed_on_quota_unavailable(self):
        from src.services.subscription_gating import QuotaUnavailableError

        with patch(
            "src.services.subscription_gating.check_ai_message_allowed_for_user",
            side_effect=QuotaUnavailableError("db down"),
        ):
            from src.rico_telegram_webhook import _gate_telegram_ai

            reply = _gate_telegram_ai("user@example.com")
            assert reply is not None
            assert "unavailable" in reply

    def test_fails_closed_on_ambiguous_identity(self):
        from src.models.principal import IdentityOwnershipAmbiguous

        with patch(
            "src.services.subscription_gating.check_ai_message_allowed_for_user",
            side_effect=IdentityOwnershipAmbiguous("ambiguous"),
        ):
            from src.rico_telegram_webhook import _gate_telegram_ai

            reply = _gate_telegram_ai("user@example.com")
            assert reply is not None
            assert "unambiguously" in reply


class TestTelegramCallbackSaveGate:
    """A bound account's Telegram Save button must persist canonically and be
    quota-gated (board path) — never the legacy user-scopeless JSON tool."""

    JOB = {
        "id": "tgjob-1",
        "title": "HSE Manager",
        "company": "Acme",
        "link": "https://naukrigulf.com/job-1",
    }

    def test_bound_user_save_persists_via_board_not_legacy_tool(self):
        from src.services.application_board import BoardResult

        with (
            patch(
                "src.rico_telegram_ui._resolve_telegram_registered_user",
                return_value="user@example.com",
            ),
            patch(
                "src.services.application_board.persist_job_action",
                return_value=BoardResult(ok=True),
            ) as board,
            patch("src.agent.runtime.agent_runtime") as runtime,
        ):
            from src.rico_telegram_ui import handle_job_action

            runtime.handle_action.return_value.ok = True
            runtime.handle_action.return_value.message = "Saved."
            result = handle_job_action("save", self.JOB, user_id="123456")

        board.assert_called_once()
        args = board.call_args[0]
        assert args[0] == "user@example.com"  # resolved account, user-scoped
        assert args[1]["title"] == "HSE Manager"
        assert args[2] == "saved"
        runtime.handle_action.assert_called_once()
        # persist=False: the legacy JSON save tool must never run.
        assert runtime.handle_action.call_args.kwargs.get("persist") is False
        assert result["ok"] is True

    def test_bound_user_over_quota_gets_quota_reply(self):
        from src.services.application_board import BoardResult

        with (
            patch(
                "src.rico_telegram_ui._resolve_telegram_registered_user",
                return_value="user@example.com",
            ),
            patch(
                "src.services.application_board.persist_job_action",
                return_value=BoardResult(
                    ok=False, error="quota_exceeded", quota_message="Saved-jobs limit reached."
                ),
            ),
            patch("src.agent.runtime.agent_runtime") as runtime,
        ):
            from src.rico_telegram_ui import handle_job_action

            result = handle_job_action("save", self.JOB, user_id="123456")

        assert result["ok"] is False
        assert "limit" in result["reply"]
        runtime.handle_action.assert_not_called()

    def test_native_telegram_user_keeps_legacy_path(self):
        with (
            patch(
                "src.rico_telegram_ui._resolve_telegram_registered_user",
                return_value=None,
            ),
            patch("src.agent.runtime.agent_runtime") as runtime,
        ):
            from src.rico_telegram_ui import handle_job_action

            runtime.handle_action.return_value.ok = True
            runtime.handle_action.return_value.message = "Saved."
            result = handle_job_action("save", self.JOB, user_id="123456")

        runtime.handle_action.assert_called_once()
        # persist defaults to True for native users (no billing relationship).
        assert runtime.handle_action.call_args.kwargs.get("persist") is not False
        assert result["ok"] is True


class TestProcessTelegramUpdateGate:
    def test_capped_bound_user_gets_gate_reply_and_no_chat_call(self):
        with (
            patch(
                "src.rico_telegram_webhook._resolve_registered_user",
                return_value="user@example.com",
            ),
            patch(
                "src.rico_telegram_webhook._gate_telegram_ai",
                return_value="You've used your free AI messages for today.",
            ),
            patch("src.rico_telegram_webhook.send_telegram_to_user") as send,
            patch("src.rico_telegram_webhook.chat_api") as chat_api,
        ):
            from src.rico_telegram_webhook import process_telegram_update

            result = process_telegram_update(_update("hello"))
        send.assert_called_once()
        assert "free AI messages" in send.call_args[0][1]
        chat_api.process_message.assert_not_called()
        assert result["chat_id"] == "123456789"

    def test_uncapped_bound_user_reaches_chat(self):
        with (
            patch(
                "src.rico_telegram_webhook._resolve_registered_user",
                return_value="user@example.com",
            ),
            patch("src.rico_telegram_webhook._gate_telegram_ai", return_value=None),
            patch(
                "src.rico_telegram_webhook.chat_api",
            ) as chat_api,
        ):
            from src.rico_telegram_webhook import process_telegram_update

            chat_api.process_message.return_value = {"message": "hello back"}
            result = process_telegram_update(_update("hello"))
        chat_api.process_message.assert_called_once()
        # Final-hardening (B-1): a bound account's turn runs under the ACCOUNT
        # identity so Telegram usage is recorded against the same allowance the
        # gate just checked — not under the raw chat_id (which never resolved).
        assert chat_api.process_message.call_args.kwargs.get("user_id") == "user@example.com"
        assert result["reply"]["message"] == "hello back"

    def test_native_telegram_chat_within_allowance_reaches_chat(self):
        # No registered web binding → bounded daily allowance gate applies; when
        # within the allowance the message proceeds under the chat identity.
        with (
            patch(
                "src.rico_telegram_webhook._resolve_registered_user",
                return_value=None,
            ),
            patch("src.rico_telegram_webhook._gate_native_telegram", return_value=None),
            patch(
                "src.rico_telegram_webhook.chat_api",
            ) as chat_api,
        ):
            from src.rico_telegram_webhook import process_telegram_update

            chat_api.process_message.return_value = {"message": "ok"}
            result = process_telegram_update(_update("hello"))
        chat_api.process_message.assert_called_once()
        assert result["reply"]["message"] == "ok"

    def test_native_telegram_chat_over_allowance_blocked(self):
        with (
            patch(
                "src.rico_telegram_webhook._resolve_registered_user",
                return_value=None,
            ),
            patch(
                "src.rico_telegram_webhook._gate_native_telegram",
                return_value="You've reached today's free message limit (10).",
            ),
            patch("src.rico_telegram_webhook.send_telegram_to_user") as send,
            patch("src.rico_telegram_webhook.chat_api") as chat_api,
        ):
            from src.rico_telegram_webhook import process_telegram_update

            result = process_telegram_update(_update("hello"))
        send.assert_called_once()
        chat_api.process_message.assert_not_called()
        assert "limit" in result["reply"]["message"]

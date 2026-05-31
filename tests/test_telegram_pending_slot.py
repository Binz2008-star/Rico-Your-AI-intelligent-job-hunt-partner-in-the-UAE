"""tests/test_telegram_pending_slot.py

Tests for Telegram username collection in the Rico chat pipeline.

Invariants verified:
  - "@Robin_amg" as the whole message is detected and saved (not routed to job search)
  - "my telegram is @Robin_amg" is detected and saved
  - "telegram: Robin_amg" (no @) is detected and saved
  - Pending-slot: if Rico asked for Telegram, the next message is the username
  - Invalid format while pending re-prompts without clearing the slot
  - upsert_profile is called exactly once with the normalised username
  - Confirmation message contains the @handle
  - pending_question slot is cleared after successful save
  - _looks_like_bare_target_role returns False for @username inputs
  - _extract_telegram_username returns None for non-Telegram messages
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rico_chat_api import RicoChatAPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api() -> RicoChatAPI:
    """Return a RicoChatAPI instance with all external dependencies mocked."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    api.memory = MagicMock()
    api.agent = MagicMock()
    api.system = MagicMock()
    api.memory.load_profile.return_value = MagicMock()
    api.memory.get_context.return_value = {}
    api.memory.set_context.return_value = None
    return api


def _blank_context(api: RicoChatAPI) -> None:
    """Ensure no pending_question is in context."""
    api.memory.get_context.return_value = {}


def _pending_telegram_context(api: RicoChatAPI) -> None:
    """Simulate Rico having just asked for Telegram username."""
    api.memory.get_context.return_value = {"pending_question": "telegram_username"}


# ---------------------------------------------------------------------------
# _extract_telegram_username
# ---------------------------------------------------------------------------

class TestExtractTelegramUsername:
    def test_bare_at_handle(self):
        assert RicoChatAPI._extract_telegram_username("@Robin_amg") == "Robin_amg"

    def test_natural_my_telegram_is(self):
        assert RicoChatAPI._extract_telegram_username("my telegram is @Robin_amg") == "Robin_amg"

    def test_natural_telegram_colon(self):
        assert RicoChatAPI._extract_telegram_username("telegram: @Robin_amg") == "Robin_amg"

    def test_natural_without_at(self):
        assert RicoChatAPI._extract_telegram_username("my telegram is Robin_amg") == "Robin_amg"

    def test_natural_telegram_handle(self):
        assert RicoChatAPI._extract_telegram_username("my telegram handle is @test_user") == "test_user"

    def test_natural_telegram_username(self):
        assert RicoChatAPI._extract_telegram_username("my telegram username @testuser1") == "testuser1"

    def test_arabic_telegram(self):
        result = RicoChatAPI._extract_telegram_username("تيليجرام: @Robin_amg")
        assert result == "Robin_amg"

    def test_bare_at_with_spaces_not_extracted(self):
        # A bare @handle embedded in a long message should NOT be extracted
        # (too risky — could be an email domain reference or other)
        result = RicoChatAPI._extract_telegram_username("please search @Robin_amg jobs in Dubai")
        assert result is None

    def test_not_a_telegram_message(self):
        assert RicoChatAPI._extract_telegram_username("find me HSE jobs in Dubai") is None

    def test_email_not_extracted_as_telegram(self):
        # email addresses share the @ — must not be confused with Telegram
        assert RicoChatAPI._extract_telegram_username("my email is user@example.com") is None

    def test_too_short_username(self):
        # Telegram requires at least 5 chars; we accept 4 minimum per our regex
        # but a 3-char handle should not match
        assert RicoChatAPI._extract_telegram_username("@abc") is None

    def test_at_alone_not_extracted(self):
        assert RicoChatAPI._extract_telegram_username("@") is None


# ---------------------------------------------------------------------------
# _looks_like_bare_target_role — @username guard
# ---------------------------------------------------------------------------

class TestBareRoleGateAtGuard:
    def test_at_username_not_a_role(self):
        assert RicoChatAPI._looks_like_bare_target_role("@Robin_amg") is False

    def test_at_username_with_words_not_a_role(self):
        # Even "@Robin_amg" with trailing text — first token starts with @
        assert RicoChatAPI._looks_like_bare_target_role("@Robin_amg hello") is False

    def test_normal_role_still_passes(self):
        assert RicoChatAPI._looks_like_bare_target_role("HSE Manager") is True


# ---------------------------------------------------------------------------
# Direct declaration flow (no pending slot)
# ---------------------------------------------------------------------------

class TestDirectTelegramDeclaration:
    def test_bare_at_username_saved(self):
        api = _make_api()
        _blank_context(api)
        profile = MagicMock()

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_append_chat"):
            mock_upsert.return_value = profile
            result = api._handle_telegram_username("user1", "Robin_amg", profile)

        mock_upsert.assert_called_once_with(
            user_id="user1",
            updates={"telegram_username": "Robin_amg"},
        )
        assert result["type"] == "profile_update"
        assert result["field"] == "telegram_username"
        assert "@Robin_amg" in result["message"]

    def test_at_prefix_stripped_before_save(self):
        api = _make_api()
        _blank_context(api)
        profile = MagicMock()

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_append_chat"):
            mock_upsert.return_value = profile
            api._handle_telegram_username("user1", "@Robin_amg", profile)

        mock_upsert.assert_called_once_with(
            user_id="user1",
            updates={"telegram_username": "Robin_amg"},
        )

    def test_pending_slot_cleared_after_save(self):
        api = _make_api()
        captured_ctx = {"pending_question": "telegram_username"}
        api.memory.get_context.return_value = captured_ctx
        profile = MagicMock()

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_append_chat"):
            mock_upsert.return_value = profile
            api._handle_telegram_username("user1", "Robin_amg", profile)

        # Slot must be cleared
        saved_ctx = api.memory.set_context.call_args[0][2]
        assert "pending_question" not in saved_ctx

    def test_save_failure_returns_friendly_message(self):
        api = _make_api()
        _blank_context(api)
        profile = MagicMock()

        with patch("src.rico_chat_api.upsert_profile", side_effect=Exception("DB down")), \
             patch.object(api, "_append_chat"):
            result = api._handle_telegram_username("user1", "Robin_amg", profile)

        assert result["type"] == "profile_update"
        assert "couldn't save" in result["message"].lower() or "couldn't persist" in result["message"].lower() or "couldn't" in result["message"].lower()


# ---------------------------------------------------------------------------
# Pending-slot flow
# ---------------------------------------------------------------------------

class TestPendingSlotFlow:
    def _run_handle(self, api, message):
        """Drive _handle_active_user_inner with all external calls patched."""
        profile = MagicMock()
        api.memory.load_profile.return_value = profile

        with patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
            return api._handle_active_user_inner("user1", message, profile)

    def test_pending_slot_accepts_bare_username(self):
        api = _make_api()
        _pending_telegram_context(api)

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_resolve_profile", return_value=MagicMock()), \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
            mock_upsert.return_value = MagicMock()
            result = api._handle_active_user_inner("user1", "@Robin_amg")

        mock_upsert.assert_called_once_with(
            user_id="user1",
            updates={"telegram_username": "Robin_amg"},
        )
        assert result["type"] == "profile_update"

    def test_pending_slot_accepts_username_without_at(self):
        api = _make_api()
        _pending_telegram_context(api)

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_resolve_profile", return_value=MagicMock()), \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
            mock_upsert.return_value = MagicMock()
            result = api._handle_active_user_inner("user1", "Robin_amg")

        mock_upsert.assert_called_once_with(
            user_id="user1",
            updates={"telegram_username": "Robin_amg"},
        )

    def test_pending_slot_invalid_format_reprompts(self):
        api = _make_api()
        _pending_telegram_context(api)

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_resolve_profile", return_value=MagicMock()), \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
            result = api._handle_active_user_inner("user1", "not a valid @handle!!!")

        mock_upsert.assert_not_called()
        assert result["type"] == "clarification"
        assert "telegram" in result["message"].lower()

    def test_no_pending_slot_at_username_still_detected(self):
        """Even without a pending slot, @handle is caught by direct detection."""
        api = _make_api()
        _blank_context(api)

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_resolve_profile", return_value=MagicMock()), \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
            mock_upsert.return_value = MagicMock()
            result = api._handle_active_user_inner("user1", "@Robin_amg")

        mock_upsert.assert_called_once_with(
            user_id="user1",
            updates={"telegram_username": "Robin_amg"},
        )
        assert result["type"] == "profile_update"

    def test_natural_phrase_no_pending_slot(self):
        """'my telegram is @Robin_amg' is saved via direct detection (no slot needed)."""
        api = _make_api()
        _blank_context(api)

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_resolve_profile", return_value=MagicMock()), \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_finalize", side_effect=lambda r, *a, **kw: r):
            mock_upsert.return_value = MagicMock()
            result = api._handle_active_user_inner("user1", "my telegram is @Robin_amg")

        mock_upsert.assert_called_once_with(
            user_id="user1",
            updates={"telegram_username": "Robin_amg"},
        )
        assert result["type"] == "profile_update"
        assert "@Robin_amg" in result["message"]


# ---------------------------------------------------------------------------
# _ask_for_telegram_username
# ---------------------------------------------------------------------------

class TestAskForTelegramUsername:
    def test_sets_pending_slot_in_context(self):
        api = _make_api()
        _blank_context(api)

        with patch.object(api, "_append_chat"):
            result = api._ask_for_telegram_username("user1")

        saved_ctx = api.memory.set_context.call_args[0][2]
        assert saved_ctx.get("pending_question") == "telegram_username"
        assert result["type"] == "clarification"
        assert "@" in result["message"]

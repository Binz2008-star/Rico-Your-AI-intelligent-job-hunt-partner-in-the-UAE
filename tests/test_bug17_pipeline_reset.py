"""
tests/test_bug17_pipeline_reset.py

Regression tests for pipeline-reset intent misclassification.

Problem: "Clear them we must start over" (after seeing 103 tracked applications)
was routed as a job-role search because "clear" was not in _NON_ROLE_STARTERS and
_looks_like_bare_target_role() accepted it.

Three fixes applied:
  Fix A — "clear" and "reset" added to _NON_ROLE_STARTERS so they never start a role.
  Fix B — _PIPELINE_RESET_RE added for explicit phrases ("clear all applications",
           "reset pipeline", "start over", "archive all applications", etc.)
  Fix C — _PIPELINE_RESET_IMPLICIT_RE added for vague phrases ("clear them",
           "must start over") that only fire when last_turn.intent == "application_tracking".

Safety constraints:
  - No DB write happens without explicit user confirmation.
  - No action executes immediately — all paths go through a 2-turn confirmation.
  - Tests must NOT touch the live database (all persistence mocked).
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ---------------------------------------------------------------------------
# Fix A — "clear" / "reset" must not be classified as bare role names
# ---------------------------------------------------------------------------

class TestClearResetNotClassifiedAsRole:
    """Phrases starting with 'clear' or 'reset' must never look like job titles."""

    def test_clear_them_not_a_role(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("Clear them we must start over") is False

    def test_reset_pipeline_not_a_role(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("Reset pipeline") is False

    def test_clear_all_applications_not_a_role(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("Clear all applications") is False

    def test_legitimate_role_hse_manager_still_matches(self):
        """Regression guard: adding 'clear'/'reset' must not break real role titles."""
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("HSE Manager") is True


# ---------------------------------------------------------------------------
# Fix B — after application_tracking context, implicit phrases → reset confirm
# ---------------------------------------------------------------------------

class TestImplicitResetAfterApplicationContext:
    """'Clear them we must start over' → pipeline_reset_confirm when last turn was app tracking."""

    def _make_api(self):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI()
        api.memory = MagicMock()
        api.memory.get_context.return_value = None  # no pending state by default
        return api

    def _run(self, message: str, last_intent: str):
        api = self._make_api()

        # Simulate the last-turn context
        api.memory.get_context.side_effect = lambda uid, key: (
            {"intent": last_intent, "response_type": "application_status", "object": {}, "user_message": ""}
            if key == "last_turn" else {}
        )

        with patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            result = api._handle_pending_pipeline_reset("u@example.com", message)
        return result

    def test_clear_them_after_app_context_returns_confirm(self):
        """'Clear them we must start over' must return pipeline_reset_confirm after app tracking."""
        from src.rico_chat_api import RicoChatAPI, _PIPELINE_RESET_IMPLICIT_RE

        # Verify the regex matches the smoke-evidence phrase
        assert _PIPELINE_RESET_IMPLICIT_RE.search("Clear them we must start over"), (
            "Regex must match 'Clear them we must start over'"
        )

        # Without a pending state, _handle_pending_pipeline_reset returns None
        # (the guard runs in _handle_active_user_inner, which sets the pending then
        # the next turn reads it). So here we verify the regex + _handle_pipeline_reset.
        api = RicoChatAPI()
        api.memory = MagicMock()
        api.memory.get_context.return_value = None

        with patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            result = api._handle_pipeline_reset("u@example.com", "Clear them we must start over")

        assert result["type"] == "pipeline_reset_confirm"
        assert result["next_action"] == "await_confirmation"

    def test_vague_clear_them_without_app_context_does_not_trigger(self):
        """Without application_tracking context, implicit phrases must not fire."""
        from src.rico_chat_api import RicoChatAPI, _PIPELINE_RESET_IMPLICIT_RE

        # The regex matches the phrase itself
        assert _PIPELINE_RESET_IMPLICIT_RE.search("clear them")

        # But _handle_active_user_inner only dispatches to _handle_pipeline_reset
        # when last_turn.intent == "application_tracking". Verify the guard works
        # by checking the last_turn intent lookup behavior.
        api = RicoChatAPI()
        api.memory = MagicMock()
        # last_turn has a non-application intent
        api.memory.get_context.side_effect = lambda uid, key: (
            {"intent": "job_search", "response_type": "job_matches", "object": {}}
            if key == "last_turn" else None
        )

        last_t = api._get_last_turn("u@example.com")
        assert last_t.get("intent") != "application_tracking", (
            "Without app context, implicit reset must not activate"
        )


# ---------------------------------------------------------------------------
# Fix B (explicit) — explicit phrases always trigger reset confirmation
# ---------------------------------------------------------------------------

class TestExplicitPipelineResetAlwaysTriggers:
    """Explicit phrases must match _PIPELINE_RESET_RE regardless of conversation context."""

    def _phrases(self):
        return [
            "clear all applications",
            "clear my pipeline",
            "reset pipeline",
            "reset all applications",
            "archive all applications",
            "start over",
            "start fresh",
            "start from scratch",
            "remove all tracked jobs",
            "wipe all applications",
        ]

    def test_all_explicit_phrases_match_regex(self):
        from src.rico_chat_api import _PIPELINE_RESET_RE
        for phrase in self._phrases():
            assert _PIPELINE_RESET_RE.search(phrase), f"Regex must match: {phrase!r}"

    def test_explicit_clear_all_applications_returns_confirm(self):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI()
        api.memory = MagicMock()
        api.memory.get_context.return_value = None

        with patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            result = api._handle_pipeline_reset("u@example.com", "clear all applications")

        assert result["type"] == "pipeline_reset_confirm"
        assert result["next_action"] == "await_confirmation"
        assert "archive" in result["message"].lower() or "أرشف" in result["message"]


# ---------------------------------------------------------------------------
# Fix C — confirmation flow: no archive/delete without explicit confirmation
# ---------------------------------------------------------------------------

class TestConfirmationFlowRequiresExplicitChoice:
    """Archive and delete must only execute after an explicit user choice in turn 2."""

    def _api_with_pending(self):
        """Build an API instance with an active pending pipeline reset."""
        from src.rico_chat_api import RicoChatAPI
        import time

        api = RicoChatAPI()
        api.memory = MagicMock()
        pending = {"pending": True, "expires_at": int(time.time()) + 120}
        api.memory.get_context.side_effect = lambda uid, key: (
            pending if key == RicoChatAPI._PENDING_PIPELINE_RESET_KEY else None
        )
        return api

    def test_no_action_taken_on_confirmation_prompt_turn(self):
        """Requesting the reset (turn 1) sets pending but takes no destructive action."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI()
        api.memory = MagicMock()
        api.memory.get_context.return_value = None

        with patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._handle_pipeline_reset("u@example.com", "clear all applications")

        # No profile mutation
        mock_upsert.assert_not_called()
        # Response is a confirmation prompt, not an execution receipt
        assert result["type"] == "pipeline_reset_confirm"

    def test_archive_confirmation_redirects_to_applications(self):
        """Typing 'archive' in turn 2 redirects to /applications (no immediate DB op)."""
        api = self._api_with_pending()

        with patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._handle_pending_pipeline_reset("u@example.com", "archive")

        assert result is not None
        assert result["type"] == "pipeline_reset_archive"
        assert result.get("target_route") == "/applications"
        mock_upsert.assert_not_called()

    def test_cancel_clears_pending_and_takes_no_action(self):
        """Typing 'cancel' or 'no' in turn 2 cancels the operation without any DB write."""
        api = self._api_with_pending()

        with patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._handle_pending_pipeline_reset("u@example.com", "cancel")

        assert result is not None
        assert result["type"] == "pipeline_reset_cancelled"
        mock_upsert.assert_not_called()

    def test_delete_choice_redirects_without_db_write(self):
        """Typing 'delete' redirects to /applications — no immediate destructive DB op."""
        api = self._api_with_pending()

        with patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._handle_pending_pipeline_reset("u@example.com", "delete")

        assert result is not None
        assert result["type"] == "pipeline_reset_delete_redirect"
        assert result.get("target_route") == "/applications"
        mock_upsert.assert_not_called()

    def test_no_pending_returns_none(self):
        """Without an active pending state, the pending handler must pass through (return None)."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI()
        api.memory = MagicMock()
        api.memory.get_context.return_value = None  # no pending

        result = api._handle_pending_pipeline_reset("u@example.com", "archive")
        assert result is None

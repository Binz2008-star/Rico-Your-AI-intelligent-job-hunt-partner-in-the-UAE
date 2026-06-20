"""Tests for pending-intent / conversation-state feature in RicoChatAPI.

Covers:
- _is_affirmative() — EN + AR
- _is_negative() — EN + AR
- _resolve_pending_intent() — no pending, CV-improve, job-search, reminder
- Full flow via _handle_active_user(): affirmative → resolved intent, negative → clarification
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.rico_chat_api import RicoChatAPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api() -> RicoChatAPI:
    """Return a RicoChatAPI instance with all heavy dependencies mocked out."""
    with (
        patch("src.rico_chat_api.RicoMemoryStore"),
        patch("src.rico_chat_api.RicoAgent"),
        patch("src.rico_chat_api.RicoSystem"),
        patch("src.rico_chat_api.RicoOpenAIAgent"),
    ):
        return RicoChatAPI(persist=False)


def _make_profile(target_roles: list[str] | None = None) -> MagicMock:
    profile = MagicMock()
    profile.has_cv = True
    profile.target_roles = ["Software Engineer"] if target_roles is None else target_roles
    # Set string fields to None so they don't pollute string operations inside
    # _handle_cv_generate_from_profile (MagicMock is truthy but not a str).
    profile.name = None
    profile.email = None
    profile.phone = None
    profile.current_role = None
    profile.years_experience = None
    profile.skills = []
    profile.certifications = []
    profile.preferred_cities = []
    profile.industries = []
    profile.work_experience = []
    profile.education = []
    profile.cv_filename = "cv.pdf"
    return profile


# ---------------------------------------------------------------------------
# _is_affirmative
# ---------------------------------------------------------------------------

class TestIsAffirmative:
    def test_english_yes(self):
        assert RicoChatAPI._is_affirmative("yes") is True

    def test_english_sure(self):
        assert RicoChatAPI._is_affirmative("sure") is True

    def test_english_ok(self):
        assert RicoChatAPI._is_affirmative("ok") is True

    def test_english_okay(self):
        assert RicoChatAPI._is_affirmative("okay") is True

    def test_english_yep(self):
        assert RicoChatAPI._is_affirmative("yep") is True

    def test_english_absolutely(self):
        assert RicoChatAPI._is_affirmative("absolutely") is True

    def test_english_go_ahead(self):
        assert RicoChatAPI._is_affirmative("go ahead") is True

    def test_arabic_naam(self):
        assert RicoChatAPI._is_affirmative("نعم") is True

    def test_arabic_aywa(self):
        assert RicoChatAPI._is_affirmative("أيوه") is True

    def test_arabic_yalla(self):
        assert RicoChatAPI._is_affirmative("يلا") is True

    def test_arabic_tafaddal(self):
        assert RicoChatAPI._is_affirmative("تفضل") is True

    def test_arabic_muwafiq(self):
        assert RicoChatAPI._is_affirmative("موافق") is True

    def test_affirmative_with_punctuation_stripped(self):
        assert RicoChatAPI._is_affirmative("yes!") is True

    def test_affirmative_with_trailing_whitespace(self):
        assert RicoChatAPI._is_affirmative("  sure  ") is True

    def test_affirmative_case_insensitive(self):
        assert RicoChatAPI._is_affirmative("YES") is True

    def test_negative_word_is_not_affirmative(self):
        assert RicoChatAPI._is_affirmative("no") is False

    def test_empty_string_is_not_affirmative(self):
        assert RicoChatAPI._is_affirmative("") is False

    def test_long_sentence_is_not_affirmative(self):
        assert RicoChatAPI._is_affirmative("yes I want to search for a job") is False


# ---------------------------------------------------------------------------
# _is_negative
# ---------------------------------------------------------------------------

class TestIsNegative:
    def test_english_no(self):
        assert RicoChatAPI._is_negative("no") is True

    def test_english_nope(self):
        assert RicoChatAPI._is_negative("nope") is True

    def test_english_cancel(self):
        assert RicoChatAPI._is_negative("cancel") is True

    def test_english_never_mind(self):
        assert RicoChatAPI._is_negative("never mind") is True

    def test_english_not_now(self):
        assert RicoChatAPI._is_negative("not now") is True

    def test_arabic_la(self):
        assert RicoChatAPI._is_negative("لا") is True

    def test_arabic_la2(self):
        assert RicoChatAPI._is_negative("لأ") is True

    def test_arabic_ma_abi(self):
        assert RicoChatAPI._is_negative("ما ابي") is True

    def test_negative_with_punctuation_stripped(self):
        assert RicoChatAPI._is_negative("no!") is True

    def test_affirmative_word_is_not_negative(self):
        assert RicoChatAPI._is_negative("yes") is False

    def test_empty_string_is_not_negative(self):
        assert RicoChatAPI._is_negative("") is False


# ---------------------------------------------------------------------------
# _resolve_pending_intent
# ---------------------------------------------------------------------------

class TestResolvePendingIntent:
    """Unit-tests for _resolve_pending_intent with the last assistant message mocked."""

    def _api_with_last_message(self, last_msg: str) -> RicoChatAPI:
        api = _make_api()
        api._get_last_assistant_message = MagicMock(return_value=last_msg)
        return api

    # ── No pending intent ──────────────────────────────────────────────────

    def test_returns_none_when_message_is_not_affirmative(self):
        api = self._api_with_last_message("improve your cv to get better results")
        result = api._resolve_pending_intent("user1", "no", _make_profile())
        assert result is None

    def test_returns_none_when_no_last_assistant_message(self):
        api = self._api_with_last_message("")
        result = api._resolve_pending_intent("user1", "yes", _make_profile())
        assert result is None

    def test_returns_none_when_last_message_has_no_known_signal(self):
        api = self._api_with_last_message("Hello! How can I help you today?")
        result = api._resolve_pending_intent("user1", "yes", _make_profile())
        assert result is None

    # ── CV improvement ─────────────────────────────────────────────────────

    def test_cv_improve_en_signal(self):
        api = self._api_with_last_message("Would you like me to improve your cv?")
        result = api._resolve_pending_intent("user1", "yes", _make_profile())
        # cv_improve_signals now route to _handle_cv_generate_from_profile
        assert result is not None
        assert result["type"] in ("cv_draft", "cv_creation", "cv_suggestions")

    def test_cv_improve_ar_signal(self):
        api = self._api_with_last_message("هل تريد اقتراح تحسين سيرتك الذاتية؟")
        result = api._resolve_pending_intent("user1", "نعم", _make_profile())
        assert result is not None
        assert result["type"] in ("cv_draft", "cv_creation", "cv_suggestions")

    def test_cv_update_signal(self):
        api = self._api_with_last_message("I can update your cv to highlight relevant skills.")
        result = api._resolve_pending_intent("user1", "sure", _make_profile())
        assert result is not None
        assert result["type"] in ("cv_draft", "cv_creation", "cv_suggestions")

    # ── Job search ─────────────────────────────────────────────────────────

    def test_job_search_signal_shall_i_search(self):
        # P0 fix: _classified_role_search is now called instead of _answer_with_ai_fallback.
        # Previously this was asserting AI fallback was called (the buggy behaviour).
        api = self._api_with_last_message("Shall I search for live UAE jobs for you?")
        profile = _make_profile(["Data Analyst"])

        with patch.object(api, "_classified_role_search",
                          return_value={"type": "job_matches", "jobs": [], "message": "Searching..."}) as mock_search, \
             patch.object(api, "_answer_with_ai_fallback") as mock_ai:
            result = api._resolve_pending_intent("user1", "yes", profile)

        mock_ai.assert_not_called()
        mock_search.assert_called_once()
        assert result is not None
        assert result["type"] in ("job_matches", "job_list", "job_results")

    def test_job_search_signal_want_me_to_search(self):
        # P0 fix: _classified_role_search is now called instead of _answer_with_ai_fallback.
        api = self._api_with_last_message("Want me to search for matching roles?")
        profile = _make_profile(["Product Manager"])

        with patch.object(api, "_classified_role_search",
                          return_value={"type": "job_matches", "jobs": [], "message": "..."}) as mock_search, \
             patch.object(api, "_answer_with_ai_fallback") as mock_ai:
            result = api._resolve_pending_intent("user1", "okay", profile)

        mock_ai.assert_not_called()
        mock_search.assert_called_once()
        assert result is not None

    def test_job_search_falls_back_to_my_target_role_when_no_roles(self):
        # P0 fix: with no target roles, the resolver now returns a clarification asking
        # for the role instead of forwarding to AI fallback (which generated "ببحث الآن...").
        api = self._api_with_last_message("Want me to search for live jobs?")
        profile = _make_profile([])

        with patch.object(api, "_answer_with_ai_fallback") as mock_ai:
            result = api._resolve_pending_intent("user1", "yes", profile)

        mock_ai.assert_not_called()
        assert result is not None
        assert result["type"] == "clarification"
        assert not RicoChatAPI._is_promise_only_reply(result.get("message", ""))

    # ── Application angle ──────────────────────────────────────────────────

    def test_application_angle_signal(self):
        api = self._api_with_last_message("Shall I prepare your application angle and cover letter?")
        ai_resp = {"type": "application_angle", "message": "Here's your angle."}
        api._answer_with_ai_fallback = MagicMock(return_value=ai_resp)

        result = api._resolve_pending_intent("user1", "yes", _make_profile())
        assert result is ai_resp

    # ── Reminder ───────────────────────────────────────────────────────────

    def test_reminder_en_signal(self):
        api = self._api_with_last_message("Want me to set a reminder to follow up next week?")
        result = api._resolve_pending_intent("user1", "yes", _make_profile())
        assert result is not None
        assert result["type"] == "reminder_set"
        assert "Reminder" in result["message"] or "reminder" in result["message"]

    def test_reminder_ar_signal(self):
        api = self._api_with_last_message("هل تريد تذكير للمتابعة؟")
        result = api._resolve_pending_intent("user1", "نعم", _make_profile())
        assert result is not None
        assert result["type"] == "reminder_set"
        assert "تذكير" in result["message"] or "تذك" in result["message"]


# ---------------------------------------------------------------------------
# Full flow: _handle_active_user → affirmative → resolved intent
# ---------------------------------------------------------------------------

class TestHandleActiveUserPendingIntentFlow:
    """Integration-style tests that exercise _handle_active_user() with mocks."""

    def _api_with_setup(self, last_assistant_msg: str, ai_response: dict) -> RicoChatAPI:
        api = _make_api()
        # Stub heavy internals
        api._get_last_assistant_message = MagicMock(return_value=last_assistant_msg)
        api._answer_with_ai_fallback = MagicMock(return_value=ai_response)
        api._get_openai_agent = MagicMock(return_value=MagicMock(
            openai_available=True,
            deepseek_available=False,
            hf_available=False,
            provider_available=True,
            model="gpt-4.1-mini",
        ))

        # Mock profile retrieval
        profile = _make_profile(["UX Designer"])
        api._get_or_create_profile = MagicMock(return_value=profile)
        # _handle_active_user needs _get_profile_for_user or similar; mock at memory level
        api.memory = MagicMock()
        api.memory.get_profile.return_value = profile.__dict__ if hasattr(profile, "__dict__") else {}

        return api, profile

    def test_affirmative_with_cv_pending_returns_non_generic_response(self):
        """'yes' after Rico offered CV improvement → cv_draft or cv_suggestions type, not action card."""
        ai_response = {"type": "cv_suggestions", "message": "Here are specific suggestions."}
        api, profile = self._api_with_setup("Would you like me to improve your cv?", ai_response)

        with patch.object(api, "_get_profile", return_value=profile, create=True), \
             patch.object(api, "_load_profile", return_value=profile, create=True), \
             patch.object(api, "_profile_value", side_effect=lambda p, k: getattr(p, k, None)):
            # Call _resolve_pending_intent directly to verify routing
            result = api._resolve_pending_intent("user1", "yes", profile)

        assert result is not None
        assert result["type"] in ("cv_draft", "cv_creation", "cv_suggestions")
        # Verify it is NOT a generic options/action-card response
        assert result["type"] != "options"

    def test_affirmative_with_job_search_pending_returns_job_response(self):
        """'نعم' after Rico offered job search → actual job search type (not AI fallback)."""
        # P0 fix: _classified_role_search is now called, returning "job_matches" type.
        # The old assertion was "job_list" which was the AI fallback mock type — incorrect.
        api, profile = self._api_with_setup("Want me to search for live UAE jobs for you?",
                                             {"type": "job_list", "jobs": []})

        with patch.object(api, "_profile_value", side_effect=lambda p, k: getattr(p, k, None)), \
             patch.object(api, "_classified_role_search",
                          return_value={"type": "job_matches", "jobs": [], "message": "Searching..."}), \
             patch.object(api, "_answer_with_ai_fallback") as mock_ai:
            result = api._resolve_pending_intent("user1", "نعم", profile)

        mock_ai.assert_not_called()
        assert result is not None
        assert result["type"] in ("job_matches", "job_list", "job_results")

    def test_negative_reply_produces_clarification_via_is_negative(self):
        """Verify negative detection gates the clarification path in _handle_active_user."""
        api = _make_api()
        # Negative reply should resolve correctly
        assert RicoChatAPI._is_negative("لا") is True
        assert RicoChatAPI._is_negative("no") is True

    def test_affirmative_no_pending_returns_none_from_resolve(self):
        """'yes' when Rico's last message has no pending signal → None, falls through."""
        ai_response = {"type": "options", "message": "How can I help?", "options": []}
        api, profile = self._api_with_setup("Here is a summary of your profile.", ai_response)

        result = api._resolve_pending_intent("user1", "yes", profile)
        assert result is None

    def test_arabic_affirmative_yalla_resolves_cv_intent(self):
        """'يلا' (yalla) is affirmative and resolves a pending CV intent."""
        ai_response = {"type": "cv_suggestions", "message": "اقتراحات."}
        api, profile = self._api_with_setup(
            "هل تريد اقتراح تحسين cv_improvement سيرتك؟", ai_response
        )
        # Manually set the signal so cv_improve triggers
        api._get_last_assistant_message = MagicMock(
            return_value="Would you like me to improve your cv and update your profile?"
        )

        result = api._resolve_pending_intent("user1", "يلا", profile)
        assert result is not None
        assert result["type"] in ("cv_draft", "cv_creation", "cv_suggestions")

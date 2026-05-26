"""tests/unit/test_help_option_phrase_routing.py

Tests for help-option phrase routing fix.

Before the fix, phrases like "Finding jobs" and "job search" — typed by users
when selecting from a help menu — were passed to _classified_role_search and
rejected as unknown job roles ("I do not recognize 'Finding jobs' as a job role").

After the fix:
  - "Finding jobs", "job search", and similar help-option phrases hit a
    deterministic guard before _classified_role_search.
  - With a CV they return profile_role_suggestions (asking which role to search).
  - Without a CV they return a clarification asking for a specific role name.
  - Real role searches (HSE Manager, General Manager) are unchanged.
  - "find jobs" (classified as job_search_explicit) is unchanged.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER = "help-route@rico.ai"


def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api._memory = {}
    return api


def _make_profile(target_roles: list[str] | None = None) -> MagicMock:
    p = MagicMock()
    p.has_cv = True
    p.target_roles = target_roles or []
    p.skills = ["NEBOSH", "ISO 45001", "risk assessment"]
    p.name = "Test User"
    p.email = USER
    p.cv_filename = "test_cv.pdf"
    p.cv_status = "parsed"
    return p


def _call(api: RicoChatAPI, message: str, profile: MagicMock, context: dict | None = None) -> dict:
    """Drive process_message with all DB/AI/intent patched."""
    from src.agent.intelligence.intent_classifier import IntentResult
    mock_agent = MagicMock()
    mock_agent.openai_available = False
    mock_agent.deepseek_available = False
    mock_agent.hf_available = False
    mock_agent.provider_available = True
    mock_agent.model = ""

    # Patch classify_intent to return unknown so the job search help guard is exercised
    unknown_intent = IntentResult(
        intent="unknown", confidence=0.0, source="fallback"
    )
    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=profile),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=mock_agent),
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
        patch.object(api, "_get_recent_context", return_value=dict(context or {})),
        patch.object(api, "_store_recent_context"),
        patch("src.rico_chat_api.classify_intent", return_value=unknown_intent),
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None),
    ):
        return api.process_message(USER, message)


# ---------------------------------------------------------------------------
# 1. _looks_like_bare_target_role — gerunds now blocked
# ---------------------------------------------------------------------------

class TestBareRoleGerundGuard:

    def test_finding_jobs_not_bare_role(self):
        assert not RicoChatAPI._looks_like_bare_target_role("Finding jobs")

    def test_searching_for_roles_not_bare_role(self):
        assert not RicoChatAPI._looks_like_bare_target_role("Searching for roles")

    def test_tailoring_my_resume_not_bare_role(self):
        assert not RicoChatAPI._looks_like_bare_target_role("Tailoring my resume")

    def test_improving_my_cv_not_bare_role(self):
        assert not RicoChatAPI._looks_like_bare_target_role("Improving my CV")

    def test_updating_profile_not_bare_role(self):
        assert not RicoChatAPI._looks_like_bare_target_role("Updating my profile")

    def test_tracking_applications_not_bare_role(self):
        assert not RicoChatAPI._looks_like_bare_target_role("Tracking my applications")

    def test_hse_manager_still_bare_role(self):
        assert RicoChatAPI._looks_like_bare_target_role("HSE Manager")

    def test_general_manager_still_bare_role(self):
        assert RicoChatAPI._looks_like_bare_target_role("General Manager")

    def test_environmental_engineer_still_bare_role(self):
        assert RicoChatAPI._looks_like_bare_target_role("Environmental Engineer")

    def test_interview_prep_still_bare_role(self):
        # "interview" is a noun/adj start — still passes bare role check
        # (but classified correctly by classify_intent as interview_prep)
        assert RicoChatAPI._looks_like_bare_target_role("interview prep")

    def test_listing_agent_still_bare_role(self):
        # "listing" must NOT be in _NON_ROLE_STARTERS — "Listing Agent" is a real
        # real-estate job title; blocking it would send the user to AI fallback
        assert RicoChatAPI._looks_like_bare_target_role("Listing Agent")


# ---------------------------------------------------------------------------
# 2. _JOB_SEARCH_HELP_PHRASES membership
# ---------------------------------------------------------------------------

class TestJobSearchHelpPhrases:

    def _in(self, phrase: str) -> bool:
        return phrase.strip().lower() in RicoChatAPI._JOB_SEARCH_HELP_PHRASES

    def test_finding_jobs_in_set(self):
        assert self._in("Finding jobs")

    def test_job_search_in_set(self):
        assert self._in("job search")

    def test_find_matching_uae_jobs_in_set(self):
        assert self._in("find matching uae jobs")

    def test_help_me_find_jobs_in_set(self):
        assert self._in("help me find jobs")

    def test_hse_manager_not_in_set(self):
        assert not self._in("HSE Manager")

    def test_find_jobs_not_in_set(self):
        # "find jobs" is handled by job_search_explicit intent, not this guard
        assert not self._in("find jobs")

    def test_general_manager_not_in_set(self):
        assert not self._in("General Manager")


# ---------------------------------------------------------------------------
# 3. process_message routing for help-option phrases
# ---------------------------------------------------------------------------

class TestHelpOptionPhraseRouting:

    def setup_method(self):
        self.api = _make_api()

    def test_finding_jobs_returns_role_suggestions_with_cv(self):
        profile = _make_profile()
        result = _call(self.api, "Finding jobs", profile)
        # Should return role suggestions, not "I do not recognize..."
        assert result.get("type") in ("profile_role_suggestions", "clarification")
        assert "do not recognize" not in result.get("message", "").lower()

    def test_job_search_returns_role_prompt_with_cv(self):
        profile = _make_profile()
        result = _call(self.api, "job search", profile)
        assert "do not recognize" not in result.get("message", "").lower()
        assert result.get("type") in ("profile_role_suggestions", "clarification")

    def test_find_matching_uae_jobs_returns_role_suggestions(self):
        profile = _make_profile()
        result = _call(self.api, "find matching UAE jobs", profile)
        assert "do not recognize" not in result.get("message", "").lower()

    def test_finding_jobs_without_cv_returns_role_clarification(self):
        profile = _make_profile()
        profile.has_cv = False
        profile.cv_filename = None
        profile.cv_status = None
        result = _call(self.api, "Finding jobs", profile)
        assert result.get("type") in ("clarification", "profile_role_suggestions", "profile_incomplete")
        assert "do not recognize" not in result.get("message", "").lower()

    def test_finding_jobs_no_role_text_in_response(self):
        """The error phrase 'I do not recognize' must never appear."""
        profile = _make_profile()
        for phrase in ["Finding jobs", "job search", "find matching UAE jobs",
                       "finding jobs matching my target roles"]:
            result = _call(self.api, phrase, profile)
            assert "do not recognize" not in result.get("message", "").lower(), (
                f"Got error response for {phrase!r}: {result.get('message')!r}"
            )


# ---------------------------------------------------------------------------
# 4. Real role searches unchanged
# ---------------------------------------------------------------------------

class TestRealRoleSearchesUnchanged:

    def setup_method(self):
        self.api = _make_api()

    def _call_with_role_intent(self, message: str, profile: MagicMock) -> dict:
        """For real roles, let classify_intent run normally (don't patch to unknown)."""
        mock_agent = MagicMock()
        mock_agent.openai_available = False
        mock_agent.deepseek_available = False
        mock_agent.hf_available = False
        mock_agent.provider_available = True
        mock_agent.model = ""
        with (
            patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
            patch.object(self.api, "_resolve_profile", return_value=profile),
            patch.object(self.api, "_append_chat"),
            patch.object(self.api, "_get_openai_agent", return_value=mock_agent),
            patch.object(self.api, "_looks_like_career_execution_request", return_value=False),
            patch.object(self.api, "_get_recent_context", return_value={}),
            patch.object(self.api, "_store_recent_context"),
            patch("src.services.subscription_gating.check_ai_message_allowed", return_value=None),
            patch("src.rico_chat_api.run_for_profile", return_value={"matches": [], "status": "ok"}),
        ):
            return self.api.process_message(USER, message)

    def test_hse_manager_not_treated_as_help_phrase(self):
        assert "HSE Manager".strip().lower() not in RicoChatAPI._JOB_SEARCH_HELP_PHRASES
        assert RicoChatAPI._looks_like_bare_target_role("HSE Manager")

    def test_general_manager_not_treated_as_help_phrase(self):
        assert "General Manager".strip().lower() not in RicoChatAPI._JOB_SEARCH_HELP_PHRASES
        assert RicoChatAPI._looks_like_bare_target_role("General Manager")

    def test_find_jobs_classified_as_job_search_explicit(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        result = classify_intent("find jobs", has_cv_profile=True)
        assert result.intent == "job_search_explicit"

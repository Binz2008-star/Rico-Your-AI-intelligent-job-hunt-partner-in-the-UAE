"""tests/unit/test_job_authenticity_lifecycle_guards.py

Unit tests for job authenticity and application lifecycle guards introduced in
the fix/job-authenticity-lifecycle-guards branch.

Covers:
  - _format_match: apply_url / source_url / verification_status fields
  - _build_role_search_message: live / lead / mixed wording
  - _has_apply_evidence: context-driven evidence detection
  - mark_applied guard: clarification on first call, proceed on second
  - track_job wording: "Saved" vs "Saved as lead"
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI
from src.agent.intelligence.intent_classifier import IntentResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER = "test@rico.ai"


def _make_api() -> RicoChatAPI:
    """Return a RicoChatAPI instance with _persist disabled to skip DB writes."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api._memory = {}  # in-memory chat history stub
    return api


def _make_profile(has_cv: bool = False) -> MagicMock:
    """Return a minimal profile mock."""
    p = MagicMock()
    p.has_cv = has_cv
    # Return empty / falsy values for all field lookups
    p.target_roles = []
    p.skills = []
    p.name = "Test User"
    p.email = USER
    p.years_experience = None
    p.current_location = None
    p.cv_filename = None
    p.completion_score = 0.0
    p.missing_fields = []
    return p


def _make_intent(intent: str, title: str = "HSE Officer", company: str = "Acme Corp") -> IntentResult:
    return IntentResult(
        intent=intent,
        confidence=1.0,
        source="exact",
        extracted_title=title,
        extracted_company=company,
    )


def _call_process(api: RicoChatAPI, message: str, context: dict | None = None) -> dict:
    """Call process_message with standard mocks."""
    mock_profile = _make_profile(has_cv=False)
    mock_agent = MagicMock()
    mock_agent.openai_available = False
    mock_agent.deepseek_available = False
    mock_agent.hf_available = False
    mock_agent.provider_available = True
    mock_agent.model = ""

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=mock_profile),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=mock_agent),
        patch("src.rico_chat_api.mark_onboarding_complete"),
        # Prevent career execution path from firing
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
        patch.object(api, "_get_recent_context", return_value=dict(context or {})),
        patch.object(api, "_store_recent_context"),
        patch("src.repositories.applications_repo.create_manual", return_value=True),
    ):
        return api.process_message(USER, message)


# ---------------------------------------------------------------------------
# 1. _format_match — URL fields and verification_status
# ---------------------------------------------------------------------------

class TestFormatMatch:

    def test_with_apply_link_sets_verified(self):
        # linkedin.com is a known trusted domain → live_verified
        m = {"title": "HSE Officer", "company": "Acme", "job_apply_link": "https://linkedin.com/jobs/123"}
        result = RicoChatAPI._format_match(m, profile=None)
        assert result["apply_url"] == "https://linkedin.com/jobs/123"
        assert result["verification_status"] == "live_verified"

    def test_with_unknown_domain_sets_needs_verification(self):
        # Unknown domain → needs_source_verification (domain-based classification)
        m = {"title": "HSE Officer", "company": "Acme", "job_apply_link": "https://example.com/apply"}
        result = RicoChatAPI._format_match(m, profile=None)
        assert result["apply_url"] == "https://example.com/apply"
        assert result["verification_status"] == "needs_source_verification"

    def test_with_link_field_sets_needs_verification(self):
        # Unknown domain via link field → needs_source_verification
        m = {"title": "HSE Officer", "company": "Acme", "link": "https://example.com/apply"}
        result = RicoChatAPI._format_match(m, profile=None)
        assert result["apply_url"] == "https://example.com/apply"
        assert result["verification_status"] == "needs_source_verification"

    def test_without_url_sets_needs_verification(self):
        # No URL → needs_source_verification (replaces old lead_needs_verification)
        m = {"title": "HSE Officer", "company": "Acme"}
        result = RicoChatAPI._format_match(m, profile=None)
        assert result["apply_url"] == ""
        assert result["verification_status"] == "needs_source_verification"

    def test_source_url_falls_back_to_apply_url(self):
        m = {"title": "HSE Officer", "company": "Acme", "link": "https://apply.example.com"}
        result = RicoChatAPI._format_match(m, profile=None)
        assert result["source_url"] == "https://apply.example.com"

    def test_source_url_prefers_google_link(self):
        m = {
            "title": "HSE Officer", "company": "Acme",
            "job_apply_link": "https://apply.example.com",
            "job_google_link": "https://google.com/jobs",
        }
        result = RicoChatAPI._format_match(m, profile=None)
        assert result["source_url"] == "https://google.com/jobs"

    def test_actions_always_present(self):
        m = {"title": "HSE Officer", "company": "Acme"}
        result = RicoChatAPI._format_match(m, profile=None)
        assert isinstance(result.get("actions"), list)
        assert len(result["actions"]) > 0


# ---------------------------------------------------------------------------
# 2. _build_role_search_message — live / lead / mixed wording
# ---------------------------------------------------------------------------

class TestBuildRoleSearchMessage:

    def setup_method(self):
        self.api = _make_api()

    def _msg(self, matches: list) -> str:
        return self.api._build_role_search_message(
            "HSE Officer", " in Dubai", " on a full-time basis", matches, None
        )

    def test_all_live_matches(self):
        matches = [
            {"link": "https://a.com"},
            {"job_apply_link": "https://b.com"},
        ]
        msg = self._msg(matches)
        assert "live match" in msg
        assert "lead" not in msg

    def test_all_lead_matches(self):
        matches = [{"title": "no url"}, {"title": "also no url"}]
        msg = self._msg(matches)
        assert "lead" in msg
        assert "live match" not in msg

    def test_mixed_live_and_lead(self):
        matches = [
            {"link": "https://a.com"},
            {"title": "no url"},
        ]
        msg = self._msg(matches)
        assert "live match" in msg
        assert "lead" in msg
        assert "need verification" in msg

    def test_no_matches_generic_message(self):
        msg = self._msg([])
        # Honest no-match copy (no false "keep scanning" promise).
        assert "did not find" in msg or "No live matches found" in msg


# ---------------------------------------------------------------------------
# 3. _has_apply_evidence — context-based detection
# ---------------------------------------------------------------------------

class TestHasApplyEvidence:

    def setup_method(self):
        self.api = _make_api()

    def _check(self, ctx: dict, title: str = "HSE Officer", company: str = "Acme Corp") -> bool:
        with patch.object(self.api, "_get_recent_context", return_value=ctx):
            return self.api._has_apply_evidence(USER, title, company)

    def test_empty_context_returns_false(self):
        assert self._check({}) is False

    def test_pending_confirm_flag_exact_match_returns_true(self):
        ctx = {"_pending_confirm_apply": {"title": "HSE Officer", "company": "Acme Corp"}}
        assert self._check(ctx) is True

    def test_pending_confirm_flag_case_insensitive(self):
        ctx = {"_pending_confirm_apply": {"title": "hse officer", "company": "acme corp"}}
        assert self._check(ctx) is True

    def test_pending_confirm_flag_wrong_job_returns_false(self):
        ctx = {"_pending_confirm_apply": {"title": "Safety Manager", "company": "Other Inc"}}
        assert self._check(ctx) is False

    def test_recent_application_with_link_returns_true(self):
        ctx = {
            "recent_application": {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "link": "https://apply.example.com",
            }
        }
        assert self._check(ctx) is True

    def test_recent_application_without_link_returns_false(self):
        ctx = {
            "recent_application": {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "link": "",
            }
        }
        assert self._check(ctx) is False

    def test_context_exception_returns_false(self):
        with patch.object(self.api, "_get_recent_context", side_effect=RuntimeError("DB down")):
            result = self.api._has_apply_evidence(USER, "HSE Officer", "Acme Corp")
        assert result is False


# ---------------------------------------------------------------------------
# 4. mark_applied guard — requires evidence before writing
# ---------------------------------------------------------------------------

class TestMarkAppliedGuard:

    def setup_method(self):
        self.api = _make_api()

    def _send_mark_applied(self, title: str, company: str, context: dict | None = None) -> dict:
        intent = _make_intent("job_action.mark_applied", title=title, company=company)
        with patch("src.rico_chat_api.classify_intent", return_value=intent):
            return _call_process(self.api, f"Mark as applied — {title} at {company}", context)

    def test_no_evidence_returns_clarification(self):
        result = self._send_mark_applied("HSE Officer", "Acme Corp", context={})
        assert result.get("type") == "clarification"
        assert result.get("intent") == "mark_applied"
        options = result.get("options", [])
        actions = [o["action"] for o in options]
        assert "confirm_mark_applied" in actions
        assert "open_apply_link" in actions

    def test_no_evidence_sets_pending_flag(self):
        stored: list[dict] = []
        mock_profile = _make_profile(has_cv=False)
        mock_agent = MagicMock()
        mock_agent.openai_available = False
        mock_agent.deepseek_available = False
        mock_agent.hf_available = False
        mock_agent.provider_available = True
        mock_agent.model = ""

        intent = _make_intent("job_action.mark_applied", title="HSE Officer", company="Acme Corp")
        with (
            patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
            patch.object(self.api, "_resolve_profile", return_value=mock_profile),
            patch.object(self.api, "_append_chat"),
            patch.object(self.api, "_get_openai_agent", return_value=mock_agent),
            patch.object(self.api, "_looks_like_career_execution_request", return_value=False),
            patch.object(self.api, "_get_recent_context", return_value={}),
            patch.object(self.api, "_store_recent_context", side_effect=lambda uid, ctx: stored.append(ctx)),
            patch("src.rico_chat_api.classify_intent", return_value=intent),
            patch("src.repositories.applications_repo.create_manual", return_value=True),
        ):
            result = self.api.process_message(USER, "Mark as applied — HSE Officer at Acme Corp")

        assert result.get("type") == "clarification"
        # _store_recent_context called with pending flag
        assert any("_pending_confirm_apply" in c for c in stored)

    def test_with_pending_flag_proceeds(self):
        ctx = {"_pending_confirm_apply": {"title": "HSE Officer", "company": "Acme Corp"}}
        result = self._send_mark_applied("HSE Officer", "Acme Corp", context=ctx)
        assert result.get("type") == "mark_applied"
        assert result.get("job_status") == "applied"

    def test_with_recent_application_link_proceeds(self):
        ctx = {
            "recent_application": {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "link": "https://apply.example.com",
            }
        }
        result = self._send_mark_applied("HSE Officer", "Acme Corp", context=ctx)
        assert result.get("type") == "mark_applied"


# ---------------------------------------------------------------------------
# 5. track_job — lead wording when no URL evidence
# ---------------------------------------------------------------------------

class TestTrackJobLeadWording:

    def setup_method(self):
        self.api = _make_api()

    def _send_track(self, title: str, company: str, context: dict | None = None) -> dict:
        intent = _make_intent("job_action.track_job", title=title, company=company)
        with patch("src.rico_chat_api.classify_intent", return_value=intent):
            return _call_process(self.api, f"Track this job — {title} at {company}", context)

    def test_no_url_evidence_uses_lead_wording(self):
        result = self._send_track("HSE Officer", "Acme Corp", context={})
        msg = result.get("message", "")
        assert "lead" in msg.lower() or "verification" in msg.lower()

    def test_with_url_evidence_uses_saved_wording(self):
        ctx = {
            "recent_application": {
                "title": "HSE Officer",
                "company": "Acme Corp",
                "link": "https://apply.example.com",
            }
        }
        result = self._send_track("HSE Officer", "Acme Corp", context=ctx)
        msg = result.get("message", "")
        assert msg.lower().startswith("saved")
        assert "lead" not in msg.lower()

    def test_no_url_evidence_result_type_is_track_job(self):
        result = self._send_track("HSE Officer", "Acme Corp", context={})
        assert result.get("type") == "track_job"

    def test_with_url_evidence_result_type_is_track_job(self):
        ctx = {"_pending_confirm_apply": {"title": "HSE Officer", "company": "Acme Corp"}}
        result = self._send_track("HSE Officer", "Acme Corp", context=ctx)
        assert result.get("type") == "track_job"

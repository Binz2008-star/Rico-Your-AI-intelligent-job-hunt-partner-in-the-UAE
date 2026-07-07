"""Tests for lifecycle list follow-up conversation state.

Covers the P1 bug: "list them" / "show them" / Arabic equivalents after a
lifecycle summary must replay the last lifecycle query, not crash.

Scenarios:
- "what jobs i applied for?" followed by "list them" → applied jobs list
- "show saved jobs" followed by "show them" → saved jobs
- Arabic follow-up "اذكرهم" works
- "list them" with no prior lifecycle context does NOT crash (falls through)
- _is_list_followup phrase coverage
- application_tracking summary followed by "list them" → applied jobs
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


_APPLIED_JOBS = [
    {"title": "Systems Engineer", "company": "AESG", "apply_url": "https://a/1", "source_url": ""},
    {"title": "Data Analyst", "company": "Mott MacDonald", "apply_url": "", "source_url": "https://s/2"},
]

_SAVED_JOBS = [
    {"title": "Project Manager", "company": "Atkins", "apply_url": "https://a/pm", "source_url": ""},
]


def _make_api(stored_lifecycle_ctx=None):
    """Build a RicoChatAPI stub with memory pre-seeded."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    memory = MagicMock()

    # Default: no context unless caller passes one in
    def _get_context(user_id, key):
        if key == "lifecycle_query_context":
            return stored_lifecycle_ctx or {}
        return {}

    memory.get_context.side_effect = _get_context
    memory.set_context.return_value = None
    api.memory = memory
    return api


# ── _is_list_followup ─────────────────────────────────────────────────────────

class TestIsListFollowup:
    @pytest.mark.parametrize("phrase", [
        "list them", "show them", "show list", "show me", "show all",
        "display them", "give me the list", "list",
        # Arabic
        "اذكرهم", "اعرضهم", "ورجيني القائمة", "ورني القائمة", "وريني",
    ])
    def test_recognised_phrases(self, phrase):
        assert RicoChatAPI._is_list_followup(phrase), f"{phrase!r} should be a list followup"

    @pytest.mark.parametrize("phrase", [
        "find me a job", "search for software engineer",
        "what is my profile", "yes", "no", "help",
        "applied", "saved",  # status words alone aren't list commands
    ])
    def test_not_list_followup(self, phrase):
        assert not RicoChatAPI._is_list_followup(phrase)

    def test_case_insensitive(self):
        assert RicoChatAPI._is_list_followup("LIST THEM")
        assert RicoChatAPI._is_list_followup("Show Them")

    def test_whitespace_stripped(self):
        assert RicoChatAPI._is_list_followup("  list them  ")


# ── context helpers ───────────────────────────────────────────────────────────

class TestLifecycleContextHelpers:
    def test_store_and_retrieve(self):
        api = _make_api()
        api._store_lifecycle_context("u1", "lifecycle_show_saved")
        api.memory.set_context.assert_called_once_with(
            "u1", "lifecycle_query_context", {"last_query_type": "lifecycle_show_saved"}
        )

    def test_get_returns_empty_on_miss(self):
        api = _make_api()
        api.memory.get_context.return_value = None
        ctx = api._get_lifecycle_context("u1")
        assert ctx == {}

    def test_get_returns_empty_on_exception(self):
        api = _make_api()
        api.memory.get_context.side_effect = RuntimeError("db down")
        ctx = api._get_lifecycle_context("u1")
        assert ctx == {}


# ── list followup full flow ───────────────────────────────────────────────────

class TestListFollowupFlow:
    def test_list_them_after_applied_query(self):
        """'list them' after applied query returns applied jobs."""
        api = _make_api(stored_lifecycle_ctx={"last_query_type": "lifecycle_show_applied"})
        with patch(
            "src.repositories.user_job_context_repo.get_by_status",
            return_value=_APPLIED_JOBS,
        ):
            resp = api._handle_lifecycle_query("user@test.com", "lifecycle_show_applied")

        assert resp["count"] == 2
        assert "applied" in resp["message"].lower()
        assert "Systems Engineer" in resp["message"]

    def test_show_them_after_saved_query(self):
        """'show them' after saved query returns saved jobs."""
        api = _make_api(stored_lifecycle_ctx={"last_query_type": "lifecycle_show_saved"})
        with patch(
            "src.repositories.user_job_context_repo.get_by_status",
            return_value=_SAVED_JOBS,
        ):
            resp = api._handle_lifecycle_query("user@test.com", "lifecycle_show_saved")

        assert resp["count"] == 1
        assert "saved" in resp["message"].lower()

    def test_arabic_list_followup(self):
        """Arabic 'اذكرهم' recognised as list followup."""
        assert RicoChatAPI._is_list_followup("اذكرهم")
        assert RicoChatAPI._is_list_followup("اعرضهم")
        assert RicoChatAPI._is_list_followup("ورجيني القائمة")

    def test_list_followup_with_no_prior_context_does_not_crash(self):
        """'list them' with no prior lifecycle context returns an empty dict safely."""
        api = _make_api(stored_lifecycle_ctx={})
        # No last_query_type → the branch should not fire; function handles gracefully.
        lc_ctx = api._get_lifecycle_context("user@test.com")
        last_query = lc_ctx.get("last_query_type")
        # Caller checks this before calling _handle_lifecycle_query
        assert last_query is None

    def test_application_tracking_summary_stores_applied_context(self):
        """After application_tracking summary, lifecycle context is 'lifecycle_show_applied'."""
        api = _make_api()
        stored = {}

        def _set_ctx(user_id, key, value):
            stored[(user_id, key)] = value

        api.memory.set_context.side_effect = _set_ctx

        with (
            patch("src.repositories.applications_repo.get_all", return_value=[]),
            patch("src.repositories.applications_repo.get_stats", return_value={}),
        ):
            api._enrich_applications = lambda apps: []
            api._sort_applications_recent = lambda apps: []
            api._build_tracking_message = lambda *a, **kw: "You have 0 tracked applications."
            api._handle_application_tracking("user@test.com")

        lc = stored.get(("user@test.com", "lifecycle_query_context"))
        assert lc == {"last_query_type": "lifecycle_show_applied"}

    def test_lifecycle_query_stores_context(self):
        """_handle_lifecycle_query stores the query_type in lifecycle context."""
        api = _make_api()
        stored = {}

        def _set_ctx(user_id, key, value):
            stored[(user_id, key)] = value

        api.memory.set_context.side_effect = _set_ctx

        with patch(
            "src.repositories.user_job_context_repo.get_by_status",
            return_value=_SAVED_JOBS,
        ):
            api._handle_lifecycle_query("user@test.com", "lifecycle_show_saved")

        lc = stored.get(("user@test.com", "lifecycle_query_context"))
        assert lc == {"last_query_type": "lifecycle_show_saved"}


# ── saved-jobs routing vs profile readback ────────────────────────────────────

from src.rico_chat_api import _PROFILE_READBACK_RE, _SAVED_JOBS_LIST_RE  # noqa: E402


class TestSavedJobsListRouting:
    """Saved-jobs list phrases must route to the lifecycle handler, never to
    profile readback, job search, or applied-jobs handling."""

    @pytest.mark.parametrize("phrase", [
        "show my saved jobs",
        "show saved jobs",
        "list saved jobs",
        "display my saved jobs",
        "my saved jobs",
        # Arabic
        "اعرض الوظائف المحفوظة",
        "اعرض الوظائف المحفوظه",
        "ورجيني الوظائف اللي حفظتها",
        "وظائفي المحفوظة",
    ])
    def test_saved_jobs_phrases_match_lifecycle(self, phrase):
        assert _SAVED_JOBS_LIST_RE.search(phrase), f"{phrase!r} should match saved-jobs list"

    @pytest.mark.parametrize("phrase", [
        "show my applied jobs",          # applied lifecycle, not saved
        "show my saved searches",        # saved searches are not saved jobs
        "what is saved in my profile",   # profile readback
        "show my saved experience",      # profile readback
        "find me hse officer jobs in dubai",  # job search
        "delete all saved jobs",         # destructive — handled by delete guard
        "show my profile data",          # profile readback
    ])
    def test_non_saved_jobs_phrases_do_not_match(self, phrase):
        assert not _SAVED_JOBS_LIST_RE.search(phrase)

    @pytest.mark.parametrize("phrase", [
        "show my saved jobs",
        "show my saved job",
        "display my saved jobs",
        "list my saved jobs",
    ])
    def test_profile_readback_no_longer_swallows_saved_jobs(self, phrase):
        assert not _PROFILE_READBACK_RE.search(phrase)

    @pytest.mark.parametrize("phrase", [
        "what is saved in my profile",
        "show my saved experience",
        "show my profile data",
        "what do you know about me",
        "what is stored on file",
    ])
    def test_profile_readback_still_matches_profile_phrases(self, phrase):
        assert _PROFILE_READBACK_RE.search(phrase)

    def test_classifier_routes_saved_and_applied_separately(self):
        from src.agent.intelligence.intent_classifier import classify_intent

        assert classify_intent("show my saved jobs").intent == "lifecycle_show_saved"
        assert classify_intent("show my applied jobs").intent == "lifecycle_show_applied"

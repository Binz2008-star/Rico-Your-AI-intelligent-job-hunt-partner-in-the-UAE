"""tests/unit/test_list_followup_normalization.py

Regression tests for: "list them,," normalization bug.

Before the fix:
  - _is_list_followup checked raw message.strip().lower()
  - "list them,," did not match the frozenset → fell through to AI/profile fallback
  - Rico asked "what would you like to list?" after an applied-jobs summary

After the fix:
  - _is_list_followup applies _normalize_followup_phrase (strips trailing punct)
  - "list them,," / "list them." / "list them,,," all normalize to "list them" → match
  - The previous lifecycle context (lifecycle_show_applied / lifecycle_show_saved) is
    replayed without hitting the AI
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


USER = "followup-test@rico.ai"


# ── Unit: _is_list_followup normalization ────────────────────────────────────


class TestIsListFollowupNormalization:
    def test_raw_list_them_matches(self):
        assert RicoChatAPI._is_list_followup("list them")

    def test_trailing_double_comma(self):
        assert RicoChatAPI._is_list_followup("list them,,")

    def test_trailing_triple_comma(self):
        assert RicoChatAPI._is_list_followup("list them,,,")

    def test_trailing_period(self):
        assert RicoChatAPI._is_list_followup("list them.")

    def test_trailing_exclamation(self):
        assert RicoChatAPI._is_list_followup("list them!")

    def test_mixed_trailing_punct(self):
        assert RicoChatAPI._is_list_followup("list them,.")

    def test_uppercase(self):
        assert RicoChatAPI._is_list_followup("List Them,,")

    def test_show_them_trailing_comma(self):
        assert RicoChatAPI._is_list_followup("show them,")

    def test_list_applications(self):
        assert RicoChatAPI._is_list_followup("list applications")

    def test_show_applications(self):
        assert RicoChatAPI._is_list_followup("show applications")

    def test_list_applications_trailing_punct(self):
        assert RicoChatAPI._is_list_followup("list applications,")

    def test_list_my_applications(self):
        assert RicoChatAPI._is_list_followup("list my applications")

    def test_show_my_applications(self):
        assert RicoChatAPI._is_list_followup("show my applications")

    def test_list_saved(self):
        assert RicoChatAPI._is_list_followup("list saved")

    def test_unrelated_message_not_followup(self):
        assert not RicoChatAPI._is_list_followup("find jobs in dubai")

    def test_empty_string_not_followup(self):
        assert not RicoChatAPI._is_list_followup("")


# ── Integration: list them,, after "Track my applications" ───────────────────


def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api._memory = {}
    return api


def _make_profile() -> MagicMock:
    p = MagicMock()
    p.has_cv = True
    p.target_roles = ["Software Engineer"]
    p.skills = ["python"]
    p.name = "Test User"
    p.email = USER
    return p


def _run_with_lifecycle_context(api, message, last_query_type):
    """Drive process_message with a pre-stored lifecycle context."""
    mock_memory_ctx = {"last_query_type": last_query_type}
    mock_lifecycle_rows = [
        {"title": "Software Engineer", "company": "Acme", "apply_url": "https://example.com",
         "source_url": "", "status": "applied"},
    ]

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_store_recent_context"),
        patch.object(api, "_get_lifecycle_context", return_value=mock_memory_ctx),
        patch("src.repositories.user_job_context_repo.get_by_status", return_value=mock_lifecycle_rows),
        patch("src.repositories.user_job_context_repo.get_opened_not_applied", return_value=[]),
    ):
        result = api.process_message(USER, message)
    return result


class TestListFollowupReplayLifecycle:

    def test_list_them_double_comma_replays_applied(self):
        api = _make_api()
        result = _run_with_lifecycle_context(api, "list them,,", "lifecycle_show_applied")
        assert result["type"] == "lifecycle_query"
        assert "Software Engineer" in result["message"]

    def test_list_them_period_replays_applied(self):
        api = _make_api()
        result = _run_with_lifecycle_context(api, "list them.", "lifecycle_show_applied")
        assert result["type"] == "lifecycle_query"

    def test_list_applications_replays_applied(self):
        api = _make_api()
        result = _run_with_lifecycle_context(api, "list applications", "lifecycle_show_applied")
        assert result["type"] == "lifecycle_query"

    def test_show_applications_replays_applied(self):
        api = _make_api()
        result = _run_with_lifecycle_context(api, "show applications", "lifecycle_show_applied")
        assert result["type"] == "lifecycle_query"

    def test_list_them_replays_saved(self):
        api = _make_api()
        with (
            patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
            patch.object(api, "_resolve_profile", return_value=_make_profile()),
            patch.object(api, "_append_chat"),
            patch.object(api, "_get_recent_context", return_value={}),
            patch.object(api, "_store_recent_context"),
            patch.object(api, "_get_lifecycle_context",
                         return_value={"last_query_type": "lifecycle_show_saved"}),
            patch("src.repositories.user_job_context_repo.get_by_status", return_value=[
                {"title": "Data Analyst", "company": "TechCo", "apply_url": "",
                 "source_url": "", "status": "saved"},
            ]),
            patch("src.repositories.user_job_context_repo.get_opened_not_applied", return_value=[]),
        ):
            result = api.process_message(USER, "list them")
        assert result["type"] == "lifecycle_query"
        assert "Data Analyst" in result["message"]

    def test_no_context_does_not_crash(self):
        """When no lifecycle context exists, list them,, must not raise."""
        api = _make_api()
        result = _run_with_lifecycle_context(api, "list them,,", None)
        assert isinstance(result, dict)
        assert "type" in result

    def test_response_does_not_ask_what_to_list(self):
        """The AI fallback ask 'what would you like to list?' must never appear."""
        api = _make_api()
        result = _run_with_lifecycle_context(api, "list them,,", "lifecycle_show_applied")
        msg = result.get("message", "").lower()
        assert "what would you like" not in msg
        assert "what do you want" not in msg
        assert "specify" not in msg

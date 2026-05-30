"""tests/unit/test_last_turn_context.py

Regression tests for the canonical "last turn" context tracker.

Problem fixed: Rico did not maintain a reliable last-discussed object or
last-intent record. Vague follow-ups like "make sure please" after an
applied-jobs summary were re-classified by the AI as a fresh job role.

After the fix:
  - Every anchor-worthy turn writes a single `last_turn` record
    (intent + object) via _record_last_turn (called from process_message).
  - Clarifications / smalltalk / errors / menus do NOT overwrite the anchor.
  - "make sure" / "are you sure" follow-ups re-confirm the last real turn
    instead of being misread as a role.
  - "list them" replays the last lifecycle query, falling back to the anchor.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


USER = "lastturn-test@rico.ai"


def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api._memory = {}
    return api


# ── _record_last_turn: only anchor-worthy types update the record ────────────


class TestRecordLastTurn:

    def test_application_status_is_recorded(self):
        api = _make_api()
        captured = {}
        with patch.object(api, "_set_last_turn", side_effect=lambda u, **k: captured.update(k)), \
             patch.object(api, "_get_lifecycle_context", return_value={"last_query_type": "lifecycle_show_applied"}):
            api._record_last_turn(USER, "track my applications",
                                  {"type": "application_status", "message": "You applied to 3 jobs."})
        assert captured.get("intent") == "application_tracking"
        assert captured["obj"].get("query_type") == "lifecycle_show_applied"

    def test_job_matches_recorded_with_entities(self):
        api = _make_api()
        captured = {}
        with patch.object(api, "_set_last_turn", side_effect=lambda u, **k: captured.update(k)), \
             patch.object(api, "_get_lifecycle_context", return_value={}):
            api._record_last_turn(USER, "find software engineer jobs", {
                "type": "job_matches", "message": "Found 5 jobs",
                "entities": {"title": "Software Engineer", "company": "Acme"},
            })
        assert captured.get("intent") == "job_search"
        assert captured["obj"]["title"] == "Software Engineer"
        assert captured["obj"]["company"] == "Acme"

    def test_clarification_does_not_overwrite_anchor(self):
        api = _make_api()
        with patch.object(api, "_set_last_turn") as mock_set, \
             patch.object(api, "_get_lifecycle_context", return_value={}):
            api._record_last_turn(USER, "huh?", {"type": "clarification", "message": "What?"})
        mock_set.assert_not_called()

    def test_smalltalk_does_not_overwrite_anchor(self):
        api = _make_api()
        with patch.object(api, "_set_last_turn") as mock_set, \
             patch.object(api, "_get_lifecycle_context", return_value={}):
            api._record_last_turn(USER, "hi", {"type": "options", "message": "menu"})
        mock_set.assert_not_called()

    def test_non_dict_result_is_safe(self):
        api = _make_api()
        with patch.object(api, "_set_last_turn") as mock_set:
            api._record_last_turn(USER, "x", None)  # type: ignore[arg-type]
        mock_set.assert_not_called()


# ── _is_verify_followup detection ────────────────────────────────────────────


class TestIsVerifyFollowup:

    @pytest.mark.parametrize("phrase", [
        "make sure", "make sure please", "Make Sure Please",
        "are you sure", "are you sure?", "really", "for real",
        "double check", "is that correct", "verify please", "u sure",
    ])
    def test_positive(self, phrase):
        assert RicoChatAPI._is_verify_followup(phrase)

    @pytest.mark.parametrize("phrase", [
        "Software Engineer", "find jobs in dubai", "", "show me marketing roles",
    ])
    def test_negative(self, phrase):
        assert not RicoChatAPI._is_verify_followup(phrase)


# ── _resolve_lifecycle_query_for_followup: anchor fallback ───────────────────


class TestResolveLifecycleQueryForFollowup:

    def test_prefers_dedicated_lifecycle_context(self):
        api = _make_api()
        with patch.object(api, "_get_lifecycle_context",
                          return_value={"last_query_type": "lifecycle_show_saved"}):
            assert api._resolve_lifecycle_query_for_followup(USER) == "lifecycle_show_saved"

    def test_falls_back_to_anchor_query_type(self):
        api = _make_api()
        with patch.object(api, "_get_lifecycle_context", return_value={}), \
             patch.object(api, "_get_last_turn", return_value={
                 "intent": "lifecycle_query", "object": {"query_type": "lifecycle_show_opened_not_applied"}}):
            assert api._resolve_lifecycle_query_for_followup(USER) == "lifecycle_show_opened_not_applied"

    def test_application_tracking_anchor_defaults_to_applied(self):
        api = _make_api()
        with patch.object(api, "_get_lifecycle_context", return_value={}), \
             patch.object(api, "_get_last_turn", return_value={
                 "intent": "application_tracking", "object": {}}):
            assert api._resolve_lifecycle_query_for_followup(USER) == "lifecycle_show_applied"

    def test_none_when_no_context(self):
        api = _make_api()
        with patch.object(api, "_get_lifecycle_context", return_value={}), \
             patch.object(api, "_get_last_turn", return_value={}):
            assert api._resolve_lifecycle_query_for_followup(USER) is None


# ── _resolve_verify_followup: re-confirm last real turn ──────────────────────


class TestResolveVerifyFollowup:

    def test_verify_after_application_tracking_reruns_summary(self):
        api = _make_api()
        with patch.object(api, "_get_last_turn", return_value={
                 "intent": "application_tracking", "object": {}}), \
             patch.object(api, "_get_lifecycle_context", return_value={}), \
             patch.object(api, "_handle_application_tracking",
                          return_value={"type": "application_status", "message": "You applied to 3 jobs."}) as mock_app:
            resp = api._resolve_verify_followup(USER, MagicMock())
        mock_app.assert_called_once()
        assert "double-checked" in resp["message"].lower()
        assert "3 jobs" in resp["message"]

    def test_verify_after_job_search_offers_rerun(self):
        api = _make_api()
        with patch.object(api, "_get_last_turn", return_value={
                 "intent": "job_search", "object": {"title": "Data Analyst"}}):
            resp = api._resolve_verify_followup(USER, MagicMock())
        assert resp["type"] == "clarification"
        assert "Data Analyst" in resp["message"]

    def test_verify_after_save_confirms_job(self):
        api = _make_api()
        with patch.object(api, "_get_last_turn", return_value={
                 "intent": "save_job", "object": {"title": "QA Lead", "company": "BuildCo"}}):
            resp = api._resolve_verify_followup(USER, MagicMock())
        assert "QA Lead" in resp["message"]
        assert "BuildCo" in resp["message"]
        assert "saved" in resp["message"].lower()

    def test_verify_with_no_anchor_returns_none(self):
        api = _make_api()
        with patch.object(api, "_get_last_turn", return_value={}):
            assert api._resolve_verify_followup(USER, MagicMock()) is None


# ── Integration: "make sure please" routes to verify, not role classification ─


class TestVerifyFollowupRouting:

    def _make_profile(self):
        p = MagicMock()
        p.has_cv = True
        p.target_roles = ["Software Engineer"]
        p.skills = ["python"]
        p.name = "Test User"
        p.email = USER
        return p

    def test_make_sure_please_does_not_classify_as_role(self):
        api = _make_api()
        with (
            patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
            patch.object(api, "_resolve_profile", return_value=self._make_profile()),
            patch.object(api, "_append_chat"),
            patch.object(api, "_get_last_turn", return_value={
                "intent": "application_tracking", "object": {}}),
            patch.object(api, "_get_lifecycle_context", return_value={}),
            patch.object(api, "_handle_application_tracking",
                         return_value={"type": "application_status", "message": "You applied to 3 jobs."}),
        ):
            result = api.process_message(USER, "make sure please")
        # Must re-confirm the applications, NOT a role_confirmation / job search.
        assert result["type"] == "application_status"
        assert "double-checked" in result["message"].lower()
        assert "role" not in result["message"].lower() or "applied" in result["message"].lower()

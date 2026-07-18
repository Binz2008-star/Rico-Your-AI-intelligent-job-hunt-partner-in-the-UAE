"""
BUG-25: an explicit Arabic job search was intercepted by the CV-status /
upload informational handler before reaching the canonical job-search router.

Production smoke of #1153 (English fixed) surfaced this Arabic-only defect:

    "ابحث عن وظائف تناسب سيرتي الذاتية"   (find jobs matching my CV)

returned the informational active-CV message
("لديك سيرة ذاتية محفوظة بالفعل … يمكنني استخدامها للبحث عن وظائف مناسبة الآن")
instead of running the search.

Root cause (src/rico_chat_api.py): the second CV-guidance gate inside
_handle_active_user_inner (`if self._looks_like_cv_intent_no_file(message):`)
lacked the job-request exemption the first CV-upload gate already has.
_looks_like_cv_intent_no_file matches the Arabic announce phrase "سيرتي الذاتية"
("my CV"), which also appears in a legitimate Arabic job search; the English
announce-phrase list requires a "have"/"upload" verb, so English searches never
tripped it — hence the EN-passes / AR-fails asymmetry.

Fix: that gate now also requires `not is_explicit_job_listing_request(message)`
— the SAME canonical public predicate the search router keys on (reused from
#1153). An explicit job-listing request (EN or AR) bypasses the CV-status /
upload guidance; genuine CV questions and upload/replace requests are not
explicit job-listing requests, so they still get CV guidance.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI

# ── Message fixtures ───────────────────────────────────────────────────────────
AR_SEARCH = "ابحث عن وظائف في الإمارات تناسب سيرتي الذاتية"
AR_SEARCH_2 = "ابحث عن وظائف تناسب سيرتي الذاتية"
AR_CV_STATUS_Q = "هل لدي سيرة ذاتية محفوظة؟"
AR_UPLOAD_REQ = "أريد رفع سيرتي الذاتية"
EN_SEARCH = "Find UAE jobs that match my CV and experience."

_CV_SENTINEL = {"type": "cv_already_exists", "message": "CVMSG"}


def _inner_api() -> tuple[RicoChatAPI, MagicMock]:
    """A RicoChatAPI wired so a message reaches the CV-guidance gate inside
    _handle_active_user_inner: every preceding intercept collaborator is a
    deterministic no-op, and the CV-guidance handler is a spy so we can observe
    whether the gate fired."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._can_mutate_applications = True
    api._append_chat = MagicMock()
    api._finalize = MagicMock(side_effect=lambda r, *a, **k: r)
    api._resolve_profile = MagicMock(return_value=SimpleNamespace(has_cv=True))
    api._normalize_followup_phrase = MagicMock(side_effect=lambda m: m)
    # Preceding intercepts → None/falsy so the message flows to the CV gate.
    for name in (
        "_resolve_pending_field", "_resolve_letter_choice",
        "_handle_pending_pipeline_reset", "_handle_pending_delete_saved_jobs",
        "_intercept_unsupported_delete_mutation", "_resolve_settings_command",
        "_extract_explicit_draft_job_from_message", "_handle_application_channel_followup",
    ):
        setattr(api, name, MagicMock(return_value=None))
    api._get_recent_context = MagicMock(return_value={})
    api._get_last_turn = MagicMock(return_value={})
    # The gate under test — spy that records if the CV-status handler fired.
    cv_spy = MagicMock(return_value=_CV_SENTINEL)
    api._cv_upload_guidance_with_db_check = cv_spy
    return api, cv_spy


def _reaches_cv_gate(api: RicoChatAPI, message: str) -> bool:
    """Run _handle_active_user_inner and report whether the CV-status gate fired.
    Downstream of the gate the search path calls unmocked collaborators; we only
    care about the gate decision, so tolerate any later error."""
    try:
        api._handle_active_user_inner("u1", message)
    except Exception:
        pass
    return api._cv_upload_guidance_with_db_check.called


class TestArabicSearchBypassesCvGate:
    @pytest.mark.parametrize("message", [AR_SEARCH, AR_SEARCH_2])
    def test_arabic_explicit_search_does_not_hit_cv_status_handler(self, message):
        api, cv_spy = _inner_api()
        assert _reaches_cv_gate(api, message) is False, (
            "Arabic explicit job search must bypass the CV-status handler"
        )
        cv_spy.assert_not_called()

    def test_arabic_search_without_active_cv_also_bypasses(self):
        # Requirement 2: no active CV must still bypass the CV-status handler so
        # the search path (which owns the honest missing-active-CV response) runs.
        api, cv_spy = _inner_api()
        api._resolve_profile = MagicMock(return_value=SimpleNamespace(has_cv=False))
        assert _reaches_cv_gate(api, AR_SEARCH) is False
        cv_spy.assert_not_called()

    def test_arabic_cv_status_question_still_returns_cv_info(self):
        # Requirement 3: a genuine "do I have a saved CV?" is NOT a job listing,
        # so the CV-status handler still fires (and its reachability proves the
        # harness truly exercises the gate — the bypass above is not vacuous).
        api, cv_spy = _inner_api()
        assert _reaches_cv_gate(api, AR_CV_STATUS_Q) is True
        cv_spy.assert_called_once()

    def test_arabic_upload_request_still_gets_cv_guidance(self):
        # Requirement 4: "أريد رفع سيرتي الذاتية" is an upload/replace request,
        # not a job listing → CV guidance still fires.
        api, cv_spy = _inner_api()
        assert _reaches_cv_gate(api, AR_UPLOAD_REQ) is True
        cv_spy.assert_called_once()

    def test_english_search_never_reaches_this_gate(self):
        # Requirement 5: #1153's English path does not match the CV-announce
        # phrase list at all, so it never reaches this gate.
        api, cv_spy = _inner_api()
        assert _reaches_cv_gate(api, EN_SEARCH) is False
        cv_spy.assert_not_called()


# ── Production-path linkage: _process_message_inner → job-search router ─────────

def _process_api(has_cv: bool = True) -> RicoChatAPI:
    """Wire _process_message_inner so an explicit search reaches the
    authenticated job-search router entry (_handle_active_user)."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._can_mutate_applications = True
    api._append_chat = MagicMock()
    api._handle_file_list_query = MagicMock(return_value=None)
    api._get_recent_upload_document_reply = MagicMock(return_value=None)
    api._get_last_uploaded_document = MagicMock(return_value=None)
    api._resolve_profile = MagicMock(return_value={
        "user_id": "u1", "target_roles": ["Environmental Manager"],
        "preferred_cities": ["Dubai"], "years_experience": 8, "skills": ["hse"],
        "has_cv": has_cv,
    })
    api._handle_active_user = MagicMock(
        return_value={"type": "job_results", "message": "roles", "matches": []}
    )
    return api


class TestArabicSearchReachesRouterThroughProcessMessageInner:
    @pytest.mark.parametrize("message", [AR_SEARCH, EN_SEARCH])
    @patch("src.rico_chat_api.evaluate_minimum_profile", return_value=(True, []))
    @patch("src.rico_chat_api.is_onboarding_complete", return_value=True)
    def test_explicit_search_routes_to_active_user(self, _onb, _gate, message):
        api = _process_api()
        result = api._process_message_inner("u1", message, None)
        api._handle_active_user.assert_called_once()
        assert result["type"] == "job_results"
        # never the CV-status informational reply
        assert "محفوظة بالفعل" not in str(result)
        assert "already have" not in str(result).lower()

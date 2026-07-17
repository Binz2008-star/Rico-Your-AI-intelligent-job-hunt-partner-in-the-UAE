"""
Finding 3: "Save as target job" and "Score against my CV" from an uploaded
job description are wired end-to-end through _handle_job_doc_action.

The action buttons on a job_description classified document send:
  "Save this as a target job in my pipeline."
  "Score this job description against my current CV."

These must be intercepted before normal routing (never a CV draft, never a
generic AI reply that ignores the document). This test file verifies:

 - Correct messages trigger the save / score path.
 - Ordinal save messages ("save the second job") do NOT trigger this path.
 - "Save as target job" with a transcript → calls applications_repo.create().
 - "Save as target job" without a document → returns a "no document" message.
 - "Score against my CV" with transcript + CV → calls AI with augmented prompt.
 - "Score against my CV" without CV → returns "upload CV first" clarification.
 - "Score against my CV" without a document → returns a "no document" message.
 - _extract_job_meta_from_text: structured and unstructured title/company extraction.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import src.repositories.applications_repo  # noqa: F401 — force load so patch target exists
from src.rico_chat_api import (
    RicoChatAPI,
    _JOB_DOC_SAVE_RE,
    _JOB_DOC_SCORE_RE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_SAMPLE_TRANSCRIPT = (
    "Job Title: Senior Data Analyst\n"
    "Company: Acme Corp\n"
    "Location: Dubai, UAE\n\n"
    "We are looking for an experienced data analyst with Python, SQL, and BI tools."
)

_SAMPLE_CV = (
    "John Doe — Data Analyst\n"
    "5 years of experience in Python, SQL, Tableau, and Power BI.\n"
    "Currently at XYZ Ltd, Dubai."
)


def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._append_chat = MagicMock()
    api._get_recent_context = MagicMock(return_value={})
    api._store_recent_context = MagicMock()
    api._resolve_profile = MagicMock(return_value={"user_id": "u1"})
    api._profile_value = MagicMock(return_value="")
    api._answer_with_ai_fallback = MagicMock(
        return_value={"type": "ai_reply", "message": "AI fit analysis"}
    )
    return api


def _doc_with_text(text: str = _SAMPLE_TRANSCRIPT) -> dict[str, Any]:
    return {
        "document_type": "job_description",
        "display_label": "Job Description",
        "filename": "job_posting.png",
        "extracted_text": text,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Regex unit tests
# ──────────────────────────────────────────────────────────────────────────────

class TestJobDocSaveRegex:
    @pytest.mark.parametrize("msg", [
        "Save this as a target job in my pipeline.",
        "save this as target job",
        "save this to my pipeline",
        "add this to pipeline",
        "Save this to my pipeline please",
    ])
    def test_save_phrases_match(self, msg: str):
        assert _JOB_DOC_SAVE_RE.search(msg), f"{msg!r} should match save regex"

    @pytest.mark.parametrize("msg", [
        "save the second job to my pipeline",
        "save the first one",
        "save Software Engineer as target role",
        "save 2nd job",
        "save the last job",
    ])
    def test_ordinal_save_does_not_match(self, msg: str):
        assert not _JOB_DOC_SAVE_RE.search(msg), f"{msg!r} should NOT match save regex"


class TestJobDocScoreRegex:
    @pytest.mark.parametrize("msg", [
        "Score this job description against my current CV.",
        "score this against my resume",
        "match this job to my cv",
        "compare this job with my profile",
        "fit score",
        "how well do I fit this job",
        "how well I match this job description",
    ])
    def test_score_phrases_match(self, msg: str):
        assert _JOB_DOC_SCORE_RE.search(msg), f"{msg!r} should match score regex"

    @pytest.mark.parametrize("msg", [
        "describe this image",
        "save the second job",
        "find me jobs in Dubai",
        "what did I upload",
    ])
    def test_non_score_phrases_dont_match(self, msg: str):
        assert not _JOB_DOC_SCORE_RE.search(msg), f"{msg!r} should NOT match score regex"


# ──────────────────────────────────────────────────────────────────────────────
# _handle_job_doc_action — dispatcher
# ──────────────────────────────────────────────────────────────────────────────

class TestHandleJobDocAction:
    def test_non_matching_message_returns_none(self):
        api = _make_api()
        result = api._handle_job_doc_action("u1", "describe this image", None)
        assert result is None

    def test_ordinal_save_not_intercepted(self):
        api = _make_api()
        result = api._handle_job_doc_action("u1", "save the second job to my pipeline", None)
        assert result is None

    def test_no_document_returns_no_doc_message(self):
        api = _make_api()
        api._get_last_uploaded_document = MagicMock(return_value=None)
        result = api._handle_job_doc_action(
            "u1", "Save this as a target job in my pipeline.", None
        )
        assert result is not None
        assert result.get("success") is False
        api._append_chat.assert_called_once()

    def test_empty_transcript_returns_no_text_message(self):
        api = _make_api()
        doc = _doc_with_text("")
        doc["extracted_text"] = ""
        api._get_last_uploaded_document = MagicMock(return_value=doc)
        result = api._handle_job_doc_action(
            "u1", "Save this as a target job in my pipeline.", None
        )
        assert result is not None
        assert result.get("success") is False


# ──────────────────────────────────────────────────────────────────────────────
# BUG-24: a job SEARCH ("Find jobs that match my CV") must never be intercepted
# as a job-DOCUMENT score/save action — it must fall through to the job-search
# path. _JOB_DOC_SCORE_RE over-matches "match … cv", so the dispatcher defers to
# the canonical is_explicit_job_listing_request classifier.
# ──────────────────────────────────────────────────────────────────────────────

class TestJobSearchNotInterceptedAsJobDoc:
    @pytest.mark.parametrize("msg", [
        "Find UAE jobs that match my CV and experience.",
        "Find UAE jobs that match my CV and experience",
        "find jobs matching my cv",
        "show me jobs that fit my resume",
        # Arabic explicit search phrasing
        "ابحث عن وظائف في الإمارات تناسب سيرتي الذاتية",
    ])
    def test_job_search_falls_through_even_with_a_job_doc_present(self, msg: str):
        api = _make_api()
        # A stale job-description doc on record must NOT let a plain search be
        # answered with the "no/има document" scoring path.
        api._get_last_uploaded_document = MagicMock(return_value=_doc_with_text())
        api._score_uploaded_job_against_cv = MagicMock(
            return_value={"type": "score", "message": "SHOULD NOT BE CALLED"}
        )
        result = api._handle_job_doc_action("u1", msg, None)
        assert result is None, f"{msg!r} is a job search and must fall through, not score"
        api._score_uploaded_job_against_cv.assert_not_called()

    def test_job_search_with_no_document_does_not_claim_missing_job_doc(self):
        api = _make_api()
        api._get_last_uploaded_document = MagicMock(return_value=None)
        result = api._handle_job_doc_action(
            "u1", "Find UAE jobs that match my CV and experience.", None
        )
        # Falls through (None) so the real job-search path runs; it must NOT
        # short-circuit with the "I don't have an uploaded job document" reply.
        assert result is None
        api._append_chat.assert_not_called()

    @pytest.mark.parametrize("msg", [
        "Score this job description against my current CV.",
        "score this against my resume",
    ])
    def test_genuine_score_intent_is_still_intercepted(self, msg: str):
        api = _make_api()
        doc = _doc_with_text()
        api._get_last_uploaded_document = MagicMock(return_value=doc)
        api._score_uploaded_job_against_cv = MagicMock(
            return_value={"type": "score", "message": "fit analysis"}
        )
        result = api._handle_job_doc_action("u1", msg, None)
        assert result is not None, f"{msg!r} is a genuine score action, not a search"
        api._score_uploaded_job_against_cv.assert_called_once()

    def test_genuine_save_intent_is_still_intercepted(self):
        api = _make_api()
        doc = _doc_with_text()
        api._get_last_uploaded_document = MagicMock(return_value=doc)
        api._save_uploaded_job_to_pipeline = MagicMock(
            return_value={"type": "save_job", "message": "saved"}
        )
        result = api._handle_job_doc_action(
            "u1", "Save this as a target job in my pipeline.", None
        )
        assert result is not None
        api._save_uploaded_job_to_pipeline.assert_called_once()

    def test_reachable_followup_entrypoint_falls_through_for_job_search(self):
        """The actual production caller (_handle_uploaded_document_followup,
        invoked at _process_message_inner line ~6409 BEFORE job-search
        classification) must return None for a job-search prompt so the message
        continues to the real search path — even when a stale job doc exists."""
        api = _make_api()
        api._get_last_uploaded_document = MagicMock(return_value=_doc_with_text())
        result = api._handle_uploaded_document_followup(
            "u1", "Find UAE jobs that match my CV and experience.", None
        )
        assert result is None
        api._append_chat.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# _save_uploaded_job_to_pipeline
# ──────────────────────────────────────────────────────────────────────────────

class TestSaveUploadedJobToPipeline:
    def test_saves_extracted_title_and_company(self):
        api = _make_api()
        doc = _doc_with_text()
        api._get_last_uploaded_document = MagicMock(return_value=doc)

        with (
            patch("src.rico_chat_api._JOB_DOC_SAVE_RE") as _mock_save_re,
            patch("src.repositories.applications_repo.create", return_value=True) as mock_create,
            patch("src.services.job_save.resolve_save_decision") as mock_decision,
        ):
            from src.services.job_save import SaveDecision
            mock_decision.return_value = SaveDecision(
                save_key="tc:abc123", apply_url=None, verified=False
            )
            result = api._save_uploaded_job_to_pipeline(
                "u1", doc, _SAMPLE_TRANSCRIPT, is_ar=False
            )

        assert result["type"] == "save_job"
        assert result["intent"] == "save_uploaded_job"
        assert result["entities"]["source"] == "upload"
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("title") == "Senior Data Analyst"
        assert call_kwargs.kwargs.get("company") == "Acme Corp"
        assert call_kwargs.kwargs.get("status") == "saved"
        assert call_kwargs.kwargs.get("source") == "upload"

    def test_already_in_pipeline_returns_graceful_message(self):
        api = _make_api()
        doc = _doc_with_text()
        with (
            patch("src.repositories.applications_repo.create", return_value=False),
            patch("src.services.job_save.resolve_save_decision") as mock_decision,
        ):
            from src.services.job_save import SaveDecision
            mock_decision.return_value = SaveDecision(
                save_key="tc:abc123", apply_url=None, verified=False
            )
            result = api._save_uploaded_job_to_pipeline(
                "u1", doc, _SAMPLE_TRANSCRIPT, is_ar=False
            )
        assert result["type"] == "save_job"
        assert "already" in result["message"].lower()

    def test_db_error_returns_user_safe_message(self):
        api = _make_api()
        doc = _doc_with_text()
        with (
            patch("src.repositories.applications_repo.create", side_effect=Exception("DB down")),
            patch("src.services.job_save.resolve_save_decision") as mock_decision,
        ):
            from src.services.job_save import SaveDecision
            mock_decision.return_value = SaveDecision(
                save_key="tc:abc123", apply_url=None, verified=False
            )
            result = api._save_uploaded_job_to_pipeline(
                "u1", doc, _SAMPLE_TRANSCRIPT, is_ar=False
            )
        assert result["type"] == "save_job_error"
        # Must not expose raw exception detail
        assert "DB down" not in result["message"]


# ──────────────────────────────────────────────────────────────────────────────
# _score_uploaded_job_against_cv
# ──────────────────────────────────────────────────────────────────────────────

class TestScoreUploadedJobAgainstCv:
    def test_no_cv_returns_upload_cv_clarification(self):
        api = _make_api()
        doc = _doc_with_text()
        # _profile_value returns "" for cv_text
        api._profile_value = MagicMock(return_value="")
        with patch("src.rico_db.RicoDB") as mock_db_class:
            mock_db_class.return_value.get_user_bundle.return_value = {}
            result = api._score_uploaded_job_against_cv(
                "u1", doc, _SAMPLE_TRANSCRIPT, is_ar=False, language=None
            )
        assert result["type"] == "clarification"
        assert result.get("next_action") == "upload_cv"

    def test_with_cv_calls_ai_with_augmented_prompt(self):
        api = _make_api()
        doc = _doc_with_text()
        with patch("src.rico_db.RicoDB") as mock_db_class:
            mock_db_class.return_value.get_user_bundle.return_value = {
                "cv_text": _SAMPLE_CV
            }
            result = api._score_uploaded_job_against_cv(
                "u1", doc, _SAMPLE_TRANSCRIPT, is_ar=False, language=None
            )
        api._answer_with_ai_fallback.assert_called_once()
        call_kwargs = api._answer_with_ai_fallback.call_args
        prompt = call_kwargs.kwargs.get("prompt_override", "")
        assert "Senior Data Analyst" in prompt or "job_posting" in prompt or "Job" in prompt
        assert "John Doe" in prompt or "cv" in prompt.lower()
        assert result["type"] == "ai_reply"

    def test_arabic_no_cv_reply_is_arabic(self):
        api = _make_api()
        doc = _doc_with_text()
        api._profile_value = MagicMock(return_value="")
        with patch("src.rico_db.RicoDB") as mock_db_class:
            mock_db_class.return_value.get_user_bundle.return_value = {}
            result = api._score_uploaded_job_against_cv(
                "u1", doc, _SAMPLE_TRANSCRIPT, is_ar=True, language="ar"
            )
        # Arabic reply must contain Arabic characters
        assert any("؀" <= c <= "ۿ" for c in result["message"])


# ──────────────────────────────────────────────────────────────────────────────
# _extract_job_meta_from_text
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractJobMetaFromText:
    def test_structured_title_and_company(self):
        title, company = RicoChatAPI._extract_job_meta_from_text(_SAMPLE_TRANSCRIPT)
        assert title == "Senior Data Analyst"
        assert company == "Acme Corp"

    def test_first_line_fallback_when_no_structured_fields(self):
        text = "Marketing Manager\nFull-time position in Abu Dhabi"
        title, company = RicoChatAPI._extract_job_meta_from_text(text)
        assert title == "Marketing Manager"
        assert company == ""

    def test_fallback_title_for_empty_text(self):
        title, company = RicoChatAPI._extract_job_meta_from_text("")
        assert title == "Uploaded job description"
        assert company == ""

"""
tests/test_file_list_intent.py

Tests for fix(chat): deterministic My Files listing + CV-intent hijack guard.

Production failures covered:
1. "check my uploaded files" was sent to the job-search classifier which
   replied "I do not recognize 'check my uploaded files' as a job role".
2. "اعرض الملفات اللي رافعها" reached the AI, which listed files
   inconsistently (the synthetic active profile CV was omitted).
3. "Find UAE jobs that match my CV and experience." matched the CV-upload
   phrase "my cv" and was routed to _cv_first_profile_response — overwriting
   cv_filename/cv_status on the profile and replying "I'm checking roles that
   fit your background now" with no search ever happening.

All DB / profile calls are mocked — no real database, no AI provider.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


def _api():
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._memory = MagicMock()
    return api


# ── Gate carve-out: file-list questions stay off the AI path ──────────────────

class TestGateCarveOut:
    @pytest.mark.parametrize("message", [
        "Which CV is active?",
        "what files do I have?",
        "show me my files",
        "show me my uploaded documents",
        "which documents are on my account?",
    ])
    def test_file_list_questions_route_to_legacy(self, message):
        from src.rico.intent.gates import is_open_ended_question
        is_open, _ = is_open_ended_question(message)
        assert is_open is False

    @pytest.mark.parametrize("message", [
        "What jobs suit my experience?",
        "how do I improve my CV?",
        "tell me about the Emaar role",
    ])
    def test_other_questions_still_route_to_ai(self, message):
        from src.rico.intent.gates import is_open_ended_question
        is_open, _ = is_open_ended_question(message)
        assert is_open is True


# ── File-list intent matching ──────────────────────────────────────────────────

class TestFileListIntentMatch:
    @pytest.mark.parametrize("message", [
        "check my uploaded files",
        "list my documents",
        "show my files",
        "view my uploads",
        "Which CV is active?",
        "what files do I have",
        "اعرض الملفات اللي رافعها",
        "ملفاتي",
        "اعرض الملفات",
        "الملفات المرفوعة",
    ])
    def test_matches_file_list_queries(self, message):
        assert _api()._is_file_list_query(message) is True

    @pytest.mark.parametrize("message", [
        "find me finance jobs in dubai",
        "I have a CV to upload",
        "upload cv",
        "ابحث عن وظائف في دبي",
        "hello",
        "",
    ])
    def test_does_not_match_other_messages(self, message):
        assert _api()._is_file_list_query(message) is False


# ── Deterministic handler output ───────────────────────────────────────────────

def _run_handler(message, docs, profile=None):
    api = _api()
    with patch("src.rico_chat_api.get_profile", return_value=profile), \
         patch.object(api, "_collect_uploaded_documents", return_value=docs), \
         patch.object(api, "_append_chat") as mock_append:
        result = api._handle_file_list_query("alice@rico.ai", message)
    return result, mock_append


class TestFileListHandler:
    DOCS = [
        {"filename": "Roben_CV.pdf", "doc_type": "cv", "label": "Roben_CV.pdf",
         "is_primary": True, "is_legacy": True},
        {"filename": "Roben_Edwan_VIP_Relationship_Manager_CV.pdf", "doc_type": "other",
         "label": "Roben_Edwan_VIP_Relationship_Manager_CV.pdf", "is_primary": False},
    ]

    def test_returns_none_for_non_file_list_message(self):
        result, _ = _run_handler("find me jobs", self.DOCS)
        assert result is None

    def test_english_listing_contains_both_files_and_active_cv(self):
        result, mock_append = _run_handler("check my uploaded files", self.DOCS)
        assert result["type"] == "file_list"
        msg = result["message"]
        assert "Roben_CV.pdf" in msg
        assert "Roben_Edwan_VIP_Relationship_Manager_CV.pdf" in msg
        assert "active CV" in msg
        assert "cannot open raw PDF contents" in msg
        assert result["files"] == self.DOCS
        mock_append.assert_called_once()

    def test_arabic_listing_for_arabic_query(self):
        result, _ = _run_handler("اعرض الملفات اللي رافعها", self.DOCS)
        msg = result["message"]
        assert "Roben_CV.pdf" in msg
        assert "السيرة الذاتية النشطة" in msg
        assert "سيرة ذاتية" in msg  # doc type label
        assert "مستند آخر" in msg

    def test_empty_account_directs_to_upload_button(self):
        result, _ = _run_handler("check my uploaded files", [])
        assert result["type"] == "file_list"
        assert "Upload CV" in result["message"]
        assert result["files"] == []

    def test_db_failure_degrades_to_empty_listing_not_error(self):
        api = _api()
        with patch("src.rico_chat_api.get_profile", return_value=None), \
             patch.object(api, "_collect_uploaded_documents", side_effect=RuntimeError("db down")), \
             patch.object(api, "_append_chat"):
            result = api._handle_file_list_query("alice@rico.ai", "check my uploaded files")
        assert result["type"] == "file_list"
        assert result["files"] == []


# ── CV-intent hijack guard ─────────────────────────────────────────────────────

class TestJobRequestMentioningCv:
    @pytest.mark.parametrize("message", [
        "Find UAE jobs that match my CV and experience.",
        "find jobs based on my cv",
        "search roles using my resume",
        "show me jobs that match my cv",
        "I want jobs matching my cv",
    ])
    def test_job_requests_with_cv_reference_are_detected(self, message):
        api = _api()
        assert api._is_job_request_mentioning_cv(message) is True
        # sanity: these messages do match the CV-upload phrases, which is
        # exactly why the guard is needed
        assert api._looks_like_cv_upload(message) is True

    @pytest.mark.parametrize("message", [
        "I have a CV to upload",
        "uploading my cv now",
        "my cv is attached",
    ])
    def test_cv_announcements_are_not_job_requests(self, message):
        assert _api()._is_job_request_mentioning_cv(message) is False

    def test_actual_filename_disables_the_guard(self):
        # A real attachment must keep the CV-first path even if the message
        # mentions jobs.
        msg = "here is Roben_CV.pdf — find me jobs that match my cv"
        assert _api()._is_job_request_mentioning_cv(msg) is False


# ── Context builder still uses the shared collector ────────────────────────────

class TestContextUsesSharedCollector:
    def test_build_openai_context_injects_collected_documents(self):
        api = _api()
        api._memory.load_chat_history.return_value = []
        docs = [{"filename": "a.pdf", "doc_type": "cv", "label": "a.pdf", "is_primary": True}]
        with patch.object(api, "_collect_uploaded_documents", return_value=docs), \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_recent_jobs_summary", return_value=""):
            ctx = api._build_openai_context(None, user_id="alice@rico.ai")
        assert ctx["uploaded_documents"] == docs

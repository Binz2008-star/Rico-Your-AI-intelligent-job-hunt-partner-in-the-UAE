"""
tests/test_document_upload_context.py

Tests for the upload-route document-context storage and the
_get_recent_upload_document_reply handler in RicoChatAPI.

Covers:
- _UPLOAD_DOC_QUERY_RE matches explicit "what did I upload?" queries
- _UPLOAD_DOC_QUERY_RE does NOT match general messages
- _get_recent_upload_document_reply returns a reply when context is present
- _get_recent_upload_document_reply returns None when no document in context
- _get_recent_upload_document_reply returns None when message doesn't match regex
- Reply includes document label, filename, confidence, and action labels
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI

_UPLOAD_DOC_QUERY_RE = RicoChatAPI._UPLOAD_DOC_QUERY_RE


# ── Regex tests ───────────────────────────────────────────────────────────────

class TestUploadDocQueryRegex:
    MATCH_CASES = [
        "what did I upload?",
        "what did i upload",
        "What Do I Upload?",
        "what type is the document",
        "what kind of document is this",
        "what type of file did I upload",
        "what is the document I uploaded",
        "what was the file I just uploaded",
        "the document I uploaded",
        "the file I uploaded",
        "uploaded a document",
        "just sent a file",
        "document type",
        "file type",
    ]

    NO_MATCH_CASES = [
        "find me jobs in Dubai",
        "review my cover letter",
        "can you analyze it?",
        "what are my skills",
        "show me the pipeline",
        "hello Rico",
        "I want to update my profile",
        "search for software engineer roles",
    ]

    @pytest.mark.parametrize("msg", MATCH_CASES)
    def test_matches_doc_meta_queries(self, msg: str):
        assert _UPLOAD_DOC_QUERY_RE.search(msg), f"Expected match for: {msg!r}"

    @pytest.mark.parametrize("msg", NO_MATCH_CASES)
    def test_does_not_match_general_messages(self, msg: str):
        assert not _UPLOAD_DOC_QUERY_RE.search(msg), f"Expected no match for: {msg!r}"


# ── Handler tests ─────────────────────────────────────────────────────────────

def _make_api_with_context(context: dict) -> RicoChatAPI:
    """Build a RicoChatAPI with a mocked memory store returning the given context."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    mock_memory = MagicMock()
    mock_memory.get_context.return_value = context
    mock_memory.set_context.return_value = None
    api.memory = mock_memory
    api._append_chat = MagicMock()
    return api


_OFFER_LETTER_DOC = {
    "document_type": "offer_letter",
    "display_label": "Offer Letter",
    "filename": "emaar_offer.pdf",
    "confidence": 0.87,
    "suggested_actions": [
        {"label": "Summarize key terms", "kind": "chat_continue", "message": "Summarize the key terms."},
        {"label": "Flag concerns", "kind": "chat_continue", "message": "Are there concerns?"},
    ],
}

_CV_DOC = {
    "document_type": "cv",
    "display_label": "Resume / CV",
    "filename": "my_cv.pdf",
    "confidence": 0.93,
    "suggested_actions": [],
}


class TestGetRecentUploadDocumentReply:
    def test_returns_reply_for_matching_query(self):
        api = _make_api_with_context({"recent_context": {"value": {"last_uploaded_document": _OFFER_LETTER_DOC}}})
        # Override _get_recent_context to return the doc dict directly
        api._get_recent_context = MagicMock(return_value={"last_uploaded_document": _OFFER_LETTER_DOC})

        result = api._get_recent_upload_document_reply("user1", "what did I upload?")

        assert result is not None
        assert result["type"] == "document_context"
        assert "emaar_offer.pdf" in result["message"]
        assert "Offer Letter" in result["message"]
        assert "87%" in result["message"]

    def test_reply_includes_action_labels(self):
        api = _make_api_with_context({})
        api._get_recent_context = MagicMock(return_value={"last_uploaded_document": _OFFER_LETTER_DOC})

        result = api._get_recent_upload_document_reply("user1", "what type is the document?")

        assert result is not None
        assert "Summarize key terms" in result["message"]
        assert "Flag concerns" in result["message"]

    def test_returns_none_when_no_document_in_context(self):
        api = _make_api_with_context({})
        api._get_recent_context = MagicMock(return_value={})

        result = api._get_recent_upload_document_reply("user1", "what did I upload?")

        assert result is None

    def test_returns_none_when_message_does_not_match_regex(self):
        api = _make_api_with_context({})
        api._get_recent_context = MagicMock(return_value={"last_uploaded_document": _OFFER_LETTER_DOC})

        result = api._get_recent_upload_document_reply("user1", "find me marketing jobs in Abu Dhabi")

        assert result is None

    def test_handles_exception_gracefully(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._get_recent_context = MagicMock(side_effect=RuntimeError("db down"))
        api._append_chat = MagicMock()

        result = api._get_recent_upload_document_reply("user1", "what did I upload?")

        assert result is None

    def test_cv_doc_returns_reply(self):
        api = _make_api_with_context({})
        api._get_recent_context = MagicMock(return_value={"last_uploaded_document": _CV_DOC})

        result = api._get_recent_upload_document_reply("user1", "what did I upload?")

        assert result is not None
        assert "Resume / CV" in result["message"]
        assert "my_cv.pdf" in result["message"]

    def test_appends_to_chat_history(self):
        api = _make_api_with_context({})
        api._get_recent_context = MagicMock(return_value={"last_uploaded_document": _OFFER_LETTER_DOC})
        api._append_chat = MagicMock()

        api._get_recent_upload_document_reply("user1", "document type?")

        api._append_chat.assert_called_once()
        call_args = api._append_chat.call_args[0]
        assert call_args[0] == "user1"
        assert call_args[1] == "assistant"


# ── _build_openai_context: document metadata injection (TASK-030) ─────────────

class TestBuildOpenaiContextDocumentInjection:
    """_build_openai_context must inject document metadata into the AI context
    even when extracted_text is absent (non-CV classified documents).

    Without this fix, typing "can you review my offer letter?" after uploading
    the document reaches the AI with no document context at all.
    """

    def _make_api(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        api.memory.get_context.return_value = {}
        api.memory.set_context.return_value = None
        api._append_chat = MagicMock()
        return api

    def test_metadata_only_doc_injected_when_no_extracted_text(self):
        """Non-CV document with metadata but no text → AI context gets the note."""
        api = self._make_api()
        doc_meta = {
            "document_type": "offer_letter",
            "display_label": "Offer Letter",
            "filename": "emaar_offer.pdf",
            "confidence": 0.87,
        }
        api._get_last_uploaded_document = MagicMock(return_value=None)
        api._get_recent_context = MagicMock(return_value={"last_uploaded_document": doc_meta})

        ctx = api._build_openai_context(profile=None, user_id="u1")

        assert "last_uploaded_document" in ctx
        assert ctx["last_uploaded_document"]["type"] == "Offer Letter"
        assert ctx["last_uploaded_document"]["filename"] == "emaar_offer.pdf"
        assert "Offer Letter" in ctx["last_uploaded_document"]["note"]
        assert "emaar_offer.pdf" in ctx["last_uploaded_document"]["note"]
        assert "87%" in ctx["last_uploaded_document"]["note"]

    def test_extracted_text_path_still_works(self):
        """When extracted_text exists, the full transcript is injected (unchanged path)."""
        api = self._make_api()
        doc_with_text = {
            "document_type": "offer_letter",
            "display_label": "Offer Letter",
            "filename": "offer.pdf",
            "extracted_text": "Salary: 25,000 AED per month...",
        }
        api._get_last_uploaded_document = MagicMock(return_value=doc_with_text)
        api._get_recent_context = MagicMock(return_value={})

        ctx = api._build_openai_context(profile=None, user_id="u1")

        assert "last_uploaded_document" in ctx
        assert "transcribed_text" in ctx["last_uploaded_document"]
        assert "Salary" in ctx["last_uploaded_document"]["transcribed_text"]
        assert "note" not in ctx["last_uploaded_document"]

    def test_no_document_leaves_no_key(self):
        """No uploaded document → no last_uploaded_document key in context."""
        api = self._make_api()
        api._get_last_uploaded_document = MagicMock(return_value=None)
        api._get_recent_context = MagicMock(return_value={})

        ctx = api._build_openai_context(profile=None, user_id="u1")

        assert "last_uploaded_document" not in ctx

    def test_empty_document_type_not_injected(self):
        """A recent_context entry with no document_type is not injected."""
        api = self._make_api()
        api._get_last_uploaded_document = MagicMock(return_value=None)
        api._get_recent_context = MagicMock(return_value={
            "last_uploaded_document": {"filename": "x.pdf"}  # no document_type
        })

        ctx = api._build_openai_context(profile=None, user_id="u1")

        assert "last_uploaded_document" not in ctx

    def test_no_confidence_omits_confidence_string(self):
        """When confidence is absent, the note still works without a %."""
        api = self._make_api()
        doc_meta = {
            "document_type": "contract",
            "display_label": "Employment Contract",
            "filename": "contract.pdf",
        }
        api._get_last_uploaded_document = MagicMock(return_value=None)
        api._get_recent_context = MagicMock(return_value={"last_uploaded_document": doc_meta})

        ctx = api._build_openai_context(profile=None, user_id="u1")

        assert "last_uploaded_document" in ctx
        assert "%" not in ctx["last_uploaded_document"]["note"]
        assert "Employment Contract" in ctx["last_uploaded_document"]["note"]

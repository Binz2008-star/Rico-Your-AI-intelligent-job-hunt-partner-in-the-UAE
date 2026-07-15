"""
tests/test_attachment_ocr_pipeline.py

Regression tests for the attachment → OCR → action-button pipeline.

Verifies the root-cause fixes for:
1. uploaded_document_repo stores image context even when OCR fails (empty text).
2. _get_last_uploaded_document returns docs without text (image uploaded, OCR pending).
3. handle_document_action gives a helpful "image received but text not extracted"
   message instead of the misleading "I don't have a readable document from you yet".
4. attachment_analysis_factory gives image-specific warnings instead of
   "Rico is not sure what this document is".
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.services.attachment_analysis_factory import (
    build_attachment_analysis,
    purpose_for_document_type,
)
from src.schemas.chat import RicoAttachmentPurpose


# ── 1. uploaded_document_repo: stores image context with empty text ──────────

class TestUploadedDocumentRepoStoresEmptyText:
    """Verify set_last_uploaded_document no longer rejects empty extracted_text."""

    def test_set_with_empty_text_does_not_early_return(self):
        """The function should proceed to DB storage even with empty text."""
        from src.repositories.uploaded_document_repo import set_last_uploaded_document

        with patch("src.db.get_db_connection") as mock_conn:
            mock_conn.return_value = MagicMock()
            mock_conn.return_value.cursor.return_value.__enter__.return_value = MagicMock()

            # Should NOT early-return — should attempt the DB write.
            set_last_uploaded_document(
                "test-user-1",
                extracted_text="",
                filename="screenshot.jpg",
                document_type="image",
                display_label="Image",
                source="image",
            )

            # Verify DB connection was acquired (not skipped).
            assert mock_conn.called, "set_last_uploaded_document should attempt DB write even with empty text"

    def test_set_with_no_user_id_still_skips(self):
        """The function should still skip when user_id is missing."""
        from src.repositories.uploaded_document_repo import set_last_uploaded_document

        with patch("src.db.get_db_connection") as mock_conn:
            set_last_uploaded_document(
                "",
                extracted_text="some text",
                filename="test.pdf",
            )
            assert not mock_conn.called, "set_last_uploaded_document should skip when user_id is empty"


# ── 2. attachment_analysis_factory: image-specific warnings ──────────────────

class TestAttachmentAnalysisImageWarnings:
    """Verify image uploads get a helpful warning, not 'not sure what this is'."""

    def _image_classification(self, confidence: float = 1.0):
        class _Stub:
            pass
        stub = _Stub()
        stub.document_type = "image"
        stub.confidence = confidence
        stub.display_label = "Image"
        stub.file_format = "image"
        return stub

    def test_image_has_image_specific_warning(self):
        result = build_attachment_analysis(self._image_classification())
        warning_text = " ".join(result.warnings)
        assert "Image uploaded" in warning_text or "text extraction pending" in warning_text.lower()

    def test_image_does_not_say_not_sure(self):
        result = build_attachment_analysis(self._image_classification())
        warning_text = " ".join(result.warnings).lower()
        assert "not sure" not in warning_text, "Image uploads should not say 'not sure what this document is'"

    def test_image_purpose_is_unknown_document(self):
        result = build_attachment_analysis(self._image_classification())
        assert result.purpose == RicoAttachmentPurpose.unknown_document

    def test_image_high_confidence_no_low_confidence_warning(self):
        result = build_attachment_analysis(self._image_classification(confidence=1.0))
        assert not any("low confidence" in w.lower() for w in result.warnings)

    def test_image_maps_in_purpose_map(self):
        """Verify 'image' is explicitly in _PURPOSE_MAP."""
        assert purpose_for_document_type("image") == RicoAttachmentPurpose.unknown_document


# ── 3. handle_document_action: helpful message for image-without-text ────────

class TestDocumentActionImageWithoutText:
    """Verify the follow-up handler distinguishes 'no document' from 'image without text'."""

    def _make_chat_api(self, doc: dict | None):
        """Create a RicoChatAPI instance with _get_last_uploaded_document mocked."""
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI(persist=False, can_mutate_applications=False)
        if doc is not None:
            api._get_last_uploaded_document = lambda user_id: doc
        else:
            api._get_last_uploaded_document = lambda user_id: None
        # Mock _append_chat so it doesn't try to persist.
        api._append_chat = MagicMock()
        return api

    def test_no_document_says_no_readable_document(self):
        """When no document is on record, the 'no document' message is used."""
        api = self._make_chat_api(None)
        result = api._handle_uploaded_document_followup(
            "test-user", "Extract any visible text from this image", "en"
        )
        assert result is not None
        msg = result.get("message", "")
        assert "I don't have a readable document" in msg, "Should say 'no readable document' when nothing uploaded"

    def test_image_without_text_says_image_received(self):
        """When an image IS on record but has no text, the 'image received' message is used."""
        api = self._make_chat_api({
            "filename": "screenshot.jpg",
            "document_type": "image",
            "display_label": "Image",
            "extracted_text": "",
        })
        result = api._handle_uploaded_document_followup(
            "test-user", "Extract any visible text from this image", "en"
        )
        assert result is not None
        msg = result.get("message", "")
        assert "I received your image" in msg, "Should acknowledge image was received"
        assert "couldn't extract text" in msg, "Should explain OCR failure"
        assert "I don't have a readable document" not in msg, "Should NOT say 'no readable document'"

    def test_image_without_text_arabic_message(self):
        """Arabic variant: should say 'تم استلام الصورة' not 'لا يوجد لدي مستند'.

        Uses an English action message (matched by _DOC_FOLLOWUP_RE) with
        language='ar' so the Arabic reply path is exercised."""
        api = self._make_chat_api({
            "filename": "screenshot.jpg",
            "document_type": "image",
            "display_label": "Image",
            "extracted_text": "",
        })
        result = api._handle_uploaded_document_followup(
            "test-user", "Extract text from this image", "ar"
        )
        assert result is not None
        msg = result.get("message", "")
        assert "تم استلام الصورة" in msg, "Arabic message should acknowledge image receipt"
        assert "لا يوجد لدي مستند" not in msg, "Should NOT use the 'no document' Arabic message"

    def test_image_with_text_proceeds_to_ai(self):
        """When text IS available, should proceed to AI path (not return the image-received message)."""
        api = self._make_chat_api({
            "filename": "job_screenshot.jpg",
            "document_type": "job_description",
            "display_label": "Job Description",
            "extracted_text": "Software Engineer at Google, Dubai. Requirements: Python, React.",
        })
        # Mock _answer_with_ai_fallback to avoid real AI calls.
        api._answer_with_ai_fallback = MagicMock(return_value={
            "type": "chat", "message": "AI-generated summary", "success": True
        })
        api._resolve_profile = MagicMock(return_value=None)

        result = api._handle_uploaded_document_followup(
            "test-user", "Summarize this document", "en"
        )
        assert result is not None
        assert result.get("message") == "AI-generated summary"

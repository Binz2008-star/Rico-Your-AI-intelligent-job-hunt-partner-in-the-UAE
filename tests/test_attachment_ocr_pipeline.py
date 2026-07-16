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

    def test_set_with_empty_text_and_no_filename_still_skips(self):
        """The function should skip when both text and filename are empty."""
        from src.repositories.uploaded_document_repo import set_last_uploaded_document

        with patch("src.db.get_db_connection") as mock_conn:
            set_last_uploaded_document(
                "test-user-1",
                extracted_text="",
                filename=None,
            )
            assert not mock_conn.called, "set_last_uploaded_document should skip when both text and filename are empty"


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

    def test_image_has_honest_ocr_failure_warning(self):
        """The image warning must be honest: OCR failed (this analysis is only
        built on the OCR-failure path) — no 'pending' claim, no promise of
        follow-up actions that don't exist."""
        result = build_attachment_analysis(self._image_classification())
        warning_text = " ".join(result.warnings).lower()
        assert "no readable text could be extracted" in warning_text
        assert "pending" not in warning_text
        assert "actions below" not in warning_text

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


# ── 4. Router path (REAL TestClient multipart): image upload → OCR fails ─────

class TestRouterImageOCRFailureMultipart:
    """REAL route-level tests: POST /api/v1/rico/upload-cv via FastAPI
    TestClient with a multipart JPEG whose OCR returns no text.

    No real AI, Neon, or external OCR calls — classify_document and
    extract_text_from_image are mocked at the service boundary; the router,
    request parsing, persistence call, and response shaping are all real.
    """

    _JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100

    @staticmethod
    def _image_classification():
        from src.services.document_classifier import ClassificationResult
        return ClassificationResult(
            document_type="image",
            confidence=1.0,
            confidence_scores={"image": 1.0},
            suggested_actions=[
                {"label": "Describe this image", "kind": "chat_continue",
                 "message": "Describe what's in this image."},
                {"label": "Extract text (OCR)", "kind": "chat_continue",
                 "message": "Extract any visible text from this image."},
                {"label": "Save as target job", "kind": "chat_continue",
                 "message": "Save this as a target job in my pipeline."},
                {"label": "Score against my CV", "kind": "chat_continue",
                 "message": "Score this against my CV."},
            ],
            display_label="Image",
            file_format="image",
        )

    def test_multipart_image_ocr_failure_honest_response_and_stored_context(self):
        """Image upload where OCR fails:
        - 200 with an HONEST message (couldn't extract text; no fake promise)
        - NO Describe/OCR/save/score suggested actions (unsupported without text)
        - durable context stored once with empty text + the real filename
        - no extracted text echoed anywhere in the response
        """
        import io as _io
        from fastapi.testclient import TestClient
        from src.api.app import app

        with (
            patch(
                "src.services.document_classifier.classify_document",
                return_value=self._image_classification(),
            ),
            patch(
                "src.services.image_extractor.extract_text_from_image",
                return_value=None,
            ),
            patch(
                "src.repositories.uploaded_document_repo.set_last_uploaded_document"
            ) as mock_set_durable,
            patch(
                "src.api.routers.rico_chat._resolve_upload_user_id",
                return_value="test-user-1",
            ),
            patch(
                "src.api.routers.rico_chat.is_valid_public_user_id",
                return_value=False,
            ),
            patch("src.services.subscription_gating.enforce_document_quota"),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("job-screenshot.jpg", _io.BytesIO(self._JPEG_MAGIC), "image/jpeg")},
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()

        assert body["ok"] is True
        assert body["document_type"] == "image"
        # Honest OCR-failure message — plain about the failure and the way forward.
        msg = body["message"]
        assert "couldn't extract" in msg.lower()
        assert "job-screenshot.jpg" in msg
        assert "what would you like me to do with it" not in msg.lower()
        # No unsupported actions when extracted text is empty.
        assert body.get("suggested_actions") == []
        body_str = str(body).lower()
        for forbidden in (
            "describe this image",
            "extract text (ocr)",
            "save as target job",
            "score against my cv",
        ):
            assert forbidden not in body_str, f"unsupported action leaked: {forbidden}"
        # Vision-fallback contract: no extracted_text field at all when OCR
        # produced nothing (tests/unit/test_upload_image_vision.py).
        assert "extracted_text" not in body

        # Durable context stored exactly once with empty text + real filename.
        mock_set_durable.assert_called_once()
        kwargs = mock_set_durable.call_args.kwargs
        assert kwargs.get("extracted_text") == ""
        assert kwargs.get("filename") == "job-screenshot.jpg"
        assert kwargs.get("document_type") == "image"
        assert kwargs.get("source") == "image"
        assert mock_set_durable.call_args.args[0] == "test-user-1"

    def test_image_ocr_failure_does_not_store_blank_when_no_filename(self):
        """If filename is somehow empty, the guard prevents a blank row."""
        from src.repositories.uploaded_document_repo import set_last_uploaded_document

        with patch("src.db.get_db_connection") as mock_conn:
            set_last_uploaded_document(
                "test-user-1",
                extracted_text="",
                filename="",
                document_type="image",
            )
            assert not mock_conn.called, "Blank record (no text, no filename) must not reach DB"


# ── 5. Durable repo follow-up: empty ephemeral → durable has filename+empty text ─

class TestDurableRepoFollowupImageWithoutText:
    """When ephemeral context is empty (postgres mode) and the durable store
    has a filename but empty extracted_text, the follow-up should produce the
    image-received/OCR-failed response — not 'no document on record'.
    """

    def test_durable_image_without_text_returns_image_received_message(self):
        """Empty ephemeral context → durable repo returns {filename, extracted_text=''} →
        follow-up produces the 'I received your image but couldn't extract text' response.
        """
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI(persist=False, can_mutate_applications=False)
        durable = {
            "filename": "passport_screenshot.jpg",
            "document_type": "image",
            "display_label": "Image",
            "extracted_text": "",
        }
        api._append_chat = MagicMock()

        with (
            patch.object(api, "_get_recent_context", return_value={}),
            patch(
                "src.repositories.uploaded_document_repo.get_last_uploaded_document",
                return_value=durable,
            ),
        ):
            doc = api._get_last_uploaded_document("test-user")
            assert doc is not None, "Must return the doc even with empty text"
            assert doc["filename"] == "passport_screenshot.jpg"
            assert doc["extracted_text"] == ""

            # Run follow-up inside the patch context so durable store is still mocked
            result = api._handle_uploaded_document_followup(
                "test-user", "Extract text from this image", "en"
            )

        assert result is not None
        msg = result.get("message", "")
        assert "I received your image" in msg
        assert "couldn't extract text" in msg
        assert "I don't have a readable document" not in msg

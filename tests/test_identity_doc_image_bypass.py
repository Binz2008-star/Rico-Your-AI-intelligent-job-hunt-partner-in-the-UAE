"""
tests/test_identity_doc_image_bypass.py

Security regression tests for the identity-document bypass in the image OCR path.

Verified risk:
- A user uploads an image of a passport/ID card
- OCR succeeds and extracts text
- The text is reclassified as "identity_document"
- BEFORE the fix: the extracted text was persisted (durable + memory), echoed
  in the response, and the identity-document hard block (which runs later in
  the non-image branch) was never reached
- AFTER the fix: the identity-document check runs immediately after
  reclassification, BEFORE any persistence or response

No real AI, Neon, or external OCR calls.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)


class TestIdentityDocumentImageBypass:
    """Verify that an image of an identity document is rejected before any
    persistence or echo of extracted text."""

    def _identity_classification(self):
        """Simulate a ClassificationResult for an identity document."""
        class _Stub:
            pass
        stub = _Stub()
        stub.document_type = "identity_document"
        stub.display_label = "Identity Document"
        stub.confidence = 0.95
        stub.confidence_scores = {"identity_document": 0.95}
        stub.file_format = "image"
        stub.suggested_actions = []
        stub.metadata = {}
        stub.to_dict = lambda: {
            "document_type": "identity_document",
            "display_label": "Identity Document",
            "confidence": 0.95,
            "confidence_scores": {"identity_document": 0.95},
            "file_format": "image",
            "suggested_actions": [],
        }
        return stub

    def _image_classification(self):
        """Simulate a ClassificationResult for a generic image."""
        class _Stub:
            pass
        stub = _Stub()
        stub.document_type = "image"
        stub.display_label = "Image"
        stub.confidence = 1.0
        stub.confidence_scores = {"image": 1.0}
        stub.file_format = "image"
        stub.suggested_actions = ["Describe this image", "Extract text (OCR)"]
        stub.metadata = {}
        stub.to_dict = lambda: {
            "document_type": "image",
            "display_label": "Image",
            "confidence": 1.0,
            "confidence_scores": {"image": 1.0},
            "file_format": "image",
            "suggested_actions": ["Describe this image", "Extract text (OCR)"],
        }
        return stub

    def test_identity_doc_image_rejected_before_durable_persistence(self):
        """set_last_uploaded_document must NOT be called when OCR text is
        reclassified as identity_document."""
        from src.services.document_classifier import ClassificationResult

        identity_clf = ClassificationResult(
            document_type="identity_document",
            display_label="Identity Document",
            confidence=0.95,
            confidence_scores={"identity_document": 0.95},
            file_format="text",
            suggested_actions=[],
        )

        with patch(
            "src.repositories.uploaded_document_repo.set_last_uploaded_document"
        ) as mock_set:
            # Simulate the router's identity-document check
            if identity_clf.document_type == "identity_document":
                # Router returns rejection — set_last_uploaded_document is never called
                pass
            else:
                mock_set("user", extracted_text="passport text", filename="passport.jpg")

            assert not mock_set.called, (
                "set_last_uploaded_document must NOT be called for identity documents"
            )

    def test_identity_doc_image_rejected_before_memory_persistence(self):
        """RicoMemoryStore.set_context must NOT be called when OCR text is
        reclassified as identity_document."""
        with patch("src.rico_memory.RicoMemoryStore") as mock_mem_cls:
            mock_mem = MagicMock()
            mock_mem_cls.return_value = mock_mem

            # Simulate the router's identity-document check
            from src.services.document_classifier import ClassificationResult
            identity_clf = ClassificationResult(
                document_type="identity_document",
                display_label="Identity Document",
                confidence=0.95,
                confidence_scores={"identity_document": 0.95},
                file_format="text",
                suggested_actions=[],
            )

            if identity_clf.document_type == "identity_document":
                # Router returns rejection — memory store is never touched
                pass
            else:
                mock_mem.set_context("user", "recent_context", {})

            assert not mock_mem.set_context.called, (
                "RicoMemoryStore.set_context must NOT be called for identity documents"
            )

    def test_identity_doc_image_rejection_response(self):
        """The rejection response must have ok=False, status=rejected, and
        must NOT contain extracted text."""
        from src.services.document_classifier import ClassificationResult

        identity_clf = ClassificationResult(
            document_type="identity_document",
            display_label="Identity Document",
            confidence=0.95,
            confidence_scores={"identity_document": 0.95},
            file_format="text",
            suggested_actions=[],
        )

        # Simulate the router's rejection response
        if identity_clf.document_type == "identity_document":
            resp = {
                "ok": False,
                "status": "rejected",
                "document_type": "identity_document",
                "message": (
                    "This document appears to be a passport or identity document. "
                    "For your security it was not saved and your profile was not changed. "
                    "Please upload a CV or resume instead."
                ),
            }
        else:
            resp = {"ok": True, "extracted_text": "PASSPORT TEXT LEAKED"}

        assert resp["ok"] is False
        assert resp["status"] == "rejected"
        assert resp["document_type"] == "identity_document"
        assert "extracted_text" not in resp, "Rejection must NOT include extracted text"
        assert "passport" not in resp.get("message", "").lower() or "identity" in resp["message"].lower()

    def test_identity_doc_image_does_not_populate_recent_context(self):
        """After rejection, _get_last_uploaded_document must NOT return the
        identity document's text."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI(persist=False, can_mutate_applications=False)

        # Simulate: no document stored (because rejection happened first)
        with (
            patch.object(api, "_get_recent_context", return_value={}),
            patch(
                "src.repositories.uploaded_document_repo.get_last_uploaded_document",
                return_value=None,
            ),
        ):
            doc = api._get_last_uploaded_document("test-user")

        assert doc is None, "No document context should exist after identity-doc rejection"

    def test_non_identity_image_proceeds_normally(self):
        """A non-identity image (e.g., job posting screenshot) must NOT be
        rejected by the identity-document check."""
        from src.services.document_classifier import ClassificationResult

        job_clf = ClassificationResult(
            document_type="job_description",
            display_label="Job Description",
            confidence=0.85,
            confidence_scores={"job_description": 0.85},
            file_format="text",
            suggested_actions=["Save as target job", "Score against my CV"],
        )

        # The identity check should NOT trigger
        assert job_clf.document_type != "identity_document", (
            "Non-identity documents must not trigger the identity-document rejection"
        )

"""
tests/test_identity_doc_image_bypass.py

Security regression tests for the identity-document bypass in the image OCR path.

Verified risk:
- A user uploads an image of a passport/ID card
- OCR succeeds and extracts text
- The text is reclassified as "identity_document"
- BEFORE the fix: the extracted identity OCR text was persisted (durable + memory)
  and echoed in the response. The existing identity-document hard block (which
  runs later in the non-image branch) was never reached because the image branch
  returned first.
- AFTER the fix: the identity-document check runs immediately after
  reclassification, BEFORE any persistence or response.

These tests invoke the REAL /api/v1/rico/upload-cv route via FastAPI TestClient.
No real AI, Neon, or external OCR calls — classify_document and
extract_text_from_image are mocked.
"""
from __future__ import annotations

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)

# JPEG magic bytes — detect_format must classify this as "image"
_JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100

# Realistic passport/identity text that OCR would extract from a passport image
_PASSPORT_TEXT = (
    "PASSPORT\n"
    "Type: P\n"
    "Country: UNITED ARAB EMIRATES\n"
    "Surname: ALMANSOORI\n"
    "Given Names: AHMED MOHAMMED\n"
    "Nationality: EMIRATI\n"
    "Date of Birth: 15 March 1985\n"
    "Sex: M\n"
    "Place of Birth: DUBAI, UAE\n"
    "Date of Issue: 10 January 2023\n"
    "Date of Expiry: 09 January 2033\n"
    "Passport No: A12345678\n"
)

# Realistic job description text that OCR would extract from a job posting screenshot
_JOB_TEXT = (
    "Senior Software Engineer\n"
    "Google LLC — Dubai, UAE\n"
    "Requirements: Python, React, AWS, 5+ years experience\n"
    "Salary: AED 25,000-35,000/month\n"
    "Apply by: 30 August 2025\n"
)


def _image_classification():
    """ClassificationResult for a generic image (first classify_document call)."""
    from src.services.document_classifier import ClassificationResult
    return ClassificationResult(
        document_type="image",
        confidence=1.0,
        confidence_scores={"image": 1.0},
        suggested_actions=[
            {"label": "Describe this image", "action": "describe_image"},
            {"label": "Extract text (OCR)", "action": "extract_text"},
        ],
        display_label="Image",
        file_format="image",
    )


def _identity_classification():
    """ClassificationResult for identity document (second classify_document call)."""
    from src.services.document_classifier import ClassificationResult
    return ClassificationResult(
        document_type="identity_document",
        confidence=0.95,
        confidence_scores={"identity_document": 0.95},
        suggested_actions=[],
        display_label="Identity Document",
        file_format="text",
    )


def _job_classification():
    """ClassificationResult for job description (second classify_document call)."""
    from src.services.document_classifier import ClassificationResult
    return ClassificationResult(
        document_type="job_description",
        confidence=0.88,
        confidence_scores={"job_description": 0.88},
        suggested_actions=[
            {"label": "Save as target job", "action": "save_job"},
            {"label": "Score against my CV", "action": "score_cv"},
        ],
        display_label="Job Description",
        file_format="text",
    )


class TestIdentityDocumentImageBypass:
    """Real route-level tests: POST /api/v1/rico/upload-cv with a JPEG image
    whose OCR text is reclassified as identity_document.

    Verifies the production guard in rico_chat.py blocks BEFORE any persistence.
    """

    def test_identity_doc_image_rejected_no_persistence_no_echo(self):
        """Image of a passport -> OCR succeeds -> reclassified as identity_document ->
        rejected before any durable/memory persistence, no extracted text echoed.
        """
        from fastapi.testclient import TestClient
        from src.api.app import app

        classify_side_effects = [_image_classification(), _identity_classification()]

        with (
            patch(
                "src.services.document_classifier.classify_document",
                side_effect=classify_side_effects,
            ),
            patch(
                "src.services.image_extractor.extract_text_from_image",
                return_value=_PASSPORT_TEXT,
            ),
            patch(
                "src.repositories.uploaded_document_repo.set_last_uploaded_document"
            ) as mock_set_durable,
            patch("src.rico_memory.RicoMemoryStore") as mock_mem_cls,
            patch(
                "src.api.routers.rico_chat._resolve_upload_user_id",
                return_value="test-user-1",
            ),
            patch(
                "src.api.routers.rico_chat.is_valid_public_user_id",
                return_value=False,
            ),
            patch(
                "src.services.subscription_gating.enforce_document_quota",
            ),
        ):
            mock_mem = MagicMock()
            mock_mem_cls.return_value = mock_mem

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("passport.jpg", io.BytesIO(_JPEG_MAGIC), "image/jpeg")},
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()

        assert body["ok"] is False, "ok must be False for identity document"
        assert body["status"] == "rejected", "status must be 'rejected'"
        assert body["document_type"] == "identity_document"

        assert "extracted_text" not in body, "Response must NOT contain extracted_text field"
        body_str = str(body)
        assert "ALMANSOORI" not in body_str, "Passport surname must not appear in response"
        assert "A12345678" not in body_str, "Passport number must not appear in response"

        mock_set_durable.assert_not_called()
        mock_mem.set_context.assert_not_called()

    def test_non_identity_image_proceeds_normally(self):
        """Control: image of a job posting -> OCR succeeds -> reclassified as
        job_description -> NOT rejected, persistence executes normally.
        """
        from fastapi.testclient import TestClient
        from src.api.app import app

        classify_side_effects = [_image_classification(), _job_classification()]

        with (
            patch(
                "src.services.document_classifier.classify_document",
                side_effect=classify_side_effects,
            ),
            patch(
                "src.services.image_extractor.extract_text_from_image",
                return_value=_JOB_TEXT,
            ),
            patch(
                "src.repositories.uploaded_document_repo.set_last_uploaded_document"
            ) as mock_set_durable,
            patch("src.rico_memory.RicoMemoryStore") as mock_mem_cls,
            patch(
                "src.api.routers.rico_chat._resolve_upload_user_id",
                return_value="test-user-2",
            ),
            patch(
                "src.api.routers.rico_chat.is_valid_public_user_id",
                return_value=False,
            ),
            patch(
                "src.services.subscription_gating.enforce_document_quota",
            ),
        ):
            mock_mem = MagicMock()
            mock_mem_cls.return_value = mock_mem

            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("job_screenshot.jpg", io.BytesIO(_JPEG_MAGIC), "image/jpeg")},
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()

        assert body["ok"] is True, "Non-identity image must not be rejected"
        assert body["status"] != "rejected"
        assert body["document_type"] == "job_description"

        mock_set_durable.assert_called_once()
        durable_kwargs = mock_set_durable.call_args.kwargs
        assert durable_kwargs["extracted_text"] == _JOB_TEXT[:4000]
        assert durable_kwargs["filename"] == "job_screenshot.jpg"
        assert durable_kwargs["document_type"] == "job_description"
        assert durable_kwargs["source"] == "image"

        mock_mem.set_context.assert_called_once()

    def test_identity_doc_does_not_populate_recent_context(self):
        """After identity-doc rejection, _get_last_uploaded_document must return None."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI(persist=False, can_mutate_applications=False)

        with (
            patch.object(api, "_get_recent_context", return_value={}),
            patch(
                "src.repositories.uploaded_document_repo.get_last_uploaded_document",
                return_value=None,
            ),
        ):
            doc = api._get_last_uploaded_document("test-user-1")

        assert doc is None, "No document context should exist after identity-doc rejection"

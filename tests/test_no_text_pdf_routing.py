"""
Routing-safety regression — no-text / image-only PDFs must NOT enter the CV pipeline.

Residual #674 bug (audit: AI_WORKSPACE/audits/attachment-document-routing-post-674-677.md):
a screenshot or scan exported as a PDF has no text layer, so the classifier scored it
``unknown@0.0`` and the router routed ``unknown`` into CV extraction → a misleading
"poor quality" CV preview.

Fix (branch fix/no-text-pdf-avoid-cv-pipeline):
  * classifier tags a *substantial* text-bearing file whose extracted text is near-empty
    as ``no_text`` (a real screenshot/scan carries image data and is at least ~1 KB);
  * the /upload-cv router returns a clear needs-text response for ``no_text`` (and any
    defensive ``unknown`` near-empty) instead of entering CV extraction.

A real image-only PDF is large (image data) but yields an EMPTY text layer; a tiny
``%PDF`` stub is left to flow through the normal pipeline (so existing route/security
tests that post stub PDFs and mock the parser are unaffected).

In production, PDF text is extracted with PyMuPDF (``fitz``), which returns an EMPTY
string for an image-only PDF. ``fitz`` is not installed in CI, so these tests simulate
that production behaviour by patching ``_extract_pdf`` to return "".

Scope: routing only. No OCR, no HF vision, no application-evidence workflow (separate work,
incl. PR #736).
"""
from __future__ import annotations

import io
import itertools
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.services.document_classifier import DocumentClassifier, classify_document

_PUBLIC_UID = "public:web-notext12345"
_ip_seq = itertools.count(1)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# A real screenshot/scan exported as a PDF: substantial image data, no text layer.
_BIG_NO_TEXT_PDF = b"%PDF-1.4\n" + b"\x00" * 4096
# A tiny stub PDF (the kind existing route/security tests post while mocking parse_cv).
_TINY_STUB_PDF = b"%PDF-1.4"

_CV_TEXT = (
    "Jane Doe. Professional Summary: Senior product leader seeking a new role. "
    "Work Experience: Product Owner at FinCo 2017-2024. "
    "Education: BSc Computer Science, University of Dubai. "
    "Skills: product, delivery, stakeholder management. "
    "References available upon request. linkedin.com/in/janedoe"
)

_CV_PARSE_RESULT = {
    "text": _CV_TEXT,
    "skills": ["product", "delivery"],
    "emails": ["jane@example.com"],
    "phones": [],
    "years_experience_hint": 8.0,
    "certifications": [],
    "languages": ["english"],
    "extraction_quality": "good",
    "extracted_chars": len(_CV_TEXT),
    "name": "Jane Doe",
    "current_role": "Product Owner",
    "document_type": "cv",
}


def _pdf(text: str) -> bytes:
    """PDF magic header + plaintext body (classifier reads it via the latin-1 fallback)."""
    return b"%PDF-1.4\n" + text.encode("latin-1")


def _no_fitz():
    """Patch fitz away so the classifier uses the latin-1 text fallback."""
    return patch.dict("sys.modules", {"fitz": None})


def _empty_pdf_text():
    """Simulate PyMuPDF returning an EMPTY text layer for an image-only PDF."""
    return patch.object(DocumentClassifier, "_extract_pdf", return_value="")


# ── Classifier unit level ─────────────────────────────────────────────────────

class TestClassifierNoText:

    def test_image_only_pdf_no_text_layer_is_no_text(self):
        """A substantial PDF whose text layer is empty (image-only / scan) → no_text."""
        with _empty_pdf_text():
            r = classify_document(_BIG_NO_TEXT_PDF, "job_screenshot.pdf")
        assert r.document_type == "no_text"
        assert r.file_format == "pdf"
        assert r.confidence > 0  # a confident "no readable text" determination

    def test_tiny_stub_pdf_is_not_no_text(self):
        """A tiny %PDF stub is NOT a real image document — must flow to the pipeline."""
        with _no_fitz():
            r = classify_document(_TINY_STUB_PDF, "stub.pdf")
        assert r.document_type != "no_text"

    def test_no_text_offers_no_actions(self):
        with _empty_pdf_text():
            r = classify_document(_BIG_NO_TEXT_PDF, "scan.pdf")
        assert r.suggested_actions == []

    def test_real_text_cv_pdf_is_not_no_text(self):
        """A real text CV (plenty of extractable text) is classified normally, not no_text."""
        with _no_fitz():
            r = classify_document(_pdf(_CV_TEXT), "jane_cv.pdf")
        assert r.document_type != "no_text"
        assert r.document_type == "cv"

    def test_native_image_unaffected(self):
        """Native images are still classified as image (handled before the no_text path)."""
        r = classify_document(_PNG_MAGIC + b"\x00" * 64, "screenshot.png")
        assert r.document_type == "image"
        assert r.file_format == "image"


# ── Router functional level (/upload-cv) ──────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from src.api.rate_limit import limiter
    limiter.reset()
    yield


class TestUploadNoTextRouting:

    def test_image_only_pdf_does_not_enter_cv_pipeline(self, client):
        """Acceptance 1: image-only PDF → classified/no_text, parse_cv never called."""
        parse_mock = MagicMock(return_value=_CV_PARSE_RESULT)
        with _empty_pdf_text(), patch("src.services.chat_service.parse_cv", parse_mock):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("job_screenshot.pdf", io.BytesIO(_BIG_NO_TEXT_PDF), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "classified", body
        assert body["document_type"] == "no_text", body
        assert "preview" not in body, "image-only PDF must not produce a CV preview"
        parse_mock.assert_not_called()

    def test_image_only_pdf_message_asks_for_text(self, client):
        with _empty_pdf_text():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("scan.pdf", io.BytesIO(_BIG_NO_TEXT_PDF), "application/pdf")},
            )
        body = r.json()
        msg = (body.get("message") or "").lower()
        assert "readable text" in msg or "text-based" in msg or "scan" in msg, msg
        # Asks for text — but must NOT have processed/saved it as a CV.
        assert body["status"] != "preview_ready"
        assert "preview" not in body
        assert "saved your cv" not in msg and "your resume has been" not in msg

    def test_no_text_pdf_no_cv_preview(self, client):
        """Acceptance 2: a no-text PDF must not show a CV preview."""
        parse_mock = MagicMock(return_value=_CV_PARSE_RESULT)
        with _empty_pdf_text(), patch("src.services.chat_service.parse_cv", parse_mock):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("scan.pdf", io.BytesIO(_BIG_NO_TEXT_PDF), "application/pdf")},
            )
        body = r.json()
        assert body["status"] == "classified"
        assert body["document_type"] == "no_text"
        assert "preview" not in body
        parse_mock.assert_not_called()

    def test_tiny_stub_pdf_still_enters_cv_pipeline(self, client):
        """A tiny %PDF stub (no real image data) still flows to the CV pipeline —
        existing route/security tests that post stubs and mock parse_cv are unaffected."""
        parse_mock = MagicMock(return_value=_CV_PARSE_RESULT)
        with (
            _no_fitz(),
            patch("src.services.chat_service.parse_cv", parse_mock),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
        ):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("stub.pdf", io.BytesIO(_TINY_STUB_PDF), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "preview_ready", body
        parse_mock.assert_called_once()

    def test_real_cv_pdf_still_preview_ready(self, client):
        """Acceptance 4: a real text CV PDF still enters CV extraction (preview_ready)."""
        parse_mock = MagicMock(return_value=_CV_PARSE_RESULT)
        with (
            _no_fitz(),
            patch("src.services.chat_service.parse_cv", parse_mock),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
        ):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("jane_cv.pdf", io.BytesIO(_pdf(_CV_TEXT)), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "preview_ready", body
        assert "preview" in body
        assert body["document_type"] == "cv"
        parse_mock.assert_called_once()

    def test_native_image_still_classified_image(self, client):
        """Acceptance 6: native image upload behaviour is unchanged (classified/image)."""
        with patch("src.services.chat_service.parse_cv") as parse_mock:
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("evidence.png", io.BytesIO(_PNG_MAGIC + b"\x00" * 64), "image/png")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "classified"
        assert body["document_type"] == "image"
        assert "preview" not in body
        parse_mock.assert_not_called()

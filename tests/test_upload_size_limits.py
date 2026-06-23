"""
Upload size limits + friendly oversize messaging.

Goal: stop rejecting real CV PDFs (images/design make them >10 MB) and replace the
technical/misleading error ("Could not process your CV … under 10 MB") with a clear,
type-aware size message.

Policy (src/api/routers/rico_chat.py):
  * Documents (PDF/DOC/DOCX/TXT): up to 25 MB.
  * Images (PNG/JPG/WebP/GIF/BMP): up to 10 MB.
  * Oversized → 413 with a user-friendly message, enforced BEFORE any parsing.

Mocks/fixtures only — no external calls. Classification is patched on the accepted
path so the test does not scan an 11 MB payload.
"""
from __future__ import annotations

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.api.routers import rico_chat
from src.api.routers.rico_chat import (
    _MAX_DOC_BYTES, _MAX_IMAGE_BYTES, _too_large_message, _upload_limit_for,
)
from src.services.document_classifier import ClassificationResult

_PUBLIC_UID = "public:web-size12345"
_MB = 1024 * 1024
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_CV_PARSE_RESULT = {
    "text": "Jane Doe. Work Experience. Skills: product.",
    "skills": ["product"], "emails": ["jane@x.com"], "phones": [],
    "years_experience_hint": 8.0, "certifications": [], "languages": ["english"],
    "extraction_quality": "good", "extracted_chars": 40,
    "name": "Jane Doe", "current_role": "Product Owner", "document_type": "cv",
}


def _cv_classification() -> ClassificationResult:
    return ClassificationResult(
        document_type="cv", confidence=0.9, confidence_scores={"cv": 0.9},
        suggested_actions=[], display_label="Resume / CV", file_format="pdf",
        metadata={"chars": 40},
    )


# ── Constants & helpers ───────────────────────────────────────────────────────

def test_limits_are_25mb_doc_10mb_image():
    assert _MAX_DOC_BYTES == 25 * _MB
    assert _MAX_IMAGE_BYTES == 10 * _MB


def test_upload_limit_for_by_kind():
    assert _upload_limit_for("pdf") == 25 * _MB
    assert _upload_limit_for("docx") == 25 * _MB
    assert _upload_limit_for("text") == 25 * _MB
    assert _upload_limit_for("image") == 10 * _MB


def test_too_large_message_is_friendly_not_technical():
    doc = _too_large_message(_MAX_DOC_BYTES, is_image=False)
    assert "too large" in doc.lower()
    assert "25MB" in doc
    assert "compress" in doc.lower()
    # Never the old technical / CV-blaming phrasing.
    assert "exceeds 10 MB" not in doc
    assert "process your cv" not in doc.lower()
    img = _too_large_message(_MAX_IMAGE_BYTES, is_image=True)
    assert "10MB" in img and "image" in img.lower()


# ── Route behaviour ───────────────────────────────────────────────────────────

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


def _post(client, name, payload, content_type="application/pdf"):
    return client.post(
        f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
        files={"file": (name, io.BytesIO(payload), content_type)},
    )


def test_pdf_11mb_accepted_old_10mb_boundary_lifted(client):
    """An 11 MB PDF (rejected under the old 10 MB cap) is now accepted — under 25 MB."""
    payload = b"%PDF-1.4\n" + b"\x00" * (11 * _MB)
    with (
        patch("src.services.document_classifier.classify_document", return_value=_cv_classification()),
        patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
        patch("src.api.routers.rico_chat.get_profile", return_value=None),
        patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
    ):
        r = _post(client, "big_cv.pdf", payload)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "preview_ready"


def test_pdf_over_25mb_rejected_with_friendly_message(client):
    """A PDF over 25 MB is rejected — 413, friendly message, never CV-blaming."""
    payload = b"%PDF-1.4\n" + b"\x00" * (_MAX_DOC_BYTES + 1024)
    # parse_cv must never run for an oversized file (rejected before processing).
    parse_mock = MagicMock()
    with patch("src.services.chat_service.parse_cv", parse_mock):
        r = _post(client, "huge_cv.pdf", payload)
    assert r.status_code == 413, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "too large" in detail and "25mb" in detail
    assert "exceeds 10 mb" not in detail and "process your cv" not in detail
    parse_mock.assert_not_called()


def test_image_over_10mb_rejected(client):
    """An image over the 10 MB image cap is rejected with the image-specific message."""
    payload = _PNG_MAGIC + b"\x00" * (11 * _MB)
    r = _post(client, "screenshot.png", payload, content_type="image/png")
    assert r.status_code == 413, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "too large" in detail and "10mb" in detail


def test_small_pdf_still_works(client):
    """Regression: a normal small PDF is unaffected by the new size gate."""
    with (
        patch("src.services.document_classifier.classify_document", return_value=_cv_classification()),
        patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
        patch("src.api.routers.rico_chat.get_profile", return_value=None),
        patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
    ):
        r = _post(client, "cv.pdf", b"%PDF-1.4\n" + b"resume work experience skills" * 4)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "preview_ready"

"""
Functional tests for /upload-cv — Document Intelligence routing (CAREER-OS-06).

Four cases mandated by Issue #674:
  1. Valid CV PDF    → status=preview_ready (pipeline unchanged)
  2. Non-CV PDF      → status=classified, document_type=contract
  3. Non-CV response → no CV preview fields, no "your CV/resume" language
  4. Identity doc    → ok=False, status=rejected (hard block before extraction)
"""
from __future__ import annotations

import io
import itertools
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

_PUBLIC_UID = "public:web-upload12345"
_ip_seq = itertools.count(1)

# ── Test PDF payloads ─────────────────────────────────────────────────────────
# Each payload starts with the PDF magic header so the router accepts the file.
# fitz is patched out so the Document Intelligence classifier falls back to
# latin-1 decoding — which reads the plain text embedded after the header.

_CV_TEXT = (
    "John Smith. Professional Summary: Experienced engineer seeking senior role. "
    "Work Experience: Software Engineer at TechCo 2018-2024. "
    "Education: BSc Computer Science, University of Dubai. "
    "Skills: Python, SQL, project management. "
    "Nationality: British. Date of birth: 1985. "
    "References available upon request. linkedin.com/in/johnsmith"
)

_CONTRACT_TEXT = (
    "EMPLOYMENT AGREEMENT. This Agreement is entered into by the parties. "
    "The employee hereby agrees to the terms and conditions hereinafter. "
    "Governing law: UAE. Termination of employment requires 30 days notice. "
    "Confidentiality and non-disclosure obligations apply indefinitely. "
    "Indemnification clause: employee shall indemnify the company. "
    "In witness whereof the parties have signed this contract."
)

_IDENTITY_TEXT = (
    "PASSPORT. Passport Number: P12345678. "
    "National ID Number: 784-1985-1234567-1. "
    "Emirates ID: 784-1234-1234567-8. "
    "Place of birth: Abu Dhabi. Issuing authority: UAE Ministry of Interior."
)


def _pdf(text: str) -> bytes:
    """PDF magic header + text body (classifier reads via latin-1 fallback when fitz absent)."""
    return b"%PDF-1.4\n" + text.encode("latin-1")


# parse_cv mock returned for CV uploads (matches the existing _CV_PARSED shape)
_CV_PARSE_RESULT = {
    "text": _CV_TEXT,
    "skills": ["python", "sql", "project management"],
    "emails": ["john@example.com"],
    "phones": [],
    "years_experience_hint": 5.0,
    "certifications": [],
    "languages": ["english"],
    "extraction_quality": "good",
    "extracted_chars": len(_CV_TEXT),
    "name": "John Smith",
    "current_role": "Software Engineer",
    "document_type": "cv",
}


def _no_fitz():
    """Patch the fitz module away so the classifier uses the latin-1 text fallback."""
    return patch.dict("sys.modules", {"fitz": None})


@pytest.fixture(scope="module")
def client():
    from src.api.app import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the in-memory rate limiter before each test so counters never accumulate."""
    from src.api.rate_limit import limiter
    limiter.reset()
    yield


class TestUploadDocumentIntelligence:

    # ── Case 1 ────────────────────────────────────────────────────────────────

    def test_case1_valid_cv_pdf_returns_preview_ready(self, client):
        """A CV PDF must still return status=preview_ready — pipeline unchanged."""
        with (
            _no_fitz(),
            patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
        ):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("john_smith_cv.pdf", io.BytesIO(_pdf(_CV_TEXT)), "application/pdf")},
            )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True, f"Expected ok=True: {body}"
        assert body["status"] == "preview_ready", (
            f"Valid CV must return preview_ready, got: {body.get('status')!r}"
        )
        assert "preview" in body, "preview key must be present for CV upload"
        assert body["document_type"] == "cv"

    def test_case1_preview_contains_extracted_name(self, client):
        """CV preview must include the name extracted by parse_cv."""
        with (
            _no_fitz(),
            patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
        ):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("cv.pdf", io.BytesIO(_pdf(_CV_TEXT)), "application/pdf")},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["preview"]["name"] == "John Smith"

    # ── Case 2 ────────────────────────────────────────────────────────────────

    def test_case2_contract_pdf_returns_classified(self, client):
        """A contract PDF must return status=classified — not enter the CV pipeline."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("employment_contract.pdf", io.BytesIO(_pdf(_CONTRACT_TEXT)), "application/pdf")},
            )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True, f"Expected ok=True: {body}"
        assert body["status"] == "classified", (
            f"Contract PDF must return classified, got: {body.get('status')!r}"
        )
        assert body["document_type"] == "contract", (
            f"Expected document_type=contract, got: {body.get('document_type')!r}"
        )

    def test_case2_classified_includes_confidence(self, client):
        """classified response must include confidence score > 0."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("contract.pdf", io.BytesIO(_pdf(_CONTRACT_TEXT)), "application/pdf")},
            )
        body = r.json()
        assert "confidence" in body, "confidence key must be present"
        assert body["confidence"] > 0, "confidence must be > 0 for a classified document"

    def test_case2_classified_includes_suggested_actions(self, client):
        """classified response must include at least one suggested action."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("contract.pdf", io.BytesIO(_pdf(_CONTRACT_TEXT)), "application/pdf")},
            )
        body = r.json()
        assert "suggested_actions" in body
        assert len(body["suggested_actions"]) > 0
        labels = [a["label"] for a in body["suggested_actions"]]
        assert any("Summarize" in lbl or "dates" in lbl or "risks" in lbl for lbl in labels), (
            f"Expected contract-relevant actions, got: {labels}"
        )

    # ── Case 3 ────────────────────────────────────────────────────────────────

    def test_case3_non_cv_response_has_no_preview_key(self, client):
        """Non-CV classified response must not contain a CV profile preview."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("contract.pdf", io.BytesIO(_pdf(_CONTRACT_TEXT)), "application/pdf")},
            )
        body = r.json()
        assert "preview" not in body, (
            "CV preview must not appear in a non-CV classified response"
        )

    def test_case3_non_cv_message_does_not_treat_file_as_cv(self, client):
        """The classified message must not say 'your resume', 'your CV', etc."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("contract.pdf", io.BytesIO(_pdf(_CONTRACT_TEXT)), "application/pdf")},
            )
        body = r.json()
        msg = (body.get("message") or "").lower()
        assert "your resume" not in msg, f"Message incorrectly references 'your resume': {msg}"
        assert "your cv" not in msg, f"Message incorrectly references 'your CV': {msg}"
        assert "save to profile" not in msg, f"Message suggests CV save: {msg}"

    def test_case3_non_cv_actions_do_not_include_save_to_profile(self, client):
        """Contract actions must not include 'save to profile' (a CV-only action)."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("contract.pdf", io.BytesIO(_pdf(_CONTRACT_TEXT)), "application/pdf")},
            )
        body = r.json()
        action_labels = [a.get("label", "").lower() for a in body.get("suggested_actions", [])]
        assert not any("save to profile" in lbl for lbl in action_labels), (
            f"Non-CV must not offer 'save to profile': {action_labels}"
        )

    def test_case3_display_label_is_contract_not_cv(self, client):
        """display_label must say 'Employment Contract', not 'Resume / CV'."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("contract.pdf", io.BytesIO(_pdf(_CONTRACT_TEXT)), "application/pdf")},
            )
        body = r.json()
        assert body.get("display_label") != "Resume / CV", (
            f"Non-CV display_label must not be 'Resume / CV', got: {body.get('display_label')}"
        )

    # ── Case 4 ────────────────────────────────────────────────────────────────

    def test_case4_identity_document_returns_rejected(self, client):
        """Passport/identity PDF must be hard-rejected — ok=False, status=rejected."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("passport.pdf", io.BytesIO(_pdf(_IDENTITY_TEXT)), "application/pdf")},
            )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False, (
            f"Identity document must return ok=False, got: {body}"
        )
        assert body["status"] == "rejected", (
            f"Identity document must return status=rejected, got: {body.get('status')!r}"
        )
        assert body.get("document_type") == "identity_document", (
            f"Expected document_type=identity_document, got: {body.get('document_type')!r}"
        )

    def test_case4_identity_response_contains_no_parsed_content(self, client):
        """Rejected identity document must not leak any parsed content."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("passport.pdf", io.BytesIO(_pdf(_IDENTITY_TEXT)), "application/pdf")},
            )
        body = r.json()
        assert "preview" not in body, "Identity response must not contain a preview"
        assert "parsed" not in body, "Identity response must not contain parsed content"
        assert "suggested_actions" not in body, "Identity response must not offer actions"

    def test_case4_identity_rejection_message_explains_reason(self, client):
        """Rejection message must explain why and not suggest profile was updated."""
        with _no_fitz():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("passport.pdf", io.BytesIO(_pdf(_IDENTITY_TEXT)), "application/pdf")},
            )
        body = r.json()
        msg = (body.get("message") or "").lower()
        assert "security" in msg or "identity" in msg or "passport" in msg, (
            f"Rejection message must reference security or identity, got: {msg!r}"
        )
        assert "profile was not changed" in msg or "not saved" in msg, (
            f"Rejection message must confirm no profile change, got: {msg!r}"
        )

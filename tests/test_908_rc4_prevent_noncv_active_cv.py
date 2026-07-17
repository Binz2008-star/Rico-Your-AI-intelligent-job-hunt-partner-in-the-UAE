"""
tests/test_908_rc4_prevent_noncv_active_cv.py

#908 RC4: an invoice (or any non-CV document) must never become the user's
"Active CV". Two independent bugs made this possible:

1. `/upload-cv`'s CV-pipeline exclusion gate required BOTH a minimum absolute
   confidence (>= 0.18) AND that confidence exceed the "cv" score -- but the
   blended `confidence` value is a *scaled-down* version of the top raw score
   (penalised when a runner-up type is close), so it can fall below the gate
   even when the document's true top-scoring type (e.g. "invoice") clearly
   beat "cv" on raw score. A low-confidence invoice could slip into the CV
   extraction pipeline.
2. `/confirm-cv-profile` silently coerced any unrecognized `doc_type` to
   "cv" and unconditionally set `is_primary=True` -- so if a mis-routed
   preview was ever confirmed, it became the permanent "Active CV" in
   `user_documents` regardless of what the file actually was.

These tests exercise both routes directly (real FastAPI TestClient / real
DocumentClassifier) with no live DB or AI provider calls.
"""
from __future__ import annotations

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _guest_capability_owner_browser(monkeypatch):
    """This suite exercises upload/confirm/chat mechanics AS the owning guest
    browser. The #1070 ownership boundary (unproved claims over existing
    sessions are 403) is covered by tests/test_1070_guest_identity_binding.py;
    here every request is treated as the session's first/owning browser so the
    mechanics under test stay deterministic across test order and DB state."""
    monkeypatch.setattr("src.api.public_identity.guest_state_exists", lambda _uid: False)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.services.document_classifier import classify_document

_PUBLIC_UID = "public:web-rc4test12345"

# A minimal invoice text -- few signals, low absolute score, but "invoice" is
# still the argmax type (confirmed against the real classifier below).
_INVOICE_TEXT = (
    "Invoice Number: INV-2024-0091\n"
    "Bill To: Acme Trading LLC\n"
    "Total Amount Due: AED 4,250.00\n"
    "Payment Due: 30 days\n"
)

# A genuine application-rejection/confirmation-style screenshot transcript.
_APPLICATION_CONFIRMATION_TEXT = (
    "Thank you for applying to the Credit Relationship Manager role. "
    "Your application was sent to Mashreq Bank. Application reference: APP-88213."
)

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
    return b"%PDF-1.4\n" + text.encode("latin-1")


def _no_fitz():
    return patch.dict("sys.modules", {"fitz": None})


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


# ── Sanity: confirm the classifier fixtures behave as the tests assume ───────

class TestClassifierFixtureSanity:
    def test_invoice_text_classifies_as_invoice_with_low_confidence(self):
        """The exact vulnerability this PR closes: confidence < 0.18 but
        doc_type is still unambiguously "invoice", not "cv"."""
        r = classify_document(_INVOICE_TEXT.encode("utf-8"), "invoice.pdf")
        assert r.document_type == "invoice"
        assert r.confidence < 0.18
        assert r.confidence_scores.get("cv", 0.0) == 0.0

    def test_application_confirmation_text_classifies_correctly(self):
        r = classify_document(_APPLICATION_CONFIRMATION_TEXT.encode("utf-8"), "confirmation.txt")
        assert r.document_type == "application_confirmation"


# ── /upload-cv: known non-CV types must never enter the CV pipeline ──────────

class TestUploadCvPipelineEligibility:
    def test_low_confidence_invoice_does_not_enter_cv_pipeline(self, client):
        """The exact #908 regression: a low-confidence invoice must be
        excluded by TYPE, not by the (unreliable) blended confidence score."""
        parse_mock = MagicMock(return_value=_CV_PARSE_RESULT)
        with _no_fitz(), patch("src.services.chat_service.parse_cv", parse_mock):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("invoice.pdf", io.BytesIO(_pdf(_INVOICE_TEXT)), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "classified", body
        assert body["document_type"] == "invoice", body
        assert "preview" not in body, "an invoice must never produce a CV preview"
        parse_mock.assert_not_called()

    def test_application_confirmation_does_not_enter_cv_pipeline(self, client):
        parse_mock = MagicMock(return_value=_CV_PARSE_RESULT)
        with _no_fitz(), patch("src.services.chat_service.parse_cv", parse_mock):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={
                    "file": (
                        "confirmation.pdf",
                        io.BytesIO(_pdf(_APPLICATION_CONFIRMATION_TEXT)),
                        "application/pdf",
                    )
                },
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["document_type"] == "application_confirmation", body
        assert "preview" not in body
        parse_mock.assert_not_called()

    def test_identity_document_still_hard_blocked(self, client):
        """Regression guard for the pre-existing identity_document hard block
        (untouched by this fix, must stay correct)."""
        identity_text = (
            "Passport Number: A1234567\nPlace of Birth: Dubai\n"
            "Machine Readable Zone\nIssuing Authority: UAE\n"
        )
        parse_mock = MagicMock(return_value=_CV_PARSE_RESULT)
        with _no_fitz(), patch("src.services.chat_service.parse_cv", parse_mock):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("passport.pdf", io.BytesIO(_pdf(identity_text)), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "rejected"
        parse_mock.assert_not_called()

    def test_real_cv_pdf_still_preview_ready(self, client):
        """Regression: a real CV text must still enter the CV pipeline."""
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
        assert body["document_type"] == "cv"
        parse_mock.assert_called_once()


# ── /confirm-cv-profile: non-CV doc_type must never become the Active CV ────

def _make_fake_ricodb(get_or_create_mock, *, legacy_save_mock=None):
    """Fake RicoDB exposing ONLY the canonical get_or_create_user_document
    path (#963/#960). `legacy_save_mock` (unused by confirm-cv-profile since
    #963) is still exposed so a regression back to the legacy path is
    provable by asserting it was never called, not just by its absence."""
    class _FakeRicoDB:
        available = True

        def __init__(self, *args, **kwargs):
            pass

        def get_or_create_user_document(self, **kwargs):
            result = get_or_create_mock(**kwargs)
            if result is not None:
                return result
            return {
                "id": "fake-doc-id",
                "filename": kwargs.get("filename"),
                "doc_type": kwargs.get("doc_type"),
                "is_primary": kwargs.get("is_primary", False),
                "inserted": True,
            }

        def save_user_document(self, **kwargs):
            if legacy_save_mock is not None:
                return legacy_save_mock(**kwargs)
            raise AssertionError(
                "save_user_document (legacy) must never be called by "
                "confirm-cv-profile after #963 -- use get_or_create_user_document"
            )

    return _FakeRicoDB


def _confirm_payload(filename="upload.pdf", doc_type="cv", upload_id="artifact-1"):
    payload = {
        "preview": {
            "name": "Test User",
            "current_role": "HSE Manager",
            "experience_years": 5,
            "skills_detected": ["hse"],
            "target_roles": ["HSE Manager"],
            "certifications": [],
            "languages": [],
        },
        "filename": filename,
        "doc_type": doc_type,
    }
    if upload_id is not None:
        payload["upload_id"] = upload_id
    return payload


def _artifact_for(*, filename, doc_type, content_hash="deadbeef" * 4, file_size=2048):
    """A complete, trustworthy artifact matching the given filename/doc_type --
    the doc_type here is the SERVER-DERIVED value (set by upload-cv's
    classifier at upload time), which is what #963's strict-reject confirm
    now persists from -- payload.doc_type (client-echoed) is never used."""
    return {
        "filename": filename, "doc_type": doc_type,
        "content_hash": content_hash, "file_size": file_size, "cv_text": "",
    }


class TestConfirmCvProfileDocTypeValidation:
    def _post_confirm(self, client, doc_type, filename="upload.pdf"):
        get_or_create_mock = MagicMock(return_value=None)
        with (
            patch("src.api.routers.rico_chat.upsert_profile"),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(True, [])),
            patch("src.repositories.onboarding_repo.set_onboarding_status"),
            patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
            patch("src.services.subscription_gating.record_profile_optimization_usage"),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value="alice@rico.ai"),
            patch(
                "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
                return_value=_artifact_for(filename=filename, doc_type=doc_type),
            ),
            patch("src.rico_db.RicoDB", _make_fake_ricodb(get_or_create_mock)),
        ):
            r = client.post(
                "/api/v1/rico/confirm-cv-profile?user_id=alice@rico.ai",
                json=_confirm_payload(filename=filename, doc_type=doc_type),
            )
        return r, get_or_create_mock

    def test_valid_cv_doc_type_happy_path_preserved(self, client):
        """Regression: a genuine CV confirm must still save doc_type='cv'
        with is_primary=True -- the existing happy path is unchanged."""
        r, get_or_create_mock = self._post_confirm(client, doc_type="cv")
        assert r.status_code == 200, r.text
        get_or_create_mock.assert_called_once()
        kwargs = get_or_create_mock.call_args.kwargs
        assert kwargs["doc_type"] == "cv"
        assert kwargs["is_primary"] is True

    def test_unrecognized_doc_type_not_coerced_to_cv(self, client):
        """The exact #908 RC4 bug: confirming a mis-routed invoice must not
        silently write doc_type='cv' / is_primary=True."""
        r, get_or_create_mock = self._post_confirm(client, doc_type="invoice", filename="Invoice-W7JSBCPT-0003.pdf")
        assert r.status_code == 200, r.text
        get_or_create_mock.assert_called_once()
        kwargs = get_or_create_mock.call_args.kwargs
        assert kwargs["doc_type"] != "cv"
        assert kwargs["is_primary"] is False

    def test_identity_document_doc_type_not_coerced_to_cv(self, client):
        r, get_or_create_mock = self._post_confirm(client, doc_type="identity_document")
        kwargs = get_or_create_mock.call_args.kwargs
        assert kwargs["doc_type"] != "cv"
        assert kwargs["is_primary"] is False

    def test_application_confirmation_doc_type_not_coerced_to_cv(self, client):
        r, get_or_create_mock = self._post_confirm(client, doc_type="application_confirmation")
        kwargs = get_or_create_mock.call_args.kwargs
        assert kwargs["doc_type"] != "cv"
        assert kwargs["is_primary"] is False

    def test_cover_letter_doc_type_saved_but_never_primary(self, client):
        """cover_letter is a recognized, confirmable type but is not
        CV-family (per document_resolver._CV_DOC_TYPES) -- it must be saved
        under its own type and never marked as the Active CV."""
        r, get_or_create_mock = self._post_confirm(client, doc_type="cover_letter")
        kwargs = get_or_create_mock.call_args.kwargs
        assert kwargs["doc_type"] == "cover_letter"
        assert kwargs["is_primary"] is False

    def test_legacy_save_user_document_never_called(self, client):
        """#963 architecture requirement: confirm-cv-profile must never use
        the legacy, non-hash-aware save_user_document for confirmed CV
        persistence -- only the canonical get_or_create_user_document.

        Asserted directly against a real MagicMock (not via a raise-if-called
        fake) because the doc-save block runs inside a broad try/except that
        would otherwise swallow the very AssertionError meant to catch a
        regression back to the legacy path.
        """
        legacy_mock = MagicMock()
        get_or_create_mock = MagicMock(return_value=None)
        with (
            patch("src.api.routers.rico_chat.upsert_profile"),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(True, [])),
            patch("src.repositories.onboarding_repo.set_onboarding_status"),
            patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
            patch("src.services.subscription_gating.record_profile_optimization_usage"),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value="alice@rico.ai"),
            patch(
                "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
                return_value=_artifact_for(filename="upload.pdf", doc_type="cv"),
            ),
            patch("src.rico_db.RicoDB", _make_fake_ricodb(get_or_create_mock, legacy_save_mock=legacy_mock)),
        ):
            r = client.post(
                "/api/v1/rico/confirm-cv-profile?user_id=alice@rico.ai",
                json=_confirm_payload(doc_type="cv"),
            )
        assert r.status_code == 200, r.text
        get_or_create_mock.assert_called_once()
        legacy_mock.assert_not_called()

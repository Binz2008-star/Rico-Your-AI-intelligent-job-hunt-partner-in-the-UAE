"""
BUG-19 — Job-confirmation screenshots are application EVIDENCE.

Before this fix:
1. A job-application confirmation screenshot transcript matched no classifier
   signal bank → `unknown` → the UI rendered "Unrecognized Document" with
   generic Summarize/Extract dead-ends.
2. "Track this application" / "I applied" then resolved the job from recent
   chat context — `candidates[0]` was blindly the first recent-search job, so
   the WRONG job got tracked.

All DB/AI access is mocked — no live Neon / providers.
"""
from __future__ import annotations

from unittest.mock import patch

from src.rico_chat_api import RicoChatAPI
from src.services.document_classifier import classify_document


LINKEDIN_STYLE = (
    "Your application was sent to Yalla Pizza\n"
    "Regional General Manager\n"
    "Ajman, United Arab Emirates\n"
    "Application submitted successfully. We have received your application "
    "and will review it shortly. Application ID: 88213"
)

PORTAL_STYLE = (
    "Thank you for applying!\n"
    "Your application for the Operations Manager position at Emaar Properties "
    "has been submitted. Your application is under review.\n"
    "Application reference: EMR-2231"
)


# ── Classifier ────────────────────────────────────────────────────────────────

def test_confirmation_text_classified_as_application_confirmation():
    res = classify_document(PORTAL_STYLE.encode("utf-8"), "confirmation.txt")
    assert res.document_type == "application_confirmation"
    assert res.display_label == "Application Confirmation"
    assert res.confidence >= 0.5


def test_confirmation_offers_track_action_not_generic_deadends():
    res = classify_document(LINKEDIN_STYLE.encode("utf-8"), "image-text.txt")
    assert res.document_type == "application_confirmation"
    labels = [a["label"] for a in res.suggested_actions]
    assert "Track this application" in labels


def test_job_description_still_classified_as_job_description():
    jd = (
        "Job Title: HSE Manager\n"
        "Key responsibilities: lead the HSE function. Requirements: 10 years "
        "experience. We are looking for an ideal candidate. Apply now. "
        "Salary: competitive. About the company: a leading UAE contractor."
    )
    res = classify_document(jd.encode("utf-8"), "jd.txt")
    assert res.document_type == "job_description"


def test_cv_text_still_classified_as_cv():
    cv = (
        "Professional Summary\nWork Experience\nEducation\nSkills\n"
        "Nationality: Jordanian. Visa status: residence. "
        "References available upon request. linkedin.com/in/someone "
        "Curriculum Vitae. Key achievements: led operations."
    )
    res = classify_document(cv.encode("utf-8"), "cv.txt")
    assert res.document_type == "cv"


def test_single_incidental_signal_does_not_hijack():
    """One weak hit ('your application to') must not force the override."""
    text = (
        "Dear Hiring Manager, I am writing to apply for the role. "
        "I am confident my experience fits. Please find attached my resume. "
        "Yours sincerely. Thank you for considering your application to us."
    )
    res = classify_document(text.encode("utf-8"), "letter.txt")
    assert res.document_type != "application_confirmation"


# ── Attachment purpose mapping ────────────────────────────────────────────────

def test_purpose_maps_to_application_evidence():
    from src.services.attachment_analysis_factory import (
        build_attachment_analysis,
        purpose_for_document_type,
    )
    from src.schemas.chat import RicoAttachmentPurpose

    assert (
        purpose_for_document_type("application_confirmation")
        == RicoAttachmentPurpose.application_evidence
    )
    res = classify_document(PORTAL_STYLE.encode("utf-8"), "confirmation.txt")
    analysis = build_attachment_analysis(res, "confirmation.txt")
    assert analysis.purpose == RicoAttachmentPurpose.application_evidence
    # No "not sure what this document is" warning for a recognized confirmation.
    assert all("not sure" not in w for w in analysis.warnings)


# ── Meta extraction ───────────────────────────────────────────────────────────

def test_extract_meta_title_and_company_portal_style():
    title, company = RicoChatAPI._extract_application_meta_from_text(PORTAL_STYLE)
    assert title == "Operations Manager"
    assert company == "Emaar Properties"


def test_extract_meta_company_only_linkedin_style():
    title, company = RicoChatAPI._extract_application_meta_from_text(
        "Your application was sent to Yalla Pizza"
    )
    assert company == "Yalla Pizza"


def test_extract_meta_labelled_fields():
    text = (
        "Application received.\nPosition: QHSE Manager\nCompany: Acme Contracting\n"
        "Thank you for applying."
    )
    title, company = RicoChatAPI._extract_application_meta_from_text(text)
    assert title == "QHSE Manager"
    assert company == "Acme Contracting"


def test_extract_meta_strips_confirmation_verbiage_from_company():
    title, company = RicoChatAPI._extract_application_meta_from_text(
        "Your application for Operations Manager at Emaar Properties has been submitted"
    )
    assert company == "Emaar Properties"


# ── Wrong-job fallback fix (_resolve_application_status_job) ─────────────────

def _api():
    return RicoChatAPI(persist=False)


def _ctx_with(doc: dict | None, matches: list | None = None) -> dict:
    ctx: dict = {}
    if matches is not None:
        ctx["recent_search_matches"] = matches
    if doc is not None:
        ctx["last_uploaded_document"] = doc
    return ctx


WRONG_JOB = {"title": "Sales Executive", "company": "WrongCo"}


def test_resolver_prefers_uploaded_confirmation_over_recent_search():
    api = _api()
    doc = {"document_type": "application_confirmation", "extracted_text": PORTAL_STYLE}
    with patch.object(api, "_get_recent_context", return_value=_ctx_with(doc, [WRONG_JOB])):
        job = api._resolve_application_status_job("u@test", "I applied, track it")
    assert job["title"] == "Operations Manager"
    assert job["company"] == "Emaar Properties"


def test_resolver_asks_instead_of_guessing_when_meta_unreadable():
    """Confirmation doc present but title/company unreadable → None (ask), never WrongCo."""
    api = _api()
    doc = {"document_type": "application_confirmation",
           "extracted_text": "Application submitted. We have received your application."}
    with patch.object(api, "_get_recent_context", return_value=_ctx_with(doc, [WRONG_JOB])):
        job = api._resolve_application_status_job("u@test", "I applied, track it")
    assert job is None


def test_resolver_explicit_message_match_still_wins():
    """Naming a recent job in the message still resolves to that job."""
    api = _api()
    doc = {"document_type": "application_confirmation", "extracted_text": PORTAL_STYLE}
    with patch.object(api, "_get_recent_context", return_value=_ctx_with(doc, [WRONG_JOB])):
        job = api._resolve_application_status_job("u@test", "I applied to WrongCo yesterday")
    assert job["company"] == "WrongCo"


def test_resolver_unchanged_without_confirmation_doc():
    """No uploaded confirmation → legacy behavior (first recent candidate)."""
    api = _api()
    jd_doc = {"document_type": "job_description", "extracted_text": "Job Title: X"}
    with patch.object(api, "_get_recent_context", return_value=_ctx_with(jd_doc, [WRONG_JOB])):
        job = api._resolve_application_status_job("u@test", "I applied")
    assert job["company"] == "WrongCo"


# ── "Track this application" action ──────────────────────────────────────────

TRACK_MSG = "Track this application in my pipeline."


def test_track_action_persists_job_from_transcript():
    api = _api()
    doc = {"document_type": "application_confirmation", "extracted_text": PORTAL_STYLE}
    persisted = {}

    def _fake_persist(*, user_id, job):
        persisted.update(job)
        return True, "job-key-1"

    with (
        patch.object(api, "_get_recent_context", return_value=_ctx_with(doc)),
        patch.object(api, "_persist_confirmed_application_status", side_effect=_fake_persist),
        patch.object(api, "_store_application_status_context"),
    ):
        res = api._handle_uploaded_document_followup("u@test", TRACK_MSG, None)

    assert res["type"] == "application_status_update"
    assert res["job_title"] == "Operations Manager"
    assert res["job_company"] == "Emaar Properties"
    assert persisted["title"] == "Operations Manager"
    assert persisted["company"] == "Emaar Properties"


def test_track_action_public_user_requires_sign_in():
    api = _api()
    doc = {"document_type": "application_confirmation", "extracted_text": PORTAL_STYLE}
    with patch.object(api, "_get_recent_context", return_value=_ctx_with(doc)):
        res = api._handle_uploaded_document_followup("public:web-abc", TRACK_MSG, None)
    assert res["next_action"] == "sign_in_required"


def test_track_action_asks_for_details_when_meta_unreadable():
    api = _api()
    doc = {"document_type": "application_confirmation",
           "extracted_text": "Application submitted. Application ID: 123"}
    with patch.object(api, "_get_recent_context", return_value=_ctx_with(doc)):
        res = api._handle_uploaded_document_followup("u@test", TRACK_MSG, None)
    assert res["type"] == "clarification"
    assert res["next_action"] == "provide_manual_application_details"


def test_track_message_without_confirmation_doc_falls_through():
    """'Track this application' with no confirmation transcript → None (normal routing)."""
    api = _api()
    jd_doc = {"document_type": "job_description", "extracted_text": "Job Title: X at Acme"}
    with (
        patch.object(api, "_get_recent_context", return_value=_ctx_with(jd_doc)),
        patch("src.repositories.uploaded_document_repo.get_last_uploaded_document",
              return_value=None),
    ):
        res = api._handle_uploaded_document_followup("u@test", TRACK_MSG, None)
    assert res is None


def test_save_as_target_job_still_works_for_job_description():
    """Non-regression: the Finding-3 save path for job descriptions is untouched."""
    api = _api()
    jd_doc = {"document_type": "job_description",
              "extracted_text": "Job Title: HSE Manager\nCompany: Acme Contracting"}
    saved = {}

    def _fake_save(user_id, doc, text, is_ar):
        saved["called"] = True
        return {"type": "save_job", "message": "saved"}

    with (
        patch.object(api, "_get_recent_context", return_value=_ctx_with(jd_doc)),
        patch.object(api, "_save_uploaded_job_to_pipeline", side_effect=_fake_save),
    ):
        res = api._handle_uploaded_document_followup(
            "u@test", "Save this as a target job in my pipeline.", None
        )
    assert saved.get("called") is True
    assert res["type"] == "save_job"

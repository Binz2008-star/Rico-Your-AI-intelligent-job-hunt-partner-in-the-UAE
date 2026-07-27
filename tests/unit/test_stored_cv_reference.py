"""
tests/unit/test_stored_cv_reference.py

fix: referencing a previously uploaded CV by filename in chat dead-ended in
the canned "Your CV is already parsed and your profile is set up." reply.

Covered here:
- A message naming a STORED document gets a real, document-grounded
  cv_analysis reply (the live regression: "not my profile but the previous
  uploaded cv of Roudain Mosleh 2026.pdf").
- A message naming a file that is NOT stored gets an honest
  cv_reference_not_found reply with recovery guidance (My Files / free a
  slot), because a quota-rejected upload is never saved server-side.
- An analysis ask without a filename analyses the active CV.
- Messages with neither a filename nor an analysis ask keep the existing
  behaviour (handler returns None; canned reply preserved).

D3 — READ FAILURE != VERIFIED ABSENCE
-------------------------------------
The same module answers "what CV does this user have?" from two independent
reads, and both used to collapse a failed read into a confident absence:

  1. The CV-context consumer path. ``resolve_cv_context`` already reports
     ``availability_reason="store_unavailable"`` when the grounding read
     fails, but the consumer only ever read ``.state`` / ``.has_cv`` /
     ``.has_content`` — so an outage rendered as "you haven't uploaded one"
     (English) or as ``next_action="upload_cv"`` (Arabic).
  2. ``_handle_stored_cv_reference``. A document-store exception became
     ``docs=[]``, which is indistinguishable from a successful empty read, so
     the user was told there were "no saved CVs on your account".

Both send a user to re-upload a file the product already holds. The classes
below assert the one invariant across both entry points, in English and in
Arabic, and assert that genuine absence and genuine unreadable-content
behaviour are unchanged.

Mocks only — no real DB, no AI providers.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


# ── fixtures ─────────────────────────────────────────────────────────────────

STORED_DOCS = [
    {
        "id": "doc-1",
        "filename": "Roudain Mosleh 2026.pdf",
        "original_filename": "Roudain Mosleh 2026.pdf",
        "label": None,
        "doc_type": "cv",
        "is_primary": False,
        "skills_json": ["iso 14001", "compliance", "environmental management"],
        "years_experience": 8.0,
        "current_role": "Founder & General Manager",
    },
    {
        "id": "doc-2",
        "filename": "banking_cv.pdf",
        "original_filename": "banking_cv.pdf",
        "label": "Banking CV",
        "doc_type": "cv",
        "is_primary": True,
        "skills_json": ["compliance", "excel"],
        "years_experience": 8.0,
        "current_role": "Compliance Officer",
    },
]

PARSED_PROFILE = {
    "cv_status": "parsed",
    "cv_filename": "banking_cv.pdf",
    "skills": ["compliance", "excel"],
    "years_experience": 8,
    "target_roles": ["Compliance Manager"],
    "preferred_cities": ["Dubai"],
}


def _api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    return api


def _handler_result(message: str, docs=None, profile=None):
    api = _api()
    mock_db = MagicMock()
    mock_db.available = True
    mock_db.list_user_documents.return_value = list(docs if docs is not None else STORED_DOCS)
    with (
        patch("src.rico_db.RicoDB", return_value=mock_db),
        patch.object(api, "_append_chat", MagicMock()),
    ):
        return api._handle_stored_cv_reference(
            "u@test.com", profile if profile is not None else dict(PARSED_PROFILE), message
        )


# ── 1. The live regression: stored file referenced by name ───────────────────

def test_stored_cv_referenced_by_name_gets_document_analysis():
    result = _handler_result(
        "not my profile but the previous uploaded cv of Roudain Mosleh 2026.pdf"
    )
    assert result is not None
    assert result["type"] == "cv_analysis"
    assert result["filename"] == "Roudain Mosleh 2026.pdf"
    assert result["is_active_cv"] is False
    msg = result["message"]
    assert "Roudain Mosleh 2026.pdf" in msg
    assert "already parsed" not in msg.lower()
    # Grounded in the document row's stored extraction, not the profile
    assert "iso 14001" in msg
    assert "Founder & General Manager" in msg


def test_stored_active_cv_referenced_by_name_uses_parsed_profile():
    result = _handler_result("analyze banking_cv.pdf please")
    assert result is not None
    assert result["type"] == "cv_analysis"
    assert result["is_active_cv"] is True
    assert "active CV" in result["message"]


# ── 2. Referenced file not stored: honest recovery guidance ──────────────────

def test_unknown_file_reference_gets_not_found_with_recovery_steps():
    result = _handler_result("please analyze Unknown Person 2030.pdf")
    assert result is not None
    assert result["type"] == "cv_reference_not_found"
    msg = result["message"]
    assert "Unknown Person 2030.pdf" in msg
    # Lists what IS stored, and explains the recovery path
    assert "Roudain Mosleh 2026.pdf" in msg
    assert "My Files" in msg
    assert "never saved" in msg


def test_unknown_file_with_no_stored_docs_says_so():
    result = _handler_result("analyze My New CV.pdf", docs=[], profile={"cv_status": "parsed"})
    assert result is not None
    assert result["type"] == "cv_reference_not_found"
    assert "no saved CVs" in result["message"]


# ── 3. Analysis ask without a filename → active CV ───────────────────────────

def test_analysis_ask_without_filename_analyses_active_cv():
    result = _handler_result("I uploaded my cv — can you review it?")
    assert result is not None
    assert result["type"] == "cv_analysis"
    assert result["filename"] == "banking_cv.pdf"
    assert result["is_active_cv"] is True


# ── 4. Neither filename nor analysis ask → None (existing routing preserved) ─

def test_plain_upload_statement_returns_none():
    assert _handler_result("i have uploaded my cv") is None


def test_empty_message_returns_none():
    assert _handler_result("") is None


# ── 5. Display-name extraction trims the greedy CV_FILE_RE capture ───────────

def test_referenced_filename_display_strips_leading_words():
    display = RicoChatAPI._referenced_filename_display(
        "not my profile but the previous uploaded cv of Roudain Mosleh 2026.pdf"
    )
    assert display == "Roudain Mosleh 2026.pdf"


def test_referenced_filename_display_none_without_file_token():
    assert RicoChatAPI._referenced_filename_display("review my cv please") is None


# ── 6. Arabic message referencing a stored file ──────────────────────────────

def test_arabic_reference_gets_arabic_analysis():
    result = _handler_result("حلل السيرة الذاتية Roudain Mosleh 2026.pdf")
    assert result is not None
    assert result["type"] == "cv_analysis"
    assert result["filename"] == "Roudain Mosleh 2026.pdf"
    assert "المهارات" in result["message"]


# ── 7. Document read FAILURE is never reported as verified absence ───────────
#
# The handler must still contain the exception — a chat turn is not allowed to
# die because the document store blinked — but containment is not permission to
# answer as if the read had succeeded and returned nothing.

def _read_failure_result(message: str, profile=None):
    """Run the handler with the document store raising on read."""
    api = _api()
    mock_db = MagicMock()
    mock_db.available = True
    mock_db.list_user_documents.side_effect = RuntimeError("db down")
    with (
        patch("src.rico_db.RicoDB", return_value=mock_db),
        patch.object(api, "_append_chat", MagicMock()),
    ):
        return api._handle_stored_cv_reference(
            "u@test.com", profile if profile is not None else dict(PARSED_PROFILE), message
        )


def test_document_read_failure_is_contained_not_crashed():
    """Containment is preserved: an infrastructure fault never raises here."""
    result = _read_failure_result("analyze Roudain Mosleh 2026.pdf")
    assert result is not None
    assert isinstance(result.get("message"), str) and result["message"].strip()


def test_document_read_failure_is_not_a_successful_empty_read_english():
    result = _read_failure_result("analyze Roudain Mosleh 2026.pdf")
    # Not "cv_reference_not_found" — that is the branch a SUCCESSFUL empty read
    # produces, and no read succeeded here.
    assert result["type"] == "cv_state_unverified"
    msg = result["message"]
    assert "no saved CVs" not in msg
    assert "couldn't find" not in msg
    # No upload / re-upload instruction, and no upload action.
    assert "Upload CV" not in msg
    assert "upload the file again" not in msg
    assert result.get("next_action") != "upload_cv"
    # Truthful about the inability to verify, non-blaming about the cause.
    assert "couldn't verify your saved CV" in msg
    assert "won't ask you to upload it again" in msg
    assert "database" not in msg.lower()


def test_document_read_failure_is_not_a_successful_empty_read_arabic():
    result = _read_failure_result("حلل السيرة الذاتية Roudain Mosleh 2026.pdf")
    assert result["type"] == "cv_state_unverified"
    msg = result["message"]
    assert "لم أجد" not in msg
    assert "لا توجد سير ذاتية محفوظة" not in msg
    # No upload-button instruction, no upload action.
    assert "زر **رفع السيرة الذاتية**" not in msg
    assert result.get("next_action") != "upload_cv"
    assert "تعذّر عليّ التحقق من سيرتك المحفوظة" in msg
    assert "لن أطلب منك رفعها مجددًا" in msg


def test_document_read_failure_without_filename_token_also_unverified():
    """An analysis ask with no filename must not silently analyse nothing."""
    result = _read_failure_result("can you review my uploaded cv?")
    assert result is not None
    assert result["type"] == "cv_state_unverified"


# ── 8. A SUCCESSFUL empty read keeps its existing, truthful behaviour ────────

def test_successful_empty_read_still_reports_genuine_absence():
    result = _handler_result("analyze My New CV.pdf", docs=[], profile={"cv_status": "parsed"})
    assert result is not None
    assert result["type"] == "cv_reference_not_found"
    msg = result["message"]
    assert "no saved CVs" in msg
    # Real absence keeps real recovery guidance — it is not softened into the
    # unverifiable wording.
    assert "My Files" in msg
    assert "couldn't verify your saved CV" not in msg


# ── 9. CV-context consumer path: a grounding-read outage is not "no CV" ─────
#
# These drive the real resolver (no stubbed CVContext) by failing the grounding
# read the way production fails it, so the `store_unavailable` reason is derived
# rather than asserted into existence.

NO_CV_PROFILE = {
    "cv_status": None,
    "cv_filename": None,
    "skills": [],
    "target_roles": ["Compliance Manager"],
    "preferred_cities": ["Dubai"],
}

METADATA_ONLY_PROFILE = {
    "cv_status": "uploaded",
    "cv_filename": "banking_cv.pdf",
    "skills": [],
    "target_roles": ["Compliance Manager"],
    "preferred_cities": ["Dubai"],
}


def _grounding_row(**fields):
    """A grounding row the resolver can read. Absent fields are genuinely absent.

    ``get_cv_grounding`` returning ``None`` is the resolver's signal for a FAILED
    read, not for an empty profile — so a real empty account must be modelled as
    a row whose CV columns are all None.
    """
    row = {
        "cv_structured": None,
        "cv_text": None,
        "cv_filename": None,
        "cv_status": None,
        "years_experience": None,
    }
    row.update(fields)
    return MagicMock(**row)


def _chat_turn(message: str, profile: dict, *, grounding_fails: bool):
    """One authenticated chat turn, with the CV grounding read up or down."""
    api = RicoChatAPI()
    if grounding_fails:
        grounding = MagicMock(side_effect=RuntimeError("grounding store down"))
        doc_lookup = MagicMock(side_effect=RuntimeError("document store down"))
        identity_lookup = MagicMock(side_effect=RuntimeError("document store down"))
    else:
        grounding = MagicMock(return_value=_grounding_row())
        doc_lookup = MagicMock(return_value=None)
        identity_lookup = MagicMock(return_value=False)
    with (
        patch("src.rico_chat_api.get_profile", return_value=dict(profile)),
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch(
            "src.rico_chat_api.upsert_profile",
            side_effect=lambda uid, upd: {**profile, **upd},
        ),
        patch("src.repositories.profile_repo.get_cv_grounding", grounding),
        patch("src.services.document_resolver.resolve_user_cv", doc_lookup),
        patch("src.services.document_resolver.has_only_identity_documents", identity_lookup),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_append_chat", MagicMock()),
    ):
        return api._handle_active_user("u@test.com", message)


def test_store_outage_never_claims_the_user_has_no_cv_english():
    result = _chat_turn("review my cv", NO_CV_PROFILE, grounding_fails=True)
    msg = result.get("message") or ""
    assert "haven't uploaded one" not in msg
    assert "you haven't uploaded" not in msg
    assert "Upload your CV" not in msg
    assert "Upload CV" not in msg
    assert result.get("next_action") != "upload_cv"
    assert result.get("type") == "cv_state_unverified"
    assert "couldn't verify your saved CV" in msg
    assert "won't ask you to upload it again" in msg


def test_store_outage_never_asks_for_upload_arabic():
    result = _chat_turn("حلل سيرتي الذاتية", NO_CV_PROFILE, grounding_fails=True)
    msg = result.get("message") or ""
    assert result.get("next_action") != "upload_cv"
    assert "زر **رفع السيرة الذاتية**" not in msg
    assert not any(
        opt.get("action") == "upload_cv" for opt in (result.get("options") or [])
    )
    assert result.get("type") == "cv_state_unverified"
    assert "تعذّر عليّ التحقق من سيرتك المحفوظة" in msg
    assert "لن أطلب منك رفعها مجددًا" in msg


def test_store_outage_with_cv_metadata_does_not_blame_the_document():
    """state=metadata_only + store_unavailable must not become "unreadable PDF".

    A failed grounding read on a profile that shows a filename resolves to
    metadata_only. The unreadable-content branch would then tell the user to
    re-upload a text-based PDF — blaming a document nobody managed to read.
    """
    result = _chat_turn("review my cv", METADATA_ONLY_PROFILE, grounding_fails=True)
    msg = result.get("message") or ""
    assert "Re-upload it" not in msg
    assert "scanned image" not in msg
    assert result.get("next_action") != "upload_cv"
    assert result.get("type") == "cv_state_unverified"
    assert "couldn't verify your saved CV" in msg


def test_genuine_absence_still_says_no_cv_uploaded():
    """availability_reason=no_cv_on_file is a fact, and keeps its wording."""
    result = _chat_turn("review my cv", NO_CV_PROFILE, grounding_fails=False)
    msg = result.get("message") or ""
    assert "haven't uploaded one" in msg
    assert "Upload your CV" in msg
    assert "couldn't verify your saved CV" not in msg


def test_unreadable_content_stays_a_content_problem_not_an_outage():
    """A verified metadata_only CV keeps the content wording, not outage wording."""
    api = RicoChatAPI()
    grounding = MagicMock(
        return_value=_grounding_row(cv_filename="banking_cv.pdf", cv_status="uploaded")
    )
    with (
        patch("src.rico_chat_api.get_profile", return_value=dict(METADATA_ONLY_PROFILE)),
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch(
            "src.rico_chat_api.upsert_profile",
            side_effect=lambda uid, upd: {**METADATA_ONLY_PROFILE, **upd},
        ),
        patch("src.repositories.profile_repo.get_cv_grounding", grounding),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_append_chat", MagicMock()),
        patch.object(api, "_handle_stored_cv_reference", return_value=None),
    ):
        result = api._handle_active_user("u@test.com", "what is wrong with my cv")
    msg = result.get("message") or ""
    assert "couldn't read its contents" in msg
    assert "banking_cv.pdf" in msg
    assert "couldn't verify your saved CV" not in msg
    assert result.get("type") != "cv_state_unverified"


# ── 10. End-to-end: routing reaches the handler, not the canned reply ────────

def test_e2e_stored_reference_never_gets_canned_already_parsed_reply():
    api = RicoChatAPI()
    mock_db = MagicMock()
    mock_db.available = True
    mock_db.list_user_documents.return_value = list(STORED_DOCS)
    profile = dict(PARSED_PROFILE)
    with (
        patch("src.rico_chat_api.get_profile", return_value=profile),
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch("src.rico_chat_api.upsert_profile", side_effect=lambda uid, upd: {**profile, **upd}),
        patch("src.rico_db.RicoDB", return_value=mock_db),
        patch.object(api, "_get_recent_context", return_value={}),
        patch.object(api, "_append_chat", MagicMock()),
    ):
        result = api._handle_active_user(
            "u@test.com",
            "not my profile but the previous uploaded cv of Roudain Mosleh 2026.pdf",
        )
    assert result.get("type") == "cv_analysis"
    assert "already parsed" not in (result.get("message") or "").lower()

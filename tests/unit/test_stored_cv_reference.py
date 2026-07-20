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


# ── 7. DB failure degrades to not-found guidance, never crashes ──────────────

def test_db_failure_degrades_gracefully():
    api = _api()
    mock_db = MagicMock()
    mock_db.available = True
    mock_db.list_user_documents.side_effect = RuntimeError("db down")
    with (
        patch("src.rico_db.RicoDB", return_value=mock_db),
        patch.object(api, "_append_chat", MagicMock()),
    ):
        result = api._handle_stored_cv_reference(
            "u@test.com", dict(PARSED_PROFILE), "analyze Roudain Mosleh 2026.pdf"
        )
    assert result is not None
    assert result["type"] == "cv_reference_not_found"


# ── 8. End-to-end: routing reaches the handler, not the canned reply ─────────

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

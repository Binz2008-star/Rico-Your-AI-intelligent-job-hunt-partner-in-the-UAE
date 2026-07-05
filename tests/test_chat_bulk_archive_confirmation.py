"""
tests/test_chat_bulk_archive_confirmation.py

PR A.1 — Fix the confirmed bulk-archive flow in Rico chat.

Source of truth (broken transcript):
    User:  CLEAR THEM LETS START FRESH
    Rico:  asks archive / delete / cancel
    User:  archive
    Rico:  (BUG) tells the user to go to /applications instead of archiving

Fix: when an authenticated user confirms "archive", Rico executes a reversible
bulk archive (status -> 'archived') for that user, and only claims a count after
the DB write succeeds. Delete stays UI-only (no permanent delete from chat),
cancel is a no-op.

Safety: no live DB — persistence is mocked (src.rico_db.RicoDB).
"""
from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

AUTH_UID = "user@example.com"
PUBLIC_UID = "public:web:anon-123"


def _api_with_pending():
    """RicoChatAPI with an active pending pipeline-reset, memory mocked."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    api.memory = MagicMock()
    pending = {"pending": True, "expires_at": int(time.time()) + 120}
    api.memory.get_context.side_effect = lambda uid, key: (
        pending if key == RicoChatAPI._PENDING_PIPELINE_RESET_KEY else None
    )
    return api


# 1. "CLEAR THEM LETS START FRESH" -> asks confirmation ----------------------

def test_clear_them_lets_start_fresh_asks_confirmation():
    from src.rico_chat_api import RicoChatAPI, _PIPELINE_RESET_RE

    # The exact broken-transcript phrase is detected as a reset request.
    assert _PIPELINE_RESET_RE.search("CLEAR THEM LETS START FRESH")

    api = RicoChatAPI()
    api.memory = MagicMock()
    api.memory.get_context.return_value = None
    with patch.object(api, "_append_chat"):
        result = api._handle_pipeline_reset(AUTH_UID, "CLEAR THEM LETS START FRESH")

    assert result["type"] == "pipeline_reset_confirm"
    assert result["next_action"] == "await_confirmation"
    # Offers archive as the recommended, reversible option.
    assert "archive" in result["message"].lower()


# 2. "archive" after pending -> archives active tracked applications ---------

def test_archive_executes_reversible_bulk_archive_for_authenticated_user():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls:
        mock_db_cls.return_value.archive_all_applications.return_value = 5
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    # Executed the bulk archive against the DB for this exact authenticated user.
    mock_db_cls.return_value.archive_all_applications.assert_called_once_with(AUTH_UID)
    assert result["type"] == "pipeline_reset_archived"
    # Completes in chat — does NOT punt the user to /applications as the only path.
    assert result.get("target_route") != "/applications"
    assert "/applications" not in result["message"] or "restore" in result["message"].lower()


# 3. Confirmation includes archived count ------------------------------------

def test_archive_confirmation_reports_the_count():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls:
        mock_db_cls.return_value.archive_all_applications.return_value = 7
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    assert result.get("archived_count") == 7
    assert "7" in result["message"]


# 4. DB failure -> no success claim, nothing changed -------------------------

def test_archive_db_failure_makes_no_success_claim():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls:
        mock_db_cls.return_value.archive_all_applications.side_effect = RuntimeError("db down")
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    assert result["type"] == "pipeline_reset_archive_failed"
    # No count / no success receipt.
    assert "archived_count" not in result
    low = result["message"].lower()
    assert "couldn't" in low or "could not" in low
    assert "nothing was changed" in low


# 5. "cancel" -> no mutation -------------------------------------------------

def test_cancel_performs_no_mutation():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls:
        result = api._handle_pending_pipeline_reset(AUTH_UID, "cancel")

    assert result["type"] == "pipeline_reset_cancelled"
    assert "nothing was changed" in result["message"].lower()
    # The DB is never touched on cancel.
    mock_db_cls.assert_not_called()


# 6. "delete" -> does NOT permanently delete from chat -----------------------

def test_delete_does_not_permanently_delete_from_chat():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls:
        result = api._handle_pending_pipeline_reset(AUTH_UID, "delete")

    # No permanent delete is executed from chat (UI-only / safer redirect).
    assert result["type"] == "pipeline_reset_delete_redirect"
    mock_db_cls.assert_not_called()


# 8. Public/anonymous session must not archive under a public id -------------

def test_public_session_does_not_archive_under_public_id():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls:
        result = api._handle_pending_pipeline_reset(PUBLIC_UID, "archive")

    assert result["type"] == "pipeline_reset_archive_requires_auth"
    # No DB archive is ever attempted for a public/anonymous user.
    mock_db_cls.return_value.archive_all_applications.assert_not_called()

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


def _api_with_pending(can_mutate_applications: bool = True):
    """RicoChatAPI with an active pending pipeline-reset, memory mocked.

    Defaults to an authenticated capability (can_mutate_applications=True) so
    existing archive-execution tests exercise an authenticated session, mirroring
    how chat_service.py sets it from ctx.auth_type == "authenticated". Tests for
    the public/unauthenticated path pass can_mutate_applications=False explicitly.
    """
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI(can_mutate_applications=can_mutate_applications)
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

def test_archive_executes_bulk_archive_for_authenticated_user():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "db-uuid-123"
        mock_db_cls.return_value.archive_all_applications.return_value = 5
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    # Resolved DB user ID before archive
    mock_resolve.assert_called_once()
    # Executed the bulk archive against the DB with resolved UUID
    mock_db_cls.return_value.archive_all_applications.assert_called_once_with("db-uuid-123")
    assert result["type"] == "pipeline_reset_archived"
    # Completes in chat — does NOT punt the user to /applications as the only path.
    assert result.get("target_route") != "/applications"


# 3. Confirmation includes archived count ------------------------------------

def test_archive_confirmation_reports_the_count():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "db-uuid-123"
        mock_db_cls.return_value.archive_all_applications.return_value = 7
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    assert result.get("archived_count") == 7
    assert "7" in result["message"]


# 4. DB failure -> no success claim, nothing changed -------------------------

def test_archive_db_failure_makes_no_success_claim():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "db-uuid-123"
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
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        result = api._handle_pending_pipeline_reset(AUTH_UID, "cancel")

    assert result["type"] == "pipeline_reset_cancelled"
    assert "nothing was changed" in result["message"].lower()
    # The DB is never touched on cancel.
    mock_db_cls.assert_not_called()
    mock_resolve.assert_not_called()


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
    api = _api_with_pending(can_mutate_applications=False)
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        result = api._handle_pending_pipeline_reset(PUBLIC_UID, "archive")

    assert result["type"] == "pipeline_reset_archive_requires_auth"
    # No DB archive is ever attempted for a public/anonymous user.
    mock_db_cls.return_value.archive_all_applications.assert_not_called()
    mock_resolve.assert_not_called()


# 8b. Public session with an unverified EMAIL-SHAPED user_id must still be
# blocked — auth must never be inferred from the shape of user_id. This is
# the exact cross-user mutation risk: /chat/public lets a caller set user_id
# to any string, including one that looks like a real account's email, while
# auth_type stays "public".

def test_public_session_with_email_shaped_user_id_cannot_archive():
    api = _api_with_pending(can_mutate_applications=False)
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve, \
         patch("src.repositories.user_job_context_repo.bulk_archive_active") as mock_ctx_archive:
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    assert result["type"] == "pipeline_reset_archive_requires_auth"
    mock_resolve.assert_not_called()
    mock_db_cls.return_value.archive_all_applications.assert_not_called()
    mock_ctx_archive.assert_not_called()


def test_authenticated_session_can_archive_with_email_user_id():
    """Sanity counterpart: the same email-shaped id DOES archive once the
    caller has actually verified auth_type == 'authenticated'."""
    api = _api_with_pending(can_mutate_applications=True)
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "db-uuid-789"
        mock_db_cls.return_value.archive_all_applications.return_value = 2
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    mock_resolve.assert_called_once()
    mock_db_cls.return_value.archive_all_applications.assert_called_once_with("db-uuid-789")
    assert result["type"] == "pipeline_reset_archived"


def test_archive_dont_delete_still_archives():
    """'archive, don't delete' must archive — negation must be scoped to the
    word it negates, not cancel on any negative word anywhere in the message."""
    api = _api_with_pending(can_mutate_applications=True)
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "db-uuid-321"
        mock_db_cls.return_value.archive_all_applications.return_value = 4
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive, don't delete")

    assert result["type"] == "pipeline_reset_archived"
    mock_db_cls.return_value.archive_all_applications.assert_called_once_with("db-uuid-321")


def test_archive_do_not_delete_still_archives():
    api = _api_with_pending(can_mutate_applications=True)
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "db-uuid-654"
        mock_db_cls.return_value.archive_all_applications.return_value = 1
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive, do not delete")

    assert result["type"] == "pipeline_reset_archived"
    mock_db_cls.return_value.archive_all_applications.assert_called_once_with("db-uuid-654")


# 7. Negative/cancel intent cancels without DB call -----------------------------

def test_dont_archive_cancels_without_db_call():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        result = api._handle_pending_pipeline_reset(AUTH_UID, "don't archive")

    assert result["type"] == "pipeline_reset_cancelled"
    assert "nothing was changed" in result["message"].lower()
    # DB is never touched when user says "don't archive"
    mock_db_cls.assert_not_called()
    mock_resolve.assert_not_called()


def test_cancel_archive_cancels_without_db_call():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        result = api._handle_pending_pipeline_reset(AUTH_UID, "cancel archive")

    assert result["type"] == "pipeline_reset_cancelled"
    assert "nothing was changed" in result["message"].lower()
    # DB is never touched when user cancels
    mock_db_cls.assert_not_called()
    mock_resolve.assert_not_called()


# 8. DB user resolution safety -------------------------------------------------

def test_archive_resolves_db_user_id_before_update():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "resolved-db-uuid-456"
        mock_db_cls.return_value.archive_all_applications.return_value = 3
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    # DB user ID is resolved before archive
    mock_resolve.assert_called_once()
    # Archive uses resolved UUID, not raw email
    mock_db_cls.return_value.archive_all_applications.assert_called_once_with("resolved-db-uuid-456")
    assert result["type"] == "pipeline_reset_archived"


def test_archive_db_user_resolution_failure_is_safe():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = None  # Resolution fails
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    assert result["type"] == "pipeline_reset_archive_failed"
    # No DB write when resolution fails
    mock_db_cls.return_value.archive_all_applications.assert_not_called()
    low = result["message"].lower()
    assert "couldn't" in low or "could not" in low or "تعذّر" in result["message"]


# 9. Success message does not claim restore ------------------------------------

def test_archive_success_message_does_not_claim_restore():
    api = _api_with_pending()
    with patch.object(api, "_append_chat"), \
         patch("src.rico_db.RicoDB") as mock_db_cls, \
         patch("src.repositories.applications_repo._provision_db_user_id") as mock_resolve:
        mock_resolve.return_value = "db-uuid-123"
        mock_db_cls.return_value.archive_all_applications.return_value = 5
        result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

    assert result["type"] == "pipeline_reset_archived"
    msg = result["message"].lower()
    # Should not claim reversibility or restore capability
    assert "reversible" not in msg
    assert "restore" not in msg
    assert "قابلة للعكس" not in result["message"]
    # Should mention viewing archive instead
    assert "view" in msg or "عرض" in result["message"]

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

Tests cover two complementary code paths that together fix the bug:
  1. _handle_pipeline_reset / _handle_pending_pipeline_reset (P2-B path)
     — triggered by _PIPELINE_RESET_RE, backed by RicoDB.archive_all_applications
  2. _resolve_pending_field confirm_bulk_archive path
     — triggered by _BULK_ARCHIVE_REQUEST_RE, backed by bulk_archive_active repo fn

Safety: no live DB — persistence is mocked.
"""
from __future__ import annotations

import os
import re
import sys
import time
from types import ModuleType
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

AUTH_UID = "user@example.com"
PUBLIC_UID = "public:web:anon-123"
USER_ID = "test_archive_user@example.com"


def _stub_heavy_modules():
    """Inject just-enough module stubs so rico_chat_api can be imported."""
    stubs = {
        "requests": MagicMock(),
        "openai": MagicMock(),
        "redis": MagicMock(),
        "redis.asyncio": MagicMock(),
        "rq": MagicMock(),
        "slowapi": MagicMock(),
        "slowapi.util": MagicMock(),
        "slowapi.errors": MagicMock(),
        "limits": MagicMock(),
        "limits.storage": MagicMock(),
        "jose": MagicMock(),
        "jose.jwt": MagicMock(),
        "passlib": MagicMock(),
        "passlib.context": MagicMock(),
        "sentry_sdk": MagicMock(),
        "PyMuPDF": MagicMock(),
        "fitz": MagicMock(),
        "docx": MagicMock(),
        "python_docx": MagicMock(),
        "filelock": MagicMock(),
        "playwright": MagicMock(),
        "playwright.sync_api": MagicMock(),
        "anthropic": MagicMock(),
    }
    injected = {}
    for name, stub in stubs.items():
        if name not in sys.modules:
            sys.modules[name] = stub
            injected[name] = True
    return injected


# Apply stubs at module level so all top-level imports of rico_chat_api succeed.
_stub_heavy_modules()


# ─── Helper: build API with active pending pipeline-reset ────────────────────

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


# ═══════════════════════════════════════════════════════════════════════════════
# Part 1: _handle_pipeline_reset / _handle_pending_pipeline_reset (P2-B path)
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# Part 2: _BULK_ARCHIVE_REQUEST_RE + _resolve_pending_field confirm_bulk_archive
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Regex: tested inline to avoid importing rico_chat_api ───────────────────
# Keep this pattern in sync with the one in rico_chat_api.py.
_BULK_ARCHIVE_REQUEST_RE = re.compile(
    r"\b(?:clear|wipe|reset|remove|delete|erase)\s+(?:all\s+(?:my\s+)?|them|my\s+)?(?:applications?|tracked\s+jobs?|job\s+tracks?|tracking)\b"
    r"|\b(?:start|begin)\s+(?:over|fresh|again|from\s+scratch)\b"
    r"|\bclear\s+them\b"
    r"|\bwipe\s+(?:it|them)\s+all\b"
    r"|\bرجّع\s+من\s+البداية\b"
    r"|\b(?:امسح|احذف|مسح|حذف)\s+(?:كل\s+)?(?:طلباتي|التتبع|الوظائف\s+المتتبعة)\b",
    re.IGNORECASE,
)


class TestBulkArchiveRequestRegex:
    """_BULK_ARCHIVE_REQUEST_RE must match the documented trigger phrases."""

    def test_clear_them_matches(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("CLEAR THEM LETS START FRESH")

    def test_start_fresh_matches(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("I want to start fresh")

    def test_start_over_matches(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("let's start over")

    def test_clear_all_applications(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("clear all my applications")

    def test_reset_all_applications(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("reset all applications")

    def test_wipe_my_tracked_jobs(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("wipe my tracked jobs")

    def test_clear_tracking_matches(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("clear my tracking")

    def test_begin_again(self):
        assert _BULK_ARCHIVE_REQUEST_RE.search("begin again")

    def test_unrelated_does_not_match(self):
        assert not _BULK_ARCHIVE_REQUEST_RE.search("show me jobs in Dubai")

    def test_apply_for_job_does_not_match(self):
        assert not _BULK_ARCHIVE_REQUEST_RE.search("apply for this job")

    def test_find_me_jobs_does_not_match(self):
        assert not _BULK_ARCHIVE_REQUEST_RE.search("find me jobs in finance")


# ─── Repo: bulk_archive_active ────────────────────────────────────────────────

class TestBulkArchiveActiveRepo:
    """bulk_archive_active in user_job_context_repo must behave correctly."""

    def test_returns_minus_one_for_empty_user_id(self):
        from src.repositories.user_job_context_repo import bulk_archive_active

        result = bulk_archive_active("")
        assert result == -1

    def test_returns_minus_one_for_none_user_id(self):
        from src.repositories.user_job_context_repo import bulk_archive_active

        result = bulk_archive_active(None)  # type: ignore[arg-type]
        assert result == -1

    def test_returns_minus_one_when_db_unavailable(self):
        from src.repositories.user_job_context_repo import bulk_archive_active

        with patch("src.db.get_db_connection", return_value=None):
            result = bulk_archive_active(USER_ID)

        assert result == -1

    def test_returns_rowcount_on_success(self):
        from src.repositories.user_job_context_repo import bulk_archive_active

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 5
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.get_db_connection", return_value=mock_conn):
            result = bulk_archive_active(USER_ID)

        assert result == 5
        mock_conn.commit.assert_called_once()

    def test_returns_minus_one_on_db_error(self):
        from src.repositories.user_job_context_repo import bulk_archive_active

        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("DB exploded")

        with patch("src.db.get_db_connection", return_value=mock_conn):
            result = bulk_archive_active(USER_ID)

        assert result == -1
        mock_conn.rollback.assert_called()

    def test_sql_excludes_already_archived(self):
        """SQL WHERE clause must exclude already-archived rows."""
        from src.repositories.user_job_context_repo import bulk_archive_active

        executed_sql = []

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 2

        def capture_execute(sql, params):
            executed_sql.append(sql)

        mock_cursor.execute = capture_execute
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.get_db_connection", return_value=mock_conn):
            bulk_archive_active(USER_ID)

        assert executed_sql, "execute must have been called"
        assert "archived" in executed_sql[0], (
            "SQL must reference 'archived' to filter out already-archived rows"
        )

    def test_sql_sets_status_to_archived(self):
        """Verify the UPDATE sets status = 'archived'."""
        from src.repositories.user_job_context_repo import bulk_archive_active

        executed_sql = []

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 1

        def capture_execute(sql, params):
            executed_sql.append(sql)

        mock_cursor.execute = capture_execute
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.get_db_connection", return_value=mock_conn):
            bulk_archive_active(USER_ID)

        assert any("UPDATE" in sql for sql in executed_sql), "Must issue an UPDATE"
        assert any("archived" in sql for sql in executed_sql)


# ─── _resolve_pending_field: confirm_bulk_archive ────────────────────────────

def _resolve_pending_field_under_test(pending_field: str, user_reply: str, bulk_return: int):
    """
    Directly invoke _resolve_pending_field with confirm_bulk_archive pending
    and bulk_archive_active returning `bulk_return`.

    Returns the response dict (or None if the pending field wasn't matched).
    """
    injected = _stub_heavy_modules()
    try:
        # Clear cached module if already loaded without stubs
        for mod in list(sys.modules):
            if "rico_chat_api" in mod:
                del sys.modules[mod]

        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI()
        api.memory = MagicMock()

        # _get_recent_context returns the pending field
        api.memory.get_context.return_value = {"_pending_field": pending_field}
        api.memory.set_context.return_value = None
        api._append_chat = MagicMock()

        profile = MagicMock()
        profile.has_cv = True

        with patch(
            "src.repositories.user_job_context_repo.bulk_archive_active",
            return_value=bulk_return,
        ):
            return api._resolve_pending_field(USER_ID, user_reply, profile)
    finally:
        for name in injected:
            del sys.modules[name]


class TestResolvePendingBulkArchive:
    """_resolve_pending_field: confirm_bulk_archive cases."""

    def test_archive_reply_returns_count(self):
        result = _resolve_pending_field_under_test("confirm_bulk_archive", "archive", 7)
        assert result is not None
        assert result.get("archived_count") == 7
        assert "7" in result["message"]

    def test_archive_reply_singular_count(self):
        result = _resolve_pending_field_under_test("confirm_bulk_archive", "archive", 1)
        assert result is not None
        assert result.get("archived_count") == 1
        assert "1" in result["message"]

    def test_db_failure_returns_error_not_success(self):
        """bulk_archive_active returning -1 must produce type='error', no count."""
        result = _resolve_pending_field_under_test("confirm_bulk_archive", "archive", -1)
        assert result is not None
        assert result.get("type") == "error"
        assert "archived_count" not in result
        msg = result["message"].lower()
        assert any(w in msg for w in ("wrong", "error", "fail", "not", "could")), (
            f"Error message should indicate failure, got: {result['message']}"
        )

    def test_zero_active_apps_no_count(self):
        result = _resolve_pending_field_under_test("confirm_bulk_archive", "archive", 0)
        assert result is not None
        assert result.get("type") == "info"
        assert "archived_count" not in result

    def test_cancel_does_not_call_bulk_archive(self):
        injected = _stub_heavy_modules()
        try:
            for mod in list(sys.modules):
                if "rico_chat_api" in mod:
                    del sys.modules[mod]

            from src.rico_chat_api import RicoChatAPI

            api = RicoChatAPI()
            api.memory = MagicMock()
            api.memory.get_context.return_value = {"_pending_field": "confirm_bulk_archive"}
            api.memory.set_context.return_value = None
            api._append_chat = MagicMock()
            profile = MagicMock()

            with patch(
                "src.repositories.user_job_context_repo.bulk_archive_active"
            ) as mock_bulk:
                result = api._resolve_pending_field(USER_ID, "cancel", profile)

            mock_bulk.assert_not_called()
            assert result is not None
            assert result.get("type") == "info"
            assert "archived_count" not in result
        finally:
            for name in injected:
                del sys.modules[name]

    def test_no_does_not_call_bulk_archive(self):
        injected = _stub_heavy_modules()
        try:
            for mod in list(sys.modules):
                if "rico_chat_api" in mod:
                    del sys.modules[mod]

            from src.rico_chat_api import RicoChatAPI

            api = RicoChatAPI()
            api.memory = MagicMock()
            api.memory.get_context.return_value = {"_pending_field": "confirm_bulk_archive"}
            api.memory.set_context.return_value = None
            api._append_chat = MagicMock()
            profile = MagicMock()

            with patch(
                "src.repositories.user_job_context_repo.bulk_archive_active"
            ) as mock_bulk:
                result = api._resolve_pending_field(USER_ID, "no", profile)

            mock_bulk.assert_not_called()
        finally:
            for name in injected:
                del sys.modules[name]

    def test_delete_blocked_and_pending_kept_alive(self):
        """'delete' must not permanently delete; pending field must remain."""
        injected = _stub_heavy_modules()
        try:
            for mod in list(sys.modules):
                if "rico_chat_api" in mod:
                    del sys.modules[mod]

            from src.rico_chat_api import RicoChatAPI

            api = RicoChatAPI()
            api.memory = MagicMock()
            ctx = {"_pending_field": "confirm_bulk_archive"}
            api.memory.get_context.return_value = ctx
            api.memory.set_context.return_value = None
            api._append_chat = MagicMock()
            profile = MagicMock()

            with patch(
                "src.repositories.user_job_context_repo.bulk_archive_active"
            ) as mock_bulk:
                result = api._resolve_pending_field(USER_ID, "delete", profile)

            mock_bulk.assert_not_called()
            assert result is not None
            assert result.get("type") == "info"

            # Pending must have been reset so a follow-up "archive" still works
            set_calls = [c for c in api.memory.set_context.call_args_list
                         if len(c.args) > 1 and c.args[1] == "recent_context"]
            assert any(
                c.args[2].get("_pending_field") == "confirm_bulk_archive"
                for c in set_calls
            ), "pending_field must remain confirm_bulk_archive after 'delete' reply"
        finally:
            for name in injected:
                del sys.modules[name]

    def test_no_route_to_applications_page(self):
        """Archive reply must NOT route to /applications."""
        result = _resolve_pending_field_under_test("confirm_bulk_archive", "archive", 4)
        assert result is not None
        assert result.get("target_route") != "/applications"

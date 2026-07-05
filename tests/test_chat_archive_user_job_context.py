"""
tests/test_chat_archive_user_job_context.py

Follow-up to PR #851 (which archived only rico_job_recommendations).

The chat's lifecycle lists — saved / applied / opened-but-not-applied — are
read from ``user_job_context`` (see rico_chat_api._handle_lifecycle_query,
"Answer funnel-memory questions from user_job_context"), NOT from
``rico_job_recommendations``. So a confirmed "archive" that touched only the
recommendations table left those lists visibly intact and the "start fresh"
reset looked like it did nothing.

This suite covers:
  - bulk_archive_active(user_id) on user_job_context: success, DB-unavailable,
    empty user, DB error, and that the SQL archives (not deletes) and skips
    already-archived rows.
  - _handle_pending_pipeline_reset now also archives user_job_context and folds
    its rowcount into the reported count — while a context-side failure never
    undoes or misreports the recommendations archive that already committed.

Safety: no live DB — both stores are mocked.
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
USER_ID = "archive_ctx_user@example.com"

_CTX_ARCHIVE = "src.repositories.user_job_context_repo.bulk_archive_active"


# ─── Repo: bulk_archive_active on user_job_context ───────────────────────────

class TestBulkArchiveActiveContextRepo:
    def test_empty_user_id_returns_minus_one(self):
        from src.repositories.user_job_context_repo import bulk_archive_active
        assert bulk_archive_active("") == -1

    def test_none_user_id_returns_minus_one(self):
        from src.repositories.user_job_context_repo import bulk_archive_active
        assert bulk_archive_active(None) == -1  # type: ignore[arg-type]

    def test_db_unavailable_returns_minus_one(self):
        from src.repositories.user_job_context_repo import bulk_archive_active
        with patch("src.db.get_db_connection", return_value=None):
            assert bulk_archive_active(USER_ID) == -1

    def test_success_returns_rowcount_and_commits(self):
        from src.repositories.user_job_context_repo import bulk_archive_active

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 4
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.get_db_connection", return_value=mock_conn):
            assert bulk_archive_active(USER_ID) == 4
        mock_conn.commit.assert_called_once()

    def test_db_error_returns_minus_one_and_rolls_back(self):
        from src.repositories.user_job_context_repo import bulk_archive_active

        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("DB exploded")

        with patch("src.db.get_db_connection", return_value=mock_conn):
            assert bulk_archive_active(USER_ID) == -1
        mock_conn.rollback.assert_called()

    def test_sql_archives_not_deletes_and_skips_archived(self):
        """UPDATE ... SET status='archived' WHERE status <> 'archived' — reversible."""
        from src.repositories.user_job_context_repo import bulk_archive_active

        seen = []
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 1
        mock_cursor.execute = lambda sql, params: seen.append(sql)
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.get_db_connection", return_value=mock_conn):
            bulk_archive_active(USER_ID)

        assert seen, "execute must have been called"
        sql = seen[0]
        assert "UPDATE user_job_context" in sql
        assert "DELETE" not in sql.upper()
        assert "archived" in sql
        assert "<>" in sql  # excludes already-archived rows


# ─── Handler: _handle_pending_pipeline_reset archives BOTH stores ────────────

def _api_with_pending():
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    api.memory = MagicMock()
    pending = {"pending": True, "expires_at": int(time.time()) + 120}
    api.memory.get_context.side_effect = lambda uid, key: (
        pending if key == RicoChatAPI._PENDING_PIPELINE_RESET_KEY else None
    )
    return api


class TestHandlerArchivesBothStores:
    def test_archive_also_clears_user_job_context(self):
        """Confirmed 'archive' must call bulk_archive_active for the same user."""
        api = _api_with_pending()
        with patch.object(api, "_append_chat"), \
             patch("src.rico_db.RicoDB") as mock_db_cls, \
             patch(_CTX_ARCHIVE, return_value=3) as mock_ctx:
            mock_db_cls.return_value.archive_all_applications.return_value = 5
            result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

        mock_ctx.assert_called_once_with(AUTH_UID)
        assert result["type"] == "pipeline_reset_archived"

    def test_reported_count_is_combined_total(self):
        """recommendations (5) + user_job_context (3) → 8 reported."""
        api = _api_with_pending()
        with patch.object(api, "_append_chat"), \
             patch("src.rico_db.RicoDB") as mock_db_cls, \
             patch(_CTX_ARCHIVE, return_value=3):
            mock_db_cls.return_value.archive_all_applications.return_value = 5
            result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

        assert result["archived_count"] == 8
        assert "8" in result["message"]

    def test_context_only_rows_still_report_success(self):
        """rec=0 but ctx=6 must report an archive, not 'nothing to archive'."""
        api = _api_with_pending()
        with patch.object(api, "_append_chat"), \
             patch("src.rico_db.RicoDB") as mock_db_cls, \
             patch(_CTX_ARCHIVE, return_value=6):
            mock_db_cls.return_value.archive_all_applications.return_value = 0
            result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

        assert result["archived_count"] == 6
        assert "6" in result["message"]
        assert "don't have any active" not in result["message"].lower()

    def test_context_failure_does_not_break_or_misreport(self):
        """ctx returns -1 (unavailable/error): report only the rec count, no crash."""
        api = _api_with_pending()
        with patch.object(api, "_append_chat"), \
             patch("src.rico_db.RicoDB") as mock_db_cls, \
             patch(_CTX_ARCHIVE, return_value=-1):
            mock_db_cls.return_value.archive_all_applications.return_value = 5
            result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

        # -1 is never added — the recommendations count stands on its own.
        assert result["archived_count"] == 5
        assert result["type"] == "pipeline_reset_archived"

    def test_context_exception_is_swallowed(self):
        """A raised exception from the context archive must not fail the flow."""
        api = _api_with_pending()
        with patch.object(api, "_append_chat"), \
             patch("src.rico_db.RicoDB") as mock_db_cls, \
             patch(_CTX_ARCHIVE, side_effect=RuntimeError("boom")):
            mock_db_cls.return_value.archive_all_applications.return_value = 5
            result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

        assert result["archived_count"] == 5
        assert result["type"] == "pipeline_reset_archived"

    def test_recommendations_failure_still_short_circuits(self):
        """If the recommendations archive fails, we never touch user_job_context."""
        api = _api_with_pending()
        with patch.object(api, "_append_chat"), \
             patch("src.rico_db.RicoDB") as mock_db_cls, \
             patch(_CTX_ARCHIVE) as mock_ctx:
            mock_db_cls.return_value.archive_all_applications.side_effect = RuntimeError("db down")
            result = api._handle_pending_pipeline_reset(AUTH_UID, "archive")

        assert result["type"] == "pipeline_reset_archive_failed"
        assert "archived_count" not in result
        mock_ctx.assert_not_called()

    def test_public_session_archives_neither_store(self):
        api = _api_with_pending()
        with patch.object(api, "_append_chat"), \
             patch("src.rico_db.RicoDB") as mock_db_cls, \
             patch(_CTX_ARCHIVE) as mock_ctx:
            result = api._handle_pending_pipeline_reset(PUBLIC_UID, "archive")

        assert result["type"] == "pipeline_reset_archive_requires_auth"
        mock_db_cls.return_value.archive_all_applications.assert_not_called()
        mock_ctx.assert_not_called()

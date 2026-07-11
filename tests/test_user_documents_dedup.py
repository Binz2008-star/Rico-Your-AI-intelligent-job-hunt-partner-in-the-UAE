"""
tests/test_user_documents_dedup.py

Exact-duplicate protection + atomic idempotency for CV/document uploads (#960).

Covers:
  * repo: save_user_document(content_hash=...) — new insert vs ON CONFLICT dup
    returns the existing row id (idempotent under concurrent/retry).
  * repo: find_user_document_by_hash.
  * route: POST /api/v1/user/files — exact duplicate returns the existing doc,
    creates no row, and does NOT consume quota; a distinct file still enforces
    quota; response stays backward-compatible; primary CV invariant preserved.

All DB / quota calls are mocked — no real database.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_FASTAPI_OK = importlib.util.find_spec("fastapi") is not None

from src.rico_db import RicoDB

_PDF = b"%PDF-1.4\n%demo cv bytes\n"


# ── Repo-level: atomic dedup in save_user_document ────────────────────────────

def _db_with_cursor(cur):
    """Patch RicoDB._transaction to yield a connection whose cursor is `cur`."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    tx = MagicMock()
    tx.__enter__.return_value = conn
    tx.__exit__.return_value = False
    return tx


class TestSaveUserDocumentDedup:
    def _db(self):
        db = RicoDB.__new__(RicoDB)
        db.database_url = "postgres://test"
        return db

    def test_new_insert_returns_new_id(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "new-uuid"}
        db = self._db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            doc_id = db.save_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, content_hash="abc123",
            )
        assert doc_id == "new-uuid"
        sql = " ".join(str(c.args[0]).upper() for c in cur.execute.call_args_list)
        assert "ON CONFLICT" in sql and "CONTENT_HASH" in sql

    def test_exact_duplicate_returns_existing_id_without_new_row(self):
        cur = MagicMock()
        # INSERT ... DO NOTHING returns no row; the follow-up SELECT finds the existing id.
        cur.fetchone.side_effect = [None, {"id": "existing-uuid"}]
        db = self._db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            doc_id = db.save_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, content_hash="abc123",
            )
        assert doc_id == "existing-uuid"
        # Exactly two statements: the conflicting INSERT, then the SELECT — no extra INSERT.
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        assert statements == ["INSERT", "SELECT"]

    def test_no_hash_path_unchanged(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "legacy-uuid"}
        db = self._db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)), \
             patch.object(RicoDB, "_clear_primary_flag") as clear:
            doc_id = db.save_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10,  # no content_hash
            )
        assert doc_id == "legacy-uuid"
        sql = " ".join(str(c.args[0]).upper() for c in cur.execute.call_args_list)
        assert "ON CONFLICT" not in sql
        clear.assert_not_called()  # is_primary False

    def test_find_user_document_by_hash(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True}
        db = self._db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            found = db.find_user_document_by_hash("u@test.com", "cv", "abc123")
        assert found == {"id": "x", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True}

    def test_find_user_document_by_hash_none(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        db = self._db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            assert db.find_user_document_by_hash("u@test.com", "cv", "nope") is None
        # empty hash short-circuits without a query
        assert db.find_user_document_by_hash("u@test.com", "cv", "") is None


# ── Route-level: POST /api/v1/user/files upload ──────────────────────────────

class _FakeUpload:
    def __init__(self, data: bytes, filename: str = "cv.pdf", size=None):
        self._data = data
        self.filename = filename
        self.size = size

    async def read(self) -> bytes:
        return self._data


@pytest.mark.skipif(not _FASTAPI_OK, reason="fastapi not installed in this environment")
class TestUploadDedupRoute:
    def _call(self, *, existing, doc_type="cv", data=_PDF):
        """Invoke the undecorated upload_file handler with mocked deps."""
        from src.api.routers import files as files_mod

        raw = getattr(files_mod.upload_file, "__wrapped__", files_mod.upload_file)
        mock_db = MagicMock()
        mock_db.available = True
        mock_db.find_user_document_by_hash.return_value = existing
        mock_db.save_user_document.return_value = "new-doc-id"

        enforce = MagicMock()
        req = MagicMock()
        with patch.object(files_mod, "_db", mock_db), \
             patch.object(files_mod, "enforce_document_quota", enforce), \
             patch.object(files_mod, "get_current_user", return_value={"email": "u@test.com", "role": "user"}):
            result = asyncio.get_event_loop().run_until_complete(
                raw(req, file=_FakeUpload(data), doc_type=doc_type)
            )
        return result, mock_db, enforce

    def test_exact_duplicate_returns_existing_no_quota_no_insert(self):
        existing = {"id": "existing-uuid", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True}
        result, mock_db, enforce = self._call(existing=existing)
        assert result["ok"] is True
        assert result["id"] == "existing-uuid"
        assert result["duplicate"] is True
        # No quota consumed and no new row on a duplicate.
        enforce.assert_not_called()
        mock_db.save_user_document.assert_not_called()

    def test_distinct_file_enforces_quota_and_saves_with_hash(self):
        result, mock_db, enforce = self._call(existing=None)
        assert result["ok"] is True
        assert result["id"] == "new-doc-id"
        assert result["duplicate"] is False
        # Quota enforced exactly as before for a new document.
        enforce.assert_called_once_with("u@test.com", "cv")
        # Saved with a content hash (atomic dedup at the DB layer).
        _, kwargs = mock_db.save_user_document.call_args
        assert kwargs["content_hash"] and isinstance(kwargs["content_hash"], str)
        assert kwargs["is_primary"] is False

    def test_response_shape_backward_compatible(self):
        result, _, _ = self._call(existing=None)
        assert {"ok", "id", "filename", "doc_type"}.issubset(result.keys())

    def test_primary_cv_reupload_preserves_primary(self):
        """Re-uploading the current primary CV returns it unchanged (no save, no quota)."""
        existing = {"id": "primary-uuid", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True}
        result, mock_db, enforce = self._call(existing=existing, doc_type="cv")
        assert result["id"] == "primary-uuid"
        assert result["duplicate"] is True
        mock_db.save_user_document.assert_not_called()  # primary flag untouched
        enforce.assert_not_called()

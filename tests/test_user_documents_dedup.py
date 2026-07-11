"""
tests/test_user_documents_dedup.py

Exact-duplicate protection + atomic idempotency for CV/document uploads (#960).

Covers:
  * repo: get_or_create_user_document — new insert vs ON CONFLICT reuse,
    canonical existing metadata on reuse, primary flag only moved on a real
    insert, single-transaction atomicity.
  * repo: find_user_document_by_hash.
  * repo: save_user_document (legacy, no content_hash) — atomic primary
    clear+insert in one transaction.
  * repo: set_primary_document — atomic, and a failed target lookup never
    wipes the existing primary (failure-safety test).
  * repo: update_user_document — a unique-violation (doc_type rename
    collision) raises DocumentConflictError instead of propagating as an
    unhandled 500; unrelated errors are not swallowed.
  * route: POST /api/v1/user/files — exact duplicate returns the EXISTING
    document's canonical filename, creates no row, and does NOT consume
    quota; a distinct file still enforces quota; a lost duplicate-insert race
    (pre-check says "new", DB says "duplicate") is still reported as
    duplicate=true with the canonical filename, never the uploaded one;
    different filename + same bytes = duplicate; same filename + different
    bytes = not a duplicate.
  * route: PATCH /api/v1/user/files/{id} — a doc_type rename that collides
    with an existing row returns 409, never an unhandled 500.

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

from src.rico_db import DocumentConflictError, RicoDB

_PDF = b"%PDF-1.4\n%demo cv bytes\n"


def _db_with_cursor(cur):
    """Patch RicoDB._transaction to yield a connection whose cursor is `cur`."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    tx = MagicMock()
    tx.__enter__.return_value = conn
    tx.__exit__.return_value = False
    return tx


def _new_db() -> RicoDB:
    db = RicoDB.__new__(RicoDB)
    db.database_url = "postgres://test"
    return db


# ── Repo-level: get_or_create_user_document ───────────────────────────────────

class TestGetOrCreateUserDocument:
    def test_new_insert_returns_inserted_true(self):
        cur = MagicMock()
        # 1st fetchone: duplicate pre-check (SELECT) -> not found.
        # 2nd fetchone: INSERT ... RETURNING.
        cur.fetchone.side_effect = [
            None,
            {"id": "new-uuid", "filename": "cv.pdf", "doc_type": "cv", "is_primary": False},
        ]
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, content_hash="abc123",
            )
        assert result == {
            "id": "new-uuid", "filename": "cv.pdf", "doc_type": "cv",
            "is_primary": False, "inserted": True,
        }
        sql = " ".join(str(c.args[0]).upper() for c in cur.execute.call_args_list)
        assert "ON CONFLICT" in sql and "CONTENT_HASH" in sql
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # content-lock SELECT is acquired on EVERY call, even is_primary=False
        # — this is the fix for the concurrency gap: two identical
        # non-primary uploads used to race the INSERT with no lock at all.
        assert statements == ["SELECT", "SELECT", "INSERT"]

    def test_exact_duplicate_returns_existing_canonical_metadata(self):
        """A pre-existing row must surface its OWN filename, not the filename
        of the upload that is being deduped against it — the response must
        never claim metadata that isn't actually what's stored."""
        cur = MagicMock()
        # Duplicate pre-check SELECT finds it immediately — no INSERT attempted.
        cur.fetchone.return_value = {
            "id": "existing-uuid", "filename": "ORIGINAL-cv.pdf", "doc_type": "cv", "is_primary": True,
        }
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="renamed-on-reupload.pdf",
                original_filename="renamed-on-reupload.pdf",
                doc_type="cv", file_size=10, content_hash="abc123",
            )
        assert result["inserted"] is False
        assert result["id"] == "existing-uuid"
        assert result["filename"] == "ORIGINAL-cv.pdf"  # canonical, not the incoming name
        assert result["is_primary"] is True
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # content-lock, THEN duplicate check finds it — no INSERT, no UPDATE.
        assert statements == ["SELECT", "SELECT"]

    def test_different_filename_same_bytes_is_a_duplicate(self):
        """Same content_hash (same bytes) with a different filename is still
        an exact duplicate — dedup is content-keyed, not filename-keyed."""
        cur = MagicMock()
        cur.fetchone.return_value = {
            "id": "existing-uuid", "filename": "first-name.pdf", "doc_type": "cv", "is_primary": False,
        }
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="second-name.pdf", original_filename="second-name.pdf",
                doc_type="cv", file_size=10, content_hash="same-hash-different-name",
            )
        assert result["inserted"] is False
        assert result["filename"] == "first-name.pdf"

    def test_same_filename_different_bytes_is_not_a_duplicate(self):
        """Two uploads sharing a filename but distinct content_hash both insert."""
        cur = MagicMock()
        cur.fetchone.side_effect = [
            None,
            {"id": "new-uuid-2", "filename": "cv.pdf", "doc_type": "cv", "is_primary": False},
        ]
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, content_hash="a-different-hash",
            )
        assert result["inserted"] is True
        assert result["id"] == "new-uuid-2"

    def test_primary_flag_untouched_when_duplicate_already_primary(self):
        """No promotion UPDATE is issued when the found duplicate is already
        primary — nothing to do."""
        cur = MagicMock()
        cur.fetchone.return_value = {
            "id": "existing-uuid", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True,
        }
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            db.get_or_create_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, content_hash="abc123", is_primary=True,
            )
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # content-lock, primary-lock, duplicate-check — no UPDATE, no INSERT.
        assert statements == ["SELECT", "SELECT", "SELECT"]

    def test_primary_requested_promotes_existing_nonprimary_duplicate(self):
        """The scenario a non-primary upload racing a primary one for the
        SAME content_hash relies on: is_primary=True finds an existing
        duplicate that is NOT primary (a concurrent non-primary call won the
        content-lock race and inserted it first) via the fast pre-check —
        it must be promoted, or the caller would get inserted=false with
        is_primary=false, silently dropping the is_primary=True request and
        leaving zero primary documents for this doc_type."""
        cur = MagicMock()
        cur.fetchone.return_value = {
            "id": "existing-uuid", "filename": "cv.pdf", "doc_type": "cv", "is_primary": False,
        }
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, content_hash="abc123", is_primary=True,
            )
        assert result["inserted"] is False
        assert result["id"] == "existing-uuid"
        assert result["is_primary"] is True  # promoted, never silently dropped
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # content-lock, primary-lock, duplicate-check (found, not primary),
        # then _promote_if_requested's clear-others + set-primary.
        assert statements == ["SELECT", "SELECT", "SELECT", "UPDATE", "UPDATE"]

    def test_primary_flag_moved_atomically_on_real_insert(self):
        """A genuine insert with is_primary=True clears the OLD primary BEFORE
        inserting the new one (required by the non-deferrable partial unique
        index), all inside one locked transaction (single _transaction() call
        = atomic)."""
        cur = MagicMock()
        cur.fetchone.side_effect = [
            None,  # duplicate pre-check: not found
            {"id": "new-uuid", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True},  # INSERT RETURNING
        ]
        db = _new_db()
        tx = _db_with_cursor(cur)
        with patch.object(RicoDB, "_transaction", return_value=tx) as mock_tx:
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, content_hash="abc123", is_primary=True,
            )
        assert result["inserted"] is True
        mock_tx.assert_called_once()  # one transaction — locks + check + clear + insert together
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # content-lock, primary-lock, duplicate check, clear-old-primary, THEN
        # insert — never insert-before-clear (that would violate the
        # non-deferrable partial unique index the instant the INSERT ran).
        assert statements == ["SELECT", "SELECT", "SELECT", "UPDATE", "INSERT"]

    def test_non_primary_conflict_under_content_lock_returns_gracefully(self):
        """The bug this round fixes: a non-primary upload used to have NO
        lock at all, so a concurrent identical upload could make its own
        INSERT ... ON CONFLICT DO NOTHING return no row, and the old code
        raised RuntimeError -> a 500 for a completely normal double-click /
        client-retry race. It must now return inserted=False with the
        winner's canonical row instead, same as any other duplicate."""
        cur = MagicMock()
        cur.fetchone.side_effect = [
            None,  # duplicate pre-check: not found (raced)
            None,  # INSERT ... ON CONFLICT DO NOTHING: lost the race, no row
            {"id": "winner-uuid", "filename": "winner.pdf", "doc_type": "cv", "is_primary": False},  # fallback SELECT
        ]
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="loser.pdf", original_filename="loser.pdf",
                doc_type="cv", file_size=10, content_hash="abc123",
            )
        assert result == {
            "id": "winner-uuid", "filename": "winner.pdf", "doc_type": "cv",
            "is_primary": False, "inserted": False,
        }
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        assert statements == ["SELECT", "SELECT", "INSERT", "SELECT"]
        assert "RAISE" not in " ".join(statements)  # sanity: no exception path taken

    def test_primary_conflict_under_lock_promotes_found_row_never_zero_primary(self):
        """Same race as above but is_primary=True was requested and we'd
        already cleared the old primary — the found existing row must be
        promoted so the transaction never commits with zero primaries."""
        cur = MagicMock()
        cur.fetchone.side_effect = [
            None,  # duplicate pre-check: not found (raced)
            None,  # INSERT ... ON CONFLICT DO NOTHING: lost the race
            {"id": "winner-uuid", "filename": "winner.pdf", "doc_type": "cv", "is_primary": False},  # fallback SELECT
        ]
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            result = db.get_or_create_user_document(
                user_id="u@test.com", filename="loser.pdf", original_filename="loser.pdf",
                doc_type="cv", file_size=10, content_hash="abc123", is_primary=True,
            )
        assert result["inserted"] is False
        assert result["id"] == "winner-uuid"
        assert result["is_primary"] is True  # promoted, not left False
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # content-lock, primary-lock, dup-check, clear-old (pre-insert),
        # INSERT(conflict), fallback SELECT, then _promote_if_requested's
        # own clear-others (redundant no-op here) + set-primary UPDATE.
        assert statements == ["SELECT", "SELECT", "SELECT", "UPDATE", "INSERT", "SELECT", "UPDATE", "UPDATE"]

    def test_conflict_with_no_matching_row_at_all_still_raises(self):
        """The one remaining raise: not a normal duplicate race (ON CONFLICT
        DO NOTHING implies a conflicting row exists) but genuinely nothing is
        found afterward — real anomaly, not a race, so the transaction must
        roll back rather than fabricate a document."""
        cur = MagicMock()
        cur.fetchone.side_effect = [None, None, None]  # pre-check, INSERT, fallback SELECT — all empty
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            with pytest.raises(RuntimeError):
                db.get_or_create_user_document(
                    user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                    doc_type="cv", file_size=10, content_hash="abc123",
                )


# ── Repo-level: find_user_document_by_hash ─────────────────────────────────────

class TestFindUserDocumentByHash:
    def test_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True}
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            found = db.find_user_document_by_hash("u@test.com", "cv", "abc123")
        assert found == {"id": "x", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True}

    def test_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            assert db.find_user_document_by_hash("u@test.com", "cv", "nope") is None

    def test_empty_hash_short_circuits(self):
        db = _new_db()
        assert db.find_user_document_by_hash("u@test.com", "cv", "") is None


# ── Repo-level: save_user_document (legacy, no content_hash) ─────────────────

class TestSaveUserDocumentLegacy:
    def test_insert_returns_new_id(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "legacy-uuid"}
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            doc_id = db.save_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10,
            )
        assert doc_id == "legacy-uuid"

    def test_primary_clear_and_insert_are_one_transaction(self):
        """The pre-PR bug: clear-old-primary and insert-new ran in two separate
        transactions. A crash between them could leave zero primary docs. Both
        must now happen inside a single _transaction() call."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "new-primary-uuid"}
        db = _new_db()
        tx = _db_with_cursor(cur)
        with patch.object(RicoDB, "_transaction", return_value=tx) as mock_tx:
            db.save_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, is_primary=True,
            )
        mock_tx.assert_called_once()
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # advisory lock, THEN clear-old-primary, THEN insert.
        assert statements == ["SELECT", "UPDATE", "INSERT"]

    def test_no_primary_clear_when_not_primary(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            db.save_user_document(
                user_id="u@test.com", filename="cv.pdf", original_filename="cv.pdf",
                doc_type="cv", file_size=10, is_primary=False,
            )
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        assert statements == ["INSERT"]


# ── Repo-level: set_primary_document ──────────────────────────────────────────

class TestSetPrimaryDocument:
    def test_success_validates_then_clears_then_sets_atomically(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "doc-1"}  # validate SELECT matched
        db = _new_db()
        tx = _db_with_cursor(cur)
        with patch.object(RicoDB, "_transaction", return_value=tx) as mock_tx:
            ok = db.set_primary_document("u@test.com", "doc-1")
        assert ok is True
        mock_tx.assert_called_once()
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        # advisory lock, validate (no mutation), clear-old, set-new — never two
        # TRUE rows visible to the non-deferrable partial unique index at once.
        assert statements == ["SELECT", "SELECT", "UPDATE", "UPDATE"]

    def test_failure_target_not_found_never_touches_other_rows(self):
        """A bad/foreign doc_id must abort before clearing anything — the
        existing primary (if any) must survive an invalid set-primary call."""
        cur = MagicMock()
        cur.fetchone.return_value = None  # validate SELECT matched nothing
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            ok = db.set_primary_document("u@test.com", "does-not-exist")
        assert ok is False
        # Only the advisory lock + the (no-op) validate SELECT ran — zero UPDATEs.
        statements = [str(c.args[0]).strip().upper().split()[0] for c in cur.execute.call_args_list]
        assert statements == ["SELECT", "SELECT"]
        assert "UPDATE" not in statements


# ── Repo-level: update_user_document conflict handling ────────────────────────

class TestUpdateUserDocumentConflict:
    def test_unique_violation_raises_document_conflict_error(self):
        """A doc_type rename that collides with an existing (user_id, doc_type,
        content_hash) row must raise a controlled DocumentConflictError, never
        let the raw unique-violation propagate as an unhandled 500."""
        cur = MagicMock()
        violation = Exception("duplicate key value violates unique constraint")
        violation.pgcode = "23505"
        cur.execute.side_effect = violation
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            with pytest.raises(DocumentConflictError):
                db.update_user_document("u@test.com", "doc-1", doc_type="cv")

    def test_unrelated_db_error_is_not_swallowed(self):
        cur = MagicMock()
        other_error = Exception("connection reset")
        other_error.pgcode = None
        cur.execute.side_effect = other_error
        db = _new_db()
        with patch.object(RicoDB, "_transaction", return_value=_db_with_cursor(cur)):
            with pytest.raises(Exception) as exc_info:
                db.update_user_document("u@test.com", "doc-1", doc_type="cv")
        assert exc_info.value is other_error
        assert not isinstance(exc_info.value, DocumentConflictError)


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
    def _call(self, *, existing, get_or_create_result=None, doc_type="cv", data=_PDF, filename="cv.pdf"):
        """Invoke the undecorated upload_file handler with mocked deps."""
        from src.api.routers import files as files_mod

        raw = getattr(files_mod.upload_file, "__wrapped__", files_mod.upload_file)
        mock_db = MagicMock()
        mock_db.available = True
        mock_db.find_user_document_by_hash.return_value = existing
        mock_db.get_or_create_user_document.return_value = get_or_create_result

        enforce = MagicMock()
        req = MagicMock()
        with patch.object(files_mod, "_db", mock_db), \
             patch.object(files_mod, "enforce_document_quota", enforce), \
             patch.object(files_mod, "get_current_user", return_value={"email": "u@test.com", "role": "user"}):
            # asyncio.run() (not get_event_loop().run_until_complete()) --
            # get_event_loop() raises "there is no current event loop in
            # thread 'MainThread'" when an earlier async test in the same
            # pytest session has already torn down/unset the thread's loop
            # (order-dependent, only reproduces in the full combined run).
            # asyncio.run() always creates and cleans up its own loop, so
            # it's independent of any prior test's event-loop state.
            result = asyncio.run(
                raw(req, file=_FakeUpload(data, filename=filename), doc_type=doc_type)
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
        mock_db.get_or_create_user_document.assert_not_called()

    def test_distinct_file_enforces_quota_and_saves_with_hash(self):
        insert_result = {
            "id": "new-doc-id", "filename": "cv.pdf", "doc_type": "cv",
            "is_primary": False, "inserted": True,
        }
        result, mock_db, enforce = self._call(existing=None, get_or_create_result=insert_result)
        assert result["ok"] is True
        assert result["id"] == "new-doc-id"
        assert result["duplicate"] is False
        # Quota enforced exactly as before for a new document.
        enforce.assert_called_once_with("u@test.com", "cv")
        # Saved with a content hash (atomic dedup at the DB layer).
        _, kwargs = mock_db.get_or_create_user_document.call_args
        assert kwargs["content_hash"] and isinstance(kwargs["content_hash"], str)
        assert kwargs["is_primary"] is False

    def test_lost_race_still_reports_duplicate_with_canonical_filename(self):
        """The pre-check says 'not a duplicate' (find_user_document_by_hash ->
        None), but a concurrent identical upload wins the DB-level race, so
        get_or_create_user_document returns inserted=False. The response MUST
        reflect that — duplicate=True and the EXISTING row's filename, never
        the filename this (losing) request tried to upload."""
        race_result = {
            "id": "winner-uuid", "filename": "WINNER-cv.pdf", "doc_type": "cv",
            "is_primary": False, "inserted": False,
        }
        result, mock_db, enforce = self._call(
            existing=None, get_or_create_result=race_result, filename="loser-cv.pdf",
        )
        enforce.assert_called_once()  # pre-check missed it, so quota still ran
        assert result["duplicate"] is True
        assert result["id"] == "winner-uuid"
        assert result["filename"] == "WINNER-cv.pdf"  # canonical, not "loser-cv.pdf"

    def test_response_shape_backward_compatible(self):
        insert_result = {
            "id": "new-doc-id", "filename": "cv.pdf", "doc_type": "cv",
            "is_primary": False, "inserted": True,
        }
        result, _, _ = self._call(existing=None, get_or_create_result=insert_result)
        assert {"ok", "id", "filename", "doc_type", "duplicate"}.issubset(result.keys())

    def test_primary_cv_reupload_preserves_primary(self):
        """Re-uploading the current primary CV returns it unchanged (no save, no quota)."""
        existing = {"id": "primary-uuid", "filename": "cv.pdf", "doc_type": "cv", "is_primary": True}
        result, mock_db, enforce = self._call(existing=existing, doc_type="cv")
        assert result["id"] == "primary-uuid"
        assert result["duplicate"] is True
        mock_db.get_or_create_user_document.assert_not_called()  # primary flag untouched
        enforce.assert_not_called()


# ── Route-level: PATCH /api/v1/user/files/{id} doc_type rename conflict ──────

@pytest.mark.skipif(not _FASTAPI_OK, reason="fastapi not installed in this environment")
class TestUpdateFileRouteConflict:
    def _call(self, *, side_effect):
        from src.api.routers import files as files_mod

        mock_db = MagicMock()
        mock_db.available = True
        mock_db.update_user_document.side_effect = side_effect

        req = MagicMock()
        body = files_mod.FileUpdateRequest(doc_type="cv")
        with patch.object(files_mod, "_db", mock_db), \
             patch.object(files_mod, "get_current_user", return_value={"email": "u@test.com", "role": "user"}):
            return files_mod.update_file("doc-1", body, req)

    def test_doc_type_rename_collision_returns_409_not_500(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            self._call(side_effect=DocumentConflictError("duplicate content in target doc_type"))
        assert exc_info.value.status_code == 409

    def test_normal_rename_still_succeeds(self):
        result = self._call(side_effect=None)
        # side_effect=None makes update_user_document return whatever the
        # MagicMock default is (truthy) rather than raising.
        assert result["ok"] is True

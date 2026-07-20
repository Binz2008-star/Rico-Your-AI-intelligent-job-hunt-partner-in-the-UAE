"""
Regression tests for the saved-search upsert fallback (#1249 step-4 finding).

Live defect (confirmed against production schema): ``rico_saved_searches``
has no ``UNIQUE (user_id, query)`` constraint, so the ``ON CONFLICT
(user_id, query)`` upsert raises — and because the old code had no savepoint,
that error ABORTED the whole transaction, making the "simple insert" fallback
fail too ("current transaction is aborted"). Net effect: every saved-search
write returned None ("لم أستطع حفظ البحث المجدول" in chat, and the generic
saved-search POST endpoint silently failing) for ALL users.

Fix under test: the upsert attempt runs inside a SAVEPOINT; on failure the
code rolls back to the savepoint and performs a manual UPDATE-then-INSERT that
preserves the same canonical (user_id, query) identity without the constraint.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.repositories import profile_repo


class AbortedTransactionError(Exception):
    """Stand-in for psycopg2's 'current transaction is aborted' behaviour."""


class FakeCursor:
    """Cursor that raises on ON CONFLICT (no unique constraint) and, like real
    PostgreSQL, refuses every later statement until ROLLBACK TO SAVEPOINT."""

    def __init__(self, *, existing_row_id=None, constraint_exists=False):
        self.executed: list[str] = []
        self._last_result = None
        self._aborted = False
        self._existing_row_id = existing_row_id
        self._constraint_exists = constraint_exists

    # context-manager protocol (used via conn.cursor())
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        stmt = " ".join(sql.split())
        if self._aborted and "ROLLBACK TO SAVEPOINT" not in stmt:
            raise AbortedTransactionError("current transaction is aborted")
        self.executed.append(stmt)

        if "ROLLBACK TO SAVEPOINT" in stmt:
            self._aborted = False
            self._last_result = None
        elif "SAVEPOINT" in stmt:
            self._last_result = None
        elif "ON CONFLICT" in stmt:
            if not self._constraint_exists:
                self._aborted = True
                raise Exception(
                    "no unique or exclusion constraint matching the ON CONFLICT specification"
                )
            self._last_result = {"id": self._existing_row_id or "new-id"}
        elif stmt.startswith("UPDATE rico_saved_searches SET filters"):
            self._last_result = (
                {"id": self._existing_row_id} if self._existing_row_id else None
            )
        elif stmt.startswith("INSERT INTO rico_saved_searches"):
            self._last_result = {"id": "inserted-id"}
        else:
            self._last_result = None

    def fetchone(self):
        return self._last_result


def _run_save_search(cursor: FakeCursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor

    @contextmanager
    def fake_transaction():
        yield conn

    db = MagicMock()
    db.upsert_user.return_value = {"id": "db-user-1"}

    with patch.object(profile_repo, "_db", return_value=db), \
         patch.object(profile_repo, "_db_transaction", fake_transaction):
        return profile_repo.save_search("alice@rico.ai", "Scheduled daily job search — Dubai — 10000+ AED",
                                        {"schedule": {"enabled": True}})


class TestSavedSearchUpsertFallback:
    def test_missing_constraint_existing_row_updates_in_place(self):
        """ON CONFLICT raises → savepoint rollback → UPDATE hits the existing
        canonical row → its id returned, no duplicate INSERT."""
        cur = FakeCursor(existing_row_id="row-7", constraint_exists=False)
        assert _run_save_search(cur) == "row-7"
        joined = "\n".join(cur.executed)
        assert "SAVEPOINT saved_search_upsert" in joined
        assert "ROLLBACK TO SAVEPOINT saved_search_upsert" in joined
        plain_inserts = [s for s in cur.executed
                         if s.startswith("INSERT INTO rico_saved_searches (user_id")
                         and "ON CONFLICT" not in s]
        assert plain_inserts == []  # no duplicate row created

    def test_missing_constraint_new_row_inserts_once(self):
        """ON CONFLICT raises → rollback → UPDATE finds nothing → plain INSERT
        succeeds (the transaction is still usable — the actual bug)."""
        cur = FakeCursor(existing_row_id=None, constraint_exists=False)
        assert _run_save_search(cur) == "inserted-id"
        inserts = [s for s in cur.executed
                   if s.startswith("INSERT INTO rico_saved_searches (user_id")
                   and "ON CONFLICT" not in s]
        assert len(inserts) == 1

    def test_old_behaviour_would_have_failed(self):
        """Sanity-pin of the defect model: without ROLLBACK TO SAVEPOINT the
        fake transaction (like PostgreSQL) rejects any further statement."""
        cur = FakeCursor(constraint_exists=False)
        try:
            cur.execute("INSERT ... ON CONFLICT (user_id, query) ...")
        except Exception:
            pass
        try:
            cur.execute("INSERT INTO rico_saved_searches (user_id, query, filters) VALUES (1,2,3)")
            raised = False
        except AbortedTransactionError:
            raised = True
        assert raised, "aborted transaction must reject the naive fallback"

    def test_constraint_present_fast_path_unchanged(self):
        """When the unique constraint exists the atomic upsert wins and no
        fallback SQL runs at all."""
        cur = FakeCursor(existing_row_id="row-3", constraint_exists=True)
        assert _run_save_search(cur) == "row-3"
        joined = "\n".join(cur.executed)
        assert "ROLLBACK TO SAVEPOINT" not in joined
        assert not any(s.startswith("UPDATE rico_saved_searches SET filters") for s in cur.executed)

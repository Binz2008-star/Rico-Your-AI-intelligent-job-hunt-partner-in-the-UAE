"""
tests/integration/test_user_documents_postgres.py

Real-PostgreSQL integration tests for the single-primary-CV invariant (#960).

Why this file exists: the unit tests in tests/test_user_documents_dedup.py
mock the cursor/transaction entirely, so they can verify *what SQL gets sent*
but cannot verify how a real PostgreSQL server actually enforces the
migration-037 partial unique index `uq_user_documents_one_primary_per_type`
mid-transaction, or how `pg_advisory_xact_lock` actually serializes two
concurrent connections. A mocked cursor happily lets you INSERT a second
is_primary=TRUE row with no error; real Postgres will raise a unique
violation the instant that statement runs, because the index is not
deferrable. This file runs the same code paths (`RicoDB.set_primary_document`,
`RicoDB.save_user_document`, `RicoDB.get_or_create_user_document`) against a
real, disposable Postgres database with migration 037 actually applied.

Requires a real Postgres reachable via RICO_TEST_DATABASE_URL (NOT the shared
DATABASE_URL — kept separate so the fake-DB unit-test job never accidentally
tries to run these). Skips cleanly when that variable isn't set, e.g. on a
laptop with no local Postgres. In CI this is wired to a postgres service
container in .github/workflows/qa-tests.yml (job: postgres-integration).

Scenarios covered:
  * existing primary A -> switch to B succeeds; A becomes false, B becomes true
  * invalid/foreign doc_id leaves A primary untouched
  * inserting a new primary while A exists succeeds atomically (both via
    save_user_document and get_or_create_user_document)
  * two concurrent primary-selection calls (real threads, real connections)
    result in exactly one primary, never zero, never two
  * a failure partway through a hand-rolled primary-swap transaction rolls
    back and restores the previous primary (proves the underlying Postgres
    rollback semantics the RicoDB methods rely on)
  * two concurrent NON-primary get_or_create_user_document calls with the
    same content_hash — the gap the content-lock fix closes: previously only
    is_primary=True calls were locked, so two identical ordinary uploads
    could both miss the pre-check and race the INSERT, and the loser raised
    RuntimeError -> a 500 for a normal double-click/retry
  * the same race at the route level (POST /api/v1/user/files), real DB,
    real threads — never 500, exactly one duplicate=false + one duplicate=true
  * a primary and a non-primary get_or_create_user_document call racing on
    the SAME content_hash — exactly one document row, exactly one valid
    primary state, never zero primaries regardless of which call wins
"""
from __future__ import annotations

import asyncio
import os
import threading
import uuid
from unittest.mock import MagicMock, patch

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

from src.rico_db import RicoDB

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres integration tests skipped. Set RICO_TEST_DATABASE_URL "
           "to a disposable Postgres to run these.",
)

_MIGRATION_037_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "migrations", "037_user_documents_content_hash.sql"
)


@pytest.fixture(scope="module")
def db() -> RicoDB:
    """One RicoDB against the real test database, schema + migration 037 applied once."""
    instance = RicoDB(database_url=TEST_DATABASE_URL)
    conn = instance.connect()  # runs _ensure_schema (base tables, no 037 content)
    try:
        with open(_MIGRATION_037_PATH) as f:
            migration_sql = f.read()
        with conn.cursor() as cur:
            cur.execute(migration_sql)
        conn.commit()
    finally:
        conn.close()
    return instance


@pytest.fixture(autouse=True)
def _clean_table(db: RicoDB):
    """Isolate each test — real Postgres, so state persists across tests otherwise."""
    yield
    conn = db.connect(ensure_schema=False)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_documents")
        conn.commit()
    finally:
        conn.close()


def _user_id() -> str:
    return f"pg-integration-{uuid.uuid4()}@rico.test"


def _primary_row_count(db: RicoDB, user_id: str, doc_type: str = "cv") -> int:
    conn = db.connect(ensure_schema=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM user_documents "
                "WHERE user_id = %s AND doc_type = %s AND is_primary = TRUE",
                (user_id, doc_type),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return int(row["cnt"] if isinstance(row, dict) else row[0])


def _is_primary(db: RicoDB, doc_id: str) -> bool:
    conn = db.connect(ensure_schema=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT is_primary FROM user_documents WHERE id = %s", (doc_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    return bool(row["is_primary"] if isinstance(row, dict) else row[0])


class TestSetPrimaryDocumentRealPostgres:
    def test_switch_primary_from_a_to_b(self, db: RicoDB):
        user_id = _user_id()
        doc_a = db.save_user_document(
            user_id=user_id, filename="a.pdf", original_filename="a.pdf",
            doc_type="cv", is_primary=True,
        )
        doc_b = db.save_user_document(
            user_id=user_id, filename="b.pdf", original_filename="b.pdf",
            doc_type="cv", is_primary=False,
        )
        assert _is_primary(db, doc_a) is True
        assert _is_primary(db, doc_b) is False

        ok = db.set_primary_document(user_id, doc_b)

        assert ok is True
        assert _is_primary(db, doc_a) is False
        assert _is_primary(db, doc_b) is True
        assert _primary_row_count(db, user_id) == 1

    def test_invalid_target_leaves_existing_primary_untouched(self, db: RicoDB):
        user_id = _user_id()
        doc_a = db.save_user_document(
            user_id=user_id, filename="a.pdf", original_filename="a.pdf",
            doc_type="cv", is_primary=True,
        )

        ok = db.set_primary_document(user_id, "00000000-0000-0000-0000-000000000000")

        assert ok is False
        assert _is_primary(db, doc_a) is True
        assert _primary_row_count(db, user_id) == 1

    def test_insert_new_primary_while_one_exists_is_atomic(self, db: RicoDB):
        """This is the exact scenario the reviewed bug broke: inserting an
        is_primary=TRUE row via get_or_create_user_document while another
        primary already exists must not violate
        uq_user_documents_one_primary_per_type."""
        user_id = _user_id()
        doc_a = db.save_user_document(
            user_id=user_id, filename="a.pdf", original_filename="a.pdf",
            doc_type="cv", is_primary=True,
        )

        result = db.get_or_create_user_document(
            user_id=user_id, filename="b.pdf", original_filename="b.pdf",
            doc_type="cv", content_hash="hash-b", is_primary=True,
        )

        assert result["inserted"] is True
        assert _is_primary(db, doc_a) is False
        assert _is_primary(db, result["id"]) is True
        assert _primary_row_count(db, user_id) == 1

    def test_save_user_document_insert_new_primary_while_one_exists_is_atomic(self, db: RicoDB):
        user_id = _user_id()
        doc_a = db.save_user_document(
            user_id=user_id, filename="a.pdf", original_filename="a.pdf",
            doc_type="cv", is_primary=True,
        )

        doc_b = db.save_user_document(
            user_id=user_id, filename="b.pdf", original_filename="b.pdf",
            doc_type="cv", is_primary=True,
        )

        assert _is_primary(db, doc_a) is False
        assert _is_primary(db, doc_b) is True
        assert _primary_row_count(db, user_id) == 1


class TestConcurrentPrimarySelection:
    def test_two_concurrent_set_primary_calls_result_in_exactly_one_primary(self, db: RicoDB):
        user_id = _user_id()
        doc_a = db.save_user_document(
            user_id=user_id, filename="a.pdf", original_filename="a.pdf",
            doc_type="cv", is_primary=True,
        )
        doc_b = db.save_user_document(
            user_id=user_id, filename="b.pdf", original_filename="b.pdf",
            doc_type="cv", is_primary=False,
        )
        doc_c = db.save_user_document(
            user_id=user_id, filename="c.pdf", original_filename="c.pdf",
            doc_type="cv", is_primary=False,
        )

        # Two independent RicoDB instances (=> independent psycopg2
        # connections) racing to make a DIFFERENT document primary for the
        # SAME user at (as close to) the same time.
        db_thread_1 = RicoDB(database_url=TEST_DATABASE_URL)
        db_thread_2 = RicoDB(database_url=TEST_DATABASE_URL)
        barrier = threading.Barrier(2)
        results: dict[str, bool] = {}
        errors: list[BaseException] = []

        def _run(db_instance: RicoDB, doc_id: str, key: str) -> None:
            try:
                barrier.wait(timeout=5)
                results[key] = db_instance.set_primary_document(user_id, doc_id)
            except BaseException as exc:  # noqa: BLE001 — surface any thread failure
                errors.append(exc)

        t1 = threading.Thread(target=_run, args=(db_thread_1, doc_b, "b"))
        t2 = threading.Thread(target=_run, args=(db_thread_2, doc_c, "c"))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"concurrent set_primary_document raised: {errors}"
        # The advisory lock serializes them — both calls target real,
        # existing documents, so both succeed (just one after the other).
        assert results == {"b": True, "c": True}
        # Whichever ran last wins, but there is EXACTLY one primary — never
        # zero (both instantaneously cleared without setting) and never two
        # (both inserted/set before the other's clear ran).
        assert _primary_row_count(db, user_id) == 1
        primaries = [
            doc_id for doc_id in (doc_a, doc_b, doc_c) if _is_primary(db, doc_id)
        ]
        assert len(primaries) == 1
        assert primaries[0] in (doc_b, doc_c)  # the original primary A lost the flag


class TestTransactionFailureRestoresPreviousPrimary:
    def test_failure_after_clearing_old_primary_rolls_back_to_original_state(self, db: RicoDB):
        """Hand-rolled version of the same clear-then-set transaction, with a
        forced failure injected between the two steps, to prove the
        underlying Postgres rollback semantics RicoDB's methods rely on:
        if the final write fails, the whole transaction — including the
        earlier clear — is undone, and the original primary survives."""
        user_id = _user_id()
        doc_a = db.save_user_document(
            user_id=user_id, filename="a.pdf", original_filename="a.pdf",
            doc_type="cv", is_primary=True,
        )

        conn = psycopg2.connect(TEST_DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"test:{user_id}:cv",))
                cur.execute(
                    "UPDATE user_documents SET is_primary = FALSE WHERE user_id = %s AND doc_type = 'cv'",
                    (user_id,),
                )
                # Forced failure: doc_type has a NOT NULL constraint, so this
                # UPDATE targeting a nonexistent id with a bad column raises.
                with pytest.raises(psycopg2.Error):
                    cur.execute(
                        "UPDATE user_documents SET doc_type = NULL WHERE id = %s",
                        (doc_a,),
                    )
            conn.rollback()
        finally:
            conn.close()

        # The clear from the failed transaction was rolled back entirely.
        assert _is_primary(db, doc_a) is True
        assert _primary_row_count(db, user_id) == 1


def _doc_count_for_hash(user_id: str, doc_type: str, content_hash: str) -> int:
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM user_documents WHERE user_id = %s AND doc_type = %s AND content_hash = %s",
                (user_id, doc_type, content_hash),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return int(row[0])


class TestConcurrentNonPrimaryGetOrCreate:
    """The exact gap flagged in review: an ordinary (is_primary=False)
    upload had NO advisory lock at all before this fix, so two identical
    concurrent uploads could both miss the pre-check and race the INSERT —
    the loser's ON CONFLICT DO NOTHING returned no row, and the old code
    raised RuntimeError instead of returning duplicate=true."""

    def test_two_concurrent_non_primary_uploads_same_hash(self, db: RicoDB):
        user_id = _user_id()
        content_hash = "shared-content-hash-nonprimary"

        db_thread_1 = RicoDB(database_url=TEST_DATABASE_URL)
        db_thread_2 = RicoDB(database_url=TEST_DATABASE_URL)
        barrier = threading.Barrier(2)
        results: dict[str, dict] = {}
        errors: list[BaseException] = []

        def _run(db_instance: RicoDB, key: str) -> None:
            try:
                barrier.wait(timeout=5)
                results[key] = db_instance.get_or_create_user_document(
                    user_id=user_id, filename=f"{key}.pdf", original_filename=f"{key}.pdf",
                    doc_type="cv", content_hash=content_hash, is_primary=False,
                )
            except BaseException as exc:  # noqa: BLE001 — surface any thread failure
                errors.append(exc)

        t1 = threading.Thread(target=_run, args=(db_thread_1, "one"))
        t2 = threading.Thread(target=_run, args=(db_thread_2, "two"))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"concurrent get_or_create_user_document raised: {errors}"
        inserted_flags = sorted(r["inserted"] for r in results.values())
        assert inserted_flags == [False, True]  # exactly one of each, never both True
        # Both calls must agree on the SAME row id (the winner's).
        assert results["one"]["id"] == results["two"]["id"]
        assert _doc_count_for_hash(user_id, "cv", content_hash) == 1


class TestConcurrentRouteUpload:
    """Same race, but through the actual POST /api/v1/user/files handler —
    real DB, real threads, quota/auth mocked out (that plumbing is already
    covered elsewhere; this test is specifically about the DB race)."""

    class _FakeUpload:
        """Models the real UploadFile read API: read(size) returns successive
        chunks and b"" at EOF (required by the #1080 bounded reader)."""

        def __init__(self, data: bytes, filename: str = "cv.pdf"):
            self._data = data
            self._pos = 0
            self.filename = filename
            self.size = None

        async def read(self, size: int = -1) -> bytes:
            if self._pos >= len(self._data):
                return b""
            if size is None or size < 0:
                chunk = self._data[self._pos:]
            else:
                chunk = self._data[self._pos:self._pos + size]
            self._pos += len(chunk)
            return chunk

        async def close(self) -> None:
            return None

    def test_concurrent_upload_route_never_500s_on_duplicate_race(self, db: RicoDB):
        from src.api.routers import files as files_mod

        user_id = _user_id()
        pdf_bytes = b"%PDF-1.4\n%route-level concurrency race bytes\n"

        results: dict[str, dict] = {}
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def _run(key: str) -> None:
            try:
                barrier.wait(timeout=5)
                raw = getattr(files_mod.upload_file, "__wrapped__", files_mod.upload_file)
                req = MagicMock()
                with patch.object(files_mod, "_db", db), \
                     patch.object(files_mod, "enforce_document_quota", MagicMock()), \
                     patch.object(files_mod, "get_current_user", return_value={"email": user_id, "role": "user"}):
                    results[key] = asyncio.run(
                        raw(req, file=self._FakeUpload(pdf_bytes, filename=f"{key}.pdf"), doc_type="cv")
                    )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=_run, args=("one",))
        t2 = threading.Thread(target=_run, args=("two",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"concurrent upload route raised (would surface as a 500): {errors}"
        duplicate_flags = sorted(r["duplicate"] for r in results.values())
        assert duplicate_flags == [False, True]
        assert results["one"]["id"] == results["two"]["id"]


class TestConcurrentPrimaryAndNonPrimaryGetOrCreate:
    """A primary and a non-primary get_or_create_user_document call racing
    on the SAME content_hash — regardless of which one wins the lock, there
    must be exactly one document row and exactly one valid primary state,
    never zero primaries."""

    def test_concurrent_primary_and_nonprimary_same_hash(self, db: RicoDB):
        user_id = _user_id()
        content_hash = "shared-content-hash-mixed-primary"

        db_thread_1 = RicoDB(database_url=TEST_DATABASE_URL)
        db_thread_2 = RicoDB(database_url=TEST_DATABASE_URL)
        barrier = threading.Barrier(2)
        results: dict[str, dict] = {}
        errors: list[BaseException] = []

        def _run(db_instance: RicoDB, key: str, is_primary: bool) -> None:
            try:
                barrier.wait(timeout=5)
                results[key] = db_instance.get_or_create_user_document(
                    user_id=user_id, filename=f"{key}.pdf", original_filename=f"{key}.pdf",
                    doc_type="cv", content_hash=content_hash, is_primary=is_primary,
                )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=_run, args=(db_thread_1, "primary", True))
        t2 = threading.Thread(target=_run, args=(db_thread_2, "nonprimary", False))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"concurrent primary/non-primary get_or_create raised: {errors}"
        # Exactly one document row for this hash, regardless of who won.
        assert _doc_count_for_hash(user_id, "cv", content_hash) == 1
        assert results["primary"]["id"] == results["nonprimary"]["id"]
        # The is_primary=True request must be honored regardless of whether
        # it was the one that actually inserted the row, or found the other
        # thread's row already there — never a silently-dropped primary
        # request, never zero primaries.
        assert results["primary"]["is_primary"] is True
        assert _primary_row_count(db, user_id) == 1

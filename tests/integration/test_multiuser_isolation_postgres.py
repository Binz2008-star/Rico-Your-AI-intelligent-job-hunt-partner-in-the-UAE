# -*- coding: utf-8 -*-
"""Real-PostgreSQL cross-user isolation invariants, driven by the synthetic persona matrix.

Why this file exists: `#1437` landed `tests/factory/personas.py` and
`tests/factory/isolation.py` — a deterministic persona matrix plus four
deliberate *collision* builders (same filename, same CV byte-hash, similar
display name, same target role). Nothing exercises them against the ownership
layer: `tests/test_persona_factory.py` tests the factory's own output, and the
existing isolation suites (`test_user_isolation.py`, `test_jwt_user_isolation.py`,
`test_identity_ownership_boundaries.py`) assert route- and token-level scoping
with mocked storage. So the question these collisions exist to answer —
*does a shared filename or a shared content hash merge two users' ownership in
a real database?* — has never actually been asked of Postgres.

It has to be asked of Postgres specifically. Migration 037 scopes both unique
indexes per user:

    uq_user_documents_user_type_hash        (user_id, doc_type, content_hash)
                                            WHERE content_hash IS NOT NULL
    uq_user_documents_one_primary_per_type  (user_id, doc_type)
                                            WHERE is_primary = TRUE

A mocked cursor cannot tell a per-user index from a global one — both accept
every INSERT. Only a real server proves that two different users may each hold
byte-identical CVs, and that each may independently hold a primary CV. If
either index were ever narrowed to `(doc_type, content_hash)` or `(doc_type)`,
every test here would fail and every mocked test would still pass.

Isolation invariants asserted (Journey E in the reliability program), all P0:

  * two users may hold byte-identical CV content — the hash does not merge
    ownership, and each row is owned by its own uploader
  * two users may hold the identical filename with different content
  * neither user's listing ever contains the other's document
  * each user may independently hold their own primary CV
  * A cannot delete B's document by id, and the failed attempt leaves B intact
  * A cannot promote B's document to primary
  * two users writing byte-identical content concurrently (real threads, real
    connections) both succeed, with no ownership crossover

Positive control — these assertions are not vacuous, and the two ways of
breaking the per-user index fail differently. Both were run against a
disposable Postgres 16:

  * baseline, unmodified                          -> 9 passed
  * per-user index REPLACED by (doc_type, content_hash)
        -> 9 failed, `InvalidColumnReference: there is no unique or exclusion
           constraint matching the ON CONFLICT specification`. A UniqueViolation
           is impossible here: with the per-user index gone, the writer's
           ON CONFLICT (user_id, doc_type, content_hash) target can no longer
           be inferred, so the statement fails before any row is compared.
  * global index ADDED ALONGSIDE the per-user one
        -> 5 failed / 4 passed, `UniqueViolation` on
           `Key (doc_type, content_hash)`. The survivors are exactly the tests
           that do not depend on cross-user hash uniqueness.

Recording both matters: an earlier revision of this file described the second
result as belonging to the first experiment. It does not.

Requires a real Postgres reachable via RICO_TEST_DATABASE_URL (NOT the shared
DATABASE_URL — kept separate so the fake-DB unit-test job never runs these).
Skips cleanly when unset. In CI this is wired to the postgres service container
in .github/workflows/qa-tests.yml (job: postgres-integration).

Synthetic data only: every identity comes from the persona factory, whose
addresses live under the reserved `.invalid` TLD and can never route.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

import pytest

try:
    import psycopg2  # noqa: F401
except Exception:  # pragma: no cover - environment without the driver
    psycopg2 = None  # type: ignore[assignment]

from src.rico_db import RicoDB
from tests.factory.isolation import (
    build_same_cv_hash_pair,
    build_same_filename_pair,
    build_same_target_role_pair,
)

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

#: Fixed run id: the factory is deterministic, so the personas, their
#: fingerprints and the collision content are identical on every run. A random
#: id would make a failure impossible to reproduce from the report alone.
RUN_ID = "multiuser-isolation-postgres"


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


def _rows_for(db: RicoDB, user_id: str) -> List[Dict[str, Any]]:
    return db.list_user_documents(user_id)


def _owner_of(db: RicoDB, doc_id: str) -> Optional[str]:
    """Read the ownership column directly — never through a user-scoped helper.

    A user-scoped read would filter by the id we are trying to verify, so it
    could never catch an ownership crossover; this asks the table who owns the
    row without telling it the answer we expect.
    """
    conn = db.connect(ensure_schema=False)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM user_documents WHERE id = %s", (doc_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return row["user_id"] if isinstance(row, dict) else row[0]


def _store(db: RicoDB, cv, *, is_primary: bool = False) -> Dict[str, Any]:
    """Persist one CvFixture through the real dedup-aware write path."""
    return db.get_or_create_user_document(
        user_id=cv.persona.user_id,
        filename=cv.filename,
        original_filename=cv.filename,
        content_hash=cv.content_hash,
        doc_type="cv",
        file_size=len(cv.content.encode("utf-8")),
        is_primary=is_primary,
    )


class TestIdenticalContentDoesNotMergeOwnership:
    """The same CV bytes uploaded by two different users stay two owned rows."""

    def test_both_users_can_store_byte_identical_content(self, db: RicoDB):
        pair = build_same_cv_hash_pair(RUN_ID)
        assert pair.cv_a.content_hash == pair.cv_b.content_hash, "fixture precondition"
        assert pair.user_a.user_id != pair.user_b.user_id

        result_a = _store(db, pair.cv_a)
        result_b = _store(db, pair.cv_b)

        # Both are genuine inserts. If the hash index were not user-scoped,
        # B's write does NOT quietly resolve to A's row — it fails outright:
        # UniqueViolation when a global index sits alongside the per-user one,
        # InvalidColumnReference when it replaces it. The isolation failure
        # surfaces as a refused write, not as a silent handover.
        assert result_a["inserted"] is True
        assert result_b["inserted"] is True
        assert result_a["id"] != result_b["id"]

        assert _owner_of(db, result_a["id"]) == pair.user_a.user_id
        assert _owner_of(db, result_b["id"]) == pair.user_b.user_id

    def test_neither_listing_contains_the_other_users_document(self, db: RicoDB):
        pair = build_same_cv_hash_pair(RUN_ID)
        result_a = _store(db, pair.cv_a)
        result_b = _store(db, pair.cv_b)

        ids_a = {r["id"] for r in _rows_for(db, pair.user_a.user_id)}
        ids_b = {r["id"] for r in _rows_for(db, pair.user_b.user_id)}

        assert ids_a == {result_a["id"]}
        assert ids_b == {result_b["id"]}
        assert ids_a.isdisjoint(ids_b)

    def test_same_user_reuploading_identical_content_is_deduped(self, db: RicoDB):
        """The per-user half of the same index: a user's own re-upload is NOT a new row.

        Asserted here so a regression that widened the index to make the
        cross-user test pass would be caught by this one failing.
        """
        pair = build_same_cv_hash_pair(RUN_ID)
        first = _store(db, pair.cv_a)
        second = _store(db, pair.cv_a)

        assert first["inserted"] is True
        assert second["inserted"] is False
        assert second["id"] == first["id"]
        assert len(_rows_for(db, pair.user_a.user_id)) == 1


class TestIdenticalFilenameDoesNotCrossUsers:
    """Two users may use the same filename; lookup by name must not leak."""

    def test_both_users_store_the_same_filename(self, db: RicoDB):
        pair = build_same_filename_pair(RUN_ID)
        assert pair.cv_a.filename == pair.cv_b.filename, "fixture precondition"
        assert pair.cv_a.content_hash != pair.cv_b.content_hash, "fixture precondition"

        result_a = _store(db, pair.cv_a)
        result_b = _store(db, pair.cv_b)

        assert result_a["inserted"] is True
        assert result_b["inserted"] is True
        assert _owner_of(db, result_a["id"]) == pair.user_a.user_id
        assert _owner_of(db, result_b["id"]) == pair.user_b.user_id

    # NOTE: there is deliberately no "filename lookup is user-scoped" test here.
    # `rico_db.py` exposes no lookup-by-filename path — a test that filtered
    # `list_user_documents()` output in Python would assert nothing the listing
    # test above does not already cover, while reading as though a real lookup
    # had been exercised. If a by-filename resolver is ever added, that is the
    # point to test it.


class TestPrimaryDocumentIsPerUser:
    def test_each_user_holds_their_own_primary_simultaneously(self, db: RicoDB):
        """`uq_user_documents_one_primary_per_type` is per-user, not global."""
        pair = build_same_target_role_pair(RUN_ID)
        result_a = _store(db, pair.cv_a, is_primary=True)
        result_b = _store(db, pair.cv_b, is_primary=True)

        rows_a = _rows_for(db, pair.user_a.user_id)
        rows_b = _rows_for(db, pair.user_b.user_id)

        assert [r["id"] for r in rows_a if r["is_primary"]] == [result_a["id"]]
        assert [r["id"] for r in rows_b if r["is_primary"]] == [result_b["id"]]

    def test_user_a_cannot_promote_user_bs_document(self, db: RicoDB):
        pair = build_same_target_role_pair(RUN_ID)
        _store(db, pair.cv_a, is_primary=True)
        result_b = _store(db, pair.cv_b, is_primary=False)

        promoted = db.set_primary_document(pair.user_a.user_id, result_b["id"])

        assert promoted is False, "a foreign doc_id must not be promotable"
        assert _owner_of(db, result_b["id"]) == pair.user_b.user_id
        rows_b = _rows_for(db, pair.user_b.user_id)
        assert [r["is_primary"] for r in rows_b] == [False]


class TestDeletionIsolation:
    def test_user_a_cannot_delete_user_bs_document(self, db: RicoDB):
        pair = build_same_cv_hash_pair(RUN_ID)
        _store(db, pair.cv_a)
        result_b = _store(db, pair.cv_b)

        deleted = db.delete_user_document(pair.user_a.user_id, result_b["id"])

        assert deleted is False
        assert _owner_of(db, result_b["id"]) == pair.user_b.user_id
        assert len(_rows_for(db, pair.user_b.user_id)) == 1

    def test_deleting_own_document_leaves_the_other_user_intact(self, db: RicoDB):
        pair = build_same_cv_hash_pair(RUN_ID)
        result_a = _store(db, pair.cv_a)
        result_b = _store(db, pair.cv_b)

        assert db.delete_user_document(pair.user_a.user_id, result_a["id"]) is True

        assert _rows_for(db, pair.user_a.user_id) == []
        assert [r["id"] for r in _rows_for(db, pair.user_b.user_id)] == [result_b["id"]]
        assert _owner_of(db, result_b["id"]) == pair.user_b.user_id


class TestConcurrentIdenticalUploadsAcrossUsers:
    def test_two_users_writing_identical_bytes_concurrently_do_not_cross(self, db: RicoDB):
        """Real threads, real connections: contention does not cross ownership.

        Two users commit byte-identical content at the same moment and each
        ends up owning exactly their own row.

        What this does NOT prove, stated so nobody reads more into it: it does
        not establish that the advisory-lock key in
        `get_or_create_user_document` is user-scoped. Dropping `user_id` from
        that key leaves every assertion here passing, because the pre-check
        SELECT and the unique index are *already* user-scoped — a shared lock
        key would cost throughput, not correctness. This test covers the
        correctness half only.
        """
        pair = build_same_cv_hash_pair(RUN_ID)
        results: Dict[str, Dict[str, Any]] = {}
        errors: List[BaseException] = []
        barrier = threading.Barrier(2)

        def worker(cv) -> None:
            try:
                barrier.wait(timeout=10)
                results[cv.persona.user_id] = _store(db, cv)
            except BaseException as exc:  # noqa: BLE001 - surfaced in the assertion
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(cv,)) for cv in (pair.cv_a, pair.cv_b)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"concurrent identical-content writes raised: {errors!r}"
        assert set(results) == {pair.user_a.user_id, pair.user_b.user_id}

        result_a = results[pair.user_a.user_id]
        result_b = results[pair.user_b.user_id]
        assert result_a["inserted"] is True
        assert result_b["inserted"] is True
        assert result_a["id"] != result_b["id"]
        assert _owner_of(db, result_a["id"]) == pair.user_a.user_id
        assert _owner_of(db, result_b["id"]) == pair.user_b.user_id


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))

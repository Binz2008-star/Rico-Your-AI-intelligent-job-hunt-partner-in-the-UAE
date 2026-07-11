"""
tests/integration/test_cv_upload_artifacts_postgres.py

Real-PostgreSQL integration tests for the CV upload artifact (#963 / #975).

Why this file exists (PR #975 blocker 3): the unit tests in
tests/test_963_onboarding_cv_persistence.py mock the cursor/connection, so they
verify *what SQL gets sent* but cannot prove that migration 038 actually
creates a working table, that create/resolve round-trip against a real server,
that `expires_at`-based freshness really filters, or that the opportunistic
purge really DELETEs expired rows. onboarding-CV persistence depends on this
artifact working end-to-end, so it must be proven against a real Postgres, not
just asserted at the mock layer.

This applies migration 038 to a disposable Postgres and exercises the real
repo functions (create_cv_upload_artifact / resolve_cv_upload_artifact /
purge_expired_cv_upload_artifacts) by pointing src.db.get_db_connection at the
test database.

Requires a real Postgres reachable via RICO_TEST_DATABASE_URL (NOT the shared
DATABASE_URL). Skips cleanly when unset (e.g. a laptop with no local Postgres).
In CI this is wired to the postgres service container in
.github/workflows/qa-tests.yml (job: postgres-integration).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

from src.repositories.cv_upload_artifact_repo import (
    create_cv_upload_artifact,
    purge_expired_cv_upload_artifacts,
    resolve_cv_upload_artifact,
)

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres integration tests skipped.",
)

_MIGRATION_038_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "migrations", "038_cv_upload_artifacts.sql"
)


@pytest.fixture(scope="module", autouse=True)
def _apply_migration_038():
    """Apply migration 038 once against the real test database."""
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with open(_MIGRATION_038_PATH) as f:
            migration_sql = f.read()
        with conn.cursor() as cur:
            cur.execute(migration_sql)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _route_repo_to_test_db():
    """Point the repo's src.db.get_db_connection at the test database, and
    isolate each test by truncating the table afterward."""
    def _factory():
        return psycopg2.connect(TEST_DATABASE_URL)

    with patch("src.db.get_db_connection", side_effect=_factory):
        yield
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cv_upload_artifacts")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _raw():
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def _count() -> int:
    with _raw() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cv_upload_artifacts")
            return int(cur.fetchone()[0])


def _insert_expired(user_id: str, filename: str, content_hash: str) -> None:
    """Seed an ALREADY-EXPIRED row via raw SQL. Must bypass the public
    create_cv_upload_artifact(), whose own inline purge would immediately
    delete a row inserted already-expired (proving, incidentally, that the
    opportunistic cleanup runs)."""
    with _raw() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cv_upload_artifacts
                    (user_id, filename, doc_type, content_hash, file_size, cv_text, expires_at)
                VALUES (%s, %s, 'cv', %s, 10, 'x', NOW() - INTERVAL '1 hour')
                """,
                (user_id, filename, content_hash),
            )
        conn.commit()


# ── migration 038 objects exist ──────────────────────────────────────────────

def test_migration_038_created_table_and_index():
    with _raw() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.cv_upload_artifacts')")
            assert cur.fetchone()[0] is not None
            cur.execute("SELECT to_regclass('public.idx_cv_upload_artifacts_user_expires')")
            assert cur.fetchone()[0] is not None


# ── create + resolve round trip ──────────────────────────────────────────────

def test_create_then_resolve_round_trip():
    upload_id = create_cv_upload_artifact(
        "alice@rico.test",
        filename="jane_cv.pdf",
        doc_type="cv",
        content_hash="a" * 64,
        file_size=2048,
        cv_text="Jane Doe — full parsed CV text",
    )
    assert upload_id  # a real UUID string
    artifact = resolve_cv_upload_artifact("alice@rico.test", upload_id)
    assert artifact == {
        "filename": "jane_cv.pdf",
        "doc_type": "cv",
        "content_hash": "a" * 64,
        "file_size": 2048,
        "cv_text": "Jane Doe — full parsed CV text",
    }


def test_resolve_is_scoped_to_owner():
    upload_id = create_cv_upload_artifact(
        "owner@rico.test", filename="cv.pdf", doc_type="cv",
        content_hash="b" * 64, file_size=10, cv_text="x",
    )
    assert upload_id
    # Same id, different (server-derived) user -> never resolves.
    assert resolve_cv_upload_artifact("attacker@rico.test", upload_id) is None
    # Owner still resolves.
    assert resolve_cv_upload_artifact("owner@rico.test", upload_id) is not None


# ── expiry: not readable AND actually deleted (Blocker 2) ─────────────────────

def test_expired_artifact_does_not_resolve():
    _insert_expired("alice@rico.test", "cv.pdf", "c" * 64)
    # It exists but is past its freshness window -> never resolves.
    assert _count() == 1
    with _raw() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM cv_upload_artifacts WHERE user_id = %s",
                ("alice@rico.test",),
            )
            expired_id = str(cur.fetchone()[0])
    assert resolve_cv_upload_artifact("alice@rico.test", expired_id) is None


def test_purge_deletes_expired_rows_but_keeps_live_ones():
    # One live row (created when no expired rows exist, so its inline purge is a
    # no-op), then two already-expired rows seeded via raw SQL.
    live = create_cv_upload_artifact(
        "alice@rico.test", filename="live.pdf", doc_type="cv",
        content_hash="d" * 64, file_size=10, cv_text="x", ttl_minutes=180,
    )
    _insert_expired("alice@rico.test", "old1.pdf", "e" * 64)
    _insert_expired("bob@rico.test", "old2.pdf", "f" * 64)
    assert _count() == 3

    deleted = purge_expired_cv_upload_artifacts()
    assert deleted == 2
    assert _count() == 1
    # The live one survived and still resolves.
    assert resolve_cv_upload_artifact("alice@rico.test", live) is not None


def test_create_opportunistically_purges_expired_rows():
    # Seed an already-expired row directly (raw, to bypass create's own purge).
    _insert_expired("alice@rico.test", "old.pdf", "0" * 64)
    assert _count() == 1
    # A brand-new create must clean up the expired row in the same transaction,
    # so the table never accumulates unbounded expired artifacts even with no
    # background worker.
    new_id = create_cv_upload_artifact(
        "alice@rico.test", filename="new.pdf", doc_type="cv",
        content_hash="1" * 64, file_size=10, cv_text="x", ttl_minutes=180,
    )
    assert new_id
    assert _count() == 1  # expired purged, only the new live row remains
    assert resolve_cv_upload_artifact("alice@rico.test", new_id) is not None


def test_create_already_expired_is_immediately_purged():
    """A negative-TTL create inserts an already-expired row, then its own
    inline purge deletes it in the same transaction — so it neither resolves
    nor lingers. (This is why expired rows can't be seeded via create.)"""
    upload_id = create_cv_upload_artifact(
        "alice@rico.test", filename="dead.pdf", doc_type="cv",
        content_hash="9" * 64, file_size=10, cv_text="x", ttl_minutes=-10,
    )
    assert upload_id
    assert _count() == 0
    assert resolve_cv_upload_artifact("alice@rico.test", upload_id) is None

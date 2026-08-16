"""
tests/integration/test_migration_runner_postgres.py

Real-PostgreSQL integration tests for the Phase-3 migration runner
(``src/db_migrations.py``). Exercises the runner against a REAL, disposable
Postgres: ledger semantics, ordering, idempotency, one-behind targeting,
advisory-lock concurrency, fail-loud failure handling, checksum mismatch, and
DB-unavailable behavior.

Isolation: this file uses a DEDICATED database (``rico_test_migrations``) on the
same server as ``RICO_TEST_DATABASE_URL`` so dropping/recreating its schema can
never interfere with the other integration files' ``rico_test`` public schema.
Skips cleanly when ``RICO_TEST_DATABASE_URL`` is unset (no local Postgres); in
CI it is wired to the postgres service container (job: postgres-integration).

NOTE on "fresh database": the numbered migrations are NOT self-sufficient —
migration 009 references ``rico_users``, which only the application runtime DDL
creates (a documented, pre-existing architectural debt). The "fresh database"
scenario therefore mirrors production boot order: runtime DDL first, then the
numbered migrations. Reconciling the two DDL sources is a separate
consolidation effort, out of scope for the runner.
"""
from __future__ import annotations

import os
import threading
import urllib.parse

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres migration-runner tests skipped.",
)

_MIGRATIONS_DB = "rico_test_migrations"


def _migrations_db_url() -> str:
    """RICO_TEST_DATABASE_URL with dbname replaced by the dedicated database."""
    parsed = urllib.parse.urlparse(TEST_DATABASE_URL)
    path = "/" + _MIGRATIONS_DB
    return urllib.parse.urlunparse(parsed._replace(path=path))


def _connect(dsn: str):
    return psycopg2.connect(dsn, connect_timeout=10)


def _fresh_schema(dsn: str) -> None:
    conn = _connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
    finally:
        conn.close()


def _bootstrap_runtime_ddl(dsn: str) -> None:
    """Mirror production boot DDL so the numbered migrations can replay."""
    os.environ["DATABASE_URL"] = dsn
    from src.db import init_db
    from src.rico_db import RicoDB

    init_db()
    RicoDB(database_url=dsn).init()


@pytest.fixture(scope="module", autouse=True)
def _dedicated_db():
    """Create the dedicated migrations database on first use."""
    server = urllib.parse.urlparse(TEST_DATABASE_URL)._replace(path="/postgres")
    conn = _connect(urllib.parse.urlunparse(server))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_MIGRATIONS_DB,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{_MIGRATIONS_DB}"')
    finally:
        conn.close()
    yield
    # Leave the database in place across test runs (idempotent create above).


@pytest.fixture(autouse=True)
def _fresh_db():
    """Each test starts from an empty, fresh database."""
    dsn = _migrations_db_url()
    _fresh_schema(dsn)
    yield dsn
    _fresh_schema(dsn)


class TestFreshDatabaseAllMigrations:
    def test_fresh_db_applies_all_migrations_and_is_drift_clean(self, _fresh_db):
        from src.db_migrations import apply_all, check

        _bootstrap_runtime_ddl(_fresh_db)
        applied = apply_all(_fresh_db)
        assert "005" in applied and "052" in applied
        assert check(_fresh_db) == []


class TestIdempotency:
    def test_second_apply_is_a_no_op(self, _fresh_db):
        from src.db_migrations import apply_all

        _bootstrap_runtime_ddl(_fresh_db)
        first = apply_all(_fresh_db)
        second = apply_all(_fresh_db)
        assert set(first) == set(second)
        assert apply_all(_fresh_db) == first


class TestOneBehind:
    def test_target_then_remainder(self, _fresh_db):
        from src.db_migrations import apply_all, check

        _bootstrap_runtime_ddl(_fresh_db)
        partial = apply_all(_fresh_db, target="041")
        assert "043" not in partial and "041" in partial
        full = apply_all(_fresh_db)
        assert "043" in full and "052" in full
        assert check(_fresh_db) == []


class TestOrdering:
    def test_ledger_is_monotonic(self, _fresh_db):
        import psycopg2

        from src.db_migrations import apply_all

        _bootstrap_runtime_ddl(_fresh_db)
        apply_all(_fresh_db)
        conn = psycopg2.connect(_fresh_db)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version FROM schema_migrations ORDER BY version")
                versions = [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
        # schema_migrations PRIMARY KEY is TEXT; ordering must be numeric.
        assert versions == sorted(versions, key=lambda v: int(v))


class TestConcurrentApply:
    def test_advisory_lock_serializes_two_racers(self, _fresh_db):
        from src.db_migrations import apply_all

        _bootstrap_runtime_ddl(_fresh_db)
        errors: list[Exception] = []
        results: list[int] = []

        def _worker() -> None:
            try:
                applied = apply_all(_fresh_db)
                results.append(len(applied))
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)

        assert errors == []
        # Both runs completed; neither double-applied anything. The advisory
        # lock guarantees the second run is a no-op. Expected = migrations on
        # disk (grows as migrations are added).
        from src.db_migrations import _list_migrations

        expected = {len(_list_migrations())}
        assert set(results) == expected


class TestFailureHandling:
    def test_failing_migration_raises_and_is_not_recorded(self, _fresh_db):
        import pathlib

        from src.db_migrations import MIGRATIONS_DIR, apply_all

        _bootstrap_runtime_ddl(_fresh_db)
        bad = pathlib.Path(MIGRATIONS_DIR) / "099_bad_test.sql"
        bad.write_text("CREATE TABLE bad_ok (id INT);\nSELECT * FROM nonexistent_zzz;")
        try:
            with pytest.raises(RuntimeError, match="099"):
                apply_all(_fresh_db)
        finally:
            bad.unlink()

        conn = psycopg2.connect(_fresh_db)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version FROM schema_migrations WHERE version='099'")
                assert cur.fetchone() is None, "failed migration must not be recorded"
        finally:
            conn.close()


class TestChecksumMismatch:
    def test_modified_applied_file_raises(self, _fresh_db):
        import pathlib

        from src.db_migrations import MIGRATIONS_DIR, apply_all

        _bootstrap_runtime_ddl(_fresh_db)
        apply_all(_fresh_db)
        target = pathlib.Path(MIGRATIONS_DIR) / "052_settings_notifications_reconciliation.sql"
        original = target.read_text(encoding="utf-8")
        try:
            target.write_text(original + "\n-- tampered\n", encoding="utf-8")
            with pytest.raises(RuntimeError, match="checksum mismatch"):
                apply_all(_fresh_db)
        finally:
            target.write_text(original, encoding="utf-8")


class TestInvalidMetadata:
    def test_non_numeric_filenames_are_ignored(self, _fresh_db):
        import pathlib

        from src.db_migrations import MIGRATIONS_DIR, _list_migrations

        _bootstrap_runtime_ddl(_fresh_db)
        junk = pathlib.Path(MIGRATIONS_DIR) / "README.sql"
        junk.write_text("-- ignored\n")
        try:
            paths = _list_migrations()
            assert all(p.name[:3].isdigit() for p in paths)
        finally:
            junk.unlink()


class TestDatabaseUnavailable:
    def test_apply_raises_when_db_unreachable(self):
        from src.db_migrations import apply_all

        with pytest.raises(Exception):
            apply_all("postgresql://nobody:wrong@127.0.0.1:59999/nowhere")

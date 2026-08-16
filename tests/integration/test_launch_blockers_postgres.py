"""
tests/integration/test_launch_blockers_postgres.py

Real-PostgreSQL tests for the launch-blocker closure primitives:
  * account_confirmation (migration 054): single-use, time-limited,
    hash-at-rest, account+purpose-bound tokens; valid / invalid / expired /
    reused / wrong-account / concurrent confirmations.
  * the content-free usage ledger's OCR key space (external-OCR daily cap).

Skips cleanly without RICO_TEST_DATABASE_URL (real Postgres required).
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
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — real-Postgres launch-blocker tests skipped.",
)

_MIGRATIONS_DB = "rico_test_migrations"


def _migrations_db_url() -> str:
    parsed = urllib.parse.urlparse(TEST_DATABASE_URL)
    return urllib.parse.urlunparse(parsed._replace(path="/" + _MIGRATIONS_DB))


@pytest.fixture(scope="module", autouse=True)
def _dedicated_db():
    server = urllib.parse.urlparse(TEST_DATABASE_URL)._replace(path="/postgres")
    conn = psycopg2.connect(urllib.parse.urlunparse(server), connect_timeout=10)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_MIGRATIONS_DB,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{_MIGRATIONS_DB}"')
    finally:
        conn.close()
    yield


@pytest.fixture(autouse=True)
def _fresh_db():
    dsn = _migrations_db_url()
    conn = psycopg2.connect(dsn, connect_timeout=10)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
    finally:
        conn.close()
    # src.db may already be imported with DATABASE_URL unset (a prior test file
    # imported it), which freezes DB_ENABLED=False at module scope. Point the
    # module at the dedicated DB explicitly so the pool/repos can connect.
    import src.db as _db_mod

    _db_mod.DATABASE_URL = dsn
    _db_mod.DB_ENABLED = True
    os.environ["DATABASE_URL"] = dsn
    # Bootstrap runtime DDL (production boot order), then apply numbered
    # migrations (005..054).
    from src.db import init_db
    from src.rico_db import RicoDB

    init_db()
    RicoDB(database_url=dsn).init()
    from src.db_migrations import apply_all

    apply_all(dsn)
    yield dsn


class TestConfirmationLifecycle:
    def _create_and_consume(self, dsn):
        from src.repositories.account_confirmation_repo import (
            JOTFORM_MERGE_PURPOSE,
            consume_confirmation,
            create_confirmation,
        )

        raw = create_confirmation(
            "owner@example.com", JOTFORM_MERGE_PURPOSE, {"profile": {"skills": ["hse"]}}
        )
        assert raw and len(raw) >= 32
        # Only the hash is stored — the raw token must never be in the DB.
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT token_hash, payload FROM account_confirmations")
                row = cur.fetchone()
                assert row[0] != raw
                assert raw not in (row[1] or "")
        finally:
            conn.close()
        return raw

    def test_valid_consume_returns_payload(self, _fresh_db):
        raw = self._create_and_consume(_fresh_db)
        from src.repositories.account_confirmation_repo import (
            JOTFORM_MERGE_PURPOSE,
            consume_confirmation,
        )

        payload = consume_confirmation(raw, JOTFORM_MERGE_PURPOSE, "owner@example.com")
        assert payload and payload["profile"]["skills"] == ["hse"]

    def test_reused_token_is_rejected(self, _fresh_db):
        raw = self._create_and_consume(_fresh_db)
        from src.repositories.account_confirmation_repo import (
            JOTFORM_MERGE_PURPOSE,
            consume_confirmation,
        )

        first = consume_confirmation(raw, JOTFORM_MERGE_PURPOSE, "owner@example.com")
        second = consume_confirmation(raw, JOTFORM_MERGE_PURPOSE, "owner@example.com")
        assert first is not None
        assert second is None  # single-use; replay fails closed

    def test_wrong_account_is_rejected(self, _fresh_db):
        raw = self._create_and_consume(_fresh_db)
        from src.repositories.account_confirmation_repo import (
            JOTFORM_MERGE_PURPOSE,
            consume_confirmation,
        )

        assert consume_confirmation(raw, JOTFORM_MERGE_PURPOSE, "other@example.com") is None

    def test_wrong_purpose_is_rejected(self, _fresh_db):
        raw = self._create_and_consume(_fresh_db)
        from src.repositories.account_confirmation_repo import (
            TELEGRAM_BIND_PURPOSE,
            consume_confirmation,
        )

        assert consume_confirmation(raw, TELEGRAM_BIND_PURPOSE, "owner@example.com") is None

    def test_expired_token_is_rejected(self, _fresh_db):
        from src.repositories.account_confirmation_repo import (
            JOTFORM_MERGE_PURPOSE,
            consume_confirmation,
            create_confirmation,
        )

        raw = create_confirmation(
            "owner@example.com", JOTFORM_MERGE_PURPOSE, payload={}, ttl_seconds=-10
        )
        assert raw
        assert consume_confirmation(raw, JOTFORM_MERGE_PURPOSE, "owner@example.com") is None

    def test_concurrent_confirmation_only_one_wins(self, _fresh_db):
        raw = self._create_and_consume(_fresh_db)
        from src.repositories.account_confirmation_repo import (
            JOTFORM_MERGE_PURPOSE,
            consume_confirmation,
        )

        results: list[object] = []
        barrier = threading.Barrier(2)

        def _worker():
            barrier.wait()
            results.append(consume_confirmation(raw, JOTFORM_MERGE_PURPOSE, "owner@example.com"))

        threads = [threading.Thread(target=_worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        non_none = [r for r in results if r is not None]
        assert len(non_none) == 1  # exactly one concurrent confirm wins


class TestOcrLedgerKeySpace:
    def test_ocr_key_counts_independently(self, _fresh_db):
        from datetime import datetime, timezone

        from src.repositories.ai_usage_repo import (
            count_public_ai_usage_strict,
            record_public_ai_usage,
        )

        now = datetime.now(timezone.utc)
        window = now.replace(hour=0, minute=0, second=0, microsecond=0)
        record_public_ai_usage("ocr:user@example.com")
        record_public_ai_usage("ocr:user@example.com")
        record_public_ai_usage("user@example.com")  # different key space
        assert count_public_ai_usage_strict("ocr:user@example.com", window) == 2
        assert count_public_ai_usage_strict("user@example.com", window) == 1

"""
tests/integration/test_career_memory_deletion_postgres.py

Real-PostgreSQL proof of the #1088 deletion gate for the Career Memory Engine
(#1025): migration 042 applies cleanly (including the deletion-state addendum),
purge erases exactly one account's rows and advances its deletion generation,
a write carrying a pre-purge generation is refused (no resurrection), fresh
post-purge writes persist normally, and purge is monotonic + idempotent.

Mock-layer tests cannot prove any of this — the FOR SHARE / FOR UPDATE
serialization and the partial unique indexes only exist on a real server.

Requires RICO_TEST_DATABASE_URL (NOT the shared DATABASE_URL). Skips cleanly
when unset. In CI this runs in the postgres-integration job.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres integration tests skipped.",
)

_MIGRATION_042_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "migrations", "042_career_memory_engine.sql"
)


@pytest.fixture(scope="module", autouse=True)
def _apply_migration_042():
    """Migration evidence (#1025 gate item 5): 042 applies on a real server."""
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with open(_MIGRATION_042_PATH) as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute(sql)
            # Idempotency evidence: re-running the whole migration is safe.
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _route_repo_to_test_db():
    def _factory():
        return psycopg2.connect(TEST_DATABASE_URL)

    with patch(
        "src.repositories.career_memory_repo.get_db_connection",
        side_effect=_factory,
    ):
        yield
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM career_memory_events")
            cur.execute("DELETE FROM career_memory_facts")
            cur.execute("DELETE FROM career_memory_deletion_state")
        conn.commit()
    finally:
        conn.close()


def _write_event(account_id: str, key: str, expected_generation=None) -> str:
    from src.repositories.career_memory_repo import insert_event

    return insert_event(
        account_id=account_id,
        event_type="job_action.save",
        idempotency_key=key,
        occurred_at=datetime.now(timezone.utc),
        actor="user",
        source="verified_event",
        confidence=1.0,
        payload={"job_key": "abc123"},
        source_record_id="rec-1",
        expected_deletion_generation=expected_generation,
    )


def _write_fact(account_id: str, key: str, expected_generation=None) -> str:
    from src.repositories.career_memory_repo import insert_fact

    return insert_fact(
        account_id=account_id,
        fact_key="identity.notice_period",
        fact_class="replaceable",
        value={"days": 30},
        idempotency_key=key,
        occurred_at=datetime.now(timezone.utc),
        actor="user",
        source="user_stated",
        confidence=1.0,
        source_record_id="rec-1",
        expected_deletion_generation=expected_generation,
    )


def _counts(account_id: str) -> tuple[int, int]:
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM career_memory_events WHERE account_id = %s",
                (account_id,),
            )
            events = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM career_memory_facts WHERE account_id = %s",
                (account_id,),
            )
            facts = int(cur.fetchone()[0])
            return events, facts
    finally:
        conn.close()


class TestPurgeIsolationAndReceipt:
    def test_purge_erases_only_the_target_account(self):
        from src.repositories.career_memory_repo import purge_account_memory

        acct_a = str(uuid.uuid4())
        acct_b = str(uuid.uuid4())
        assert _write_event(acct_a, "a-e1") == "written"
        assert _write_fact(acct_a, "a-f1") == "written"
        assert _write_event(acct_b, "b-e1") == "written"
        assert _write_fact(acct_b, "b-f1") == "written"

        receipt = purge_account_memory(account_id=acct_a)

        assert receipt["deletion_generation"] == 1
        assert receipt["events_deleted"] == 1
        assert receipt["facts_deleted"] == 1
        assert receipt["purged_at"] is not None
        assert _counts(acct_a) == (0, 0)
        # Account B is completely untouched — strict per-account isolation.
        assert _counts(acct_b) == (1, 1)

    def test_purge_is_monotonic_and_idempotent(self):
        from src.repositories.career_memory_repo import (
            get_deletion_generation,
            purge_account_memory,
        )

        acct = str(uuid.uuid4())
        assert get_deletion_generation(account_id=acct) == 0
        r1 = purge_account_memory(account_id=acct)
        r2 = purge_account_memory(account_id=acct)
        assert (r1["deletion_generation"], r2["deletion_generation"]) == (1, 2)
        assert r2["events_deleted"] == 0 and r2["facts_deleted"] == 0
        assert get_deletion_generation(account_id=acct) == 2


class TestNoResurrectionAcrossBoundary:
    def test_stale_generation_event_write_is_refused(self):
        """A late write that captured its data before the purge cannot land."""
        from src.repositories.career_memory_repo import (
            get_deletion_generation,
            purge_account_memory,
        )

        acct = str(uuid.uuid4())
        assert _write_event(acct, "pre-1") == "written"
        pre_purge_generation = get_deletion_generation(account_id=acct)

        purge_account_memory(account_id=acct)

        # The "paused append" from #1088: it replays with the generation it
        # captured before the clear boundary — refused, nothing persisted.
        assert _write_event(acct, "pre-2", expected_generation=pre_purge_generation) \
            == "refused_deletion_boundary"
        assert _write_fact(acct, "pre-3", expected_generation=pre_purge_generation) \
            == "refused_deletion_boundary"
        assert _counts(acct) == (0, 0)

    def test_fresh_writes_after_purge_persist_normally(self):
        from src.repositories.career_memory_repo import (
            get_deletion_generation,
            purge_account_memory,
        )

        acct = str(uuid.uuid4())
        assert _write_event(acct, "old-1") == "written"
        purge_account_memory(account_id=acct)

        # A brand-new post-clear write (no stale generation claim) is admitted
        # under the current generation and stamped with it.
        assert _write_event(acct, "new-1") == "written"
        current = get_deletion_generation(account_id=acct)
        assert _write_event(acct, "new-2", expected_generation=current) == "written"
        assert _counts(acct)[0] == 2

        conn = psycopg2.connect(TEST_DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT deletion_generation
                    FROM career_memory_events WHERE account_id = %s
                    """,
                    (acct,),
                )
                stamped = {int(r[0]) for r in cur.fetchall()}
        finally:
            conn.close()
        assert stamped == {1}

    def test_second_purge_erases_post_first_purge_rows(self):
        """clear → write → clear again: the second boundary erases the new rows."""
        from src.repositories.career_memory_repo import purge_account_memory

        acct = str(uuid.uuid4())
        _write_event(acct, "gen0-1")
        purge_account_memory(account_id=acct)
        _write_event(acct, "gen1-1")
        receipt = purge_account_memory(account_id=acct)
        assert receipt["events_deleted"] == 1
        assert _counts(acct) == (0, 0)


class TestWriterLevelPurge:
    def test_writer_purge_resolves_account_and_returns_receipt(self):
        from src.services import memory_writer as mw

        acct = str(uuid.uuid4())
        assert _write_event(acct, "w-1") == "written"

        with patch.object(
            mw.MemoryWriter, "_resolve_account_id", staticmethod(lambda _ext: acct)
        ):
            receipt = mw.MemoryWriter().purge_account(external_user_id="user@test.com")

        assert receipt is not None
        assert receipt["events_deleted"] == 1
        assert _counts(acct) == (0, 0)

    def test_writer_purge_works_with_flag_off(self, monkeypatch):
        """Deletion must be honored even when the engine is disabled."""
        from src.services import memory_writer as mw

        monkeypatch.delenv("RICO_MEMORY_ENGINE_ENABLED", raising=False)
        acct = str(uuid.uuid4())
        assert _write_event(acct, "off-1") == "written"

        with patch.object(
            mw.MemoryWriter, "_resolve_account_id", staticmethod(lambda _ext: acct)
        ):
            writer = mw.MemoryWriter()
            assert writer.enabled() is False
            receipt = writer.purge_account(external_user_id="user@test.com")

        assert receipt is not None and receipt["events_deleted"] == 1
        assert _counts(acct) == (0, 0)

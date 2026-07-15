"""
tests/integration/test_career_memory_engine_postgres.py

Real-PostgreSQL integration tests for the Career Memory Engine M1 schema
(ADR-001, migration 042).

Why this file exists: the unit tests in tests/test_memory_engine_m1.py mock
the repository layer entirely, so they verify writer policy but cannot verify
what real Postgres enforces — the (account_id, idempotency_key) unique
constraints, the partial unique indexes guarding the single-current-row
invariant of the fact history model, the provenance/vocabulary CHECK
constraints, or per-account row isolation. This file applies migration 042 to
a disposable database and exercises the real MemoryWriter → career_memory_repo
path against it.

Requires RICO_TEST_DATABASE_URL (never the shared DATABASE_URL). Skips cleanly
when unset. In CI this is wired to the postgres service container in
.github/workflows/qa-tests.yml (job: postgres-integration).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

from src.rico_db import RicoDB
from src.services.memory_writer import MemoryWriter

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres integration tests skipped.",
)

_MIGRATION_042_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "migrations", "042_career_memory_engine.sql"
)

NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

ACCOUNT_A = str(uuid.uuid4())
ACCOUNT_B = str(uuid.uuid4())
PUBLIC_ROW = str(uuid.uuid4())

EMAIL_A = "memory-a@test.invalid"
EMAIL_B = "memory-b@test.invalid"
PUBLIC_ID = "public:web-memtest-1"


@pytest.fixture(scope="module")
def db() -> RicoDB:
    """RicoDB against the real test database with migration 042 applied and
    three synthetic identities present (two accounts + one public session)."""
    instance = RicoDB(database_url=TEST_DATABASE_URL)
    conn = instance.connect()  # ensures base schema, incl. rico_users
    try:
        with open(_MIGRATION_042_PATH) as f:
            migration_sql = f.read()
        with conn.cursor() as cur:
            cur.execute(migration_sql)
            # Delete-then-insert (not ON CONFLICT DO NOTHING): this module's
            # UUID constants are regenerated per run, so a leftover row from a
            # previous run against the same database would otherwise win the
            # identity resolution and every account_id assertion would miss.
            cur.execute(
                "DELETE FROM rico_users WHERE external_user_id IN (%s, %s, %s)",
                ("ext-memtest-a", "ext-memtest-b", PUBLIC_ID),
            )
            cur.execute(
                """
                INSERT INTO rico_users (id, external_user_id, email)
                VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s)
                """,
                (
                    ACCOUNT_A, "ext-memtest-a", EMAIL_A,
                    ACCOUNT_B, "ext-memtest-b", EMAIL_B,
                    PUBLIC_ROW, PUBLIC_ID, None,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return instance


@pytest.fixture(autouse=True)
def _engine_env(db: RicoDB, monkeypatch):
    """Point src.db at the test database, enable the engine, resolve identity
    through the same test database, and clean the memory tables after each
    test (real Postgres — state persists otherwise)."""
    monkeypatch.setattr("src.db.DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr("src.db.DB_ENABLED", True)
    monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
    monkeypatch.delenv("RICO_MEMORY_ENGINE_KILL", raising=False)
    monkeypatch.setattr(
        "src.rico_db.RicoDB",
        lambda *a, **k: RicoDB(database_url=TEST_DATABASE_URL),
    )
    yield
    conn = db.connect(ensure_schema=False)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM career_memory_facts")
            cur.execute("DELETE FROM career_memory_events")
        conn.commit()
    finally:
        conn.close()


def _query(db: RicoDB, sql: str, params=()):
    # Plain psycopg2 connection: RicoDB.connect() uses a dict cursor, and these
    # assertions index rows positionally.
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def _exec_raw(db: RicoDB, sql: str, params=()):
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def event_kwargs(**overrides):
    base = dict(
        external_user_id=EMAIL_A,
        event_type="job_action.save",
        idempotency_key="evt-1",
        occurred_at=NOW,
        actor="user",
        source="verified_event",
        confidence=1.0,
        payload={"action": "save", "title": "Ops Manager", "company": "Acme"},
        source_record_id="action_audit_log:test-1",
    )
    base.update(overrides)
    return base


def fact_kwargs(**overrides):
    base = dict(
        external_user_id=EMAIL_A,
        fact_key="identity.notice_period",
        fact_class="replaceable",
        value={"weeks": 4},
        idempotency_key="fct-1",
        occurred_at=NOW,
        actor="user",
        source="user_stated",
        confidence=1.0,
        source_record_id="chat:msg-1",
    )
    base.update(overrides)
    return base


# ── Events: idempotency + isolation ──────────────────────────────────────────

class TestEventConstraints:
    def test_idempotency_unique_constraint_dedupes(self, db):
        writer = MemoryWriter()
        first = writer.record_event(**event_kwargs())
        second = writer.record_event(**event_kwargs())

        assert first.status == "written"
        assert second.status == "duplicate"
        rows = _query(
            db,
            "SELECT COUNT(*) FROM career_memory_events WHERE account_id = %s",
            (first.account_id,),
        )
        assert rows[0][0] == 1

    def test_same_key_different_accounts_both_insert(self, db):
        writer = MemoryWriter()
        a = writer.record_event(**event_kwargs(external_user_id=EMAIL_A))
        b = writer.record_event(**event_kwargs(external_user_id=EMAIL_B))

        assert a.status == "written"
        assert b.status == "written"
        assert a.account_id != b.account_id

    def test_per_user_isolation(self, db):
        writer = MemoryWriter()
        writer.record_event(**event_kwargs(idempotency_key="a-1"))
        writer.record_event(**event_kwargs(idempotency_key="a-2"))
        writer.record_event(**event_kwargs(
            external_user_id=EMAIL_B, idempotency_key="b-1"
        ))

        from src.repositories.career_memory_repo import count_events

        assert count_events(account_id=ACCOUNT_A) == 2
        assert count_events(account_id=ACCOUNT_B) == 1

    def test_public_session_rows_stay_out_of_account_memory(self, db):
        """ADR §3 against real resolution: the public session writes under its
        own canonical row, never into an account's memory."""
        writer = MemoryWriter()
        pub = writer.record_event(**event_kwargs(
            external_user_id=PUBLIC_ID, idempotency_key="pub-1"
        ))

        assert pub.status == "written"
        assert pub.account_id == PUBLIC_ROW

        from src.repositories.career_memory_repo import count_events

        assert count_events(account_id=PUBLIC_ROW) == 1
        assert count_events(account_id=ACCOUNT_A) == 0
        assert count_events(account_id=ACCOUNT_B) == 0

    def test_check_constraints_reject_bad_vocabulary(self, db):
        base_cols = (
            "account_id, event_type, idempotency_key, occurred_at, actor, "
            "source, confidence, payload, source_record_id"
        )
        good = (ACCOUNT_A, "t", "raw-1", NOW, "user", "verified_event", 1.0,
                json.dumps({}), "x")

        # Bad source tier.
        with pytest.raises(psycopg2.errors.CheckViolation):
            _exec_raw(db, f"""
                INSERT INTO career_memory_events ({base_cols})
                VALUES (%s,%s,%s,%s,%s,'guesswork',%s,%s,%s)
            """, (good[0], good[1], "raw-2", good[3], good[4], good[6], good[7], good[8]))

        # Confidence out of range.
        with pytest.raises(psycopg2.errors.CheckViolation):
            _exec_raw(db, f"""
                INSERT INTO career_memory_events ({base_cols})
                VALUES (%s,%s,%s,%s,%s,%s,1.5,%s,%s)
            """, (good[0], good[1], "raw-3", good[3], good[4], good[5], good[7], good[8]))

        # Mandatory provenance: no source_record_id AND no source_uri.
        with pytest.raises(psycopg2.errors.CheckViolation):
            _exec_raw(db, f"""
                INSERT INTO career_memory_events ({base_cols})
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL)
            """, (good[0], good[1], "raw-4", good[3], good[4], good[5], good[6], good[7]))


# ── Facts: history semantics ─────────────────────────────────────────────────

class TestFactHistory:
    def test_replaceable_supersede_keeps_history(self, db):
        writer = MemoryWriter()
        v1 = writer.record_fact(**fact_kwargs(idempotency_key="f-1"))
        v2 = writer.record_fact(**fact_kwargs(
            idempotency_key="f-2", value={"weeks": 8}
        ))
        assert v1.status == "written"
        assert v2.status == "written"

        rows = _query(db, """
            SELECT value, effective_to, superseded_by
            FROM career_memory_facts
            WHERE account_id = %s AND fact_key = 'identity.notice_period'
            ORDER BY id ASC
        """, (ACCOUNT_A,))
        assert len(rows) == 2
        old, new = rows[0], rows[1]
        # Old value is preserved, closed, and linked to its successor.
        assert old[0] == {"weeks": 4}
        assert old[1] is not None
        assert old[2] is not None
        # New value is the single current row.
        assert new[0] == {"weeks": 8}
        assert new[1] is None

    def test_retry_of_same_write_does_not_close_current_twice(self, db):
        writer = MemoryWriter()
        writer.record_fact(**fact_kwargs(idempotency_key="f-1"))
        writer.record_fact(**fact_kwargs(idempotency_key="f-2", value={"weeks": 8}))
        retry = writer.record_fact(**fact_kwargs(idempotency_key="f-2", value={"weeks": 8}))

        assert retry.status == "duplicate"
        current = _query(db, """
            SELECT COUNT(*) FROM career_memory_facts
            WHERE account_id = %s AND fact_key = 'identity.notice_period'
                  AND effective_to IS NULL
        """, (ACCOUNT_A,))
        assert current[0][0] == 1

    def test_partial_unique_index_blocks_second_current_row(self, db):
        writer = MemoryWriter()
        writer.record_fact(**fact_kwargs(idempotency_key="f-1"))

        # A direct INSERT bypassing the writer cannot create a second current
        # row for the same replaceable fact — real Postgres enforcement.
        with pytest.raises(psycopg2.errors.UniqueViolation):
            _exec_raw(db, """
                INSERT INTO career_memory_facts (
                    account_id, fact_key, fact_class, value, source,
                    source_record_id, confidence, actor, occurred_at,
                    idempotency_key
                ) VALUES (%s, 'identity.notice_period', 'replaceable', %s,
                          'user_stated', 'chat:msg-2', 1.0, 'user', %s, 'f-rogue')
            """, (ACCOUNT_A, json.dumps({"weeks": 12}), NOW))

    def test_set_valued_members_add_and_explicit_remove(self, db):
        writer = MemoryWriter()
        m1 = writer.record_fact(**fact_kwargs(
            fact_key="identity.target_roles", fact_class="set_valued",
            value={"role": "Operations Manager"}, idempotency_key="s-1",
        ))
        m2 = writer.record_fact(**fact_kwargs(
            fact_key="identity.target_roles", fact_class="set_valued",
            value={"role": "Supply Chain Lead"}, idempotency_key="s-2",
        ))
        assert m1.status == "written"
        assert m2.status == "written"

        from src.repositories.career_memory_repo import (
            close_set_member,
            get_current_set_members,
        )

        members = get_current_set_members(
            account_id=ACCOUNT_A, fact_key="identity.target_roles"
        )
        assert len(members) == 2

        # Removal is explicit — a new arrival never implies one (ADR §7).
        closed = close_set_member(
            account_id=ACCOUNT_A, fact_key="identity.target_roles",
            value={"role": "Operations Manager"},
        )
        assert closed is True
        members = get_current_set_members(
            account_id=ACCOUNT_A, fact_key="identity.target_roles"
        )
        assert [m["value"] for m in members] == [{"role": "Supply Chain Lead"}]

        # History retained: the removed member still exists as a closed row.
        rows = _query(db, """
            SELECT COUNT(*) FROM career_memory_facts
            WHERE account_id = %s AND fact_key = 'identity.target_roles'
        """, (ACCOUNT_A,))
        assert rows[0][0] == 2

    def test_duplicate_set_member_is_idempotent_at_member_level(self, db):
        writer = MemoryWriter()
        writer.record_fact(**fact_kwargs(
            fact_key="identity.target_roles", fact_class="set_valued",
            value={"role": "Operations Manager"}, idempotency_key="s-1",
        ))
        # Same member value again under a NEW idempotency key: the partial
        # unique index (account, key, md5(value)) makes this a repo-level
        # failure surfaced as a writer 'failed' status — never a second
        # current member row.
        dup = writer.record_fact(**fact_kwargs(
            fact_key="identity.target_roles", fact_class="set_valued",
            value={"role": "Operations Manager"}, idempotency_key="s-9",
        ))
        assert dup.status in ("failed", "duplicate")

        from src.repositories.career_memory_repo import get_current_set_members

        members = get_current_set_members(
            account_id=ACCOUNT_A, fact_key="identity.target_roles"
        )
        assert len(members) == 1

    def test_fact_isolation_between_accounts(self, db):
        writer = MemoryWriter()
        writer.record_fact(**fact_kwargs(idempotency_key="f-a"))
        writer.record_fact(**fact_kwargs(
            external_user_id=EMAIL_B, idempotency_key="f-b", value={"weeks": 2}
        ))

        from src.repositories.career_memory_repo import get_current_fact

        fact_a = get_current_fact(
            account_id=ACCOUNT_A, fact_key="identity.notice_period"
        )
        fact_b = get_current_fact(
            account_id=ACCOUNT_B, fact_key="identity.notice_period"
        )
        assert fact_a["value"] == {"weeks": 4}
        assert fact_b["value"] == {"weeks": 2}

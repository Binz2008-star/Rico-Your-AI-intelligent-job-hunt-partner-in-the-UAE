"""
tests/integration/test_erasure_wiring_postgres.py

Real-PostgreSQL proof of the #1088 erasure wiring: the shared orchestrator
(src/services/erasure_service.py) erases DB chat rows, legacy local memory
copies, and memory-engine rows for EXACTLY one account; a stale pre-erasure
engine write cannot resurrect data; retries are idempotent; and a DB outage
raises instead of producing a success claim.

Requires RICO_TEST_DATABASE_URL (NOT the shared DATABASE_URL). Skips cleanly
when unset. In CI this runs in the postgres-integration job. No production
database is involved.
"""
from __future__ import annotations

import json
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
def _schema():
    """Base rico schema (via RicoDB) + migration 042 on the test database."""
    from src.rico_db import RicoDB

    RicoDB(database_url=TEST_DATABASE_URL).connect().close()
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with open(_MIGRATION_042_PATH) as f:
            with conn.cursor() as cur:
                cur.execute(f.read())
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _wire_to_test_db(monkeypatch, tmp_path):
    """Point RicoDB (env), the engine repo, and the legacy memory dir at
    disposable stores; clean all rows afterward."""
    import src.rico_memory as rm

    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)

    def _factory():
        return psycopg2.connect(TEST_DATABASE_URL)

    with patch(
        "src.repositories.career_memory_repo.get_db_connection",
        side_effect=_factory,
    ):
        yield tmp_path

    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_chat_history")
            cur.execute("DELETE FROM career_memory_events")
            cur.execute("DELETE FROM career_memory_facts")
            cur.execute("DELETE FROM career_memory_deletion_state")
            cur.execute("DELETE FROM rico_users WHERE external_user_id LIKE 'erasure-%'")
        conn.commit()
    finally:
        conn.close()


def _seed_user(tag: str) -> tuple[str, str]:
    """Create a rico_users row + 2 chat rows. Returns (external_id, uuid)."""
    external = f"erasure-{tag}-{uuid.uuid4().hex[:8]}@test.com"
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rico_users (external_user_id, email, name)
                VALUES (%s, %s, %s) RETURNING id::text
                """,
                (external, external, f"Erasure {tag}"),
            )
            uid = cur.fetchone()[0]
            for i in range(2):
                cur.execute(
                    """
                    INSERT INTO rico_chat_history (user_id, role, message)
                    VALUES (%s, 'user', %s)
                    """,
                    (uid, f"sentinel message {tag} {i}"),
                )
        conn.commit()
        return external, uid
    finally:
        conn.close()


def _seed_memories(tmp_path, external: str) -> None:
    import src.rico_memory as rm

    path = tmp_path / f"memories_{rm._safe_key(external)}.json"
    path.write_text(json.dumps([
        {"memory_type": "conversation", "content": f"sentinel conv {external}"},
        {"memory_type": "preference", "content": "likes Dubai"},
    ]), encoding="utf-8")
    chat = tmp_path / f"chat_{rm._safe_key(external)}.json"
    chat.write_text("[]", encoding="utf-8")


def _seed_engine_event(account_uuid: str, key: str) -> str:
    from src.repositories.career_memory_repo import insert_event

    return insert_event(
        account_id=account_uuid,
        event_type="job_action.save",
        idempotency_key=key,
        occurred_at=datetime.now(timezone.utc),
        actor="user",
        source="verified_event",
        confidence=1.0,
        payload={"job_key": "abc"},
        source_record_id="rec-1",
    )


def _chat_rows(uid: str) -> int:
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM rico_chat_history WHERE user_id = %s", (uid,)
            )
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def _engine_events(uid: str) -> int:
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM career_memory_events WHERE account_id = %s", (uid,)
            )
            return int(cur.fetchone()[0])
    finally:
        conn.close()


class TestAccountErasureIsolation:
    def test_account_scope_erases_exactly_one_account(self, _wire_to_test_db):
        tmp_path = _wire_to_test_db
        import src.rico_memory as rm
        from src.services.erasure_service import erase_account_data

        ext_a, uid_a = _seed_user("a")
        ext_b, uid_b = _seed_user("b")
        _seed_memories(tmp_path, ext_a)
        _seed_memories(tmp_path, ext_b)
        assert _seed_engine_event(uid_a, "a-1") == "written"
        assert _seed_engine_event(uid_b, "b-1") == "written"

        receipt = erase_account_data(ext_a)

        assert receipt["scope"] == "account"
        assert receipt["chat_rows_deleted"] == 2
        assert receipt["memory_entries_deleted"] == 2
        assert receipt["engine"]["provisioned"] is True
        assert receipt["engine"]["events_deleted"] == 1
        assert receipt["engine"]["deletion_generation"] == 1

        # Account A fully erased.
        assert _chat_rows(uid_a) == 0
        assert _engine_events(uid_a) == 0
        assert not (tmp_path / f"memories_{rm._safe_key(ext_a)}.json").exists()
        # Account B untouched — strict isolation.
        assert _chat_rows(uid_b) == 2
        assert _engine_events(uid_b) == 1
        assert (tmp_path / f"memories_{rm._safe_key(ext_b)}.json").exists()

    def test_retry_is_idempotent_success(self, _wire_to_test_db):
        from src.services.erasure_service import erase_account_data

        ext_a, uid_a = _seed_user("retry")
        first = erase_account_data(ext_a)
        second = erase_account_data(ext_a)
        assert first["chat_rows_deleted"] == 2
        assert second["chat_rows_deleted"] == 0
        assert second["engine"]["deletion_generation"] == 2  # boundary advances
        assert _chat_rows(uid_a) == 0


class TestNoResurrection:
    def test_stale_pre_erasure_engine_write_is_refused(self, _wire_to_test_db):
        from src.repositories.career_memory_repo import (
            get_deletion_generation,
            insert_event,
        )
        from src.services.erasure_service import erase_account_data

        ext_a, uid_a = _seed_user("stale")
        assert _seed_engine_event(uid_a, "pre-1") == "written"
        pre_generation = get_deletion_generation(account_id=uid_a)

        erase_account_data(ext_a)

        status = insert_event(
            account_id=uid_a,
            event_type="job_action.save",
            idempotency_key="pre-2",
            occurred_at=datetime.now(timezone.utc),
            actor="user",
            source="verified_event",
            confidence=1.0,
            payload={"job_key": "stale"},
            source_record_id="rec-1",
            expected_deletion_generation=pre_generation,
        )
        assert status == "refused_deletion_boundary"
        assert _engine_events(uid_a) == 0


class TestConversationScopeOnPostgres:
    def test_chat_scope_erases_conversation_but_not_engine(self, _wire_to_test_db):
        tmp_path = _wire_to_test_db
        import src.rico_memory as rm
        from src.services.erasure_service import erase_conversation_data

        ext_a, uid_a = _seed_user("chat")
        _seed_memories(tmp_path, ext_a)
        assert _seed_engine_event(uid_a, "keep-1") == "written"

        receipt = erase_conversation_data(ext_a)

        assert receipt["chat_rows_deleted"] == 2
        assert receipt["conversation_memories_deleted"] == 1
        assert _chat_rows(uid_a) == 0
        # Job-action episodes are NOT conversation data — chat scope keeps them.
        assert _engine_events(uid_a) == 1
        remaining = json.loads(
            (tmp_path / f"memories_{rm._safe_key(ext_a)}.json").read_text(encoding="utf-8")
        )
        assert [m["memory_type"] for m in remaining] == ["preference"]


class TestTruthfulFailure:
    def test_db_outage_raises_and_leaves_other_data_intact(self, _wire_to_test_db, monkeypatch):
        from src.services.erasure_service import ErasureError, erase_account_data

        ext_b, uid_b = _seed_user("intact")

        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://nobody@127.0.0.1:59999/nowhere"
        )
        with pytest.raises(ErasureError):
            erase_account_data(ext_b)

        monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
        assert _chat_rows(uid_b) == 2

"""Atomic shared operation-ownership store — real Postgres (DEC-20260721-001 slice 1).

Proves the property the in-process nonce model could not provide (pinned as
unsafe by tests/unit/test_operation_duplicate_guard.py's
test_concurrent_foreign_process_would_release_ownership_UNSAFE_for_multiworker):
with ownership in `chat_operations` (migration 050),

  * a concurrently-ALIVE second worker CANNOT steal or release a live
    operation — its claim is atomically refused and no duplicate provider
    cascade can start;
  * ownership releases ONLY on proof of executor death — a heartbeat lease
    that stopped being renewed — never on age or on process identity;
  * the attempt fence is enforced in SQL: after a lease takeover, the dead
    execution's late result write is refused (one generation completes at
    most once);
  * a different user re-sending the same operation_id neither observes,
    blocks, nor clobbers the owner — they get a fresh operation;
  * a `failed` write never overwrites `completed`.

Requires a real Postgres via RICO_TEST_DATABASE_URL; skips cleanly when unset.
Wired to the postgres-integration job in .github/workflows/qa-tests.yml.

NOTE: this store makes multi-worker ownership CORRECT; actually raising
workers/instances stays blocked until the dedicated multi-worker validation
slice (DEC-20260721-001 slice 4 — cancellation/monitoring proof) passes.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

from src.repositories import chat_operations_repo as repo
from src.services import operation_state as ops

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — skipped.",
)

_USER = "owner-a@test.com"
_OTHER_USER = "owner-b@test.com"
_OP = "op_ownership_it_0001"
_MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "050_chat_operations.sql"


def _raw():
    return psycopg2.connect(TEST_DATABASE_URL)


@pytest.fixture(scope="module")
def _schema():
    conn = _raw()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(_MIGRATION.read_text())
        yield
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _postgres_store(_schema, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("RICO_OPERATION_STORE", "postgres")
    conn = _raw()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE chat_operations")
    finally:
        conn.close()
    ops.reset_for_tests()
    yield
    ops.reset_for_tests()


def _set_heartbeat_age(operation_id: str, seconds: int) -> None:
    conn = _raw()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_operations SET heartbeat_at = now() - make_interval(secs => %s) "
                    "WHERE operation_id = %s",
                    (seconds, operation_id),
                )
                assert cur.rowcount == 1
    finally:
        conn.close()


def _row(operation_id: str) -> tuple:
    conn = _raw()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, status, attempt, executor_nonce, result_count "
                    "FROM chat_operations WHERE operation_id = %s",
                    (operation_id,),
                )
                return cur.fetchone()
    finally:
        conn.close()


# ── The property the nonce model lacked ──────────────────────────────────────

def test_concurrent_worker_cannot_steal_live_operation(monkeypatch):
    """A second ALIVE worker's same-id claim is refused — no release, no
    duplicate cascade. This is the exact hole documented by the unit suite's
    ..._UNSAFE_for_multiworker test, closed."""
    monkeypatch.setattr(ops, "_PROCESS_NONCE", "proc-a")
    first = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    assert first["claimed"] is True and first["attempt"] == 1

    monkeypatch.setattr(ops, "_PROCESS_NONCE", "proc-b")  # a DIFFERENT live worker
    second = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    assert second["claimed"] is False
    assert second["operation_id"] == _OP
    # Ownership untouched: still worker A's attempt-1 running execution.
    assert _row(_OP) == (_USER, "running", 1, "proc-a", None)

    # The read path agrees: live (fresh lease) from ANY process, and
    # expire_if_orphaned refuses to transition a fresh-lease operation.
    seen = ops.get_operation(_USER, _OP)
    assert seen["ownership"] == "db"
    assert ops.is_actively_running(seen) is True
    unchanged = ops.expire_if_orphaned(_USER, seen)
    assert unchanged["status"] == "running"


def test_lease_takeover_only_after_executor_death(monkeypatch):
    """Ownership releases ONLY when the heartbeat lease expired (proof of
    death), and the takeover bumps `attempt`, fencing the dead execution's
    late write in SQL."""
    monkeypatch.setattr(ops, "_PROCESS_NONCE", "proc-a")
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    _set_heartbeat_age(_OP, ops.LEASE_SECONDS + 5)  # executor died

    monkeypatch.setattr(ops, "_PROCESS_NONCE", "proc-b")
    taken = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    assert taken["claimed"] is True and taken["attempt"] == 2

    # Dead execution (attempt 1) cannot record a late completion…
    refused = ops.mark_completed(_USER, _OP, result_count=9, attempt=1)
    assert refused is None
    assert _row(_OP)[1:3] == ("running", 2)
    # …the live owner (attempt 2) can.
    applied = ops.mark_completed(_USER, _OP, result_count=3, attempt=2)
    assert applied is not None
    assert _row(_OP) == (_USER, "completed", 2, "proc-b", 3)


def test_read_path_expires_lease_dead_operation():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    _set_heartbeat_age(_OP, ops.LEASE_SECONDS + 5)
    seen = ops.get_operation(_USER, _OP)
    assert ops.is_actively_running(seen) is False
    expired = ops.expire_if_orphaned(_USER, seen)
    assert expired["status"] == "expired"
    assert _row(_OP)[1] == "expired"


def test_foreign_user_same_id_gets_fresh_operation_and_no_leak():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    # The other user can neither observe…
    assert ops.get_operation(_OTHER_USER, _OP) is None
    # …nor be blocked, nor clobber: they execute under a FRESH id.
    theirs = ops.start_job_search_operation(
        user_id=_OTHER_USER, role_or_query="accountant", operation_id=_OP
    )
    assert theirs["claimed"] is True
    assert theirs["operation_id"] != _OP
    assert _row(_OP)[0] == _USER  # owner's record untouched
    assert _row(theirs["operation_id"])[0] == _OTHER_USER


def test_failed_write_never_overwrites_completed():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.mark_completed(_USER, _OP, result_count=5, attempt=1)
    kept = ops.mark_failed(_USER, _OP, error="late cascade error", attempt=1)
    assert kept is not None and kept["status"] == "completed"
    assert _row(_OP)[1] == "completed" and _row(_OP)[4] == 5


def test_heartbeat_renews_only_for_the_owning_generation():
    started = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    nonce = started["executor_nonce"]
    _set_heartbeat_age(_OP, 30)
    assert repo.heartbeat(operation_id=_OP, attempt=1, executor_nonce=nonce) is True
    fresh = ops.get_operation(_USER, _OP)
    assert fresh["heartbeat_age_seconds"] < 5
    # Superseded generation / wrong nonce cannot renew.
    assert repo.heartbeat(operation_id=_OP, attempt=2, executor_nonce=nonce) is False
    assert repo.heartbeat(operation_id=_OP, attempt=1, executor_nonce="stranger") is False


def test_restart_after_terminal_bumps_attempt():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.mark_failed(_USER, _OP, error="provider down", attempt=1)
    again = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    assert again["claimed"] is True and again["attempt"] == 2
    assert _row(_OP)[1:3] == ("running", 2)


def test_stats_reports_stuck_and_recent_operations():
    """Slice-2 observability: stats() counts the lease-dead-but-unexpired
    population (stuck) and recent volume/failure counters from real rows."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.start_job_search_operation(
        user_id=_OTHER_USER, role_or_query="accountant", operation_id="op_ownership_it_0002"
    )
    ops.mark_failed(_OTHER_USER, "op_ownership_it_0002", error="provider down", attempt=1)
    _set_heartbeat_age(_OP, ops.LEASE_SECONDS + 30)  # stuck: lease-dead, not yet expired

    data = repo.stats(lease_seconds=ops.LEASE_SECONDS)
    assert data["running"] == 1
    assert data["stuck_lease_dead"] == 1
    assert data["failed_24h"] == 1
    assert data["started_24h"] == 2
    assert data["started_7d"] == 2
    assert data["oldest_active_age_seconds"] is not None


def test_latest_lookup_reads_from_the_shared_store():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    latest = ops.get_latest_job_search_operation(_USER)
    assert latest is not None and latest["operation_id"] == _OP
    status = ops.build_status_response(_USER)
    assert status is not None and status["operation_id"] == _OP

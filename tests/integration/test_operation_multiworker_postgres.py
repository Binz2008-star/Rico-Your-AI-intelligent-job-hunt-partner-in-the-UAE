"""Multi-worker readiness proof for the atomic ownership store — REAL Postgres,
REAL independent OS processes (DEC-20260721-001 slice 4).

Unlike tests/integration/test_operation_ownership_postgres.py (which swaps
_PROCESS_NONCE sequentially in one process), these tests spawn independent
Python processes that race on a multiprocessing.Barrier, so concurrency is
genuine. Each worker resets its own _PROCESS_NONCE at startup — exactly what a
real uvicorn process does — and runs under RICO_OPERATION_STORE=postgres.

Proves the gate criteria for raising worker/instance count:
  1. two workers racing the SAME user+operation_id → exactly one claims, the
     other is honestly refused, and the provider cascade runs ONCE;
  2. a live owner that keeps renewing its heartbeat past the lease CANNOT be
     robbed by a second worker;
  3. an owner that DIES without writing a terminal status frees the operation
     only AFTER the lease expires — the takeover bumps attempt to 2 and a late
     attempt=1 write is refused;
  4. normal completion stops the heartbeat, leaves no false "running" row, and
     the stats/admin view does not report it as stuck;
  5. Postgres down during claim under the MANDATORY mode fails closed — NO
     memory fallback, NO cascade, an honest OperationStoreUnavailable;
  6. two different users on the same operation_id keep independent ownership —
     no leak, no cross-block.

Lease/heartbeat are shortened via TEST-ONLY env vars (production values are
unchanged); no long sleeps beyond one lease window. Requires a real Postgres
via RICO_TEST_DATABASE_URL; skips cleanly when unset.

NOTE: passing this suite is the READINESS proof only. Actually raising Render
workers/instances is a separate production decision AFTER merge + verification,
and REQUIRES RICO_OPERATION_STORE=postgres in the environment.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time
import uuid
from pathlib import Path

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — skipped.",
)

_MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "051_chat_operations.sql"
_LEASE = 2          # seconds — test-only short lease
_HEARTBEAT = 0.3    # seconds — test-only fast heartbeat
_USER = "worker-a@test.com"
_OP = "op_multiworker_0001"

# Fork keeps env + already-imported modules; each worker still re-randomizes
# its nonce and re-reads env at use-time, so it behaves as a distinct process.
_CTX = mp.get_context("fork")


def _raw():
    return psycopg2.connect(TEST_DATABASE_URL)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    conn = _raw()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(_MIGRATION.read_text())
        yield
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clean_table(monkeypatch):
    # The PARENT test process also drives repo.* directly (takeover/stats
    # assertions); point its DATABASE_URL at the test DB and mirror the
    # short-lease env the workers use.
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("RICO_OPERATION_STORE", "postgres")
    monkeypatch.setenv("RICO_OPERATION_LEASE_SECONDS", str(_LEASE))
    monkeypatch.setenv("RICO_OPERATION_HEARTBEAT_SECONDS", str(_HEARTBEAT))
    conn = _raw()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("TRUNCATE chat_operations")
    finally:
        conn.close()
    yield


def _row(operation_id):
    conn = _raw()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, status, attempt, result_count FROM chat_operations "
                "WHERE operation_id = %s", (operation_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


# ── worker entrypoints (module-level so fork/spawn can pickle them) ───────────

def _worker_env(extra_down: bool = False):
    os.environ["RICO_OPERATION_STORE"] = "postgres"
    os.environ["DATABASE_URL"] = "postgresql://bad-host:1/nodb" if extra_down else TEST_DATABASE_URL
    os.environ["RICO_OPERATION_LEASE_SECONDS"] = str(_LEASE)
    os.environ["RICO_OPERATION_HEARTBEAT_SECONDS"] = str(_HEARTBEAT)


def _fresh_nonce():
    from src.services import operation_state as ops
    ops._PROCESS_NONCE = uuid.uuid4().hex  # distinct process identity


def _race_via_real_wrapper(user_id, op_id, barrier, cascade_counter, result_q, hold_seconds=0.0):
    """Drive the REAL cascade-decision wrapper (RicoChatAPI._begin_job_search_
    operation): claimed → 'run cascade'; OperationClaimRefused → skip. This is
    the actual code path that decides whether a provider cascade runs."""
    _worker_env()
    _fresh_nonce()
    from src.rico_chat_api import RicoChatAPI
    from src.services.operation_state import OperationClaimRefused

    api = RicoChatAPI.__new__(RicoChatAPI)
    api._current_operation_id = op_id
    api._current_operation_attempt = None
    try:
        barrier.wait(timeout=30)
        try:
            api._begin_job_search_operation(user_id, "hse manager")
            with cascade_counter.get_lock():
                cascade_counter.value += 1  # a cascade would run here
            # Signal the claim IMMEDIATELY (before any hold) so the parent can
            # race a second worker WHILE this owner is still alive and its
            # heartbeat thread is renewing the lease.
            result_q.put(("claimed", op_id))
            if hold_seconds:
                time.sleep(hold_seconds)  # stay alive, heartbeat keeps renewing
        except OperationClaimRefused:
            result_q.put(("refused", op_id))
    except Exception as exc:  # pragma: no cover - surfaced to the assertion
        result_q.put(("error", f"{type(exc).__name__}: {exc}"))


def _claim_and_die(user_id, op_id, ready_q):
    """Claim then exit WITHOUT a terminal status — simulates worker death.
    The daemon heartbeat thread dies with the process, so the lease expires."""
    _worker_env()
    _fresh_nonce()
    from src.services.operation_state import start_job_search_operation
    op = start_job_search_operation(user_id=user_id, role_or_query="hse manager", operation_id=op_id)
    ready_q.put(("claimed", op["attempt"]))
    # process ends here — no terminal write, heartbeat thread killed


def _claim_complete_normally(user_id, op_id, ready_q):
    _worker_env()
    _fresh_nonce()
    from src.services import operation_state as ops
    op = ops.start_job_search_operation(user_id=user_id, role_or_query="hse manager", operation_id=op_id)
    attempt = op["attempt"]
    ops.mark_completed(user_id, op_id, result_count=4, attempt=attempt)
    # give the heartbeat thread a beat to notice terminal + stop
    time.sleep(_HEARTBEAT * 2)
    ready_q.put(("done", attempt))


def _claim_under_dead_db(user_id, op_id, result_q, cascade_counter):
    """MANDATORY mode + unreachable DB: must fail closed, no cascade."""
    _worker_env(extra_down=True)
    _fresh_nonce()
    from src.services.operation_state import (
        start_job_search_operation, OperationStoreUnavailable,
    )
    try:
        start_job_search_operation(user_id=user_id, role_or_query="hse", operation_id=op_id)
        with cascade_counter.get_lock():
            cascade_counter.value += 1  # MUST NOT happen
        result_q.put(("claimed_wrongly", None))
    except OperationStoreUnavailable:
        result_q.put(("failed_closed", None))
    except Exception as exc:
        result_q.put(("other_error", f"{type(exc).__name__}"))


# ── 1. simultaneous race: one claim, one refuse, cascade runs once ───────────

def test_two_workers_race_cascade_runs_once():
    barrier = _CTX.Barrier(2)
    cascade = _CTX.Value("i", 0)
    q = _CTX.Queue()
    procs = [
        _CTX.Process(target=_race_via_real_wrapper, args=(_USER, _OP, barrier, cascade, q))
        for _ in range(2)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=40)

    outcomes = sorted(q.get() for _ in range(2))
    kinds = sorted(o[0] for o in outcomes)
    assert kinds == ["claimed", "refused"], f"expected one claim + one refuse, got {outcomes}"
    assert cascade.value == 1, f"provider cascade must run exactly once, ran {cascade.value}"
    # The surviving row is a single running operation owned by _USER.
    row = _row(_OP)
    assert row[0] == _USER and row[1] == "running" and row[2] == 1


# ── 2. live owner renewing heartbeat cannot be robbed past the lease ─────────

def test_live_owner_survives_past_lease():
    cascade = _CTX.Value("i", 0)
    q = _CTX.Queue()
    # Owner claims immediately (solo barrier) and holds for > 2 lease windows
    # while its heartbeat thread keeps renewing the lease.
    owner = _CTX.Process(
        target=_race_via_real_wrapper,
        args=(_USER, _OP, _CTX.Barrier(1), cascade, q, _LEASE * 2 + 1),
    )
    owner.start()
    owner_claimed = q.get(timeout=30)  # wait for the owner's claim to land
    assert owner_claimed[0] == "claimed"

    time.sleep(_LEASE + 0.5)  # a full lease passes — but the owner is still alive

    # A second worker attempts the SAME id now; the fresh lease must refuse it.
    q2 = _CTX.Queue()
    second = _CTX.Process(target=_race_via_real_wrapper, args=(_USER, _OP, _CTX.Barrier(1), cascade, q2))
    second.start()
    second.join(timeout=30)
    owner.join(timeout=30)

    assert q2.get(timeout=5)[0] == "refused", "a live, heartbeating owner must not be robbed"
    assert cascade.value == 1, "only the owner's cascade ran"


# ── 3. owner dies without terminal → takeover after lease, attempt bumped ────

def test_dead_owner_taken_over_after_lease_and_late_write_refused():
    from src.repositories import chat_operations_repo as repo

    ready = _CTX.Queue()
    dead = _CTX.Process(target=_claim_and_die, args=(_USER, _OP, ready))
    dead.start()
    dead.join(timeout=30)
    assert ready.get(timeout=5) == ("claimed", 1)
    assert _row(_OP)[1:3] == ("running", 1)

    # Before the lease expires, a takeover claim is refused (owner presumed live).
    early = repo.claim(
        user_id=_USER, operation_id=_OP, role_query="hse",
        executor_nonce="taker", lease_seconds=_LEASE,
    )
    assert early["claimed"] is False

    time.sleep(_LEASE + 0.6)  # lease expires (dead process stopped renewing)

    taken = repo.claim(
        user_id=_USER, operation_id=_OP, role_query="hse",
        executor_nonce="taker", lease_seconds=_LEASE,
    )
    assert taken["claimed"] is True
    assert taken["operation"]["attempt"] == 2

    # The dead owner's late result (attempt=1) is refused in SQL.
    late = repo.update_status(
        user_id=_USER, operation_id=_OP, status="completed",
        result_count=99, attempt=1,
    )
    assert late is None
    assert _row(_OP)[1:3] == ("running", 2)


# ── 4. normal completion: heartbeat stops, no stuck row ──────────────────────

def test_normal_completion_leaves_no_stuck_row():
    from src.repositories import chat_operations_repo as repo

    ready = _CTX.Queue()
    p = _CTX.Process(target=_claim_complete_normally, args=(_USER, _OP, ready))
    p.start()
    p.join(timeout=30)
    assert ready.get(timeout=5)[0] == "done"

    row = _row(_OP)
    assert row[1] == "completed" and row[3] == 4
    # Well past the lease, the stats view must NOT count it as stuck/running.
    time.sleep(_LEASE + 0.3)
    stats = repo.stats(lease_seconds=_LEASE)
    assert stats["running"] == 0
    assert stats["stuck_lease_dead"] == 0
    assert stats["completed_24h"] >= 1


# ── 5. mandatory mode + dead DB during claim → fail closed, no cascade ───────

def test_mandatory_mode_dead_db_fails_closed():
    cascade = _CTX.Value("i", 0)
    q = _CTX.Queue()
    p = _CTX.Process(target=_claim_under_dead_db, args=(_USER, _OP, q, cascade))
    p.start()
    p.join(timeout=30)
    assert q.get(timeout=5) == ("failed_closed", None)
    assert cascade.value == 0, "no cascade may run when the mandatory store is down"
    # Nothing was written to the (real) table either.
    assert _row(_OP) is None


# ── 6. two different users, same operation_id → independent ownership ────────

def test_two_users_same_operation_id_independent():
    barrier = _CTX.Barrier(2)
    cascade = _CTX.Value("i", 0)
    q = _CTX.Queue()
    other = "worker-b@test.com"
    procs = [
        _CTX.Process(target=_race_via_real_wrapper, args=(_USER, _OP, barrier, cascade, q)),
        _CTX.Process(target=_race_via_real_wrapper, args=(other, _OP, barrier, cascade, q)),
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=40)

    outcomes = [q.get(timeout=5) for _ in range(2)]
    # Neither user blocks the other: BOTH claim (independent ownership),
    # so BOTH cascades run — one per user.
    assert all(o[0] == "claimed" for o in outcomes), f"users must not cross-block: {outcomes}"
    assert cascade.value == 2

    # _USER keeps op_id; the foreign user got a DISTINCT minted id (no clobber).
    conn = _raw()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT user_id, operation_id FROM chat_operations ORDER BY user_id")
            rows = cur.fetchall()
    finally:
        conn.close()
    owners = {r[0] for r in rows}
    assert owners == {_USER, other}
    # Exactly one user won the id race and KEEPS _OP; the other got a fresh
    # minted id (no clobber). Which user wins is nondeterministic — the
    # invariant is one-keeps-_OP, one-distinct, both owned independently.
    ids = {r[0]: r[1] for r in rows}
    assert sum(1 for v in ids.values() if v == _OP) == 1, f"exactly one row keeps _OP: {ids}"
    assert len(set(ids.values())) == 2, f"the other user must get a distinct id: {ids}"


# ── monitoring reflects real running / stuck / failed state ──────────────────

def _insert_row(operation_id, user_id, status, heartbeat_age_seconds):
    conn = _raw()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_operations "
                "(operation_id, user_id, op_type, role_query, status, attempt, "
                " executor_nonce, heartbeat_at) "
                "VALUES (%s, %s, 'job_search', 'hse', %s, 1, 'n', "
                "        now() - make_interval(secs => %s))",
                (operation_id, user_id, status, heartbeat_age_seconds),
            )
    finally:
        conn.close()


def test_admin_ops_overview_reflects_real_state():
    """/api/v1/admin/ops/overview's operations section must report running,
    stuck (lease-dead but not yet expired), and failed truthfully from real
    rows — the slice-4 monitoring gate criterion."""
    from src.api.routers import admin_ops
    from src.services.operation_state import LEASE_SECONDS

    _insert_row("op_run_fresh", _USER, "running", heartbeat_age_seconds=1)
    _insert_row("op_run_stuck", _USER, "running", heartbeat_age_seconds=LEASE_SECONDS + 60)
    _insert_row("op_failed_1", _USER, "failed", heartbeat_age_seconds=5)

    section = admin_ops._operations_section()
    assert section["available"] is True
    assert section["store"] == "postgres"
    assert section["running"] == 2            # both running-status rows
    assert section["stuck_lease_dead"] == 1   # only the lease-dead one
    assert section["failed_24h"] == 1
    assert section["oldest_active_age_seconds"] is not None

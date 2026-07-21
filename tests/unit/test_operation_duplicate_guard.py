"""Duplicate-execution guard: one operation_id → one search execution.

Pins the contract added for the duplicate-search fix (2026-07-19 smoke
evidence: a 45s frontend timeout auto-retry re-ran a ~55s provider cascade,
producing two server-side searches and two search_performed events for one
user intent):

1. While an operation is RUNNING/TIMED_OUT and owned by this live process,
   a request re-sending the same operation_id gets an in-progress status
   reply and the pipeline does NOT re-execute — REGARDLESS OF AGE (there is
   no enforced cascade cancellation, so age can never prove death; past
   STALE_AFTER_SECONDS the reply is the honest stale/stuck variant).
2. A COMPLETED operation returns a completed-status reply (result already
   in chat history) — never a re-execution.
3. Ownership releases ONLY on proof of executor death (process-nonce
   mismatch / pre-nonce legacy record) or terminal statuses
   (failed/cancelled/expired); unknown ids and missing operation_id
   execute normally — a legitimate retry is never suppressed.
4. Guard replies are not job_matches: they emit NO analytics and append
   nothing to chat history.

Backend note (DEC-20260721-001 slice 1): these tests pin the MEMORY backend
(tests/conftest.py forces RICO_OPERATION_STORE=memory), which remains the
DB-outage/pre-migration fallback and is safe only with exactly one Render
instance and one uvicorn worker. The atomic shared Postgres store that lifts
that invariant is proven separately in
tests/integration/test_operation_ownership_postgres.py; scaling stays blocked
until the multi-worker validation slice passes on that store.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.rico_chat_api import RicoChatAPI
from src.services import operation_state as ops

_USER = "guard-user@test.com"
_OP = "op_test_guard_0001"
_SEARCH_MSG = "find me hse manager jobs in dubai"


@pytest.fixture(autouse=True)
def _isolated_operation_store(monkeypatch):
    """Fresh in-process store; memory-mirror writes become no-ops so unit
    tests never touch the JSON context files."""
    monkeypatch.setattr(ops, "_OPERATIONS", {})
    monkeypatch.setattr(ops, "_LATEST_BY_USER", {})

    class _NullMemory:
        def set_context(self, *args, **kwargs):
            return None

        def get_context(self, *args, **kwargs):
            return None

    monkeypatch.setattr(ops, "_memory", _NullMemory())


def _process(message=_SEARCH_MSG, operation_id=_OP, user_id=_USER):
    """Run process_message with the heavy pipeline stubbed out; returns
    (response, inner_mock) so tests can assert execution vs guard."""
    api = RicoChatAPI.__new__(RicoChatAPI)
    with patch.object(
        RicoChatAPI, "_process_message_inner",
        return_value={"type": "response", "message": "executed"},
    ) as inner, patch.object(RicoChatAPI, "_record_last_turn"):
        result = api.process_message(
            user_id=user_id, message=message, operation_id=operation_id
        )
    return result, inner


# ── 1. Running → blocked with in-progress status ─────────────────────────────

def test_running_operation_blocks_reexecution():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    result, inner = _process()
    assert not inner.called  # the provider cascade must NOT run again
    assert result["type"] == "search_in_progress"
    assert result["operation_status"] == "running"
    assert result["operation_id"] == _OP
    assert result["success"] is True
    assert result["response_source"] == "operation_guard"


def test_running_guard_replies_in_arabic_for_arabic_turns():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    result, inner = _process(message="ابحث لي عن وظائف في دبي")
    assert not inner.called
    assert result["type"] == "search_in_progress"
    assert "بحث" in result["message"]


# ── 2. Completed → status reply, never re-execution ──────────────────────────

def test_completed_operation_returns_status_not_reexecution():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.mark_completed(_USER, _OP, result_count=5)
    result, inner = _process()
    assert not inner.called
    assert result["type"] == "search_status"
    assert result["operation_status"] == "completed"
    assert result["result_count"] == 5
    assert result["recover_from_history"] is True


# ── 3. Terminal / orphaned / unknown → retry executes normally ───────────────

def test_failed_operation_allows_retry():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.mark_failed(_USER, _OP, error="provider down")
    result, inner = _process()
    assert inner.called
    assert result["message"] == "executed"


def test_fresh_timed_out_still_blocks_reexecution():
    """timed_out is a CLIENT-presentation state (the 45s "are you done"
    flow) — the server execution may still be running, so ownership is
    retained until the MAX_EXECUTION_SECONDS ceiling. This closes the hole
    where a status-followup at t=46s would have re-enabled the blind retry
    while the cascade was still live."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.update_operation(user_id=_USER, operation_id=_OP, status="timed_out")
    result, inner = _process()
    assert not inner.called
    assert result["type"] == "search_in_progress"


def test_stale_operation_cannot_coexist_with_second_execution():
    """Owner invariant (round 3): crossing the stale threshold NEVER releases
    ownership while the executor's process is alive — there is no enforced
    cascade cancellation, so the old execution may still be running and a
    same-id re-send must not start a second provider cascade. The reply is
    the honest stale/stuck message with the manual-recovery pointer."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    very_old = (
        datetime.now(timezone.utc)
        - timedelta(seconds=ops.STALE_AFTER_SECONDS * 10)
    ).isoformat()
    ops._OPERATIONS[_OP]["created_at"] = very_old
    result, inner = _process()
    assert not inner.called  # NO second cascade, no matter the age
    assert result["type"] == "search_in_progress"
    assert result["stale"] is True
    # Ownership was NOT released: the record is still running, not expired.
    assert ops.get_operation(_USER, _OP)["status"] == "running"


def test_stale_timed_out_operation_also_keeps_blocking():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.update_operation(user_id=_USER, operation_id=_OP, status="timed_out")
    ops._OPERATIONS[_OP]["created_at"] = (
        datetime.now(timezone.utc)
        - timedelta(seconds=ops.STALE_AFTER_SECONDS + 1)
    ).isoformat()
    result, inner = _process()
    assert not inner.called
    assert result["type"] == "search_in_progress"
    assert ops.get_operation(_USER, _OP)["status"] == "timed_out"


def test_cancelled_operation_allows_retry():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.update_operation(user_id=_USER, operation_id=_OP, status="cancelled")
    result, inner = _process()
    assert inner.called


# ── Attempt fence: expiry can never yield two completions ────────────────────

def test_superseded_execution_cannot_record_a_late_completion():
    """One operation_id generation completes at most once: after expiry +
    legitimate re-start (attempt bump), the FIRST execution's late
    mark_completed is refused — so 'expired' never permits a second
    execution while the first can still complete."""
    first = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    assert first["attempt"] == 1
    second = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    assert second["attempt"] == 2
    # Stale executor (attempt 1) tries to complete late → refused.
    refused = ops.mark_completed(_USER, _OP, result_count=9, attempt=1)
    assert refused is None
    current = ops.get_operation(_USER, _OP)
    assert current["status"] == "running"
    assert current["result_count"] is None
    # The owning execution (attempt 2) completes normally.
    applied = ops.mark_completed(_USER, _OP, result_count=3, attempt=2)
    assert applied is not None
    assert ops.get_operation(_USER, _OP)["status"] == "completed"
    assert ops.get_operation(_USER, _OP)["result_count"] == 3


def test_attemptless_writes_keep_legacy_behavior():
    """Callers outside the fenced execution path (attempt=None) behave as
    before — e.g. the read-path expired transition."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse", operation_id=_OP
    )
    assert ops.mark_completed(_USER, _OP, result_count=1) is not None


def test_dead_process_record_is_released_and_retry_allowed():
    """Ownership release requires PROOF the executor died: a record stamped
    by another (dead) process nonce — e.g. found in the mirror after a
    restart — expires on read and the retry executes."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops._OPERATIONS[_OP]["process_nonce"] = "dead-process-nonce"
    result, inner = _process()
    assert inner.called
    # The release was RECORDED before execution was allowed (the stubbed
    # pipeline doesn't re-start the operation; a real one would, bumping
    # `attempt` — pinned in test_superseded_execution_cannot_record_a_late_completion).
    assert ops.get_operation(_USER, _OP)["status"] == "expired"


def test_pre_nonce_legacy_record_is_released():
    """Records written before the nonce deploy have no process_nonce — their
    process died with the previous deploy, so they release."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    del ops._OPERATIONS[_OP]["process_nonce"]
    result, inner = _process()
    assert inner.called


def test_unparseable_created_at_still_owned_by_live_process():
    """Liveness is process-based, not clock-based: a garbage created_at on a
    record owned by THIS live process still blocks re-execution (and reads
    as stale for representation)."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops._OPERATIONS[_OP]["created_at"] = "not-a-timestamp"
    result, inner = _process()
    assert not inner.called
    assert result["type"] == "search_in_progress"
    assert result["stale"] is True


def test_unknown_operation_id_executes_normally():
    result, inner = _process(operation_id="op_never_started_01")
    assert inner.called
    assert result["message"] == "executed"


def test_missing_operation_id_executes_normally():
    result, inner = _process(operation_id=None)
    assert inner.called


# ── User isolation ───────────────────────────────────────────────────────────

def test_guard_is_user_scoped():
    """Another user re-sending the same id neither blocks nor leaks state."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    result, inner = _process(user_id="other-user@test.com")
    assert inner.called  # not blocked by someone else's operation


# ── 4. Analytics + history honesty ──────────────────────────────────────────

def test_guard_reply_emits_no_analytics_and_appends_no_history():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    api = RicoChatAPI.__new__(RicoChatAPI)
    with patch.object(
        RicoChatAPI, "_process_message_inner",
        return_value={"type": "response", "message": "executed"},
    ) as inner, patch.object(RicoChatAPI, "_record_last_turn"), patch.object(
        RicoChatAPI, "_append_chat"
    ) as append, patch(
        "src.repositories.analytics_events_repo.record_event"
    ) as record:
        result = api.process_message(
            user_id=_USER, message=_SEARCH_MSG, operation_id=_OP
        )
    assert not inner.called
    assert result["type"] == "search_in_progress"
    assert not append.called  # a duplicate is not a new turn
    assert not record.called  # guard replies never emit search_performed


# ── Helper semantics (used by the status endpoint) ───────────────────────────

def test_is_actively_running_and_stale_semantics():
    op = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse", operation_id=_OP
    )
    # Fresh, owned by this process: live and not stale.
    assert ops.is_actively_running(op) is True
    assert ops.is_stale(op) is False
    # Age does NOT end liveness — only representation flips to stale.
    old = dict(op)
    old["created_at"] = (
        datetime.now(timezone.utc)
        - timedelta(seconds=ops.STALE_AFTER_SECONDS + 1)
    ).isoformat()
    assert ops.is_actively_running(old) is True
    assert ops.is_stale(old) is True
    # A foreign/dead process nonce ends liveness regardless of age.
    foreign = dict(op)
    foreign["process_nonce"] = "dead-process"
    assert ops.is_actively_running(foreign) is False
    # timed_out stays live while owned by this process.
    timed_out = dict(op)
    timed_out["status"] = "timed_out"
    assert ops.is_actively_running(timed_out) is True
    # Terminal ends liveness.
    ops.mark_completed(_USER, _OP, result_count=1)
    assert ops.is_actively_running(ops.get_operation(_USER, _OP)) is False
    assert ops.operation_age_seconds({"created_at": "garbage"}) is None


# ── Process boundary / restart regression (owner items 3-4, round 3) ─────────
#
# Ownership is PROCESS-BASED. These tests pin the accepted production
# invariant: safe with exactly ONE Render instance and ONE uvicorn worker.
# Each simulated process has its own dicts AND its own _PROCESS_NONCE while
# sharing the RicoMemoryStore mirror (same disk). A restart is a new process
# (new nonce, empty dicts) reading the surviving mirror.

class _SharedMirror:
    """Stands in for the on-disk RicoMemoryStore context all processes see."""

    def __init__(self):
        self._data: dict = {}

    def set_context(self, user_id, key, value):
        self._data[(user_id, key)] = value

    def get_context(self, user_id, key):
        return self._data.get((user_id, key))


class _ProcessSim:
    """Swap in a process-local state (dicts + nonce) over a shared mirror."""

    def __init__(self, monkeypatch, mirror, nonce):
        self.monkeypatch = monkeypatch
        self.mirror = mirror
        self.nonce = nonce

    def activate(self):
        self.monkeypatch.setattr(ops, "_OPERATIONS", {})
        self.monkeypatch.setattr(ops, "_LATEST_BY_USER", {})
        self.monkeypatch.setattr(ops, "_memory", self.mirror)
        self.monkeypatch.setattr(ops, "_PROCESS_NONCE", self.nonce)


def test_restart_releases_ownership_of_the_dead_cascade(monkeypatch):
    """After a process restart the old cascade is provably dead: the new
    process treats the mirror's running record as orphaned (expired) and a
    retry executes — retries are never blocked forever."""
    mirror = _SharedMirror()
    before = _ProcessSim(monkeypatch, mirror, nonce="proc-old")
    after_restart = _ProcessSim(monkeypatch, mirror, nonce="proc-new")

    before.activate()
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )

    after_restart.activate()  # old process died with its cascade
    result, inner = _process()
    assert inner.called


def test_restart_preserves_completed_result_retrievability(monkeypatch):
    """A COMPLETED record is terminal — nonce-independent — so the late
    result stays retrievable after a restart via the mirror."""
    mirror = _SharedMirror()
    before = _ProcessSim(monkeypatch, mirror, nonce="proc-old")
    after_restart = _ProcessSim(monkeypatch, mirror, nonce="proc-new")

    before.activate()
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.mark_completed(_USER, _OP, result_count=5, attempt=1)

    after_restart.activate()
    found = ops.get_operation(_USER, _OP)
    assert found is not None and found["status"] == "completed"
    assert found["result_count"] == 5
    result, inner = _process()
    assert not inner.called
    assert result["type"] == "search_status"
    assert result["result_count"] == 5


def test_concurrent_foreign_process_would_release_ownership_UNSAFE_for_multiworker(monkeypatch):
    """Documents WHY the MEMORY FALLBACK keeps multi-worker/multi-instance
    BLOCKED: a concurrently-ALIVE second process is indistinguishable from a
    dead one under nonce ownership, so it would release ownership and run a
    duplicate cascade. The shared Postgres store (migration 050) closes
    exactly this hole — proven by test_concurrent_worker_cannot_steal_live_operation
    in tests/integration/test_operation_ownership_postgres.py — but while the
    fallback can activate (DB outage / migration not applied), the
    single-worker invariant stands until slice-4 validation."""
    mirror = _SharedMirror()
    worker_a = _ProcessSim(monkeypatch, mirror, nonce="proc-a")
    worker_b = _ProcessSim(monkeypatch, mirror, nonce="proc-b")

    worker_a.activate()
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )

    worker_b.activate()
    result, inner = _process()
    assert inner.called  # the documented unsafe release — hence the invariant


def test_other_user_cannot_observe_or_block_across_processes(monkeypatch):
    mirror = _SharedMirror()
    worker_a = _ProcessSim(monkeypatch, mirror, nonce="proc-a")
    worker_b = _ProcessSim(monkeypatch, mirror, nonce="proc-b")

    worker_a.activate()
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )

    worker_b.activate()
    # Cannot observe: the mirror is keyed by user; a foreign lookup is None.
    assert ops.get_operation("intruder@test.com", _OP) is None
    # Cannot be blocked: the intruder's own turn executes normally.
    result, inner = _process(user_id="intruder@test.com")
    assert inner.called

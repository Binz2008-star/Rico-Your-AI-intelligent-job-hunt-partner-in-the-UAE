"""Duplicate-execution guard: one operation_id → one search execution.

Pins the contract added for the duplicate-search fix (2026-07-19 smoke
evidence: a 45s frontend timeout auto-retry re-ran a ~55s provider cascade,
producing two server-side searches and two search_performed events for one
user intent):

1. While an operation is RUNNING (and younger than MAX_EXECUTION_SECONDS),
   a request re-sending the same operation_id gets an in-progress status
   reply and the pipeline does NOT re-execute.
2. A COMPLETED operation returns a completed-status reply (result already
   in chat history) — never a re-execution.
3. Terminal failed/timed_out operations, orphaned running records, unknown
   ids, and requests without an operation_id all execute normally — a
   legitimate retry is never suppressed.
4. Guard replies are not job_matches: they emit NO analytics and append
   nothing to chat history.
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


def test_over_ceiling_timed_out_expires_then_allows_retry():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.update_operation(user_id=_USER, operation_id=_OP, status="timed_out")
    stale = (
        datetime.now(timezone.utc)
        - timedelta(seconds=ops.MAX_EXECUTION_SECONDS + 1)
    ).isoformat()
    ops._OPERATIONS[_OP]["created_at"] = stale
    result, inner = _process()
    assert inner.called
    # Ownership release is RECORDED: the read path transitioned it to expired.
    assert ops.get_operation(_USER, _OP)["status"] == "expired"


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


def test_orphaned_running_operation_allows_retry():
    """A 'running' record older than MAX_EXECUTION_SECONDS is an orphan
    (worker restart / lost thread) — it must never block retries forever."""
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    stale = (
        datetime.now(timezone.utc)
        - timedelta(seconds=ops.MAX_EXECUTION_SECONDS + 1)
    ).isoformat()
    ops._OPERATIONS[_OP]["created_at"] = stale
    result, inner = _process()
    assert inner.called
    assert ops.get_operation(_USER, _OP)["status"] == "expired"


def test_unparseable_created_at_never_blocks():
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops._OPERATIONS[_OP]["created_at"] = "not-a-timestamp"
    result, inner = _process()
    assert inner.called


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

def test_is_actively_running_semantics():
    op = ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse", operation_id=_OP
    )
    assert ops.is_actively_running(op) is True
    ops.mark_completed(_USER, _OP, result_count=1)
    assert ops.is_actively_running(ops.get_operation(_USER, _OP)) is False
    assert ops.operation_age_seconds({"created_at": "garbage"}) is None
    assert ops.is_actively_running({"status": "running", "created_at": "garbage"}) is False
    # timed_out within the ceiling is STILL live (ownership retained).
    fresh_timed_out = {
        "status": "timed_out",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    assert ops.is_actively_running(fresh_timed_out) is True


# ── Multi-worker / restart regression (owner item 6) ─────────────────────────
#
# Simulates the deployment boundary honestly: each "worker" has its OWN
# in-process dicts, while both share the RicoMemoryStore context mirror
# (data/rico/context_*.json — same disk on one instance). A process restart
# is a worker with empty dicts and the surviving mirror.

class _SharedMirror:
    """Stands in for the on-disk RicoMemoryStore context both workers see."""

    def __init__(self):
        self._data: dict = {}

    def set_context(self, user_id, key, value):
        self._data[(user_id, key)] = value

    def get_context(self, user_id, key):
        return self._data.get((user_id, key))


class _WorkerSim:
    """Context manager that swaps in a worker-local process state while
    keeping the shared mirror in place."""

    def __init__(self, monkeypatch, mirror):
        self.monkeypatch = monkeypatch
        self.mirror = mirror

    def activate(self):
        self.monkeypatch.setattr(ops, "_OPERATIONS", {})
        self.monkeypatch.setattr(ops, "_LATEST_BY_USER", {})
        self.monkeypatch.setattr(ops, "_memory", self.mirror)


def test_worker_b_blocks_duplicate_started_on_worker_a(monkeypatch):
    mirror = _SharedMirror()
    worker_a = _WorkerSim(monkeypatch, mirror)
    worker_b = _WorkerSim(monkeypatch, mirror)

    worker_a.activate()
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )

    worker_b.activate()  # fresh dicts — only the mirror is shared
    assert ops._OPERATIONS == {}
    result, inner = _process()
    assert not inner.called  # no second provider cascade on worker B
    assert result["type"] == "search_in_progress"


def test_worker_b_retrieves_completion_recorded_on_worker_a(monkeypatch):
    mirror = _SharedMirror()
    worker_a = _WorkerSim(monkeypatch, mirror)
    worker_b = _WorkerSim(monkeypatch, mirror)

    worker_a.activate()
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )
    ops.mark_completed(_USER, _OP, result_count=5, attempt=1)

    worker_b.activate()
    found = ops.get_operation(_USER, _OP)
    assert found is not None and found["status"] == "completed"
    assert found["result_count"] == 5
    result, inner = _process()
    assert not inner.called
    assert result["type"] == "search_status"
    assert result["result_count"] == 5


def test_restart_preserves_guard_and_result_via_mirror(monkeypatch):
    mirror = _SharedMirror()
    before = _WorkerSim(monkeypatch, mirror)
    after_restart = _WorkerSim(monkeypatch, mirror)

    before.activate()
    ops.start_job_search_operation(
        user_id=_USER, role_or_query="hse manager", operation_id=_OP
    )

    after_restart.activate()  # process died; dicts gone; mirror survived
    result, inner = _process()
    assert not inner.called  # still guarded across the restart
    assert result["type"] == "search_in_progress"


def test_other_user_cannot_observe_or_block_across_workers(monkeypatch):
    mirror = _SharedMirror()
    worker_a = _WorkerSim(monkeypatch, mirror)
    worker_b = _WorkerSim(monkeypatch, mirror)

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

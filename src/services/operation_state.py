"""Chat operation ownership state (duplicate-execution guard).

Two backends, selected per call (DEC-20260721-001 stabilization slice 1):

* **postgres** — the atomic shared store (`chat_operations`, migration 051,
  src/repositories/chat_operations_repo.py). Claims are serialized by a row
  lock and liveness is a **heartbeat lease**: the claiming execution renews
  `heartbeat_at` from a dedicated daemon thread, so a lease that stops being
  renewed is proof the executor process died — valid across ANY number of
  workers/instances, unlike the process-nonce model below. This backend is
  used when `DATABASE_URL` is set (override: RICO_OPERATION_STORE=
  auto|postgres|memory) and the table exists.

* **memory** (legacy fallback) — in-process dict + RicoMemoryStore mirror
  with process-nonce liveness. SAFE ONLY with exactly one Render instance
  and one uvicorn worker: a concurrently-alive second process is
  indistinguishable from a dead one, so it would release ownership and run
  a duplicate provider cascade.

Fallback contract (DEC-20260721-001 slice 4):

* **RICO_OPERATION_STORE=postgres (MANDATORY — the multi-worker-safe mode):**
  a store failure (table missing, connection down) NEVER falls back to the
  memory backend — it raises `OperationStoreUnavailable`, which callers
  surface as an honest 503. A memory fallback under multiple live workers is
  exactly the duplicate-cascade hazard slice 1 removed, so it is forbidden
  here. **Any multi-worker / multi-instance deployment MUST set
  RICO_OPERATION_STORE=postgres.**
* **RICO_OPERATION_STORE=auto (default) / memory:** on a store failure the
  call still falls back to the in-process memory backend — this preserves
  single-worker behavior only, and the single-worker invariant in
  AI_WORKSPACE/OPERATING_RULES.md continues to apply until the deployment is
  switched to the mandatory mode above.

KNOWN LIMITATION — expansion gate stays CLOSED (DEC-20260721-001 slice 4):
the simultaneous-claim race and the mandatory-mode pre-claim outage are safe,
but a Postgres partition that begins AFTER a worker has claimed and started
its provider cascade is NOT yet fully safe. The heartbeat cannot renew during
the partition; if it outlasts the lease, a peer may take over and start a
SECOND cascade while the first is still executing. The attempt fence stops the
first worker's late result WRITE, and the heartbeat now SELF-FENCES (marks
ownership lost — see ownership_lost()), but neither cancels the first worker's
in-flight provider requests. Eliminating that duplicate-cascade window needs
end-to-end cooperative cascade cancellation (a separate, larger PR). Until then
Render worker/instance count MUST stay at 1 — raising it is NOT authorized by
this slice.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

from src.rico_memory import RicoMemoryStore
from src.repositories import chat_operations_repo as _repo
from src.repositories.chat_operations_repo import RepoUnavailable

logger = logging.getLogger(__name__)

OperationStatus = Literal[
    "running", "timed_out", "failed", "completed", "cancelled", "expired"
]

# ── Terminal-ownership model (duplicate-execution guard) ─────────────────────
# running    — a live execution OWNS the operation_id; duplicates are blocked.
# timed_out  — CLIENT-facing presentation state (the 45s "are you done" flow);
#              the server execution may still be running, so ownership is
#              RETAINED.
# completed  — terminal: finished with results; duplicates get a status reply.
# failed     — terminal: execution errored; a retry is legitimate.
# cancelled  — terminal: reserved for explicit user cancellation (no server
#              cancel surface exists yet); a retry is legitimate.
# expired    — terminal: ownership released because the EXECUTOR IS PROVABLY
#              DEAD. Proof differs per backend: postgres = the heartbeat
#              lease stopped being renewed (LEASE_SECONDS of missed beats);
#              memory = process-nonce mismatch. Age alone NEVER releases
#              ownership: the provider cascade has per-call timeouts
#              (jsearch_client._TIMEOUT_S, job_providers._HTTP_TIMEOUT_S) but
#              NO enforced end-to-end cancellation, so a long-running cascade
#              may still be alive and must keep blocking same-id re-execution.
#              Expiry also revokes the dead execution's right to record a
#              result: re-claiming bumps `attempt`, and status writes carrying
#              a stale attempt are refused (in SQL for postgres; in
#              update_operation for memory).
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "expired"})

# Memory-backend invariant (owner-accepted, 2026-07-19; scoped 2026-07-21):
# the process-nonce model is safe only with EXACTLY ONE Render instance and
# ONE uvicorn worker (render.yaml startCommand has no --workers). Within that
# topology, a nonce mismatch is PROOF the executing cascade no longer exists.
# The postgres backend replaces this proof with the heartbeat lease.
_PROCESS_NONCE = uuid.uuid4().hex

CLIENT_TIMEOUT_SECONDS = 45
# STALE REPRESENTATION threshold (NOT an ownership release): past this age a
# still-owned operation is reported as stale/unknown so clients stop waiting
# and offer manual recovery (a NEW turn = a NEW operation_id). The observed
# production cascade is ~55s end-to-end (2026-07-19 smoke).
STALE_AFTER_SECONDS = 120

# Heartbeat lease (postgres backend). The renewal thread is independent of
# the cascade's blocking I/O, so missed renewals mean the process died — not
# that the cascade is merely slow. 60s ≈ 6 missed beats: conservative proof.
#
# These are the PRODUCTION defaults. Multiprocessing integration tests need a
# much shorter lease so a "dead worker" is detectable in seconds, and env vars
# are the only override that crosses a process boundary (monkeypatch does not).
# The overrides are read at USE-TIME via _lease_seconds()/_heartbeat_interval()
# so a child process that re-imports the module still picks them up. They are
# TEST-ONLY and never set in production.
HEARTBEAT_INTERVAL_SECONDS = 10
LEASE_SECONDS = 60
_LEASE_ENV = "RICO_OPERATION_LEASE_SECONDS"           # test-only override
_HEARTBEAT_ENV = "RICO_OPERATION_HEARTBEAT_SECONDS"   # test-only override


def _test_timings_allowed() -> bool:
    """The short-lease overrides are honored ONLY inside an active pytest run.

    pytest sets PYTEST_CURRENT_TEST for the duration of every test (and forked
    child processes inherit it), while production NEVER has it. This guard
    makes the overrides genuinely test-only: a stray/misconfigured
    RICO_OPERATION_LEASE_SECONDS in a production environment is IGNORED and can
    never shrink the lease to a takeover-racy value."""
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _lease_seconds() -> int:
    if _test_timings_allowed():
        raw = os.getenv(_LEASE_ENV)
        if raw:
            try:
                return max(1, int(raw))
            except ValueError:
                pass
    return LEASE_SECONDS


def _heartbeat_interval() -> float:
    if _test_timings_allowed():
        raw = os.getenv(_HEARTBEAT_ENV)
        if raw:
            try:
                return max(0.05, float(raw))
            except ValueError:
                pass
    return HEARTBEAT_INTERVAL_SECONDS


# Backend override: auto (default; postgres when DATABASE_URL is set),
# postgres (force), memory (force legacy — used by unit tests).
_STORE_ENV = "RICO_OPERATION_STORE"

MAX_IN_MEMORY_OPERATIONS = 500
_LATEST_JOB_SEARCH_KEY = "latest_job_search_operation"
_OPERATION_KEY_PREFIX = "operation:"
_OPERATIONS: dict[str, dict[str, Any]] = {}
_LATEST_BY_USER: dict[str, str] = {}
_memory = RicoMemoryStore()

# Live heartbeat threads keyed by (operation_id, attempt) → stop event.
_HEARTBEAT_STOPS: dict[tuple[str, int], threading.Event] = {}
_HEARTBEAT_LOCK = threading.Lock()

# PREPARATORY ownership-loss signal (DEC-20260721-001 slice 4). An
# (operation_id, attempt) lands here when THIS worker can no longer prove it
# holds the lease — its heartbeat could not renew for longer than the lease
# (DB partition) or the row was taken over/expired. It is a cooperative
# checkpoint: `ownership_lost()` lets a future executor stop recording / stop
# issuing provider calls. THERE IS NO EXECUTOR CONSUMER IN THIS PR — the actual
# in-flight provider cascade is not yet cancelled, so the post-claim-partition
# duplicate-cascade WINDOW is NOT eliminated and the expansion gate stays
# CLOSED. This state has an explicit lifecycle so it cannot leak:
#   * cleared for (op, attempt) when that generation reaches a terminal status
#     or is restarted/taken over (see _discard_ownership_loss / _stop_heartbeats);
#   * hard-capped at _MAX_LOST_OWNERSHIP with FIFO eviction as a safety valve.
_LOST_OWNERSHIP: "OrderedDict[tuple[str, int], None]" = OrderedDict()
_MAX_LOST_OWNERSHIP = 2048


def _mark_ownership_lost(operation_id: str, attempt: int) -> None:
    key = (operation_id, int(attempt))
    with _HEARTBEAT_LOCK:
        _LOST_OWNERSHIP[key] = None
        _LOST_OWNERSHIP.move_to_end(key)
        while len(_LOST_OWNERSHIP) > _MAX_LOST_OWNERSHIP:
            _LOST_OWNERSHIP.popitem(last=False)  # evict oldest (FIFO safety valve)


def _discard_ownership_loss(operation_id: str, attempt: int | None = None) -> None:
    """Remove ownership-loss entries once they can no longer be needed: a
    specific generation on terminal write, or every generation of an op when
    its heartbeats are stopped."""
    with _HEARTBEAT_LOCK:
        if attempt is not None:
            _LOST_OWNERSHIP.pop((operation_id, int(attempt)), None)
        else:
            for key in [k for k in _LOST_OWNERSHIP if k[0] == operation_id]:
                _LOST_OWNERSHIP.pop(key, None)


def ownership_lost(operation_id: str, attempt: int) -> bool:
    """True when this worker's heartbeat self-fenced (lease unrenewable past
    the lease window, or the row was taken over). Cooperative checkpoint for a
    future executor consumer; see the _LOST_OWNERSHIP note above."""
    with _HEARTBEAT_LOCK:
        return (operation_id, int(attempt)) in _LOST_OWNERSHIP


class OperationClaimRefused(Exception):
    """An atomic claim was refused: a live execution owns this operation_id.

    Raised by callers (rico_chat_api._begin_job_search_operation) so the
    request unwinds to an honest in-progress reply instead of running a
    duplicate provider cascade. Carries the refusing (live) operation."""

    def __init__(self, operation: dict[str, Any]):
        super().__init__("operation claim refused: live execution owns this id")
        self.operation = operation


class OperationStoreUnavailable(Exception):
    """The mandatory Postgres ownership store is unreachable (fail-closed).

    Raised ONLY under RICO_OPERATION_STORE=postgres (the multi-worker-safe
    mode) when the shared store cannot be reached — table missing, connection
    down. There is deliberately NO memory fallback in this mode: a
    second live worker + an in-process store would run a duplicate provider
    cascade (the exact hazard slice 1 removed). Callers must surface this as
    an honest temporary-unavailable (503), NEVER as a 500 and NEVER by
    executing the job-search cascade unguarded. (DEC-20260721-001 slice 4.)"""


def _db_mode() -> bool:
    """True when the Postgres store should be consulted for this call."""
    mode = (os.getenv(_STORE_ENV) or "auto").strip().lower()
    if mode == "memory":
        return False
    if mode == "postgres":
        return True
    return bool(os.getenv("DATABASE_URL"))


def _mandatory_db() -> bool:
    """True when Postgres is MANDATORY (RICO_OPERATION_STORE=postgres).

    In this mode a RepoUnavailable must fail closed (raise
    OperationStoreUnavailable) instead of falling back to the in-process
    memory store. Multi-worker/multi-instance deployment REQUIRES this mode —
    the `auto` default preserves single-worker memory-fallback compatibility
    but is NOT safe beyond one process (see the module docstring)."""
    return (os.getenv(_STORE_ENV) or "auto").strip().lower() == "postgres"


def _on_repo_unavailable(exc: "RepoUnavailable", op: str) -> None:
    """Mandatory mode: fail closed. Auto mode: log and let the caller fall
    back to memory (single-worker only)."""
    if _mandatory_db():
        logger.error(
            "operation_state: mandatory Postgres store unavailable during %s — "
            "failing closed (no memory fallback): %s", op, exc,
        )
        raise OperationStoreUnavailable(str(exc)) from exc
    logger.warning(
        "operation_state: postgres store unavailable during %s, using memory "
        "fallback (single-worker only): %s", op, exc,
    )


def new_operation_id() -> str:
    return f"op_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _operation_key(operation_id: str) -> str:
    return f"{_OPERATION_KEY_PREFIX}{operation_id}"


# ── Heartbeat lease management (postgres backend) ────────────────────────────

def _start_heartbeat(operation_id: str, attempt: int, nonce: str) -> None:
    stop = threading.Event()
    with _HEARTBEAT_LOCK:
        _HEARTBEAT_STOPS[(operation_id, attempt)] = stop

    def _run() -> None:
        first_failure_at: float | None = None
        try:
            while not stop.wait(_heartbeat_interval()):
                try:
                    renewed = _repo.heartbeat(
                        operation_id=operation_id, attempt=attempt, executor_nonce=nonce
                    )
                except RepoUnavailable:
                    # DB partition: we cannot renew, so we cannot prove we still
                    # hold the lease. If the outage outlasts the lease, a peer
                    # may legitimately take over — SELF-FENCE (mark ownership
                    # lost) so a cooperating executor stops recording. This
                    # bounds, but does not yet eliminate, the duplicate-cascade
                    # window (full cascade cancellation is a follow-up PR).
                    now = time.monotonic()
                    if first_failure_at is None:
                        first_failure_at = now
                    elif now - first_failure_at >= _lease_seconds():
                        _mark_ownership_lost(operation_id, attempt)
                        logger.error(
                            "operation_state: heartbeat unrenewable for op=%s attempt=%s "
                            "beyond lease — self-fencing (ownership presumed lost to a peer)",
                            operation_id, attempt,
                        )
                        break
                    continue
                first_failure_at = None  # a successful renew clears the streak
                if not renewed:
                    # The UPDATE matched 0 rows: the row was taken over, expired,
                    # or reached a terminal status — we no longer own it.
                    _mark_ownership_lost(operation_id, attempt)
                    break
        finally:
            with _HEARTBEAT_LOCK:
                _HEARTBEAT_STOPS.pop((operation_id, attempt), None)

    threading.Thread(
        target=_run, daemon=True, name=f"op-heartbeat-{operation_id[:16]}"
    ).start()


def _stop_heartbeats(operation_id: str) -> None:
    with _HEARTBEAT_LOCK:
        keys = [k for k in _HEARTBEAT_STOPS if k[0] == operation_id]
        for key in keys:
            _HEARTBEAT_STOPS.pop(key).set()
    # The op just reached a terminal status — no generation of it can still
    # need its ownership-loss signal; drop them all so the state cannot grow.
    _discard_ownership_loss(operation_id)


# ── Memory backend internals (legacy fallback) ───────────────────────────────

def _persist(user_id: str, operation: dict[str, Any]) -> None:
    _OPERATIONS[operation["operation_id"]] = dict(operation)
    _LATEST_BY_USER[user_id] = operation["operation_id"]
    _prune_in_memory_operations()
    try:
        _memory.set_context(user_id, _operation_key(operation["operation_id"]), operation)
        _memory.set_context(user_id, _LATEST_JOB_SEARCH_KEY, operation["operation_id"])
    except Exception:
        pass


def _prune_in_memory_operations() -> None:
    if len(_OPERATIONS) <= MAX_IN_MEMORY_OPERATIONS:
        return
    ordered = sorted(
        _OPERATIONS.items(),
        key=lambda item: str(item[1].get("updated_at") or item[1].get("created_at") or ""),
    )
    for op_id, operation in ordered[: len(_OPERATIONS) - MAX_IN_MEMORY_OPERATIONS]:
        _OPERATIONS.pop(op_id, None)
        owner = str(operation.get("user_id") or "")
        if _LATEST_BY_USER.get(owner) == op_id:
            _LATEST_BY_USER.pop(owner, None)


def _memory_start(
    user_id: str, role_or_query: str, operation_id: str | None
) -> dict[str, Any]:
    op_id = operation_id or new_operation_id()
    # Re-starting an existing operation_id (legitimate retry after a terminal
    # outcome) bumps `attempt`, which revokes the previous execution's right
    # to record a result — update_operation refuses stale-attempt writes.
    previous = _memory_get(user_id, op_id) if operation_id else None
    attempt = int(previous.get("attempt") or 1) + 1 if previous else 1
    created_at = _now()
    operation = {
        "operation_id": op_id,
        "user_id": user_id,
        "type": "job_search",
        "role": role_or_query,
        "query": role_or_query,
        "status": "running",
        "attempt": attempt,
        "process_nonce": _PROCESS_NONCE,
        "result_count": None,
        "error": None,
        "created_at": created_at,
        "updated_at": _now(),
        "completed_at": None,
        "claimed": True,
    }
    _persist(user_id, operation)
    return operation


def _memory_get(user_id: str, operation_id: str) -> dict[str, Any] | None:
    operation = _OPERATIONS.get(operation_id)
    if operation:
        return dict(operation) if operation.get("user_id") == user_id else None
    try:
        loaded = _memory.get_context(user_id, _operation_key(operation_id))
    except Exception:
        loaded = None
    if not isinstance(loaded, dict) or loaded.get("user_id") != user_id:
        return None
    return dict(loaded)


# ── Public API ───────────────────────────────────────────────────────────────

def start_job_search_operation(
    *,
    user_id: str,
    role_or_query: str,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Claim an operation for execution.

    postgres backend: the claim is ATOMIC. The returned operation carries
    ``claimed``: True when this caller owns the execution; False when a live
    execution (same user, fresh lease) already owns the id — the caller must
    NOT run the cascade (raise OperationClaimRefused). A live FOREIGN user's
    id is never taken over and never leaked: a fresh operation_id is minted
    and claimed instead (matching the memory backend's "another user neither
    blocks nor observes" contract).

    memory backend: legacy last-writer-wins semantics, always claimed=True
    (safe only under the single-worker invariant — see module docstring).
    """
    if _db_mode():
        op_id = operation_id or new_operation_id()
        try:
            outcome = _repo.claim(
                user_id=user_id,
                operation_id=op_id,
                role_query=role_or_query,
                executor_nonce=_PROCESS_NONCE,
                lease_seconds=_lease_seconds(),
            )
            if not outcome["claimed"] and outcome["reason"] == "refused_foreign":
                # Never blocked by (or informed about) someone else's op.
                outcome = _repo.claim(
                    user_id=user_id,
                    operation_id=new_operation_id(),
                    role_query=role_or_query,
                    executor_nonce=_PROCESS_NONCE,
                    lease_seconds=_lease_seconds(),
                )
            if outcome["claimed"]:
                operation = dict(outcome["operation"])
                operation["claimed"] = True
                _start_heartbeat(
                    operation["operation_id"], int(operation["attempt"]), _PROCESS_NONCE
                )
                return operation
            refused = dict(outcome["operation"] or {})
            refused["claimed"] = False
            return refused
        except RepoUnavailable as exc:
            _on_repo_unavailable(exc, "start_job_search_operation")  # raises in mandatory mode
    return _memory_start(user_id, role_or_query, operation_id)


def get_operation(user_id: str, operation_id: str) -> dict[str, Any] | None:
    if _db_mode():
        try:
            found = _repo.get(user_id, operation_id)
            if found is not None:
                return found
            # Row genuinely absent in the shared store — do NOT consult memory
            # in mandatory mode (it would resurrect stale in-process state).
            if _mandatory_db():
                return None
        except RepoUnavailable as exc:
            _on_repo_unavailable(exc, "get_operation")  # raises in mandatory mode
    return _memory_get(user_id, operation_id)


def get_latest_job_search_operation(user_id: str) -> dict[str, Any] | None:
    if _db_mode():
        try:
            found = _repo.get_latest(user_id)
            if found is not None:
                return found
            if _mandatory_db():
                return None
        except RepoUnavailable as exc:
            _on_repo_unavailable(exc, "get_latest_job_search_operation")  # raises in mandatory mode
    op_id = _LATEST_BY_USER.get(user_id)
    if not op_id:
        try:
            op_id = _memory.get_context(user_id, _LATEST_JOB_SEARCH_KEY)
        except Exception:
            op_id = None
    if not op_id:
        return None
    return _memory_get(user_id, str(op_id))


def update_operation(
    *,
    user_id: str,
    operation_id: str,
    status: OperationStatus,
    result_count: int | None = None,
    error: str | None = None,
    attempt: int | None = None,
) -> dict[str, Any] | None:
    if _db_mode():
        try:
            updated = _repo.update_status(
                user_id=user_id,
                operation_id=operation_id,
                status=status,
                result_count=result_count,
                error=error,
                attempt=attempt,
            )
            if updated is not None and status in TERMINAL_STATUSES:
                _stop_heartbeats(operation_id)
            if updated is not None:
                return updated
            # Distinguish "row absent → try memory fallback" from "fence or
            # completed-protection rejected the write → refuse".
            try:
                if _repo.get(user_id, operation_id) is not None:
                    logger.info(
                        "operation_state: refused fenced write op=%s status=%s attempt=%s",
                        operation_id, status, attempt,
                    )
                    return None
            except RepoUnavailable as exc:
                _on_repo_unavailable(exc, "update_operation.recheck")  # raises in mandatory mode
            # Row absent in the shared store; in mandatory mode never fall
            # through to the memory store.
            if _mandatory_db():
                return None
        except RepoUnavailable as exc:
            _on_repo_unavailable(exc, "update_operation")  # raises in mandatory mode

    operation = _memory_get(user_id, operation_id)
    if not operation:
        return None
    # Attempt fencing: an executor whose operation generation was superseded
    # (expiry → legitimate re-start bumped `attempt`) may no longer record an
    # outcome — otherwise a late first execution could complete on top of the
    # second one, yielding two completions for one operation_id.
    if attempt is not None and int(operation.get("attempt") or 1) != int(attempt):
        logger.info(
            "operation_state: refused stale-attempt write op=%s status=%s "
            "stale_attempt=%s current_attempt=%s",
            operation_id, status, attempt, operation.get("attempt"),
        )
        return None
    operation["status"] = status
    operation["updated_at"] = _now()
    if result_count is not None:
        operation["result_count"] = result_count
    if error is not None:
        operation["error"] = error
    if status in TERMINAL_STATUSES:
        operation["completed_at"] = operation["updated_at"]
    _persist(user_id, operation)
    return operation


def mark_completed(
    user_id: str, operation_id: str, result_count: int, attempt: int | None = None
) -> dict[str, Any] | None:
    return update_operation(
        user_id=user_id,
        operation_id=operation_id,
        status="completed",
        result_count=result_count,
        error=None,
        attempt=attempt,
    )


def mark_failed(
    user_id: str, operation_id: str, error: str, attempt: int | None = None
) -> dict[str, Any] | None:
    operation = get_operation(user_id, operation_id)
    if operation and operation.get("status") == "completed":
        return operation
    return update_operation(
        user_id=user_id,
        operation_id=operation_id,
        status="failed",
        error=error,
        attempt=attempt,
    )


def operation_age_seconds(operation: dict[str, Any]) -> float | None:
    """Seconds since the operation was created; None when unparseable."""
    try:
        created_at = datetime.fromisoformat(str(operation["created_at"]).replace("Z", "+00:00"))
    except Exception:
        return None
    return (datetime.now(timezone.utc) - created_at).total_seconds()


def is_actively_running(operation: dict[str, Any]) -> bool:
    """True while this operation's execution must be treated as live.

    Liveness is never clock-of-creation based (there is no enforced
    end-to-end cascade cancellation, so age can never prove death). The
    proof-of-life differs per record origin:

    * shared-store records (``ownership == "db"``): the heartbeat lease —
      fresh (< LEASE_SECONDS since the last renewal) means some process's
      executor is alive, REGARDLESS of which process this is. Works across
      any number of workers.
    * memory records: the process nonce — a running/timed_out record created
      by THIS process may still have its cascade on a thread here; a record
      from a different nonce is dead under the single-worker invariant.
    """
    if operation.get("status") not in ("running", "timed_out"):
        return False
    if operation.get("ownership") == "db":
        age = operation.get("heartbeat_age_seconds")
        return age is not None and float(age) < _lease_seconds()
    return operation.get("process_nonce") == _PROCESS_NONCE


def is_stale(operation: dict[str, Any]) -> bool:
    """Representation flag: still OWNED (live) but past the
    STALE_AFTER_SECONDS threshold or age-unprovable — clients should stop
    waiting and offer manual recovery (a new turn), while same-id
    re-execution stays blocked."""
    if not is_actively_running(operation):
        return False
    age = operation_age_seconds(operation)
    return age is None or age >= STALE_AFTER_SECONDS


def expire_if_orphaned(user_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    """Release ownership ONLY when the executor is provably dead.

    Called on guard/status READ paths. Proof of death per record origin:
    shared-store records — the heartbeat lease expired (re-checked atomically
    inside the UPDATE against the database clock, so a concurrent renewal
    wins); memory records — a process-nonce mismatch (or a pre-nonce legacy
    record) under the single-worker invariant. Combined with the attempt
    fence (a re-claim bumps `attempt`), one operation_id generation can
    complete at most once. Age alone NEVER triggers this transition.
    """
    if operation.get("status") not in ("running", "timed_out"):
        return operation
    if operation.get("ownership") == "db":
        if is_actively_running(operation):
            return operation
        try:
            expired = _repo.expire_if_lease_dead(
                user_id=user_id,
                operation_id=str(operation.get("operation_id")),
                lease_seconds=_lease_seconds(),
            )
            return expired or get_operation(user_id, str(operation.get("operation_id"))) or operation
        except RepoUnavailable:
            return operation
    if operation.get("process_nonce") == _PROCESS_NONCE:
        return operation
    updated = update_operation(
        user_id=user_id,
        operation_id=str(operation.get("operation_id")),
        status="expired",
    )
    return updated or operation


def maybe_mark_timed_out(user_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    if operation.get("status") != "running":
        return operation
    try:
        created_at = datetime.fromisoformat(str(operation["created_at"]).replace("Z", "+00:00"))
    except Exception:
        return operation
    age = (datetime.now(timezone.utc) - created_at).total_seconds()
    if age < CLIENT_TIMEOUT_SECONDS:
        return operation
    updated = update_operation(
        user_id=user_id,
        operation_id=str(operation["operation_id"]),
        status="timed_out",
    )
    return updated or operation


def is_status_followup(message: str) -> bool:
    text = " ".join((message or "").strip().lower().split()).strip(" ؟?!.,")
    return text in {
        "are you done",
        "are u done",
        "is it finished",
        "is it done",
        "done",
        "finished",
        "check status",
        "status",
        "خلصت",
        "انتهيت",
        "شو صار",
    }


def build_status_response(user_id: str) -> dict[str, Any] | None:
    try:
        operation = get_latest_job_search_operation(user_id)
    except OperationStoreUnavailable:
        # Mandatory store down during a status check ("are you done?"). Answer
        # honestly rather than 500 — we simply cannot read status right now.
        return {
            "type": "service_unavailable",
            "intent": "operation_status",
            "success": False,
            "service_unavailable": True,
            "response_source": "operation_store_unavailable",
            "error": "operation_store_unavailable",
            "message": (
                "The service is temporarily unavailable — I can't check your "
                "search status right now. Please try again shortly."
            ),
        }
    if not operation:
        return None
    operation = maybe_mark_timed_out(user_id, operation)
    role = operation.get("role") or operation.get("query") or "your last job search"
    status = operation.get("status")
    count = operation.get("result_count")

    if status == "completed":
        message = f"The job search for {role} completed with {count or 0} result(s)."
    elif status == "failed":
        message = f"The job search for {role} failed. Please try again or use a narrower role."
    elif status == "timed_out":
        message = f"The job search for {role} timed out. It may still finish if the server kept the request alive."
    else:
        message = f"Still searching for {role}. I have not received a final result yet."

    return {
        "type": "operation_status",
        "intent": "operation_status",
        "message": message,
        "response_source": "operation_state",
        "operation_id": operation.get("operation_id"),
        "operation_status": status,
        "operation_type": operation.get("type"),
        "role": role,
        "result_count": count,
        "error": "job_search_failed" if status == "failed" else None,
    }


def reset_for_tests() -> None:
    _OPERATIONS.clear()
    _LATEST_BY_USER.clear()
    with _HEARTBEAT_LOCK:
        for stop in _HEARTBEAT_STOPS.values():
            stop.set()
        _HEARTBEAT_STOPS.clear()
        _LOST_OWNERSHIP.clear()

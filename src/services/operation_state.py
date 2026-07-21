"""Chat operation ownership state (duplicate-execution guard).

Two backends, selected per call (DEC-20260721-001 stabilization slice 1):

* **postgres** — the atomic shared store (`chat_operations`, migration 051,
  src/repositories/chat_operations_repo.py). Claims are serialized by a row
  lock and liveness is a **heartbeat lease**: the claiming execution renews
  `heartbeat_at` from a dedicated daemon thread, so a lease that stops being
  renewed is proof the executor process died — valid across ANY number of
  workers/instances, unlike the process-nonce model below. This backend is
  used when `DATABASE_URL` is set (override: RICO_OPERATION_STORE=
  auto|postgres|memory) and the table exists; any infrastructure failure
  falls back to the memory backend for that call.

* **memory** (legacy fallback) — in-process dict + RicoMemoryStore mirror
  with process-nonce liveness. SAFE ONLY with exactly one Render instance
  and one uvicorn worker: a concurrently-alive second process is
  indistinguishable from a dead one, so it would release ownership and run
  a duplicate provider cascade. While this fallback can be active (DB outage
  or migration 051 not applied), the single-worker production invariant in
  AI_WORKSPACE/OPERATING_RULES.md still stands. Scaling remains BLOCKED
  until the multi-worker validation slice (DEC-20260721-001 slice 4) passes
  on the postgres backend.
"""
from __future__ import annotations

import logging
import os
import threading
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
HEARTBEAT_INTERVAL_SECONDS = 10
LEASE_SECONDS = 60

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


class OperationClaimRefused(Exception):
    """An atomic claim was refused: a live execution owns this operation_id.

    Raised by callers (rico_chat_api._begin_job_search_operation) so the
    request unwinds to an honest in-progress reply instead of running a
    duplicate provider cascade. Carries the refusing (live) operation."""

    def __init__(self, operation: dict[str, Any]):
        super().__init__("operation claim refused: live execution owns this id")
        self.operation = operation


def _db_mode() -> bool:
    mode = (os.getenv(_STORE_ENV) or "auto").strip().lower()
    if mode == "memory":
        return False
    if mode == "postgres":
        return True
    return bool(os.getenv("DATABASE_URL"))


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
        try:
            while not stop.wait(HEARTBEAT_INTERVAL_SECONDS):
                try:
                    renewed = _repo.heartbeat(
                        operation_id=operation_id, attempt=attempt, executor_nonce=nonce
                    )
                except RepoUnavailable:
                    # Transient DB trouble: keep trying until terminal/stopped —
                    # an unrenewed lease self-resolves via takeover anyway.
                    continue
                if not renewed:  # superseded or terminal — stop renewing
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
                lease_seconds=LEASE_SECONDS,
            )
            if not outcome["claimed"] and outcome["reason"] == "refused_foreign":
                # Never blocked by (or informed about) someone else's op.
                outcome = _repo.claim(
                    user_id=user_id,
                    operation_id=new_operation_id(),
                    role_query=role_or_query,
                    executor_nonce=_PROCESS_NONCE,
                    lease_seconds=LEASE_SECONDS,
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
            logger.warning("operation_state: postgres store unavailable, using memory fallback: %s", exc)
    return _memory_start(user_id, role_or_query, operation_id)


def get_operation(user_id: str, operation_id: str) -> dict[str, Any] | None:
    if _db_mode():
        try:
            found = _repo.get(user_id, operation_id)
            if found is not None:
                return found
        except RepoUnavailable:
            pass
    return _memory_get(user_id, operation_id)


def get_latest_job_search_operation(user_id: str) -> dict[str, Any] | None:
    if _db_mode():
        try:
            found = _repo.get_latest(user_id)
            if found is not None:
                return found
        except RepoUnavailable:
            pass
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
            except RepoUnavailable:
                pass
        except RepoUnavailable as exc:
            logger.warning("operation_state: postgres store unavailable, using memory fallback: %s", exc)

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
        return age is not None and float(age) < LEASE_SECONDS
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
                lease_seconds=LEASE_SECONDS,
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
    operation = get_latest_job_search_operation(user_id)
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

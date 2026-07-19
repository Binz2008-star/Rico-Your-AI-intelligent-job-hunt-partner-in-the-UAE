"""Lightweight chat operation state for timeout recovery.

This intentionally avoids schema changes. State is kept in-process for fast
same-worker reads and mirrored to the existing Rico JSON context when enabled.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

from src.rico_memory import RicoMemoryStore

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
# expired    — terminal: ownership released because the EXECUTOR'S PROCESS IS
#              DEAD (process-nonce mismatch — see below). Age alone NEVER
#              releases ownership: the provider cascade has per-call timeouts
#              (jsearch_client._TIMEOUT_S, job_providers._HTTP_TIMEOUT_S) but
#              NO enforced end-to-end cancellation, so a long-running cascade
#              may still be alive and must keep blocking same-id re-execution
#              — otherwise two concurrent cascades could run for one turn.
#              Expiry also revokes the dead execution's right to record a
#              result: re-execution bumps the record's `attempt`, and
#              update_operation refuses writes carrying a stale attempt.
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "expired"})

# PRODUCTION INVARIANT (owner-accepted, 2026-07-19): this ownership model is
# safe only with EXACTLY ONE Render instance and ONE uvicorn worker
# (render.yaml startCommand has no --workers). Within that topology, a
# process-nonce mismatch is PROOF the executing cascade no longer exists.
# Increasing workers/instances is BLOCKED until ownership moves to an atomic
# shared store (Redis/Postgres) — see AI_WORKSPACE/OPERATING_RULES.md.
_PROCESS_NONCE = uuid.uuid4().hex

CLIENT_TIMEOUT_SECONDS = 45
# STALE REPRESENTATION threshold (NOT an ownership release): past this age a
# still-owned operation is reported as stale/unknown so clients stop waiting
# and offer manual recovery (a NEW turn = a NEW operation_id). The observed
# production cascade is ~55s end-to-end (2026-07-19 smoke).
STALE_AFTER_SECONDS = 120
MAX_IN_MEMORY_OPERATIONS = 500
_LATEST_JOB_SEARCH_KEY = "latest_job_search_operation"
_OPERATION_KEY_PREFIX = "operation:"
_OPERATIONS: dict[str, dict[str, Any]] = {}
_LATEST_BY_USER: dict[str, str] = {}
_memory = RicoMemoryStore()


def new_operation_id() -> str:
    return f"op_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _operation_key(operation_id: str) -> str:
    return f"{_OPERATION_KEY_PREFIX}{operation_id}"


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


def start_job_search_operation(
    *,
    user_id: str,
    role_or_query: str,
    operation_id: str | None = None,
) -> dict[str, Any]:
    op_id = operation_id or new_operation_id()
    # Re-starting an existing operation_id (legitimate retry after a terminal
    # outcome) bumps `attempt`, which revokes the previous execution's right
    # to record a result — update_operation refuses stale-attempt writes.
    previous = get_operation(user_id, op_id) if operation_id else None
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
    }
    _persist(user_id, operation)
    return operation


def get_operation(user_id: str, operation_id: str) -> dict[str, Any] | None:
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


def get_latest_job_search_operation(user_id: str) -> dict[str, Any] | None:
    op_id = _LATEST_BY_USER.get(user_id)
    if not op_id:
        try:
            op_id = _memory.get_context(user_id, _LATEST_JOB_SEARCH_KEY)
        except Exception:
            op_id = None
    if not op_id:
        return None
    return get_operation(user_id, str(op_id))


def update_operation(
    *,
    user_id: str,
    operation_id: str,
    status: OperationStatus,
    result_count: int | None = None,
    error: str | None = None,
    attempt: int | None = None,
) -> dict[str, Any] | None:
    operation = get_operation(user_id, operation_id)
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

    Liveness is PROCESS-BASED, not clock-based: a running/timed_out record
    created by THIS process may still have its cascade on a thread here, so
    it keeps blocking same-id re-execution no matter how old it is (there is
    no enforced end-to-end cascade cancellation to make an age bound safe).
    A record from a DIFFERENT process nonce is not live — under the accepted
    one-instance/one-worker topology that process is dead, and its cascade
    died with it.
    """
    if operation.get("status") not in ("running", "timed_out"):
        return False
    return operation.get("process_nonce") == _PROCESS_NONCE


def is_stale(operation: dict[str, Any]) -> bool:
    """Representation flag: still OWNED (live in this process) but past the
    STALE_AFTER_SECONDS threshold or age-unprovable — clients should stop
    waiting and offer manual recovery (a new turn), while same-id
    re-execution stays blocked."""
    if not is_actively_running(operation):
        return False
    age = operation_age_seconds(operation)
    return age is None or age >= STALE_AFTER_SECONDS


def expire_if_orphaned(user_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    """Release ownership ONLY when the executor's process is provably dead.

    Called on guard/status READ paths. A running/timed_out record whose
    process_nonce differs from this process's nonce (or is absent — written
    by a pre-nonce deploy) cannot have a live cascade under the accepted
    one-instance/one-worker topology: transition it to the terminal
    "expired" state. Combined with the attempt fence in update_operation (a
    re-start bumps `attempt`), one operation_id generation can complete at
    most once. Age alone NEVER triggers this transition.
    """
    if operation.get("status") not in ("running", "timed_out"):
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

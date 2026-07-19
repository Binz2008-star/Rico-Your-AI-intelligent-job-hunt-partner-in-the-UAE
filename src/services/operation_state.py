"""Lightweight chat operation state for timeout recovery.

This intentionally avoids schema changes. State is kept in-process for fast
same-worker reads and mirrored to the existing Rico JSON context when enabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
import uuid

from src.rico_memory import RicoMemoryStore

OperationStatus = Literal["running", "timed_out", "failed", "completed"]

CLIENT_TIMEOUT_SECONDS = 45
# Duplicate-execution guard ceiling: past this age a "running" record is
# treated as an orphan (worker restart, lost thread) rather than a live
# execution, so retries are never blocked forever. The production provider
# cascade has been observed at ~55s end-to-end (2026-07-19 smoke), so 120s
# comfortably covers a slow-but-alive search.
MAX_EXECUTION_SECONDS = 120
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
    created_at = _now()
    operation = {
        "operation_id": op_id,
        "user_id": user_id,
        "type": "job_search",
        "role": role_or_query,
        "query": role_or_query,
        "status": "running",
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
) -> dict[str, Any] | None:
    operation = get_operation(user_id, operation_id)
    if not operation:
        return None
    operation["status"] = status
    operation["updated_at"] = _now()
    if result_count is not None:
        operation["result_count"] = result_count
    if error is not None:
        operation["error"] = error
    if status in {"failed", "completed"}:
        operation["completed_at"] = operation["updated_at"]
    _persist(user_id, operation)
    return operation


def mark_completed(user_id: str, operation_id: str, result_count: int) -> dict[str, Any] | None:
    return update_operation(
        user_id=user_id,
        operation_id=operation_id,
        status="completed",
        result_count=result_count,
        error=None,
    )


def mark_failed(user_id: str, operation_id: str, error: str) -> dict[str, Any] | None:
    operation = get_operation(user_id, operation_id)
    if operation and operation.get("status") == "completed":
        return operation
    return update_operation(
        user_id=user_id,
        operation_id=operation_id,
        status="failed",
        error=error,
    )


def operation_age_seconds(operation: dict[str, Any]) -> float | None:
    """Seconds since the operation was created; None when unparseable."""
    try:
        created_at = datetime.fromisoformat(str(operation["created_at"]).replace("Z", "+00:00"))
    except Exception:
        return None
    return (datetime.now(timezone.utc) - created_at).total_seconds()


def is_actively_running(operation: dict[str, Any]) -> bool:
    """True while this operation's search execution must be treated as live.

    The duplicate-execution guard blocks re-execution only in this window.
    Terminal states (completed/failed), the client-facing "timed_out" state,
    an unparseable created_at, and running records older than
    MAX_EXECUTION_SECONDS are all NOT active — so a legitimate retry after a
    genuine failure or an orphaned record is never suppressed.
    """
    if operation.get("status") != "running":
        return False
    age = operation_age_seconds(operation)
    if age is None:
        return False
    return age < MAX_EXECUTION_SECONDS


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

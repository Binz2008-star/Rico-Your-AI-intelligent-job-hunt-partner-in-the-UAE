"""
src/agent/orchestrator/orchestrator.py
Coordinates intent detection → idempotency check → tool execution → audit log → response.

Two entry paths:
  1. Message-based: detect intent → tool execution → build response
  2. Action-based:  validate type → idempotency guard → tool → audit → build response

Idempotency is enforced on IDEMPOTENT_ACTION_TYPES (apply/skip/save/block).
All executed actions are logged to the audit repository.
"""
from __future__ import annotations

import inspect
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.agent.orchestrator.intent_detector import ACTION_TO_TOOL, PRIVILEGED_TOOLS, VALID_ACTION_TYPES, detect
from src.agent.registry import tool_registry
from src.repositories.audit_repo import IDEMPOTENT_ACTION_TYPES, is_duplicate, log_action
from src.schemas.agent import AgentAction, AgentUIResponse, ToolExecutionResult

logger = logging.getLogger(__name__)
_UTC = timezone.utc


def process(
    message: str,
    action: Optional[AgentAction] = None,
    user_email: str = "anonymous",
    actor_is_admin: bool = False,
) -> AgentUIResponse:
    """
    Main entry point called by the route handler.
    Returns a fully-built AgentUIResponse ready for serialization.

    ``actor_is_admin`` gates privileged tools (e.g. the global pipeline) and
    defaults to False (fail-closed); callers pass the JWT-verified admin flag.
    """
    wall_start = time.monotonic()

    if action is not None:
        result = _execute_action(action, user_email, actor_is_admin=actor_is_admin)
    else:
        result = _execute_intent(message, user_email=user_email, actor_is_admin=actor_is_admin)

    response = _build(result, message, action)
    response.execution_time_ms = int((time.monotonic() - wall_start) * 1000)
    return response


# ── Action execution path ─────────────────────────────────────────────────────

def _execute_action(action: AgentAction, user_email: str, actor_is_admin: bool = False) -> ToolExecutionResult:
    """Validate → authorize → idempotency check → execute → audit log."""
    start = time.monotonic()

    # 1. Validate action type
    if action.type not in VALID_ACTION_TYPES:
        result = ToolExecutionResult(
            success=False,
            tool_name="unknown",
            error=(
                f"Unknown action type {action.type!r}. "
                f"Valid types: {sorted(VALID_ACTION_TYPES)}"
            ),
        )
        _audit(action, user_email, result, int((time.monotonic() - start) * 1000))
        return result

    # 1b. Privileged-tool authorization (#1093): admin-only tools must never run
    #     for a non-admin actor. Fail-closed default.
    if ACTION_TO_TOOL.get(action.type) in PRIVILEGED_TOOLS and not actor_is_admin:
        logger.warning("action_privileged_denied type=%s user=%s", action.type, user_email)
        result = ToolExecutionResult(
            success=False,
            tool_name=ACTION_TO_TOOL.get(action.type, "unknown"),
            error="admin_required: this action requires an administrator.",
        )
        _audit(action, user_email, result, int((time.monotonic() - start) * 1000))
        return result

    # 2. Idempotency guard (apply/skip/save/block only)
    if action.type in IDEMPOTENT_ACTION_TYPES and is_duplicate(action.action_id):
        logger.info(
            "action_duplicate_rejected action_id=%s type=%s user=%s",
            action.action_id, action.type, user_email,
        )
        result = ToolExecutionResult(
            success=False,
            tool_name=ACTION_TO_TOOL.get(action.type, "unknown"),
            error=(
                f"Duplicate action: {action.type!r} for this job was already executed. "
                "No side effects were repeated."
            ),
        )
        _audit(action, user_email, result, int((time.monotonic() - start) * 1000), status_override="duplicate")
        return result

    # 3. Resolve tool
    tool_name = ACTION_TO_TOOL[action.type]
    try:
        tool_def = tool_registry.get(tool_name)
    except KeyError as exc:
        result = ToolExecutionResult(success=False, tool_name=tool_name, error=str(exc))
        _audit(action, user_email, result, int((time.monotonic() - start) * 1000))
        return result

    # 4. Execute
    job = action.job or {}
    logger.info(
        "action_execute type=%r tool=%r job_title=%r user=%r action_id=%s",
        action.type, tool_name, job.get("title", ""), user_email, action.action_id,
    )
    # Detect whether the tool expects a job argument.  No-arg tools (e.g.
    # trigger_pipeline) should be called without arguments even on the action
    # path, which passes a job dict for job-oriented tools.
    _sig = inspect.signature(tool_def.fn)
    _needs_job = any(
        p.default is inspect.Parameter.empty
        and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for p in _sig.parameters.values()
    )
    result = tool_def.fn(job) if _needs_job else tool_def.fn()

    # 5. Audit log
    _audit(action, user_email, result, int((time.monotonic() - start) * 1000))
    return result


# ── Intent execution path ─────────────────────────────────────────────────────

def _execute_intent(message: str, user_email: str = "anonymous", actor_is_admin: bool = False) -> ToolExecutionResult:
    intent, tool_name = detect(message)
    # #1076: message text is user content — log length only.
    logger.info("intent_detected intent=%r tool=%r message_len=%d", intent, tool_name, len(message or ""))

    if tool_name is None:
        return ToolExecutionResult(success=True, tool_name="help", data={"intent": "help"})

    # Privileged-tool authorization (#1093): an NL-detected admin-only tool
    # (e.g. "run the pipeline now") must never run for a non-admin actor.
    if tool_name in PRIVILEGED_TOOLS and not actor_is_admin:
        logger.warning("intent_privileged_denied tool=%s user=%s", tool_name, user_email)
        return ToolExecutionResult(
            success=False,
            tool_name=tool_name,
            error="admin_required: this action requires an administrator.",
        )

    try:
        tool_def = tool_registry.get(tool_name)
    except KeyError as exc:
        return ToolExecutionResult(success=False, tool_name=tool_name, error=str(exc))

    return tool_def.fn(user_id=user_email) if "user_id" in inspect.signature(tool_def.fn).parameters else tool_def.fn()


# ── Response assembly ─────────────────────────────────────────────────────────

def _build(
    result: ToolExecutionResult,
    message: str,
    action: Optional[AgentAction],
) -> AgentUIResponse:
    from src.agent.response_builder.response_builder import build_response
    return build_response(result, original_message=message, original_action=action)


# ── Audit helper ──────────────────────────────────────────────────────────────

def _audit(
    action: AgentAction,
    user_email: str,
    result: ToolExecutionResult,
    duration_ms: int,
    status_override: Optional[str] = None,
) -> None:
    job = action.job or {}
    status = status_override or ("success" if result.success else "failure")
    log_action({
        "action_id":     action.action_id,
        "action_type":   action.type,
        "user_email":    user_email,
        "job_id":        action.job_id,
        "job_title":     job.get("title"),
        "job_company":   job.get("company"),
        "timestamp":     datetime.now(_UTC).isoformat(),
        "result_status": status,
        "result_message": result.error or (str(result.data or "")),
        "duration_ms":   duration_ms,
        "failure_reason": result.error if not result.success else None,
    })

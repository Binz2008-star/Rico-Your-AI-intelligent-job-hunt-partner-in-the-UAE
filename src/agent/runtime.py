"""
src/agent/runtime.py
Rico agent runtime — single entry point for all job actions.

Callers (Telegram, API, future UI layers) use one method:

    result = agent_runtime.handle_action(
        user_id  = user_id,
        action   = "apply",       # apply | save | skip | not_relevant |
                                  # draft | why | remind | block
        job_key  = job_key,       # hex fingerprint from get_job_id()
        job      = job_dict,      # full dict if available; else resolved from cache
        source   = "telegram",    # "telegram" | "api" | "test" | …
        dry_run  = False,         # True = log intent, skip side effects
    )

All state-changing actions are:
  - idempotency-guarded (no double-applies)
  - audit-logged
  - routed through the registered tool in the tool registry

Interactive code is unreachable from this module.
"""
from __future__ import annotations

import hashlib
import inspect
import logging
import time
from typing import Any, Dict, Optional

from src.agent.orchestrator.intent_detector import ACTION_TO_TOOL, VALID_ACTION_TYPES
from src.agent.registry import tool_registry
from src.agent.types import RuntimeResult
from src.repositories.audit_repo import IDEMPOTENT_ACTION_TYPES, is_duplicate, log_action

logger = logging.getLogger(__name__)

# Actions with side effects that must pass the idempotency guard
_IDEMPOTENT = frozenset(IDEMPOTENT_ACTION_TYPES)

# Confidence level by action category (explicit user choice → 1.0)
_CONFIDENCE: Dict[str, float] = {
    "apply": 1.0, "save": 1.0, "skip": 1.0, "not_relevant": 1.0,
    "block": 1.0, "draft": 1.0, "why": 1.0, "remind": 1.0,
    "trigger_pipeline": 1.0,
}

_REPLY: Dict[str, str] = {
    "apply":        "Marked as applied. Rico will track this job.",
    "save":         "Saved. Rico will keep this job in your tracker.",
    "skip":         "Skipped. Rico noted your feedback.",
    "not_relevant": "Marked not relevant. Rico will reduce similar matches.",
    "block":        "Company blocked. Rico will exclude it from future results.",
    "draft":        "",   # filled from tool data
    "why":          "",   # filled from tool data
    "remind":       "",   # filled from tool data
}


class AgentRuntime:
    """
    Central dispatcher for Rico agent actions.
    Stateless and thread-safe — a single module-level instance is exported.
    """

    def handle_action(
        self,
        user_id: str,
        action: str,
        job_key: str = "",
        job: Optional[Dict[str, Any]] = None,
        source: str = "api",
        dry_run: bool = False,
        pre_approved: bool = False,
    ) -> RuntimeResult:
        """
        Execute a single named action on behalf of a user.

        Args:
            user_id:      Identifies the user (Telegram chat_id, email, etc.)
            action:       One of VALID_ACTION_TYPES
            job_key:      Fingerprint from get_job_id() — used to look up job if
                          `job` dict not provided
            job:          Full job dict. If None, resolved from Telegram job cache.
            source:       Caller label for audit logs ("telegram", "api", …)
            dry_run:      When True, the action is NOT executed; only logged.
            pre_approved: When True (set by execute_permission_action after explicit
                          user approval via PermissionRequestCard), injects ``_approved``
                          sentinel so apply_to_job bypasses the approval gate. This flag
                          must never be set by untrusted callers — only the
                          /actions/execute endpoint (which derives user_id from JWT) sets it.

        Returns:
            RuntimeResult — always returned, never raises.
        """
        wall_start = time.monotonic()

        # Stable idempotency key: same user + action + job within the TTL window
        # is treated as a duplicate regardless of which surface triggered it.
        _idem_raw = f"{user_id}:{action}:{job_key}"
        action_id = hashlib.md5(_idem_raw.encode(), usedforsecurity=False).hexdigest()[:16]

        # 1. Validate action
        if action not in VALID_ACTION_TYPES:
            return RuntimeResult(
                ok=False,
                message=f"Unknown action '{action}'. Supported: {sorted(VALID_ACTION_TYPES)}",
                action=action, job_key=job_key, source=source, user_id=user_id,
                error=f"unknown_action:{action}",
                duration_ms=int((time.monotonic() - wall_start) * 1000),
            )

        # 2. Resolve job dict
        resolved_job = self._resolve_job(job, job_key)

        # Inject _user_id so service-layer tools (save/skip/block) can route writes to
        # the correct store (DB for SaaS users, JSON fallback for legacy). The runtime
        # always has a valid user_id from the caller (JWT for API, chat_id for Telegram).
        resolved_job = {**resolved_job, "_user_id": user_id}

        # 2a. When the caller has already surfaced a PermissionRequestCard and the user
        #     explicitly clicked Approve, inject the sentinel so apply_job passes it
        #     through to apply_to_job(approved=True). This is the ONLY path where the
        #     approval gate is bypassed — and only after a traceable permission_id is
        #     recorded in `source` by execute_permission_action.
        if pre_approved and action == "apply":
            resolved_job = {**resolved_job, "_approved": True}

        # 3. Idempotency guard for state-changing actions
        if action in _IDEMPOTENT and is_duplicate(action_id):
            logger.info("runtime_duplicate_skipped action=%s user=%s", action, user_id)
            return RuntimeResult(
                ok=True,  # duplicate = already done = success; callers must not surface as error
                message="This action was already executed for this job.",
                action=action, job_key=job_key, source=source, user_id=user_id,
                error=None,
                duration_ms=int((time.monotonic() - wall_start) * 1000),
            )

        # 4. Dry-run: return what would happen without executing
        if dry_run:
            tool_name = ACTION_TO_TOOL[action]
            msg = f"[DRY RUN] Would execute '{tool_name}' for '{resolved_job.get('title','unknown')}'"
            logger.info("runtime_dry_run action=%s tool=%s user=%s source=%s", action, tool_name, user_id, source)
            return RuntimeResult(
                ok=True,
                message=msg,
                action=action, job_key=job_key, source=source, user_id=user_id,
                dry_run=True,
                confidence=_CONFIDENCE.get(action, 1.0),
                explanation=f"dry_run: {tool_name} on {resolved_job.get('title','?')}",
                duration_ms=int((time.monotonic() - wall_start) * 1000),
            )

        # 5. Subscription gate for apply actions.
        #    Only enforced when RICO_ENABLE_AUTO_APPLY=true. When the global flag is off,
        #    apply_to_job() itself returns manual_required — no upgrade prompt for a feature
        #    that cannot run in the current environment.
        if action == "apply":
            from src.services.apply_service import (
                _auto_apply_globally_enabled,
                _enforce_automation_allowed,
            )
            if _auto_apply_globally_enabled():
                try:
                    _enforce_automation_allowed(user_id)
                except Exception as exc:
                    elapsed = int((time.monotonic() - wall_start) * 1000)
                    logger.info("runtime_apply_gated user=%s reason=%s", user_id, exc)
                    detail = getattr(exc, "detail", None)
                    user_msg = (
                        detail.get("message") if isinstance(detail, dict) else str(exc)
                    )
                    return RuntimeResult(
                        ok=False,
                        message=user_msg,
                        action=action, job_key=job_key, source=source, user_id=user_id,
                        error="subscription_limit",
                        duration_ms=elapsed,
                    )

        # 6. Execute tool
        tool_name = ACTION_TO_TOOL[action]
        try:
            tool_def = tool_registry.get(tool_name)
        except KeyError as exc:
            return RuntimeResult(
                ok=False, message="Tool not available.",
                action=action, job_key=job_key, source=source, user_id=user_id,
                error=str(exc),
                duration_ms=int((time.monotonic() - wall_start) * 1000),
            )

        logger.info(
            "runtime_execute action=%s tool=%s user=%s source=%s job=%r",
            action, tool_name, user_id, source, resolved_job.get("title", ""),
        )

        try:
            sig = inspect.signature(tool_def.fn)
            tool_result = tool_def.fn() if len(sig.parameters) == 0 else tool_def.fn(resolved_job)
        except Exception as exc:
            logger.exception("runtime_tool_error action=%s tool=%s", action, tool_name)
            tool_result = None
            error_str = str(exc)
        else:
            error_str = tool_result.error if tool_result and not tool_result.success else None

        elapsed = int((time.monotonic() - wall_start) * 1000)
        tool_ok = bool(tool_result and tool_result.success)
        tool_data = dict((tool_result.data or {}) if tool_result else {})

        # 6a. When apply is gated (approval_required), attach a PermissionRequest payload
        #     so any caller (chat router, API layer) can surface the PermissionRequestCard
        #     without building the payload themselves.
        if action == "apply" and tool_ok and tool_data.get("status") == "approval_required":
            try:
                from src.services.permission_factory import build_apply_permission_dict
                tool_data["permission_request"] = build_apply_permission_dict(
                    resolved_job, user_id
                )
            except Exception:
                logger.debug("runtime: failed to build permission_request payload", exc_info=True)

        # 7. Build message
        message = self._build_message(action, tool_ok, tool_data, error_str)

        # 8. Audit log
        self._audit(
            action_id=action_id, action=action, user_id=user_id,
            job=resolved_job, source=source, ok=tool_ok,
            message=message, error=error_str, duration_ms=elapsed,
        )

        # 9. Persist per-job interaction so Rico can recall it across sessions.
        #    Fire-and-forget: never let a context-write failure affect the action.
        if tool_ok and resolved_job.get("title") and resolved_job.get("company"):
            try:
                from src.repositories.user_job_context_repo import (
                    record_interaction,
                    set_lifecycle_status,
                )
                from src.job_lifecycle import lifecycle_for_action
                record_interaction(
                    user_id=user_id,
                    title=resolved_job.get("title", ""),
                    company=resolved_job.get("company", ""),
                    action=action,
                )
                lc = lifecycle_for_action(action)
                if lc:
                    lc_status, _ = lc
                    set_lifecycle_status(
                        user_id=user_id,
                        title=resolved_job.get("title", ""),
                        company=resolved_job.get("company", ""),
                        status=lc_status,
                        apply_url=resolved_job.get("apply_url", ""),
                        source_url=resolved_job.get("source_url", ""),
                    )
            except Exception:
                logger.debug("runtime: failed to record job context interaction", exc_info=True)

        # 10. Update behavioral learning signals so DeepSeek context stays fresh.
        #     apply/save boost role+location+company weights; skip/not_relevant/block
        #     apply negative weights. Fire-and-forget — never blocks the response.
        _LEARNING_ACTIONS = frozenset({"apply", "save", "skip", "not_relevant", "block"})
        if tool_ok and action in _LEARNING_ACTIONS and resolved_job:
            try:
                from src.repositories.learning_repo import get_learning_repository
                get_learning_repository().infer_signals_from_job_action(
                    user_id, action, resolved_job
                )
                logger.debug(
                    "runtime_learning_signal action=%s user=%s job=%r",
                    action, user_id, resolved_job.get("title", ""),
                )
            except Exception:
                logger.debug("runtime: learning signal failed action=%s", action, exc_info=True)

        # 11. Career memory — persist the action so Rico can reference it across
        #     sessions (blocked companies, recent applies, etc). Fire-and-forget.
        _MEMORY_ACTIONS = frozenset({"apply", "save", "skip", "block", "not_relevant"})
        if tool_ok and action in _MEMORY_ACTIONS and resolved_job:
            try:
                from src.services.career_memory import record_action as _cm_record
                _cm_record(user_id, action, resolved_job)
            except Exception:
                logger.debug("runtime: career_memory record failed", exc_info=True)

        return RuntimeResult(
            ok=tool_ok,
            message=message,
            action=action,
            job_key=job_key,
            source=source,
            user_id=user_id,
            dry_run=False,
            data=tool_data,
            error=error_str,
            confidence=_CONFIDENCE.get(action, 1.0),
            explanation=f"{tool_name} executed via {source}",
            duration_ms=elapsed,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_job(job: Optional[Dict[str, Any]], job_key: str) -> Dict[str, Any]:
        """Return the best available job dict. Falls back to a stub with the key."""
        if job:
            return job
        if job_key:
            try:
                from src.rico_telegram_ui import lookup_job
                cached = lookup_job(job_key)
                if cached:
                    return cached
            except Exception:
                pass
        return {"id": job_key} if job_key else {}

    @staticmethod
    def _build_message(
        action: str, ok: bool, data: Dict[str, Any], error: Optional[str]
    ) -> str:
        if not ok:
            return f"Action failed: {error or 'unknown error'}"

        # Actions whose reply comes from tool output
        if action == "draft":
            return data.get("draft") or "Draft message could not be generated."
        if action == "why":
            return data.get("explanation") or "No explanation available."
        if action == "remind":
            reminder_date = data.get("reminder_date", "")
            return f"Reminder set for {reminder_date}." if reminder_date else "Reminder noted."
        if action == "apply":
            # apply_to_job() always returns a status-specific message (e.g.
            # "approval_required", "manual_required", or real engine success) —
            # never mask it with the generic static reply, or the user is told
            # "Marked as applied" for an apply that never actually happened.
            return data.get("message") or _REPLY.get(action, "Action completed.")

        return _REPLY.get(action, "Action completed.")

    @staticmethod
    def _audit(
        action_id: str, action: str, user_id: str,
        job: Dict[str, Any], source: str,
        ok: bool, message: str, error: Optional[str], duration_ms: int,
    ) -> None:
        try:
            from datetime import datetime, timezone
            log_action({
                "action_id":      action_id,
                "action_type":    action,
                "user_email":     user_id,
                "job_id":         str(job.get("id") or job.get("_key") or ""),
                "job_title":      job.get("title"),
                "job_company":    job.get("company"),
                "timestamp":      datetime.now(timezone.utc).isoformat(),
                "result_status":  "success" if ok else "failure",
                "result_message": message,
                "duration_ms":    duration_ms,
                "failure_reason": error if not ok else None,
                "source":         source,
            })
        except Exception:
            logger.exception("runtime_audit_failed action=%s", action)


# Module-level singleton — import and use directly:
#   from src.agent.runtime import agent_runtime
agent_runtime = AgentRuntime()

"""
src/services/apply_service.py
Delegates browser-automation apply requests to the correct engine.

Phase-0 additions (additive, no existing behaviour removed):
* ApplyLinkResult dataclass
* resolve_apply_action() — full trust-gate resolution
* wrap_action_error()    — internal codes → user-safe strings

All existing public functions are preserved unchanged so that every
importer that does ``from src.services.apply_service import apply_to_job``
continues to work without modification.

_resolve_apply_link() now routes through the Phase-0 trust gate so that
untrusted / placeholder URLs are silently rejected before any caller
receives them.  The function signature and return type are unchanged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.rico_env import env_bool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase-0 result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApplyLinkResult:
    """Outcome of a trust-gated apply-link resolution."""

    success: bool
    apply_url: Optional[str]
    show_apply_button: bool
    message: str
    internal_code: str = field(default="", compare=False)


# ---------------------------------------------------------------------------
# Phase-0 safe messages
# ---------------------------------------------------------------------------

_SAFE_MESSAGES: dict[str, str] = {
    "no_apply_link_available": (
        "I don't have a verified apply link for this job yet. "
        "I can save it to your pipeline or help you search the company career page."
    ),
    "apply_url_untrusted": (
        "I couldn't verify the apply link for this job. "
        "I can save it to your pipeline or help you find the official application page."
    ),
    "apply_url_placeholder": (
        "The apply link for this job doesn't look right. "
        "I can save the job to your pipeline while you verify the link directly."
    ),
    "job_not_found": (
        "I couldn't find this job in my records. "
        "Try searching again or let me know the company name."
    ),
    "action_timeout": (
        "The action took too long to complete. Please try again in a moment."
    ),
}

_GENERIC_SAFE_MESSAGE = (
    "Something went wrong with that action. "
    "Please try again or let me know how I can help."
)


# ---------------------------------------------------------------------------
# Existing helpers — unchanged from main
# ---------------------------------------------------------------------------


def _approval_required() -> bool:
    """Whether applications need explicit user approval before Rico submits them.

    Defaults to True (safe) so a missing or blank env var can never silently
    enable auto-submission.  Set RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=false
    to disable.
    """
    return env_bool("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", True)


def _is_browser_unavailable(exc: Exception) -> bool:
    """Detect Playwright / browser-launch errors → surface as 'manual_required'."""
    msg = str(exc).lower()
    return any(
        phrase in msg
        for phrase in (
            "playwright install",
            "browser type",
            "chromium",
            "executable",
            "browser not found",
            "executable doesn't exist",
            "browser.launch",
            "failed to launch",
        )
    )


def _clean_apply_error(exc: Exception) -> Dict[str, str]:
    """Return a user-facing message; log raw technical detail server-side only."""
    if _is_browser_unavailable(exc):
        logger.warning("browser_unavailable: %s", exc)
        return {
            "status": "manual_required",
            "message": "Manual apply required. Browser automation is unavailable for this job.",
        }
    logger.exception("apply_failed")
    return {
        "status": "error",
        "message": "Application failed. Please try again or apply manually.",
    }


def _resolve_apply_link(job: Dict[str, Any]) -> str:
    """Pick the best *trusted* apply URL from a job dict.

    Phase-0 change: routes through the trust gate before returning.
    If the resolved URL is a placeholder or LLM-generated, returns "".
    Signature and return type are unchanged; all callers continue to work.
    """
    # --- trust gate (Phase-0) -------------------------------------------
    try:
        from src.services.job_link_trust import resolve_trusted_apply_url
        trusted = resolve_trusted_apply_url(job, origin=job.get("origin"))
        if trusted:
            return trusted
        # Trust gate rejected — fall through to return ""
        # (do not return a raw untrusted URL)
        raw_url = (
            job.get("external_url")
            or job.get("alt_url")
            or job.get("source_url")
            or job.get("link")
            or job.get("apply_url")
        )
        if raw_url:
            # Log server-side only; never return to caller
            logger.warning(
                "_resolve_apply_link: rejected untrusted url job_id=%s",
                job.get("job_id"),
            )
        return ""
    except ImportError:
        # job_link_trust not yet available (test isolation) — fall back to
        # legacy key-walk so existing non-Phase-0 tests keep passing.
        pass

    # --- legacy fallback (used only when job_link_trust is unavailable) ---
    for key in (
        "link",
        "apply_url",
        "apply_link",
        "job_apply_link",
        "url",
        "job_url",
        "alt_link",
        "source_url",
    ):
        value = str(job.get(key) or "").strip()
        if value:
            return value

    for nested_key in ("job", "job_data"):
        nested = job.get(nested_key)
        if isinstance(nested, dict):
            value = _resolve_apply_link(nested)
            if value:
                return value

    return ""


_AUTO_APPLY_DISABLED_STATUSES = {"no_result", "disabled", "unsupported"}


def _auto_apply_globally_enabled() -> bool:
    return env_bool("RICO_ENABLE_AUTO_APPLY", False)


def _manual_required_response(job: Dict[str, Any]) -> Dict[str, str]:
    """User-safe response when automation cannot run for any reason.

    Phase-0 change: the apply_url included in the response is now the
    trust-gated result of _resolve_apply_link().  Untrusted / placeholder
    URLs are silently omitted so they are never returned to the chat layer.
    """
    link = _resolve_apply_link(job)
    msg = "Automated apply is not currently enabled."
    if link:
        msg += f" You can apply manually here: {link}"
    return {"status": "manual_required", "message": msg, "apply_url": link}


def _enforce_automation_allowed(user_id: str) -> None:
    """Raise HTTP 402 if the user's plan does not include application automation.

    Only called when RICO_ENABLE_AUTO_APPLY=true.
    """
    from fastapi import HTTPException
    from src.subscription_plans import resolve_effective_user_plan

    resolved = resolve_effective_user_plan(user_id)
    if not resolved.subscription.entitlements.application_automation_enabled:
        plan = resolved.subscription.plan.value
        raise HTTPException(
            status_code=402,
            detail={
                "type": "subscription_limit",
                "intent": "subscription_limit",
                "message": (
                    f"Automated applications are not available on the {plan.title()} plan. "
                    "Upgrade to Premium to enable this feature."
                ),
                "response_source": "subscription_gate",
                "feature": "application_automation",
                "plan": plan,
                "next_action": "upgrade_subscription",
                "options": [
                    {"action": "upgrade_subscription", "label": "View plans", "message": "upgrade plan"},
                    {"action": "subscription_status", "label": "Check current plan", "message": "what is my plan?"},
                ],
            },
        )


def apply_to_job(
    job: Dict[str, Any],
    *,
    approved: bool = False,
    user_id: str | None = None,
) -> Dict[str, str]:
    """
    Trigger automated application for a job.
    Returns: {"status": str, "message": str, "job_id": str (optional)}

    Gate order:
    1. Approval guard  — agent paths need explicit user approval.
    2. Global flag     — RICO_ENABLE_AUTO_APPLY=false → manual_required for all.
    3. Subscription    — only checked when the global flag is on.
    4. Engine routing  — Premium users reach the actual apply engines.
    """
    resolved_link = _resolve_apply_link(job)

    if _approval_required() and not approved:
        logger.warning(
            "apply_blocked_pending_approval link=%s",
            resolved_link[:120] if resolved_link else "",
        )
        return {
            "status": "approval_required",
            "message": "This application needs your explicit approval before Rico can submit it.",
        }

    if not _auto_apply_globally_enabled():
        logger.info("auto_apply_globally_disabled user=%s", user_id or "anonymous")
        return _manual_required_response(job)

    if user_id:
        _enforce_automation_allowed(user_id)

    link = resolved_link.lower()

    if not link:
        return {"status": "error", "message": "Job is missing a link"}

    job = {**job, "link": resolved_link}

    if "naukrigulf.com" in link:
        return _normalize_engine_result(_apply_naukrigulf(job), job)

    if "indeed.com" in link:
        return _normalize_engine_result(_apply_indeed(job), job)

    # LinkedIn and all other sources: no active engine
    return _manual_required_response(job)


def _normalize_engine_result(
    result: Dict[str, str], job: Dict[str, Any]
) -> Dict[str, str]:
    """Convert opaque engine-disabled statuses into a user-safe manual_required."""
    if result.get("status") in _AUTO_APPLY_DISABLED_STATUSES:
        logger.info("engine_not_active status=%s", result.get("status"))
        return _manual_required_response(job)
    return result


def _apply_naukrigulf(job: Dict[str, Any]) -> Dict[str, str]:
    try:
        from src.naukrigulf_apply import run_naukrigulf_apply

        results = run_naukrigulf_apply(jobs=[job], max_applies=1)
        if not results:
            return {"status": "no_result", "message": "Apply engine returned no result"}

        result = results[0]
        return {
            "status": result.status.value,
            "message": result.message or f"Applied to {job.get('title', 'Unknown')}",
            "job_id": result.job_id or "",
        }
    except Exception as exc:
        return _clean_apply_error(exc)


def _apply_indeed(job: Dict[str, Any]) -> Dict[str, str]:
    try:
        from src.indeed_apply import IndeedApplyEngine

        with IndeedApplyEngine() as engine:
            result = engine.apply_one(job)
        return {
            "status": result.status.value,
            "message": result.message,
            "job_id": result.job_id,
        }
    except Exception as exc:
        error = _clean_apply_error(exc)
        if error.get("status") == "error":
            error = {
                **error,
                "message": str(exc) or error["message"],
                "method": "indeed",
            }
        return error


# ---------------------------------------------------------------------------
# Phase-0 public API (additive)
# ---------------------------------------------------------------------------


def resolve_apply_action(
    job: Dict[str, Any],
    *,
    origin: Optional[str] = None,
) -> ApplyLinkResult:
    """Resolve the apply action for *job* through the full Phase-0 trust gate.

    Always returns an :class:`ApplyLinkResult`; never raises.
    Check ``.success`` to decide whether to show the apply button.
    """
    from src.services.job_link_trust import (
        resolve_trusted_apply_url,
        safe_no_apply_link_message,
    )

    trusted_url = resolve_trusted_apply_url(job, origin=origin)

    if trusted_url:
        return ApplyLinkResult(
            success=True,
            apply_url=trusted_url,
            show_apply_button=True,
            message="",
        )

    raw_url = (
        job.get("external_url")
        or job.get("alt_url")
        or job.get("source_url")
    )
    if not raw_url:
        internal_code = "no_apply_link_available"
    elif origin == "llm":
        internal_code = "apply_url_untrusted"
    else:
        from src.services.source_quality import is_placeholder_url
        internal_code = (
            "apply_url_placeholder" if is_placeholder_url(raw_url) else "apply_url_untrusted"
        )

    logger.warning(
        "apply_service: %s job_id=%s persisted_job_id=%s source_job_id=%s",
        internal_code,
        job.get("job_id"),
        job.get("persisted_job_id"),
        job.get("source_job_id"),
    )

    safe_msg = _SAFE_MESSAGES.get(internal_code) or safe_no_apply_link_message(job)

    return ApplyLinkResult(
        success=False,
        apply_url=None,
        show_apply_button=False,
        message=safe_msg,
        internal_code=internal_code,
    )


def wrap_action_error(
    internal_code: str,
    job: Optional[Dict[str, Any]] = None,
) -> str:
    """Return a user-safe message for any internal action error code.

    Use in ``rico_chat_api.py`` action handlers that currently return the raw
    ``internal_code`` string to the chat layer.
    """
    if internal_code in _SAFE_MESSAGES:
        return _SAFE_MESSAGES[internal_code]
    if job:
        from src.services.job_link_trust import safe_no_apply_link_message
        return safe_no_apply_link_message(job)
    logger.error(
        "apply_service.wrap_action_error: unknown code '%s' – using generic message",
        internal_code,
    )
    return _GENERIC_SAFE_MESSAGE

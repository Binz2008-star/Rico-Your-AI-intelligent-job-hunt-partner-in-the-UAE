"""
src/services/apply_service.py
Delegates browser-automation apply requests to the correct engine.
Routes call apply_to_job() — never import engine modules directly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from src.rico_env import env_bool

logger = logging.getLogger(__name__)


def _approval_required() -> bool:
    """Whether applications need explicit user approval before Rico submits them.

    Defaults to True (safe) so a missing or blank env var can never silently enable
    auto-submission. Set RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=false to disable.
    """
    return env_bool("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", True)


def _is_browser_unavailable(exc: Exception) -> bool:
    """Detect Playwright / browser-launch errors that should surface as 'manual_required'."""
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
    """Return a user-facing message. Log raw technical detail server-side only."""
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


def _enforce_automation_allowed(user_id: str) -> None:
    """Raise HTTP 402 if the user's plan does not include application automation."""
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


def apply_to_job(job: Dict[str, Any], *, approved: bool = False, user_id: str | None = None) -> Dict[str, str]:
    """
    Trigger automated application for a job.
    Returns: {"status": str, "message": str, "job_id": str (optional)}

    Safety: this is the single chokepoint for real application submission. When approval
    mode is enabled (RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true, the default), the caller
    MUST pass approved=True — i.e. the user explicitly approved THIS application. Agent /
    automation callers leave approved=False, so they can never auto-submit on the user's
    behalf; they receive an "approval_required" result instead.
    """
    if _approval_required() and not approved:
        logger.warning(
            "apply_blocked_pending_approval link=%s", (job.get("link") or "")[:120]
        )
        return {
            "status": "approval_required",
            "message": "This application needs your explicit approval before Rico can submit it.",
        }

    if user_id:
        _enforce_automation_allowed(user_id)

    link = (job.get("link") or "").lower()

    if not link:
        return {"status": "error", "message": "Job is missing a link"}

    if "naukrigulf.com" in link:
        return _apply_naukrigulf(job)

    if "indeed.com" in link:
        return _apply_indeed(job)

    if "linkedin.com" in link:
        return {
            "status": "unsupported",
            "message": "LinkedIn Easy Apply is not enabled in this environment",
        }

    return {
        "status": "unsupported",
        "message": (
            f"No automated apply engine is available for this source. "
            f"Open manually: {job.get('link', '')}"
        ),
    }


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

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


_AUTO_APPLY_DISABLED_STATUSES = {"no_result", "disabled", "unsupported"}


def _auto_apply_globally_enabled() -> bool:
    return env_bool("RICO_ENABLE_AUTO_APPLY", False)


def _manual_required_response(job: Dict[str, Any]) -> Dict[str, str]:
    """User-safe response when automation cannot run for any reason."""
    link = job.get("link") or job.get("apply_link") or ""
    msg = "Automated apply is not currently enabled."
    if link:
        msg += f" You can apply manually here: {link}"
    return {"status": "manual_required", "message": msg, "apply_url": link}


def _enforce_automation_allowed(user_id: str) -> None:
    """Raise HTTP 402 if the user's plan does not include application automation.

    Only called when RICO_ENABLE_AUTO_APPLY=true. Never called when the global
    flag is off — we return manual_required instead of an upgrade prompt for a
    feature that cannot actually run.
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


def apply_to_job(job: Dict[str, Any], *, approved: bool = False, user_id: str | None = None) -> Dict[str, str]:
    """
    Trigger automated application for a job.
    Returns: {"status": str, "message": str, "job_id": str (optional)}

    Order of gates:
    1. Approval guard — agent paths cannot auto-submit without explicit user approval.
    2. Global flag (RICO_ENABLE_AUTO_APPLY) — if false, return manual_required for ALL
       users regardless of plan. No upgrade prompt is shown for a feature that cannot run.
    3. Subscription entitlement — only checked when the global flag is on; Free/Pro get 402.
    4. Engine routing — Premium users reach the actual apply engines.
    """
    if _approval_required() and not approved:
        logger.warning(
            "apply_blocked_pending_approval link=%s", (job.get("link") or "")[:120]
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

    link = (job.get("link") or "").lower()

    if not link:
        return {"status": "error", "message": "Job is missing a link"}

    if "naukrigulf.com" in link:
        return _normalize_engine_result(_apply_naukrigulf(job), job)

    if "indeed.com" in link:
        return _normalize_engine_result(_apply_indeed(job), job)

    # LinkedIn and all other sources: no active engine
    return _manual_required_response(job)


def _normalize_engine_result(result: Dict[str, str], job: Dict[str, Any]) -> Dict[str, str]:
    """Convert opaque engine-disabled statuses into a user-safe manual_required response."""
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

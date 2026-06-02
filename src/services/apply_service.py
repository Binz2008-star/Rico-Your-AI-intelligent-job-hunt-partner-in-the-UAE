"""
src/services/apply_service.py
Delegates browser-automation apply requests to the correct engine.
Routes call apply_to_job() — never import engine modules directly.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_AUTO_APPLY_ENABLED = os.getenv("RICO_ENABLE_AUTO_APPLY", "false").lower() in ("true", "1", "yes")
_REQUIRE_APPROVAL = os.getenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", "true").lower() in ("true", "1", "yes")


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


def _already_applied(job: Dict[str, Any]) -> bool:
    """Check if this job has already been applied to (idempotency guard)."""
    job_id = job.get("job_id") or job.get("id") or ""
    if not job_id:
        return False
    try:
        from src.repositories.audit_repo import is_duplicate
        return is_duplicate(user_id="", action="apply", job_key=job_id)
    except Exception:
        return False


def apply_to_job(
    job: Dict[str, Any],
    user_id: str = "",
    dry_run: bool = False,
) -> Dict[str, str]:
    """
    Trigger automated application for a job.

    Returns: {"status": str, "message": str, "job_id": str (optional)}

    Status values:
      success            - applied successfully
      already_applied    - duplicate guard triggered
      approval_required  - RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true
      auto_apply_disabled - RICO_ENABLE_AUTO_APPLY=false
      manual_required    - browser not available
      unsupported        - no engine for this source
      dry_run            - dry_run=True, would have applied
      error              - unexpected failure
    """
    if not _AUTO_APPLY_ENABLED:
        return {
            "status": "auto_apply_disabled",
            "message": "Automated apply is disabled. Please apply manually via the job link.",
            "job_id": job.get("job_id", ""),
        }

    if _REQUIRE_APPROVAL and not dry_run:
        return {
            "status": "approval_required",
            "message": "Rico requires your confirmation before submitting applications. Please confirm in the dashboard.",
            "job_id": job.get("job_id", ""),
        }

    link = (job.get("link") or job.get("apply_link") or "").lower()

    if not link:
        return {"status": "error", "message": "Job is missing a link", "job_id": job.get("job_id", "")}

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"Dry run: would have applied to {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}",
            "job_id": job.get("job_id", ""),
        }

    if "naukrigulf.com" in link:
        return _apply_naukrigulf(job)

    if "indeed.com" in link:
        return _apply_indeed(job)

    if "linkedin.com" in link:
        return _apply_linkedin(job)

    return {
        "status": "unsupported",
        "message": (
            f"No automated apply engine is available for this source. "
            f"Open manually: {job.get('link', '')}"
        ),
        "job_id": job.get("job_id", ""),
    }


def _apply_linkedin(job: Dict[str, Any]) -> Dict[str, str]:
    try:
        from src.auto_apply import run_auto_apply, AUTO_APPLY_ENABLED

        if not AUTO_APPLY_ENABLED:
            return {
                "status": "auto_apply_disabled",
                "message": "LinkedIn Easy Apply is disabled. Set RICO_ENABLE_AUTO_APPLY=true to enable.",
                "job_id": job.get("job_id", ""),
            }

        results = run_auto_apply(jobs=[job], max_applies=1)
        if not results:
            return {
                "status": "no_result",
                "message": "LinkedIn apply engine returned no result",
                "job_id": job.get("job_id", ""),
            }

        result = results[0]
        return {
            "status": result.status.value,
            "message": result.message or f"Applied to {job.get('title', 'Unknown')}",
            "job_id": result.job_id or job.get("job_id", ""),
        }
    except Exception as exc:
        error = _clean_apply_error(exc)
        error.setdefault("job_id", job.get("job_id", ""))
        return error


def _apply_naukrigulf(job: Dict[str, Any]) -> Dict[str, str]:
    try:
        from src.naukrigulf_apply import run_naukrigulf_apply

        results = run_naukrigulf_apply(jobs=[job], max_applies=1)
        if not results:
            return {
                "status": "no_result",
                "message": "Apply engine returned no result",
                "job_id": job.get("job_id", ""),
            }

        result = results[0]
        return {
            "status": result.status.value,
            "message": result.message or f"Applied to {job.get('title', 'Unknown')}",
            "job_id": result.job_id or job.get("job_id", ""),
        }
    except Exception as exc:
        error = _clean_apply_error(exc)
        error.setdefault("job_id", job.get("job_id", ""))
        return error


def _apply_indeed(job: Dict[str, Any]) -> Dict[str, str]:
    try:
        from src.indeed_apply import IndeedApplyEngine

        with IndeedApplyEngine() as engine:
            result = engine.apply_one(job)
        return {
            "status": result.status.value,
            "message": result.message,
            "job_id": result.job_id or job.get("job_id", ""),
        }
    except Exception as exc:
        error = _clean_apply_error(exc)
        error.setdefault("job_id", job.get("job_id", ""))
        return error


def get_apply_capabilities() -> Dict[str, Any]:
    """Return which apply engines are available in this environment."""
    return {
        "auto_apply_enabled": _AUTO_APPLY_ENABLED,
        "approval_required": _REQUIRE_APPROVAL,
        "engines": {
            "linkedin": _AUTO_APPLY_ENABLED,
            "naukrigulf": _AUTO_APPLY_ENABLED,
            "indeed": _AUTO_APPLY_ENABLED,
        },
    }

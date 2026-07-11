"""Auto-save service for Rico's autonomous mode.

Automatically saves high-match jobs to a user's pipeline when:
  - Score >= configurable threshold (default 75)
  - Job is not already saved/applied/skipped/blocked
  - Daily auto-save limit not exceeded
  - Job passes exclusion keyword filter

All auto-saves are:
  - Logged to the audit trail with source="autonomous"
  - Reversible (user can undo via chat)
  - Rate-limited per user per day

This service NEVER submits applications. It only saves jobs.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.rico_env import env_bool

logger = logging.getLogger(__name__)

_UTC = timezone.utc

DEFAULT_SCORE_THRESHOLD = 75
DEFAULT_MAX_SAVES_PER_DAY = 10
MINIMUM_SCORE_THRESHOLD = 70

# Thread-local lock for concurrent auto-save dedup within a single process.
# DB-level ON CONFLICT in upsert_recommendation provides cross-process idempotency.
_SAVE_LOCK = threading.Lock()


@dataclass
class AutoSaveResult:
    user_id: str
    saved: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def saved_count(self) -> int:
        return len(self.saved)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "saved_count": self.saved_count,
            "skipped_count": self.skipped_count,
            "errors": self.errors,
            "saved": self.saved,
        }


def _get_score_threshold() -> int:
    threshold = int(os.getenv("RICO_AUTONOMOUS_AUTO_SAVE_THRESHOLD", DEFAULT_SCORE_THRESHOLD))
    return max(threshold, MINIMUM_SCORE_THRESHOLD)


def _get_max_saves_per_day() -> int:
    return int(os.getenv("RICO_AUTONOMOUS_MAX_SAVES_PER_DAY", DEFAULT_MAX_SAVES_PER_DAY))


def _get_exclusion_keywords() -> set[str]:
    raw = os.getenv("EXCLUDE_KEYWORDS", "")
    if not raw:
        return set()
    return {kw.strip().lower() for kw in raw.split(",") if kw.strip()}


def _is_excluded(job: Dict[str, Any], exclusions: set[str]) -> bool:
    if not exclusions:
        return False
    text = " ".join(str(v) for v in job.values() if isinstance(v, (str, int, float))).lower()
    return any(kw in text for kw in exclusions)


def _get_job_score(job: Dict[str, Any]) -> int:
    score = job.get("score") or job.get("rico_score") or 0
    try:
        return int(score)
    except (TypeError, ValueError):
        return 0


def _get_job_key(job: Dict[str, Any]) -> str:
    raw = (
        job.get("job_id")
        or job.get("job_key")
        or job.get("id")
        or f"{job.get('title', '')}|{job.get('company', '')}|{job.get('link', '')}"
    )
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:16]


def _is_already_saved(job: Dict[str, Any], existing_keys: set[str]) -> bool:
    job_key = _get_job_key(job)
    return job_key in existing_keys


def _audit_log(
    user_id: str,
    action: str,
    job_key: str,
    job_title: str,
    job_company: str,
    result_status: str,
    message: str = "",
) -> None:
    """Write an audit log entry for an autonomous action."""
    try:
        from src.models.action_log import ActionLog
        from src.repositories.audit_repo import log_action

        action_id = hashlib.md5(
            f"{user_id}:{action}:{job_key}".encode(), usedforsecurity=False
        ).hexdigest()[:16]
        log_action(ActionLog(
            action_id=action_id,
            action_type=action,
            user_email=user_id,
            job_id=job_key,
            job_title=job_title,
            job_company=job_company,
            timestamp=datetime.now(_UTC).isoformat(),
            result_status=result_status,
            result_message=message,
            duration_ms=0,
            failure_reason=message if result_status == "failure" else None,
        ))
    except Exception:
        logger.debug("auto_save: audit log failed user=%s job=%s", user_id, job_key)


def auto_save_jobs(
    user_id: str,
    jobs: List[Dict[str, Any]],
    existing_job_keys: Optional[set[str]] = None,
    daily_save_count: int = 0,
    dry_run: bool = False,
) -> AutoSaveResult:
    """Auto-save high-match jobs for a user.

    Args:
        user_id: The user's external ID. Must be a non-empty authenticated user ID.
        jobs: List of job dicts with at least title, company, score, link.
        existing_job_keys: Set of job keys already in the user's pipeline.
        daily_save_count: How many auto-saves have been done today for this user.
        dry_run: When True, no actual saves are performed — just returns what would happen.

    Returns:
        AutoSaveResult with saved and skipped job lists.

    Write path: src/repositories/applications_repo.create() →
        RicoDB.upsert_recommendation() → Neon rico_job_recommendations table.
        Subscription gating via enforce_saved_job_allowed() is called inside create().
        No legacy JSON or Render-disk persistence when user_id is present.
    Idempotency: DB-level ON CONFLICT (user_id, job_key) DO UPDATE in upsert_recommendation.
        In-process _SAVE_LOCK prevents concurrent duplicate saves within one process.
    Audit: Every save, skip (duplicate), and failure is logged to action_audit_log.
    Safety: apply is never called. Only status='saved' is written.
    """
    result = AutoSaveResult(user_id=user_id)

    # Guest/public user rejection — autonomous mode requires authenticated user_id.
    # Reject all guest/public identity formats including public:*, public_*, anonymous, guest.
    # Do not trust arbitrary worker task arguments as authenticated identity.
    if not user_id or user_id in {"anonymous", "guest", "public"} or user_id.startswith(("public:", "public_")):
        result.errors.append("Autonomous auto-save requires an authenticated canonical user_id.")
        logger.warning("auto_save_rejected reason=unauthenticated user=%s", user_id)
        return result

    # Safety guard check — fail closed. If the guard cannot load or execute,
    # perform NO mutation. This is a merge-blocking requirement.
    try:
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        safety = guard.check_autonomous_action("save")
        if not safety.allowed:
            result.errors.append(f"Safety guard blocked autonomous save: {safety.reason}")
            logger.warning("auto_save_blocked reason=safety_guard user=%s", user_id)
            return result
    except Exception:
        result.errors.append("Safety guard failed to load — autonomous save blocked (fail-closed).")
        logger.error("auto_save_blocked reason=safety_guard_load_failure user=%s", user_id)
        return result

    threshold = _get_score_threshold()
    max_saves = _get_max_saves_per_day()
    exclusions = _get_exclusion_keywords()
    existing = existing_job_keys if existing_job_keys is not None else set()

    remaining_budget = max_saves - daily_save_count
    if remaining_budget <= 0:
        logger.info(
            "auto_save_budget_exhausted user=%s saved_today=%d max=%d",
            user_id, daily_save_count, max_saves,
        )
        return result

    for job in jobs:
        if len(result.saved) >= remaining_budget:
            result.skipped.append({"job": job, "reason": "daily_limit_reached"})
            continue

        score = _get_job_score(job)
        if score < threshold:
            result.skipped.append({"job": job, "reason": f"score_below_threshold:{score}<{threshold}"})
            continue

        job_key = _get_job_key(job)
        job_title = job.get("title", "Unknown Role")
        job_company = job.get("company", "Unknown Company")

        if _is_already_saved(job, existing):
            result.skipped.append({"job": job, "reason": "already_in_pipeline"})
            _audit_log(user_id, "save", job_key, job_title, job_company, "duplicate", "Job already in pipeline")
            continue

        if _is_excluded(job, exclusions):
            result.skipped.append({"job": job, "reason": "excluded_keyword"})
            continue

        if dry_run:
            result.saved.append({"job": job, "score": score, "dry_run": True})
            continue

        try:
            from src.repositories.applications_repo import create as create_application

            with _SAVE_LOCK:
                # Double-check under lock to prevent concurrent duplicate
                if job_key in existing:
                    result.skipped.append({"job": job, "reason": "concurrent_duplicate"})
                    _audit_log(user_id, "save", job_key, job_title, job_company, "duplicate", "Concurrent duplicate prevented")
                    continue

                create_application(
                    job_id=job_key,
                    title=job_title,
                    company=job_company,
                    location=job.get("location", job.get("city", "")),
                    url=job.get("link", job.get("url", "")),
                    status="saved",
                    source="autonomous",
                    user_id=user_id,
                )
                existing.add(job_key)

            result.saved.append({"job": job, "score": score, "job_key": job_key})
            _audit_log(user_id, "save", job_key, job_title, job_company, "success", "Auto-saved by autonomous loop")
            logger.info(
                "auto_save_success user=%s job_key=%s score=%d title=%s",
                user_id, job_key, score, job_title[:60],
            )
        except Exception as exc:
            logger.exception("auto_save_error user=%s job=%s", user_id, job_title)
            result.errors.append(f"Failed to save '{job_title}': {exc}")
            _audit_log(user_id, "save", job_key, job_title, job_company, "failure", str(exc))

    logger.info(
        "auto_save_complete user=%s saved=%d skipped=%d errors=%d",
        user_id, result.saved_count, result.skipped_count, len(result.errors),
    )
    return result

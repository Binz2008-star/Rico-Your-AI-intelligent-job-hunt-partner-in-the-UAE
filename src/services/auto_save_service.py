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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.rico_env import env_bool

logger = logging.getLogger(__name__)

_UTC = timezone.utc

DEFAULT_SCORE_THRESHOLD = 75
DEFAULT_MAX_SAVES_PER_DAY = 10
MINIMUM_SCORE_THRESHOLD = 70


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


def auto_save_jobs(
    user_id: str,
    jobs: List[Dict[str, Any]],
    existing_job_keys: Optional[set[str]] = None,
    daily_save_count: int = 0,
    dry_run: bool = False,
) -> AutoSaveResult:
    """Auto-save high-match jobs for a user.

    Args:
        user_id: The user's external ID.
        jobs: List of job dicts with at least title, company, score, link.
        existing_job_keys: Set of job keys already in the user's pipeline.
        daily_save_count: How many auto-saves have been done today for this user.
        dry_run: When True, no actual saves are performed — just returns what would happen.

    Returns:
        AutoSaveResult with saved and skipped job lists.
    """
    result = AutoSaveResult(user_id=user_id)
    threshold = _get_score_threshold()
    max_saves = _get_max_saves_per_day()
    exclusions = _get_exclusion_keywords()
    existing = existing_job_keys or set()

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

        if _is_already_saved(job, existing):
            result.skipped.append({"job": job, "reason": "already_in_pipeline"})
            continue

        if _is_excluded(job, exclusions):
            result.skipped.append({"job": job, "reason": "excluded_keyword"})
            continue

        if dry_run:
            result.saved.append({"job": job, "score": score, "dry_run": True})
            continue

        try:
            from src.repositories.applications_repo import create as create_application

            job_key = _get_job_key(job)
            create_application(
                job_id=job_key,
                title=job.get("title", "Unknown Role"),
                company=job.get("company", "Unknown Company"),
                location=job.get("location", job.get("city", "")),
                url=job.get("link", job.get("url", "")),
                status="saved",
                source="autonomous",
                user_id=user_id,
            )
            result.saved.append({"job": job, "score": score, "job_key": job_key})
            existing.add(job_key)
            logger.info(
                "auto_save_success user=%s job_key=%s score=%d title=%s",
                user_id, job_key, score, job.get("title", "?")[:60],
            )
        except Exception as exc:
            logger.exception("auto_save_error user=%s job=%s", user_id, job.get("title", "?"))
            result.errors.append(f"Failed to save '{job.get('title', '?')}': {exc}")

    logger.info(
        "auto_save_complete user=%s saved=%d skipped=%d errors=%d",
        user_id, result.saved_count, result.skipped_count, len(result.errors),
    )
    return result

"""Autonomous draft generation service for Rico.

Generates cover letters and recruiter messages for auto-saved jobs.
Drafts are stored as 'prepared' status — they are NEVER sent without
explicit user approval.

Uses the existing message_generator.py + LLM provider chain.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_DRAFTS_PER_DAY = 3


@dataclass
class DraftResult:
    user_id: str
    drafts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def draft_count(self) -> int:
        return len(self.drafts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "draft_count": self.draft_count,
            "errors": self.errors,
            "drafts": self.drafts,
        }


def _get_max_drafts_per_day() -> int:
    return int(os.getenv("RICO_AUTONOMOUS_MAX_DRAFTS_PER_DAY", DEFAULT_MAX_DRAFTS_PER_DAY))


def generate_drafts_for_jobs(
    user_id: str,
    jobs: List[Dict[str, Any]],
    profile: Optional[Any] = None,
    daily_draft_count: int = 0,
    dry_run: bool = False,
) -> DraftResult:
    """Generate cover letter drafts for the top auto-saved jobs.

    Args:
        user_id: The user's external ID.
        jobs: List of job dicts (sorted by score descending).
        profile: Optional user profile for personalization.
        daily_draft_count: How many drafts have been generated today.
        dry_run: When True, no actual drafts are generated.

    Returns:
        DraftResult with generated drafts.
    """
    result = DraftResult(user_id=user_id)
    max_drafts = _get_max_drafts_per_day()
    remaining = max_drafts - daily_draft_count

    if remaining <= 0:
        logger.info(
            "autonomous_draft_budget_exhausted user=%s drafts_today=%d max=%d",
            user_id, daily_draft_count, max_drafts,
        )
        return result

    top_jobs = jobs[:remaining]

    for job in top_jobs:
        if dry_run:
            result.drafts.append({
                "job_title": job.get("title", "?"),
                "company": job.get("company", "?"),
                "draft": "[DRY RUN] Would generate cover letter",
                "dry_run": True,
            })
            continue

        try:
            from src.message_generator import generate_message

            draft_text = generate_message(job, profile=profile)
            if not draft_text or not draft_text.strip():
                logger.warning(
                    "autonomous_draft_empty user=%s job=%s",
                    user_id, job.get("title", "?")[:60],
                )
                continue

            result.drafts.append({
                "job_title": job.get("title", "?"),
                "company": job.get("company", "?"),
                "job_key": job.get("job_id", job.get("job_key", "")),
                "draft": draft_text,
                "status": "prepared",
            })
            logger.info(
                "autonomous_draft_success user=%s job=%s length=%d",
                user_id, job.get("title", "?")[:60], len(draft_text),
            )
        except Exception as exc:
            logger.exception(
                "autonomous_draft_error user=%s job=%s",
                user_id, job.get("title", "?")[:60],
            )
            result.errors.append(
                f"Failed to draft for '{job.get('title', '?')}': {exc}"
            )

    logger.info(
        "autonomous_draft_complete user=%s drafts=%d errors=%d",
        user_id, result.draft_count, len(result.errors),
    )
    return result

"""
src/services/jobs_service.py
Business logic for job listing and dashboard actions.
Calls repositories — never reaches into DB or files directly.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from src.applications import (
    get_applied_jobs,
    get_job_id,
    is_applied,
    mark_applied,
)
from src.db import is_db_available
from src.repositories import jobs_repo
from src.repositories.profile_repo import get_profile as get_user_profile
from src.services.job_match_explanation import build_match_explanation

logger = logging.getLogger(__name__)
_PERSONALIZED_DB_FETCH_FLOOR = 1000


def list_jobs(
    page: int = 1,
    limit: int = 20,
    min_score: int = 0,
    source: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated job list. DB preferred; applied_jobs.json fallback.
    jobs table is global feed, but scoring is personalized with user_id."""
    offset = (page - 1) * limit

    if is_db_available():
        if user_id:
            fetch_limit = max(page * limit, _PERSONALIZED_DB_FETCH_FLOOR)
            result = jobs_repo.list_from_db(0, fetch_limit, 0, source)
            if result is not None:
                jobs = result.get("jobs", [])
                return _score_and_paginate_jobs(
                    jobs=jobs,
                    user_id=user_id,
                    offset=offset,
                    limit=limit,
                    min_score=min_score,
                )

        result = jobs_repo.list_from_db(offset, limit, min_score, source)
        if result is not None:
            return _attach_match_explanations(result, user_id=user_id)

    return _list_from_json(offset, limit, min_score, user_id)


def _list_from_json(offset: int, limit: int, min_score: int, user_id: Optional[str] = None) -> Dict[str, Any]:
    from src.job_history import load_job_history
    all_jobs = load_job_history()

    if all_jobs and user_id:
        return _score_and_paginate_jobs(
            jobs=all_jobs,
            user_id=user_id,
            offset=offset,
            limit=limit,
            min_score=min_score,
        )

    filtered = [j for j in all_jobs if isinstance(j, dict) and j.get("score", 0) >= min_score]
    filtered.sort(key=lambda j: j.get("score", 0), reverse=True)
    total = len(filtered)
    page_jobs = filtered[offset : offset + limit]
    return _attach_match_explanations({
        "jobs": page_jobs,
        "total": total,
        "page": offset // limit + 1,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }, user_id=user_id)


def _score_and_paginate_jobs(
    jobs: list[Dict[str, Any]],
    user_id: str,
    offset: int,
    limit: int,
    min_score: int,
) -> Dict[str, Any]:
    """Score the full candidate window for one user, then filter, sort, and paginate."""
    from src.scoring import score_jobs_for_user

    personalized_jobs = [dict(job) for job in jobs if isinstance(job, dict)]
    scored_jobs = score_jobs_for_user(personalized_jobs, user_id)

    filtered = [
        job for job in scored_jobs
        if isinstance(job, dict) and int(job.get("score", 0) or 0) >= min_score
    ]
    filtered.sort(
        key=lambda job: (
            int(job.get("score", 0) or 0),
            str(job.get("title", "")).lower(),
            str(get_job_id(job) or ""),
        ),
        reverse=True,
    )

    total = len(filtered)
    page_jobs = filtered[offset : offset + limit]
    return _attach_match_explanations({
        "jobs": page_jobs,
        "total": total,
        "page": offset // limit + 1,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }, user_id=user_id)


def _load_profile_for_jobs(user_id: Optional[str]) -> Any | None:
    if not user_id:
        return None

    try:
        return get_user_profile(user_id)
    except Exception:
        logger.exception("job match explanation profile lookup failed user_id=%s", user_id)
        return None


def _attach_match_explanations(
    result: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    jobs = result.get("jobs", [])
    if not isinstance(jobs, list):
        return result

    profile = _load_profile_for_jobs(user_id)
    enriched_jobs = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_data = dict(job)
        job_data["match_explanation"] = build_match_explanation(job_data, profile)
        enriched_jobs.append(job_data)

    return {**result, "jobs": enriched_jobs}


def _job_matches_id(job: Dict[str, Any], job_id: str) -> bool:
    """Check if job matches the given job_id across multiple field names."""
    if not isinstance(job, dict):
        return False

    candidates = {
        job.get("id"),
        job.get("job_id"),
        job.get("key"),
        job.get("job_key"),
        job.get("link"),
        job.get("url"),
        job.get("job_url"),
    }

    return str(job_id) in {str(value) for value in candidates if value is not None}


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Single job by DB integer id or SHA-256 job_id hash. jobs table is global feed."""
    if is_db_available() and job_id.isdigit():
        job = jobs_repo.get_by_db_id(int(job_id))
        if job:
            return job

    for job in get_applied_jobs():
        if _job_matches_id(job, job_id):
            return job

    # Fallback: search job_history.json (same source as list_jobs fallback)
    from src.job_history import load_job_history
    for item in load_job_history():
        # Handle both flat job objects and nested {"job": {...}} entries
        job = item.get("job") if isinstance(item, dict) and isinstance(item.get("job"), dict) else item
        if _job_matches_id(job, job_id):
            return job

    return None


def skip_job(job: Dict[str, Any], user_id: Optional[str] = None) -> bool:
    """Mark skipped. Returns True if newly persisted, False if already tracked."""
    if not user_id:
        raise ValueError("user_id is required for authenticated access")

    if is_applied(job, user_id=user_id):
        return False
    return mark_applied(job, status="decision_made", notes="Skipped via API", user_id=user_id)


def save_job(job: Dict[str, Any], user_id: Optional[str] = None) -> bool:
    """Mark saved. Returns True if newly persisted, False if already tracked."""
    if not user_id:
        raise ValueError("user_id is required for authenticated access")

    if is_applied(job, user_id=user_id):
        return False

    # Route through applications_repo so writes and count_saved_jobs reads use
    # the same store (DB when available). The repo enforces the saved-jobs limit
    # internally when status=="saved", so no separate gate call is needed here.
    from src.repositories.applications_repo import create as _repo_create

    return _repo_create(
        job_id=job.get("job_id", ""),
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        url=job.get("link", ""),
        status="saved",
        user_id=user_id,
    )


def block_company(job: Dict[str, Any], user_id: Optional[str] = None) -> str:
    """
    Block company for this user only (user-scoped, not global).
    Returns the blocked company name.
    Does NOT modify EXCLUDE_KEYWORDS (which affects all users).
    """
    if not user_id:
        raise ValueError("user_id is required for authenticated access")

    company = (job.get("company") or "").strip()
    if not company:
        raise ValueError("Job missing company field")

    if not is_applied(job, user_id=user_id):
        mark_applied(job, status="decision_made", notes="Company blocked via API", user_id=user_id)

    # TODO: Store user-specific blocked companies in database table
    # For now, just mark the job as blocked for this user
    logger.info("block_company: user=%s blocked company=%r", user_id, company)

    return company

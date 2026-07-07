"""
src/api/routers/job_lifecycle.py
Application Lifecycle API — track where each job sits in the user's funnel and
answer "show saved jobs", "what jobs did I apply to?", and "show jobs I opened
but did not apply to".

State lives on user_job_context (the chat-side job memory), keyed by
(user_id, title, company). Identity always comes from the JWT — callers cannot
read or mutate another user's funnel.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.deps import get_current_user
from src.api.rate_limit import LIMIT_CHAT, limiter
from src.job_lifecycle import normalize_status
from src.repositories import user_job_context_repo as repo
from src.schemas.job_lifecycle import (
    FollowupJob,
    FollowupListResponse,
    LifecycleJob,
    LifecycleListResponse,
    LifecycleUpdateRequest,
    LifecycleUpdateResponse,
)
from src.services.operational_memory_readiness import (
    DEFAULT_REVISIT_DAYS,
    select_revisit_candidates,
)

router = APIRouter(prefix="/api/v1/jobs/lifecycle", tags=["lifecycle"])


def _iso(value) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else (value or None)


def _to_job(row: dict) -> LifecycleJob:
    return LifecycleJob(
        title=row.get("title", ""),
        company=row.get("company", ""),
        location=row.get("location"),
        status=row.get("status"),
        apply_url=row.get("apply_url", "") or "",
        source_url=row.get("source_url", "") or "",
        saved_at=_iso(row.get("saved_at")),
        opened_at=_iso(row.get("opened_at")),
        prepared_at=_iso(row.get("prepared_at")),
        applied_at=_iso(row.get("applied_at")),
    )


def _to_followup_job(candidate) -> FollowupJob:
    return FollowupJob(
        title=candidate.title,
        company=candidate.company,
        apply_url=candidate.apply_url,
        source_url=candidate.source_url,
        applied_at=candidate.applied_at.isoformat(),
        days_since_applied=candidate.days_since_applied,
    )


@router.post("", response_model=LifecycleUpdateResponse)
@limiter.limit(LIMIT_CHAT)
def set_status(
    request: Request,
    req: LifecycleUpdateRequest,
    user: dict = Depends(get_current_user),
) -> LifecycleUpdateResponse:
    """Move a job to a lifecycle status (and stamp the matching timestamp)."""
    norm = normalize_status(req.status)
    if not norm:
        return LifecycleUpdateResponse(
            ok=False, status="", message=f"Invalid status '{req.status}'."
        )
    ok = repo.set_lifecycle_status(
        user_id=user["email"],
        title=req.title,
        company=req.company,
        status=norm,
        apply_url=req.apply_url,
        source_url=req.source_url,
        note=req.note,
    )
    return LifecycleUpdateResponse(
        ok=ok,
        status=norm if ok else "",
        message=f"Job marked as {norm}." if ok else "Could not update job status.",
    )


@router.get("", response_model=LifecycleListResponse)
@limiter.limit(LIMIT_CHAT)
def list_by_status(
    request: Request,
    status: str = Query(..., description="Lifecycle status to filter by"),
    limit: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> LifecycleListResponse:
    """List the authenticated user's jobs at a given lifecycle status."""
    rows = repo.get_by_status(user["email"], status, limit=limit)
    jobs = [_to_job(r) for r in rows]
    return LifecycleListResponse(ok=True, count=len(jobs), jobs=jobs)


@router.get("/follow-ups", response_model=FollowupListResponse)
@limiter.limit(LIMIT_CHAT)
def list_followups(
    request: Request,
    min_days_since_applied: int = Query(DEFAULT_REVISIT_DAYS, ge=0, le=90),
    limit: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> FollowupListResponse:
    """List applied jobs that are old enough to revisit/follow up.

    Read-only: this does not send notifications, write DB rows, or mutate
    application state. Identity comes only from the authenticated user.
    """
    rows = repo.get_by_status(user["email"], "applied", limit=100)
    candidates = select_revisit_candidates(
        rows,
        min_days_since_applied=min_days_since_applied,
        limit=limit,
    )
    jobs = [_to_followup_job(candidate) for candidate in candidates]
    return FollowupListResponse(ok=True, count=len(jobs), jobs=jobs)


@router.get("/opened-not-applied", response_model=LifecycleListResponse)
@limiter.limit(LIMIT_CHAT)
def list_opened_not_applied(
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> LifecycleListResponse:
    """Jobs opened externally but never marked as applied."""
    rows = repo.get_opened_not_applied(user["email"], limit=limit)
    jobs = [_to_job(r) for r in rows]
    return LifecycleListResponse(ok=True, count=len(jobs), jobs=jobs)

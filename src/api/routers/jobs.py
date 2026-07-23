"""
src/api/routers/jobs.py
Thin HTTP layer for job actions. All logic lives in src.services.jobs_service.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_current_user
from src.schemas.jobs import JobActionRequest, JobActionResponse, JobListResponse
from src.services.apply_service import apply_to_job
from src.services.jobs_service import (
    block_company,
    get_job,
    list_jobs,
    save_job,
    skip_job,
)
from src.services.subscription_gating import enforce_saved_job_allowed
from src.mutation_guard import MutationConfirmationGuard, MutationResult

_MUTATION_CONFIRMATION_GUARD = MutationConfirmationGuard()

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _current_user_id(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("email")
        or current_user.get("sub")
        or current_user.get("id")
        or ""
    )


def _resolve_action_job(job_id: str, req: Optional[JobActionRequest] = None) -> Dict[str, Any]:
    body_job = req.job if req and req.job else None
    client_job_id = body_job.get("job_id") or body_job.get("id") if body_job else None
    if client_job_id and str(client_job_id) != job_id:
        raise HTTPException(status_code=422, detail="Job object in request body does not match job_id in URL")
    job = get_job(job_id)
    if job:
        return job
    if body_job:
        return {"id": job_id, **body_job}
    raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")


@router.get("", response_model=JobListResponse)
def get_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    min_score: int = Query(0, ge=0, le=100),
    source: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = _current_user_id(current_user)
    return list_jobs(page=page, limit=limit, min_score=min_score, source=source, user_id=user_id)


@router.get("/{job_id}")
def get_job_by_id(
    job_id: str,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job


@router.post("/{job_id}/apply", response_model=JobActionResponse)
def apply_job(
    job_id: str,
    req: Optional[JobActionRequest] = None,
    current_user: dict = Depends(get_current_user),
) -> JobActionResponse:
    user_id = _current_user_id(current_user)
    job = _resolve_action_job(job_id, req)

    # Attempt browser automation (no-op in cloud when NG_ENABLED=false).
    # This is an explicit, authenticated, per-job apply action initiated by the user
    # (they POSTed to apply to this specific job), so it carries the approval the
    # apply_to_job safety gate requires. Agent/automation paths never set approved=True.
    result = apply_to_job(job, approved=True, user_id=user_id)

    # Regardless of automation outcome, record the apply action in the
    # lifecycle tracker so the /flow page and application history stay
    # consistent.  We record even for "unsupported" sources because the
    # user's intention to apply is what matters for tracking.
    try:
        from src.repositories.user_job_context_repo import (
            record_interaction,
            set_lifecycle_status,
        )
        from src.job_lifecycle import lifecycle_for_action

        from src.services.job_link_trust import validate_job_url

        record_interaction(
            user_id=user_id,
            title=job.get("title", ""),
            company=job.get("company", ""),
            action="apply",
        )
        lc = lifecycle_for_action("apply")
        if lc:
            lc_status, _ = lc
            raw_link = job.get("apply_link") or job.get("link") or ""
            safe_link = validate_job_url(raw_link)
            set_lifecycle_status(
                user_id=user_id,
                title=job.get("title", ""),
                company=job.get("company", ""),
                status=lc_status,
                apply_url=safe_link,
                source_url=validate_job_url(job.get("link") or ""),
            )
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).debug(
            "apply tracking failed user=%s job=%s", user_id, job_id, exc_info=True
        )

    return JobActionResponse(
        status=result.get("status", "unknown"),
        message=result.get("message", ""),
        job_id=result.get("job_id"),
    )


@router.post("/{job_id}/skip", response_model=JobActionResponse)
def skip_job_route(
    job_id: str,
    req: Optional[JobActionRequest] = None,
    current_user: dict = Depends(get_current_user),
) -> JobActionResponse:
    user_id = _current_user_id(current_user)
    job = _resolve_action_job(job_id, req)
    skipped = skip_job(job, user_id=user_id)
    if skipped:
        return JobActionResponse(status="skipped", message="Job skipped and persisted")
    return JobActionResponse(status="already_tracked", message="Job was already tracked")


@router.post("/{job_id}/save", response_model=JobActionResponse)
def save_job_route(
    job_id: str,
    req: Optional[JobActionRequest] = None,
    current_user: dict = Depends(get_current_user),
) -> JobActionResponse:
    user_id = _current_user_id(current_user)
    enforce_saved_job_allowed(user_id)
    job = _resolve_action_job(job_id, req)
    saved = save_job(job, user_id=user_id)
    if saved:
        from src.applications import get_job_id
        from src.repositories import applications_repo

        job_key = get_job_id(job)
        confirmed = _MUTATION_CONFIRMATION_GUARD.confirm(
            MutationResult(success=True),
            verifier=lambda: (
                (applications_repo.find_by_job_id(job_key, user_id=user_id) or {}).get("status")
                == "saved"
            ),
            success_en="confirmed",
            success_ar="confirmed",
            failure_en="failed",
            failure_ar="failed",
        ) == "confirmed"
        if not confirmed:
            raise HTTPException(status_code=500, detail="Job save could not be confirmed. Please try again.")
        return JobActionResponse(status="saved", message="Job saved and persisted")
    return JobActionResponse(status="already_tracked", message="Job was already tracked")


@router.post("/{job_id}/block", response_model=JobActionResponse)
def block_job_route(
    job_id: str,
    req: Optional[JobActionRequest] = None,
    current_user: dict = Depends(get_current_user),
) -> JobActionResponse:
    user_id = _current_user_id(current_user)
    job = _resolve_action_job(job_id, req)
    try:
        company = block_company(job, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JobActionResponse(
        status="blocked",
        message=f"Blocked: {company}. This block is scoped to your account.",
    )

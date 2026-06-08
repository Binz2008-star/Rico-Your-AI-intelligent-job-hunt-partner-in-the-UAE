"""
src/api/routers/applications.py
Thin HTTP layer for tracked applications.
All data access goes through src.repositories.applications_repo.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Map outcome statuses to the action type that best represents them for
# learning-signal inference.  "interview" and "offer" are positive signals;
# "rejected" is a mild negative.  Other statuses carry no learning signal.
_OUTCOME_ACTION_MAP: Dict[str, str] = {
    "interview": "save",       # mutual positive interest → weight +0.5
    "offer":     "apply",      # strongest positive signal  → weight +0.8
    "rejected":  "not_relevant",  # mild negative           → weight −0.2
}

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_current_user_id
from src.applications import VALID_STATUSES
from src.repositories.applications_repo import create, create_manual, find_by_job_id, get_all, get_stats, update_status
from src.schemas.applications import (
    ApplicationCreateRequest,
    ApplicationListResponse,
    ManualApplicationCreateRequest,
    StatusUpdateRequest,
    StatusUpdateResponse,
)

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


def _fire_outcome_signal(user_id: str, status: str, application: Dict[str, Any]) -> None:
    """Dispatch a background thread that records a learning signal for an outcome."""
    mapped_action = _OUTCOME_ACTION_MAP.get(status)
    if not mapped_action:
        return

    def _run() -> None:
        try:
            from src.repositories.learning_repo import get_learning_repository
            get_learning_repository().infer_signals_from_job_action(
                user_id, mapped_action, application
            )
            logger.debug(
                "outcome_learning_signal status=%s action=%s user=%s title=%r",
                status, mapped_action, user_id, application.get("title", ""),
            )
        except Exception:
            logger.debug("outcome_learning_signal_failed status=%s user=%s", status, user_id, exc_info=True)

    threading.Thread(target=_run, daemon=True).start()


@router.post("", response_model=StatusUpdateResponse)
def create_application(
    req: ApplicationCreateRequest,
    user_id: str = Depends(get_current_user_id),
) -> StatusUpdateResponse:
    if req.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status {req.status!r}. Valid: {sorted(VALID_STATUSES)}",
        )

    ok = create(
        job_id=req.job_id,
        title=req.title,
        company=req.company,
        location=req.location,
        url=req.url,
        status=req.status,
        source=req.source,
        user_id=user_id,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create application record")

    return StatusUpdateResponse(
        status=req.status,
        job_id=req.job_id,
        message="Application record created",
    )


@router.post("/manual", response_model=StatusUpdateResponse)
def create_manual_application(
    req: ManualApplicationCreateRequest,
    user_id: str = Depends(get_current_user_id),
) -> StatusUpdateResponse:
    if req.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status {req.status!r}. Valid: {sorted(VALID_STATUSES)}",
        )

    ok = create_manual(
        title=req.title,
        company=req.company,
        location=req.location,
        url=req.url,
        status=req.status,
        user_id=user_id,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create manual application record")

    # Generate job_id for response
    raw = f"{req.title}|{req.company}|{req.location}".lower().strip()
    job_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    return StatusUpdateResponse(
        status=req.status,
        job_id=job_id,
        message="Manual application record created",
    )


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    if status and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Valid values: {sorted(VALID_STATUSES)}",
        )

    all_apps: List[Dict[str, Any]] = get_all(user_id=user_id)
    if status:
        all_apps = [a for a in all_apps if a.get("status") == status]

    total = len(all_apps)
    offset = (page - 1) * limit
    return {
        "applications": all_apps[offset : offset + limit],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }


@router.patch("/{job_id}", response_model=StatusUpdateResponse)
def update_application(
    job_id: str,
    req: StatusUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> StatusUpdateResponse:
    if req.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status {req.status!r}. Valid: {sorted(VALID_STATUSES)}",
        )

    target = find_by_job_id(job_id, user_id=user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Application {job_id!r} not found")

    ok = update_status(target, req.status, user_id, req.notes or "")
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update application status")

    # Fire-and-forget learning signal for outcome status transitions.
    # Runs in a daemon thread so it never delays the HTTP response.
    if req.status in _OUTCOME_ACTION_MAP:
        _fire_outcome_signal(user_id, req.status, target)

    return StatusUpdateResponse(status=req.status, job_id=job_id, message="Status updated")


@router.get("/stats")
def application_stats(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    from src.repositories.jobs_repo import get_pipeline_stats
    app_stats = get_stats(user_id=user_id)
    pipeline = get_pipeline_stats()
    return {**app_stats, **pipeline}

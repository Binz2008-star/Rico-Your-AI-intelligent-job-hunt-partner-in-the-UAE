"""
src/api/routers/pipeline.py
Thin HTTP layer for pipeline status and manual trigger.
All state management lives in src.services.pipeline_service.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.deps import get_current_user, require_admin, require_cron_secret
from src.schemas.pipeline import (
    PipelineStatusResponse,
    PipelineTriggerResponse,
    RemindersResponse,
)
from src.services.followup_service import DEFAULT_FOLLOWUP_INTERVAL_DAYS, run_due_scan
from src.services.pipeline_service import get_status, trigger

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.get("/status", response_model=PipelineStatusResponse)
def pipeline_status(_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    return get_status()


@router.post("/trigger", response_model=PipelineTriggerResponse)
def trigger_pipeline(_user: dict = Depends(require_admin)) -> PipelineTriggerResponse:
    try:
        trigger()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return PipelineTriggerResponse(
        status="triggered",
        message="Pipeline started. Poll /api/v1/pipeline/status for progress.",
    )


@router.post("/reminders", response_model=RemindersResponse)
def run_reminders(
    request: Request,
    _cron: None = Depends(require_cron_secret),
) -> RemindersResponse:
    """Follow-up reminder sweep (Issue #355), called by Render Cron.

    Guarded by the X-Cron-Secret shared secret (not JWT). Transitions applied
    jobs older than the interval to ``follow_up_due`` so they surface on /flow.
    Idempotent. Optional ``?interval_days=N`` overrides the 7-day default.
    """
    raw = request.query_params.get("interval_days")
    interval = DEFAULT_FOLLOWUP_INTERVAL_DAYS
    if raw is not None:
        try:
            interval = int(raw)
        except ValueError:
            raise HTTPException(status_code=422, detail="interval_days must be an integer")
        if interval < 1:
            raise HTTPException(status_code=422, detail="interval_days must be >= 1")

    summary = run_due_scan(interval)
    return RemindersResponse(**summary)

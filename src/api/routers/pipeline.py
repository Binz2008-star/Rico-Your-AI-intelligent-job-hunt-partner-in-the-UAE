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
    JobAlertEmailsResponse,
    PipelineStatusResponse,
    PipelineTriggerResponse,
    ProfileNudgeResponse,
    RemindersResponse,
)
from src.services.followup_service import DEFAULT_FOLLOWUP_INTERVAL_DAYS, run_due_scan
from src.services.pipeline_service import get_status, trigger
from src.services.profile_nudge_service import run_profile_nudge_sweep

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


@router.post("/job-alert-emails", response_model=JobAlertEmailsResponse)
def run_job_alert_emails(
    request: Request,
    _cron: None = Depends(require_cron_secret),
) -> JobAlertEmailsResponse:
    """Personalized job-alert email sweep, called by cron (Render/GitHub).

    Guarded by the X-Cron-Secret shared secret (not JWT). Sends one digest email
    of top matches to each opted-in user, respecting dedup and the per-user
    daily/weekly cadence. Idempotent within a cadence window.

    Sending requires ``RICO_ENABLE_EMAIL_ALERTS`` to be truthy. Pass
    ``?dry_run=true`` to evaluate matching and report counts WITHOUT sending or
    logging (this bypasses the kill-switch for smoke testing).
    """
    from src.services.email_alert_service import run_email_alert_sweep

    raw = (request.query_params.get("dry_run") or "").strip().lower()
    dry_run = raw in {"1", "true", "yes", "on"}
    summary = run_email_alert_sweep(dry_run=dry_run)
    return JobAlertEmailsResponse(**summary)


@router.post("/profile-nudge", response_model=ProfileNudgeResponse)
def run_profile_nudge(
    _cron: None = Depends(require_cron_secret),
) -> ProfileNudgeResponse:
    """One-time profile completion nudge sweep (requires migration 029).

    Finds users registered > 24 h ago with no nudge sent yet and an incomplete
    profile (missing CV, target roles, or preferred cities), sends them a single
    email, and stamps profile_nudge_sent_at so the sweep is idempotent.
    Guarded by X-Cron-Secret. Safe to call repeatedly — never double-sends.
    """
    summary = run_profile_nudge_sweep()
    return ProfileNudgeResponse(**summary)

"""
src/api/routers/pipeline.py
Thin HTTP layer for pipeline status and manual trigger.
All state management lives in src.services.pipeline_service.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.deps import get_current_user, require_admin, require_cron_secret
from src.schemas.pipeline import (
    AdminDigestResponse,
    AnalyticsPurgeResponse,
    JobAlertEmailsResponse,
    PipelineStatusResponse,
    PipelineTriggerResponse,
    ProfileNudgeResponse,
    RemindersResponse,
    ScheduledSearchSweepResponse,
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


@router.post("/scheduled-searches", response_model=ScheduledSearchSweepResponse)
def run_scheduled_searches(
    request: Request,
    _cron: None = Depends(require_cron_secret),
) -> ScheduledSearchSweepResponse:
    """Scheduled saved-search sweep (#1249), called by cron (Render/GitHub).

    Guarded by the X-Cron-Secret shared secret (not JWT). Executes each
    ENABLED scheduled search with its saved constraints (city, minimum AED
    salary) and stores new results in-app on the schedule row. Sends NO email
    — email alerts remain the separate opt-in sweep. Idempotent across runs
    via per-schedule delivered-key dedup.

    Execution requires ``RICO_ENABLE_SCHEDULED_SEARCHES`` to be truthy. Pass
    ``?dry_run=true`` to evaluate matching and report counts WITHOUT
    persisting results or dedup keys (bypasses the kill switch for smoke
    testing, mirroring the email sweep's semantics).
    """
    from src.services.scheduled_search_service import run_scheduled_search_sweep

    raw = (request.query_params.get("dry_run") or "").strip().lower()
    dry_run = raw in {"1", "true", "yes", "on"}
    summary = run_scheduled_search_sweep(dry_run=dry_run)
    return ScheduledSearchSweepResponse(**summary)


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


# Kill switch for the scheduled analytics retention purge (DEC-20260719-001).
# Default OFF (fail-closed): disabled runs are an explicit 200 no-op that never
# touches the repository, so a scheduled caller never pages on the gate.
_ANALYTICS_PURGE_FLAG = "RICO_ENABLE_ANALYTICS_PURGE"


def _analytics_purge_enabled() -> bool:
    return os.getenv(_ANALYTICS_PURGE_FLAG, "false").strip().lower() in {"1", "true", "yes", "on"}


@router.post("/analytics-purge", response_model=AnalyticsPurgeResponse)
def run_analytics_purge(
    request: Request,
    _cron: None = Depends(require_cron_secret),
) -> AnalyticsPurgeResponse:
    """Scheduled analytics_events retention purge (migration 047 contract).

    Deletes rows older than the fixed ``RETENTION_DAYS`` constant in
    src/repositories/analytics_events_repo.py. The retention window is NEVER
    caller-controlled: no query parameter or body field can change it —
    changing the window is a reviewed code change (DEC-20260719-001).

    Guarded twice: the X-Cron-Secret shared secret AND the
    ``RICO_ENABLE_ANALYTICS_PURGE`` kill switch (default off). Idempotent —
    reruns delete nothing new, and a table-absent database is a fail-soft
    zero. Pass ``?dry_run=true`` to report the would-delete count (built from
    the same predicate as the DELETE) without deleting.
    """
    from src.repositories.analytics_events_repo import (
        RETENTION_DAYS,
        count_expired,
        purge_expired,
    )

    raw = (request.query_params.get("dry_run") or "").strip().lower()
    dry_run = raw in {"1", "true", "yes", "on"}

    if not _analytics_purge_enabled():
        return AnalyticsPurgeResponse(
            status="disabled", removed=0, retention_days=RETENTION_DAYS, dry_run=dry_run,
        )
    if dry_run:
        return AnalyticsPurgeResponse(
            status="dry_run",
            removed=0,
            would_remove=count_expired(),
            retention_days=RETENTION_DAYS,
            dry_run=True,
        )
    return AnalyticsPurgeResponse(
        status="ok", removed=purge_expired(), retention_days=RETENTION_DAYS, dry_run=False,
    )


@router.post("/admin-digest", response_model=AdminDigestResponse)
def run_admin_digest(
    request: Request,
    _cron: None = Depends(require_cron_secret),
) -> AdminDigestResponse:
    """Weekly admin activation digest (issue #922; requires migration 036).

    Aggregates the previous full ISO week of signup/activation metrics and
    emails one summary to the admin recipient. Guarded by X-Cron-Secret.
    Idempotent per ISO week: reruns return status="already_sent" without
    emailing. Pass ``?dry_run=true`` to compute metrics WITHOUT claiming the
    week or sending.
    """
    from src.services.admin_digest_service import run_weekly_admin_digest

    raw = (request.query_params.get("dry_run") or "").strip().lower()
    dry_run = raw in {"1", "true", "yes", "on"}
    summary = run_weekly_admin_digest(dry_run=dry_run)
    return AdminDigestResponse(**summary)

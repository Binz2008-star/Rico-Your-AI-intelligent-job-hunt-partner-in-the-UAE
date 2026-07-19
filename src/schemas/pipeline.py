from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PipelineStatusResponse(BaseModel):
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    jobs_found: int = 0
    error: Optional[str] = None
    run_id: Optional[int] = None

    model_config = {"extra": "allow"}


class PipelineTriggerResponse(BaseModel):
    status: str
    message: str


class RemindersResponse(BaseModel):
    status: str
    interval_days: int
    marked_due: int = 0


class ProfileNudgeResponse(BaseModel):
    status: str
    nudges_sent: int = 0
    nudges_failed: int = 0
    skipped: int = 0
    skipped_synthetic: int = 0


class JobAlertEmailsResponse(BaseModel):
    status: str
    users: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    dry_run: bool = False


class AnalyticsPurgeResponse(BaseModel):
    status: str  # "disabled" | "dry_run" | "ok"
    removed: int = 0
    would_remove: Optional[int] = None  # dry-run only: rows a real run would delete
    retention_days: int
    dry_run: bool = False


class AdminDigestResponse(BaseModel):
    status: str
    sent: bool = False
    dry_run: bool = False
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    metrics: Optional[dict] = None

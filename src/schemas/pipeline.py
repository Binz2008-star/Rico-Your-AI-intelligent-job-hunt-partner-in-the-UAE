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

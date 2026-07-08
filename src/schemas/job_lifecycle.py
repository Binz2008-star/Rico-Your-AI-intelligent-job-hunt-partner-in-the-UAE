"""
src/schemas/job_lifecycle.py
HTTP contracts for the Application Lifecycle endpoints
(POST/GET /api/v1/jobs/lifecycle).
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.job_lifecycle import LIFECYCLE_STATUSES

_VALID = ", ".join(LIFECYCLE_STATUSES)


class LifecycleUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    company: str = Field(..., min_length=1, max_length=512)
    status: str = Field(..., description=f"One of: {_VALID}")
    apply_url: str = Field("", max_length=2048)
    source_url: str = Field("", max_length=2048)
    note: Optional[str] = Field(None, max_length=2000)


class LifecycleJob(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    status: Optional[str] = None
    apply_url: str = ""
    source_url: str = ""
    saved_at: Optional[str] = None
    opened_at: Optional[str] = None
    prepared_at: Optional[str] = None
    applied_at: Optional[str] = None


class FollowupJob(BaseModel):
    title: str
    company: str
    apply_url: str = ""
    source_url: str = ""
    applied_at: str
    days_since_applied: int


class LifecycleUpdateResponse(BaseModel):
    ok: bool
    status: str
    message: str


class LifecycleListResponse(BaseModel):
    ok: bool
    count: int
    jobs: List[LifecycleJob]


class FollowupListResponse(BaseModel):
    ok: bool
    count: int
    jobs: List[FollowupJob]

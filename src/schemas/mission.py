"""src/schemas/mission.py
MissionState — the canonical Career OS object for Sprint 1.

Computed entirely from existing tables (profile, job_recommendations).
No new DB schema required.
"""
from __future__ import annotations

from pydantic import BaseModel


class MissionState(BaseModel):
    # What the user is trying to accomplish
    goal: str
    target_roles: list[str]
    target_locations: list[str]

    # CV evidence
    cv_status: str  # "uploaded" | "missing"

    # Pipeline activity (real counts from rico_job_recommendations)
    jobs_saved: int
    applications_sent: int

    # Progress: 4 binary factors × 25 pts each (0, 25, 50, 75, or 100)
    progress_score: int
    missing_factors: list[str]

    # Rico's one-sentence next best action
    next_recommendation: str
    blocking_reason: str | None = None

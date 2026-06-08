from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_applied: int
    status_breakdown: Dict[str, int]
    interviews_scheduled: int
    rejections: int
    pending: int
    success_rate: float
    jobs_total: int = 0
    avg_score: int = 0
    new_today: int = 0

    model_config = {"extra": "allow"}

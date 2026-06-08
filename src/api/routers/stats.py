"""
src/api/routers/stats.py
Aggregated statistics — applications + jobs pipeline.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user_id
from src.repositories.applications_repo import get_stats
from src.repositories.jobs_repo import get_pipeline_stats

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("")
def get_stats_route(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    app_stats = get_stats(user_id=user_id)
    pipeline = get_pipeline_stats()
    return {**app_stats, **pipeline}

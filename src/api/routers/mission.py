"""src/api/routers/mission.py
GET /api/v1/mission/current — returns the authenticated user's MissionState.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user_id
from src.schemas.mission import MissionState
from src.services.mission_service import compute_mission

router = APIRouter(prefix="/api/v1/mission", tags=["mission"])


@router.get("/current", response_model=MissionState)
def get_current_mission(user_id: str = Depends(get_current_user_id)) -> MissionState:
    return compute_mission(user_id)

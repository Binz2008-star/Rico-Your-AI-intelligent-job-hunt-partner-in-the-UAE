"""Read-only pre-launch access decision used by the Next.js route gate."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request

from src.services.launch_mode import (
    get_launch_mode,
    is_internal_email,
    request_user_email,
)

router = APIRouter(prefix="/api/v1/prelaunch", tags=["prelaunch"])


@router.get("/access")
def prelaunch_access(request: Request) -> Dict[str, Any]:
    mode = get_launch_mode()
    allowed = mode != "waitlist" or is_internal_email(request_user_email(request))
    return {"mode": mode, "allowed": allowed}

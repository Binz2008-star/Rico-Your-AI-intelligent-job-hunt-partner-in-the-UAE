"""GET /api/v1/me — current session identity."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["user"])


@router.get("/me")
def me(request: Request) -> Dict[str, Any]:
    user = getattr(request.state, "current_user", None)
    if not isinstance(user, dict) or not user.get("email"):
        return {
            "email": None,
            "role": "guest",
            "authenticated": False,
            "guest": True,
        }

    return {
        "email":         user["email"],
        "role":          user.get("role", "user"),
        "authenticated": True,
    }

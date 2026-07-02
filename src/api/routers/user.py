"""GET /api/v1/me — current session identity."""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["user"])
logger = logging.getLogger(__name__)


def _fetch_display_name(email: str) -> str | None:
    """Best-effort lookup of the user's display name via RicoDB (same connection as profile endpoints)."""
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        bundle = db.get_user_bundle(email)
        return bundle.get("name") if bundle else None
    except Exception:
        logger.debug("me_name_lookup_failed email=%s", email)
        return None


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

    email = user["email"]
    return {
        "email":         email,
        "role":          user.get("role", "user"),
        "authenticated": True,
        "name":          _fetch_display_name(email),
    }

"""GET /api/v1/me — current session identity."""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["user"])
logger = logging.getLogger(__name__)


def _fetch_display_name(email: str) -> str | None:
    """Best-effort lookup of the user's display name from rico_users."""
    try:
        from src.db import get_db_connection
        conn = get_db_connection()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT name FROM rico_users WHERE email = %s LIMIT 1",
                    (email,),
                )
                row = cur.fetchone()
                return row[0] if row and row[0] else None
        finally:
            conn.close()
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

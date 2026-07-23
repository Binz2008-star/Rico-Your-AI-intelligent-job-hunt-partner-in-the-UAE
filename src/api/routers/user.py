"""GET /api/v1/me — current session identity."""
from __future__ import annotations

import logging

from src.log_privacy import user_ref
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from src.api.rate_limit import LIMIT_PROFILE, limiter

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
        logger.debug("me_name_lookup_failed user=%s", user_ref(email))
        return None


@router.get("/me")
@limiter.limit(LIMIT_PROFILE)
def me(request: Request) -> Dict[str, Any]:
    guest = {
        "email": None,
        "role": "guest",
        "authenticated": False,
        "guest": True,
    }
    # Middleware hydration is claims-only — use it to recognize the guest
    # shape cheaply, but never to assert identity (#1072).
    hydrated = getattr(request.state, "current_user", None)
    if not isinstance(hydrated, dict) or not hydrated.get("email"):
        return guest

    # Full verification (auth_version / is_active / DB role). A revoked or
    # deactivated token must render as logged-out here, not as the account;
    # a store outage stays a retryable 503 — never an identity guess.
    from src.api.deps import get_current_user
    try:
        user = get_current_user(request)
    except HTTPException as exc:
        if exc.status_code == 503:
            raise
        return guest

    email = user["email"]
    return {
        "email":         email,
        "role":          user.get("role", "user"),
        "authenticated": True,
        "name":          _fetch_display_name(email),
    }

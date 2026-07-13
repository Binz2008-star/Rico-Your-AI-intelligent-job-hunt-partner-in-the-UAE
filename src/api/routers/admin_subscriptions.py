"""Admin-only subscription management endpoints.

POST /api/v1/admin/subscriptions/activate  — manually activate a subscription
after receiving payment outside of an automated checkout (WhatsApp / bank transfer).
GET  /api/v1/admin/subscriptions/intents   — list recent upgrade intents for lead tracking.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr

from src.api.deps import require_admin
from src.db import get_subscription_intents
from src.repositories.users_repo import list_active_users

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/subscriptions", tags=["admin-subscriptions"])


class AdminActivateRequest(BaseModel):
    email: str
    plan: Literal["pro"]  # single-plan scope: Rico Monthly only
    duration_days: int
    payment_reference: Optional[str] = None


class AdminActivateResponse(BaseModel):
    success: bool
    email: str
    plan: str
    status: str
    expires_at: Optional[datetime]


@router.post("/activate", response_model=AdminActivateResponse)
def admin_activate_subscription(
    body: AdminActivateRequest,
    admin: Dict[str, Any] = Depends(require_admin),
) -> AdminActivateResponse:
    """Manually activate a subscription for a user by email.

    Finds the user, sets their subscription to active with the requested plan
    and expiry. Logs payment_reference; DB column reserved for future schema.
    """
    from src.db import is_db_available
    from src.repositories.users_repo import get_user_by_email
    from src.repositories import paddle_repo

    email = body.email.strip().lower()

    if body.duration_days < 1 or body.duration_days > 3650:
        raise HTTPException(status_code=422, detail="duration_days must be between 1 and 3650")

    if not is_db_available():
        raise HTTPException(status_code=503, detail="Database unavailable. Please retry.")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail=f"No active user found with email: {email}")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=body.duration_days)

    if body.payment_reference:
        logger.info(
            "admin_activate: user=%s plan=%s duration_days=%d payment_ref=%s activated_by=%s",
            email, body.plan, body.duration_days, body.payment_reference, admin.get("email"),
        )
    else:
        logger.info(
            "admin_activate: user=%s plan=%s duration_days=%d activated_by=%s",
            email, body.plan, body.duration_days, admin.get("email"),
        )

    # Manually-activated subscriptions have no real Paddle IDs — use stable
    # sentinels so repeat activations for the same email upsert cleanly
    # (paddle_subscriptions.user_id is the unique key regardless).
    try:
        result = paddle_repo.upsert_paddle_subscription(
            None,
            user_id=email,
            paddle_subscription_id=f"admin_manual_{email}",
            paddle_customer_id=f"admin_manual_{email}",
            plan=body.plan,
            status="active",
            current_period_start=now,
            current_period_end=expires_at,
            clear_past_due=True,
        )
    except Exception:
        logger.exception("admin_activate_failed user=%s", email)
        result = None

    if not result:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Subscription could not be activated.",
        )

    return AdminActivateResponse(
        success=True,
        email=email,
        plan=body.plan,
        status="active",
        expires_at=expires_at,
    )


@router.get("/intents")
def list_upgrade_intents(
    limit: int = Query(default=100, le=500),
    _admin: str = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Return recent subscription upgrade intents for lead tracking."""
    return get_subscription_intents(limit=limit)


@router.get("/users")
def list_recent_signups(
    limit: int = Query(default=100, le=500),
    _admin: str = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Return recent signups for admin lead view."""
    users = list_active_users()
    result = []
    for u in users[-limit:]:
        result.append({
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        })
    # Signup source (issue #922) — best-effort; absent until migration 036 is applied.
    try:
        from src.repositories.users_repo import get_signup_sources
        sources = get_signup_sources([r["id"] for r in result])
    except Exception:
        sources = {}
    for r in result:
        r["signup_source"] = sources.get(r["id"])
    result.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return result

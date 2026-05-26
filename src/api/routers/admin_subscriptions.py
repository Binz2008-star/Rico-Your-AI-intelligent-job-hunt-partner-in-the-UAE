"""Admin-only subscription management endpoints.

POST /api/v1/admin/subscriptions/activate  — manually activate a subscription
after receiving payment outside of an automated checkout (WhatsApp / bank transfer).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from src.api.deps import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/subscriptions", tags=["admin-subscriptions"])


class AdminActivateRequest(BaseModel):
    email: str
    plan: Literal["pro", "premium"]
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
    from src.repositories.subscription_repo import upsert_subscription

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

    result = upsert_subscription(
        user_id=email,
        plan=body.plan,
        status="active",
        current_period_start=now,
        current_period_end=expires_at,
        cancel_at=None,
        canceled_at=None,
        clear_cancellation=True,
    )

    if result is None:
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

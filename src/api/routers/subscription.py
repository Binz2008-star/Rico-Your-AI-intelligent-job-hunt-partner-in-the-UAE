"""Read-only subscription plan/status endpoints.

Checkout, portal, and webhook processing live in
src/api/routers/paddle_billing.py — this router only exposes the plan
catalog and the current user's resolved status (both backed by
src/subscription_plans.resolve_effective_user_plan, which reads Paddle
subscription state).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_current_user_id
from src.db import record_subscription_intent
from src.schemas.subscription import (
    PlansResponse,
    SubscriptionIntentRequest,
    SubscriptionIntentResponse,
    SubscriptionResponse,
)
from src.subscription_plans import list_paid_plans, resolve_effective_user_plan

router = APIRouter(prefix="/api/v1/subscription", tags=["subscription"])


@router.post("/intent", response_model=SubscriptionIntentResponse)
async def record_upgrade_intent(
    body: SubscriptionIntentRequest,
    request: Request,
) -> SubscriptionIntentResponse:
    """Fire-and-forget upgrade intent log. Works for both authenticated and anonymous users."""
    user_id: Optional[str] = None
    email: Optional[str] = None
    try:
        from src.api.deps import get_current_user
        user = get_current_user(request)
        user_id = user.get("email", "").strip() or None
        email = user_id
    except Exception:
        pass  # unauthenticated — record without user info

    recorded = record_subscription_intent(
        plan=body.plan,
        billing_mode=body.billing_mode,
        user_id=user_id,
        email=email,
        source_page=body.source_page,
    )
    return SubscriptionIntentResponse(recorded=recorded)


@router.get("/plans", response_model=PlansResponse)
def get_subscription_plans() -> PlansResponse:
    return list_paid_plans()


@router.get("/me", response_model=SubscriptionResponse)
def get_my_subscription(user_id: str = Depends(get_current_user_id)) -> SubscriptionResponse:
    return resolve_effective_user_plan(user_id)

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user_id
from src.schemas.subscription import (
    CheckoutResponse,
    PlansResponse,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SubscriptionWebhookResponse,
    WebhookEvent,
)
from src.subscription_plans import (
    build_checkout_response,
    handle_subscription_webhook,
    list_paid_plans,
    resolve_effective_user_plan,
)

router = APIRouter(prefix="/api/v1/subscription", tags=["subscription"])


@router.get("/plans", response_model=PlansResponse)
def get_subscription_plans() -> PlansResponse:
    return list_paid_plans()


@router.get("/me", response_model=SubscriptionResponse)
def get_my_subscription(user_id: str = Depends(get_current_user_id)) -> SubscriptionResponse:
    return resolve_effective_user_plan(user_id)


@router.post("/checkout", response_model=CheckoutResponse)
def create_subscription_checkout(
    request: SubscriptionCreateRequest,
    user_id: str = Depends(get_current_user_id),
) -> CheckoutResponse:
    try:
        return build_checkout_response(user_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/webhook", response_model=SubscriptionWebhookResponse)
def subscription_webhook(event: WebhookEvent) -> SubscriptionWebhookResponse:
    return handle_subscription_webhook(event)

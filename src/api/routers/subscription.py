from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError

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
    create_customer_portal_session,
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


@router.post("/portal", response_model=CheckoutResponse)
def create_customer_portal(
    user_id: str = Depends(get_current_user_id),
) -> CheckoutResponse:
    try:
        return create_customer_portal_session(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/webhook", response_model=SubscriptionWebhookResponse)
async def subscription_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
) -> SubscriptionWebhookResponse:
    payload = await request.body()
    try:
        body = json.loads(payload or b"{}")
        event = WebhookEvent.model_validate(body)
        return handle_subscription_webhook(event, payload=payload, signature=stripe_signature)
    except ValidationError as exc:
        if os.getenv("STRIPE_WEBHOOK_SECRET", "").strip():
            try:
                event = WebhookEvent(id="stripe_signed_event", type="stripe.signed", data={})
                return handle_subscription_webhook(event, payload=payload, signature=stripe_signature)
            except ValueError as inner_exc:
                raise HTTPException(status_code=400, detail=str(inner_exc))
        raise HTTPException(status_code=422, detail=exc.errors())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Stripe webhook processing failed")

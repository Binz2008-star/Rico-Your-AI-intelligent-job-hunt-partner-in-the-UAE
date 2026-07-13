from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from src.api.deps import get_current_user_id
from src.db import record_subscription_intent
from src.schemas.subscription import (
    CheckoutResponse,
    PlansResponse,
    SubscriptionCreateRequest,
    SubscriptionIntentRequest,
    SubscriptionIntentResponse,
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
    except RuntimeError as exc:
        logger.error("stripe_portal_session_failed user=%s error=%s", user_id, exc)
        raise HTTPException(status_code=502, detail="Could not create billing portal session")


@router.post("/webhook", response_model=SubscriptionWebhookResponse)
async def subscription_webhook(
    request: Request,
    paddle_signature: str | None = Header(default=None, alias="paddle-signature"),
) -> SubscriptionWebhookResponse:
    payload = await request.body()
    paddle_secret = os.getenv("PADDLE_WEBHOOK_SECRET", "").strip()
    try:
        if paddle_secret:
            # Signature-verified path: skip Pydantic entirely. Paddle's own payload
            # format may not match our schema, so we hand raw bytes + signature to
            # paddle_client.verify_webhook_signature() which is the authoritative check.
            # The sentinel is never inspected by handle_subscription_webhook here.
            sentinel = WebhookEvent(id="paddle_signed_event", type="paddle.signed", data={})
            return handle_subscription_webhook(sentinel, payload=payload, signature=paddle_signature)
        # No webhook secret: mock/dev mode — validate body with Pydantic normally.
        body = json.loads(payload or b"{}")
        event = WebhookEvent.model_validate(body)
        return handle_subscription_webhook(event, payload=payload, signature=None)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("paddle_webhook_error")
        raise HTTPException(status_code=500, detail="Paddle webhook processing failed")

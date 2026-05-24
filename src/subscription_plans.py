"""Rico Hunt subscription plans and entitlement helpers."""
from __future__ import annotations

import importlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from src.schemas.subscription import (
    CheckoutResponse,
    PlansResponse,
    SubscriptionCreateRequest,
    SubscriptionEntitlements,
    SubscriptionPlan,
    SubscriptionResponse,
    SubscriptionStatus,
    SubscriptionTier,
    SubscriptionWebhookResponse,
    UsageCheckResponse,
    UserSubscription,
    WebhookEvent,
)

FREE_ENTITLEMENTS = SubscriptionEntitlements(
    monthly_ai_message_limit=50,
    saved_jobs_limit=10,
    profile_optimization_limit=1,
    premium_recommendations_enabled=False,
    application_automation_enabled=False,
)

PRO_PLAN = SubscriptionPlan(
    id="pro_monthly",
    plan=SubscriptionTier.PRO,
    name="Pro",
    price_monthly=50,
    currency="AED",
    description="Higher Rico usage for active job seekers.",
    features=[
        "300 AI messages per month",
        "100 saved jobs",
        "20 profile optimizations per month",
    ],
    entitlements=SubscriptionEntitlements(
        monthly_ai_message_limit=300,
        saved_jobs_limit=100,
        profile_optimization_limit=20,
        premium_recommendations_enabled=False,
        application_automation_enabled=False,
    ),
)

PREMIUM_PLAN = SubscriptionPlan(
    id="premium_monthly",
    plan=SubscriptionTier.PREMIUM,
    name="Premium",
    price_monthly=150,
    currency="AED",
    description="Full Rico automation and premium recommendations.",
    features=[
        "1500 AI messages per month",
        "Unlimited saved jobs",
        "100 profile optimizations per month",
        "Premium recommendations",
        "Application automation",
    ],
    entitlements=SubscriptionEntitlements(
        monthly_ai_message_limit=1500,
        saved_jobs_limit=None,
        profile_optimization_limit=100,
        premium_recommendations_enabled=True,
        application_automation_enabled=True,
    ),
    is_popular=True,
)

PAID_PLANS = {
    SubscriptionTier.PRO: PRO_PLAN,
    SubscriptionTier.PREMIUM: PREMIUM_PLAN,
}

PRICE_ENV_BY_PLAN = {
    SubscriptionTier.PRO: ("STRIPE_PRO_PRICE_ID", "STRIPE_PRICE_PRO"),
    SubscriptionTier.PREMIUM: ("STRIPE_PREMIUM_PRICE_ID", "STRIPE_PRICE_PREMIUM"),
}


def resolve_effective_user_plan(user_id: str) -> SubscriptionResponse:
    from src.repositories.subscription_repo import get_subscription  # deferred — avoids circular at import time

    now = datetime.now(timezone.utc)
    row = get_subscription(user_id)

    if row is None:
        sub = UserSubscription(
            user_id=user_id,
            plan=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.INACTIVE,
            current_period_start=None,
            current_period_end=now + timedelta(days=30),
            entitlements=FREE_ENTITLEMENTS,
        )
        return SubscriptionResponse(subscription=sub, plan=None, is_active=False)

    try:
        tier = SubscriptionTier(row["plan"])
        plan_recognized = True
    except ValueError:
        tier = SubscriptionTier.FREE
        plan_recognized = False

    try:
        status = SubscriptionStatus(row["status"])
    except ValueError:
        status = SubscriptionStatus.INACTIVE

    is_active = plan_recognized and status == SubscriptionStatus.ACTIVE
    plan_obj = PAID_PLANS.get(tier)
    
    # Check if subscription is expired
    current_period_end = row.get("current_period_end")
    if current_period_end and current_period_end < now:
        is_active = False

    # Entitlements come from plan definitions; DB columns are reserved for future per-user overrides.
    entitlements = plan_obj.entitlements if (plan_obj and is_active) else FREE_ENTITLEMENTS

    sub = UserSubscription(
        user_id=user_id,
        plan=tier,
        subscription_status=status,
        stripe_customer_id=row.get("stripe_customer_id"),
        stripe_subscription_id=row.get("stripe_subscription_id"),
        current_period_start=row.get("current_period_start"),
        current_period_end=current_period_end,
        cancel_at=row.get("cancel_at"),
        canceled_at=row.get("canceled_at"),
        entitlements=entitlements,
    )
    return SubscriptionResponse(subscription=sub, plan=plan_obj, is_active=is_active)


def list_paid_plans() -> PlansResponse:
    return PlansResponse(plans=list(PAID_PLANS.values()))


def get_paid_plan(plan: SubscriptionTier) -> SubscriptionPlan:
    if plan not in PAID_PLANS:
        raise ValueError("Only pro and premium plans can be checked out")
    return PAID_PLANS[plan]


def _load_stripe() -> Any:
    return importlib.import_module("stripe")


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "https://ricohunt.com").strip().rstrip("/") or "https://ricohunt.com"


def _checkout_urls(request: SubscriptionCreateRequest) -> tuple[str, str]:
    frontend = _frontend_url()
    return (
        request.success_url or f"{frontend}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
        request.cancel_url or f"{frontend}/subscription?checkout=cancelled",
    )


def _stripe_price_id(plan: SubscriptionTier) -> str:
    for env_name in PRICE_ENV_BY_PLAN[plan]:
        price_id = os.getenv(env_name, "").strip()
        if price_id:
            return price_id
    return ""


def build_checkout_response(
    user_id: str,
    request: SubscriptionCreateRequest,
) -> CheckoutResponse:
    plan = get_paid_plan(request.plan)
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    stripe_price = _stripe_price_id(plan.plan)

    if not stripe_key or not stripe_price:
        return CheckoutResponse(
            checkout_url=(
                f"https://checkout.ricohunt.com/mock?"
                f"plan={plan.plan.value}"
            ),
            provider="mock",
            plan=plan.plan,
            status="mock",
        )

    stripe = _load_stripe()
    stripe.api_key = stripe_key
    success_url, cancel_url = _checkout_urls(request)
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": stripe_price, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_id,
        metadata={"user_id": user_id, "plan": plan.plan.value},
        subscription_data={"metadata": {"user_id": user_id, "plan": plan.plan.value}},
    )
    checkout_url = getattr(session, "url", None)
    if not checkout_url and isinstance(session, dict):
        checkout_url = session.get("url")
    if not checkout_url:
        raise RuntimeError("Stripe checkout session did not include a URL")

    return CheckoutResponse(
        checkout_url=checkout_url,
        provider="stripe",
        plan=plan.plan,
        status="ready",
    )


def _webhook_response(event: Any, *, mock: bool) -> SubscriptionWebhookResponse:
    event_type = event.get("type") if isinstance(event, dict) else event.type
    return SubscriptionWebhookResponse(
        received=True,
        event_type=event_type,
        processed=(
            event_type.startswith("checkout.")
            or event_type.startswith("customer.subscription.")
            or event_type.startswith("invoice.")
        ),
        mock=mock,
    )


def handle_subscription_webhook(
    event: WebhookEvent,
    *,
    payload: bytes | None = None,
    signature: str | None = None,
) -> SubscriptionWebhookResponse:
    stripe_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not stripe_secret:
        # Mock mode — no signature verification, no DB writes.
        return _webhook_response(event, mock=True)
    if not payload or not signature:
        raise ValueError("Stripe webhook signature is required")

    stripe = _load_stripe()
    verified_event = stripe.Webhook.construct_event(payload, signature, stripe_secret)

    # Process the verified event (idempotent, DB-backed).
    try:
        from src.services.subscription_webhook_service import process_stripe_event
        _ev = verified_event if isinstance(verified_event, dict) else dict(verified_event)
        process_stripe_event(
            event_id=_ev.get("id", ""),
            event_type=_ev.get("type", ""),
            event_data=_ev.get("data", {}),
        )
        # Stripe always gets 200 — failures are tracked in subscription_events and
        # surfaced via internal logs/retries, not by returning 5xx to Stripe.
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("handle_subscription_webhook: processing failed")
        # Do not re-raise: Stripe must receive 200 so it doesn't retry blindly.

    return _webhook_response(verified_event, mock=False)


def check_usage_allowed(user_id: str, feature: str, current_usage: int) -> UsageCheckResponse:
    resolved = resolve_effective_user_plan(user_id)
    limit = getattr(resolved.subscription.entitlements, feature, None)
    if limit is None:
        return UsageCheckResponse(allowed=True, message="No limit configured")
    remaining = max(0, int(limit) - int(current_usage))
    allowed = current_usage < int(limit)
    return UsageCheckResponse(
        allowed=allowed,
        remaining=remaining,
        limit=int(limit),
        message=None if allowed else f"Limit reached for {feature}",
    )


def create_customer_portal_session(user_id: str) -> CheckoutResponse:
    """Create a Stripe Customer Portal session for subscription management."""
    from src.repositories.subscription_repo import get_subscription
    
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not stripe_key:
        return CheckoutResponse(
            checkout_url="",
            provider="mock",
            plan=SubscriptionTier.FREE,
            status="mock",
        )
    
    sub = get_subscription(user_id)
    if not sub or not sub.get("stripe_customer_id"):
        raise ValueError("No active subscription found for user")
    
    stripe = _load_stripe()
    stripe.api_key = stripe_key
    frontend = _frontend_url()
    
    session = stripe.billing_portal.Session.create(
        customer=sub["stripe_customer_id"],
        return_url=f"{frontend}/subscription",
    )
    
    try:
        plan = SubscriptionTier(sub.get("plan", "free"))
    except ValueError:
        plan = SubscriptionTier.FREE

    portal_url = getattr(session, "url", None)
    if not portal_url and isinstance(session, dict):
        portal_url = session.get("url")
    if not portal_url:
        raise RuntimeError("Stripe billing portal session did not include a URL")

    return CheckoutResponse(
        checkout_url=portal_url,
        provider="stripe",
        plan=plan,
        status="ready",
    )

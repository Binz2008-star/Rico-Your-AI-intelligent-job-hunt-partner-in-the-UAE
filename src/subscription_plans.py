"""Rico Hunt subscription plan and entitlement helpers.

Single-plan scope: Rico Monthly is the only paid plan. Entitlements are
resolved from the Paddle-backed paddle_subscriptions table (see
src/repositories/paddle_repo.py) — this is the sole source of truth for
paid status; there is no separate Stripe/manual subscription ledger.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from src.schemas.subscription import (
    PlansResponse,
    SubscriptionEntitlements,
    SubscriptionPlan,
    SubscriptionResponse,
    SubscriptionStatus,
    SubscriptionTier,
    UsageCheckResponse,
    UserSubscription,
)

# 7-day payment-retry grace period (see apps/web/app/refund-policy/RefundPolicyContent.tsx):
# a past_due subscription keeps paid entitlements until this window elapses.
PAST_DUE_GRACE_PERIOD = timedelta(days=7)

# Free-tier AI messages are enforced as a DAILY allowance that resets at 00:00
# UTC, not a monthly cap (see src/services/subscription_gating.py
# check_ai_message_allowed_for_user). The entitlement field is shared with the
# paid plan for schema/API compatibility, so the value here is the per-day cap
# for Free while it stays a per-month cap for Rico Monthly. User-facing copy must
# say "per day / resets every 24 hours" for Free — never "per month".
FREE_ENTITLEMENTS = SubscriptionEntitlements(
    monthly_ai_message_limit=10,
    saved_jobs_limit=10,
    profile_optimization_limit=1,
    cv_storage_limit=1,
    other_document_limit=2,
    premium_recommendations_enabled=False,
    application_automation_enabled=False,
)


def _price_from_env(env_name: str, default: float) -> float:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return default
    try:
        price = float(raw_value)
    except ValueError:
        return default
    return price if price > 0 else default


RICO_MONTHLY_PLAN = SubscriptionPlan(
    id="rico_monthly",
    plan=SubscriptionTier.PRO,
    name="Rico Monthly",
    # Paddle charges USD 21.50/month (Paddle does not support AED billing).
    # AED 79 is the approximate reference shown to UAE users alongside the USD price.
    price_monthly=_price_from_env("RICO_PRO_PRICE_USD", 21.50),
    currency="USD",
    description="Smart AI job hunting for active UAE professionals.",
    # Human-readable marketing bullets. These MUST NOT promise more than the
    # entitlements enforced below (issue #1067): no "unlimited", no premium/
    # automation tier, and numeric claims map to the enforced limits.
    features=[
        "300 AI messages per month",
        "20 CV & profile optimizations per month",
        "Smart AI role recommendations",
        "Advanced match scoring",
        "Saved searches",
        "Priority support",
    ],
    entitlements=SubscriptionEntitlements(
        monthly_ai_message_limit=300,
        saved_jobs_limit=100,
        profile_optimization_limit=20,
        cv_storage_limit=5,
        other_document_limit=10,
        premium_recommendations_enabled=False,
        application_automation_enabled=False,
    ),
    is_popular=True,
)

# Keyed by SubscriptionTier for compatibility with existing lookups
# (PAID_PLANS.get(tier)); SubscriptionTier.PREMIUM is intentionally absent —
# Premium is out of scope until a separate pricing decision approves it.
PAID_PLANS = {
    SubscriptionTier.PRO: RICO_MONTHLY_PLAN,
}


def resolve_effective_user_plan(user_id: str) -> SubscriptionResponse:
    """Resolve a user's effective plan/entitlements from Paddle subscription state.

    Falls back to Free when there's no Paddle record, the DB is unavailable,
    or the plan/status is unrecognized. A past_due subscription keeps paid
    entitlements for PAST_DUE_GRACE_PERIOD from past_due_since before being
    treated as inactive (see paddle_webhook_service._compute_past_due_transition
    for where past_due_since is stamped/cleared).
    """
    now = datetime.now(timezone.utc)

    row = None
    try:
        import sys
        db_module = sys.modules.get("src.db") or __import__("src.db", fromlist=["get_db_connection"])
        from src.repositories.paddle_repo import get_paddle_subscription_by_user
        row = get_paddle_subscription_by_user(db_module, user_id)
    except Exception:
        row = None

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
        tier = SubscriptionTier(row.get("plan", "free"))
        plan_recognized = tier in PAID_PLANS
    except ValueError:
        tier = SubscriptionTier.FREE
        plan_recognized = False

    raw_status = row.get("status", "inactive")
    past_due_since = row.get("past_due_since")
    in_grace_period = (
        raw_status == "past_due"
        and past_due_since is not None
        and (now - past_due_since) <= PAST_DUE_GRACE_PERIOD
    )

    # Map Paddle's richer status vocabulary onto the Rico enum. trialing and
    # a within-grace past_due both read as ACTIVE for entitlement purposes.
    if raw_status in ("active", "trialing") or in_grace_period:
        status = SubscriptionStatus.ACTIVE
    elif raw_status == "past_due":
        status = SubscriptionStatus.PAST_DUE
    elif raw_status == "canceled":
        status = SubscriptionStatus.CANCELED
    else:
        status = SubscriptionStatus.INACTIVE

    is_active = plan_recognized and status == SubscriptionStatus.ACTIVE

    current_period_end = row.get("current_period_end")
    if current_period_end and current_period_end < now and not in_grace_period:
        is_active = False

    plan_obj = PAID_PLANS.get(tier)
    entitlements = plan_obj.entitlements if (plan_obj and is_active) else FREE_ENTITLEMENTS

    sub = UserSubscription(
        user_id=user_id,
        plan=tier if plan_recognized else SubscriptionTier.FREE,
        subscription_status=status,
        paddle_customer_id=row.get("paddle_customer_id"),
        paddle_subscription_id=row.get("paddle_subscription_id"),
        current_period_start=row.get("current_period_start"),
        current_period_end=current_period_end,
        cancel_at=row.get("cancel_at"),
        canceled_at=row.get("canceled_at"),
        entitlements=entitlements,
    )
    return SubscriptionResponse(subscription=sub, plan=plan_obj if is_active else None, is_active=is_active)


def list_paid_plans() -> PlansResponse:
    return PlansResponse(plans=list(PAID_PLANS.values()))


def get_paid_plan(plan: SubscriptionTier) -> SubscriptionPlan:
    if plan not in PAID_PLANS:
        raise ValueError("Only the Rico Monthly plan can be checked out")
    return PAID_PLANS[plan]


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

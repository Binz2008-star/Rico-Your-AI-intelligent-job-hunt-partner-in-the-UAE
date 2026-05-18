"""Default subscription plans and read-only helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.schemas.subscription import (
    SubscriptionPlan,
    SubscriptionResponse,
    SubscriptionStatus,
    SubscriptionTier,
    UsageCheckResponse,
    UserSubscription,
)

FREE_PLAN = SubscriptionPlan(
    id="free",
    tier=SubscriptionTier.FREE,
    name="Free",
    price_monthly=0,
    price_yearly=0,
    features=["basic_job_search"],
    limits={
        "daily_applications": 10,
        "max_memory_entries": 100,
        "max_chat_history": 50,
    },
)

PLANS = {SubscriptionTier.FREE: FREE_PLAN}


def resolve_effective_user_plan(user_id: str) -> SubscriptionResponse:
    now = datetime.now(timezone.utc)
    sub = UserSubscription(
        user_id=user_id,
        plan_tier=SubscriptionTier.FREE,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        usage_limits=FREE_PLAN.limits,
    )
    return SubscriptionResponse(subscription=sub, plan=FREE_PLAN, is_active=True)


def check_usage_allowed(user_id: str, feature: str, current_usage: int) -> UsageCheckResponse:
    resolved = resolve_effective_user_plan(user_id)
    limit = resolved.plan.limits.get(feature)
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

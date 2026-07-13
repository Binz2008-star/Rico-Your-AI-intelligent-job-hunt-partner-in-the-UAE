"""Pydantic schemas for Rico subscription plans and entitlements."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"  # internal key for the single Rico Monthly plan
    PREMIUM = "premium"  # reserved — out of scope until a pricing decision approves it


class SubscriptionStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class SubscriptionEntitlements(BaseModel):
    monthly_ai_message_limit: Optional[int] = None
    saved_jobs_limit: Optional[int] = None
    profile_optimization_limit: Optional[int] = None
    # Document storage quotas — None = unlimited (Premium tier)
    cv_storage_limit: Optional[int] = None
    other_document_limit: Optional[int] = None
    premium_recommendations_enabled: bool = False
    application_automation_enabled: bool = False


class SubscriptionPlan(BaseModel):
    id: str
    plan: SubscriptionTier
    name: str
    price_monthly: int
    currency: str = "AED"
    features: List[str]
    entitlements: SubscriptionEntitlements
    is_popular: bool = False
    description: Optional[str] = None


class UserSubscription(BaseModel):
    user_id: str
    plan: SubscriptionTier
    subscription_status: SubscriptionStatus
    paddle_customer_id: Optional[str] = None
    paddle_subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    entitlements: SubscriptionEntitlements
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionResponse(BaseModel):
    subscription: UserSubscription
    plan: Optional[SubscriptionPlan] = None
    is_active: bool


class PlansResponse(BaseModel):
    plans: List[SubscriptionPlan]


class UsageCheckResponse(BaseModel):
    allowed: bool
    remaining: Optional[int] = None
    limit: Optional[int] = None
    message: Optional[str] = None


class SubscriptionIntentRequest(BaseModel):
    plan: str
    billing_mode: str = "manual"
    source_page: str = "/subscription"


class SubscriptionIntentResponse(BaseModel):
    recorded: bool

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.schemas.chat import RicoSessionContext


def _resolved_free():
    from src.schemas.subscription import (
        SubscriptionEntitlements,
        SubscriptionResponse,
        SubscriptionStatus,
        SubscriptionTier,
        UserSubscription,
    )

    entitlements = SubscriptionEntitlements(
        monthly_ai_message_limit=50,
        saved_jobs_limit=10,
        profile_optimization_limit=1,
    )
    subscription = UserSubscription(
        user_id="limit@rico.ai",
        plan=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.INACTIVE,
        current_period_start=datetime.now(timezone.utc) - timedelta(days=3),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=27),
        entitlements=entitlements,
    )
    return SubscriptionResponse(subscription=subscription, plan=None, is_active=False)


def test_chat_blocks_when_monthly_ai_message_limit_reached():
    from src.services.chat_service import send_message

    ctx = RicoSessionContext.for_authenticated("limit@rico.ai")
    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()), \
         patch("src.services.subscription_gating.count_monthly_ai_messages", return_value=50), \
         patch("src.repositories.profile_repo.get_profile") as get_profile, \
         patch("src.services.chat_service._legacy_send_message") as legacy, \
         patch("src.services.chat_service._conversational_ai_reply") as ai:
        result = send_message(ctx, "help me plan my career")

    get_profile.assert_not_called()
    legacy.assert_not_called()
    ai.assert_not_called()
    assert result["type"] == "subscription_limit"
    assert result["response_source"] == "subscription_gate"
    assert result["feature"] == "monthly_ai_message_limit"
    assert result["usage"] == 50
    assert result["limit"] == 50
    assert result["next_action"] == "upgrade_subscription"


def test_chat_allows_when_monthly_ai_message_usage_remains():
    from src.services.chat_service import send_message

    ctx = RicoSessionContext.for_authenticated("limit@rico.ai")
    legacy_response = {"type": "legacy", "message": "ok", "response_source": "legacy"}
    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()), \
         patch("src.services.subscription_gating.count_monthly_ai_messages", return_value=49), \
         patch("src.repositories.profile_repo.get_profile", return_value=None), \
         patch("src.services.chat_service._legacy_send_message", return_value=legacy_response) as legacy, \
         patch("src.services.chat_service._conversational_ai_reply") as ai:
        result = send_message(ctx, "find me HSE jobs in Dubai")

    legacy.assert_called_once()
    ai.assert_not_called()
    assert result == legacy_response


def test_saved_job_gate_raises_402_when_free_limit_reached():
    from src.services.subscription_gating import enforce_saved_job_allowed

    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()), \
         patch("src.services.subscription_gating.count_saved_jobs", return_value=10):
        with pytest.raises(HTTPException) as exc:
            enforce_saved_job_allowed("limit@rico.ai")

    assert exc.value.status_code == 402
    assert exc.value.detail["type"] == "subscription_limit"
    assert exc.value.detail["feature"] == "saved_jobs_limit"


def test_profile_optimization_gate_raises_402_when_free_limit_reached():
    from src.services.subscription_gating import enforce_profile_optimization_allowed

    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()), \
         patch("src.services.subscription_gating.count_profile_optimizations", return_value=1):
        with pytest.raises(HTTPException) as exc:
            enforce_profile_optimization_allowed("limit@rico.ai")

    assert exc.value.status_code == 402
    assert exc.value.detail["type"] == "subscription_limit"
    assert exc.value.detail["feature"] == "profile_optimization_limit"

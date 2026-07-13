from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi")
HTTPException = fastapi.HTTPException

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


# ── Identity-key invariant ──────────────────────────────────────────────────────
#
# Subscriptions are stored keyed by the account email (admin activation writes
# ``upsert_subscription(user_id=email, ...)``) and ``resolve_effective_user_plan``
# looks the row up by that same key with no transformation. Every gating call site
# therefore MUST pass the account email — the same identity ``deps`` derives from the
# JWT (``request.state.user_id = user["email"]``). Passing any other identity (e.g. a
# UUID) silently returns FREE and would treat a paying user as unpaid. These tests
# lock that contract so a future identity/storage-key change fails loudly here.

_PAID_EMAIL = "paid@rico.ai"


def _active_pro_row(user_id: str = _PAID_EMAIL) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "plan": "pro",
        "status": "active",
        "paddle_customer_id": None,
        "paddle_subscription_id": None,
        "current_period_start": now - timedelta(days=1),
        "current_period_end": now + timedelta(days=29),
        "cancel_at": None,
        "canceled_at": None,
    }


def test_resolve_uses_the_email_key_verbatim_and_pays_out_pro():
    """A subscription stored under the email resolves to PRO when queried by that email."""
    from src.subscription_plans import resolve_effective_user_plan

    def fake_get_subscription(key):
        return _active_pro_row() if key == _PAID_EMAIL else None

    with patch("src.repositories.subscription_repo.get_subscription", side_effect=fake_get_subscription) as gs:
        resolved = resolve_effective_user_plan(_PAID_EMAIL)

    gs.assert_called_once_with(_PAID_EMAIL)  # queried by the exact key, untransformed
    assert resolved.is_active is True
    assert resolved.subscription.plan.value == "pro"
    assert resolved.subscription.entitlements.monthly_ai_message_limit == 300


def test_resolve_falls_back_to_free_for_a_non_email_identity():
    """Guard the fragility: a non-matching identity (UUID) silently degrades to FREE.

    This is the exact failure a mis-keyed gating call would produce, so the test
    documents and pins the contract that gating must key on the account email.
    """
    from src.subscription_plans import resolve_effective_user_plan

    uuid_identity = "0cb0b1d1-0037-408e-823f-c7eccb337582"

    def fake_get_subscription(key):
        return _active_pro_row() if key == _PAID_EMAIL else None

    with patch("src.repositories.subscription_repo.get_subscription", side_effect=fake_get_subscription):
        resolved = resolve_effective_user_plan(uuid_identity)

    assert resolved.is_active is False
    assert resolved.subscription.plan.value == "free"
    assert resolved.subscription.entitlements.monthly_ai_message_limit == 50


def test_gating_passes_identity_through_to_plan_resolution_unchanged():
    """The document-quota gate must forward its identity to the resolver verbatim."""
    from src.services.subscription_gating import enforce_document_quota

    seen: dict[str, str] = {}

    def spy_resolve(user_id):
        seen["user_id"] = user_id
        return _resolved_free()

    with patch("src.services.subscription_gating.resolve_effective_user_plan", side_effect=spy_resolve), \
         patch("src.services.subscription_gating.count_user_documents", return_value=0):
        enforce_document_quota(_PAID_EMAIL, "cv")

    assert seen["user_id"] == _PAID_EMAIL

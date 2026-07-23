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
        monthly_ai_message_limit=10,  # Free tier: enforced as a DAILY allowance
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
         patch("src.services.subscription_gating.count_monthly_ai_messages", return_value=10), \
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
    assert result["usage"] == 10
    assert result["limit"] == 10
    assert result["next_action"] == "upgrade_subscription"
    # Free tier is a daily allowance: the block message must be day-framed and
    # carry a reset time, never "monthly" copy.
    assert result["reset_at"] is not None
    assert "month" not in result["message"].lower()
    assert "today" in result["message"].lower()


def test_chat_allows_when_monthly_ai_message_usage_remains():
    from src.services.chat_service import send_message

    ctx = RicoSessionContext.for_authenticated("limit@rico.ai")
    legacy_response = {"type": "legacy", "message": "ok", "response_source": "legacy"}
    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()), \
         patch("src.services.subscription_gating.count_monthly_ai_messages", return_value=9), \
         patch("src.repositories.profile_repo.get_profile", return_value=None), \
         patch("src.services.chat_service._legacy_send_message", return_value=legacy_response) as legacy, \
         patch("src.services.chat_service._conversational_ai_reply") as ai:
        result = send_message(ctx, "find me HSE jobs in Dubai")

    legacy.assert_called_once()
    ai.assert_not_called()
    assert result == legacy_response


def test_limit_message_has_no_doubled_limit_word():
    """Live-QA 2026-07-19: the free-tier block read 'ai message limit limit'.

    The feature key already ends in '_limit', and the message template appends
    its own ' limit', so the label must have its trailing 'limit' stripped.
    """
    from src.services.subscription_gating import _build_gate_check

    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()):
        gate = _build_gate_check("limit@rico.ai", "monthly_ai_message_limit", usage=50)

    assert gate.allowed is False
    assert "limit limit" not in gate.message
    assert gate.message == (
        "You have reached your monthly ai message limit on the Free plan "
        "(50/50). Upgrade to continue."
    )


def test_limit_message_keeps_single_limit_for_non_limit_suffixed_feature():
    """A feature key that does not end in 'limit' still reads correctly."""
    from src.services.subscription_gating import _build_gate_check

    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()):
        gate = _build_gate_check("limit@rico.ai", "saved_jobs_limit", usage=10)

    assert gate.allowed is False
    assert "limit limit" not in gate.message
    assert "saved jobs limit" in gate.message


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
        "past_due_since": None,
        "cancel_at": None,
        "canceled_at": None,
    }


def test_resolve_uses_the_email_key_verbatim_and_pays_out_pro():
    """A subscription stored under the email resolves to PRO when queried by that email."""
    from src.subscription_plans import resolve_effective_user_plan

    def fake_get_subscription(db_module, key):
        return _active_pro_row() if key == _PAID_EMAIL else None

    with patch("src.repositories.paddle_repo.get_paddle_subscription_by_user", side_effect=fake_get_subscription) as gs:
        resolved = resolve_effective_user_plan(_PAID_EMAIL)

    gs.assert_called_once()
    assert gs.call_args.args[1] == _PAID_EMAIL  # queried by the exact key, untransformed
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

    def fake_get_subscription(db_module, key):
        return _active_pro_row() if key == _PAID_EMAIL else None

    with patch("src.repositories.paddle_repo.get_paddle_subscription_by_user", side_effect=fake_get_subscription):
        resolved = resolve_effective_user_plan(uuid_identity)

    assert resolved.is_active is False
    assert resolved.subscription.plan.value == "free"
    assert resolved.subscription.entitlements.monthly_ai_message_limit == 10


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


# ── Free daily AI-message allowance (resets 00:00 UTC, not a monthly cap) ────────


def test_free_ai_allowance_uses_daily_window_and_carries_reset_time():
    """Free users are counted over the current UTC day; reset_at is next 00:00 UTC."""
    from src.services.subscription_gating import check_ai_message_allowed_for_user

    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()), \
         patch("src.services.subscription_gating.count_monthly_ai_messages", return_value=3) as counted:
        gate = check_ai_message_allowed_for_user("free@rico.ai")

    # The window handed to the counter is start-of-day UTC — a daily allowance,
    # not the calendar-month / billing-cycle window used for paid plans.
    window_start = counted.call_args.args[1]
    assert (window_start.hour, window_start.minute, window_start.second) == (0, 0, 0)
    assert window_start.tzinfo is not None

    assert gate.allowed is True
    assert gate.limit == 10
    assert gate.remaining == 7
    assert gate.reset_at == window_start + timedelta(days=1)
    assert "month" not in gate.message.lower()


def test_free_ai_allowance_blocks_at_cap_with_resets_in_countdown():
    """At the daily cap the block message is day-framed with a reset countdown."""
    from src.services.subscription_gating import check_ai_message_allowed_for_user

    with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=_resolved_free()), \
         patch("src.services.subscription_gating.count_monthly_ai_messages", return_value=10):
        gate = check_ai_message_allowed_for_user("free@rico.ai")

    assert gate.allowed is False
    assert gate.reset_at is not None
    low = gate.message.lower()
    assert "resets in" in low
    assert "month" not in low

    resp = gate.to_response()
    assert resp["type"] == "subscription_limit"
    assert resp["reset_at"] == gate.reset_at.isoformat()

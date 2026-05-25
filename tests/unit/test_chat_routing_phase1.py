"""tests/unit/test_chat_routing_phase1.py

Policy Gateway pre-filter routing tests for chat_service.send_message().

Covers the five routing assertions required for PR A:
  1. Gmail/LinkedIn/Calendar/WhatsApp — never reach AI or legacy pipeline
  2. Subscription question (authenticated) — returns subscription status
  3. Subscription question (unauthenticated) — returns login-required
  4. Normal job search — falls through to existing pipeline
  5. Career planning — falls through to existing pipeline
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.chat import RicoSessionContext

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_AUTH_CTX = RicoSessionContext.for_authenticated("test@rico.ai")
_PUBLIC_CTX = RicoSessionContext.for_public("test-session-abc")
_LEGACY_RESP = {"type": "response", "message": "Legacy pipeline", "response_source": "legacy"}
_AI_RESP = {"type": "openai_response", "message": "AI reply", "response_source": "openai",
            "intent": "conversational"}


def _free_sub():
    from src.schemas.subscription import (
        SubscriptionEntitlements, SubscriptionResponse, SubscriptionStatus,
        SubscriptionTier, UserSubscription,
    )
    ents = SubscriptionEntitlements(
        monthly_ai_message_limit=50, saved_jobs_limit=10,
        profile_optimization_limit=1,
    )
    sub = UserSubscription(
        user_id="test@rico.ai", plan=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.INACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        entitlements=ents,
    )
    return SubscriptionResponse(subscription=sub, plan=None, is_active=False)


def _premium_sub():
    from src.schemas.subscription import (
        SubscriptionResponse, SubscriptionStatus, SubscriptionTier, UserSubscription,
    )
    from src.subscription_plans import PREMIUM_PLAN
    sub = UserSubscription(
        user_id="test@rico.ai", plan=SubscriptionTier.PREMIUM,
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        entitlements=PREMIUM_PLAN.entitlements,
    )
    return SubscriptionResponse(subscription=sub, plan=PREMIUM_PLAN, is_active=True)


# ---------------------------------------------------------------------------
# 1. Unsupported external tool — must not reach AI or legacy pipeline
# ---------------------------------------------------------------------------

class TestUnsupportedToolsNeverReachPipeline:

    @staticmethod
    def _send(message: str):
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP) as ml, \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP) as ma:
            result = send_message(_AUTH_CTX, message)
            return result, ml, ma

    def test_gmail_request_bypasses_pipeline(self):
        result, ml, ma = self._send("fetch jobs I applied for from Gmail")
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["intent"] == "unsupported"

    def test_gmail_response_contains_alternative(self):
        result, _, _ = self._send("access my Gmail")
        msg = result["message"].lower()
        assert any(w in msg for w in ["upload", "paste", "can't", "cannot", "لا أستطيع"])

        assert result["tool_available"] is False
        assert result["next_action"] == "paste_email_or_add_application"
        assert any(option["action"] == "manual_add_application" for option in result["options"])

    def test_linkedin_bypasses_pipeline(self):
        result, ml, ma = self._send("check my LinkedIn profile")
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["next_action"] == "paste_linkedin_context"
        assert any(option["action"] == "paste_linkedin_profile" for option in result["options"])

    def test_calendar_bypasses_pipeline(self):
        result, ml, ma = self._send("schedule a meeting in my calendar")
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["next_action"] == "provide_schedule_details"
        assert any(option["action"] == "record_interview_time" for option in result["options"])

    def test_whatsapp_bypasses_pipeline(self):
        result, ml, ma = self._send("send me a WhatsApp message")
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["next_action"] == "paste_message_or_use_telegram"
        assert any(option["action"] == "telegram_settings" for option in result["options"])

    def test_mixed_unsupported_tool_and_job_search_gets_choice(self):
        result, ml, ma = self._send("fetch my Gmail and find me HSE jobs")
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["type"] == "clarification"
        assert result["intent"] == "mixed_request"
        assert result["next_action"] == "choose_supported_path"
        assert any(option["action"] == "continue_without_external_tool" for option in result["options"])

    def test_gmail_arabic_bypasses_pipeline(self):
        result, ml, ma = self._send("افحص إيميلي")
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"

    def test_linkedin_arabic_bypasses_pipeline(self):
        result, ml, ma = self._send("افحص لينكد إن")
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"


# ---------------------------------------------------------------------------
# 2. Subscription question — authenticated → subscription status
# ---------------------------------------------------------------------------

class TestSubscriptionAuthenticated:

    @staticmethod
    def _send(message: str, resolved):
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP) as ml, \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP) as ma, \
             patch("src.subscription_plans.resolve_effective_user_plan", return_value=resolved):
            result = send_message(_AUTH_CTX, message)
            return result, ml, ma

    def test_what_is_my_plan_returns_status(self):
        result, ml, ma = self._send("what is my plan?", _free_sub())
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["intent"] == "account_service"
        assert "message" in result

    def test_free_user_sees_free_plan(self):
        result, _, _ = self._send("what plan am I on?", _free_sub())
        assert "Free" in result["message"]
        assert result["plan"] == "free"
        assert result["is_active"] is False

    def test_premium_user_sees_premium_plan(self):
        result, _, _ = self._send("my subscription status", _premium_sub())
        assert "Premium" in result["message"]
        assert result["plan"] == "premium"
        assert result["is_active"] is True

    def test_arabic_subscription_routes_to_service(self):
        result, ml, ma = self._send("شو اشتراكي؟", _free_sub())
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["intent"] == "account_service"

    def test_message_limit_question_routes_to_service(self):
        result, ml, ma = self._send("what is my message limit?", _free_sub())
        ma.assert_not_called()
        ml.assert_not_called()
        assert result["response_source"] == "policy_gateway"

    def test_response_contains_message_limit(self):
        result, _, _ = self._send("what is my plan?", _free_sub())
        assert "50" in result["message"]  # FREE_ENTITLEMENTS.monthly_ai_message_limit = 50


# ---------------------------------------------------------------------------
# 3. Subscription question — unauthenticated → login-required
# ---------------------------------------------------------------------------

class TestSubscriptionUnauthenticated:

    def test_public_subscription_question_returns_login_required(self):
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP) as ml, \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP) as ma:
            result = send_message(_PUBLIC_CTX, "what is my plan?")

        ml.assert_not_called()
        ma.assert_not_called()
        assert result["response_source"] == "policy_gateway"
        assert result["type"] == "login_required"
        assert "log in" in result["message"].lower() or "sign in" in result["message"].lower()

    def test_public_billing_question_falls_through(self):
        """Billing queries are not intercepted — they fall through to AI/legacy."""
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP), \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP):
            result = send_message(_PUBLIC_CTX, "billing")

        assert result.get("response_source") != "policy_gateway"


# ---------------------------------------------------------------------------
# 4. Normal job search — falls through to existing pipeline
# ---------------------------------------------------------------------------

class TestJobSearchPassthrough:

    def test_job_search_not_intercepted_by_gateway(self):
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP) as ml, \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP):
            result = send_message(_AUTH_CTX, "find me HSE jobs in Dubai")

        assert result.get("response_source") != "policy_gateway"

    def test_find_jobs_not_intercepted(self):
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP), \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP):
            result = send_message(_AUTH_CTX, "find me a job")

        assert result.get("response_source") != "policy_gateway"


# ---------------------------------------------------------------------------
# 5. Career planning — falls through to existing pipeline
# ---------------------------------------------------------------------------

class TestCareerPlanningPassthrough:

    def test_career_plan_not_intercepted(self):
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP), \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP) as ma:
            result = send_message(_AUTH_CTX, "help me build a job search strategy")

        assert result.get("response_source") != "policy_gateway"

    def test_career_advice_not_intercepted(self):
        from src.services.chat_service import send_message
        with patch("src.repositories.profile_repo.get_profile", return_value=None), \
             patch("src.services.chat_service._legacy_send_message", return_value=_LEGACY_RESP), \
             patch("src.services.chat_service._conversational_ai_reply", return_value=_AI_RESP):
            result = send_message(_AUTH_CTX, "what roles fit me?")

        assert result.get("response_source") != "policy_gateway"

"""Rico Brain Phase 2 routing eval suite.

This file intentionally freezes current policy gateway and chat routing
behavior before Phase 2 adds new behavior. It should only change when the
baseline is deliberately updated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.rico.policy import RicoDomain, classify_request
from src.schemas.chat import RicoSessionContext


@dataclass(frozen=True)
class PolicyEvalCase:
    case_id: str
    category: str
    language: str
    message: str
    domain: RicoDomain
    route: str


POLICY_EVAL_CASES: tuple[PolicyEvalCase, ...] = (
    # Subscription / account - English
    PolicyEvalCase("account_en_001", "subscription/account", "en", "what is my plan?", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_002", "subscription/account", "en", "what plan am I on", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_003", "subscription/account", "en", "my subscription status", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_004", "subscription/account", "en", "show my current subscription", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_005", "subscription/account", "en", "what is my active plan", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_006", "subscription/account", "en", "how many messages remaining", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_007", "subscription/account", "en", "how many jobs left", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_008", "subscription/account", "en", "upgrade plan", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_009", "subscription/account", "en", "cancel subscription", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_en_010", "subscription/account", "broken_en", "what my plan", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),

    # Subscription / account - Arabic and mixed
    PolicyEvalCase("account_ar_001", "subscription/account", "ar", "شو اشتراكي؟", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_ar_002", "subscription/account", "ar", "ما هو اشتراكي", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_ar_003", "subscription/account", "ar", "أنا على أي باقة؟", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_ar_004", "subscription/account", "ar", "حالة اشتراكي", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_ar_005", "subscription/account", "ar", "كم رسالة باقي", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_ar_006", "subscription/account", "ar", "ترقية الباقة", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("account_arabizi_001", "subscription/account", "arabizi", "shu ishtiraki?", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("account_mixed_001", "subscription/account", "mixed", "شو خطتي what plan", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),

    # Billing / payment
    PolicyEvalCase("billing_en_001", "billing/payment", "en", "billing", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_en_002", "billing/payment", "en", "my payment history", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_en_003", "billing/payment", "en", "where is my invoice?", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_en_004", "billing/payment", "en", "I want a refund", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_en_005", "billing/payment", "en", "credit card update", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_en_006", "billing/payment", "en", "how much do I pay", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_ar_001", "billing/payment", "ar", "أين فاتورتي؟", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_ar_002", "billing/payment", "ar", "الدفع", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_ar_003", "billing/payment", "ar", "كم السعر", RicoDomain.BILLING_PAYMENT, "ai"),
    PolicyEvalCase("billing_arabizi_001", "billing/payment", "arabizi", "wein invoice taba3i", RicoDomain.BILLING_PAYMENT, "ai"),

    # Job search
    PolicyEvalCase("job_en_001", "job search", "en", "find me HSE jobs in UAE", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_002", "job search", "en", "find me a job", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_003", "job search", "en", "search jobs", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_004", "job search", "en", "job opportunities", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_005", "job search", "en", "manager jobs", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_006", "job search", "en", "engineer job", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_007", "job search", "en", "analyst jobs", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_008", "job search", "en", "developer jobs", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_009", "job search", "en", "jobs in Dubai", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_010", "job search", "en", "jobs in Abu Dhabi", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_011", "job search", "en", "I'm looking for a manager role", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_012", "job search", "broken_en", "looking for work UAE", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_013", "job search", "broken_en", "any jobs", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_en_014", "job search", "en", "vacancies", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_ar_001", "job search", "ar", "ابحث لي عن وظيفة", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_ar_002", "job search", "ar", "وظائف", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_ar_003", "job search", "ar", "وظائف في الإمارات", RicoDomain.JOB_SEARCH, "job_search"),
    PolicyEvalCase("job_arabizi_001", "job search", "arabizi", "ab7ath 3an job fi dubai", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("job_mixed_001", "job search", "mixed", "find me وظائف in Dubai", RicoDomain.JOB_SEARCH, "job_search"),

    # Career planning
    PolicyEvalCase("career_en_001", "career planning", "en", "make me a job search plan", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_en_002", "career planning", "en", "what's my career strategy?", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_en_003", "career planning", "en", "career advice", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_en_004", "career planning", "en", "career roadmap", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_en_005", "career planning", "en", "job search strategy", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_en_006", "career planning", "en", "what roles fit me?", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_en_007", "career planning", "en", "what jobs should suit me", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("career_en_008", "career planning", "en", "help me plan my career", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_en_009", "career planning", "en", "build a strategy", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_ar_001", "career planning", "ar", "خطة مهنية", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_ar_002", "career planning", "ar", "استراتيجية", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_ar_003", "career planning", "ar", "نصيحة مهنية", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_arabizi_001", "career planning", "arabizi", "baddi career plan", RicoDomain.CAREER_STRATEGY, "ai"),
    PolicyEvalCase("career_mixed_001", "career planning", "mixed", "help me خطة مهنية", RicoDomain.CAREER_STRATEGY, "ai"),

    # CV / profile
    PolicyEvalCase("cv_en_001", "cv/profile", "en", "upload my CV", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_en_002", "cv/profile", "en", "update my resume", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_en_003", "cv/profile", "en", "show my profile", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_en_004", "cv/profile", "en", "what are my skills?", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_en_005", "cv/profile", "en", "my experience", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_en_006", "cv/profile", "en", "my background", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_en_007", "cv/profile", "en", "resume parse", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_ar_001", "cv/profile", "ar", "أرفع السيرة الذاتية", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_ar_002", "cv/profile", "ar", "ملفي", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_ar_003", "cv/profile", "ar", "خبراتي", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_ar_004", "cv/profile", "ar", "مهاراتي", RicoDomain.CV_PROFILE, "ai"),
    PolicyEvalCase("cv_arabizi_001", "cv/profile", "arabizi", "upload my seera", RicoDomain.FILE_UPLOAD, "deterministic"),
    PolicyEvalCase("cv_mixed_001", "cv/profile", "mixed", "update my CV و مهاراتي", RicoDomain.CV_PROFILE, "ai"),

    # Application tracking
    PolicyEvalCase("apps_en_001", "application tracking", "en", "track my applications", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_002", "application tracking", "en", "view applications", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_003", "application tracking", "en", "see my applications", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_004", "application tracking", "en", "what did I apply for?", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_005", "application tracking", "en", "my application status", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_006", "application tracking", "en", "my pipeline status", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_007", "application tracking", "en", "application tracking", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_008", "application tracking", "en", "status of my applications", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_en_009", "application tracking", "en", "where are my applications?", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_ar_001", "application tracking", "ar", "تتبع طلباتي", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_ar_002", "application tracking", "ar", "طلباتي", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_ar_003", "application tracking", "ar", "حالة التقديم", RicoDomain.APPLICATIONS_TRACKING, "application_tracking"),
    PolicyEvalCase("apps_arabizi_001", "application tracking", "arabizi", "wein applications taba3i", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),

    # Gmail / email unsupported access
    PolicyEvalCase("gmail_en_001", "gmail/email unsupported", "en", "fetch jobs I applied for from Gmail", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_en_002", "gmail/email unsupported", "en", "check my email inbox for applications", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_en_003", "gmail/email unsupported", "en", "access my Gmail", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_en_004", "gmail/email unsupported", "en", "scan inbox for recruiter emails", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_en_005", "gmail/email unsupported", "en", "import from email", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_en_006", "gmail/email unsupported", "en", "read my emails", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_ar_001", "gmail/email unsupported", "ar", "افحص إيميلي", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_ar_002", "gmail/email unsupported", "ar", "تفقد بريدي", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
    PolicyEvalCase("gmail_arabizi_001", "gmail/email unsupported", "arabizi", "check my email ya Rico", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),

    # LinkedIn unsupported access
    PolicyEvalCase("linkedin_en_001", "linkedin unsupported", "en", "check my LinkedIn profile", RicoDomain.LINKEDIN_REQUEST, "unsupported"),
    PolicyEvalCase("linkedin_en_002", "linkedin unsupported", "en", "read my LinkedIn messages", RicoDomain.LINKEDIN_REQUEST, "unsupported"),
    PolicyEvalCase("linkedin_en_003", "linkedin unsupported", "en", "import from LinkedIn", RicoDomain.LINKEDIN_REQUEST, "unsupported"),
    PolicyEvalCase("linkedin_en_004", "linkedin unsupported", "en", "scan LinkedIn", RicoDomain.LINKEDIN_REQUEST, "unsupported"),
    PolicyEvalCase("linkedin_en_005", "linkedin unsupported", "en", "my linkedin account", RicoDomain.LINKEDIN_REQUEST, "unsupported"),
    PolicyEvalCase("linkedin_ar_001", "linkedin unsupported", "ar", "افحص لينكد إن", RicoDomain.LINKEDIN_REQUEST, "unsupported"),
    PolicyEvalCase("linkedin_ar_002", "linkedin unsupported", "ar", "رسائل لينكد إن", RicoDomain.LINKEDIN_REQUEST, "unsupported"),
    PolicyEvalCase("linkedin_arabizi_001", "linkedin unsupported", "arabizi", "check linkedin taba3i", RicoDomain.LINKEDIN_REQUEST, "unsupported"),

    # Calendar unsupported access
    PolicyEvalCase("calendar_en_001", "calendar unsupported", "en", "schedule a meeting in my calendar", RicoDomain.CALENDAR_REQUEST, "unsupported"),
    PolicyEvalCase("calendar_en_002", "calendar unsupported", "en", "check my availability", RicoDomain.CALENDAR_REQUEST, "unsupported"),
    PolicyEvalCase("calendar_en_003", "calendar unsupported", "en", "book a slot", RicoDomain.CALENDAR_REQUEST, "unsupported"),
    PolicyEvalCase("calendar_en_004", "calendar unsupported", "en", "google calendar", RicoDomain.CALENDAR_REQUEST, "unsupported"),
    PolicyEvalCase("calendar_en_005", "calendar unsupported", "en", "outlook calendar", RicoDomain.CALENDAR_REQUEST, "unsupported"),
    PolicyEvalCase("calendar_en_006", "calendar unsupported", "en", "when am I free", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("calendar_ar_001", "calendar unsupported", "ar", "التقويم", RicoDomain.CALENDAR_REQUEST, "unsupported"),
    PolicyEvalCase("calendar_ar_002", "calendar unsupported", "ar", "جدولة اجتماع", RicoDomain.CALENDAR_REQUEST, "unsupported"),
    PolicyEvalCase("calendar_arabizi_001", "calendar unsupported", "arabizi", "book meeting bukra", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),

    # Telegram / settings
    PolicyEvalCase("telegram_en_001", "telegram/settings", "en", "enable telegram notifications", RicoDomain.TELEGRAM_REQUEST, "ai"),
    PolicyEvalCase("telegram_en_002", "telegram/settings", "en", "setup telegram", RicoDomain.TELEGRAM_REQUEST, "ai"),
    PolicyEvalCase("telegram_en_003", "telegram/settings", "en", "telegram alerts", RicoDomain.TELEGRAM_REQUEST, "ai"),
    PolicyEvalCase("telegram_en_004", "telegram/settings", "en", "tg bot", RicoDomain.TELEGRAM_REQUEST, "ai"),
    PolicyEvalCase("settings_en_001", "telegram/settings", "en", "my settings", RicoDomain.SETTINGS_AUTOMATION, "ai"),
    PolicyEvalCase("settings_en_002", "telegram/settings", "en", "notification settings", RicoDomain.SETTINGS_AUTOMATION, "ai"),
    PolicyEvalCase("settings_en_003", "telegram/settings", "en", "configure preferences", RicoDomain.SETTINGS_AUTOMATION, "ai"),
    PolicyEvalCase("settings_ar_001", "telegram/settings", "ar", "إعدادات", RicoDomain.SETTINGS_AUTOMATION, "ai"),
    PolicyEvalCase("settings_ar_002", "telegram/settings", "ar", "تفضيلات", RicoDomain.SETTINGS_AUTOMATION, "ai"),
    PolicyEvalCase("telegram_arabizi_001", "telegram/settings", "arabizi", "f3el telegram", RicoDomain.TELEGRAM_REQUEST, "ai"),

    # Unclear / mixed
    PolicyEvalCase("mixed_001", "unclear/mixed", "en", "xyz123 nonsense input here", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_002", "unclear/mixed", "en", "...", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_003", "unclear/mixed", "en", "hi", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_004", "unclear/mixed", "en", "HSE Manager", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_005", "unclear/mixed", "en", "fetch my Gmail and find me HSE jobs", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_006", "unclear/mixed", "en", "what is my plan and find me jobs", RicoDomain.ACCOUNT_SUBSCRIPTION, "account_service"),
    PolicyEvalCase("mixed_007", "unclear/mixed", "en", "calendar and LinkedIn please", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_008", "unclear/mixed", "broken_en", "job me maybe plan also", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_009", "unclear/mixed", "arabizi", "shu job plan cv?", RicoDomain.UNKNOWN_OR_MIXED, "clarification"),
    PolicyEvalCase("mixed_010", "unclear/mixed", "mixed", "شو jobs and Gmail", RicoDomain.EMAIL_GMAIL_REQUEST, "unsupported"),
)

EXPECTED_POLICY_EVAL_CASE_COUNT = 133
_MIXED_CLASSIFIER_LANGUAGE_BASELINE = {
    "account_mixed_001": "ar",
    "job_mixed_001": "en",
    "career_mixed_001": "ar",
    "cv_mixed_001": "ar",
    "mixed_010": "en",
}


def _expected_classifier_language(case: PolicyEvalCase) -> str:
    if case.case_id in _MIXED_CLASSIFIER_LANGUAGE_BASELINE:
        return _MIXED_CLASSIFIER_LANGUAGE_BASELINE[case.case_id]
    return "ar" if case.language == "ar" else "en"


@pytest.mark.parametrize("case", POLICY_EVAL_CASES, ids=lambda case: case.case_id)
def test_phase2_policy_gateway_eval_baseline(case: PolicyEvalCase) -> None:
    decision = classify_request(case.message)

    assert decision.domain == case.domain
    assert decision.route == case.route
    assert decision.language == _expected_classifier_language(case)


def test_phase2_policy_eval_matrix_size_and_coverage() -> None:
    assert len(POLICY_EVAL_CASES) == EXPECTED_POLICY_EVAL_CASE_COUNT

    categories = {case.category for case in POLICY_EVAL_CASES}
    languages = {case.language for case in POLICY_EVAL_CASES}

    assert {
        "subscription/account",
        "billing/payment",
        "job search",
        "career planning",
        "cv/profile",
        "application tracking",
        "gmail/email unsupported",
        "linkedin unsupported",
        "calendar unsupported",
        "telegram/settings",
        "unclear/mixed",
    }.issubset(categories)
    assert {"en", "ar", "arabizi", "mixed", "broken_en"}.issubset(languages)


@dataclass(frozen=True)
class ChatRoutingEvalCase:
    case_id: str
    category: str
    message: str
    auth: str
    expected_source: str
    expected_type: str | None = None
    expected_passthrough_source: str | None = None


CHAT_ROUTING_EVAL_CASES: tuple[ChatRoutingEvalCase, ...] = (
    ChatRoutingEvalCase("chat_account_auth_001", "subscription/account", "what is my plan?", "authenticated", "policy_gateway", "subscription_status"),
    ChatRoutingEvalCase("chat_account_auth_002", "subscription/account", "my subscription status", "authenticated", "policy_gateway", "subscription_status"),
    ChatRoutingEvalCase("chat_account_public_001", "subscription/account", "what is my plan?", "public", "policy_gateway", "login_required"),
    ChatRoutingEvalCase("chat_gmail_001", "gmail/email unsupported", "access my Gmail", "authenticated", "policy_gateway", "unsupported_tool"),
    ChatRoutingEvalCase("chat_gmail_002", "gmail/email unsupported", "check my email inbox", "authenticated", "policy_gateway", "unsupported_tool"),
    ChatRoutingEvalCase("chat_linkedin_001", "linkedin unsupported", "read my LinkedIn messages", "authenticated", "policy_gateway", "unsupported_tool"),
    ChatRoutingEvalCase("chat_calendar_001", "calendar unsupported", "check my availability", "authenticated", "policy_gateway", "unsupported_tool"),
    ChatRoutingEvalCase("chat_whatsapp_001", "whatsapp unsupported", "send me a WhatsApp message", "authenticated", "policy_gateway", "unsupported_tool"),
    ChatRoutingEvalCase("chat_billing_001", "billing/payment", "where is my invoice?", "authenticated", "passthrough", expected_passthrough_source="openai"),
    ChatRoutingEvalCase("chat_job_001", "job search", "find me HSE jobs in Dubai", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_job_002", "job search", "I'm looking for a manager role", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_career_001", "career planning", "make me a job search plan", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_cv_001", "cv/profile", "upload my CV", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_apps_001", "application tracking", "track my applications", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_telegram_001", "telegram/settings", "enable telegram notifications", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_settings_001", "telegram/settings", "my settings", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_unclear_001", "unclear/mixed", "hi", "authenticated", "passthrough", expected_passthrough_source="legacy"),
    ChatRoutingEvalCase("chat_unclear_002", "unclear/mixed", "HSE Manager", "authenticated", "passthrough", expected_passthrough_source="legacy"),
)


def _free_subscription_response():
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
        user_id="phase2-eval@rico.ai",
        plan=SubscriptionTier.FREE,
        subscription_status=SubscriptionStatus.INACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        entitlements=entitlements,
    )
    return SubscriptionResponse(subscription=subscription, plan=None, is_active=False)


def _ctx(auth: str) -> RicoSessionContext:
    if auth == "public":
        return RicoSessionContext.for_public("phase2-eval-session")
    return RicoSessionContext.for_authenticated("phase2-eval@rico.ai")


@pytest.mark.parametrize("case", CHAT_ROUTING_EVAL_CASES, ids=lambda case: case.case_id)
def test_phase2_chat_routing_eval_baseline(case: ChatRoutingEvalCase) -> None:
    from src.services.chat_service import send_message

    legacy_response = {"type": "legacy_eval", "message": "legacy", "response_source": "legacy"}
    ai_response = {"type": "ai_eval", "message": "ai", "response_source": "openai"}

    with patch("src.repositories.profile_repo.get_profile", return_value=None), \
         patch("src.subscription_plans.resolve_effective_user_plan", return_value=_free_subscription_response()), \
         patch("src.services.chat_service._legacy_send_message", return_value=legacy_response), \
         patch("src.services.chat_service._conversational_ai_reply", return_value=ai_response):
        result = send_message(_ctx(case.auth), case.message)

    if case.expected_source == "policy_gateway":
        assert result.get("response_source") == "policy_gateway"
        assert result.get("type") == case.expected_type
    else:
        assert result.get("response_source") == case.expected_passthrough_source


def test_phase2_chat_eval_matrix_size_and_coverage() -> None:
    assert len(CHAT_ROUTING_EVAL_CASES) >= 15
    assert {case.expected_source for case in CHAT_ROUTING_EVAL_CASES} == {"policy_gateway", "passthrough"}

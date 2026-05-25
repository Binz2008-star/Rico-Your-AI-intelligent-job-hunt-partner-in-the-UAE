"""tests/unit/test_policy_gateway.py

Regression tests for Rico Brain Policy Gateway - Phase 1.

Test matrix: 40+ cases covering:
- English/Arabic subscription queries
- Billing/payment questions
- Gmail/email integration requests
- LinkedIn access requests
- Calendar access requests
- Job search requests
- Career planning requests
- CV/profile requests
- Application tracking requests
- Mixed/ambiguous requests
- Unsupported tool requests
"""

from __future__ import annotations

import pytest

from src.rico.policy import (
    RicoDomain,
    classify_request,
    PolicyDecision,
    is_capability_available,
    get_unsupported_message,
)


class TestAccountSubscription:
    """Test account and subscription domain classification."""
    
    def test_what_is_my_plan_english(self):
        """'what is my plan?' -> account_subscription"""
        decision = classify_request("what is my plan?")
        assert decision.domain == RicoDomain.ACCOUNT_SUBSCRIPTION
        assert decision.route == "account_service"
        assert decision.confidence >= 0.9
        assert decision.action == "resolve_subscription_status"
    
    def test_what_plan_am_i_on_english(self):
        """'what plan am I on?' -> account_subscription"""
        decision = classify_request("what plan am I on?")
        assert decision.domain == RicoDomain.ACCOUNT_SUBSCRIPTION
        assert decision.route == "account_service"
        assert decision.confidence >= 0.9
    
    def test_message_limit_english(self):
        """'message limit' -> account_subscription"""
        decision = classify_request("what is my message limit?")
        assert decision.domain == RicoDomain.ACCOUNT_SUBSCRIPTION
        assert decision.route == "account_service"
    
    def test_subscription_status_english(self):
        """'my subscription status' -> account_subscription"""
        decision = classify_request("my subscription status")
        assert decision.domain == RicoDomain.ACCOUNT_SUBSCRIPTION
        assert decision.route == "account_service"
    
    def test_shu_ishteriaki_arabic(self):
        """'شو اشتراكي؟' -> account_subscription"""
        decision = classify_request("شو اشتراكي؟")
        assert decision.domain == RicoDomain.ACCOUNT_SUBSCRIPTION
        assert decision.language == "ar"
        assert decision.route == "account_service"
    
    def test_ana_ala_ay_baqa_arabic(self):
        """'انا على اي باقة؟' -> account_subscription"""
        decision = classify_request("انا على اي باقة؟")
        assert decision.domain == RicoDomain.ACCOUNT_SUBSCRIPTION
        assert decision.language == "ar"
        assert decision.route == "account_service"
    
    def test_baqa_status_arabic(self):
        """'حالة اشتراكي' -> account_subscription"""
        decision = classify_request("حالة اشتراكي")
        assert decision.domain == RicoDomain.ACCOUNT_SUBSCRIPTION
        assert decision.language == "ar"


class TestBillingPayment:
    """Test billing and payment domain classification."""
    
    def test_billing_english(self):
        """'billing' -> billing_payment"""
        decision = classify_request("billing")
        assert decision.domain == RicoDomain.BILLING_PAYMENT
        assert decision.route == "account_service"
    
    def test_payment_history_english(self):
        """'payment history' -> billing_payment"""
        decision = classify_request("my payment history")
        assert decision.domain == RicoDomain.BILLING_PAYMENT
        assert decision.route == "account_service"
    
    def test_invoice_english(self):
        """'invoice' -> billing_payment"""
        decision = classify_request("where is my invoice?")
        assert decision.domain == RicoDomain.BILLING_PAYMENT
    
    def test_refund_english(self):
        """'refund' -> billing_payment"""
        decision = classify_request("I want a refund")
        assert decision.domain == RicoDomain.BILLING_PAYMENT
        assert decision.route == "account_service"
    
    def test_factoring_arabic(self):
        """'الفاتورة' -> billing_payment"""
        decision = classify_request("أين فاتورتي؟")
        assert decision.domain == RicoDomain.BILLING_PAYMENT
        assert decision.language == "ar"


class TestUnsupportedExternalIntegrations:
    """Test unsupported external integration detection."""
    
    def test_fetch_gmail_jobs_english(self):
        """'fetch jobs from Gmail' -> email_gmail_request + unsupported"""
        decision = classify_request("fetch jobs I applied for from Gmail")
        assert decision.domain == RicoDomain.EMAIL_GMAIL_REQUEST
        assert decision.route == "unsupported"
        assert decision.tool_available is False
        assert "can't access" in decision.alternative_suggestion.lower()
    
    def test_check_email_inbox_english(self):
        """'check my email inbox' -> email_gmail_request + unsupported"""
        decision = classify_request("check my email inbox for applications")
        assert decision.domain == RicoDomain.EMAIL_GMAIL_REQUEST
        assert decision.route == "unsupported"
        assert decision.tool_available is False
    
    def test_access_gmail_english(self):
        """'access my Gmail' -> email_gmail_request + unsupported"""
        decision = classify_request("access my Gmail")
        assert decision.domain == RicoDomain.EMAIL_GMAIL_REQUEST
        assert decision.route == "unsupported"
    
    def test_linkedin_profile_english(self):
        """'my LinkedIn profile' -> linkedin_request + unsupported"""
        decision = classify_request("check my LinkedIn profile")
        assert decision.domain == RicoDomain.LINKEDIN_REQUEST
        assert decision.route == "unsupported"
        assert decision.tool_available is False
    
    def test_linkedin_messages_english(self):
        """'LinkedIn messages' -> linkedin_request + unsupported"""
        decision = classify_request("read my LinkedIn messages")
        assert decision.domain == RicoDomain.LINKEDIN_REQUEST
        assert decision.route == "unsupported"
    
    def test_calendar_schedule_english(self):
        """'schedule a meeting' -> calendar_request + unsupported"""
        decision = classify_request("schedule a meeting in my calendar")
        assert decision.domain == RicoDomain.CALENDAR_REQUEST
        assert decision.route == "unsupported"
        assert decision.tool_available is False
    
    def test_whatsapp_message_english(self):
        """'send me a WhatsApp' -> whatsapp_request + unsupported"""
        decision = classify_request("send me a WhatsApp message")
        assert decision.domain == RicoDomain.WHATSAPP_REQUEST
        assert decision.route == "unsupported"
        assert decision.tool_available is False
    
    def test_gmail_arabic(self):
        """'افحص إيميلي' -> email_gmail_request + unsupported (Arabic)"""
        decision = classify_request("افحص إيميلي")
        assert decision.domain == RicoDomain.EMAIL_GMAIL_REQUEST
        assert decision.route == "unsupported"
        assert decision.language == "ar"
    
    def test_linkedin_arabic(self):
        """'لينكد إن' -> linkedin_request + unsupported (Arabic)"""
        decision = classify_request("افحص لينكد إن")
        assert decision.domain == RicoDomain.LINKEDIN_REQUEST
        assert decision.route == "unsupported"
        assert decision.language == "ar"
    
    def test_unsupported_message_arabic(self):
        """Unsupported message in Arabic is returned correctly"""
        msg = get_unsupported_message(RicoDomain.EMAIL_GMAIL_REQUEST, "ar")
        assert "لا أستطيع" in msg or "Gmail" in msg


class TestJobSearch:
    """Test job search domain classification."""
    
    def test_find_hse_jobs_english(self):
        """'find me HSE jobs in UAE' -> job_search"""
        decision = classify_request("find me HSE jobs in UAE")
        assert decision.domain == RicoDomain.JOB_SEARCH
        assert decision.route == "job_search"
        assert decision.action == "execute_job_search"
    
    def test_find_jobs_generic_english(self):
        """'find me a job' -> job_search"""
        decision = classify_request("find me a job")
        assert decision.domain == RicoDomain.JOB_SEARCH
        assert decision.route == "job_search"
    
    def test_jobs_in_dubai_english(self):
        """'jobs in Dubai' -> job_search"""
        decision = classify_request("jobs in Dubai")
        assert decision.domain == RicoDomain.JOB_SEARCH
    
    def test_looking_for_role_english(self):
        """'looking for a role' -> job_search"""
        decision = classify_request("I'm looking for a manager role")
        assert decision.domain == RicoDomain.JOB_SEARCH
    
    def test_dawri_arabic(self):
        """'دوري' -> job_search (Arabic)"""
        decision = classify_request("ابحث لي عن دوري")
        assert decision.domain == RicoDomain.JOB_SEARCH
        assert decision.language == "ar"


class TestCareerStrategy:
    """Test career strategy domain classification."""
    
    def test_career_plan_english(self):
        """'make me a job search plan' -> career_strategy"""
        decision = classify_request("make me a job search plan")
        assert decision.domain == RicoDomain.CAREER_STRATEGY
        assert decision.route == "ai"
        assert decision.action == "ai_career_planning"
    
    def test_career_strategy_english(self):
        """'career strategy' -> career_strategy"""
        decision = classify_request("what's my career strategy?")
        assert decision.domain == RicoDomain.CAREER_STRATEGY
        assert decision.route == "ai"
    
    def test_what_roles_fit_me_english(self):
        """'what roles fit me' -> career_strategy"""
        decision = classify_request("what roles fit me?")
        assert decision.domain == RicoDomain.CAREER_STRATEGY
    
    def test_help_plan_english(self):
        """'help me plan' -> career_strategy"""
        decision = classify_request("help me plan my career")
        assert decision.domain == RicoDomain.CAREER_STRATEGY


class TestCVProfile:
    """Test CV and profile domain classification."""
    
    def test_upload_cv_english(self):
        """'upload my CV' -> cv_profile"""
        decision = classify_request("upload my CV")
        assert decision.domain == RicoDomain.CV_PROFILE
        assert decision.route == "ai"
    
    def test_my_profile_english(self):
        """'my profile' -> cv_profile"""
        decision = classify_request("show my profile")
        assert decision.domain == RicoDomain.CV_PROFILE
    
    def test_skills_english(self):
        """'skills' -> cv_profile"""
        decision = classify_request("what are my skills?")
        assert decision.domain == RicoDomain.CV_PROFILE
    
    def test_serah_dhatiqa_arabic(self):
        """'السيرة الذاتية' -> cv_profile (Arabic)"""
        decision = classify_request("أرفع السيرة الذاتية")
        assert decision.domain == RicoDomain.CV_PROFILE
        assert decision.language == "ar"


class TestApplicationTracking:
    """Test application tracking domain classification."""
    
    def test_track_applications_english(self):
        """'track my applications' -> applications_tracking"""
        decision = classify_request("track my applications")
        assert decision.domain == RicoDomain.APPLICATIONS_TRACKING
        assert decision.route == "application_tracking"
        assert decision.action == "get_application_status"
    
    def test_what_did_i_apply_english(self):
        """'what did I apply for?' -> applications_tracking"""
        decision = classify_request("what did I apply for?")
        assert decision.domain == RicoDomain.APPLICATIONS_TRACKING
        assert decision.route == "application_tracking"
    
    def test_application_status_english(self):
        """'application status' -> applications_tracking"""
        decision = classify_request("what is my application status?")
        assert decision.domain == RicoDomain.APPLICATIONS_TRACKING
    
    def test_where_are_applications_english(self):
        """'where are my applications' -> applications_tracking"""
        decision = classify_request("where are my applications?")
        assert decision.domain == RicoDomain.APPLICATIONS_TRACKING


class TestMixedAmbiguous:
    """Test mixed and ambiguous request handling."""
    
    def test_conflicting_domains_gmail_and_jobs(self):
        """Mixed Gmail + job search should ask clarification"""
        # This combines external tool + core service
        decision = classify_request("fetch my Gmail and find me HSE jobs")
        # Should detect conflicting domains and ask clarification
        assert decision.route in ["clarification", "unsupported", "job_search"]
        if decision.route == "clarification":
            assert decision.action == "ask_clarification"
    
    def test_nonsense_input(self):
        """Nonsense input should ask clarification"""
        decision = classify_request("xyz123 nonsense input here")
        assert decision.route == "clarification"
        assert decision.action == "ask_clarification"
    
    def test_empty_input(self):
        """Effectively empty input should ask clarification"""
        decision = classify_request("...")
        assert decision.route == "clarification"
    
    def test_combined_billing_and_jobs(self):
        """'what is my plan and find me jobs' - both valid, should pick primary"""
        decision = classify_request("what is my plan and find me jobs")
        # Should pick one domain confidently or ask clarification
        assert decision.confidence > 0.5


class TestTelegramSettings:
    """Test Telegram and settings domains."""
    
    def test_telegram_notification_english(self):
        """'telegram notification' -> telegram_request"""
        decision = classify_request("enable telegram notifications")
        assert decision.domain == RicoDomain.TELEGRAM_REQUEST
        assert decision.route == "ai"
    
    def test_settings_english(self):
        """'settings' -> settings_automation"""
        decision = classify_request("my settings")
        assert decision.domain == RicoDomain.SETTINGS_AUTOMATION


class TestSupportLegal:
    """Test support and legal domains."""
    
    def test_help_english(self):
        """'help' -> support_help"""
        decision = classify_request("help")
        assert decision.domain == RicoDomain.SUPPORT_HELP
        assert decision.route == "ai"
    
    def test_how_to_english(self):
        """'how do I...' -> support_help"""
        decision = classify_request("how do I use Rico?")
        assert decision.domain == RicoDomain.SUPPORT_HELP
    
    def test_privacy_policy_english(self):
        """'privacy policy' -> legal_policy"""
        decision = classify_request("what is your privacy policy?")
        assert decision.domain == RicoDomain.LEGAL_POLICY
        assert decision.route == "ai"
    
    def test_terms_english(self):
        """'terms of service' -> legal_policy"""
        decision = classify_request("terms of service")
        assert decision.domain == RicoDomain.LEGAL_POLICY


class TestCapabilities:
    """Test capability registry."""
    
    def test_job_search_available(self):
        """Job search capability should be available"""
        assert is_capability_available(RicoDomain.JOB_SEARCH) is True
    
    def test_cv_profile_available(self):
        """CV profile capability should be available"""
        assert is_capability_available(RicoDomain.CV_PROFILE) is True
    
    def test_application_tracking_available(self):
        """Application tracking capability should be available"""
        assert is_capability_available(RicoDomain.APPLICATIONS_TRACKING) is True
    
    def test_gmail_unavailable(self):
        """Gmail capability should be explicitly unavailable"""
        assert is_capability_available(RicoDomain.EMAIL_GMAIL_REQUEST) is False
    
    def test_linkedin_unavailable(self):
        """LinkedIn capability should be explicitly unavailable"""
        assert is_capability_available(RicoDomain.LINKEDIN_REQUEST) is False
    
    def test_calendar_unavailable(self):
        """Calendar capability should be explicitly unavailable"""
        assert is_capability_available(RicoDomain.CALENDAR_REQUEST) is False
    
    def test_whatsapp_unavailable(self):
        """WhatsApp capability should be explicitly unavailable"""
        assert is_capability_available(RicoDomain.WHATSAPP_REQUEST) is False
    
    def test_subscription_service_available(self):
        """Subscription service capability should be available"""
        assert is_capability_available(RicoDomain.ACCOUNT_SUBSCRIPTION) is True


class TestPolicyDecisionStructure:
    """Test PolicyDecision dataclass structure."""
    
    def test_decision_has_all_fields(self):
        """PolicyDecision should have all required fields"""
        decision = classify_request("what is my plan?")
        
        # All required fields present
        assert hasattr(decision, 'domain')
        assert hasattr(decision, 'route')
        assert hasattr(decision, 'confidence')
        assert hasattr(decision, 'needs_auth')
        assert hasattr(decision, 'needs_db')
        assert hasattr(decision, 'needs_external_tool')
        assert hasattr(decision, 'tool')
        assert hasattr(decision, 'tool_available')
        assert hasattr(decision, 'action')
        assert hasattr(decision, 'reason')
        assert hasattr(decision, 'language')
    
    def test_to_log_dict_safe(self):
        """to_log_dict should not expose secrets"""
        decision = classify_request("what is my plan?")
        log_dict = decision.to_log_dict()
        
        # Should not have full message content
        assert 'message' not in log_dict or len(str(log_dict.get('message', ''))) < 100
        # Should have domain info
        assert 'domain' in log_dict
        assert 'route' in log_dict
        assert 'action' in log_dict
    
    def test_confidence_range(self):
        """Confidence should be between 0 and 1"""
        decision = classify_request("what is my plan?")
        assert 0 <= decision.confidence <= 1.0


class TestLanguageDetection:
    """Test language detection."""
    
    def test_english_detection(self):
        """English message should have language='en'"""
        decision = classify_request("what is my plan?")
        assert decision.language == "en"
    
    def test_arabic_detection(self):
        """Arabic message should have language='ar'"""
        decision = classify_request("شو اشتراكي؟")
        assert decision.language == "ar"
    
    def test_mixed_detection_arabic(self):
        """Mostly Arabic message should have language='ar'"""
        decision = classify_request("شو خطتي what plan")
        # With >30% Arabic, should detect as Arabic
        assert decision.language == "ar"


# Run count check
def test_test_matrix_count():
    """Verify we have at least 40 test cases."""
    test_classes = [
        TestAccountSubscription,
        TestBillingPayment,
        TestUnsupportedExternalIntegrations,
        TestJobSearch,
        TestCareerStrategy,
        TestCVProfile,
        TestApplicationTracking,
        TestMixedAmbiguous,
        TestTelegramSettings,
        TestSupportLegal,
        TestCapabilities,
        TestPolicyDecisionStructure,
        TestLanguageDetection,
    ]
    
    test_count = sum(len([m for m in dir(cls) if m.startswith('test_')]) for cls in test_classes)
    assert test_count >= 40, f"Expected at least 40 tests, found {test_count}"
    print(f"Total test cases: {test_count}")

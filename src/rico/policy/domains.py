"""src/rico/policy/domains.py

Domain classification constants for Rico Policy Gateway.
Defines all request domains that Rico can handle or reject.
"""

from __future__ import annotations

from enum import Enum, auto


class RicoDomain(Enum):
    """Canonical domains for request classification."""
    
    # Account & Subscription
    ACCOUNT_SUBSCRIPTION = "account_subscription"
    BILLING_PAYMENT = "billing_payment"
    
    # Core Career Services
    JOB_SEARCH = "job_search"
    CAREER_STRATEGY = "career_strategy"
    CV_PROFILE = "cv_profile"
    APPLICATIONS_TRACKING = "applications_tracking"
    
    # External Integrations (Unsupported)
    EMAIL_GMAIL_REQUEST = "email_gmail_request"
    LINKEDIN_REQUEST = "linkedin_request"
    CALENDAR_REQUEST = "calendar_request"
    WHATSAPP_REQUEST = "whatsapp_request"
    
    # Communication Channels
    TELEGRAM_REQUEST = "telegram_request"
    
    # File & Settings
    FILE_UPLOAD = "file_upload"
    SETTINGS_AUTOMATION = "settings_automation"
    
    # Support & Legal
    SUPPORT_HELP = "support_help"
    LEGAL_POLICY = "legal_policy"
    
    # Unknown/Mixed
    UNKNOWN_OR_MIXED = "unknown_or_mixed"


# Domain display names (for logging and responses)
DOMAIN_DISPLAY_NAMES: dict[RicoDomain, str] = {
    RicoDomain.ACCOUNT_SUBSCRIPTION: "Account & Subscription",
    RicoDomain.BILLING_PAYMENT: "Billing & Payment",
    RicoDomain.JOB_SEARCH: "Job Search",
    RicoDomain.CAREER_STRATEGY: "Career Strategy",
    RicoDomain.CV_PROFILE: "CV & Profile",
    RicoDomain.APPLICATIONS_TRACKING: "Application Tracking",
    RicoDomain.EMAIL_GMAIL_REQUEST: "Gmail/Email Access",
    RicoDomain.LINKEDIN_REQUEST: "LinkedIn Access",
    RicoDomain.CALENDAR_REQUEST: "Calendar Access",
    RicoDomain.WHATSAPP_REQUEST: "WhatsApp Access",
    RicoDomain.TELEGRAM_REQUEST: "Telegram Notifications",
    RicoDomain.FILE_UPLOAD: "File Upload",
    RicoDomain.SETTINGS_AUTOMATION: "Settings & Automation",
    RicoDomain.SUPPORT_HELP: "Help & Support",
    RicoDomain.LEGAL_POLICY: "Legal & Policy",
    RicoDomain.UNKNOWN_OR_MIXED: "Unknown/Mixed Request",
}


# Domain descriptions (for clarifications)
DOMAIN_DESCRIPTIONS: dict[RicoDomain, str] = {
    RicoDomain.ACCOUNT_SUBSCRIPTION: "Questions about your plan, subscription status, or limits",
    RicoDomain.BILLING_PAYMENT: "Billing history, payment methods, invoices, or refunds",
    RicoDomain.JOB_SEARCH: "Finding jobs, searching roles, or matching opportunities",
    RicoDomain.CAREER_STRATEGY: "Career planning, role suggestions, or job search strategy",
    RicoDomain.CV_PROFILE: "CV upload, profile updates, or career background",
    RicoDomain.APPLICATIONS_TRACKING: "Tracked applications, application status, or pipeline",
    RicoDomain.EMAIL_GMAIL_REQUEST: "Accessing Gmail or email inbox",
    RicoDomain.LINKEDIN_REQUEST: "Accessing LinkedIn profile, connections, or messages",
    RicoDomain.CALENDAR_REQUEST: "Accessing calendar or scheduling",
    RicoDomain.WHATSAPP_REQUEST: "WhatsApp integration or messaging",
    RicoDomain.TELEGRAM_REQUEST: "Telegram notifications or bot commands",
    RicoDomain.FILE_UPLOAD: "Uploading CV, documents, or files",
    RicoDomain.SETTINGS_AUTOMATION: "Automation settings, preferences, or tuning",
    RicoDomain.SUPPORT_HELP: "Help with using Rico or feature explanations",
    RicoDomain.LEGAL_POLICY: "Terms, privacy, refunds, or legal questions",
    RicoDomain.UNKNOWN_OR_MIXED: "Request that combines multiple unclear intents",
}

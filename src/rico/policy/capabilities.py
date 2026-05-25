"""src/rico/policy/capabilities.py

Capability registry for Rico Policy Gateway.
Defines which integrations and services are available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .domains import RicoDomain


@dataclass(frozen=True)
class Capability:
    """Capability definition with availability status."""
    name: str
    domain: RicoDomain
    available: bool
    requires_auth: bool
    requires_db: bool
    requires_external_tool: bool
    reason_if_unavailable: str
    alternative_suggestion: str


class CapabilityRegistry:
    """Central registry for Rico capabilities."""
    
    def __init__(self):
        self._capabilities: dict[RicoDomain, Capability] = {}
        self._load_capabilities()
    
    def _load_capabilities(self):
        """Initialize all capabilities with their availability status."""
        
        # Core services (always available)
        self._capabilities[RicoDomain.JOB_SEARCH] = Capability(
            name="job_search",
            domain=RicoDomain.JOB_SEARCH,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=True,  # Uses JSearch API
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        self._capabilities[RicoDomain.CV_PROFILE] = Capability(
            name="cv_profile",
            domain=RicoDomain.CV_PROFILE,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        self._capabilities[RicoDomain.APPLICATIONS_TRACKING] = Capability(
            name="application_tracking",
            domain=RicoDomain.APPLICATIONS_TRACKING,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        self._capabilities[RicoDomain.CAREER_STRATEGY] = Capability(
            name="career_strategy",
            domain=RicoDomain.CAREER_STRATEGY,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=False,  # Uses AI, not external tool
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        # Subscription services
        self._capabilities[RicoDomain.ACCOUNT_SUBSCRIPTION] = Capability(
            name="subscription_service",
            domain=RicoDomain.ACCOUNT_SUBSCRIPTION,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        self._capabilities[RicoDomain.BILLING_PAYMENT] = Capability(
            name="stripe_billing",
            domain=RicoDomain.BILLING_PAYMENT,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=True,  # Uses Stripe
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        # File & Settings
        self._capabilities[RicoDomain.FILE_UPLOAD] = Capability(
            name="file_upload",
            domain=RicoDomain.FILE_UPLOAD,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        self._capabilities[RicoDomain.SETTINGS_AUTOMATION] = Capability(
            name="settings_automation",
            domain=RicoDomain.SETTINGS_AUTOMATION,
            available=True,
            requires_auth=True,
            requires_db=True,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        # Communication channels
        # Note: Telegram is marked as available=True - the actual configuration check
        # happens in the handler. This ensures policy gateway routes it to AI,
        # and the handler can provide appropriate response if not configured.
        self._capabilities[RicoDomain.TELEGRAM_REQUEST] = Capability(
            name="telegram_notifications",
            domain=RicoDomain.TELEGRAM_REQUEST,
            available=True,  # Policy treats as available; handler checks config
            requires_auth=True,
            requires_db=True,
            requires_external_tool=True,
            reason_if_unavailable="Telegram notifications are not configured for your account",
            alternative_suggestion="Enable Telegram notifications in Settings to receive job alerts",
        )
        
        # External integrations (explicitly unavailable)
        self._capabilities[RicoDomain.EMAIL_GMAIL_REQUEST] = Capability(
            name="gmail",
            domain=RicoDomain.EMAIL_GMAIL_REQUEST,
            available=False,  # NOT available - explicit boundary
            requires_auth=True,
            requires_db=False,
            requires_external_tool=True,
            reason_if_unavailable="I can't access your Gmail or email inbox from Rico",
            alternative_suggestion="You can upload, paste, or forward the relevant information and I'll organize it",
        )
        
        self._capabilities[RicoDomain.LINKEDIN_REQUEST] = Capability(
            name="linkedin_direct_access",
            domain=RicoDomain.LINKEDIN_REQUEST,
            available=False,  # NOT available - explicit boundary
            requires_auth=True,
            requires_db=False,
            requires_external_tool=True,
            reason_if_unavailable="I can't access your LinkedIn profile or messages directly",
            alternative_suggestion="Share your LinkedIn profile URL or paste relevant information and I'll help",
        )
        
        self._capabilities[RicoDomain.CALENDAR_REQUEST] = Capability(
            name="calendar",
            domain=RicoDomain.CALENDAR_REQUEST,
            available=False,  # NOT available - explicit boundary
            requires_auth=True,
            requires_db=False,
            requires_external_tool=True,
            reason_if_unavailable="I can't access your calendar or schedule meetings",
            alternative_suggestion="Tell me your availability or preferred times and I'll track it",
        )
        
        self._capabilities[RicoDomain.WHATSAPP_REQUEST] = Capability(
            name="whatsapp",
            domain=RicoDomain.WHATSAPP_REQUEST,
            available=False,  # NOT available - explicit boundary
            requires_auth=True,
            requires_db=False,
            requires_external_tool=True,
            reason_if_unavailable="I can't send or receive WhatsApp messages",
            alternative_suggestion="Use Telegram notifications (if enabled) or email for job alerts",
        )
        
        # Support & Legal
        self._capabilities[RicoDomain.SUPPORT_HELP] = Capability(
            name="support_help",
            domain=RicoDomain.SUPPORT_HELP,
            available=True,
            requires_auth=False,  # Can help without auth
            requires_db=False,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        self._capabilities[RicoDomain.LEGAL_POLICY] = Capability(
            name="legal_policy",
            domain=RicoDomain.LEGAL_POLICY,
            available=True,
            requires_auth=False,
            requires_db=False,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
        
        # Unknown/Mixed
        self._capabilities[RicoDomain.UNKNOWN_OR_MIXED] = Capability(
            name="unknown",
            domain=RicoDomain.UNKNOWN_OR_MIXED,
            available=True,  # Will ask for clarification
            requires_auth=False,
            requires_db=False,
            requires_external_tool=False,
            reason_if_unavailable="",
            alternative_suggestion="",
        )
    
    def get(self, domain: RicoDomain) -> Optional[Capability]:
        """Get capability for a domain."""
        return self._capabilities.get(domain)
    
    def is_available(self, domain: RicoDomain) -> bool:
        """Check if a capability is available."""
        cap = self._capabilities.get(domain)
        return cap.available if cap else False
    
    def get_unsupported_message(self, domain: RicoDomain, language: str = "en") -> str:
        """Get the unsupported tool message for a domain in the specified language."""
        cap = self._capabilities.get(domain)
        if not cap or cap.available:
            return ""
        
        # Arabic messages for unsupported tools
        arabic_messages = {
            RicoDomain.EMAIL_GMAIL_REQUEST: (
                "لا أستطيع الوصول إلى بريدك الإلكتروني أو Gmail من Rico حاليًا. "
                "يمكنك رفع المعلومات أو لصقها أو إعادة توجيهها وسأقوم بتنظيمها."
            ),
            RicoDomain.LINKEDIN_REQUEST: (
                "لا أستطيع الوصول إلى ملفك الشخصي على LinkedIn أو رسائلك مباشرة. "
                "شارك رابط ملفك الشخصي أو الصق المعلومات ذات الصلة وسأساعدك."
            ),
            RicoDomain.CALENDAR_REQUEST: (
                "لا أستطيع الوصول إلى تقويمك أو جدولة الاجتماعات. "
                "أخبرني بتوافرك أو الأوقات المفضلة وسأتتبعها."
            ),
            RicoDomain.WHATSAPP_REQUEST: (
                "لا أستطيع إرسال أو استلام رسائل WhatsApp. "
                "استخدم إشعارات Telegram (إذا تم تمكينها) أو البريد الإلكتروني للتنبيهات."
            ),
        }
        
        if language == "ar" and domain in arabic_messages:
            return arabic_messages[domain]
        
        return f"{cap.reason_if_unavailable}. {cap.alternative_suggestion}."
    
    def get_alternative_suggestion(self, domain: RicoDomain) -> str:
        """Get alternative suggestion for unsupported capability."""
        cap = self._capabilities.get(domain)
        return cap.alternative_suggestion if cap else ""


# Global registry instance
_registry = CapabilityRegistry()


def get_capability(domain: RicoDomain) -> Optional[Capability]:
    """Get capability for a domain."""
    return _registry.get(domain)


def is_capability_available(domain: RicoDomain) -> bool:
    """Check if a capability is available."""
    return _registry.is_available(domain)


def get_unsupported_message(domain: RicoDomain, language: str = "en") -> str:
    """Get unsupported tool message."""
    return _registry.get_unsupported_message(domain, language)

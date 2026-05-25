"""src/rico/policy/policy.py

Rico Brain Policy Gateway - Phase 1 Implementation.

Central policy layer that:
1. Classifies requests into domains
2. Checks capability availability
3. Makes routing decisions before AI fallback
4. Handles unsupported tool requests deterministically
"""

from __future__ import annotations

import logging
import hashlib
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple

from .domains import RicoDomain
from .capabilities import (
    Capability,
    get_capability,
    is_capability_available,
    get_unsupported_message,
)

logger = logging.getLogger(__name__)


def _normalize_arabic(text: str) -> str:
    """Remove diacritics and normalise Arabic letter variants for pattern matching.

    Mirrors the same function in intent_classifier.py — kept local to avoid a
    cross-package import between the policy layer and the agent intelligence layer.
    """
    # Strip tashkeel (fatha, kasra, damma, sukun, shadda, tanwin, tatweel)
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    # Normalise alef variants (madda آ, hamza above أ, hamza below إ, wasla ٱ) → bare alef ا
    text = re.sub(r"[آأإٱ]", "ا", text)
    # Normalise alef maqsura ى → ya ي
    text = re.sub(r"ى", "ي", text)
    # Normalise ta marbuta ة → ha ه  (so وظيفة == وظيفه in lookups)
    text = re.sub(r"ة", "ه", text)
    return text


@dataclass(frozen=True)
class PolicyDecision:
    """Policy decision for a user request.
    
    Fields:
        domain: The classified domain
        route: Where to route this request
        confidence: Classification confidence (0.0-1.0)
        needs_auth: Whether authentication is required
        needs_db: Whether database access is required
        needs_external_tool: Whether external API/tool is needed
        tool: Specific tool name if applicable
        tool_available: Whether the tool is available
        action: Specific action to take
        reason: Explanation for the decision
        language: Detected language (en/ar)
    """
    domain: RicoDomain
    route: str
    confidence: float
    needs_auth: bool
    needs_db: bool
    needs_external_tool: bool
    tool: Optional[str] = None
    tool_available: bool = True
    action: str = ""
    reason: str = ""
    language: str = "en"
    alternative_suggestion: str = ""
    
    def to_log_dict(self) -> dict:
        """Convert to dict for safe logging (no secrets, no long content)."""
        return {
            "domain": self.domain.value,
            "route": self.route,
            "confidence": round(self.confidence, 2),
            "action": self.action,
            "reason": self.reason,
            "language": self.language,
            "needs_auth": self.needs_auth,
            "needs_db": self.needs_db,
            "needs_external_tool": self.needs_external_tool,
            "tool_available": self.tool_available,
        }


class PolicyGateway:
    """Central policy gateway for Rico Brain."""
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.9
    MEDIUM_CONFIDENCE = 0.7
    LOW_CONFIDENCE = 0.5
    
    # Routing destinations
    ROUTE_DETERMINISTIC = "deterministic"
    ROUTE_AI = "ai"
    ROUTE_UNSUPPORTED = "unsupported"
    ROUTE_CLARIFICATION = "clarification"
    ROUTE_ACCOUNT_SERVICE = "account_service"
    ROUTE_JOB_SEARCH = "job_search"
    ROUTE_APPLICATION_TRACKING = "application_tracking"
    
    def __init__(self):
        self._load_patterns()
    
    def _load_patterns(self):
        """Load classification patterns for all domains."""
        
        # Account & Subscription patterns (English + Arabic)
        self._account_patterns = [
            # English
            r"\bwhat('s| is) my (plan|subscription)\b",
            r"\bwhat plan am i on\b",
            r"\bmy (plan|subscription) status\b",
            r"\b(current|active) (plan|subscription)\b",
            r"\bsubscription (details|info)\b",
            r"\baccount (status|limits)\b",
            r"\bmessage limit\b",
            r"\bhow many (messages|jobs) (left|remaining)\b",
            r"\bupgrade (plan|subscription)\b",
            r"\bcancel (plan|subscription)\b",
            # Arabic (normalised: alef variants→ا, ة→ه, ى→ي — input is pre-normalised)
            r"اشتراكي",
            r"باقتي",
            r"شو\s+اشتراكي",
            r"ما\s+هو\s+اشتراكي",
            r"انا\s+على\s+اي\s+باقه",   # أنا على أي باقة → normalised
            r"على\s+اي\s+باقه",          # على أي باقة → normalised
            r"حاله\s+اشتراكي",           # حالة اشتراكي → normalised
            r"الباقه\s+الحاليه",         # الباقة الحالية → normalised
            r"حد\s+الرسائل",
            r"كم\s+رساله\s+باقي",        # كم رسالة باقي → normalised
            r"ترقيه\s+الباقه",           # ترقية الباقة → normalised
            r"الغاء\s+الاشتراك",         # إلغاء الاشتراك → normalised
            r"خطه\s+الاشتراك",           # خطة الاشتراك → normalised
            # MSA additions
            r"باقتي\s+ايه",              # باقتي إيه (Egyptian MSA — what's my plan?)
            r"نوع\s+الاشتراك",           # type of subscription
            r"تجديد\s+الاشتراك",         # subscription renewal
        ]
        
        # Billing & Payment patterns
        self._billing_patterns = [
            # English
            r"\bbilling\b",
            r"\bpayment (method|history)\b",
            r"\binvoice\b",
            r"\brefund\b",
            r"\bcharge\b",
            r"\bcredit card\b",
            r"\bhow much (do i pay|does it cost)\b",
            # Arabic - expanded
            r"الفوتره",       # الفوترة → normalised
            r"الدفع",
            r"الفاتوره",     # الفاتورة → normalised
            r"فاتورتي",
            r"فواتيري",
            r"استرداد",
            r"رسوم",
            r"بطاقه الائتمان",  # بطاقة الائتمان → normalised
            r"كم السعر",
            r"الدفعات",
        ]
        
        # Gmail/Email patterns
        self._gmail_patterns = [
            # English
            r"\bgmail\b",
            r"\bcheck my (email|inbox)\b",
            r"\bfetch (emails|messages) from\b",
            r"\b(read|access) my (emails|gmail)\b",
            r"\bscan (email|inbox) for\b",
            r"\bapplications? (from|in) (gmail|email)\b",
            r"\bimport from (gmail|email)\b",
            # Arabic
            r"\b(جيميل|الايميل|البريد|الصندوق)\b",  # إ→ا in الإيميل
            r"افحص ايميلي",      # افحص إيميلي → normalised
            r"تفقد بريدي",
            r"جيب من الايميل",   # الإيميل → normalised
            r"اقرا رسايلي",      # اقرأ → normalised
        ]
        
        # LinkedIn patterns
        self._linkedin_patterns = [
            # English - integration-intent phrases only; bare "linkedin" excluded
            r"\bmy linkedin (profile|account)\b",
            r"\b(access|check|scan) linkedin\b",
            r"\b(import|fetch) from linkedin\b",
            r"\b(linkedin|connections) (messages|inbox)\b",
            # Arabic
            r"\bلينكد ان\b",          # لينكد إن → normalised
            r"ملفي على لينكد ان",   # normalised
            r"رسائل لينكد ان",      # normalised
        ]
        
        # Calendar patterns
        self._calendar_patterns = [
            # English — bare "calendar" excluded; "calendar interview question" must not block
            r"\bmy calendar\b",
            r"\bschedule (a|meeting|interview)\b",
            r"\bbook (a|time|slot)\b",
            r"\bcheck my availability\b",
            r"\bgoogle calendar\b",
            r"\boutlook calendar\b",
            # Arabic
            r"\bالتقويم\b",
            r"\bجدولة\b",
            r"\bموعد\b",
            r"\bاجتماع\b",
            r"\bمتى اكون متفرج\b",   # أكون → normalised
        ]
        
        # WhatsApp patterns
        self._whatsapp_patterns = [
            # English
            r"\bwhatsapp\b",
            r"\b(whatsapp|wa) (message|notification)\b",
            r"\bsend (me )?a whatsapp\b",
            # Arabic
            r"\bواتساب\b",
            r"\bواتس\b",
            r"رساله واتساب",   # رسالة → normalised
        ]
        
        # Telegram patterns - Note: Telegram is SUPPORTED (available if configured)
        # This differs from Gmail/LinkedIn/Calendar which are explicitly unsupported
        self._telegram_patterns = [
            # English
            r"\btelegram\b",
            r"\btg\s+(bot|notifications?)\b",
            r"\benable\s+telegram\b",
            r"\bsetup\s+telegram\b",
            r"\btelegram\s+(notifications?|alerts?)\b",
            # Arabic
            r"\bتلغرام\b",
            r"\bتيليجرام\b",
            r"تفعيل\s+تلغرام",
            r"تفعيل\s+تيليجرام",
        ]
        
        # Job Search patterns
        self._job_search_patterns = [
            # English - more specific to avoid career strategy overlap
            r"\bfind (me\s+)?(a\s+)?job\b",
            r"\bsearch (for\s+)?jobs\b",
            r"\bjob (search|hunt|opportunities?)\b",
            r"\b(hse|manager|engineer|analyst|developer)\s+jobs?\b",
            r"\bjobs? in (dubai|abu dhabi|uae|sharjah|ras al khaimah)\b",
            r"looking\s+for\s+(a\s+)?\w*\s*(job|work|employment|role|position)",
            r"\bopenings? for\b",
            r"\bvacancies?\b",
            r"\bany\s+(jobs?|openings?)\b",
            # Arabic
            r"\bدوري\b",
            r"\bوظيفه\b",              # وظيفة → normalised
            r"\bوظائف\b",
            r"ابحث\s+لي\s+عن\s+وظيفه",  # normalised
            r"دورات\s+في\s+دبي",
            r"وظائف\s+في\s+الامارات",   # الإمارات → normalised
            # MSA additions
            r"ارغب\s+في\s+(عمل|وظيفه)",  # أرغب في عمل / وظيفة
            r"احتاج\s+وظيفه",            # أحتاج وظيفة
            r"اسعي\s+ل(وظيفه|عمل)",      # أسعى لوظيفة / لعمل
            r"هل\s+(يوجد|توجد)\s+وظائف", # are there jobs? (MSA question)
            r"هل\s+هناك\s+وظائف",        # are there any jobs?
            r"فرص\s+عمل",                # job opportunities
        ]
        
        # Career Strategy patterns
        self._career_strategy_patterns = [
            # English - higher priority phrases first
            r"\bcareer\s+(plan|strategy|path|advice|roadmap)\b",
            r"\bjob\s+search\s+(plan|strategy|roadmap)\b",
            r"\bmake\s+me\s+a\s+(career|job)\s+(plan|strategy)\b",
            r"\bhow\s+(do|should)\s+i\s+(plan|strategize)\b",
            r"\bwhat\s+(roles|jobs)\s+(should|fit|suit)\s+me\b",
            r"\bhelp\s+me\s+plan\b",
            r"\bhelp\s+me\s+with\s+my\s+career\b",
            r"\b(build|create|make)\s+(a\s+)?(plan|strategy)\b",
            r"\bcareer\s+advice\b",
            r"\bwhat\s+should\s+i\s+do\s+(for|with)\s+my\s+career\b",
            # Arabic
            r"\bخطه\s+مهنيه\b",     # خطة مهنية → normalised
            r"\bاستراتيجيه\b",      # استراتيجية → normalised
            r"\bنصيحه\s+مهنيه\b",   # نصيحة مهنية → normalised
            r"\bكيف\s+احصل\s+على\b",  # كيف أحصل على → normalised
            r"\bماذا\s+يناسبني\b",
            # MSA additions
            r"\bمسار\s+مهني\b",      # career path
            r"\bتطوير\s+مهني\b",     # professional development
        ]
        
        # CV/Profile patterns
        self._cv_profile_patterns = [
            # English
            r"\b(upload|update) (my )?(cv|resume|profile)\b",
            r"\bmy (cv|resume|profile)\b",
            r"\b(cv|resume) (upload|update|parse)\b",
            r"\bskills\b",
            r"\bexperience\b",
            r"\bbackground\b",
            # Arabic
            r"\bالسيره الذاتيه\b",  # السيرة الذاتية → normalised
            r"\bسي في\b",
            r"\bملفي\b",
            r"\bخبراتي\b",
            r"\bمهاراتي\b",
        ]
        
        # Application Tracking patterns
        self._application_tracking_patterns = [
            # English
            r"\b(track|view|see) (my )?applications?\b",
            r"\bwhat did i apply (for|to)\b",
            r"\bmy (application|pipeline|flow) status\b",
            r"\b(application|job) (tracking|tracker)\b",
            r"\bstatus of (my )?applications?\b",
            r"\bwhere (are|is) my applications?\b",
            # Arabic
            r"\bتتبع طلباتي\b",
            r"\bطلباتي\b",
            r"\bحاله التقديم\b",   # حالة التقديم → normalised
            r"\bماذا تقدمت ل\b",
            r"\bاين طلباتي\b",     # أين طلباتي → normalised
        ]
        
        # File Upload patterns
        self._file_upload_patterns = [
            # English
            r"\bupload\b",
            r"\b(file|document|attachment)\b",
            r"\bpdf\b",
            r"\bdocx?\b",
            r"\b\.pdf\b",
            r"\b\.doc\b",
            # Arabic
            r"\bرفع\b",
            r"\bملف\b",
            r"\bمستند\b",
        ]
        
        # Settings/Automation patterns
        self._settings_patterns = [
            # English
            r"\bsettings?\b",
            r"\b(automation|preferences|tuning)\b",
            r"\bnotification (settings|preferences)\b",
            r"\bconfigure\b",
            r"\bcustomize\b",
            # Arabic
            r"\bإعدادات\b",
            r"\bأتمتة\b",
            r"\bتفضيلات\b",
            r"\bضبط\b",
        ]
        
        # Support/Help patterns
        self._support_patterns = [
            # English
            r"\bhelp\b",
            r"\bhow (do|can|to)\b",
            r"\bwhat can you do\b",
            r"\bwhat (are|do) you\b",
            r"\bguide\b",
            r"\btutorial\b",
            r"\bsupport\b",
            r"\bcontact (support|help)\b",
            # Arabic
            r"\bمساعدة\b",
            r"\bكيف\b",
            r"\bماذا تفعل\b",
            r"\bدليل\b",
            r"\bشرح\b",
            r"\bتواصل\b",
        ]
        
        # Legal/Policy patterns
        self._legal_patterns = [
            # English
            r"\b(privacy|terms|refund) (policy|policy)\b",
            r"\bterms of service\b",
            r"\bprivacy policy\b",
            r"\b(refund|cancellation) policy\b",
            r"\bdata (privacy|protection)\b",
            # Arabic
            r"\bسياسة الخصوصية\b",
            r"\bشروط الاستخدام\b",
            r"\bسياسة الاسترداد\b",
            r"\bخصوصية البيانات\b",
        ]
    
    def _detect_language(self, message: str) -> str:
        """Detect if message is primarily Arabic or English."""
        arabic_chars = sum(1 for c in message if '\u0600' <= c <= '\u06FF')
        total_chars = len(message.strip())
        
        if total_chars == 0:
            return "en"
        
        arabic_ratio = arabic_chars / total_chars
        return "ar" if arabic_ratio > 0.3 else "en"
    
    def _match_patterns(self, message: str, patterns: List[str]) -> bool:
        """Check if message matches any of the patterns.

        Both the message and the pattern strings are normalised before matching
        so callers do not need to manually duplicate patterns for every hamza /
        ta-marbuta / alef-maqsura variant.
        """
        text_lower = _normalize_arabic(message.lower())
        for pattern in patterns:
            norm_pattern = _normalize_arabic(pattern)
            if re.search(norm_pattern, text_lower, re.IGNORECASE | re.UNICODE):
                return True
        return False
    
    def _score_domain(self, message: str, domain: RicoDomain) -> Tuple[float, str]:
        """Score how well a message matches a domain.
        
        Returns (confidence, reason)
        """
        if domain == RicoDomain.ACCOUNT_SUBSCRIPTION:
            if self._match_patterns(message, self._account_patterns):
                return (0.95, "subscription_keywords_matched")
        
        elif domain == RicoDomain.BILLING_PAYMENT:
            if self._match_patterns(message, self._billing_patterns):
                return (0.95, "billing_keywords_matched")
        
        elif domain == RicoDomain.EMAIL_GMAIL_REQUEST:
            if self._match_patterns(message, self._gmail_patterns):
                return (0.95, "gmail_keywords_matched")
        
        elif domain == RicoDomain.LINKEDIN_REQUEST:
            if self._match_patterns(message, self._linkedin_patterns):
                return (0.95, "linkedin_keywords_matched")
        
        elif domain == RicoDomain.CALENDAR_REQUEST:
            if self._match_patterns(message, self._calendar_patterns):
                return (0.95, "calendar_keywords_matched")
        
        elif domain == RicoDomain.WHATSAPP_REQUEST:
            if self._match_patterns(message, self._whatsapp_patterns):
                return (0.95, "whatsapp_keywords_matched")
        
        elif domain == RicoDomain.TELEGRAM_REQUEST:
            if self._match_patterns(message, self._telegram_patterns):
                return (0.95, "telegram_keywords_matched")
        
        elif domain == RicoDomain.JOB_SEARCH:
            if self._match_patterns(message, self._job_search_patterns):
                return (0.90, "job_search_keywords_matched")
        
        elif domain == RicoDomain.CAREER_STRATEGY:
            if self._match_patterns(message, self._career_strategy_patterns):
                # Higher confidence than job_search (0.90) so specific career 
                # strategy phrases like "make me a job search plan" win over 
                # generic "job search" matches
                return (0.95, "career_strategy_keywords_matched")
        
        elif domain == RicoDomain.CV_PROFILE:
            if self._match_patterns(message, self._cv_profile_patterns):
                return (0.85, "cv_profile_keywords_matched")
        
        elif domain == RicoDomain.APPLICATIONS_TRACKING:
            if self._match_patterns(message, self._application_tracking_patterns):
                return (0.95, "application_tracking_keywords_matched")
        
        elif domain == RicoDomain.FILE_UPLOAD:
            if self._match_patterns(message, self._file_upload_patterns):
                return (0.80, "file_upload_keywords_matched")
        
        elif domain == RicoDomain.SETTINGS_AUTOMATION:
            if self._match_patterns(message, self._settings_patterns):
                return (0.80, "settings_keywords_matched")
        
        elif domain == RicoDomain.SUPPORT_HELP:
            if self._match_patterns(message, self._support_patterns):
                return (0.70, "support_keywords_matched")
        
        elif domain == RicoDomain.LEGAL_POLICY:
            if self._match_patterns(message, self._legal_patterns):
                return (0.95, "legal_keywords_matched")
        
        return (0.0, "no_match")
    
    def classify(self, message: str, has_auth: bool = True) -> PolicyDecision:
        """Classify a message and return a policy decision.
        
        This is the main entry point for the policy gateway.
        """
        language = self._detect_language(message)
        
        # Score all domains
        domain_scores = []
        for domain in RicoDomain:
            score, reason = self._score_domain(message, domain)
            if score > 0:
                domain_scores.append((domain, score, reason))
        
        # Sort by score descending
        domain_scores.sort(key=lambda x: x[1], reverse=True)
        
        # If no domain matched, it's unknown/mixed
        if not domain_scores:
            return PolicyDecision(
                domain=RicoDomain.UNKNOWN_OR_MIXED,
                route=self.ROUTE_CLARIFICATION,
                confidence=0.5,
                needs_auth=False,
                needs_db=False,
                needs_external_tool=False,
                action="ask_clarification",
                reason="no_domain_matched",
                language=language,
            )
        
        # Take the highest scoring domain
        best_domain, best_score, best_reason = domain_scores[0]
        
        # Check if there are close competing domains (indicates mixed request)
        if len(domain_scores) > 1 and domain_scores[1][1] >= best_score - 0.15:
            # Two domains are close - check if they conflict
            second_domain = domain_scores[1][0]
            if self._domains_conflict(best_domain, second_domain):
                return PolicyDecision(
                    domain=RicoDomain.UNKNOWN_OR_MIXED,
                    route=self.ROUTE_CLARIFICATION,
                    confidence=best_score - 0.2,
                    needs_auth=False,
                    needs_db=False,
                    needs_external_tool=False,
                    action="ask_clarification",
                    reason=f"conflicting_domains:{best_domain.value}_vs_{second_domain.value}",
                    language=language,
                )
        
        # Get capability info
        capability = get_capability(best_domain)
        if capability is None:
            capability = Capability(
                name="unknown",
                domain=best_domain,
                available=False,
                requires_auth=True,
                requires_db=False,
                requires_external_tool=False,
                reason_if_unavailable="Unknown capability",
                alternative_suggestion="",
            )
        
        # Check availability for unsupported external tools
        if not capability.available and capability.requires_external_tool:
            unsupported_msg = get_unsupported_message(best_domain, language)
            return PolicyDecision(
                domain=best_domain,
                route=self.ROUTE_UNSUPPORTED,
                confidence=best_score,
                needs_auth=capability.requires_auth,
                needs_db=capability.requires_db,
                needs_external_tool=capability.requires_external_tool,
                tool=capability.name,
                tool_available=False,
                action="unsupported_tool_response",
                reason=best_reason,
                language=language,
                alternative_suggestion=unsupported_msg,
            )
        
        # Determine route based on domain
        route = self._determine_route(best_domain, has_auth)
        
        return PolicyDecision(
            domain=best_domain,
            route=route,
            confidence=best_score,
            needs_auth=capability.requires_auth,
            needs_db=capability.requires_db,
            needs_external_tool=capability.requires_external_tool,
            tool=capability.name if capability else None,
            tool_available=capability.available if capability else True,
            action=self._determine_action(best_domain, route),
            reason=best_reason,
            language=language,
        )
    
    def _domains_conflict(self, domain1: RicoDomain, domain2: RicoDomain) -> bool:
        """Check if two domains conflict (require different handling)."""
        # External tool requests conflict with job search
        external_domains = {
            RicoDomain.EMAIL_GMAIL_REQUEST,
            RicoDomain.LINKEDIN_REQUEST,
            RicoDomain.CALENDAR_REQUEST,
            RicoDomain.WHATSAPP_REQUEST,
        }
        
        core_domains = {
            RicoDomain.JOB_SEARCH,
            RicoDomain.CAREER_STRATEGY,
            RicoDomain.CV_PROFILE,
            RicoDomain.APPLICATIONS_TRACKING,
        }
        
        # One is external tool, one is core service = potential confusion
        if (domain1 in external_domains and domain2 in core_domains) or \
           (domain2 in external_domains and domain1 in core_domains):
            return True
        
        return False
    
    def _determine_route(self, domain: RicoDomain, has_auth: bool) -> str:
        """Determine the routing destination for a domain."""
        
        # Account/subscription -> always account_service; auth check is in the service layer
        # BILLING_PAYMENT falls through to AI so pricing/invoice queries reach the normal path
        if domain == RicoDomain.ACCOUNT_SUBSCRIPTION:
            return self.ROUTE_ACCOUNT_SERVICE
        
        # External unsupported tools (Gmail, LinkedIn, Calendar, WhatsApp)
        # These are explicitly NOT available
        if domain in (
            RicoDomain.EMAIL_GMAIL_REQUEST,
            RicoDomain.LINKEDIN_REQUEST,
            RicoDomain.CALENDAR_REQUEST,
            RicoDomain.WHATSAPP_REQUEST,
        ):
            return self.ROUTE_UNSUPPORTED
        
        # Telegram is SUPPORTED (available if configured) -> AI handler
        if domain == RicoDomain.TELEGRAM_REQUEST:
            return self.ROUTE_AI
        
        # Job search
        if domain == RicoDomain.JOB_SEARCH:
            return self.ROUTE_JOB_SEARCH
        
        # Application tracking
        if domain == RicoDomain.APPLICATIONS_TRACKING:
            return self.ROUTE_APPLICATION_TRACKING
        
        # Career strategy, CV/Profile -> AI with context
        if domain in (RicoDomain.CAREER_STRATEGY, RicoDomain.CV_PROFILE):
            return self.ROUTE_AI
        
        # Settings, Support, Legal -> AI (with appropriate handling)
        if domain in (
            RicoDomain.SETTINGS_AUTOMATION,
            RicoDomain.SUPPORT_HELP,
            RicoDomain.LEGAL_POLICY,
        ):
            return self.ROUTE_AI
        
        # File upload -> Deterministic
        if domain == RicoDomain.FILE_UPLOAD:
            return self.ROUTE_DETERMINISTIC
        
        # Default to AI
        return self.ROUTE_AI
    
    def _determine_action(self, domain: RicoDomain, route: str) -> str:
        """Determine the specific action for a domain/route combination."""
        action_map = {
            (RicoDomain.ACCOUNT_SUBSCRIPTION, self.ROUTE_ACCOUNT_SERVICE): "resolve_subscription_status",
            (RicoDomain.BILLING_PAYMENT, self.ROUTE_AI): "ai_billing_info",
            (RicoDomain.JOB_SEARCH, self.ROUTE_JOB_SEARCH): "execute_job_search",
            (RicoDomain.APPLICATIONS_TRACKING, self.ROUTE_APPLICATION_TRACKING): "get_application_status",
            (RicoDomain.CAREER_STRATEGY, self.ROUTE_AI): "ai_career_planning",
            (RicoDomain.CV_PROFILE, self.ROUTE_AI): "ai_cv_assistance",
            (RicoDomain.FILE_UPLOAD, self.ROUTE_DETERMINISTIC): "handle_file_upload",
            (RicoDomain.SUPPORT_HELP, self.ROUTE_AI): "ai_help_response",
            (RicoDomain.LEGAL_POLICY, self.ROUTE_AI): "ai_legal_info",
            (RicoDomain.TELEGRAM_REQUEST, self.ROUTE_AI): "ai_telegram_setup",
            (RicoDomain.EMAIL_GMAIL_REQUEST, self.ROUTE_UNSUPPORTED): "unsupported_gmail_response",
            (RicoDomain.LINKEDIN_REQUEST, self.ROUTE_UNSUPPORTED): "unsupported_linkedin_response",
            (RicoDomain.CALENDAR_REQUEST, self.ROUTE_UNSUPPORTED): "unsupported_calendar_response",
            (RicoDomain.WHATSAPP_REQUEST, self.ROUTE_UNSUPPORTED): "unsupported_whatsapp_response",
        }
        
        return action_map.get((domain, route), "ai_fallback")
    
    def log_decision(self, user_id: str, message_preview: str, decision: PolicyDecision):
        """Log a policy decision safely without recording user message text."""
        message_hash = hashlib.sha256(message_preview.encode("utf-8")).hexdigest()[:12]
        log_data = {
            "user_id": user_id[:8] + "..." if len(user_id) > 8 else user_id,  # Partial ID
            "domain": decision.domain.value,
            "route": decision.route,
            "confidence": round(decision.confidence, 2),
            "action": decision.action,
            "reason": decision.reason,
            "language": decision.language,
            "tool_available": decision.tool_available,
            "needs_auth": decision.needs_auth,
            "message_hash": message_hash,
            "message_length": len(message_preview),
        }
        logger.info("policy_decision: %s", log_data)


# Global gateway instance
_gateway = PolicyGateway()


def classify_request(message: str, has_auth: bool = True) -> PolicyDecision:
    """Classify a user request and return policy decision.
    
    Main entry point for the policy gateway.
    """
    return _gateway.classify(message, has_auth)


def log_policy_decision(user_id: str, message_preview: str, decision: PolicyDecision):
    """Log a policy decision safely."""
    _gateway.log_decision(user_id, message_preview, decision)

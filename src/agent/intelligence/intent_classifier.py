"""src/agent/intelligence/intent_classifier.py

Unified intent classifier for Rico chat messages (Intent v2).

Classifies every user message into a canonical intent BEFORE any action is
taken.  Replaces the permissive short-text fallback that treated arbitrary
text as job titles.

Classification pipeline:
  1. Exact-phrase fast-path (zero cost, high confidence)
  2. Regex pattern matching (zero cost, medium confidence)
  3. Fallback to ``unknown`` — never to job search

Intent v2 Contract:
------------------
IntentResult shape:
  - intent: str (canonical dotted notation, e.g., "job_search.explicit_role")
  - subintent: Optional[str] (optional subintent for disambiguation)
  - confidence: float (0.0 to 1.0)
  - source: str ("exact", "regex", "fallback")
  - extracted_role: Optional[str] (legacy field for backward compatibility)
  - extracted_title: Optional[str] (legacy field for backward compatibility)
  - extracted_company: Optional[str] (legacy field for backward compatibility)
  - entities: dict (structured entity extraction)
    - role: str
    - job_title: str
    - company: str
    - location: str
    - application_status: str
    - plan: str
    - source: str
  - context_required: bool (whether this intent requires prior context)
  - context_type: Optional[str] (type of context required, e.g., "recent_job", "recent_application")
  - action: Optional[str] (action to perform, e.g., "search", "update", "show")
  - target_route: Optional[str] (frontend route to navigate to)

Intent groups (dotted notation):
  Job search:
    - job_search.explicit_role
    - job_search.profile_match
    - job_search.role_suggestions

  Job card actions:
    - job_action.prepare_application
    - job_action.open_apply_link
    - job_action.track_job
    - job_action.mark_applied
    - job_action.save_job
    - job_action.dismiss_job
    - job_action.explain_fit

  Application tracking:
    - application.show_flow
    - application.recent_context
    - application.mark_applied
    - application.manual_add
    - application.status_update

  Profile:
    - profile.upload_cv
    - profile.show
    - profile.update_target_roles
    - profile.update_salary
    - profile.update_location

  Subscription:
    - subscription.show_plans
    - subscription.checkout
    - subscription.portal
    - subscription.status

  Inbox import:
    - inbox_import.explain
    - inbox_import.connect
    - inbox_import.scan
    - inbox_import.coming_soon

  Career prep:
    - career_prep.interview
    - career_prep.application_angle
    - career_prep.cover_letter
    - career_prep.recruiter_message

Routing rules:
  - "open apply link for X at Y" and "Open apply link — X at Y" must be open_apply_link, not mark_applied.
  - "mark as applied — X at Y" must write/update Application Flow.
  - "where?" after tracking must route to application.recent_context.
  - "what about the job I just applied to?" must return the recent tracked application.
  - "save Environmental Manager as target role" must update target_roles.
  - "find live jobs for Environmental Compliance Officer" must search that exact role.
  - "upgrade to Pro" must route to subscription checkout/plans, not generic chat.
  - "why don't you have my past applications?" must explain Rico-tracked/manual/inbox import model.
  - "import applications from inbox" must show honest coming-soon/connect state depending on implementation.

Context memory requirements:
  After any job action, persist recent context:
    - recent_job
    - recent_application
    - recent_company
    - recent_job_title
    - recent_status
    - recent_route

  The next short follow-up must use this context:
    - where?
    - show it
    - what about it?
    - what about the job I just applied to?
    - open flow
    - show application

Safety rules:
  - Rico must not say an application is tracked unless DB write/update succeeded.
  - Rico must not silently apply to jobs.
  - Rico must not claim inbox import is live unless implemented.
  - Rico must not claim subscription is active unless backend confirms it.
  - Rico must not fall back to generic CV roles when explicit role exists.

Backward compatibility:
  - Legacy intent names are mapped via _LEGACY_INTENT_MAP in rico_chat_api.py
  - Existing handlers that expect old intent names still work via the mapping
  - Legacy fields (extracted_role, extracted_title, extracted_company) are preserved
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── Intent v2 backward compatibility mapping ────────────────────────────────

_LEGACY_INTENT_MAP = {
    # Job search
    "job_search.explicit_role": "job_search_explicit",
    "job_search.profile_match": "job_search_profile_match",
    "job_search.role_suggestions": "profile_role_suggestions",
    # Job actions
    "job_action.prepare_application": "prepare_application",
    "job_action.open_apply_link": "open_apply_link",
    "job_action.track_job": "track_job",
    "job_action.mark_applied": "mark_applied",
    "job_action.save_job": "save_job",
    "job_action.apply_job": "apply_job",
    "job_action.bulk_apply_unsafe": "bulk_apply_unsafe",
    "job_action.explain_fit": "explain_match",
    # Application tracking
    "application.show_flow": "application_tracking",
    "application.recent_context": "application_tracking",
    # Lifecycle funnel queries
    "lifecycle.show_saved": "lifecycle_show_saved",
    "lifecycle.show_applied": "lifecycle_show_applied",
    "lifecycle.show_opened_not_applied": "lifecycle_show_opened_not_applied",
    # Recent context follow-up (native legacy name, pass through)
    "recent_context": "recent_context",
    # Profile
    "profile.show": "profile_summary",
    "profile.update": "profile_update",
    "profile.update_target_roles": "save_target_role",
    "cv.create": "cv_create",
    "cv.generate": "cv_generate",
    # Career prep
    "career_prep.interview": "interview_prep",
    "career_prep.application_angle": "draft_message",
}


def _map_intent_to_legacy(intent: str) -> str:
    """Map Intent v2 dotted notation to legacy intent names for backward compatibility."""
    return _LEGACY_INTENT_MAP.get(intent, intent)


@dataclass(frozen=True)
class IntentResult:
    """Result of intent classification (v2 with entities and context)."""
    intent: str  # Canonical intent name (e.g., "job_search.explicit_role")
    confidence: float = 1.0
    source: str = "exact"  # "exact", "regex", "fallback"
    subintent: Optional[str] = None  # Optional subintent for disambiguation
    # Legacy fields for backward compatibility
    extracted_role: Optional[str] = None
    extracted_title: Optional[str] = None
    extracted_company: Optional[str] = None
    legacy_intent: Optional[str] = None  # Mapped legacy intent name for existing handlers
    # v2 entities
    entities: dict = None  # Structured entity extraction
    context_required: bool = False  # Whether this intent requires prior context
    context_type: Optional[str] = None  # Type of context required (e.g., "recent_job", "recent_application")
    action: Optional[str] = None  # Action to perform (e.g., "search", "update", "show")
    target_route: Optional[str] = None  # Frontend route to navigate to

    def __post_init__(self):
        if self.entities is None:
            object.__setattr__(self, "entities", {})
        if self.legacy_intent is None:
            object.__setattr__(self, "legacy_intent", _LEGACY_INTENT_MAP.get(self.intent, self.intent))


# ── Exact-phrase sets ────────────────────────────────────────────────────────

_PROFILE_MATCH_PHRASES = frozenset([
    "find me one that matches",
    "match my cv",
    "use my cv",
    "show matching jobs",
    "what can i apply for",
    "find me a match",
    "find matching jobs",
    "jobs for my profile",
    "jobs matching my cv",
    "what suits me",
    "what fits my profile",
    "use my profile",
    "based on my cv",
    "based on my profile",
    "jobs for me",
])

_RECENT_CONTEXT_PHRASES = frozenset([
    "where",
    "where?",
    "where can i see it",
    "where is it",
    "show it",
    "what about the job i just applied to",
    "what about the job i just applied to?",
    "what about the job i just tracked",
])

_APPLICATION_TRACKING_PHRASES = frozenset([
    "show my tracked applications",
    "show my applications",
    "application status",
    "applications status",
    "tracked applications",
    "my applications",
    "show applications",
    "show applied jobs",
    "applied jobs",
    "show my applied jobs",
    "show interviews",
    "interview status",
    "my interviews",
    "show offers",
    "show rejections",
    "follow up",
    "remind me to follow up",
    "open application flow",
    "open applications",
    # Natural-language application history queries
    "what job i applied for",
    "what jobs i applied for",
    "what have i applied for",
    "what did i apply for",
    "jobs i applied to",
    "jobs i applied for",
    "which jobs did i apply for",
    "which jobs have i applied to",
    # Colloquial affirmative + check (e.g. reply to "would you like me to check?")
    "ya check",
    "yes check",
    "yeah check",
    "ya please check",
    "yes please check",
    # ── User-ownership commands ───────────────────────────────────────────────
    # These phrases use ownership language ("my") and must always route to
    # application tracking, never to job-role extraction or search.
    "show my job applications",
    "show my job applications and their status",
    "list my job applications",
    "my job applications",
    "my jobs",
    "show my jobs",
    "list my jobs",
    "my pipeline",
    "show my pipeline",
    "application pipeline",
    "how many applied jobs do i have",
    "how many applications do i have",
    "applications this month",
])

_LIFECYCLE_SAVED_PHRASES = frozenset([
    "show saved jobs", "show my saved jobs", "my saved jobs", "saved jobs",
    "jobs i saved", "which jobs did i save", "list saved jobs",
    "اعرض الوظائف المحفوظة", "وظائفي المحفوظة",
])

_LIFECYCLE_APPLIED_PHRASES = frozenset([
    "show applied jobs", "show my applied jobs", "jobs i applied to",
    "jobs i applied for", "what jobs did i apply to", "what did i apply to",
    "which jobs did i apply to", "my applied jobs",
    "الوظائف التي تقدمت لها", "ما الوظائف التي تقدمت لها",
])

_LIFECYCLE_OPENED_NOT_APPLIED_PHRASES = frozenset([
    "show jobs i opened but did not apply to",
    "show jobs i opened but didn't apply to",
    "jobs i opened but didn't apply",
    "opened but not applied",
    "jobs i clicked but didn't apply",
    "jobs i opened without applying",
])

_LIFECYCLE_SAVED_RE = re.compile(
    r"\b(show|list|view|see|get)\b.{0,20}\bsaved\b.{0,15}\bjobs?\b"
    r"|\bsaved\b.{0,15}\bjobs?\b.{0,10}\b(show|list|view|see)\b"
    r"|\bmy\s+saved\s+jobs?\b",
    re.IGNORECASE,
)

_LIFECYCLE_APPLIED_RE = re.compile(
    r"\bjobs?\b.{0,20}\b(applied|apply)\b"
    r"|\b(applied|apply)\b.{0,10}\bto\b"
    r"|\bwhat.{0,10}\b(applied|apply)\b",
    re.IGNORECASE,
)

_LIFECYCLE_OPENED_NOT_APPLIED_RE = re.compile(
    r"\bopened?\b.{0,30}\b(not|didn.t|did\s+not)\s+appl",
    re.IGNORECASE,
)

_HELP_PHRASES = frozenset([
    "help", "menu", "options", "what can you do", "commands",
    "start", "get started", "what's next", "whats next", "what next",
    "what now", "show options", "show menu", "next steps",
    # Natural variants asking Rico to describe its capabilities
    "what can you do for me", "what can you help me with",
    "what do you do", "how can you help", "how can you help me",
    "what can rico do", "what can rico do for me",
    # Arabic "what now / what's the solution"
    "مالحل", "ما الحل", "مالحل الان", "مالحل الآن",
])

# Acknowledgement phrases — short positive/neutral replies mid-conversation.
# These do NOT trigger the cold-start greeting; they get a brief warm response.
_ACKNOWLEDGEMENT_PHRASES = frozenset([
    "thanks", "thank you", "thank you so much", "thanks a lot", "thank you very much",
    "ok", "okay", "ok thanks", "ok thank you", "okay thanks", "okay thank you",
    "great", "perfect", "nice", "cool", "awesome", "excellent", "wonderful",
    "got it", "understood", "noted", "sounds good", "looks good", "makes sense",
    "cheers", "much appreciated", "appreciate it", "appreciate that",
    "no problem", "np", "nvm", "never mind",
    # Arabic acknowledgement equivalents
    "شكرا", "شكراً", "شكرا جزيلا", "شكراً جزيلاً", "ممتاز", "رائع",
    "فهمت", "تمام", "ماشي", "حسنا", "تمام شكرا", "شكرا تمام",
])

_SMALLTALK_PHRASES = frozenset([
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "bye", "goodbye", "see you",
    "hallo", "hola", "hi there", "salam", "marhaba", "ahlan",
    # Arabic greetings (normalised: alef variants, ta marbuta)
    "مرحبا", "اهلا", "اهلا وسهلا", "السلام عليكم", "مع السلامه",
])

_PROFILE_SUMMARY_PHRASES = frozenset([
    "show my profile", "my profile", "profile summary",
    "what do you know about me", "my details",
    # CV / resume show commands — "my cv" means "show me my uploaded CV / profile"
    "my cv", "show my cv", "view my cv", "see my cv",
    "my resume", "show my resume", "view my resume",
    # Arabic profile identity
    "ما هو اسمي", "ما اسمي", "اسمي", "من انا", "ما هو ملفي",
])

# ── Learning profile summary phrases ─────────────────────────────────────────
# User wants to see what Rico has learned from their behavior.

_LEARNING_SUMMARY_PHRASES = frozenset([
    # English
    "what have you learned about me", "what did you learn about me",
    "what do you know about my preferences", "my preferences",
    "what have i taught you", "what did i teach you",
    "what do you know about what i like", "show my preferences",
    "what have you learned", "show what you learned",
    "what are my preferences", "my learned preferences",
    "what roles do i prefer", "what locations do i prefer",
    "show my learning profile", "my behavior profile",
    "what have you figured out about me",
    # Arabic (normalised)
    "ماذا تعلمت عني", "ما الذي تعلمته عني", "ما تعلمته عني",
    "ما تفضيلاتي", "تفضيلاتي", "ماذا تعرف عن تفضيلاتي",
    "ماذا تعلمت", "ارني ما تعلمته",
])

_LEARNING_SUMMARY_RE = re.compile(
    r"\b(what.{0,10}(learned|know|figured).{0,20}(about me|my preferences|what i like))\b"
    r"|\b(show|display|list).{0,15}(my\s+)?(learned|behavioral|behaviour)\s+(preferences|profile)\b"
    r"|\b(my\s+)?(learned\s+preferences|preference\s+profile|learning\s+profile)\b",
    re.IGNORECASE,
)

# ── Preference correction phrases ─────────────────────────────────────────
# User wants to remove / veto a learned preference.

_PREF_CORRECTION_PHRASES = frozenset([
    # English
    "forget my preference", "remove my preference", "clear my preference",
    "forget that preference", "remove that preference",
    "don't show me jobs in", "don't want jobs in", "not interested in jobs in",
    "remove from my preferences", "clear from my preferences",
    "i changed my mind about", "i don't like that role", "i don't want that role",
    "remove this preference", "delete this preference",
    # Arabic
    "انسَ تفضيلي", "احذف تفضيلي", "لا أريد وظائف في",
    "غيّرت رأيي", "لا أريد هذا التفضيل", "احذف هذا",
])

_PREF_CORRECTION_RE = re.compile(
    r"\b(forget|remove|clear|delete|drop).{0,10}(my\s+)?(preference|skill|role|location)\b"
    r"|\bdon.t\s+(want|show\s+me).{0,10}(jobs|roles).{0,10}\b(in|for|at)\b"
    r"|\b(i\s+)?(changed\s+my\s+mind|no\s+longer\s+want).{0,30}\b",
    re.IGNORECASE,
)

# ── Application insights phrases ─────────────────────────────────────────
# User wants to see their application success stats / patterns.

_APP_INSIGHTS_PHRASES = frozenset([
    # English
    "analyze my applications", "analyse my applications",
    "application insights", "my application stats", "application statistics",
    "how are my applications doing", "application success rate",
    "my success rate", "how many interviews did i get",
    "employer response patterns", "response patterns",
    "how long do employers take", "follow up on my applications",
    "application analysis", "how well am i doing",
    "show my application performance", "application performance",
    # Arabic
    "حلل طلباتي", "إحصائيات طلباتي", "كيف أداؤي في التقديمات",
    "معدل نجاحي", "كم مقابلة حصلت عليها", "تحليل طلباتي",
])

_APP_INSIGHTS_RE = re.compile(
    r"\b(analyz|analys|review).{0,15}(my\s+)?applications?\b"
    r"|\bapplication\s+(stats|statistics|insights|analysis|performance|success)\b"
    r"|\b(success|response|interview)\s+rate\b"
    r"|\bhow\s+(well|good|many).{0,20}(applications?|interviews?|responses?)\b",
    re.IGNORECASE,
)

_SALARY_ENQUIRY_RE = re.compile(
    r"\b(what|how\s+much|what'?s?).{0,30}(salary|salaries|pay|compensation|package|ctc|earnings?)\b"
    r"|\b(salary|pay|compensation)\s+(range|expectation|benchmark|market|typical|average|expected)\b"
    r"|\b(expect(ed)?|typical|average|market).{0,30}(salary|pay|compensation)\b"
    r"|\bhow\s+much.{0,40}\b(earn|make|get\s+paid)\b"
    r"|\bwhat.{0,50}(earn|make|get\s+paid)\b"
    r"|\bhow\s+(much|well)\s+(is|are).{0,40}(paid|compensated|earning)\b",
    re.IGNORECASE,
)

_CV_ANALYSIS_RE = re.compile(
    r"\b(weak|weakness|weaker|gap|gaps|lacking|missing|improve|improvement|deficiency)\b"
    r".{0,30}\b(cv|resume|profile|application)\b"
    r"|\b(cv|resume|profile|application)\b.{0,30}"
    r"\b(weak|weakness|gap|gaps|lacking|missing|improv|deficien)\b"
    r"|\bwhat.{0,20}wrong\b.{0,20}\b(cv|resume|profile)\b"
    r"|\bstrengthen.{0,20}\b(cv|resume|profile)\b"
    r"|\breview\s+my\s+(cv|resume)\b"
    r"|\b(cv|resume)\s+review\b",
    re.IGNORECASE,
)

_PROFILE_ROLE_SUGGESTIONS_PHRASES = frozenset([
    "show roles from my cv",
    "what roles fit my cv",
    "roles from my cv",
    "suggest roles from my cv",
    "best roles for my profile",
    "what jobs match my cv",
    "what roles match my profile",
    "suggest roles for me",
    "role suggestions",
    "what roles should i apply for",
])

_SKIP_PHRASES = frozenset([
    "skip this question", "don't know", "do not know", "skip",
    "not sure", "pass", "next question",
])

_PROFILE_UPDATE_PHRASES = frozenset([
    "update my name", "update my skills", "change my", "edit my profile",
    "update my phone", "update my salary", "update my city", "update my role",
    "update my profile", "update profile", "edit profile", "update my details",
    "update my information", "update my info", "update my cv", "update my experience",
    "تحديث ملفي", "تعديل ملفي", "تحديث البيانات",
])

# ── Subscription / pricing phrases ─────────────────────────────────────────

_SUBSCRIPTION_PHRASES = frozenset([
    # English — exact / short phrases
    "show plans", "subscription plans", "pricing", "how much does it cost",
    "what is the price", "what's the price", "upgrade plan", "current plan",
    "my subscription", "subscription status", "billing",
    # Purchase / sign-up intent (the phrases that caused the production crash)
    "how can i subscribe", "how do i subscribe", "how to subscribe",
    "i want to subscribe", "i want to buy", "how to buy",
    "subscribe today", "how can subscribe today",
    "buy subscription", "purchase subscription",
    "buy a subscription", "purchase a plan",
    "how much is it", "how much is the subscription",
    "i want to upgrade", "how to upgrade",
    # Arabic (normalised forms) — exact short phrases
    "كم الاسعار", "كيف اشترك", "كيف يمكنني الاشتراك",
    "اشتراكي", "باقتي", "الاسعار", "السعر", "خطه الاشتراك",
    "ابي اشترك", "كيف اشتري", "ابي اشتري", "كم السعر",
    "اريد الاشتراك", "اريد ان اشترك",
    "الباقة", "باقتك", "باقة", "الاشتراك", "خطتي",
    "كم الاشتراك", "سعر الاشتراك", "مجاني", "مدفوع",
    "خطة الاشتراك", "باقة برو", "باقة بريميوم",
])

_FOLLOW_UP_CONFIRMATION_PHRASES = frozenset([
    "both please", "both", "all", "keep all", "keep them all", "yes keep all",
    "continue", "ok continue", "okay continue", "yes continue",
    "yes", "confirm", "confirmed", "proceed", "go ahead",
    # Arabic confirmations / follow-up affirmatives (normalised forms)
    "تمام", "اوكي", "نعم", "اي", "موافق", "كمل", "استمر", "حسنا", "طيب",
])

# ── Regex patterns ───────────────────────────────────────────────────────────

_ROLE_CHANGE_RE = re.compile(
    r"\b(what about|switch to|change to|try|how about|search for|look for|find)\s+(.+)",
    re.IGNORECASE,
)

# UAE city name extraction — used to populate entities["location"] in search intents.
_UAE_CITY_EXTRACT_RE = re.compile(
    r"\b(dubai|abu\s+dhabi|sharjah|ajman|ras\s+al\s+khaimah|fujairah|al\s+ain|umm\s+al\s+quwain|uae)\b",
    re.IGNORECASE,
)

# Employment-type extraction — used to populate entities["employment_type"].
_EMPLOYMENT_TYPE_EXTRACT_RE = re.compile(
    r"\b(permanent|full[- ]?time|part[- ]?time|contract(?:or)?|freelance|remote|hybrid|on[- ]?site)\b",
    re.IGNORECASE,
)

# Source-filter intent: exclude/include specific job board by name.
# Must be checked BEFORE _JOB_SEARCH_EXPLICIT_RE so "exclude LinkedIn results"
# is not treated as a role-extraction query.
_SOURCE_FILTER_RE = re.compile(
    r"\b(exclude|filter\s+out|don'?t\s+show|hide|remove|without|no\s+more)\b"
    r".{0,40}\b(linkedin|naukri|bayt|indeed|glassdoor|monster|ziprecruiter|results?|listings?)\b"
    r"|\b(only\s+from|only\s+show\s+from|show\s+only\s+from|just\s+(?:show|from))\b"
    r".{0,30}\b(linkedin|naukri|bayt|indeed|glassdoor)\b"
    r"|\b(exclude|filter)\s+(linkedin|naukri|bayt|indeed|glassdoor)\b",
    re.IGNORECASE,
)

# Compound search-refinement: employment-type negation or location-only constraint
# without an explicit role name.  "show me only jobs in Dubai, no contract roles"
# fires this before _JOB_SEARCH_EXPLICIT_RE can misclassify "only" or "contract"
# as a role to search for.
_SEARCH_REFINE_RE = re.compile(
    r"\bno\s+(contract|temp|temporary|freelance|part.time)\b"
    r"|\bnot\s+contract(ing)?\b"
    r"|\b(permanent|full.time|full\s+time)\s+only\b"
    r"|\bonly\s+(permanent|full.time|full\s+time|on.site|onsite|remote|hybrid)\b"
    r"|\bonly\s+(?:in\s+)?(dubai|abu\s+dhabi|sharjah|ajman|ras\s+al\s+khaimah|fujairah|al\s+ain|umm\s+al\s+quwain|uae)\b"
    r"|\b(dubai|abu\s+dhabi|sharjah|ajman|uae)\s+only\b",
    re.IGNORECASE,
)

_JOB_SEARCH_EXPLICIT_RE = re.compile(
    r"\b(find|search|show|get|look for|looking for|any|need|want)\b.{0,60}"
    r"\b(jobs?|roles?|positions?|vacancy|vacancies|openings?|work)\b"
    r"|^(any\s+)?(jobs?|roles?|positions?|openings?|vacancies?)\s*(please|for me|available)?\s*\??$",
    re.IGNORECASE,
)

_CV_UPLOAD_RE = re.compile(
    r"\b[\w .()_-]+\.(?:pdf|docx?|txt)\b"
    r"|uploaded?\s+(?:my\s+)?(?:cv|resume)"
    r"|(?:cv|resume)\s+(?:attached|uploaded|here)"
    r"|here(?:'s| is) my (?:cv|resume)",
    re.IGNORECASE,
)

# Phrases that signal the user wants to CREATE a CV (no existing one)
_CV_CREATE_RE = re.compile(
    r"\b(create|make|build|draft|write|generate)\b.{0,30}\b(cv|resume|cv for me|resume for me)\b"
    r"|\b(no\s+cv|no\s+resume|don't\s+have\s+a\s+cv|dont\s+have\s+a\s+cv)\b"
    r"|\b(create\s+cv|make\s+me\s+a\s+cv|create\s+resume|make\s+me\s+a\s+resume)\b"
    r"|لا\s+يوجد\s+لدي\s+سير[هة]\s+ذاتي[هة]"
    r"|انشاء\s+سير[هة]\s+ذاتي[هة]"
    r"|اصنع\s+لي\s+سير[هة]\s+ذاتي[هة]",
    re.IGNORECASE | re.UNICODE,
)

# Phrases that signal the user wants to GENERATE / REWRITE their existing CV
# (colloquial Arabic + English "rewrite / refresh / update my CV")
_CV_GENERATE_RE = re.compile(
    # English: rewrite / redo / refresh / update / remake my CV/resume
    r"\b(rewrite|redo|refresh|remake|regenerate|update|revamp|improve|fix)\b.{0,30}\b(my\s+)?(cv|resume)\b"
    r"|\b(new\s+(cv|resume)|cv\s+again|resume\s+again)\b"
    # Arabic colloquial imperative forms for "make me" / "write me" + CV
    # اعملي / اعمل لي / اكتبلي / اكتب لي / اعدلي / جدد / حدث / اعيد
    r"|اعمل[يل][يي]?\s*(?:لي\s+)?(?:سير[هة]\s+ذاتي[هة]|cv|سي\s*في|سيفي)"
    r"|اعمل\s+لي\s+(?:سير[هة]\s+ذاتي[هة]|cv|سي\s*في|سيفي)"
    r"|اكتب[لي]{0,2}\s*(?:لي\s+)?(?:سير[هة]\s+ذاتي[هة]|cv|سي\s*في|سيفي)"
    r"|اكتب\s+لي\s+(?:سير[هة]\s+ذاتي[هة]|cv|سي\s*في|سيفي)"
    r"|(?:جدد|حدث|اعيد|اعد)\s*(?:ال)?(?:سير[هة]\s+الذاتي[هة]|cv|سي\s*في|سيفي)"
    r"|(?:سير[هة]\s+ذاتي[هة]|cv|سي\s*في|سيفي)\s+جديد[هة]?"
    r"|اريد\s+(?:سير[هة]\s+ذاتي[هة]|cv|سي\s*في|سيفي)\s+جديد[هة]?"
    r"|(?:عمل|كتابة|تحديث|تجديد)\s+(?:ال)?(?:سير[هة]\s+الذاتي[هة]|cv|سي\s*في)",
    re.IGNORECASE | re.UNICODE,
)

_PROFILE_UPDATE_RE = re.compile(
    r"\b(update|change|set|modify|adjust)\b.{0,40}"
    r"\b(salary|city|location|preference|role|title|industry|experience|notice|email|phone|telegram)\b"
    # Declarative city statements: "My favorite city is Dubai", "I live in Dubai"
    r"|\bmy\s+(?:favorite|preferred|home|base|target)?\s*city\s+is\b"
    r"|\bi\s+(?:live|work|am\s+based|reside)\s+in\b",
    re.IGNORECASE,
)

_SUBSCRIPTION_RE = re.compile(
    r"\b(price|pricing|plan|plans|subscription|subscribe|upgrade|cancel|billing|cost|payment)"
    r"\b.{0,40}\b(plan|subscription|price|cost|billing|payment|package|tier)\b"
    r"|\b(how much|what is the cost|what's the cost|monthly|annual|yearly)\b"
    r"|\b(pro|premium|basic|free)\b.{0,20}\b(plan|tier|package|subscription)\b"
    r"|\b(subscribe|sign up|upgrade|downgrade|renew|cancel)\b.{0,20}\b(plan|subscription|membership)\b"
    r"|\b(subscription|plan)\b.{0,20}\b(status|details|info|information)\b"
    # Catch "how can I subscribe", "I want to buy/subscribe", "buy a plan" etc.
    r"|\b(how\s+(can|do|to|could)\s+(i\s+)?subscribe)\b"
    r"|\b(i\s+want\s+to\s+(subscribe|buy|purchase|upgrade))\b"
    r"|\b(buy|purchase)\b.{0,20}\b(subscription|plan|access|package)\b"
    # Arabic contextual patterns — catches "ماهي باقتي اذا؟", "شو باقتي", "وين اشوف باقتي" etc.
    r"|(باقت[يكه]|اشتراك[يكه]|خطت[يكه])"  # possessive subscription nouns (my/your/his plan)
    r"|(كم\s+(سعر|تكلفة|ثمن|يكلف))"  # "how much does it cost" in Arabic
    r"|(هل\s+(هو|هناك|في|توجد)\s+(نسخة|نسخ|باقة|خطة)\s+(مجانية|مدفوعة|بريميوم|برو))"
    r"|(اشترك|اشتركت|اشتري|اشتريت|اتحقق|احقق).{0,25}(باقة|خطة|اشتراك)"
    r"|(باقة|خطة|اشتراك).{0,25}(مجاني|مدفوع|شهري|سنوي|بريميوم|برو|اساسي)",
    re.IGNORECASE | re.UNICODE,
)

_DELEGATED_DECISION_RE = re.compile(
    r"\b(do as you wish|do as u wish|you decide|choose for me|recommend and proceed|"
    r"pick for me|select for me|whatever you think|i trust you|you choose|"
    r"انت قرر|اختار لي|شوف الأنسب|الي تشوفه|الي تختاره|اختار الافضل)\b",
    re.IGNORECASE,
)

_APPLICATION_TRACKING_RE = re.compile(
    r"\b(tracked?|applied|application|applications|interviews?|offers?|rejected|status)\b",
    re.IGNORECASE,
)

# Guard: ownership phrases that must never fall through to job-role search.
# Catches "show my job applications and their status", "my jobs", "show my pipeline"
# before _JOB_SEARCH_EXPLICIT_RE can treat "show" + "job" as role extraction.
# Applied against the normalised lowercase form of the input.
_MY_OWNERSHIP_CMD_RE = re.compile(
    r"\bmy\s+job\s+applications?\b"
    r"|\bhow\s+many\s+(?:applied\s+)?jobs?\s+(?:do\s+)?i\s+have\b"
    r"|\bmy\s+jobs?\s*$"
    r"|\b(?:show|view|list|check|display|see)\s+my\s+jobs?\s*$"
    r"|\bmy\s+(?:application\s+)?pipeline\b",
    re.IGNORECASE,
)

_SAVE_TARGET_ROLE_RE = re.compile(
    r"\b(?:save|set|add|use)\s+(.+?)\s+as\s+(?:my\s+)?target\s+role\b",
    re.IGNORECASE,
)

_SAVE_JOB_RE = re.compile(
    r"\b(save|bookmark|keep|shortlist)\b.{0,30}\b(job|this|it|one|role)\b",
    re.IGNORECASE,
)

# "save it/Dubai to my profile/preferences/account" must route to profile_update,
# not save_job. Checked BEFORE _SAVE_JOB_RE so these never reach the job-save path.
_SAVE_TO_PROFILE_RE = re.compile(
    r"\bsave\b.{0,80}\bto\s+my\s+(?:profile|preferences?|settings?|account)\b"
    r"|\bsave\b.{0,60}\bas\s+my\s+preferred\b"
    r"|احفظ\S*.{0,60}(?:في\s+ملف(?:ي|ه|ك)|في\s+تفضيلات(?:ي|ك)|في\s+حساب(?:ي|ك))"
    r"|(?:خزّن|خزن|اضف|أضف)\S*.{0,60}(?:في\s+ملف(?:ي|ه|ك)|في\s+تفضيلات(?:ي|ك)|في\s+حساب(?:ي|ك))",
    re.IGNORECASE | re.UNICODE,
)

# Ordinal save: "save the first/second/Nth/last job to my pipeline". Emits
# save_job with an ordinal entity so the handler resolves the job from the recent
# search results — mirrors the ordinal open-apply-link path.
_SAVE_JOB_ORDINAL_RE = re.compile(
    r"\b(?:save|bookmark|keep|shortlist|add)\b\s+(?:the\s+)?"
    r"(?:"
    # "save job 2" / "save job number 2" / "save job #2"  (noun before number)
    r"job\s+(?:number\s+|#)?(?P<ord_after>\d{1,2})"
    r"|"
    # "save the second job" / "save the 2nd one"  (ordinal before noun)
    r"(?P<ord>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d{1,2})"
    r"(?:st|nd|rd|th)?\s*(?:job|role|position|result|listing|one)"
    r")\b",
    re.IGNORECASE,
)

# Arabic ordinal save: "احفظ أول وظيفة" / "احفظ ثاني وظيفة بالبايبلاين".
# Verb (احفظ/خزن/اضف) + Arabic ordinal token (around the job noun وظيفة).
_SAVE_JOB_ORDINAL_AR_RE = re.compile(
    r"(?:احفظ|احفظي|خزن|خزّن|اضف|أضف|ضيف)\b[^\n]{0,20}?"
    r"(?P<aord>اول|أول|الاولى|الأولى|الاولي|ثاني|ثانيه|ثانية|الثاني|الثانيه|الثانية|"
    r"ثالث|ثالثه|ثالثة|الثالثة|رابع|رابعة|خامس|خامسة|اخر|آخر|الاخير|الأخير|الاخيره|الأخيرة)",
    re.UNICODE,
)

_ARABIC_ORDINAL_TO_INT = {
    "اول": 1, "أول": 1, "الاولى": 1, "الأولى": 1, "الاولي": 1,
    "ثاني": 2, "ثانيه": 2, "ثانية": 2, "الثاني": 2, "الثانيه": 2, "الثانية": 2,
    "ثالث": 3, "ثالثه": 3, "ثالثة": 3, "الثالثة": 3,
    "رابع": 4, "رابعة": 4, "خامس": 5, "خامسة": 5,
    "اخر": -1, "آخر": -1, "الاخير": -1, "الأخير": -1, "الاخيره": -1, "الأخيرة": -1,
}

# Extracts explicit role name from "find/search … jobs for <role>" patterns.
# Checked alongside _JOB_SEARCH_EXPLICIT_RE to attach extracted_role.
_JOB_SEARCH_FOR_ROLE_RE = re.compile(
    r"\b(?:find|search|show|get|look(?:ing)?\s+for|need|want)\b.{0,40}\b(?:jobs?|roles?|positions?|openings?|vacancies?)\b"
    r"\s+for\s+([A-Za-z][A-Za-z &/\-]{2,60}?)(?:\s+in\b|[?.!,\s]*$)",
    re.IGNORECASE,
)

# Extracts a role that sits immediately BEFORE the job noun — the natural word order
# users type: "operations manager jobs in ajman", "find HSE manager roles",
# "any nursing positions". _JOB_SEARCH_FOR_ROLE_RE only handles the "jobs for <role>"
# order, so this is tried as a fallback. Leading command/filler words are stripped
# afterwards (see _extract_role_before_noun) so the capture yields just the role phrase.
_JOB_SEARCH_ROLE_BEFORE_NOUN_RE = re.compile(
    r"([A-Za-z][A-Za-z '&/\-]{1,60}?)\s+(?:jobs?|roles?|positions?|openings?|vacancies?)\b",
    re.IGNORECASE,
)

# Command / filler tokens dropped from the front of a "<...> jobs" capture so that
# "find operations manager jobs" -> "operations manager" (not "find operations manager")
# and pure-filler leads like "am looking for job" reduce to nothing (-> profile fallback).
_ROLE_PREFIX_STOPWORDS = frozenset({
    # command verbs
    "find", "search", "searching", "show", "get", "look", "looking", "seeking",
    "want", "need", "give", "list", "browse",
    # filler / connectors / articles / pronouns
    "for", "me", "some", "any", "all", "live", "new", "latest", "available",
    "more", "the", "a", "an", "please", "kindly", "i", "i'm", "im", "we",
    "am", "are", "is", "was", "were", "to", "of", "currently", "interested",
    "really", "just", "good", "great", "now", "today",
    # filter/constraint words — must not be extracted as role names
    "only", "filter", "exclude", "include", "no", "not", "without", "remove",
})

# ── Multi-role search-list parsing ────────────────────────────────────────────
# Users routinely request several target roles in one message:
#   "Search for Technical Product Owner, Product Owner, Technical Project Manager
#    and Operations Technology Manager roles in UAE. Do not search Software
#    Engineer, Backend, Golang or Machine Learning roles unless I ask for coding."
# The single-role extractors above treat the whole comma list as one unknown
# role, so the chat layer replied "I do not recognize '<the whole list>' as a job
# role". extract_role_list() splits the list into individual target roles and a
# trailing negative-constraint ("do not search …") clause of excluded roles.

# Leading search verb removed from the positive segment ("Search for A, B …").
_MULTI_ROLE_LEAD_RE = re.compile(
    r"^\s*(?:please\s+)?(?:search|searching|look|looking|find|finding|show|get|"
    r"fetch|give|list|browse)\w*(?:\s+(?:me|for|up))*\s+",
    re.IGNORECASE,
)

# Strips a leading "<≤3 filler words> jobs/roles for " introduction left after the
# search verb, so "search UAE jobs for HSE Manager and QHSE Manager" parses the
# list as [HSE Manager, QHSE Manager] instead of dropping the first item (whose
# "jobs for" prefix would otherwise be rejected by the non-role-word guard).
_MULTI_ROLE_JOBS_FOR_RE = re.compile(
    r"^\s*(?:\w+\s+){0,3}?(?:jobs?|roles?|positions?|openings?|vacancies?)\s+for\s+",
    re.IGNORECASE,
)

# Trailing politeness / urgency qualifiers that are not part of a role title:
# "Technical Product Owner only" -> "Technical Product Owner".
_ROLE_TRAILING_QUALIFIERS = frozenset({
    "only", "please", "pls", "plz", "now", "today", "asap", "thanks", "thx",
    "here", "kindly", "urgently", "urgent", "immediately", "soon",
})


def _strip_role_qualifiers(role: Optional[str]) -> Optional[str]:
    """Drop trailing politeness/urgency qualifier words from an extracted role."""
    if not role:
        return role
    words = role.strip().split()
    while words and words[-1].lower().strip(".,!?") in _ROLE_TRAILING_QUALIFIERS:
        words.pop()
    return " ".join(words) if words else role


# Descriptive category → concrete allowed roles (T6). Keeps Rico on safe
# product/management titles instead of guessing literal words like "product".
_CATEGORY_PRODUCT_TECH_MGMT_ROLES = [
    "Technical Product Owner", "Product Owner", "Technical Project Manager",
    "Digital Transformation Manager", "Operations Technology Manager",
]
_CATEGORY_RE = re.compile(
    r"\bproduct\s*(?:and|&|/|\+)\s*technical\s+management\b"
    r"|\btechnical\s*(?:and|&|/|\+)\s*product\s+management\b",
    re.IGNORECASE,
)
# "not coding jobs" exclusion shorthand → concrete engineering roles to exclude.
_CODING_EXCLUSION_ROLES = [
    "Software Engineer", "Full Stack", "Backend", "Golang", "Machine Learning",
]
_NOT_CODING_RE = re.compile(
    r"\b(?:not|no|without|avoid|exclude|skip|except)\s+coding\b|\bnon[- ]?coding\b",
    re.IGNORECASE,
)
# Reference to the user's CV / profile as the search basis (T5).
_CV_PROFILE_REF_RE = re.compile(
    r"\b(?:my\s+cv|my\s+resume|my\s+profile|based\s+on\s+my|match(?:es|ing)?\s+my|"
    r"from\s+my\s+(?:cv|resume|profile)|for\s+me)\b",
    re.IGNORECASE,
)

# Opener of the negative-constraint clause — everything after it is an EXCLUSION
# list. Kept narrow so ordinary prose ("not sure", "no thanks") never trips it.
_EXCLUSION_OPENER_RE = re.compile(
    r"\b(?:do\s*n['’]?t|do\s+not|never|please\s+do\s+not|please\s+do\s*n['’]?t)\s+"
    r"(?:search|include|show|fetch|return|look\s+for|want|consider|send|pull)\b"
    r"|\b(?:excluding|exclude|avoid|skip)\b",
    re.IGNORECASE,
)

# Subordinate clause that qualifies (but is not part of) a role list — dropped
# before splitting, e.g. "… roles unless I explicitly ask for coding jobs".
_ROLE_LIST_TAIL_CLAUSE_RE = re.compile(
    r"\b(?:unless|except|if|when|whenever|because|since|but|while|so\s+that)\b",
    re.IGNORECASE,
)

# Trailing job-noun / location qualifier stripped from a captured role token:
#   "Operations Technology Manager roles in UAE" -> "Operations Technology Manager"
_ROLE_TOKEN_TAIL_RE = re.compile(
    r"\s*\b(?:jobs?|roles?|positions?|openings?|vacancies?|work)?\b"
    r"\s*\bin\s+[A-Za-z'’ .\-]+$"
    r"|\s*\b(?:jobs?|roles?|positions?|openings?|vacancies?|work)\s*$",
    re.IGNORECASE,
)

# Connectors a role list is split on: commas, semicolons, slashes, ampersands,
# and the words "and" / "or".
_ROLE_LIST_SPLIT_RE = re.compile(r"\s*(?:,|;|/|&|\band\b|\bor\b|\bplus\b)\s*", re.IGNORECASE)

# Leading filler dropped from a single role token. Reuses the role-prefix
# stopwords plus list-specific qualifiers ("pure Software Engineer" -> "Software
# Engineer").
_ROLE_TOKEN_LEAD_STOPWORDS = _ROLE_PREFIX_STOPWORDS | frozenset({
    "pure", "purely", "strictly", "such", "as", "like", "also", "plus",
})

_ROLE_TOKEN_TRAILING_NOUNS = frozenset({
    "jobs", "job", "roles", "role", "positions", "position",
    "openings", "opening", "vacancies", "vacancy", "work",
})

# English location words — a token made up entirely of these is a place, not a role.
_ENGLISH_LOCATION_WORDS = frozenset({
    "uae", "u.a.e", "dubai", "abu", "dhabi", "sharjah", "ajman", "ras",
    "al", "khaimah", "fujairah", "ain", "umm", "quwain", "emirates",
    "united", "arab", "gulf", "gcc",
})

# Words that never appear inside a real role title — their presence means the
# captured token is prose, not a role (e.g. "UAE jobs that match my CV"). Used to
# reject false-positive list items so the multi-role path only fires on genuine
# role lists. Job nouns are included because a real title never carries them once
# the trailing qualifier has been stripped.
_NON_ROLE_WORDS = frozenset({
    "that", "which", "match", "matches", "matching", "suit", "suits", "fit",
    "fits", "based", "my", "me", "mine", "our", "your", "their", "his", "her",
    "i", "we", "you", "they", "cv", "resume", "profile", "experience",
    "please", "kindly", "best", "with", "apply", "applying",
    "jobs", "job", "roles", "role", "positions", "position", "openings",
    "opening", "vacancies", "vacancy", "work", "anything", "something",
})


def _clean_role_token(token: str) -> Optional[str]:
    """Normalise one role-list item to a bare role title, or None if it is not one.

    Strips a trailing "roles/jobs in <location>" qualifier, leading command/filler
    words ("pure", "search for", …) and trailing job nouns, then validates the
    remainder is a 1–6 word phrase containing letters, not a pure location, and
    free of prose/filler words that never appear inside a real role title.
    """
    t = (token or "").strip().strip(".!?;:").strip()
    if not t:
        return None
    # Iteratively peel a trailing "roles/jobs in <location>" / bare job-noun tail.
    prev = None
    while prev != t:
        prev = t
        t = _ROLE_TOKEN_TAIL_RE.sub("", t).strip().strip(".!?;:").strip()
    words = [w for w in t.split() if w]
    while words and words[0].lower() in _ROLE_TOKEN_LEAD_STOPWORDS:
        words.pop(0)
    while words and words[-1].lower().strip(".") in _ROLE_TOKEN_TRAILING_NOUNS:
        words.pop()
    if not words or not (1 <= len(words) <= _MAX_WORD_COUNT_FOR_ROLE):
        return None
    role = " ".join(words)
    if not re.search(r"[A-Za-z]", role):
        return None
    if all(w.lower().strip(".") in _ENGLISH_LOCATION_WORDS for w in words):
        return None
    # Any prose/filler word inside the phrase means this is not a clean role title.
    if any(w.lower().strip(".") in _NON_ROLE_WORDS for w in words):
        return None
    return role


def _split_role_phrase(segment: str) -> list[str]:
    """Split a comma/and-separated role segment into de-duplicated role titles."""
    if not segment:
        return []
    # Drop a trailing subordinate clause that is not part of the list itself.
    segment = _ROLE_LIST_TAIL_CLAUSE_RE.split(segment, maxsplit=1)[0]
    roles: list[str] = []
    seen: set[str] = set()
    for part in _ROLE_LIST_SPLIT_RE.split(segment):
        role = _clean_role_token(part)
        if role and role.lower() not in seen:
            seen.add(role.lower())
            roles.append(role)
    return roles


def extract_role_list(text: str) -> tuple[list[str], list[str]]:
    """Parse a multi-role search request into ``(target_roles, excluded_roles)``.

    Handles comma- and "and"/"or"-separated lists, strips trailing
    "roles in UAE" / "jobs in Dubai" qualifiers, and preserves a trailing
    negative-constraint clause ("do not search X, Y …") as the exclusion list.
    Returns two (possibly empty) lists; callers decide whether the positive list
    is long enough to treat the message as a multi-role search.
    """
    if not text:
        return [], []
    positive_segment = text
    excluded_segment = ""
    opener = _EXCLUSION_OPENER_RE.search(text)
    if opener:
        positive_segment = text[: opener.start()]
        excluded_segment = text[opener.end():]
    # Remove the leading search verb, then any "<loc> jobs/roles for" introduction
    # ("UAE jobs for HSE Manager and QHSE Manager" -> "HSE Manager and QHSE Manager").
    positive_segment = _MULTI_ROLE_LEAD_RE.sub("", positive_segment, count=1)
    positive_segment = _MULTI_ROLE_JOBS_FOR_RE.sub("", positive_segment, count=1)
    target_roles = _split_role_phrase(positive_segment)
    excluded_roles = _split_role_phrase(excluded_segment)
    return target_roles, excluded_roles


# Matches job-card action messages sent from RicoJobMatchCard:
#   "{action} — {title} at {company}"
# Must be checked BEFORE generic apply/save patterns.
_JOB_CARD_ACTION_RE = re.compile(
    r"^(Prepare application|Mark as applied|Track this job|Save job|Save|Open apply link)\s*[—\-–]\s*(.+)\s+at\s+(.+?)$",
    re.IGNORECASE | re.DOTALL,
)

# Bulk apply detection — safety-critical: must fire before generic apply_job check
_BULK_APPLY_RE = re.compile(
    r"\b(apply|submit).{0,20}(everything|all jobs|every job|all|each one|all of them)\b"
    r"|\b(find|get).{0,30}(all|every).{0,20}(job|position).{0,20}(and apply|then apply|and submit)"
    r"|\b(apply to|submit for).{0,10}(all|everything|every)\b",
    re.IGNORECASE,
)

# Free-text URL / apply-link requests.  Catches:
#   "open apply link for <title> at <company>"
#   "give me the URL", "what's the link", "share the apply link",
#   "send me the link", "what is the apply link", "how do I apply" (link request form)
_OPEN_APPLY_LINK_RE = re.compile(
    r"\bopen\s+apply\s+link\b"
    r"(?:\s+for\s+(.+?)\s+at\s+(.+?)"
    r"(?:[\s,;:]+(?:please|pls|thanks|thank\s+you))?"
    r")?\s*[.!?]*\s*$"
    r"|\b(?:give|send|share|show|get)\s+(?:me\s+)?(?:the\s+)?(?:apply\s+)?(?:url|link|application\s+link|apply\s+link)\b"
    r"|\bwhat(?:'s|\s+is)\s+(?:the\s+)?(?:apply\s+)?(?:url|link|application\s+link)\b"
    r"|\b(?:apply\s+)?link\s+(?:please|pls|for\s+(?:this|that|the)\s+(?:job|role|position))\b"
    r"|\bwhere\s+(?:can\s+I|do\s+I)\s+apply\b"
    r"|\bapply\s+(?:url|link)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

# Ordinal open-apply-link: "open the apply link for the first/second/Nth job",
# "open apply link for job 2", "show the apply link for the last one". Must be
# matched before _APPLY_JOB_RE so an ordinal link request is never mis-routed to
# apply_job (which then fails with "missing required 'link' field"). The "the"
# between open/apply that _OPEN_APPLY_LINK_RE omits is allowed here.
_OPEN_APPLY_LINK_ORDINAL_RE = re.compile(
    r"\b(?:open|show|give|send|share|get)\b(?:\s+me)?\s+(?:the\s+)?(?:apply\s+)?"
    r"(?:link|url|apply\s+link|application\s+link)\s+(?:for|to|of)\s+"
    r"(?:the\s+)?(?:job\s+(?:number\s+|#)?)?"
    r"(?P<ord>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d{1,2})"
    r"(?:st|nd|rd|th)?\s*(?:job|role|position|result|listing|one)?\b",
    re.IGNORECASE,
)

_ORDINAL_WORD_TO_INT = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}


def _parse_ordinal(token: str) -> Optional[int]:
    """Return a 1-based index for an ordinal token ("first"→1, "3"→3, "last"→-1)."""
    if not token:
        return None
    t = token.strip().lower()
    if t == "last":
        return -1
    if t in _ORDINAL_WORD_TO_INT:
        return _ORDINAL_WORD_TO_INT[t]
    if t.isdigit():
        n = int(t)
        return n if n >= 1 else None
    return None


_APPLY_JOB_RE = re.compile(
    r"\b(apply|apply to|apply for|submit|send application)\b",
    re.IGNORECASE,
)

_ARABIC_APPLIED_STATUS_RE = re.compile(
    r"(?:قمت\s+ب)?تقديم\s+الطلب"
    r"|قدمت\s+(?:الطلب|علي\s+الوظيفه|عليه|عليها|له|لها)"
    r"|تم\s+التقديم\s+بنجاح"
    r"|ارسلت\s+الطلب",
    re.UNICODE,
)

_ENGLISH_APPLIED_STATUS_QUERY_PREFIX_RE = re.compile(
    r"^\s*(?:what|which|show|list|view|see|where|how\s+many|tell\s+me)\b",
    re.IGNORECASE,
)

_ENGLISH_MANUAL_APPLIED_STATUS_RE = re.compile(
    r"\b(?:ya|yeah|yes|yep|ok|okay)?\s*i\s+"
    r"(?:(?:have|ve)\s+|already\s+)?"
    r"(?:applied|submitted)\b"
    r"(?:.{0,50}\b(?:manually|manual|my\s*self|myself|outside\s+rico|by\s+myself|application))?"
    r"|\bi\s+(?:sent|submitted)\s+(?:the\s+)?application\b"
    r"|\b(?:mark|log|record)\s+(?:it|this|this\s+job|the\s+job|that\s+job)?\s*(?:as\s+)?applied\b"
    r"|\b(?:can|could|will|would)\s+(?:you|u|rico)\s+(?:log|record|add|track)\s+"
    r"(?:it|this|this\s+job|the\s+job|that\s+job)\b"
    r"|\bhow\s+can\s+(?:you|u|rico)\s+(?:log|record|add|track)\s+"
    r"(?:it|this|this\s+job|the\s+job|that\s+job)\b",
    re.IGNORECASE,
)


def _is_english_manual_applied_status(text: str) -> bool:
    """True for manual-applied reports, not for list/history queries."""
    if _ENGLISH_APPLIED_STATUS_QUERY_PREFIX_RE.search(text):
        return False
    return bool(_ENGLISH_MANUAL_APPLIED_STATUS_RE.search(text))

_EXPLAIN_MATCH_RE = re.compile(
    r"\b(why|explain|how come|reason)\b.{0,50}\b(recommend|match|suggest|pick|this job)\b",
    re.IGNORECASE,
)

_INTERVIEW_PREP_RE = re.compile(
    r"\b(interview|prep(?:are)?|practice|get ready)\b.{0,40}\b(interview|role|job|company|questions?)\b"
    r"|\binterview\s+(?:prep|preparation|questions|tips)\b",
    re.IGNORECASE,
)

# Prepare application — catches free-text "prepare" intent before _DRAFT_RE so Arabic
# "اكتبلي cover letter" routes to draft creation, not generic cover letter guidance.
_PREPARE_APP_RE = re.compile(
    # English: prepare application / prepare this/my job/cv/resume
    r"\bprepare\b.{0,40}\b(application|apply|for\s+(?:this\s+)?(?:job|role|position))\b"
    r"|\bprepare\s+(?:my\s+)?(?:application|cv|resume)\b"
    # Arabic: جهز التقديم / جهز لهذه الوظيفة / جهزلي السيرة/السي في
    r"|جهز.{0,25}(?:التقديم|وظيف|السيرة|السيره|سيرتي|سي\s*في)"
    r"|اكتبلي\s+(?:cover\s+letter|سيرة|تقديم)"
    r"|جهزلي\s+(?:السيرة|السيره|السي\s*في|تقديم|وظيف)",
    re.IGNORECASE | re.UNICODE,
)

# Show draft — read existing pending application draft
_SHOW_DRAFT_RE = re.compile(
    r"\bshow\b.{0,30}\b(my\s+draft|draft|prepared\s+application|application\s+draft)\b"
    r"|\bmy\s+draft\b"
    r"|\bview\s+(?:my\s+)?draft\b"
    # Arabic
    r"|اعرض.{0,20}(?:المسودة|مسودة|التقديم\s+المجهز)"
    r"|ورجيني.{0,20}(?:المسودة|التقديم)"
    r"|(?:المسودة|مسودتي)",
    re.IGNORECASE | re.UNICODE,
)

_DRAFT_RE = re.compile(
    # English: draft/write/generate/create/make/prepare/build + cover letter / message / email
    r"\b(draft|write|generate|create|make|prepare|build)\b.{0,40}\b(cover\s+letter|message|email|letter)\b"
    # Standalone "cover letter" — user says it with no verb
    r"|\bcover\s+letter\b"
    # Arabic cover letter phrases
    r"|خطاب\s+(تغطية|تقديم|عمل|وظيفي)"
    r"|رسالة\s+(تغطية|تقديم|تعريفية|وظيفية)"
    r"|اكتب\s+(?:لي\s+)?(?:خطاب|رسالة)"
    r"|اعمل\s+(?:لي\s+)?(?:خطاب|رسالة)"
    r"|(?:cover\s+letter|خطاب|رسالة)\s+(?:لي|لوظيفة|للوظيفة)",
    re.IGNORECASE | re.UNICODE,
)

# ── Negative job feedback phrases ────────────────────────────────────────────
# User signals that a shown job is not suitable → record negative learning signal.

_JOB_FEEDBACK_NEGATIVE_PHRASES = frozenset([
    # English exact phrases
    "not suitable", "not relevant", "not for me", "not a good fit", "bad fit",
    "not interested", "this doesn't match", "not what i want", "not my type",
    "this job is not suitable", "this job is not relevant", "this role is not suitable",
    "this doesn't fit", "doesn't match my profile", "not relevant to me",
    "not a match", "poor match", "wrong type", "not the right fit",
    "this isn't suitable", "this isn't relevant", "this isn't for me",
    "not suitable for me", "not relevant for me", "doesn't fit my profile",
    # Arabic (normalised forms — ta marbuta, alef variants normalised before lookup)
    "مو مناسب", "مو مناسبه", "مش مناسب", "مش مناسبه",
    "هذا مو مناسب", "هذه مو مناسبه", "غير مناسب", "غير مناسبه",
    "ليس مناسبا", "ليست مناسبه", "مو ملائم", "مش ملائم",
    "مو مناسب لي", "مش مناسبه لي", "هذي مو مناسبه",
])

_JOB_FEEDBACK_NEGATIVE_RE = re.compile(
    r"\b(not|isn'?t|doesn'?t|don'?t|no)\b.{0,25}"
    r"\b(suitable|relevant|fit|match|interest|good|right|what\s+i\s+(want|need|look))\b"
    r"|\b(bad|poor|wrong|irrelevant|unrelated)\b.{0,15}\b(fit|match|job|role)\b"
    r"|\b(this|the)\s+(job|role).{0,20}\b(not|isn'?t|wrong|bad|poor|irrelevant)\b"
    r"|\b(mismatch|unsuitable|inappropriate)\b",
    re.IGNORECASE,
)

# ── Positive job feedback phrases ─────────────────────────────────────────────
# User signals that a shown job is a great match → record positive learning signal.

_JOB_FEEDBACK_POSITIVE_PHRASES = frozenset([
    # English exact phrases
    "perfect match", "great match", "exactly what i want", "exactly what i need",
    "this is perfect", "this is great", "this is ideal", "this is exactly it",
    "love this job", "love this role", "this looks great", "this looks perfect",
    "great fit", "good fit", "excellent match", "this suits me",
    "this is what i'm looking for", "this is what i was looking for",
    "this is for me", "this matches my profile", "this fits perfectly",
    "yes this", "yes this one", "exactly right", "spot on",
    # Arabic (normalised forms)
    "ممتاز", "مثالي", "هذا مناسب", "هذا مناسب لي", "هذا مثالي",
    "هذا ما ابي", "هذا ما اريد", "هذا ما احتاج", "هذا يناسبني",
    "يناسبني", "مناسب جدا", "مناسب جداً", "هذا يناسب خبرتي",
    "هذا مناسبه", "هذا مناسبه لي", "اعجبني هذا", "اعجبتني الوظيفه",
])

_JOB_FEEDBACK_POSITIVE_RE = re.compile(
    r"\b(perfect|great|ideal|excellent|exactly|love|awesome)\b.{0,20}"
    r"\b(match|fit|job|role|one|this)\b"
    r"|\b(this|the)\s+(job|role).{0,20}\b(perfect|great|ideal|excellent|suits?|fits?)\b"
    r"|\b(this\s+is\s+(perfect|great|ideal|exactly|what\s+i\s+(want|need|was\s+looking\s+for)))\b"
    r"|\b(looks?\s+(great|perfect|ideal|good|excellent))\b"
    r"|\b(spot\s+on|right\s+on|nailed\s+it)\b",
    re.IGNORECASE,
)

# ── Nonsense / safety heuristics ─────────────────────────────────────────────

_NONSENSE_RE = re.compile(
    r"^[^a-zA-Z]*$"                       # no letters at all
    r"|^(.)\1{4,}$"                        # repeated single char
    r"|^[a-z]{1,2}$"                       # single/double letter
    r"|^\d+$",                             # only digits
    re.IGNORECASE,
)

_MIN_MEANINGFUL_LENGTH = 2
_MAX_WORD_COUNT_FOR_ROLE = 6


def _normalize_exact_phrase(text: str) -> str:
    """Normalize short exact-match phrases so trailing punctuation does not alter intent."""
    lowered = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"^[\s\"'([{]+|[\s\"')\]}.,!?;:]+$", "", lowered)


# ── Arabic script support ────────────────────────────────────────────────────

_ARABIC_SCRIPT_RE = re.compile(r"[؀-ۿ]")

# Arabic job-related nouns (normalised: ta marbuta ة→ه, alef variants→bare alef, ى→ي)
_ARABIC_JOB_TERMS = frozenset([
    # Gulf / Levantine
    "وظيفه", "وظائف", "عمل", "شغل",
    "فرصه", "فرص", "مهنه", "مهن",
    "شاغر", "شواغر", "وضيفه",
    "منصب", "مناصب",
    # MSA additions
    "تعيين",      # appointment / hiring
    "مسمي",       # job title / designation
    "موظف",       # employee (used in "I want to be a موظف at …")
    "توظيف",      # employment / recruitment
    "فرصه عمل",   # job opportunity (phrase — substring match also fires on parts)
])

# Arabic verbs / phrases expressing a job-search request
_ARABIC_REQUEST_TERMS = frozenset([
    # Gulf / Levantine
    "ابحث", "بحث", "دور", "اريد", "ابي", "ابغي",
    "احتاج", "محتاج", "شوف", "طلع", "جيب",
    "ساعدني", "ايجاد", "طلب",
    # Display / show request verbs — e.g. "اعرضلي" (show me), "احدث" (latest)
    "اعرض", "اعرضلي", "عرض", "عرضلي", "احدث", "ارني", "وريني", "جيبلي",
    # MSA formal verbs (all stored in normalised form — alef variants stripped)
    "ارغب",   # أرغب — I wish / want
    "اسعي",   # أسعى — I seek
    "اطلب",   # أطلب — I request
    "ابحث عن",  # أبحث عن — I am looking for (phrase)
    "هل يوجد وظائف",  # are there jobs?
    "هل توجد وظائف",  # are there jobs? (feminine verb)
    "هل هناك وظائف",  # are there any jobs?
])

_ARABIC_STANDALONE_CV_JOB_REQUEST_TERMS = frozenset([
    "ابحث",
    "دور",
    "شوف",
    "جيب",
])

# Arabic role phrase that follows a job noun or "عن" (about/for), bounded by
# "في/بـ <city>" or the end of the message. Operates on _normalize_arabic'd text.
# e.g. "ابحث عن وظيفه مدير عمليات في عجمان" → captures "وظيفه مدير عمليات"; the leading
# job word is then stripped in _extract_arabic_role to leave "مدير عمليات".
_ARABIC_ROLE_AFTER_JOBWORD_RE = re.compile(
    r"(?:وظيفه|وظائف|فرصه|فرص|شاغر|شواغر|منصب|مناصب|مسمي|عمل|شغل|عن)\s+"
    r"([ء-ي][ء-ي\s]{1,40}?)"
    r"(?:\s+(?:في|بـ|ب|على)\s|[\s،.!؟]*$)"
)

# Location names (Arabic-normalised) that are never valid role candidates.
# Used to reject location-only captures from _extract_arabic_role.
_ARABIC_LOCATION_TERMS = frozenset({
    # UAE country / full name
    "الامارات", "الإمارات", "الامارات العربيه المتحده",
    # UAE emirates
    "دبي", "ابوظبي", "أبوظبي", "الشارقه", "الشارقة",
    "عجمان", "راس الخيمه", "الفجيره", "ام القيوين",
    # GCC / region
    "السعوديه", "الكويت", "قطر", "البحرين", "عمان",
    "الخليج", "الشرق الاوسط",
})

# Arabic job nouns / connectors stripped from the edges of a captured role phrase.
# Also includes profile-reference phrases like "بمجالي" (in my field) that should
# not be treated as a role — they imply profile-based search with no explicit role.
_ARABIC_ROLE_LEAD_STOPWORDS = frozenset({
    "وظيفه", "وظائف", "فرصه", "فرص", "شاغر", "شواغر", "منصب", "مناصب",
    "مسمي", "عمل", "شغل", "عن", "لي", "لك", "في",
    # Profile-reference suffixes — mean "in my field/domain", not a job title
    "بمجالي", "بمجال", "مجالي", "تخصصي", "في مجالي",
})

# Deterministic Arabic→English role synonyms for UAE job titles.
# Keys are _normalize_arabic'd forms (ta marbuta ه, bare alef ا, etc.).
# Applied at the end of _extract_arabic_role so Arabic search queries yield
# English role names that the JSearch / role-classifier pipeline can handle.
_ARABIC_TO_ENGLISH_ROLE_MAP: dict[str, str] = {
    # Compliance / Legal
    "مدير امتثال": "Compliance Manager",
    "مستشار قانوني": "Legal Advisor",
    "مدير مخاطر": "Risk Manager",
    # Operations / Management
    "مدير عمليات": "Operations Manager",
    "مدير مشاريع": "Project Manager",
    "مدير عام": "General Manager",
    "مدير تنفيذي": "Executive Manager",
    "مدير تطوير": "Development Manager",
    "مدير تطوير اعمال": "Business Development Manager",
    "مدير": "Manager",
    # Finance / Accounting
    "محاسب": "Accountant",
    "محاسب مالي": "Financial Accountant",
    "محاسب قانوني": "Chartered Accountant",
    "محلل مالي": "Financial Analyst",
    "محلل اعمال": "Business Analyst",
    "محلل بيانات": "Data Analyst",
    "مدير مالي": "Finance Manager",
    "مدير الماليه": "Finance Manager",
    # HR / Admin
    "مدير موارد بشريه": "HR Manager",
    "اخصائي موارد بشريه": "HR Specialist",
    # Engineering
    "مهندس مدني": "Civil Engineer",
    "مهندس كهربائي": "Electrical Engineer",
    "مهندس كهرباء": "Electrical Engineer",
    "مهندس ميكانيكي": "Mechanical Engineer",
    "مهندس برمجيات": "Software Engineer",
    "مطور برمجيات": "Software Developer",
    "مهندس": "Engineer",
    # Sales / Marketing
    "مدير تسويق": "Marketing Manager",
    "مدير مبيعات": "Sales Manager",
    "اخصائي تسويق": "Marketing Specialist",
    "اخصائي مبيعات": "Sales Specialist",
    # IT
    "مدير تقنيه المعلومات": "IT Manager",
    "مدير نظم معلومات": "Information Systems Manager",
    # Supply Chain / Logistics
    "مدير سلسله التوريد": "Supply Chain Manager",
    "مدير لوجستيات": "Logistics Manager",
    "مدير مشتريات": "Procurement Manager",
    # HSE / Quality
    "مدير جوده": "Quality Manager",
    "مدير صحه وسلامه": "HSE Manager",
}


def _normalize_arabic(text: str) -> str:
    """Remove diacritics and normalise Arabic letter variants before phrase lookup."""
    # Remove tashkeel (fatha, kasra, damma, sukun, shadda, tanwin, tatweel)
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    # Normalise alef variants (madda آ, hamza above أ, hamza below إ, wasla ٱ) → bare alef ا
    text = re.sub(r"[آأإٱ]", "ا", text)
    # Normalise alef maqsura ى → ya ي
    text = re.sub(r"ى", "ي", text)
    # Normalise ta marbuta ة → ha ه  (so وظيفة == وظيفه in lookups)
    text = re.sub(r"ة", "ه", text)
    return text


def _is_arabic_job_search(normalized_lower: str, *, has_cv: bool = False) -> bool:
    """Return True when a normalised Arabic message is a job-search request."""
    has_request = any(t in normalized_lower for t in _ARABIC_REQUEST_TERMS)
    if not has_request:
        return False
    has_ar_job = any(t in normalized_lower for t in _ARABIC_JOB_TERMS)
    # Mixed-language: Arabic request verb + English role name (e.g. "دور لي safety officer")
    has_en_content = bool(re.search(r"[a-zA-Z]{2,}", normalized_lower))
    # A standalone search command from a user who has a CV is a job-search request.
    # e.g. "ابحث" alone = "search [for jobs for me]"
    has_standalone_cv_request = normalized_lower.strip() in _ARABIC_STANDALONE_CV_JOB_REQUEST_TERMS
    return has_ar_job or has_en_content or (has_cv and has_standalone_cv_request)


def _extract_english_role_from_mixed(text: str) -> Optional[str]:
    """Extract a trailing English role phrase from a mixed Arabic+English message."""
    m = re.search(r"([A-Za-z][A-Za-z\s/()\-]{1,50}[A-Za-z])\s*$", text.strip())
    if m:
        role = m.group(1).strip()
        if 1 <= len(role.split()) <= _MAX_WORD_COUNT_FOR_ROLE:
            return role
    return None


def _extract_role_before_noun(text: str) -> Optional[str]:
    """Extract a role that appears immediately before a job noun.

    Handles the natural word order users type — "operations manager jobs in ajman",
    "find HSE manager roles", "any nursing positions" — which the "jobs for <role>"
    pattern does not capture. Leading command/filler words ("find", "me", "any", ...)
    are stripped so "find operations manager jobs" yields "operations manager".
    Returns None when nothing meaningful remains (e.g. "find me jobs" -> None).
    """
    m = _JOB_SEARCH_ROLE_BEFORE_NOUN_RE.search(text)
    if not m:
        return None
    words = m.group(1).strip().split()
    while words and words[0].lower() in _ROLE_PREFIX_STOPWORDS:
        words.pop(0)
    if not (1 <= len(words) <= _MAX_WORD_COUNT_FOR_ROLE):
        return None
    return " ".join(words)


def _extract_arabic_role(normalized_text: str) -> Optional[str]:
    """Extract a pure-Arabic role phrase from a normalised Arabic job-search message.

    "ابحث عن وظيفه مدير عمليات في عجمان" -> "مدير عمليات". The previous behaviour only
    extracted a trailing *English* role, so Arabic roles were dropped and the search fell
    back to the profile's saved roles. Input must already be passed through
    _normalize_arabic. Returns None when no clear role phrase remains.
    """
    m = _ARABIC_ROLE_AFTER_JOBWORD_RE.search(normalized_text)
    if not m:
        return None
    words = m.group(1).strip().split()
    # Strip job nouns / connectors the (leftmost) match may have swept into the capture.
    while words and words[0] in _ARABIC_ROLE_LEAD_STOPWORDS:
        words.pop(0)
    while words and words[-1] in _ARABIC_ROLE_LEAD_STOPWORDS:
        words.pop()
    if not (1 <= len(words) <= _MAX_WORD_COUNT_FOR_ROLE):
        return None
    role = " ".join(words)
    if role in _ARABIC_JOB_TERMS or role in _ARABIC_REQUEST_TERMS:
        return None
    # A phrase made up entirely of location terms is a location qualifier, not a role.
    if all(w in _ARABIC_LOCATION_TERMS for w in words):
        return None
    return role


# ── Search confirmation / continuation patterns ──────────────────────────────
#
# Stage 1 fix — production symptom:
#   "Yes, search Software Engineer" → intent=unknown → bare_role_gate_reject_to_ai
#
# Root cause: _JOB_SEARCH_EXPLICIT_RE requires a job noun in the message tail.
# Confirmation-prefixed bare-title searches have no such noun, so they fall
# through to unknown.  This early-exit block intercepts them before the fallback.
#
# Match examples (all → job_search_explicit):
#   "Yes, search Software Engineer"
#   "yes search Product Manager"
#   "Search Data Analyst"
#   "find Data Engineer"
#   "go ahead search Environmental Manager"
#   "please find Compliance Officer"
#   "sure, search UI/UX Designer"
#   "نعم، ابحث عن Software Engineer"
#
# Non-match examples (fall through to existing handlers):
#   "search jobs"           → bare job noun, excluded via negative lookahead
#   "find roles"            → bare job noun, excluded
#   "Yes"                   → acknowledgement, no change
#   "Yes, show my pipeline" → existing handler, no change
_SEARCH_CONFIRMATION_RE = re.compile(
    r"^"
    # Optional confirmation/affirmation prefix (English + Arabic)
    r"(?:"
    r"yes[,.]?\s+|yeah[,.]?\s+|yep[,.]?\s+|yup[,.]?\s+"
    r"|ok[,.]?\s+|okay[,.]?\s+"
    r"|sure[,.]?\s+|alright[,.]?\s+|fine[,.]?\s+"
    r"|please[,.]?\s+"
    r"|go\s+ahead[,.]?\s+"
    r"|نعم[،,]?\s+|اوكي[،,]?\s+|تمام[،,]?\s+|حسنا[،,]?\s+|موافق[،,]?\s+"
    r")?"
    # Required search/find verb
    r"(?:search|find|look\s+for|show\s+me|show)\s+"
    # Negative lookahead: block bare job-noun queries (those belong to other handlers)
    r"(?!(?:jobs?|roles?|positions?|openings?|vacancies|vacancy|listings?)\b)"
    # Capture the role title — allows spaces, slashes, ampersands, hyphens, parens.
    # Trailing optional group allows "in Dubai" / "jobs in UAE" suffixes.
    r"(?P<role>[A-Za-z؀-ۿ][A-Za-z؀-ۿ\s/&()\-]{1,80}?)"
    r"(?:\s+(?:jobs?|roles?|positions?|in\b|for\b).{0,50})?$",
    re.IGNORECASE,
)

# Bare job-noun guard — "search jobs" / "find roles" must NOT be captured by
# _SEARCH_CONFIRMATION_RE; they belong to profile-match or help handlers.
_BARE_JOB_NOUN_RE = re.compile(
    r"^(?:yes[,.]?\s+|yeah[,.]?\s+|ok[,.]?\s+|okay[,.]?\s+|sure[,.]?\s+|)?"
    r"(?:search|find|look\s+for|show(?:\s+me)?)\s+"
    r"(?:jobs?|roles?|positions?|openings?|vacancies|vacancy|listings?)\s*$",
    re.IGNORECASE,
)


def _extract_role_from_confirmation(text: str) -> Optional[str]:
    """Extract a clean role title from a confirmation-prefixed search phrase.

    Strips leading confirmation prefix ("Yes, ", "go ahead ", Arabic) and
    search verb ("search", "find", "look for"), and trailing location/job-noun
    suffixes ("in Dubai", "jobs in UAE"). Returns None for bare job-noun queries
    or messages that do not match the confirmation pattern.
    """
    if _BARE_JOB_NOUN_RE.match(text.strip()):
        return None
    m = _SEARCH_CONFIRMATION_RE.match(text.strip())
    if not m:
        return None
    role = m.group("role").strip().rstrip(",. ")
    return role if len(role) >= 2 else None


def classify_intent(message: str, *, has_cv_profile: bool = False) -> IntentResult:
    """Classify a user message into a canonical intent.

    Args:
        message: Raw user message text.
        has_cv_profile: Whether the user has a parsed CV / populated profile.

    Returns:
        IntentResult with intent name, confidence, and source.
    """
    text = (message or "").strip()
    lower = _normalize_exact_phrase(text)

    # Apply Arabic normalisation so phrase lookups work regardless of hamza /
    # ta marbuta / diacritic variants typed by the user.
    has_arabic = bool(_ARABIC_SCRIPT_RE.search(text))
    if has_arabic:
        lower = _normalize_arabic(lower)

    if not text or len(text) < _MIN_MEANINGFUL_LENGTH:
        return IntentResult("unknown", 0.0, "fallback")

    # ── 1. Exact-phrase fast paths (before any regex) ────────────────────
    # Acknowledgements (thanks/ok/great/etc.) are matched before greetings so
    # they never trigger the cold-start greeting mid-conversation.
    if lower in _ACKNOWLEDGEMENT_PHRASES:
        return IntentResult("acknowledgement", 1.0, "exact")

    if lower in _SMALLTALK_PHRASES:
        return IntentResult("smalltalk", 1.0, "exact")

    # ── 1b. Nonsense gate (after smalltalk check) ───────────────────────
    # Arabic text contains no Latin letters — skip the gate so Arabic is not
    # incorrectly flagged as nonsense.
    if not has_arabic and _NONSENSE_RE.match(text):
        return IntentResult("nonsense", 0.95, "regex")

    # ── 2. Exact-phrase fast paths (continued) ───────────────────────────
    if lower in _PROFILE_MATCH_PHRASES:
        return IntentResult("job_search_profile_match", 1.0, "exact")

    if lower in _RECENT_CONTEXT_PHRASES:
        return IntentResult("recent_context", 1.0, "exact")

    # Lifecycle funnel queries — exact (more specific than application_tracking)
    if lower in _LIFECYCLE_SAVED_PHRASES:
        return IntentResult("lifecycle_show_saved", 1.0, "exact")
    if lower in _LIFECYCLE_APPLIED_PHRASES:
        return IntentResult("lifecycle_show_applied", 1.0, "exact")
    if lower in _LIFECYCLE_OPENED_NOT_APPLIED_PHRASES:
        return IntentResult("lifecycle_show_opened_not_applied", 1.0, "exact")

    if lower in _APPLICATION_TRACKING_PHRASES:
        return IntentResult("application_tracking", 1.0, "exact")

    if has_arabic and _ARABIC_APPLIED_STATUS_RE.search(lower):
        return IntentResult(
            "application_status_update",
            0.95,
            "regex",
            context_required=True,
            context_type="recent_job",
            action="mark_applied",
            target_route="/applications",
        )

    if lower in _HELP_PHRASES:
        return IntentResult("help", 1.0, "exact")

    if lower in _PROFILE_SUMMARY_PHRASES:
        return IntentResult("profile_summary", 1.0, "exact")

    if lower in _LEARNING_SUMMARY_PHRASES:
        return IntentResult("learning_profile_summary", 1.0, "exact")

    if lower in _PREF_CORRECTION_PHRASES:
        return IntentResult("preference_correction", 1.0, "exact")

    if lower in _APP_INSIGHTS_PHRASES:
        return IntentResult("application_insights", 1.0, "exact")

    if lower in _PROFILE_ROLE_SUGGESTIONS_PHRASES:
        return IntentResult("profile_role_suggestions", 1.0, "exact")

    if lower in _SKIP_PHRASES:
        return IntentResult("onboarding_answer", 0.9, "exact")

    if lower in _PROFILE_UPDATE_PHRASES:
        return IntentResult("profile_update", 0.9, "exact")

    if lower in _FOLLOW_UP_CONFIRMATION_PHRASES:
        return IntentResult("follow_up_confirmation", 1.0, "exact")

    if lower in _SUBSCRIPTION_PHRASES:
        return IntentResult("subscription.show_plans", 1.0, "exact")

    # ── 3. Regex patterns (ordered by specificity) ───────────────────────

    if _CV_UPLOAD_RE.search(text):
        return IntentResult("cv_upload_or_parse", 0.95, "regex")

    # cv_generate must be checked BEFORE cv_create — rewrite/refresh/اعملي phrases
    # should route to the generate-from-profile handler, not the scratch builder.
    if _CV_GENERATE_RE.search(text):
        return IntentResult("cv_generate", 0.92, "regex")

    if _CV_CREATE_RE.search(text):
        return IntentResult("cv_create", 0.9, "regex")

    # Job-card actions carry structured context — classify before generic patterns.
    job_card_m = _JOB_CARD_ACTION_RE.match(text)
    if job_card_m:
        action_raw = job_card_m.group(1).lower()
        title = job_card_m.group(2).strip()
        company = job_card_m.group(3).strip()
        intent_map = {
            "prepare application": "prepare_application",
            "mark as applied": "mark_applied",
            "track this job": "track_job",
            "save job": "save_job",
            "save": "save_job",
            "open apply link": "open_apply_link",
        }
        matched_intent = intent_map.get(action_raw, "job_action")
        return IntentResult(matched_intent, 0.95, "regex", extracted_title=title, extracted_company=company)

    # Bulk/unsafe apply must be caught before generic apply_job — safety-critical.
    if _BULK_APPLY_RE.search(text):
        return IntentResult(
            "job_action.bulk_apply_unsafe",
            0.95,
            "regex",
            context_required=True,
            context_type="recent_job",
            action="require_explicit_consent",
            target_route="/jobs",
        )

    # Ordinal open-apply-link ("open the apply link for the first job") must be
    # caught before the title/company form and before generic apply_job.
    om = _OPEN_APPLY_LINK_ORDINAL_RE.search(text)
    if om:
        _ordinal = _parse_ordinal(om.group("ord"))
        if _ordinal is not None:
            return IntentResult(
                "open_apply_link", 0.95, "regex",
                entities={"ordinal": _ordinal},
            )

    # Free-text open-apply-link must be caught before generic apply_job.
    m = _OPEN_APPLY_LINK_RE.search(text)
    if m:
        extracted_title = (m.group(1) or "").strip() or None
        extracted_company = (m.group(2) or "").strip() or None
        return IntentResult(
            "open_apply_link", 0.95, "regex",
            extracted_title=extracted_title,
            extracted_company=extracted_company,
        )

    if not has_arabic and _is_english_manual_applied_status(text):
        return IntentResult(
            "application_status_update",
            0.93,
            "regex",
            context_required=True,
            context_type="recent_job",
            action="mark_applied",
            target_route="/applications",
        )

    if _APPLY_JOB_RE.search(text):
        return IntentResult("apply_job", 0.95, "regex")

    # Check save-target-role BEFORE save_job so "save X as target role" isn't
    # misclassified as a job-bookmark action.
    save_role_match = _SAVE_TARGET_ROLE_RE.search(text)
    if save_role_match:
        return IntentResult(
            "save_target_role", 0.95, "regex",
            extracted_role=save_role_match.group(1).strip(),
        )

    # Ordinal save ("save the second job to my pipeline" / "احفظ ثاني وظيفة")
    # must be detected before the plain save pattern so the handler can resolve
    # the Nth job from recent search results.
    _save_ord_m = _SAVE_JOB_ORDINAL_RE.search(text)
    if _save_ord_m:
        _save_ord = _parse_ordinal(_save_ord_m.group("ord") or _save_ord_m.group("ord_after"))
        if _save_ord is not None:
            return IntentResult("save_job", 0.95, "regex", entities={"ordinal": _save_ord})
    if has_arabic:
        _save_ord_ar = _SAVE_JOB_ORDINAL_AR_RE.search(text)
        if _save_ord_ar:
            _save_ord = _ARABIC_ORDINAL_TO_INT.get(_save_ord_ar.group("aord"))
            if _save_ord is not None:
                return IntentResult("save_job", 0.95, "regex", entities={"ordinal": _save_ord})

    # "save it/Dubai to my profile/preferences" — must not be mistaken for a
    # job save. Check before _SAVE_JOB_RE so profile writes take priority.
    if _SAVE_TO_PROFILE_RE.search(text):
        return IntentResult("profile_update", 0.92, "regex")

    if _SAVE_JOB_RE.search(text):
        return IntentResult("save_job", 0.95, "regex")

    if _EXPLAIN_MATCH_RE.search(text):
        return IntentResult("explain_match", 0.9, "regex")

    # prepare_application must be checked BEFORE _DRAFT_RE so "اكتبلي cover letter"
    # routes to draft creation rather than generic cover-letter guidance.
    if _PREPARE_APP_RE.search(text):
        return IntentResult("prepare_application", 0.92, "regex")

    if _SHOW_DRAFT_RE.search(text):
        return IntentResult("show_draft", 0.9, "regex")

    if _DRAFT_RE.search(text):
        return IntentResult("draft_message", 0.9, "regex")

    if _INTERVIEW_PREP_RE.search(text):
        return IntentResult("interview_prep", 0.9, "regex")

    if _PROFILE_UPDATE_RE.search(text):
        return IntentResult("profile_update", 0.85, "regex")

    if _LEARNING_SUMMARY_RE.search(text):
        return IntentResult("learning_profile_summary", 0.9, "regex")

    if _PREF_CORRECTION_RE.search(text):
        return IntentResult("preference_correction", 0.9, "regex")

    if _APP_INSIGHTS_RE.search(text):
        return IntentResult("application_insights", 0.9, "regex")

    # Salary must be checked BEFORE _SUBSCRIPTION_RE — "how much do X earn" is a salary
    # question, not a pricing query, and _SUBSCRIPTION_RE matches "how much" broadly.
    if _SALARY_ENQUIRY_RE.search(text):
        return IntentResult("salary_enquiry", 0.88, "regex")

    if _CV_ANALYSIS_RE.search(text):
        return IntentResult("cv_analysis", 0.88, "regex")

    # Subscription / pricing regex (check before job search)
    if _SUBSCRIPTION_RE.search(text):
        return IntentResult("subscription.show_plans", 0.9, "regex")

    # Delegated decision (user asks Rico to choose)
    if _DELEGATED_DECISION_RE.search(text):
        return IntentResult("delegated_decision", 0.9, "regex")

    # Lifecycle funnel queries regex (before application_tracking, more specific)
    if _LIFECYCLE_OPENED_NOT_APPLIED_RE.search(text):
        return IntentResult("lifecycle_show_opened_not_applied", 0.9, "regex")
    if _LIFECYCLE_SAVED_RE.search(text) and not _JOB_SEARCH_EXPLICIT_RE.search(text):
        return IntentResult("lifecycle_show_saved", 0.85, "regex")
    if _LIFECYCLE_APPLIED_RE.search(text) and not _JOB_SEARCH_EXPLICIT_RE.search(text):
        return IntentResult("lifecycle_show_applied", 0.85, "regex")

    # Application tracking regex (looser than exact phrases)
    if _APPLICATION_TRACKING_RE.search(text) and not _JOB_SEARCH_EXPLICIT_RE.search(text):
        return IntentResult("application_tracking", 0.8, "regex")

    # ── 4. Job search patterns ───────────────────────────────────────────
    # 4a-0. Descriptive category → concrete allowed roles ("I want product and
    # technical management jobs, not coding jobs"). Mapped before the generic
    # multi-role parser, which would otherwise treat "product"/"coding" as roles.
    if _CATEGORY_RE.search(text):
        _cat_roles = list(_CATEGORY_PRODUCT_TECH_MGMT_ROLES)
        _cat_excl = (
            list(_CODING_EXCLUSION_ROLES) if _NOT_CODING_RE.search(text)
            else extract_role_list(text)[1]
        )
        return IntentResult(
            "job_search_multi_role", 0.9, "regex",
            extracted_role=_cat_roles[0],
            entities={"roles": _cat_roles, "excluded_roles": _cat_excl, "category": True},
        )

    # 4a-1. CV/profile-based search with exclusions but no explicit positive role
    # ("find jobs based on my CV, but do not search Software Engineer, ..."). Route
    # to profile-match carrying the exclusion guard so excluded roles are never
    # searched or suggested.
    _cv_pos, _cv_excl = extract_role_list(text)
    if _cv_excl and not _cv_pos and _CV_PROFILE_REF_RE.search(text):
        return IntentResult(
            "job_search_profile_match", 0.9, "regex",
            entities={"excluded_roles": _cv_excl},
        )

    # 4a. Multi-role search list — "search for A, B and C roles in UAE, do not
    # search X, Y". A single comma/and-separated request for several target roles
    # (with optional negative constraints). Must run before role_change and
    # job_search_explicit so the whole list is not captured as one unknown role
    # ("I do not recognize '<the whole list>' as a job role"). Gated on a search
    # verb + an explicit job noun so ordinary prose never triggers it.
    if (
        (_ROLE_CHANGE_RE.match(text) or _JOB_SEARCH_EXPLICIT_RE.search(text))
        and re.search(r"\b(?:jobs?|roles?|positions?|openings?|vacancies?)\b", text, re.IGNORECASE)
    ):
        _ml_roles, _ml_excluded = extract_role_list(text)
        if len(_ml_roles) >= 2:
            _ml_entities: dict = {"roles": _ml_roles, "excluded_roles": _ml_excluded}
            _ml_city = _UAE_CITY_EXTRACT_RE.search(text)
            # "UAE" is the default search scope, not a city constraint — skip it.
            if _ml_city and _ml_city.group(1).strip().lower() != "uae":
                _ml_entities["location"] = _ml_city.group(1).strip().title()
            _ml_emp = _EMPLOYMENT_TYPE_EXTRACT_RE.search(text)
            if _ml_emp:
                _ml_entities["employment_type"] = _ml_emp.group(1).lower()
            return IntentResult(
                "job_search_multi_role", 0.9, "regex",
                extracted_role=_ml_roles[0],
                entities=_ml_entities,
            )

    # Source-filter and compound-refinement checks must precede _JOB_SEARCH_EXPLICIT_RE
    # so filter tokens ("exclude", "only", "no contract") are never misclassified as roles.
    if _SOURCE_FILTER_RE.search(text):
        return IntentResult("search_refine", 0.88, "regex", action="source_filter")

    # Fire search_refine when:
    #   (a) _SEARCH_REFINE_RE matches and _JOB_SEARCH_EXPLICIT_RE does NOT — pure constraint, or
    #   (b) both match but no role is extractable — e.g. "show me only jobs in Dubai,
    #       no contract" has "show me…jobs" but no role to search for.
    # "find HSE manager jobs in Abu Dhabi permanent only" matches both but has a role
    # → falls through to job_search_explicit where role + entities are extracted together.
    if _SEARCH_REFINE_RE.search(text):
        _has_explicit = _JOB_SEARCH_EXPLICIT_RE.search(text)
        if _has_explicit:
            # Quick role extraction to decide routing.
            _for_m = _JOB_SEARCH_FOR_ROLE_RE.search(text)
            _tentative = _for_m.group(1).strip() if _for_m else _extract_role_before_noun(text)
        else:
            _tentative = None
        if not _has_explicit or not _tentative:
            _refine_entities: dict = {}
            _rc_m = _UAE_CITY_EXTRACT_RE.search(text)
            # "UAE" is the default search scope, not a city constraint — skip it.
            if _rc_m and _rc_m.group(1).strip().lower() != "uae":
                _refine_entities["location"] = _rc_m.group(1).strip().title()
            _re_m = _EMPLOYMENT_TYPE_EXTRACT_RE.search(text)
            if _re_m:
                _refine_entities["employment_type"] = _re_m.group(1).lower()
            return IntentResult(
                "search_refine", 0.85, "regex", action="filter_constraints",
                entities=_refine_entities if _refine_entities else None,
            )

    # Guard: ownership phrases must never route to job-role search.
    # "show my job applications and their status", "my jobs", "show my pipeline"
    # all contain job nouns that _JOB_SEARCH_EXPLICIT_RE would otherwise capture.
    # Use the normalised lowercase form to benefit from punctuation stripping.
    if _MY_OWNERSHIP_CMD_RE.search(lower):
        return IntentResult(
            "application_tracking", 0.95, "regex",
            action="show",
            target_route="/applications",
        )

    # Check explicit job search FIRST (has job/role/position keyword)
    if _JOB_SEARCH_EXPLICIT_RE.search(text):
        # Try to extract an explicit role target so the handler can search for that role
        # directly instead of falling back to profile target_roles. Prefer the
        # "jobs for <role>" word order, then the natural "<role> jobs" word order.
        for_role_m = _JOB_SEARCH_FOR_ROLE_RE.search(text)
        extracted_role = for_role_m.group(1).strip() if for_role_m else None
        if not extracted_role:
            extracted_role = _extract_role_before_noun(text)
        # Strip trailing politeness/urgency qualifiers ("... Owner only" -> "... Owner").
        extracted_role = _strip_role_qualifiers(extracted_role)
        # Extract location and employment_type entities for richer search queries.
        _search_entities: dict = {}
        _city_m = _UAE_CITY_EXTRACT_RE.search(text)
        # "UAE" is the default search scope, not a city constraint — skip it.
        if _city_m and _city_m.group(1).strip().lower() != "uae":
            _search_entities["location"] = _city_m.group(1).strip().title()
        _emp_m = _EMPLOYMENT_TYPE_EXTRACT_RE.search(text)
        if _emp_m:
            _search_entities["employment_type"] = _emp_m.group(1).lower()
        return IntentResult(
            "job_search_explicit", 0.85, "regex",
            extracted_role=extracted_role,
            entities=_search_entities if _search_entities else None,
        )

    # Arabic job search: request verb + job noun, or request verb + English role name
    if has_arabic and _is_arabic_job_search(lower, has_cv=has_cv_profile):
        # Prefer a pure-Arabic role phrase ("وظيفه مدير عمليات في عجمان" -> "مدير عمليات");
        # fall back to a trailing English role for mixed-language messages.
        role = _extract_arabic_role(lower) or _extract_english_role_from_mixed(text)
        # Map known Arabic role names to English so JSearch receives a recognisable title.
        if role:
            role = _ARABIC_TO_ENGLISH_ROLE_MAP.get(role, role)
        return IntentResult("job_search_explicit", 0.85, "regex", extracted_role=role)

    # ── 4b. Search-confirmation fast-path (Stage 1 fix) ──────────────────
    # "Yes, search Software Engineer" / "go ahead find Technical Product Owner" /
    # "Search Data Analyst" — confirmation-prefixed bare-title searches that have no
    # job noun, so they fall through _JOB_SEARCH_EXPLICIT_RE above.
    # Intercept here, before role_change, and promote to job_search_explicit.
    _confirm_role = _extract_role_from_confirmation(text)
    if _confirm_role:
        return IntentResult("job_search_explicit", 0.88, "regex", extracted_role=_confirm_role)

    # Role change — only if no explicit job-search keyword present
    role_match = _ROLE_CHANGE_RE.match(text)
    if role_match:
        return IntentResult("role_change", 0.9, "regex", extracted_role=role_match.group(2).strip())

    # ── 5. Profile-match inference (only if CV exists) ───────────────────
    # Generic short requests with CV profile → profile match, NOT job search
    _GENERIC_MATCH_WORDS = {"match", "matches", "matching", "suitable", "fit", "recommend"}
    if has_cv_profile and any(w in lower.split() for w in _GENERIC_MATCH_WORDS):
        return IntentResult("job_search_profile_match", 0.8, "regex")

    # ── 5b. Job feedback (positive / negative) before unknown fallback ───
    # Positive first — "this is perfect" must not be caught by negative regex.
    if lower in _JOB_FEEDBACK_POSITIVE_PHRASES or _JOB_FEEDBACK_POSITIVE_RE.search(text):
        return IntentResult("job_feedback_positive", 0.9, "regex")

    if lower in _JOB_FEEDBACK_NEGATIVE_PHRASES or _JOB_FEEDBACK_NEGATIVE_RE.search(text):
        return IntentResult("job_feedback_negative", 0.9, "regex")

    # ── 6. Unknown — DO NOT default to job search ────────────────────────
    return IntentResult("unknown", 0.0, "fallback")

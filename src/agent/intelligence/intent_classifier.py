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
    "job_action.explain_fit": "explain_match",
    # Application tracking
    "application.show_flow": "application_tracking",
    "application.recent_context": "application_tracking",
    # Lifecycle funnel queries
    "lifecycle.show_saved": "lifecycle_show_saved",
    "lifecycle.show_applied": "lifecycle_show_applied",
    "lifecycle.show_opened_not_applied": "lifecycle_show_opened_not_applied",
    # Profile
    "profile.show": "profile_summary",
    "profile.update": "profile_update",
    "profile.update_target_roles": "save_target_role",
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
    # Arabic profile identity
    "ما هو اسمي", "ما اسمي", "اسمي", "من انا", "ما هو ملفي",
])

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
    # Arabic (normalised forms)
    "كم الاسعار", "كيف اشترك", "كيف يمكنني الاشتراك",
    "اشتراكي", "باقتي", "الاسعار", "السعر", "خطه الاشتراك",
    "ابي اشترك", "كيف اشتري", "ابي اشتري", "كم السعر",
    "اريد الاشتراك", "اريد ان اشترك",
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

_CV_CREATE_RE = re.compile(
    r"\b(create|make|build|draft|write|generate)\b.{0,30}\b(cv|resume|cv for me|resume for me)\b"
    r"|\b(no\s+cv|no\s+resume|don't\s+have\s+a\s+cv|dont\s+have\s+a\s+cv)\b"
    r"|\b(create\s+cv|make\s+me\s+a\s+cv|create\s+resume|make\s+me\s+a\s+resume)\b"
    r"|لا\s+يوجد\s+لدي\s+سيره\s+ذاتيه"
    r"|انشاء\s+سيره\s+ذاتيه"
    r"|اصنع\s+لي\s+سيره\s+ذاتيه",
    re.IGNORECASE,
)

_PROFILE_UPDATE_RE = re.compile(
    r"\b(update|change|set|modify|adjust)\b.{0,40}"
    r"\b(salary|city|location|preference|role|title|industry|experience|notice|email|phone|telegram)\b",
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
    r"|\b(buy|purchase)\b.{0,20}\b(subscription|plan|access|package)\b",
    re.IGNORECASE,
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

_SAVE_TARGET_ROLE_RE = re.compile(
    r"\b(?:save|set|add|use)\s+(.+?)\s+as\s+(?:my\s+)?target\s+role\b",
    re.IGNORECASE,
)

_SAVE_JOB_RE = re.compile(
    r"\b(save|bookmark|keep|shortlist)\b.{0,30}\b(job|this|it|one|role)\b",
    re.IGNORECASE,
)

# Extracts explicit role name from "find/search … jobs for <role>" patterns.
# Checked alongside _JOB_SEARCH_EXPLICIT_RE to attach extracted_role.
_JOB_SEARCH_FOR_ROLE_RE = re.compile(
    r"\b(?:find|search|show|get|look(?:ing)?\s+for|need|want)\b.{0,40}\b(?:jobs?|roles?|positions?|openings?|vacancies?)\b"
    r"\s+for\s+([A-Za-z][A-Za-z &/\-]{2,60}?)(?:\s+in\b|[?.!,\s]*$)",
    re.IGNORECASE,
)

# Matches job-card action messages sent from RicoJobMatchCard:
#   "{action} — {title} at {company}"
# Must be checked BEFORE generic apply/save patterns.
_JOB_CARD_ACTION_RE = re.compile(
    r"^(Prepare application|Mark as applied|Track this job|Save job|Save|Open apply link)\s*[—\-–]\s*(.+)\s+at\s+(.+?)$",
    re.IGNORECASE | re.DOTALL,
)

# Free-text "open apply link for <title> at <company>"
_OPEN_APPLY_LINK_RE = re.compile(
    r"\bopen\s+apply\s+link\b"
    r"(?:\s+for\s+(.+?)\s+at\s+(.+?)"
    r"(?:[\s,;:]+(?:please|pls|thanks|thank\s+you))?"
    r")?\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_APPLY_JOB_RE = re.compile(
    r"\b(apply|apply to|apply for|submit|send application)\b",
    re.IGNORECASE,
)

_EXPLAIN_MATCH_RE = re.compile(
    r"\b(why|explain|how come|reason)\b.{0,50}\b(recommend|match|suggest|pick|this job)\b",
    re.IGNORECASE,
)

_INTERVIEW_PREP_RE = re.compile(
    r"\b(interview|prep(?:are)?|practice|get ready)\b.{0,40}\b(interview|role|job|company|questions?)\b"
    r"|\binterview\s+(?:prep|preparation|questions|tips)\b",
    re.IGNORECASE,
)

_DRAFT_RE = re.compile(
    r"\b(draft|write|generate|create)\b.{0,40}\b(cover letter|message|email|letter)\b",
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

# Arabic application-history / tracking indicators (normalised forms).
# These signal a question about ALREADY-submitted applications and how to
# follow/track them — they must route to the application tracker, never to a
# brand-new job search.  Critical because "طلب" (request) is a substring of
# "الطلب" (the application) and a job noun like "وظيفه" appears in questions
# such as "كم وظيفة قمت بالتقديم عليها" ("how many jobs have I applied to"),
# which would otherwise trip the Arabic job-search heuristic.
_ARABIC_APPLICATION_HISTORY_TERMS = frozenset([
    "تقديم",     # application / applying (covers التقديم, بالتقديم, تقديمي)
    "قدمت",      # I submitted / applied (substring of تقدمت)
    "تقدمت",     # I applied
    "متابع",     # follow-up / track (covers متابعة, متابعته, متابعتها)
    "طلباتي",    # my applications/requests
    "تتبع",      # track
])


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


def _is_arabic_application_query(normalized_lower: str) -> bool:
    """Return True when a normalised Arabic message asks about already-submitted
    applications or how to follow/track them (application history)."""
    return any(t in normalized_lower for t in _ARABIC_APPLICATION_HISTORY_TERMS)


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

    if lower in _HELP_PHRASES:
        return IntentResult("help", 1.0, "exact")

    if lower in _PROFILE_SUMMARY_PHRASES:
        return IntentResult("profile_summary", 1.0, "exact")

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

    if _SAVE_JOB_RE.search(text):
        return IntentResult("save_job", 0.95, "regex")

    if _EXPLAIN_MATCH_RE.search(text):
        return IntentResult("explain_match", 0.9, "regex")

    if _DRAFT_RE.search(text):
        return IntentResult("draft_message", 0.9, "regex")

    if _INTERVIEW_PREP_RE.search(text):
        return IntentResult("interview_prep", 0.9, "regex")

    if _PROFILE_UPDATE_RE.search(text):
        return IntentResult("profile_update", 0.85, "regex")

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
    # Check explicit job search FIRST (has job/role/position keyword)
    if _JOB_SEARCH_EXPLICIT_RE.search(text):
        # Try to extract an explicit "find jobs for <role>" target so the handler
        # can search for that role directly instead of falling back to profile roles.
        for_role_m = _JOB_SEARCH_FOR_ROLE_RE.search(text)
        extracted_role = for_role_m.group(1).strip() if for_role_m else None
        return IntentResult("job_search_explicit", 0.85, "regex", extracted_role=extracted_role)

    # Arabic application-history / tracking query MUST be checked before the
    # Arabic job-search heuristic.  "طلب" (request) is a substring of "الطلب"
    # (the application) and "وظيفه" (job) appears in history questions like
    # "كم وظيفة قمت بالتقديم عليها" — without this guard such questions are
    # misrouted to a brand-new job search instead of the application tracker.
    if has_arabic and _is_arabic_application_query(lower):
        return IntentResult("application_tracking", 0.85, "regex")

    # Arabic job search: request verb + job noun, or request verb + English role name
    if has_arabic and _is_arabic_job_search(lower, has_cv=has_cv_profile):
        role = _extract_english_role_from_mixed(text)
        return IntentResult("job_search_explicit", 0.85, "regex", extracted_role=role)

    # Role change — only if no explicit job-search keyword present
    role_match = _ROLE_CHANGE_RE.match(text)
    if role_match:
        return IntentResult("role_change", 0.9, "regex", extracted_role=role_match.group(2).strip())

    # ── 5. Profile-match inference (only if CV exists) ───────────────────
    # Generic short requests with CV profile → profile match, NOT job search
    _GENERIC_MATCH_WORDS = {"match", "matches", "matching", "suitable", "fit", "recommend"}
    if has_cv_profile and any(w in lower.split() for w in _GENERIC_MATCH_WORDS):
        return IntentResult("job_search_profile_match", 0.8, "regex")

    # ── 6. Unknown — DO NOT default to job search ────────────────────────
    return IntentResult("unknown", 0.0, "fallback")

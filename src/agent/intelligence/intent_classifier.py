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
    "where can i see it",
    "where is it",
    "what about the job i just applied to",
    "what about the job i just tracked",
    "open application flow",
    "open applications",
])

_HELP_PHRASES = frozenset([
    "help", "menu", "options", "what can you do", "commands",
    "start", "get started", "what's next", "whats next", "what next",
    "what now", "show options", "show menu", "next steps",
    # Arabic "what now / what's the solution"
    "مالحل", "ما الحل", "مالحل الان", "مالحل الآن",
])

_SMALLTALK_PHRASES = frozenset([
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "ok", "okay", "cool", "great", "nice",
    "bye", "goodbye", "see you", "cheers",
    "hallo", "hola", "hi there", "salam", "marhaba", "ahlan",
    # Arabic greetings / social phrases (normalised: alef variants, ta marbuta)
    "مرحبا", "اهلا", "اهلا وسهلا", "السلام عليكم", "شكرا", "مع السلامه",
])

_PROFILE_SUMMARY_PHRASES = frozenset([
    "show my profile", "my profile", "profile summary",
    "what do you know about me", "my details",
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

_PROFILE_UPDATE_RE = re.compile(
    r"\b(update|change|set|modify|adjust)\b.{0,40}"
    r"\b(salary|city|location|preference|role|title|industry|experience|notice|email|phone|telegram)\b",
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
    r"^(Prepare application|Mark as applied|Track this job|Save job)\s*[—\-–]\s*(.+)\s+at\s+(.+?)$",
    re.IGNORECASE | re.DOTALL,
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
    "وظيفه", "وظائف", "عمل", "شغل",
    "فرصه", "فرص", "مهنه", "مهن",
    "شاغر", "شواغر", "وضيفه",
    "منصب", "مناصب",
])

# Arabic verbs / phrases expressing a job-search request
_ARABIC_REQUEST_TERMS = frozenset([
    "ابحث", "بحث", "دور", "اريد", "ابي", "ابغي",
    "احتاج", "محتاج", "شوف", "طلع", "جيب",
    "ساعدني", "ايجاد", "طلب",
])


def _normalize_arabic(text: str) -> str:
    """Remove diacritics and normalise Arabic letter variants before phrase lookup."""
    # Remove tashkeel (fatha, kasra, damma, sukun, shadda, tanwin, tatweel)
    text = re.sub(r"[ً-ٰٟـ]", "", text)
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
    # A standalone request verb from a user who has a CV is always a job-search request
    # e.g. "ابحث" alone = "search [for jobs for me]"
    return has_ar_job or has_en_content or has_cv


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

    # ── 3. Regex patterns (ordered by specificity) ───────────────────────

    if _CV_UPLOAD_RE.search(text):
        return IntentResult("cv_upload_or_parse", 0.95, "regex")

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
        }
        matched_intent = intent_map.get(action_raw, "job_action")
        return IntentResult(matched_intent, 0.95, "regex", extracted_title=title, extracted_company=company)

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

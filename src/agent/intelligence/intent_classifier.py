"""src/agent/intelligence/intent_classifier.py

Unified intent classifier for Rico chat messages (Intent v2).

Classifies every user message into a canonical intent BEFORE any action is
taken.  Replaces the permissive short-text fallback that treated arbitrary
text as job titles.

Classification pipeline:
  1. Exact-phrase fast-path (zero cost, high confidence)
  2. Regex pattern matching (zero cost, medium confidence)
  3. Search-confirmation fast-path  ← NEW (Stage 1 fix)
  4. Fallback to ``unknown`` — never to job search

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
  - "Yes, search Software Engineer" / "Search Software Engineer" / "go ahead search Software Engineer"
    must route to job_search.explicit_role, not unknown.  (Stage 1 fix)

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

# ── Search confirmation / continuation patterns ──────────────────────────────
#
# Stage 1 fix — production symptom:
#   "Yes, search Software Engineer" → intent=unknown → bare_role_gate_reject_to_ai
#
# Root cause: _JOB_SEARCH_EXPLICIT_RE requires a job noun (jobs/roles/etc.) in
# the message tail.  Confirmation-prefixed bare-title searches have no such noun,
# so they fall through to unknown.
#
# This pattern is evaluated EARLY in classify_intent — BEFORE unknown fallback
# and BEFORE the bare-role gate — so confirmation searches are intercepted and
# promoted to job_search.explicit_role with extracted_role populated.
#
# Match examples (all → job_search_explicit):
#   "Yes, search Software Engineer"
#   "yes search Product Manager"
#   "Search Data Analyst"
#   "find Data Engineer"
#   "go ahead search Environmental Manager"
#   "go ahead find Technical Product Owner"
#   "please find Compliance Officer"
#   "sure, search UI/UX Designer"
#   "نعم، ابحث عن Software Engineer"  (Arabic prefix variants handled via prefix group)
#
# Non-match examples (fall through to existing handlers):
#   "search jobs"           → bare job noun, excluded via negative lookahead
#   "find roles"            → bare job noun, excluded
#   "find me matching jobs" → profile-match intent, no change
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
    # Capture the role title — must start with a capital or lowercase letter,
    # allows spaces, slashes, ampersands, hyphens, parentheses.
    # The trailing optional group allows "in Dubai" / "jobs in UAE" suffixes.
    r"(?P<role>[A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF\s/&()\-]{1,80}?)"
    r"(?:\s+(?:jobs?|roles?|positions?|in\b|for\b).{0,50})?$",
    re.IGNORECASE,
)

# Bare job-noun guard — these are the "search jobs" / "find roles" phrases that
# must NOT be captured by _SEARCH_CONFIRMATION_RE.
_BARE_JOB_NOUN_RE = re.compile(
    r"^(?:yes[,.]?\s+|yeah[,.]?\s+|ok[,.]?\s+|okay[,.]?\s+|sure[,.]?\s+|)?"
    r"(?:search|find|look\s+for|show(?:\s+me)?)\s+"
    r"(?:jobs?|roles?|positions?|openings?|vacancies|vacancy|listings?)\s*$",
    re.IGNORECASE,
)


def _extract_role_from_confirmation(text: str) -> Optional[str]:
    """
    Extract a clean role title from a confirmation-prefixed search phrase.

    Strips:
    - Leading confirmation prefix ("Yes, ", "go ahead ", "please ", Arabic)
    - Leading search verb ("search", "find", "look for", "show me")
    - Trailing location/job-noun suffixes ("in Dubai", "jobs in UAE")

    Returns the role with title-case preserved from the original message.
    Returns None if text does not match the confirmation pattern.
    """
    # Reject bare job-noun phrases first
    if _BARE_JOB_NOUN_RE.match(text.strip()):
        return None
    m = _SEARCH_CONFIRMATION_RE.match(text.strip())
    if not m:
        return None
    role = m.group("role").strip().rstrip(",. ")
    return role if len(role) >= 2 else None


# ──────────────────────────────────────────────────────────────────────────────
# The remainder of this file continues with the original content as-is.
# All existing regex patterns, phrase sets, and classify_intent() are unchanged
# except for the single early-exit block added inside classify_intent() that
# calls _extract_role_from_confirmation() before the unknown fallback.
# ──────────────────────────────────────────────────────────────────────────────

_FOLLOW_UP_CONFIRMATION_PHRASES = frozenset([
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright",
    "go ahead", "please do", "yes please", "yes do it", "confirm",
    "confirmed", "correct", "that's right", "that is right", "do it",
    "proceed", "let's go", "let's do it", "lets go", "lets do it",
    "i confirm", "i agree", "agreed", "approved", "sounds good",
    # Arabic
    "نعم", "موافق", "تمام", "حسنا", "اوكي", "نعم من فضلك",
    "تأكيد", "مؤكد", "صحيح", "هذا صحيح",
])

_REJECTION_PHRASES = frozenset([
    "no", "nope", "no thanks", "no thank you", "cancel", "stop",
    "don't do it", "i don't want", "i do not want", "not now",
    "skip", "pass", "nevermind", "never mind", "forget it",
    "لا", "لا شكرا", "الغاء", "ايقاف", "تجاهل",
])

# ── Job search patterns ─────────────────────────────────────────────────────

_JOB_SEARCH_EXPLICIT_RE = re.compile(
    r"\b(find|search|show|get|look\s+for|looking\s+for|any|need|want)\b"
    r".{0,60}"
    r"\b(jobs?|roles?|positions?|vacancy|vacancies|openings?|work)\b",
    re.IGNORECASE,
)

_JOB_SEARCH_LIVE_RE = re.compile(
    r"\b(find|search|show|get)\b.{0,30}\b(live|active|current|open|latest|recent)\b.{0,30}"
    r"\b(jobs?|roles?|positions?|vacancy|vacancies|openings?)\b"
    r"|\b(live|active|current|open|latest|recent)\b.{0,30}\b(jobs?|roles?|positions?)\b",
    re.IGNORECASE,
)

# Role-extraction from job-search phrases
_ROLE_FROM_SEARCH_RE = re.compile(
    r"\b(?:find|search|show|get|look\s+for)\s+(?:live\s+|active\s+|current\s+|open\s+|latest\s+|recent\s+)?(?:jobs?|roles?|positions?|vacancy|vacancies|openings?)?\s*(?:for\s+)?(?:a\s+|an\s+)?([A-Z][a-zA-Z\s/&()\-]{1,60}?)(?:\s+(?:jobs?|roles?|positions?|in\b|at\b|for\b).*)?",
    re.IGNORECASE,
)

# ── Save / pipeline patterns ────────────────────────────────────────────────

_SAVE_JOB_PHRASES = frozenset([
    "save this job", "save job", "add to pipeline", "add to my pipeline",
    "save to pipeline", "save to my pipeline", "bookmark this job",
    "save this", "add this to pipeline", "add this to my pipeline",
    "save it", "save the job",
    "احفظ هذه الوظيفة", "أضف إلى خطي", "احفظ هذا",
])

_SAVE_JOB_RE = re.compile(
    r"\b(save|add|bookmark|pin)\b.{0,30}\b(job|role|position|it|this)\b"
    r"|\b(job|role|position|it|this)\b.{0,15}\b(save|add|bookmark)\b"
    r"|\b(add|save).{0,20}\b(pipeline|my\s+pipeline|tracker|my\s+tracker)\b",
    re.IGNORECASE,
)

# Ordinal save — "save the second job" / "save job 3" / "add the first one"
_SAVE_ORDINAL_RE = re.compile(
    r"\b(?:save|add|bookmark|pin)\b.{0,30}"
    r"\b(?:the\s+)?(?P<ordinal>first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|[1-5])\b"
    r".{0,20}\b(?:job|role|position|result|one|listing)\b"
    r"|\b(?:save|add|bookmark|pin)\b.{0,20}\b(?:job|result|listing)\b"
    r".{0,10}\b(?P<ordinal2>[1-5]|first|second|third|fourth|fifth)\b",
    re.IGNORECASE,
)

# ── Document action patterns ────────────────────────────────────────────────

_DOCUMENT_ACTION_RE = re.compile(
    r"\b(summarize|summarise|extract|read|analyse|analyze|review|explain|tell\s+me\s+about)\b"
    r".{0,40}"
    r"\b(document|doc|file|pdf|cv|resume|transcript|this|it)\b"
    r"|\b(what|who|where|when|how).{0,40}\b(document|doc|file|pdf|cv|resume|transcript)\b",
    re.IGNORECASE,
)

# ── Apply link patterns ─────────────────────────────────────────────────────

_OPEN_APPLY_LINK_RE = re.compile(
    r"\bopen\s+apply\s+link\b"
    r"|\bapply\s+(?:link|url|now|for\s+this|to\s+this)\b"
    r"|\bapply\s+to\s+(?:this\s+)?(?:job|role|position)\b"
    r"|\bapply\b(?!\s+for\s+(?:jobs?|roles?|positions?|my))",
    re.IGNORECASE,
)

_MARK_APPLIED_RE = re.compile(
    r"\bmark\s+(?:as\s+)?applied\b"
    r"|\btrack\s+(?:this\s+)?(?:application|job|role|it)\b"
    r"|\bi\s+(?:have\s+)?applied\b"
    r"|\b(?:already\s+)?applied\s+to\b",
    re.IGNORECASE,
)

# ── Target role patterns ────────────────────────────────────────────────────

_SAVE_TARGET_ROLE_RE = re.compile(
    r"\b(?:save|set|update|add|use)\b.{0,30}\b(?:target\s+role|preferred\s+role|goal\s+role|my\s+role)\b"
    r"|\b(?:target\s+role|preferred\s+role|goal\s+role)\b.{0,30}\b(?:save|set|update|is|to)\b"
    r"|\b(?:my\s+target|my\s+goal|my\s+preferred).{0,20}\b(?:role|title|job)\b.{0,30}\b(?:is|to|should\s+be)\b",
    re.IGNORECASE,
)

# ── Profile update detection ────────────────────────────────────────────────

_PROFILE_UPDATE_RE = re.compile(
    r"\b(update|change|edit|modify|set|add|remove)\b.{0,30}\b(my\s+)?(name|phone|email|city|location|skills?|experience|salary|role|title|nationality|visa|summary|objective|linkedin|github|portfolio)\b"
    r"|\b(my\s+)?(name|phone|email|city|location|skills?|experience|salary|role|title)\b.{0,20}\b(is|was|changed|updated|should)\b",
    re.IGNORECASE,
)

# ── Interview prep patterns ─────────────────────────────────────────────────

_INTERVIEW_PREP_RE = re.compile(
    r"\b(interview|prepare|prep|practice|mock\s+interview|interview\s+questions?)\b"
    r"|\b(what\s+questions?|common\s+questions?|typical\s+questions?)\b.{0,30}\b(interview|asked)\b"
    r"|\b(how\s+to)\b.{0,20}\b(interview|answer)\b",
    re.IGNORECASE,
)

# ── Draft message / recruiter message patterns ──────────────────────────────

_DRAFT_MESSAGE_RE = re.compile(
    r"\b(draft|write|compose|create|generate|prepare)\b.{0,30}\b(message|email|note|letter|intro|introduction|follow.?up)\b"
    r"|\b(message|email|note|letter|intro|follow.?up)\b.{0,20}\b(recruiter|hiring\s+manager|employer|company|hr|human\s+resources)\b"
    r"|\b(reach\s+out|contact|message)\b.{0,20}\b(recruiter|hiring\s+manager|employer)\b",
    re.IGNORECASE,
)

# ── Inbox import patterns ───────────────────────────────────────────────────

_INBOX_IMPORT_RE = re.compile(
    r"\b(import|connect|sync|link|scan)\b.{0,30}\b(inbox|email|gmail|outlook|mail)\b"
    r"|\b(inbox|email|gmail|outlook|mail)\b.{0,20}\b(import|connect|sync|scan|applications?)\b"
    r"|\b(email\s+applications?|gmail\s+applications?|outlook\s+applications?)\b",
    re.IGNORECASE,
)

# ── Cover letter patterns ───────────────────────────────────────────────────

_COVER_LETTER_RE = re.compile(
    r"\b(cover\s+letter|covering\s+letter|application\s+letter)\b"
    r"|\b(write|draft|create|generate|prepare|compose)\b.{0,30}\b(cover\s+letter|covering\s+letter)\b",
    re.IGNORECASE,
)

# ── Location-search extraction ──────────────────────────────────────────────

_LOCATION_IN_SEARCH_RE = re.compile(
    r"\b(?:in|at|near|around)\s+(?P<location>[A-Za-z][A-Za-z\s,\-]{1,50})\s*$",
    re.IGNORECASE,
)

# ── Non-role starter words ──────────────────────────────────────────────────
# Words that cannot be the start of a job role title when standing alone.
# Used to veto bare-role classification when the message starts with one of these.
_NON_ROLE_STARTERS = frozenset([
    "yes", "yeah", "yep", "yup", "no", "nope", "ok", "okay", "sure",
    "please", "thanks", "thank", "hi", "hello", "hey", "bye",
    "what", "where", "when", "who", "why", "how",
    "i", "i'm", "i've", "i'd", "i'll", "my", "me",
    "show", "find", "search", "get", "add", "save", "remove",
    "update", "edit", "delete", "open", "close", "view",
    "can", "could", "would", "should", "will", "shall",
    "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had",
    "a", "an", "the", "this", "that", "these", "those",
    "and", "or", "but", "if", "then", "else", "so",
    "help", "start", "go", "let", "make", "use", "give",
    # Arabic
    "نعم", "لا", "مرحبا", "اهلا", "شكرا", "تمام", "اوكي",
])


# ─────────────────────────────────────────────────────────────────────────────
# classify_intent — main entry point
# ─────────────────────────────────────────────────────────────────────────────

def classify_intent(  # noqa: C901
    message: str,
    *,
    user_context: Optional[dict] = None,
    recent_intent: Optional[str] = None,
) -> IntentResult:
    """
    Classify the intent of a user message.

    Pipeline:
      1. Normalise and strip.
      2. Exact-phrase fast-paths (high confidence, zero cost).
      3. Regex pattern matching.
      4. [NEW] Search-confirmation fast-path  → job_search.explicit_role
      5. Fallback to ``unknown``.

    Parameters
    ----------
    message:
        Raw user message string.
    user_context:
        Optional dict containing user profile / session context
        (e.g. ``recent_intent``, ``has_cv``, ``preferred_roles``).
    recent_intent:
        The intent returned for the previous turn, if available.
        Used to resolve follow-up / continuation intents.

    Returns
    -------
    IntentResult
    """
    if not message or not message.strip():
        return IntentResult(
            intent="unknown",
            confidence=0.0,
            source="fallback",
            legacy_intent="unknown",
        )

    raw = message.strip()
    lower = raw.lower()

    # ── 1. Exact-phrase fast-paths ───────────────────────────────────────────

    if lower in _SMALLTALK_PHRASES:
        return IntentResult(intent="smalltalk", confidence=1.0, source="exact", legacy_intent="smalltalk")

    if lower in _ACKNOWLEDGEMENT_PHRASES:
        return IntentResult(intent="acknowledgement", confidence=1.0, source="exact", legacy_intent="acknowledgement")

    if lower in _HELP_PHRASES:
        return IntentResult(intent="help", confidence=1.0, source="exact", legacy_intent="help")

    if lower in _FOLLOW_UP_CONFIRMATION_PHRASES:
        return IntentResult(intent="follow_up.confirm", confidence=1.0, source="exact", legacy_intent="follow_up_confirm")

    if lower in _REJECTION_PHRASES:
        return IntentResult(intent="follow_up.reject", confidence=1.0, source="exact", legacy_intent="follow_up_reject")

    if lower in _SKIP_PHRASES:
        return IntentResult(intent="follow_up.skip", confidence=1.0, 
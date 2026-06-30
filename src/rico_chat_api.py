"""Rico conversational AI API.

This module transforms the existing automation system into a chat-first
career agent. Rico accepts natural language messages, updates memory,
triggers workflows, and responds with autonomous actions.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace as _dc_replace
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, NamedTuple

# Standard library imports first
# Third-party imports (none currently)
# Local imports
from src.agent.intelligence.intent_classifier import (
    classify_intent,
    _LEGACY_INTENT_MAP,
    _map_intent_to_legacy,
    _OPEN_APPLY_LINK_RE,
    _OPEN_APPLY_LINK_ORDINAL_RE,
    _SAVE_JOB_ORDINAL_RE,
    _SAVE_JOB_ORDINAL_AR_RE,
)
from src.agent.intelligence.normalizer import normalize_role
from src.agent.intelligence.recommender import recommend_adjacent_roles
from src.agent.intelligence.role_classifier import classify_role_candidate
from src.agent.intelligence.role_suggester import (
    generate_role_suggestions as _suggest_roles,
    needs_clarification as _needs_clarification,
)
from src.agent.intelligence.scorer import score_profile_fit
from src.agent.responses.schema import RicoResponse, build_error_response, _generate_debug_id
from src.agent.runtime import agent_runtime
from src.models.onboarding import ONBOARDING_IN_PROGRESS
from src.rico_agent import RicoAgent
from src.rico_hf_client import generate_text, is_available as hf_ok
from src.rico_intent_router import route as _route
from src.rico_match_explainer import build_match_explanation
from src.rico_memory import RicoMemoryStore
from src.rico_openai_agent import RicoOpenAIAgent
from src.rico_repo_adapter import RicoSystem
from src.repositories.onboarding_repo import (
    is_onboarding_complete,
    mark_onboarding_complete,
    set_onboarding_status,
)
from src.repositories.profile_repo import get_profile, upsert_profile
from src.services.profile_context_resolver import (
    evaluate_minimum_profile,
    resolve_profile_context,
)
from src.services.operation_state import (
    mark_completed,
    mark_failed,
    start_job_search_operation,
)

logger = logging.getLogger(__name__)


# _LEGACY_INTENT_MAP and _map_intent_to_legacy are imported from intent_classifier above.

# Constants
_SESSION_JOB_SEARCH_HISTORY_LIMIT = 10
_SESSION_JOB_SEARCH_HISTORY: dict[str, list[dict[str, Any]]] = {}

CV_FILE_RE = re.compile(r"\b[\w .()_-]+\.(?:pdf|docx?|txt)\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
FOLLOWUP_BOUNDARY_PUNCT_RE = re.compile(r"^[\s\"'([{]+|[\s\"')\]}.,!?;:]+$")
# Single-letter choice: exactly one letter A–D (upper or lower) with optional trailing
# punctuation/whitespace.  "apple", "AB", "a b" do NOT match.
_LETTER_CHOICE_RE = re.compile(r"^[A-Da-d][.:\s]*$")
# Single-digit numeric choice: exactly one digit 1–9 with optional trailing
# punctuation/whitespace.  "30", "3 years", "3.5" do NOT match.
_NUMBER_CHOICE_RE = re.compile(r"^[1-9][.:\s]*$")
PROFILE_LIST_SPLIT_RE = re.compile(r"[,;\n\r|]+")
# Telegram username: @handle (5–32 chars, alphanumeric + underscore)
TELEGRAM_HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
# Telegram declaration in natural language: "my telegram is @handle", "@handle" etc.
TELEGRAM_MENTION_RE = re.compile(
    r"(?:my\s+)?telegram(?:\s+(?:username|handle|id|account|is|:))?\s+(?:is\s+)?(@[A-Za-z0-9_]{5,32})"
    r"|(?:^|\s)(@[A-Za-z0-9_]{5,32})(?:\s|$)",
    re.IGNORECASE,
)

# Settings/Notification commands: enable/disable notifications and alerts
_SETTINGS_NOTIFICATION_ENABLE_RE = re.compile(
    r"\b(?:enable|turn\s+on|activate|start)\s+(?:telegram\s+)?(?:notifications?|alerts?|reminders?)\b",
    re.IGNORECASE,
)
_SETTINGS_NOTIFICATION_DISABLE_RE = re.compile(
    r"\b(?:disable|turn\s+off|deactivate|stop)\s+(?:telegram\s+)?(?:notifications?|alerts?|reminders?)\b",
    re.IGNORECASE,
)
_SETTINGS_SHOW_RE = re.compile(
    r"\b(?:open\s+)?(?:notification\s+)?settings\b|\b(?:manage|change)\s+(?:notifications?|alerts?)\b",
    re.IGNORECASE,
)

# Job card "Mark as applied" action commands — must route to legacy mark_applied handler,
# NOT the manual application status update flow. Pattern: "Mark as applied — Title at Company"
_MARK_APPLIED_CARD_ACTION_RE = re.compile(
    r"^\s*mark\s+as\s+applied\s*[-—–]\s*"  # "Mark as applied —" or "Mark as applied -"
    r".+\s+at\s+.+"  # Must have "Title at Company" structure
    r"|\s*mark\s+as\s+applied\s+[-—–]\s*.+\s+at\s+.+"  # Variant with leading space
    r"|\s*mark\s+as\s+applied\s*:\s*.+\s+at\s+.+"  # Variant with colon
    r"|\s*mark\s+(?:it|this|the\s+job)\s+as\s+applied\s+[-—–:]\s*.+\s+at\s+.+"  # "mark it as applied —"
    r"|\s*mark\s+(?:it|this)\s+as\s+applied\s+(?:for|to)\s+.+\s+at\s+.+"  # "mark it as applied for X at Y"
    ,
    re.IGNORECASE,
)

# CV improvement follow-up phrases — used ONLY when last_flow_state == "cv_builder".
# Never apply this pattern without flow-state context or it will misfire on
# "improve my cover letter", "enhance it" for other content, etc.
_CV_IMPROVE_FOLLOWUP_RE = re.compile(
    # English: standalone improvement requests (no "cv"/"resume" word needed)
    r"\bplease\s+improve\s+it\b"
    r"|\bimprove\s+it\b"
    r"|\benhance\s+it\b"
    r"|\bmake\s+it\s+(better|shorter|longer|more\s+professional|professional)\b"
    r"|\brefine\s+it\b"
    r"|\btailor\s+it\b"
    # Arabic: "improve it [professionally]"
    r"|(?:نعم\s+)?حسنها(?:\s+بشكل\s+احتراف(?:ي|ياً?))?"
    r"|(?:نعم\s+)?طورها"
    r"|احسنها"
    r"|حسّنها"
    # Arabic: "improve/develop the CV"
    r"|(?:نعم\s+)?حسن\s+(?:ال)?سير[هة](?:\s+(?:ال)?ذاتي[هة])?"
    r"|(?:نعم\s+)?طور\s+(?:ال)?سير[هة](?:\s+(?:ال)?ذاتي[هة])?",
    re.IGNORECASE | re.UNICODE,
)

# Follow-up requests that act on a just-uploaded image/document — the button
# payloads from the Document Intelligence layer ("Describe what's in this image.",
# "Extract any visible text from this image.", "Summarize this document for me.",
# "Extract the most important information from this document.") plus close natural
# variants. Handled deterministically from the stored transcript BEFORE the
# onboarding / CV-builder routing so an image action can never be hijacked into a
# CV draft. Only fires when a recent uploaded document is in session context.
_DOC_FOLLOWUP_RE = re.compile(
    r"\bdescribe\b.{0,30}\b(image|picture|photo|screenshot|document|file|it)\b"
    r"|\bwhat(?:'?s| is| does)\b.{0,30}\b(in|on|say|says|contain)\b.{0,24}\b(image|picture|photo|screenshot|document|file|it)\b"
    r"|\bextract\b.{0,40}\b(text|information|info|details)\b"
    r"|\bsummari[sz]e\b.{0,30}\b(this|the|image|document|file|content|key|it)\b"
    r"|\b(read|ocr)\b.{0,30}\b(image|picture|photo|screenshot|document|file|text|it)\b",
    re.IGNORECASE,
)

# Job-document action regexes — intercept "Save as target job" and "Score against my CV"
# from the suggested-action buttons (document_classifier._SUGGESTED_ACTIONS["job_description"]).
# These run inside _handle_uploaded_document_followup BEFORE _DOC_FOLLOWUP_RE so they are
# never mis-routed to the onboarding / CV-builder / generic AI path.
# IMPORTANT: keep these narrow enough not to catch ordinal saves ("save the second job").
_JOB_DOC_SAVE_RE = re.compile(
    r"\bsave\b.{0,50}\bas\s+(?:a\s+)?target\s+job\b"
    r"|\bsave\b.{0,20}\bthis\b.{0,30}\b(?:to\s+(?:my\s+)?pipeline|as\s+target)\b"
    r"|\badd\b.{0,15}\bthis\b.{0,30}\bpipeline\b",
    re.IGNORECASE,
)
_JOB_DOC_SCORE_RE = re.compile(
    r"\bscore\b.{0,60}\b(?:cv|resume|profile)\b"
    r"|\b(?:match|compare)\b.{0,40}\b(?:cv|resume|profile)\b"
    r"|\bfit\s+score\b"
    r"|\bhow\s+(?:well|good)\b.{0,60}\b(?:fit|match|qualify)\b.{0,40}\b(?:this\s+job|job\s+desc)",
    re.IGNORECASE,
)
# Simple heuristics for extracting job title / company from a raw transcript.
_JOB_TITLE_FROM_TEXT_RE = re.compile(
    r"(?:job\s+title|position|role|title)\s*[:\-]\s*([^\n]{3,80})",
    re.IGNORECASE,
)
_JOB_COMPANY_FROM_TEXT_RE = re.compile(
    r"(?:company|employer|organization|client)\s*[:\-]\s*([^\n]{2,60})",
    re.IGNORECASE,
)

# Strings that must never appear inside a deterministic CV draft body.
# Used as a post-generation guard in _handle_cv_generate_from_profile.
_CV_PLACEHOLDER_PATTERNS = re.compile(
    r"\[Start\s+Date\]"
    r"|\[End\s+Date\]"
    r"|\[Company\s+Name\]"
    r"|\[Job\s+Title\]"
    r"|\[Add\s+\w"
    r"|Add\s+\d+.{0,20}responsibilities\s+here"
    r"|\bTBD\b"
    r"|\bassumed\b"
    r"|please\s+confirm(?:\s+inside)?",
    re.IGNORECASE,
)

# Domain-agnostic. A bare role is a short noun phrase. Anything starting with
# one of these tokens is a question, command, greeting, or sentence - never
# a role title.
_NON_ROLE_STARTERS: frozenset[str] = frozenset({
    "what", "whats", "what's", "how", "hows", "how's", "why", "when",
    "where", "who", "whom", "whose", "which",
    "is", "are", "am", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "done",
    "have", "has", "had", "having",
    "will", "would", "shall", "should", "can", "could",
    "may", "might", "must", "ought",
    "tell", "show", "give", "find", "search", "get", "fetch", "list",
    "explain", "describe", "compare", "help", "please",
    "want", "need", "looking",
    # Gerunds of action verbs — never start a job title
    # "listing" excluded: "Listing Agent" is a real UAE/real-estate role title
    "finding", "searching", "showing", "getting", "fetching",
    "tailoring", "improving", "updating", "tracking",
    "hi", "hello", "hey", "greetings", "thanks", "thank", "ok", "okay",
    "yes", "yeah", "yep", "ya", "no", "nope", "sure", "fine", "good", "great",
    "cool", "nice", "wow", "oh", "ah",
    "i", "im", "i'm", "me", "my", "mine", "myself",
    "we", "our", "ours", "us",
    "the", "a", "an", "this", "that", "these", "those",
    "some", "any", "every", "all", "none", "each", "many", "few",
    "and", "but", "or", "so", "if", "because", "though", "while", "as",
    # Imperative command / toggle verbs — start a settings command, never a job title
    "enable", "disable", "turn", "activate", "deactivate",
    "mute", "unmute", "configure", "connect",
    # Verb imperatives missing from earlier list — never start a job title
    "make", "look", "write", "draft",
    # Common action imperatives — never start a job title
    "create", "generate", "send", "change", "apply", "submit", "check",
    "review", "save", "build", "prepare", "edit", "add", "remove", "start",
    "open", "try", "set", "use", "share", "update", "improve", "track",
    # Pipeline / state management verbs — never start a job title
    "clear", "reset",
    # Gerund forms of the above that were missing
    "creating", "generating", "sending", "changing", "applying", "submitting",
    "checking", "reviewing", "saving", "building", "preparing", "editing",
    "adding", "removing", "starting", "opening", "setting", "sharing",
})
_QUESTION_CHARS: frozenset[str] = frozenset("?？!！;:")
_MAX_ROLE_WORDS: int = 6

# Location names that are never valid job-role titles. A message consisting
# entirely of these terms (e.g. "UAE", "Dubai", "jobs in UAE") should redirect
# to a profile-based search, not a role-classification error.
_LOCATION_TERMS: frozenset[str] = frozenset({
    # Country / region
    "uae", "emirates", "united arab emirates",
    # UAE cities / emirates
    "dubai", "abu dhabi", "abudhabi", "sharjah", "ajman",
    "ras al khaimah", "ras al-khaimah", "fujairah", "umm al quwain",
    "umm al-quwain",
    # GCC / region
    "gcc", "gulf", "middle east", "mena",
    # Arabic equivalents (normalised, no diacritics)
    "الإمارات", "الامارات", "دبي", "أبوظبي", "ابوظبي",
    "الشارقة", "الشارقه", "عجمان", "رأس الخيمة", "راس الخيمه",
    "الفجيرة", "الفجيره", "أم القيوين", "ام القيوين",
})
_MIN_TOKEN_ALPHA: int = 2

# Role values that users leave as default placeholders and that cannot drive a
# useful JSearch query.  Treat them as "no target role set" so the classifier
# falls through to role-suggestion prompts instead of returning irrelevant jobs.
_PLACEHOLDER_ROLE_VALUES: frozenset[str] = frozenset({
    "any", "all", "any role", "all roles", "open", "open to any",
    "open to all", "any position", "any job", "any jobs",
    "not specified", "tbd", "n/a",
})

# Settings / notification commands ("enable telegram notifications", "turn off
# email alerts", "disable reminders"). These are not job roles and not job
# searches — route them to Settings guidance instead of role classification.
_SETTINGS_COMMAND_RE = re.compile(
    r"\b(enable|disable|turn\s+(?:on|off)|activate|deactivate|mute|unmute|"
    r"switch\s+(?:on|off)|stop|start)\b"
    r".{0,40}"
    r"\b(notification|notifications|alert|alerts|telegram|whatsapp|reminder|reminders)\b",
    re.IGNORECASE,
)

# UAE-wide search expansion: "look all over UAE", "search all UAE", "all over UAE",
# "look across uae" — user wants to widen a previous search to the whole country.
_UAE_WIDE_SEARCH_RE = re.compile(
    # "all over/across/around [the] UAE"
    r"\ball\s+(?:over|across|around)\s+(?:the\s+)?(?:uae|emirates)\b"
    # "search/look/find all [of] UAE" — but not "find all UAE jobs" (role follows UAE)
    r"|\b(?:look|search|find)\s+all\s+(?:of\s+|the\s+)?(?:uae|emirates)(?!\s+(?:jobs?|roles?|vacancies))\b"
    # "look/search across/around [the] UAE"
    r"|\b(?:look|search|find)\b.{0,15}\b(?:across|around)\b.{0,20}\b(?:uae|emirates)\b"
    # "look all over [the] UAE"
    r"|\blook\s+all\s+over\s+(?:the\s+)?(?:uae|emirates)\b"
    # "expand/broaden/widen [my search] to/across UAE"
    r"|\b(?:expand|broaden|widen)\b.{0,25}\b(?:uae|emirates)\b"
    # "entire/whole [the] UAE"
    r"|\b(?:entire|whole)\s+(?:the\s+)?(?:uae|emirates)\b"
    # "anywhere in [the] UAE"
    r"|\banywhere\s+in\s+(?:the\s+)?(?:uae|emirates)\b"
    # "UAE-wide" / "UAE wide"
    r"|\b(?:uae|emirates)[- ]wide\b",
    re.IGNORECASE,
)

# Cover-letter command: "make me a cover [letter]", "write a cover letter",
# "draft a cover letter" — route to the cover-letter clarification flow before
# the intent classifier, which returns "unknown" for bare "cover" forms.
_COVER_LETTER_COMMAND_RE = re.compile(
    # "write/make/draft/create/generate/prepare [me/a/my] cover [letter] [for ...]"
    # No end-anchor so trailing context ("for ADNOC", "for the HSE role") still matches.
    r"\b(?:write|make|draft|create|generate|prepare)\b.{0,30}\bcover(?:\s+letter)?\b"
    # "I need/want a cover letter" — common phrasing without a command verb
    r"|\b(?:need|want)\b.{0,15}\bcover\s+letter\b",
    re.IGNORECASE,
)

# "Retry / again / show more" — user wants to replay or extend the last job search.
# Bare retry phrases and "show more jobs" / "any new jobs?" are intercepted before
# classify_intent; longer messages with these words still pass through normally.
_RETRY_SEARCH_RE = re.compile(
    r"^(?:retry|again|repeat|redo|run\s+it\s+again|search\s+again|"
    r"same\s+search|once\s+more|try\s+again|re[- ]?run)\s*[.!?]?$"
    r"|^(?:show\s+more(?:\s+(?:jobs?|results?|listings?|options?|roles?))?"
    r"|more\s+(?:jobs?|results?|listings?|roles?)"
    r"|(?:any\s+)?(?:new|other|more)\s+(?:jobs?|roles?|results?|openings?|listings?|vacancies)"
    r"|(?:show|find)\s+(?:more|other|different)\s+(?:jobs?|roles?|options?)"
    r"|load\s+more)\s*[.!?]?$"
    r"|^(?:مرة\s+أخرى|مجددا|مجدداً|أعد\s+البحث|كرر\s+البحث|نفس\s+البحث"
    r"|وظائف\s+أخرى|أكثر\s+من\s+ذلك|عرض\s+المزيد|هل\s+يوجد\s+غيرها)\s*[.!?]?$",
    re.IGNORECASE,
)

# Application withdrawal: "withdraw my application", "cancel my application",
# Arabic equivalents — must route before intent classifier (returns "unknown").
_APPLICATION_WITHDRAW_RE = re.compile(
    r"\b(?:withdraw|cancel|retract|pull\s+out|recall)\b.{0,35}"
    r"\b(?:application|apply|applied|submission|candidacy|request)\b"
    r"|\b(?:application|candidacy)\b.{0,25}\b(?:withdraw|cancel|retract)\b"
    r"|\b(?:سحب|اسحب|ألغ|إلغاء)\b.{0,25}\b(?:الطلب|التقديم|ترشيح)",
    re.IGNORECASE,
)

# Profile completeness query: "what's missing from my profile?", "is my profile complete?"
# Routes to a deterministic completeness report using evaluate_minimum_profile.
_PROFILE_COMPLETE_RE = re.compile(
    r"\b(?:what(?:'s|\s+is)?(?:\s+still)?)\s+missing\s+(?:from\s+)?(?:my\s+)?profile\b"
    r"|\bis\s+my\s+profile\s+(?:complete|ready|done|strong|finished|enough)\b"
    r"|\b(?:what\s+(?:do\s+I\s+)?(?:need\s+to\s+)?(?:add|fill\s+in|complete|update))\b.{0,25}\bprofile\b"
    r"|\bprofile\s+(?:completeness|gaps?|status|strength)\b"
    r"|\b(?:complete|finish|finalize)\s+my\s+profile\b"
    r"|\b(?:ما|ماذا)\s+(?:يحتاج|ينقص|ناقص)\b.{0,20}\bالملف\b"
    r"|\bملفي\s+الشخصي\s+(?:مكتمل|ناقص|جاهز)\b",
    re.IGNORECASE,
)

# Application status query (user asking for updates, not reporting a submission).
# Intercept before classify_intent to route to application_tracking, not status_update.
_APPLICATION_STATUS_QUERY_RE = re.compile(
    r"\b(?:any|got\s+any)\s+(?:update|reply|response|news|feedback)s?\s+"
    r"(?:on|about|from|for)?\s*(?:my\s+)?applications?\b"
    r"|\bwhat(?:'s|\s+is)?\s+(?:happening|going\s+on)\s+with\s+my\s+applications?\b"
    r"|\b(?:have|has)\s+(?:anyone|any\s+(?:company|employer))\s+(?:replied|responded|contacted)\b"
    r"|\bany\s+(?:interviews?|callbacks?|responses?|rejections?|offers?)\s*[.!?]?\s*$"
    r"|\bhow\s+(?:are|is)\s+(?:my\s+)?applications?\s+(?:going|doing)\b"
    r"|\b(?:أي|هل)\s+(?:ردود?|أخبار|تحديثات?)\s+(?:على|عن)?\s*(?:طلباتي|التقديمات)\b",
    re.IGNORECASE,
)

# Salary expectation setting: "my minimum salary is 50k", "set salary to 60000 AED/month".
# Conservative pattern — requires explicit salary/pay keyword to avoid false positives.
_SALARY_SET_RE = re.compile(
    r"\b(?:my\s+)?(?:minimum|expected?|target|desired?)\s+salary\s+is\s*(?:AED\s*)?(\d[\d,.]*)([Kk]?)\b"
    r"|\b(?:set|update|change)\s+(?:my\s+)?salary\s+(?:expectation\s+)?to\s*(?:AED\s*)?(\d[\d,.]*)([Kk]?)\b"
    r"|\bI\s+(?:want|expect|need|require)\s+(?:at\s+least\s+)?(?:AED\s*)?(\d[\d,.]*)([Kk]?)\s*(?:AED\s*)?"
    r"(?:per\s+month|\/month|monthly|a\s+month)\b"
    r"|\براتبي\s+(?:المتوقع|الأدنى|المرغوب)\s*(?:AED\s*|درهم\s*)?(\d[\d,.]*)([Kk]?)"
    r"|\براتبي\s+(?:المتوقع|الأدنى|المرغوب)\b.{0,30}\b(?:ألف|آلاف|مئة\s+ألف|مائة\s+ألف)\b"
    r"|\b(?:أريد|أتوقع|أحتاج)\s+(?:راتب|أجر)\b.{0,25}\b(?:\d[\d,.]*[Kk]?|ألف|آلاف)\b",
    re.IGNORECASE,
)

# Job detail inquiry: "tell me more about that job", "more details on the first one",
# "what's the job description?" — shows extended cached fields from recent_search_matches.
_JOB_DETAIL_RE = re.compile(
    r"\b(?:tell\s+me\s+more|more\s+(?:details?|info(?:rmation)?)|describe)\s+"
    r"(?:(?:about|on|for|of)\s+)?(?:that|this|the\s+(?:first|second|third|last|top))?\s*(?:job|role|position|opportunity|one)\b"
    r"|\b(?:what(?:'s|\s+is)?\s+the\s+(?:job\s+)?description|job\s+details?|role\s+details?)\b"
    r"|\bshow\s+(?:me\s+)?(?:the\s+)?(?:requirements?|details?)\b"
    r"|\bmore\s+(?:(?:about|on|for)\s+)?(?:the\s+)?(?:first|that|this)\s+(?:job|role|one)\b"
    r"|\b(?:المزيد|مزيد)\s+(?:من\s+)?(?:التفاصيل|المعلومات)\s+(?:عن|حول)?\s*(?:هذه?\s+الوظيفة|هذا\s+الدور)?\b",
    re.IGNORECASE,
)

# Profile bio/pitch: "write me a professional bio", "summarize my profile for an employer".
# Returns a deterministic pitch built from profile fields.
_PROFILE_PITCH_RE = re.compile(
    r"\b(?:write|create|generate|make|give\s+me)\b.{0,30}"
    r"\b(?:professional\s+bio|profile\s+(?:summary|pitch|description)|bio(?:\s+for\s+(?:employer|recruiter|linkedin))?)\b"
    r"|\b(?:summarize|describe|pitch)\s+my\s+(?:profile|background|experience|skills)\b"
    r"|\b(?:elevator\s+pitch|30[\s-]second\s+pitch|one[\s-]liner)\b"
    r"|\bاكتب\b.{0,25}\b(?:ملخص|نبذة)\b.{0,25}\b(?:ملفي|خبرتي|مهاراتي)\b",
    re.IGNORECASE,
)

# Application list query: "list my applications", "what jobs did I apply to?",
# "show my applied jobs", "how many applications do I have?",
# "what are my applications?", "where are my applications?", "do I have any applications?"
_APPLICATIONS_LIST_RE = re.compile(
    r"\b(?:list|show|display|view|see)\b.{0,30}"
    r"\b(?:my\s+)?(?:applications?|applied\s+jobs?|jobs?\s+i(?:'ve|\s+have)?\s+applied(?:\s+to)?|submitted(?:\s+applications?)?)\b"
    r"|\b(?:what|which)\s+(?:jobs?|companies?|roles?|positions?)\s+(?:have\s+I|did\s+I|have\s+i)\s+appl(?:ied|y)(?:\s+to)?\b"
    r"|\b(?:my\s+)?application\s+(?:list|history|tracker|overview)\b"
    r"|\bhow\s+many\s+(?:applications?|jobs?\s+(?:have\s+I|did\s+I)\s+applied(?:\s+to)?)\b"
    # Conversational question forms — "what are my applications?",
    # "where are my applications?", "do I have any applications?"
    r"|\bwhat\s+are\s+my\s+(?:job\s+)?applications?\b"
    r"|\bwhere\s+are\s+my\s+(?:job\s+)?applications?\b"
    r"|\bdo\s+i\s+have\s+any\s+(?:job\s+)?applications?\b"
    r"|\b(?:عرض|أظهر|كم)\b.{0,20}\b(?:طلباتي|التقديمات|وظائف\s+تقدمت\s+إليها)\b"
    r"|\bما\s+هي\s+طلباتي\b",
    re.IGNORECASE,
)

# Profile data readback: "what skills do you have for me?", "what do you know about me?",
# "show my profile data". Distinct from _PROFILE_PITCH_RE (which generates a bio).
_PROFILE_READBACK_RE = re.compile(
    r"\b(?:what|show|display|tell\s+me)\b.{0,25}"
    r"\b(?:(?:on\s+)?(?:my\s+)?(?:file|saved|stored|in\s+(?:my\s+)?profile)|my\s+profile\s+(?:data|info(?:rmation)?))\b"
    r"|\b(?:what\s+(?:skills?|experience|data|info(?:rmation)?))\s+(?:do\s+you|have\s+you|did\s+you)\s+(?:have|got|store|save|know)\b"
    r"|\bwhat\s+do\s+you\s+know\s+about\s+me\b"
    r"|\b(?:show|list|display)\s+(?:all\s+)?my\s+(?:skills?|certifications?|profile\s+info(?:rmation)?|saved\s+experience)\b"
    r"|\b(?:ما|ماذا)\b.{0,20}\b(?:معلوماتي|مهاراتي|بياناتي)\b.{0,15}\b(?:لديك|عندك|حفظت)\b",
    re.IGNORECASE,
)

# Ordinal job selection: "tell me more about the second job", "the third one",
# "job number 2 looks interesting", "option 3" — extracts index from search results.
_ORDINAL_JOB_RE = re.compile(
    r"\b(?:the\s+)?(?:job\s+(?:number\s+)?|option\s+|result\s+|#\s*)"
    r"(?P<n>[2-9]|1[0-9]?|first|second|third|fourth|fifth|last)\b"
    r"|\b(?:tell\s+me\s+more|more\s+(?:details?|info(?:rmation)?)|describe|about)\s+"
    r"(?:(?:about|on|for)\s+)?(?:the\s+)?"
    r"(?P<n2>second|third|fourth|fifth|last|[2-9](?:st|nd|rd|th)?|1[0-9]?(?:st|nd|rd|th)?)\s*"
    r"(?:job|role|position|opportunity|one|option)?\b"
    r"|\b(?P<n3>second|third|fourth|fifth|last)\s+(?:one|job|role|option|position)\b"
    r"|\b(?:الثاني|الثالث|الرابع|الخامس)\b.{0,20}\b(?:وظيفة|دور|خيار)?\b",
    re.IGNORECASE,
)

# Salary expectation readback: "what salary did I set?", "what's my expected salary?",
# "how much am I asking for?", "what's my minimum salary?".
_SALARY_READBACK_RE = re.compile(
    r"\bwhat(?:'s|\s+is|\s+was)?\s+my\s+(?:expected?|desired?|minimum|target|saved|set|current)?\s*salary\b"
    r"|\bwhat\s+salary\s+(?:did\s+I|have\s+I)\s+(?:set|saved?|entered?|entered?|told\s+you)\b"
    r"|\bhow\s+much\s+(?:am\s+I|do\s+I)\s+(?:asking|expecting|wanting|need(?:ing)?)\b"
    r"|\bmy\s+salary\s+(?:expectation|target|requirement|preference)\b"
    r"|\b(?:ما|كم)\b.{0,20}\b(?:راتبي\s+المتوقع|توقعاتي\s+للراتب|الراتب\s+الذي\s+(?:طلبت|حددت))\b",
    re.IGNORECASE,
)

# Delete saved jobs via chat: "delete all saved jobs", "clear my saved jobs".
# These CAN be executed after a 2-turn confirmation (P2-B).
# Intentionally does NOT match preference-removal patterns or application-history patterns.
_DELETE_SAVED_JOBS_RE = re.compile(
    r"""
    (?:
        # English: destructive verb targeting the saved-jobs list only
          \b(?:delete|erase|wipe|purge|remove|clear)\b.{0,60}?\b(?:saved\s+jobs?|all\s+(?:my\s+)?(?:saved\s+)?jobs?|my\s+(?:saved\s+jobs?|job\s+list|pipeline))\b
        |
        # Arabic: احذف/امسح + saved-jobs noun only (not applications)
        \b(?:امسح|احذف|امحِ|أزل)\b[^.!?،؟]{0,80}(?:الوظائف(?:\s+المحفوظة)?|وظائف(?:\s+المحفوظة)?|المحفوظات|قائمة\s+الوظائف)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Application-history delete via chat: these CANNOT be executed — application records
# are protected audit history. Rico redirects to the Applications page.
_DELETE_APPLICATIONS_RE = re.compile(
    r"""
    (?:
        # English: delete/clear/remove targeting application records
          \b(?:delete|erase|wipe|purge)\b.{0,60}?\b(?:applications?|my\s+records?|my\s+applied)\b
        | \bremove\b.{0,50}?\b(?:my\s+applications?|all\s+applications?)\b
        | \bclear\b.{0,50}?\b(?:my\s+applications?|all\s+applications?)\b
        |
        # Arabic: احذف + applications noun
        \b(?:امسح|احذف|امحِ|أزل)\b[^.!?،؟]{0,80}(?:الطلبات|طلباتي|جميع\s+الطلبات)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Combined guard: either saved-jobs OR applications delete — kept for the early-check
# at _handle_active_user_inner so we intercept before the AI fallback.
_UNSUPPORTED_DELETE_RE = re.compile(
    r"""
    (?:
        # English: explicit destructive verb + saved-jobs or applications noun
          \b(?:delete|erase|wipe|purge)\b.{0,60}?\b(?:saved\s+jobs?|all\s+(?:my\s+)?jobs?|my\s+(?:jobs?|pipeline|applications?|records?|list)|applications?|pipeline)\b
        | \bremove\b.{0,50}?\ball\s+(?:my\s+)?(?:saved\s+)?jobs?\b
        | \bremove\b.{0,50}?\bmy\s+applications?\b
        | \bremove\b.{0,50}?\ball\s+applications?\b
        | \bclear\b.{0,50}?\b(?:saved\s+jobs?|all\s+(?:my\s+)?jobs?|my\s+pipeline|my\s+applications?|all\s+applications?)\b
        |
        # Arabic: احذف/امسح + saved-jobs or applications noun
        \b(?:امسح|احذف|امحِ|أزل)\b[^.!?،؟]{0,80}(?:الوظائف(?:\s+المحفوظة)?|جميع\s+(?:الوظائف|الطلبات)|وظائف(?:\s+المحفوظة)?|الطلبات|طلباتي|المحفوظات|قائمة\s+الوظائف)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Explicit pipeline / application-list reset intent.
# Matches: "clear all applications", "reset my pipeline", "archive all applications",
# "start over", "start fresh", "restart pipeline", "remove all tracked jobs", etc.
# Does NOT overlap with _DELETE_SAVED_JOBS_RE (which targets saved-jobs only).
_PIPELINE_RESET_RE = re.compile(
    r"""
    (?:
        # English: destructive/reset verb + pipeline/applications/tracked-jobs noun
          \b(?:clear|reset|wipe|purge|erase)\b.{0,60}?\b(?:all\s+(?:my\s+)?)?(?:applications?|tracked\s+jobs?|job\s+pipeline|(?:my\s+)?pipeline)\b
        | \barchive\b.{0,60}?\b(?:all\s+(?:my\s+)?)?applications?\b
        | \b(?:remove|delete)\b.{0,60}?\ball\s+(?:my\s+)?tracked\s+jobs?\b
        | \b(?:start\s+(?:over|fresh|from\s+scratch)|restart\s+(?:the\s+)?(?:pipeline|job\s+(?:search|hunt)))\b
        |
        # Arabic: امسح/أعد ضبط + pipeline/applications
        \b(?:امسح|احذف|امحِ|أزل|أعد\s+ضبط)\b[^.!?،؟]{0,80}(?:الطلبات|طلباتي|جميع\s+الطلبات|خط\s+الأنابيب|مساري)
        | \b(?:ابدأ\s+(?:من\s+جديد|من\s+الصفر)|أعد\s+البدء)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Implicit pipeline reset — vague phrases like "clear them", "must start over".
# Only fires when last Rico turn was an application tracking summary (context-aware).
_PIPELINE_RESET_IMPLICIT_RE = re.compile(
    r"""
    (?:
          \b(?:clear|reset|wipe)\s+(?:them|it\s+all|everything|all\s+of\s+them|it|those)\b
        | \b(?:must\s+start\s+over|we\s+(?:must\s+)?start\s+over|lets?\s+start\s+(?:over|again|fresh))\b
        | \b(?:clean\s+slate|fresh\s+start)\b
        | \b(?:get\s+rid\s+of\s+(?:all\s+of\s+)?(?:them|everything))\b
        | \b(?:امسح|احذف)\s+(?:كل(?:ها|هم)?|الكل|جميعها)\b
        | \b(?:ابدأ\s+من\s+جديد|نبدأ\s+من\s+جديد)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Granular profile field update: "add Python to my skills", "remove OSHA from my skills",
# "update my experience to 8 years", "I'm now based in Abu Dhabi",
# "change my target role to HSE Manager", "add oil and gas to my industries".
_PROFILE_FIELD_UPDATE_RE = re.compile(
    # Add/remove from list fields
    r"\badd\b.{1,40}\bto\s+my\s+(?:skills?|certifications?|industries|target\s+roles?|preferred\s+(?:cities|locations?))\b"
    r"|\bremove\b.{1,40}\bfrom\s+my\s+(?:skills?|certifications?|industries|target\s+roles?)\b"
    # Set numeric experience
    r"|\b(?:update|set|change)\s+my\s+(?:years?\s+(?:of\s+)?)?experience\s+to\s+\d"
    r"|\bI\s+(?:now\s+)?have\s+\d+\s+years?\s+(?:of\s+)?experience\b"
    r"|\bmy\s+experience\s+is\s+(?:now\s+)?\d+\s+years?\b"
    # Set location/city
    r"|\bI(?:'m|\s+am)\s+(?:now\s+)?(?:based|located?|living|working)\s+in\s+(?:Abu\s+Dhabi|Dubai|Sharjah|Ajman|Fujairah|Ras\s+al|Al\s+Ain|Umm\s+al)\b"
    r"|\bmy\s+(?:location|city|base)\s+(?:is|has\s+changed\s+to|changed\s+to)\s+\w"
    r"|\b(?:update|change|set)\s+my\s+(?:preferred\s+)?(?:location|city)\s+to\b"
    # Set target role
    r"|\b(?:change|update|set)\s+my\s+(?:target\s+)?role\s+(?:to|as)\b"
    r"|\b(?:update|change|set)\s+my\s+(?:job\s+)?target\s+to\b"
    # Arabic
    r"|\b(?:أضف|اضف)\b.{1,30}\b(?:إلى|ل)\s*(?:مهاراتي|صناعاتي|أدواري)\b"
    r"|\b(?:غير|حدث|تحديث)\s+(?:مهاراتي|خبرتي|موقعي|دوري)\b",
    re.IGNORECASE,
)

# Application-specific lookup: "did I apply to Emirates?", "status of my ADNOC application",
# "status of my Carrefour application", "when did I apply to Carrefour?", "have I applied to Google?".
_APP_SPECIFIC_LOOKUP_RE = re.compile(
    r"\b(?:did\s+I|have\s+I|did\s+I\s+already)\s+appl(?:y|ied)\s+(?:to|at|for)\s+\w"
    r"|\b(?:status|update)\s+(?:of|on|for)\s+(?:my\s+)?(?:application|candidacy)\s+(?:at|to|with|for)\s+\w"
    r"|\b(?:status|update)\s+(?:of|on|for)\s+my\s+[A-Z]\w.{0,25}application\b"
    r"|\bmy\s+application\s+(?:at|to|with|for)\s+\w"
    r"|\b(?:what\s+happened|any\s+(?:news|update))\s+(?:with|on|about)\s+my\s+(?:application\s+(?:at|to|with)|candidacy\s+at)\s+\w"
    r"|\bwhen\s+did\s+I\s+appl(?:y|ied)\s+(?:to|at|for)\s+\w"
    r"|\b(?:am\s+I\s+(?:applying|being\s+considered)|is\s+my\s+application\s+(?:in|submitted))\s+(?:to|at|for)\s+\w"
    r"|\b(?:هل\s+تقدمت|هل\s+قدمت)\s+(?:إلى|ل|في)\s+\w",
    re.IGNORECASE,
)

# Company-targeted job search: "find jobs at ADNOC", "jobs at Emirates NBD",
# "any openings at Carrefour?", "vacancies at DEWA".
# Only fires on "at [company]" patterns to avoid colliding with location-based
# searches ("jobs in Dubai") and generic job searches.
_COMPANY_SEARCH_RE = re.compile(
    r"\b(?:find|search\s+for|show\s+me|look\s+for|get)\s+(?:me\s+)?(?:jobs?|roles?|positions?|vacancies|openings?)\s+at\s+[A-Z\w]"
    r"|\b(?:jobs?|roles?|vacancies|openings?|positions?)\s+at\s+[A-Z][A-Za-z]"
    r"|\bany\s+(?:openings?|vacancies|positions?|jobs?)\s+at\s+[A-Z\w]"
    r"|\b(?:وظائف|فرص\s+عمل)\s+(?:في|لدى|عند)\s+\w",
    re.IGNORECASE,
)

# Salary-filtered job search: "find HSE jobs paying above 20k AED",
# "QHSE roles with salary above 25000", "jobs paying more than 30k".
_SALARY_SEARCH_RE = re.compile(
    r"\b(?:find|show|search|look\s+for)\b.{0,50}\b(?:pay(?:ing)?|salary)\s+(?:above|over|more\s+than|at\s+least|minimum\s+of?)\s+\d"
    r"|\b(?:jobs?|roles?|positions?)\b.{0,30}\b(?:pay(?:ing)?|salary)\s+(?:above|over|more\s+than|at\s+least)\s+\d"
    r"|\bminimum\s+salary\s+(?:of\s+)?\d"
    r"|\bsalary\s+(?:above|over|more\s+than|at\s+least)\s+\d{4}"
    r"|\b\d+k\s+(?:AED\s+)?(?:and\s+above|minimum|or\s+more|plus)\b"
    r"|\براتب\s+(?:أعلى\s+من|فوق|لا\s+يقل\s+عن)\s+\d",
    re.IGNORECASE,
)

# Employment type filter: "find remote HSE jobs", "contract QHSE roles in Abu Dhabi",
# "show remote safety manager roles", "part-time positions in Dubai".
# Uses non-greedy .{0,30}? to allow a role name between the type and the job noun.
_EMPLOYMENT_TYPE_RE = re.compile(
    r"\b(?:find|search|show|look\s+for)\s+(?:me\s+)?(?:remote|hybrid|part[- ]?time|full[- ]?time|contract|freelance|temporary)\s+.{0,30}?\b(?:jobs?|roles?|positions?|work|vacancies)\b"
    r"|\b(?:remote|hybrid|part[- ]?time|full[- ]?time|contract|freelance|temporary)\s+.{0,25}?\b(?:jobs?|roles?|positions?|work|opportunities?)\s+(?:in|at|for|near)\b"
    r"|\b(?:only|just)\s+(?:remote|hybrid|part[- ]?time|full[- ]?time|contract|freelance)\b.{0,25}?\b(?:jobs?|roles?|positions?)\b"
    r"|\b(?:دوام\s+جزئي|دوام\s+كامل|عقد|عمل\s+عن\s+بُعد)\s+(?:وظائف|فرص)\b",
    re.IGNORECASE,
)

# Follow-up timing advice: "when should I follow up?", "how many days before following up?",
# "should I follow up with Emirates now?", "is it too early to follow up?".
_FOLLOWUP_TIMING_RE = re.compile(
    r"\bwhen\s+(?:should\s+I|to)\s+(?:follow\s+up|send\s+a\s+follow[- ]?up)\b"
    r"|\bhow\s+(?:long|many\s+days?)\s+(?:before|to\s+wait\s+before)\s+follow(?:ing)?\s+up\b"
    r"|\b(?:should\s+I|can\s+I)\s+follow\s+up\s+(?:now|yet|with|on)\b"
    r"|\bfollow[- ]?up\s+(?:timing|email|message|letter|template|after\s+applying)\b"
    r"|\b(?:is\s+it\s+(?:too\s+)?(?:early|late|soon|ok|okay|appropriate))\s+to\s+follow\s+up\b"
    r"|\bhow\s+(?:do\s+I|should\s+I)\s+follow\s+up\b"
    r"|\b(?:متى|كيف)\b.{0,20}\b(?:أتابع|المتابعة)\b",
    re.IGNORECASE,
)

# Industry-based job search: "find jobs in oil and gas", "construction sector jobs in Dubai",
# "finance industry positions", "IT sector vacancies in Abu Dhabi".
# Distinguished from role search by the presence of a sector/industry keyword.
_INDUSTRY_SEARCH_RE = re.compile(
    r"\b(?:find|show|search\s+for|look\s+for)\s+(?:me\s+)?(?:jobs?|roles?|positions?|vacancies|work)\s+in\s+(?:the\s+)?"
    r"(?:oil\s+(?:and|&)\s+gas|construction|finance|banking|IT|information\s+technology|tech(?:nology)?|"
    r"healthcare|medical|real\s+estate|retail|hospitality|tourism|logistics|supply\s+chain|"
    r"manufacturing|education|government|public\s+sector|telecom(?:munications?)?|"
    r"energy|aviation|maritime|legal|accounting|insurance|media|advertising)\b"
    r"|\b(?:oil\s+(?:and|&)\s+gas|construction|finance|banking|healthcare|medical|real\s+estate|"
    r"hospitality|logistics|manufacturing|education|telecom(?:munications?)?|energy|aviation|maritime)\s+"
    r"(?:sector\s+|industry\s+)?(?:jobs?|roles?|positions?|vacancies|careers?|opportunities?)\b"
    r"|\b(?:وظائف|فرص)\s+(?:في\s+)?(?:قطاع|صناعة)\s+\w",
    re.IGNORECASE,
)

# Job comparison: "compare job 1 and job 2", "compare the first and third job",
# "which is better job 1 or job 3?", "job 1 vs job 2".
_JOB_COMPARE_RE = re.compile(
    r"\b(?:compare|comparing|difference\s+between|which\s+(?:is\s+)?better)\b.{0,50}"
    r"(?:job|option|result|position|number|#)?\s*(?P<a>[1-5]|first|second|third|fourth|fifth)"
    r".{0,25}\b(?:and|or|vs\.?|versus)\b.{0,25}"
    r"(?:job|option|result|position|number|#)?\s*(?P<b>[1-5]|first|second|third|fourth|fifth)\b"
    r"|\b(?:job|option)\s*(?P<c>[1-5])\s+(?:vs\.?|versus|or)\s+(?:job|option)?\s*(?P<d>[1-5])\b",
    re.IGNORECASE,
)

# Search result count: "how many jobs did you find?", "how many results were there?",
# "total number of matches?", "how many vacancies?".
_RESULT_COUNT_RE = re.compile(
    r"\bhow\s+many\s+(?:jobs?|roles?|results?|matches?|vacancies|positions?|openings?)\s+"
    r"(?:did\s+you\s+(?:find|get|return|show|come\s+up\s+with)|were\s+there|are\s+there|do\s+you\s+have)\b"
    r"|\btotal\s+(?:number\s+of\s+)?(?:jobs?|results?|matches?|vacancies)\b"
    r"|(?:كم\s+عدد\s+الوظائف\s+التي\s+وجدتها(?:\s+منذ\s+بداية\s+المحادثة)?)"
    r"|\b(?:كم\s+(?:عدد\s+)?(?:ال)?(?:وظائف|وظيفة|نتائج|نتيجة|عدد))\b",
    re.IGNORECASE,
)

# Certification/qualification advice: "what certifications do I need for HSE?",
# "required qualifications for finance jobs", "what certifications for QHSE manager?".
_CERTIFICATION_ADVICE_RE = re.compile(
    r"\bwhat\s+(?:certifications?|qualifications?|courses?|credentials?|licenses?|training)\s+"
    r"(?:do\s+I\s+need|are\s+(?:needed|required|recommended)|should\s+I\s+(?:have|get|do))\b"
    r"|\b(?:certifications?|qualifications?|credentials?)\s+(?:required|needed|for)\s+\w.{1,30}\b(?:jobs?|roles?|career)\b"
    r"|\b(?:required|recommended)\s+(?:certifications?|qualifications?|credentials?|training)\b"
    r"|\bwhat\s+(?:qualifies|makes)\s+(?:me|someone)\s+(?:eligible|qualified|suitable)\b"
    r"|\b(?:شهادات|مؤهلات)\s+(?:مطلوبة|موصى\s+بها)\b",
    re.IGNORECASE,
)

# Seniority-filtered search: "find senior HSE jobs", "entry level QHSE positions",
# "manager-level roles", "junior safety engineer jobs", "director-level positions".
_SENIORITY_SEARCH_RE = re.compile(
    r"\b(?:find|show|search\s+for|look\s+for)\s+(?:me\s+)?(?:senior|junior|entry[- ]?level|mid[- ]?level|director[- ]?level|manager[- ]?level|executive[- ]?level|graduate|intern(?:ship)?)\s+.{0,30}\b(?:jobs?|roles?|positions?|vacancies)\b"
    r"|\b(?:senior|junior|entry[- ]?level|mid[- ]?level|director[- ]?level|manager[- ]?level)\s+.{0,25}\b(?:jobs?|roles?|positions?|vacancies|opportunities?)\b"
    r"|\b(?:jobs?|roles?|positions?)\s+(?:for\s+)?(?:graduates?|freshers?|entry[- ]?level|interns?)\b"
    r"|\b(?:وظائف|فرص)\s+(?:للخريجين|الأولى|مبتدئ|خبراء|إدارية)\b",
    re.IGNORECASE,
)

# Job market pulse: "how's the job market for HSE?", "are there many construction jobs?",
# "is the UAE market good for finance?", "how competitive is HSE in UAE?".
_MARKET_PULSE_RE = re.compile(
    r"\bhow(?:'s|\s+is)\s+(?:the\s+)?(?:job\s+)?market\s+(?:for|in|like\s+for)\b"
    r"|\bare\s+there\s+(?:many|enough|a\s+lot\s+of|few)\s+.{0,30}?\b(?:jobs?|roles?|positions?|vacancies|opportunities?)\b"
    r"|\bhow\s+(?:competitive|active|good|strong|busy)\s+is\s+(?:the\s+)?(?:job\s+)?market\b"
    r"|\b(?:job\s+)?market\s+(?:outlook|overview|status|situation|conditions?)\b"
    r"|\b(?:is\s+(?:it\s+)?(?:easy|hard|difficult|competitive))\s+to\s+find\s+(?:a\s+)?(?:job|work)\b"
    r"|\b(?:كيف\s+(?:هو\s+)?سوق|سوق\s+العمل)\b.{0,30}\b(?:في\s+الإمارات|الإمارات)?\b",
    re.IGNORECASE,
)

# Notice period / availability declaration or query.
# "my notice period is 30 days", "I'm available immediately", "I can join in 2 weeks",
# "what is my notice period?", "update my availability to 1 month".
_NOTICE_PERIOD_RE = re.compile(
    r"\b(?:my\s+)?notice\s+period\s+(?:is|was|will\s+be|=)\s*.{1,30}"
    r"|\bI(?:'m|\s+am)\s+available\s+(?:immediately|now|from|in\s+\d)"
    r"|\bI\s+can\s+(?:join|start)\s+(?:in|within|immediately|next)\b"
    r"|\b(?:update|set|change)\s+(?:my\s+)?(?:notice\s+period|availability)\b"
    r"|\bwhat(?:'s|\s+is)\s+my\s+notice\s+period\b"
    r"|\b(?:available\s+immediately|immediate\s+joiner|immediate\s+availability)\b"
    r"|\b(?:فترة\s+الإشعار|الإتاحة)\s*(?:هي|لدي|الخاصة\s+بي)?\b",
    re.IGNORECASE,
)

# Visa / work permit status declaration or query.
# "I'm on a spouse visa", "I have a valid work permit", "do I need a visa?",
# "update my visa status to employment visa", "my visa is expiring soon".
_VISA_STATUS_RE = re.compile(
    r"\b(?:I(?:'m|\s+am)\s+on\s+a?\s*)(?:spouse|visit|tourist|employment|golden|investor|freelance|dependent)\s+visa\b"
    r"|\b(?:I\s+have\s+(?:a\s+)?(?:valid\s+)?)?(?:UAE\s+)?(?:work\s+permit|residence\s+visa|employment\s+visa|golden\s+visa)\b"
    r"|\b(?:update|set|change)\s+(?:my\s+)?visa\s+(?:status|type|details?)\b"
    r"|\bwhat(?:'s|\s+is)\s+my\s+visa\s+(?:status|type)\b"
    r"|\bmy\s+visa\s+(?:is\s+)?(?:expir(?:ing|ed)|valid|active|cancelled)\b"
    r"|\bdo\s+I\s+need\s+a\s+(?:work\s+)?visa\b"
    r"|\b(?:need|require)\s+(?:visa\s+)?sponsorship\b"
    r"|\b(?:تأشيرة|تصريح\s+عمل|إقامة)\s+(?:عمل|الزوج|الزوجة|سارية)?\b",
    re.IGNORECASE,
)

# Salary negotiation advice — "how do I negotiate my salary?", "should I counter the offer?",
# "is the offer too low?", "how to ask for a raise?", "tips for negotiating in UAE".
_SALARY_NEGOTIATION_RE = re.compile(
    r"\bhow\s+(?:do\s+I|to|should\s+I)\s+negotiate\s+(?:my\s+)?salary\b"
    r"|\bshould\s+I\s+(?:counter|negotiate|accept|reject)\s+(?:the\s+)?offer\b"
    r"|\b(?:the\s+)?offer\s+(?:is|seems?)\s+(?:too\s+low|below\s+market|not\s+enough|low)\b"
    r"|\bhow\s+(?:to|do\s+I)\s+ask\s+for\s+(?:a\s+)?(?:raise|higher\s+salary|better\s+offer|salary\s+increase)\b"
    r"|\b(?:salary\s+)?negotiation\s+(?:tips?|advice|strategy|help|tactics?)\b"
    r"|\bwhat\s+(?:should\s+I|can\s+I)\s+(?:ask\s+for|counter(?:\s+offer)?|negotiate)\b"
    r"|\b(?:counter[\s-]offer|counteroffer)\b"
    r"|\b(?:نصائح\s+(?:تفاوض|الراتب)|كيف\s+أتفاوض)\b",
    re.IGNORECASE,
)

# Interview preparation advice — "how do I prepare for an interview?",
# "common interview questions for HSE", "what to wear to a UAE interview?".
_INTERVIEW_PREP_RE = re.compile(
    r"\bhow\s+(?:do\s+I|to)\s+prepare\s+(?:for\s+(?:a|an|the|my)\s+)?interview\b"
    r"|\b(?:interview\s+(?:tips?|advice|prep(?:aration)?|questions?|help|practice))\b"
    r"|\bcommon\s+interview\s+questions?\b"
    r"|\bwhat\s+(?:to|should\s+I)\s+(?:say|wear|bring|expect)\s+(?:in|at|to|for)\s+.{0,15}?\binterview\b"
    r"|\bhow\s+(?:to\s+)?(?:ace|pass|nail|impress)\s+(?:a|an|the|my)?\s*interview\b"
    r"|\b(?:preparing|practice)\s+for\s+(?:a|an|the|my)?\s*interview\b"
    r"|\b(?:تحضير|أسئلة|نصائح)\s+(?:المقابلة|الوظيفية|المقابلات)\b",
    re.IGNORECASE,
)

# Job rejection / no response handling — "I got rejected", "haven't heard back",
# "no response after interview", "what to do after rejection?".
_REJECTION_HANDLING_RE = re.compile(
    r"\b(?:I\s+(?:got|was|have\s+been)\s+)?rejected\b"
    r"|\bno\s+(?:response|reply|answer|feedback)\s+(?:from|after|yet)\b"
    r"|\bhaven(?:'t|\s+not)\s+heard\s+back\b"
    r"|\bwhat\s+(?:to\s+do|should\s+I\s+do)\s+(?:after|when)\s+(?:(?:a\s+)?rejection|I\s+(?:get|got)\s+rejected|rejected)\b"
    r"|\b(?:ghosted|being\s+ghosted)\b"
    r"|\b(?:job\s+)?rejection\s+(?:tips?|advice|strategy|letter|response)\b"
    r"|\bfail(?:ed|ing)\s+(?:the\s+)?interview\b"
    r"|\b(?:رفض|لم\s+يردوا|لا\s+رد)\s+(?:الطلب|على\s+طلبي|من\s+الشركة)?\b",
    re.IGNORECASE,
)

# LinkedIn / networking advice — "how to use LinkedIn for job search?",
# "should I connect with the recruiter?", "how to message a hiring manager on LinkedIn?".
_LINKEDIN_NETWORKING_RE = re.compile(
    r"\b(?:LinkedIn|لينكد\s+إن)\s+(?:profile|tips?|advice|help|strategy|message|connection|post|network)\b"
    r"|\bhow\s+(?:to\s+)?(?:use\s+LinkedIn|optimize\s+(?:my\s+)?LinkedIn|message\s+(?:a\s+)?(?:recruiter|hiring\s+manager|HR)|grow\s+(?:my\s+)?network)\b"
    r"|\bshould\s+I\s+(?:connect|message|follow\s+up)\s+(?:with\s+)?(?:the\s+)?(?:recruiter|hiring\s+manager|company|employer)\b"
    r"|\b(?:networking|network)\s+(?:tips?|advice|strategy|in\s+(?:UAE|Dubai|Abu\s+Dhabi))\b"
    r"|\bhow\s+to\s+(?:reach\s+out(?:\s+to)?|approach|contact)\s+(?:a\s+)?(?:recruiter|hiring\s+manager|company)\b"
    r"|\b(?:cold\s+message|cold\s+email|cold\s+outreach)\b"
    r"|\b(?:التواصل|نتورك)\s+(?:المهني|في\s+الإمارات|مع\s+المسؤولين)?\b",
    re.IGNORECASE,
)

# CV / resume format advice — "how should I format my CV for UAE?",
# "is my CV too long?", "what format should a UAE CV be in?", "ATS CV tips".
_CV_FORMAT_RE = re.compile(
    r"\bhow\s+(?:should\s+I\s+|to\s+)?(?:format|write|structure|layout|present)\s+(?:my\s+)?(?:CV|resume)\b"
    r"|\b(?:CV|resume)\s+(?:format|template|structure|layout|length|tips?|advice|help|style)\b"
    r"|\b(?:is\s+my\s+CV|my\s+CV\s+is)\s+(?:too\s+long|too\s+short|good|ok|fine|ready)\b"
    r"|\b(?:ATS|applicant\s+tracking)[- ](?:CV|resume|friendly|tips?)\b"
    r"|\bATS\s+(?:CV|resume|friendly|tips?)\b"
    r"|\bwhat\s+(?:should\s+(?:a|my)|does\s+a)\s+(?:UAE\s+)?(?:CV|resume)\s+(?:look\s+like|include|have|contain)\b"
    r"|\b(?:CV|resume)\s+(?:for\s+UAE|in\s+(?:the\s+)?UAE|UAE\s+standard)\b"
    r"|\b(?:نصائح|تنسيق|كيف\s+أكتب)\s+(?:السيرة\s+الذاتية|CV)\b",
    re.IGNORECASE,
)

# Cover letter tips — "how do I write a cover letter?", "do I need a cover letter?",
# "cover letter for HSE job", "UAE cover letter format".
_COVER_LETTER_TIPS_RE = re.compile(
    r"\bhow\s+(?:do\s+I|to)\s+write\s+(?:a\s+)?cover\s+letter\b"
    r"|\bcover\s+letter\s+(?:tips?|advice|help|format|template|example|guide|UAE)\b"
    r"|\bdo\s+I\s+need\s+a\s+cover\s+letter\b"
    r"|\bwhat\s+(?:should\s+(?:a|my)|to\s+put\s+in\s+(?:a|my))\s+cover\s+letter\b"
    # Arabic — interrogative / advice context only. A bare "خطاب تقديم" phrase
    # inside an explicit drafting request ("اكتب لي خطاب تقديم لوظيفة X في شركة Y")
    # must NOT be treated as a tips question; it routes to draft generation.
    r"|كيف\s+(?:أكتب|اكتب|اصيغ|اعمل|اكتبها)\s+(?:خطاب|رسالة)\s+(?:التغطية|تغطية|تقديم|التقديم)"
    r"|(?:نصائح|نموذج|نماذج|مثال|أمثلة|قالب|قوالب|صيغة|تنسيق)\s+(?:خطاب|رسالة)\s+(?:التغطية|تغطية|تقديم|التقديم)"
    r"|(?:خطاب|رسالة)\s+(?:التغطية|تغطية|تقديم|التقديم)\s+(?:نصائح|نموذج|مثال|قالب|صيغة|تنسيق)"
    r"|هل\s+(?:أحتاج|احتاج|احتاجه)\s+(?:إلى\s+)?(?:خطاب|رسالة)\s+(?:التغطية|تغطية|تقديم|التقديم)",
    re.IGNORECASE,
)

# Application pipeline summary — "how many applications have I sent?",
# "show me my application summary", "what's my application success rate?".
_APP_PIPELINE_SUMMARY_RE = re.compile(
    r"\bhow\s+many\s+(?:applications?|jobs?)\s+(?:have\s+I\s+(?:sent|applied|submitted)|did\s+I\s+(?:send|apply|submit))\b"
    r"|\b(?:application|job)\s+(?:search\s+)?(?:summary|overview|stats?|statistics|pipeline|status\s+summary|breakdown)\b"
    r"|\bmy\s+application\s+(?:record|tracker|progress|summary|stats?)\b"
    r"|\bwhat(?:'s|\s+is)\s+my\s+(?:application\s+)?success\s+rate\b"
    r"|\bhow\s+(?:am\s+I\s+doing|is\s+my\s+search\s+going|is\s+my\s+job\s+search)\b"
    r"|\b(?:إحصائيات|ملخص)\s+(?:طلباتي|التقديمات)\b",
    re.IGNORECASE,
)

# Profile improvement / completeness query — "how can I improve my profile?",
# "what's missing from my profile?", "how complete is my profile?".
_PROFILE_IMPROVE_RE = re.compile(
    r"\bhow\s+(?:can\s+I\s+|to\s+)?improve\s+(?:my\s+)?(?:profile|CV|resume)\b"
    r"|\bwhat(?:'s|\s+is)\s+missing\s+(?:from\s+)?(?:my\s+)?(?:profile|CV|resume)\b"
    r"|\bhow\s+(?:complete|strong|good)\s+is\s+(?:my\s+)?(?:profile|CV|resume)\b"
    r"|\b(?:profile|CV|resume)\s+(?:completeness|strength|score|review|gaps?|improvements?)\b"
    r"|\bwhat\s+(?:should\s+I\s+add|do\s+I\s+need)\s+(?:to\s+)?(?:my\s+)?profile\b"
    r"|\b(?:improve|strengthen|optimise|optimize)\s+(?:my\s+)?(?:profile|CV|resume)\b"
    r"|\b(?:ملف|سيرة)\s+(?:مكتمل|ناقص|قوي|يحتاج)\b",
    re.IGNORECASE,
)

# Company-type / sector-type search — "find government jobs", "find startup jobs",
# "multinational companies in UAE", "find ADNOC-type oil & gas companies".
_COMPANY_TYPE_SEARCH_RE = re.compile(
    r"\bfind\s+(?:me\s+)?(?:government|public\s+sector|federal|ministry|municipality|semi[- ]?government)\s+(?:jobs?|roles?|positions?|vacancies)\b"
    r"|\bfind\s+(?:me\s+)?(?:startup|start[- ]?up|tech\s+startup|scale[- ]?up)\s+(?:jobs?|roles?|positions?)\b"
    r"|\bfind\s+(?:me\s+)?(?:multinational|MNC|Fortune\s+500|international\s+company|global\s+company)\s+(?:jobs?|roles?|positions?)\b"
    r"|\bfind\s+(?:me\s+)?(?:SME|small\s+(?:and|&)\s+medium|family\s+business)\s+(?:jobs?|roles?|positions?)\b"
    r"|\b(?:government|public\s+sector|semi[- ]?government)\s+(?:jobs?|vacancies|roles?)\s+(?:in\s+)?(?:UAE|Dubai|Abu\s+Dhabi)?\b"
    r"|\b(?:وظائف\s+(?:حكومية|حكومة|القطاع\s+العام|الشركات\s+الكبرى))\b",
    re.IGNORECASE,
)

# Urgency / timeline job search — "I need a job urgently", "find jobs I can start immediately",
# "I need to find a job in 30 days", "help me find a job fast".
_URGENCY_SEARCH_RE = re.compile(
    r"\bI\s+(?:need|must\s+find|have\s+to\s+find)\s+a\s+job\s+(?:urgently|fast|quickly|asap|now|immediately|soon)\b"
    r"|\bfind\s+(?:me\s+)?(?:urgent|immediate)\s+(?:jobs?|roles?|openings?)\b"
    r"|\b(?:urgent(?:ly)?|immediate)\s+(?:job\s+(?:search|hunt|openings?)|employment)\b"
    r"|\bI\s+(?:need|want)\s+to\s+(?:find|get)\s+a\s+job\s+(?:in\s+\d+\s+(?:days?|weeks?|months?)|fast|quickly|asap|urgently|as\s+soon\s+as\s+possible)\b"
    r"|\bhelp\s+me\s+(?:find|get)\s+a\s+job\s+(?:fast|quickly|urgently|asap)\b"
    r"|\b(?:أحتاج\s+وظيفة|ابحث\s+عن\s+وظيفة)\s+(?:عاجل|بسرعة|الآن|فوراً)\b",
    re.IGNORECASE,
)

# Salary benchmark — "what does an HSE Manager earn in Dubai?", "how much do project managers make?",
# "what's the salary range for operations managers?", "market rate for senior engineers UAE".
# Distinct from _SALARY_SEARCH_RE (filter by minimum) and _SALARY_READBACK_RE (read stored expectation).
_SALARY_BENCHMARK_RE = re.compile(
    r"\bwhat\s+(?:is|does|are|would)\s+(?:the\s+)?(?:typical|average|standard|market|normal|usual|expected)?\s*"
    r"(?:salary|pay|compensation|package|earning)\s+(?:be\s+)?(?:for|of|in)\b"
    r"|\bwhat\s+(?:does|do)\s+.{1,50}?\b(?:earn|make|get\s+paid)\b"
    r"|\bhow\s+much\s+(?:does|do|can|should|would)\s+.{0,50}?\b(?:earn|make|get\s+paid|be\s+paid)\b"
    r"|\bwhat(?:'s|\s+is)\s+(?:the\s+)?(?:salary|pay|compensation)\s+(?:range\s+for|for)\b"
    r"|\bmarket\s+(?:rate|salary|pay|compensation)\s+for\b"
    r"|\bwhat\s+can\s+I\s+(?:earn|make)\s+(?:as|working\s+as)\b"
    r"|\b(?:salary|pay)\s+(?:benchmark|expectations?)\s+(?:for|in)\b"
    r"|\b(?:كم\s+(?:الراتب|يكسب|يتقاضى)|متوسط\s+الراتب)\b",
    re.IGNORECASE,
)

# Career change / transition advice — "I want to switch careers", "how do I transition to PM?",
# "can I move from engineering to consulting?", "career change tips UAE".
_CAREER_CHANGE_RE = re.compile(
    r"\bI\s+(?:want|need|am\s+looking)\s+to\s+(?:change|switch|transition|pivot|move)\s+(?:my\s+)?(?:careers?|fields?|industries?|sector|roles?|jobs?)\b"
    r"|\bhow\s+(?:do\s+I|can\s+I|to)\s+(?:transition|switch|change|pivot|move)\s+(?:to|from|into|careers?|fields?|industries?|sector)\b"
    r"|\b(?:career\s+(?:change|switch|pivot|transition|shift|changer))\b"
    r"|\bcan\s+I\s+(?:move|switch|transition|change)\s+(?:from|to|into)\b"
    r"|\bI(?:'m|\s+am)\s+(?:looking\s+to\s+|wanting\s+to\s+|thinking\s+(?:of|about)\s+)?(?:pivot|transition|(?:switch|switching)\s+careers?)\b"
    r"|\b(?:تغيير\s+المسار\s+المهني|تحويل\s+المهنة|التحول\s+الوظيفي)\b",
    re.IGNORECASE,
)

# Best employers / top companies — "which companies hire HSE managers?", "best employers in Dubai",
# "who are the top employers for project managers in UAE?", "top companies to work for".
_BEST_EMPLOYERS_RE = re.compile(
    r"\b(?:which|what)\s+(?:companies|employers|organisations?|firms?)\s+(?:hire|hiring|recruit|employ|look\s+for)\b"
    r"|\bwho\s+(?:are\s+(?:the\s+)?(?:best|top|leading|major)?\s*)?(?:hires?|employs?|recruits?|the\s+(?:best|top|leading)\s+(?:employers?|companies))\b"
    r"|\b(?:best|top|leading|major|biggest)\s+(?:companies|employers|organisations?|firms?)\s+"
    r"(?:to\s+work\s+for|in\s+(?:UAE|Dubai|Abu\s+Dhabi|Sharjah)|(?:hiring|that\s+hire)|for\s+\w)\b"
    r"|\b(?:best|top|leading|major|biggest)\s+(?:companies|employers|organisations?|firms?)\s+for\b"
    r"|\b(?:top|best|leading|major)\s+(?:UAE|Dubai|Abu\s+Dhabi|Sharjah)\s+(?:employers?|companies|organisations?)\b"
    r"|\b(?:أفضل\s+(?:شركات|أصحاب\s+عمل)|من\s+يوظف)\b",
    re.IGNORECASE,
)

# UAE job search tips / strategy — "how do I find a job in UAE?", "best job boards in Dubai",
# "tips for job hunting", "how long does it take to find a job?", "should I use a recruiter?".
_JOB_SEARCH_TIPS_RE = re.compile(
    r"\bhow\s+(?:do\s+I|can\s+I|to)\s+(?:find|get|search\s+for|land)\s+a\s+job\s+(?:in\s+(?:UAE|Dubai|Abu\s+Dhabi)|here|fast)?\b"
    r"|\b(?:best\s+)?(?:job\s+)?(?:boards?|sites?|platforms?|portals?)\s+(?:in\s+(?:UAE|Dubai|Abu\s+Dhabi)|to\s+(?:find|use)|for\s+(?:UAE|Dubai))\b"
    r"|\b(?:tips?|advice|strategy|guide)\s+(?:for\s+)?(?:job\s+(?:hunting|search(?:ing)?)|finding\s+a\s+job)\b"
    r"|\b(?:job\s+(?:hunting|search(?:ing)?)|finding\s+(?:a\s+)?job)\s+(?:tips?|advice|strategy|guide|resources?)\b"
    r"|\bhow\s+(?:long|much\s+time)\s+(?:does\s+it|will\s+it)\s+take\s+to\s+find\s+a\s+job\b"
    r"|\b(?:should\s+I|is\s+it\s+worth|do\s+I\s+need)\s+(?:(?:to\s+)?(?:use|using)\s+(?:a\s+)?)?(?:recruitment\s+agenc(?:y|ies)|headhunter|recruiter)\b"
    r"|\bwhere\s+(?:should\s+I|can\s+I|to)\s+(?:find|look\s+for|search\s+for)\s+(?:jobs?|work)\b"
    r"|\b(?:نصائح|دليل)\s+(?:البحث\s+عن\s+وظيفة|سوق\s+العمل)\b",
    re.IGNORECASE,
)

# UAE benefits / package query — "what benefits should I expect?", "is housing allowance standard?",
# "what's a typical UAE package?", "medical insurance in UAE".
_BENEFITS_QUERY_RE = re.compile(
    r"\b(?:benefits?|package|allowances?|perks?)\s+(?:should\s+I\s+(?:expect|ask\s+for|negotiate)|are\s+(?:typical|standard|common|included)|does\s+(?:the\s+)?(?:package|offer)\s+include)\b"
    r"|\b(?:housing|accommodation)\s+allowance\b"
    r"|\b(?:what(?:'s|\s+is)\s+(?:a\s+)?(?:good|typical|standard|normal|fair)\s+(?:UAE\s+)?(?:package|salary\s+package|benefits?\s+package|offer))\b"
    r"|\b(?:is|are)\s+.{0,30}?\b(?:allowance|benefit|medical\s+insurance|gratuity)\s+(?:standard|common|typical|included|normal|mandatory)\b"
    r"|\b(?:end\s+of\s+service|end[- ]of[- ]service|gratuity)\s+(?:in\s+UAE|calculation|rights?|entitlement)\b"
    r"|\bhow\s+many\s+(?:annual\s+leave|leave|vacation)\s+days?\b"
    r"|\b(?:annual\s+leave|paid\s+leave)\s+(?:days?\s+)?(?:in\s+UAE|entitlement|rights?)\b"
    r"|\b(?:مزايا|راتب\s+شامل|بدل\s+(?:سكن|مواصلات|طبي)|مكافأة\s+نهاية\s+الخدمة)\b",
    re.IGNORECASE,
)

# Offer evaluation — "should I accept this offer?", "how to evaluate a job offer",
# "is this offer good?", "offer pros and cons".
_OFFER_EVAL_RE = re.compile(
    r"\bshould\s+I\s+(?:accept|take|reject|decline|consider)\s+(?:this\s+)?(?:offer|job\s+offer|position)\b"
    r"|\bhow\s+(?:to|do\s+I)\s+(?:evaluate|assess|weigh|compare)\s+(?:a\s+|this\s+)?(?:job\s+)?offer\b"
    r"|\bis\s+(?:this|the)\s+offer\s+(?:good|fair|worth|competitive|reasonable|right)\b"
    r"|\b(?:job\s+)?offer\s+(?:evaluation|comparison|pros\s+and\s+cons|checklist|worth\s+it)\b"
    r"|\bwhat\s+(?:should\s+I\s+(?:look\s+for|consider|check)|to\s+(?:look\s+for|consider|check))\s+in\s+(?:a\s+)?(?:job\s+)?offer\b"
    r"|\bhow\s+(?:do\s+I|to)\s+(?:decide|know)\s+(?:if|whether)\s+(?:to\s+accept|an\s+offer\s+is)\b"
    r"|\b(?:قبول|رفض)\s+(?:العرض|عرض\s+العمل)\b",
    re.IGNORECASE,
)

# UAE labor law / probation info — "what is the probation period in UAE?",
# "can I leave during probation?", "UAE labor law rights", "termination rights UAE".
# Does NOT overlap with _NOTICE_PERIOD_RE (which handles personal notice updates)
# or _VISA_STATUS_RE (which handles employment visa status).
_UAE_LABOR_LAW_RE = re.compile(
    r"\b(?:what\s+(?:is|are)|how\s+(?:does|do))\s+(?:the\s+)?(?:probation(?:ary)?\s+period|UAE\s+lab(?:or|our)\s+law|employment\s+law)\b"
    r"|\b(?:probation(?:ary)?\s+period)\s+(?:in\s+(?:UAE|Dubai)|UAE\s+rules?|rules?|conditions?|terms?|duration|length)\b"
    r"|\bcan\s+I\s+(?:leave|quit|resign|terminate)\s+(?:my\s+job\s+)?(?:during|within|before\s+completing)\s+(?:probation|the\s+probation\s+period)\b"
    r"|\b(?:UAE\s+)?(?:labor|labour)\s+(?:law|rights?|code|card)\b"
    r"|\b(?:termination|dismissal|redundancy)\s+(?:rights?|in\s+UAE|notice|UAE)\b"
    r"|\b(?:MOHRE|ministry\s+of\s+human\s+resources)\b"
    r"|\b(?:unlimited\s+contract|limited\s+contract)\s+(?:UAE|in\s+UAE|difference|vs)\b"
    r"|\b(?:قانون\s+العمل|حقوق\s+العامل)\s*(?:في\s+الإمارات)?\b",
    re.IGNORECASE,
)

# Post-interview thank you / follow-up email — "should I send a thank you after the interview?",
# "how to write a thank you email", "post-interview follow-up note".
_POST_INTERVIEW_EMAIL_RE = re.compile(
    r"\b(?:should\s+I\s+)?(?:send|write)\s+(?:a\s+)?(?:thank[- ]you|follow[- ]?up)\s+(?:email|note|message|letter)\s+(?:after|following)\s+(?:(?:a|an|the|my)\s+)?interview\b"
    r"|\bhow\s+(?:to|do\s+I)\s+(?:write|send)\s+(?:a\s+)?(?:thank[- ]you|follow[- ]?up)\s+(?:email|note)\s+(?:after|following)\s+(?:(?:a|an|the|my)\s+)?interview\b"
    r"|\b(?:thank[- ]you\s+email|post[- ]interview\s+(?:email|follow[- ]?up))\b"
    r"|\bafter\s+(?:the|my|an?)\s+interview.{0,20}?(?:should\s+I|do\s+I)\s+(?:send|write|follow\s+up)\b"
    r"|\b(?:بريد|رسالة)\s+(?:الشكر|شكر)\s+(?:بعد\s+)?المقابلة\b",
    re.IGNORECASE,
)

# Skill gap assessment — "what skills am I missing?", "am I qualified for director?",
# "how do I close my skill gap?", "what do I need to land a senior role?".
# Positioned after _PROFILE_IMPROVE_RE and _CERTIFICATION_ADVICE_RE to avoid overlap.
_SKILL_GAP_RE = re.compile(
    r"\bwhat\s+skills?\s+(?:am\s+I\s+missing|do\s+I\s+(?:lack|need\s+to\s+(?:develop|add|gain|build)))\b"
    r"|\bam\s+I\s+(?:qualified|eligible|suitable|ready)\s+(?:for|to)\b"
    r"|\bhow\s+(?:do\s+I\s+(?:close|bridge)|to\s+(?:close|bridge))\s+(?:(?:my|the)\s+)?(?:skills?\s+)?gap\b"
    r"|\b(?:skills?\s+gap)\s+(?:analysis|assessment|for|between|to)\b"
    r"|\bwhat\s+(?:experience|skills?|qualifications?)\s+do\s+I\s+(?:need|lack)\s+(?:for|to\s+(?:get|land|become|be\s+a))\b"
    r"|\b(?:am\s+I\s+ready|ready\s+for)\s+(?:a\s+)?(?:senior|director|manager|lead|head)\b"
    r"|\b(?:فجوة\s+المهارات|ما\s+المهارات\s+الناقصة)\b",
    re.IGNORECASE,
)

# Interview preparation — "how do I prepare for an interview?", "what questions to expect",
# "tell me about yourself", "common interview questions", "behavioral interview".
_INTERVIEW_PREP_RE = re.compile(
    r"\bhow\s+(?:do\s+I|to|can\s+I)\s+(?:prepare\s+for|ace|pass|nail|crush|handle)\s+(?:(?:a|an|the|my)\s+)?interview\b"
    r"|\bhow\s+(?:to\s+)?(?:ace|pass|nail|impress)\s+(?:a|an|the|my)?\s*interview\b"
    r"|\b(?:interview\s+(?:tips?|advice|prep(?:aration)?|guide|questions?|help|practice|coaching))\b"
    r"|\b(?:common|typical|likely|hard|tough|tricky)\s+(?:interview\s+)?questions?\b"
    r"|\bwhat\s+questions?\s+(?:should\s+I\s+)?(?:expect|can\s+I\s+expect).{0,20}?\binterview\b"
    r"|\bwhat\s+(?:to|should\s+I)\s+(?:say|wear|bring|expect)\s+(?:in|at|to|for)\s+.{0,15}?\binterview\b"
    r"|\b(?:tell\s+me\s+about\s+yourself|STAR\s+method|situational\s+interview|behavioral\s+interview)\b"
    r"|\bwhat\s+(?:should\s+I|do\s+I)\s+(?:say|answer|reply)\s+when\s+(?:asked|they\s+ask)\b"
    r"|\bhow\s+(?:do\s+I|to)\s+(?:answer|respond\s+to)\s+(?:interview|the)\s+question\b"
    r"|\b(?:preparing|practice)\s+for\s+(?:a|an|the|my)?\s*interview\b"
    r"|\b(?:أسئلة\s+المقابلة|كيف\s+أتحضر\s+للمقابلة|التحضير\s+للمقابلة)\b"
    r"|\b(?:تحضير|نصائح)\s+(?:المقابلة|الوظيفية|المقابلات)\b",
    re.IGNORECASE,
)

# Salary negotiation — "how do I negotiate my salary?", "should I counter-offer",
# "how to ask for a raise", "negotiation tips".
_SALARY_NEGOTIATION_RE = re.compile(
    r"\bhow\s+(?:do\s+I|to|should\s+I|can\s+I)\s+negotiate\s+(?:my\s+)?salary\b"
    r"|\bhow\s+(?:do\s+I|to|can\s+I)\s+(?:negotiate|ask\s+for|request)\s+(?:a\s+)?(?:(?:higher\s+|better\s+)?salary|pay\s+rise|raise|pay\s+increase|counter[- ]?offer)\b"
    r"|\bshould\s+I\s+(?:counter|negotiate|accept|reject)\s+(?:the\s+)?offer\b"
    r"|\b(?:the\s+)?offer\s+(?:is|seems?)\s+(?:too\s+low|below\s+market|not\s+enough|low)\b"
    r"|\bhow\s+(?:to|do\s+I)\s+ask\s+for\s+(?:a\s+)?(?:raise|higher\s+salary|better\s+offer|salary\s+increase)\b"
    r"|\b(?:salary\s+)?negotiation\s+(?:tips?|advice|strategy|help|tactics?)\b"
    r"|\bwhat\s+(?:should\s+I|can\s+I)\s+(?:ask\s+for|counter(?:\s+offer)?|negotiate)\b"
    r"|\b(?:counter[\s-]offer|counteroffer)\b"
    r"|\b(?:salary|pay|offer)\s+(?:negotiation|negotiating|counter[- ]?offer|counter)\b"
    r"|\b(?:should\s+I|can\s+I)\s+(?:negotiate|counter|ask\s+for\s+more)\s+(?:the\s+)?(?:salary|offer|pay)\b"
    r"|\b(?:ask\s+for\s+a\s+raise|request\s+a\s+(?:salary\s+)?increase|negotiate\s+(?:my\s+)?package)\b"
    r"|\b(?:when\s+(?:should\s+I|to)\s+(?:discuss|bring\s+up|mention|negotiate)\s+salary)\b"
    r"|\b(?:نصائح\s+(?:تفاوض|الراتب)|كيف\s+أتفاوض|مفاوضة\s+الراتب|كيف\s+أطلب\s+زيادة|التفاوض\s+على\s+الراتب)\b",
    re.IGNORECASE,
)

# LinkedIn profile optimisation — "how do I improve my LinkedIn?", "LinkedIn tips",
# "should I use LinkedIn for jobs in UAE?", "LinkedIn headline/summary".
_LINKEDIN_TIPS_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:improve|optimise?|optimize|update|set\s+up|use|grow|boost)\s+(?:my\s+)?LinkedIn)\b"
    r"|\bLinkedIn\s+(?:tips?|advice|profile\s+tips?|headline|summary|bio|optimis(?:e|ation)|optim(?:ize|ization)|for\s+(?:UAE|Dubai|jobs?|job\s+search))\b"
    r"|\b(?:should\s+I\s+(?:use|be\s+on|have\s+a?\s+|join)\s+LinkedIn)\b"
    r"|\b(?:is\s+LinkedIn\s+(?:useful|important|worth\s+it|effective|good)\s+(?:in\s+UAE|for\s+(?:UAE|Dubai)|for\s+(?:finding\s+)?jobs?))\b"
    r"|\b(?:LinkedIn\s+(?:connections?|network|profile|presence|page|account)\s+(?:tips?|advice|for\s+(?:UAE|jobs?)))\b"
    r"|\b(?:نصائح\s+LinkedIn|تحسين\s+(?:ملف|حساب)\s+LinkedIn)\b",
    re.IGNORECASE,
)

# Resignation letter — "how do I write a resignation letter?", "how to resign professionally",
# "what should I say when I quit?", "draft a resignation letter".
_RESIGNATION_LETTER_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|should\s+I)\s+(?:write|draft|prepare|compose)\s+(?:a\s+)?resignation\s+(?:letter|email|note|message))\b"
    r"|\b(?:resignation\s+(?:letter|email|template|format|sample|guide|tips?))\b"
    r"|\b(?:how\s+(?:do\s+I|to|should\s+I)\s+(?:resign|quit|leave)\s+(?:professionally|properly|politely|gracefully|formally))\b"
    r"|\b(?:how\s+(?:do\s+I|to)\s+(?:hand\s+in|give|submit)\s+(?:my\s+)?(?:notice|resignation))\b"
    r"|\b(?:what\s+(?:should\s+I|to)\s+(?:say|write|include)\s+(?:in|when)\s+(?:a\s+)?(?:resignation|quitting|handing\s+in\s+notice))\b"
    r"|\b(?:خطاب\s+استقالة|كيف\s+أستقيل|رسالة\s+استقالة)\b",
    re.IGNORECASE,
)

# Relocation to UAE — "how do I move to Dubai for work?", "tips for relocating to UAE",
# "what do I need to move to Abu Dhabi?", "relocating to UAE guide".
_RELOCATION_UAE_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:move|relocate|transfer)\s+to\s+(?:UAE|Dubai|Abu\s+Dhabi|Sharjah|the\s+UAE)(?:\s+(?:for\s+work|to\s+work|for\s+a\s+job))?)\b"
    r"|\b(?:relocating|moving|relocation)\s+to\s+(?:UAE|Dubai|Abu\s+Dhabi|Sharjah|the\s+UAE)\b"
    r"|\b(?:tips?|advice|guide|checklist)\s+(?:for\s+)?(?:relocating|moving)\s+to\s+(?:UAE|Dubai|Abu\s+Dhabi|the\s+UAE)\b"
    r"|\b(?:what\s+(?:do\s+I\s+need|should\s+I\s+do|to\s+do)\s+(?:to\s+)?(?:move|relocate)\s+to\s+(?:UAE|Dubai|the\s+UAE))\b"
    r"|\b(?:cost\s+of\s+(?:living|moving)\s+in\s+(?:UAE|Dubai|Abu\s+Dhabi))\b"
    r"|\b(?:الانتقال\s+إلى\s+(?:الإمارات|دبي)|الهجرة\s+للعمل\s+في\s+الإمارات)\b",
    re.IGNORECASE,
)

# Applying from abroad — "can I apply to UAE jobs from outside UAE?",
# "do I need to be in UAE to apply?", "should I relocate before job hunting?".
_APPLY_FROM_ABROAD_RE = re.compile(
    r"\b(?:can\s+I\s+(?:apply|search|job\s+hunt)(?:\s+for)?(?:\s+(?:UAE|Dubai|Abu\s+Dhabi))?\s+(?:jobs?|roles?|positions?)\s+from\s+(?:abroad|outside(?:\s+(?:UAE|Dubai|the\s+UAE))?|overseas|my\s+country|home))\b"
    r"|\b(?:do\s+I\s+(?:need\s+to\s+be|have\s+to\s+be)\s+(?:in|inside)\s+(?:UAE|Dubai|the\s+UAE)\s+to\s+(?:apply|look\s+for\s+jobs?|job\s+hunt))\b"
    r"|\b(?:should\s+I\s+(?:move|relocate|be\s+in\s+(?:UAE|Dubai))\s+before\s+(?:applying|job\s+hunting|searching\s+for\s+a\s+job|looking\s+for\s+a\s+job))\b"
    r"|\b(?:applying\s+for\s+(?:(?:UAE|Dubai|the\s+UAE)\s+)?jobs?\s+from\s+(?:abroad|outside(?:\s+(?:UAE|Dubai|the\s+UAE))?|overseas))\b"
    r"|\b(?:job\s+hunt(?:ing)?\s+(?:while|from)\s+(?:abroad|outside\s+(?:UAE|Dubai)|overseas))\b"
    r"|\b(?:is\s+it\s+(?:possible|ok|okay|better)\s+to\s+(?:apply|job\s+hunt)\s+from\s+(?:abroad|outside|overseas))\b"
    r"|\b(?:التقديم\s+على\s+وظائف\s+الإمارات\s+من\s+الخارج|هل\s+يمكنني\s+التقديم\s+من\s+خارج\s+الإمارات)\b",
    re.IGNORECASE,
)

# Employment gap explanation — "how do I explain a career gap?",
# "I have a gap in my CV", "took time off work", "was out of work for X months".
_EMPLOYMENT_GAP_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|should\s+I)\s+(?:explain|address|handle|deal\s+with|justify)\s+(?:a\s+)?(?:career\s+gap|gap\s+in\s+(?:my\s+)?(?:CV|resume|employment|work\s+history)|employment\s+gap|work\s+gap))\b"
    r"|\b(?:(?:I\s+have|there\s+is)\s+(?:a\s+)?(?:gap|career\s+gap|employment\s+gap)\s+in\s+(?:my\s+)?(?:CV|resume|work\s+history|employment))\b"
    r"|\b(?:(?:career|employment|work)\s+gap\s+(?:explanation|on\s+(?:my\s+)?(?:CV|resume)|advice|tips?|in\s+interview))\b"
    r"|\b(?:I\s+(?:took|was\s+(?:out\s+of\s+work|unemployed|on\s+a\s+break|between\s+jobs?))\s+(?:for\s+)?(?:(?:a|an|several|many|few|\d+)\s+)?(?:months?|years?|time))\b"
    r"|\b(?:between\s+jobs?\s+(?:for|gap)|gap\s+(?:year|years?|months?)\s+(?:in\s+work|between\s+jobs?))\b"
    r"|\b(?:فجوة\s+(?:في\s+)?(?:السيرة\s+الذاتية|مسيرتي\s+المهنية)|كيف\s+أشرح\s+(?:فترة\s+)?الانقطاع\s+عن\s+العمل)\b",
    re.IGNORECASE,
)

# Company research before interview — "how do I research a company?",
# "what should I know about a company before an interview?".
_COMPANY_RESEARCH_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|should\s+I)\s+(?:research|find\s+out\s+about|learn\s+about|investigate)\s+(?:a\s+|the\s+)?company(?:\s+before\s+(?:an?\s+)?interview)?)\b"
    r"|\b(?:what\s+(?:should\s+I|to)\s+(?:know|find\s+out|research|look\s+up|check)\s+about\s+(?:a\s+|the\s+)?company\s+before\s+(?:(?:a|an|the|my)\s+)?interview)\b"
    r"|\b(?:how\s+(?:do\s+I|to)\s+(?:prepare|research)\s+(?:for|about)\s+(?:a\s+|the\s+)?company(?:\s+interview)?)\b"
    r"|\b(?:company\s+research\s+(?:before|for|tips?|guide|checklist))\b"
    r"|\b(?:what\s+(?:should\s+I|to)\s+(?:know|look\s+up|research)\s+about\s+(?:them|the\s+company|my\s+interviewer)\s+before\s+(?:(?:a|an|the|my)\s+)?interview)\b"
    r"|\b(?:كيف\s+أبحث\s+عن\s+(?:الشركة|معلومات\s+الشركة)|البحث\s+عن\s+الشركة\s+قبل\s+المقابلة)\b",
    re.IGNORECASE,
)

# Freelance permit in UAE — "can I freelance in UAE?", "how to get a freelance visa",
# "freelance permit UAE", "self-employed in UAE".
_FREELANCE_UAE_RE = re.compile(
    r"\b(?:can\s+I\s+(?:work\s+as\s+a?\s+)?freelan(?:ce|cer)\s+in\s+(?:UAE|Dubai|Abu\s+Dhabi|the\s+UAE))\b"
    r"|\b(?:how\s+(?:to|do\s+I)\s+(?:get|apply\s+for|obtain)\s+(?:a\s+)?(?:freelance\s+(?:permit|visa|licence|license)|UAE\s+freelance))\b"
    r"|\b(?:freelance\s+(?:permit|visa|licence|license)\s+(?:UAE|Dubai|Abu\s+Dhabi|in\s+UAE))\b"
    r"|\b(?:(?:UAE|Dubai)\s+freelance\s+(?:permit|visa|licence|license|visa|rules?|options?))\b"
    r"|\b(?:self[- ]?employed?\s+in\s+(?:UAE|Dubai|the\s+UAE))\b"
    r"|\b(?:can\s+I\s+be\s+(?:self[- ]?employed?|freelan(?:ce|cer))\s+in\s+(?:UAE|Dubai|the\s+UAE))\b"
    r"|\b(?:independent\s+contractor\s+(?:in|UAE|Dubai))\b"
    r"|\b(?:تصريح\s+(?:العمل\s+الحر|المستقل)|العمل\s+الحر\s+في\s+الإمارات)\b",
    re.IGNORECASE,
)

# End of service gratuity / EOSB — "what is end of service gratuity?",
# "how much gratuity am I owed?", "how is gratuity calculated in UAE?".
_EOSB_RE = re.compile(
    r"\b(?:what\s+is\s+(?:end\s+of\s+service|gratuity|EOSB))\b"
    r"|\b(?:how\s+(?:is|do\s+I\s+calculate|to\s+calculate)\s+(?:my\s+)?(?:end\s+of\s+service|gratuity))\b"
    r"|\b(?:how\s+much\s+(?:gratuity|end\s+of\s+service)\s+(?:am\s+I\s+(?:owed|entitled\s+to)|will\s+I\s+(?:get|receive)))\b"
    r"|\b(?:gratuity\s+(?:calculation|calculator|formula|in\s+UAE|UAE|entitlement|payment|amount|rights?))\b"
    r"|\b(?:end\s+of\s+service\s+(?:gratuity|benefit|payment|calculation|calculator|entitlement|in\s+UAE))\b"
    r"|\b(?:EOSB\s+(?:calculation|UAE|entitlement|amount))\b"
    r"|\b(?:am\s+I\s+(?:entitled|eligible)\s+(?:to|for)\s+(?:end\s+of\s+service|gratuity))\b"
    r"|\b(?:مكافأة\s+نهاية\s+الخدمة|كيف\s+(?:تُحسب|أحسب)\s+مكافأة\s+نهاية\s+الخدمة|حساب\s+مكافأة\s+نهاية\s+الخدمة)\b",
    re.IGNORECASE,
)

# Non-compete clause in UAE — "does my non-compete apply in UAE?",
# "can my employer enforce a non-compete?", "what is a non-compete clause?".
_NON_COMPETE_RE = re.compile(
    r"\b(?:what\s+is\s+(?:a\s+|an\s+|the\s+)?non[- ]compete(?:\s+(?:clause|agreement|restriction))?)\b"
    r"|\b(?:does\s+my\s+non[- ]compete\s+(?:apply|work|matter)?)\b"
    r"|\b(?:how\s+does\s+(?:a\s+)?non[- ]compete\s+(?:work|apply))\b"
    r"|\b(?:non[- ]compete\s+(?:clause|agreement|restriction|clause)\s+(?:in\s+UAE|UAE|Dubai|enforceable|enforced|valid|apply))\b"
    r"|\b(?:can\s+(?:my\s+)?(?:employer|company)\s+(?:enforce|stop\s+me\s+with|use)\s+(?:a\s+)?non[- ]compete)\b"
    r"|\b(?:is\s+(?:my\s+|a\s+)?non[- ]compete\s+(?:enforceable|valid|legal|binding)(?:\s+(?:in\s+UAE|in\s+Dubai))?)\b"
    r"|\b(?:non[- ]compete\s+(?:UAE|Dubai|period|duration|restriction|terms?))\b"
    r"|\b(?:شرط\s+عدم\s+المنافسة|بند\s+عدم\s+المنافسة|اتفاقية\s+عدم\s+المنافسة)\b",
    re.IGNORECASE,
)

# UAE work visa / sponsorship process — "how do I get a UAE work visa?",
# "how does visa sponsorship work?", "what documents do I need for a work visa?".
# Distinct from _VISA_STATUS_RE (which handles profile declarations).
_WORK_VISA_PROCESS_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:get|apply\s+for|obtain)\s+(?:a\s+)?(?:UAE\s+)?work\s+(?:visa|permit))\b"
    r"|\b(?:how\s+(?:does|do)\s+(?:UAE\s+)?(?:work\s+)?visa\s+(?:sponsorship|process|application)\s+work)\b"
    r"|\b(?:what\s+(?:documents?|papers?)\s+(?:do\s+I\s+)?(?:need|require)\s+for\s+(?:a\s+)?(?:UAE\s+)?work\s+(?:visa|permit))\b"
    r"|\b(?:(?:UAE|Dubai)\s+work\s+(?:visa|permit)\s+(?:process|requirements?|application|guide|steps?|how\s+to\s+get|cost))\b"
    r"|\b(?:how\s+(?:long|much)\s+(?:does|do)\s+(?:it\s+take|I\s+need)\s+(?:to\s+get|for)\s+(?:a\s+)?(?:UAE\s+)?work\s+visa)\b"
    r"|\b(?:will\s+(?:the\s+)?(?:company|employer|they)\s+(?:sponsor|provide|arrange)\s+(?:my\s+)?visa)\b"
    r"|\b(?:what\s+is\s+(?:the\s+)?visa\s+sponsorship\s+(?:process|cost|timeline))\b"
    r"|\b(?:تأشيرة\s+العمل\s+(?:في\s+الإمارات|الإمارات)|كيف\s+أحصل\s+على\s+تأشيرة\s+عمل|إجراءات\s+تأشيرة\s+العمل)\b",
    re.IGNORECASE,
)

# Arabic language requirement for UAE jobs — "do I need to speak Arabic?",
# "will not speaking Arabic hurt my chances?", "how much Arabic do I need?".
_ARABIC_REQUIREMENT_RE = re.compile(
    r"\b(?:do\s+I\s+(?:need|have)\s+to\s+speak\s+Arabic)\b"
    r"|\b(?:(?:will|does)\s+(?:not\s+)?speaking\s+Arabic\s+(?:matter|help|hurt|affect|impact))\b"
    r"|\b(?:how\s+(?:much|important)\s+(?:is\s+)?Arabic\s+(?:do\s+I\s+need|is\s+(?:needed|required|important|useful)))\b"
    r"|\b(?:how\s+(?:important|useful|necessary|essential)\s+is\s+Arabic)\b"
    r"|\b(?:(?:is|are)\s+Arabic\s+(?:skills?|language)?\s+(?:required|necessary|needed|important|essential)\s+(?:for|in|to)\s+(?:UAE|Dubai|Abu\s+Dhabi|work|jobs?))\b"
    r"|\b(?:can\s+I\s+(?:work|get\s+a\s+job|find\s+(?:a\s+)?work)\s+in\s+(?:UAE|Dubai)\s+(?:without|if\s+I\s+don't\s+speak)\s+Arabic)\b"
    r"|\b(?:Arabic\s+(?:speaking|language|skills?)\s+(?:required|needed|necessary|job|jobs?|requirement|UAE|Dubai))\b"
    r"|\b(?:هل\s+أحتاج\s+(?:إلى\s+)?تعلم\s+العربية|هل\s+اللغة\s+العربية\s+ضرورية)\b",
    re.IGNORECASE,
)

# Background check / police clearance — "will they do a background check?",
# "do I need a police clearance certificate?", "what is checked in background screening?".
_BACKGROUND_CHECK_RE = re.compile(
    r"\b(?:(?:will|do)\s+(?:they|employers?|the\s+company)\s+(?:do|run|conduct|check)\s+(?:a\s+)?background\s+(?:check|screening|verification))\b"
    r"|\b(?:background\s+(?:check|screening|verification)\s+(?:UAE|Dubai|process|how|what|required|needed))\b"
    r"|\b(?:do\s+I\s+need\s+(?:a\s+)?(?:police\s+clearance|good\s+conduct\s+certificate|criminal\s+background\s+check))\b"
    r"|\b(?:police\s+(?:clearance|clearance\s+certificate|good\s+conduct|certificate)\s+(?:UAE|Dubai|for\s+(?:a\s+)?job|required|needed))\b"
    r"|\b(?:police\s+good\s+conduct\s+certificate(?:\s+for\s+(?:a\s+)?(?:job|UAE|work))?)\b"
    r"|\b(?:what\s+(?:do\s+they\s+|is\s+)?(?:check|verify|look\s+at)\s+in\s+(?:a\s+)?(?:background|employment)\s+(?:check|screening|verification))\b"
    r"|\b(?:شهادة\s+حسن\s+السيرة|تفتيش\s+الخلفية|فحص\s+السوابق\s+الجنائية)\b",
    re.IGNORECASE,
)

# Free zone vs mainland employment in UAE — "what is the difference between free zone and mainland?",
# "should I work in a free zone or mainland?", "is a free zone job different?".
_FREE_ZONE_MAINLAND_RE = re.compile(
    r"\b(?:(?:what\s+is|what's)\s+the\s+difference\s+between\s+(?:(?:a\s+)?free\s+zone\s+and\s+mainland|mainland\s+and\s+(?:a\s+)?free\s+zone))\b"
    r"|\b(?:(?:should\s+I|is\s+it\s+better\s+to)\s+(?:work|take\s+a\s+job)\s+in\s+(?:a\s+)?free\s+zone\s+(?:or|vs\.?|versus)\s+mainland)\b"
    r"|\b(?:free\s+zone\s+(?:vs\.?\s+mainland|job|employment|company|benefits?|advantages?|disadvantages?|rules?|restrictions?))\b"
    r"|\b(?:mainland\s+(?:vs\.?\s+free\s+zone|UAE|Dubai)\s+(?:job|employment|company|rules?|restrictions?))\b"
    r"|\b(?:(?:is|are)\s+(?:free\s+zone|mainland)\s+(?:jobs?|employment|companies?)\s+(?:different|better|worse|limited|restricted))\b"
    r"|\b(?:can\s+(?:I|a\s+free\s+zone\s+employee)\s+(?:work|be\s+employed?|be\s+hired?)\s+(?:outside|in)\s+(?:a\s+)?(?:free\s+zone|mainland))\b"
    r"|\b(?:المنطقة\s+الحرة\s+(?:مقابل|و)\s+البر\s+الرئيسي|الفرق\s+بين\s+المنطقة\s+الحرة\s+والبر\s+الرئيسي)\b",
    re.IGNORECASE,
)

# UAE working hours and overtime — "what are the working hours in UAE?",
# "is overtime paid?", "how many hours can I work?".
_WORKING_HOURS_RE = re.compile(
    r"\b(?:what\s+are\s+(?:the\s+)?(?:standard|typical|normal|UAE|legal|official)\s+working\s+hours)\b"
    r"|\b(?:how\s+(?:many|much)\s+hours\s+(?:do\s+I|can\s+I|should\s+I|per\s+week|a\s+week)\s+(?:work|have\s+to\s+work|am\s+I\s+allowed))\b"
    r"|\b(?:is\s+overtime\s+(?:paid|legal|mandatory|required|common|normal)\s+(?:in\s+UAE|in\s+Dubai)?)\b"
    r"|\b(?:how\s+(?:is|does)\s+overtime\s+(?:work|pay|calculated|count)\s+(?:in\s+UAE|in\s+Dubai)?)\b"
    r"|\b(?:overtime\s+(?:pay|rules?|laws?|calculation|rate|UAE|Dubai))\b"
    r"|\b(?:(?:UAE|Dubai)\s+working\s+hours\s+(?:rules?|laws?|limits?|per\s+week|maximum|regulation))\b"
    r"|\b(?:working\s+hours\s+(?:in\s+(?:UAE|Dubai)|UAE|Dubai|limit|maximum|per\s+week|regulations?))\b"
    r"|\b(?:ساعات\s+العمل\s+(?:في\s+الإمارات|القانونية|الرسمية)|العمل\s+الإضافي\s+في\s+الإمارات)\b",
    re.IGNORECASE,
)

# UAE Golden Visa — "what is the golden visa?", "how do I get a UAE golden visa?",
# "am I eligible for a golden visa?", "golden visa UAE requirements".
_GOLDEN_VISA_RE = re.compile(
    r"\b(?:what\s+is\s+(?:the\s+)?(?:UAE\s+)?golden\s+visa)\b"
    r"|\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:get|apply\s+for|qualify\s+for|obtain)\s+(?:a\s+)?(?:UAE\s+)?golden\s+visa)\b"
    r"|\b(?:golden\s+visa\s+(?:UAE|Dubai|requirements?|eligibility|cost|application|process|benefits?|categories?))\b"
    r"|\b(?:am\s+I\s+(?:eligible|qualified)\s+for\s+(?:a\s+)?(?:UAE\s+)?golden\s+visa)\b"
    r"|\b(?:(?:UAE|Dubai)\s+golden\s+visa\s+(?:requirements?|how\s+to\s+get|eligibility|apply|process|benefits?))\b"
    r"|\b(?:10[- ]year\s+(?:UAE\s+)?(?:visa|residence|residency))\b"
    r"|\b(?:تأشيرة\s+الذهبية\s+الإمارات|الإقامة\s+الذهبية|الفيزا\s+الذهبية)\b",
    re.IGNORECASE,
)

# Professional references — "how do I ask for a reference?", "who should I use as a reference?",
# "my employer asked for references", "reference check after offer".
_JOB_REFERENCES_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|should\s+I)\s+(?:ask\s+for|request|get|find|choose|pick)\s+(?:a\s+)?(?:professional\s+)?reference)\b"
    r"|\b(?:who\s+(?:should\s+I|can\s+I)\s+(?:use|list|give|put)\s+as\s+(?:a\s+)?(?:reference|referee))\b"
    r"|\b(?:(?:professional\s+)?references?\s+(?:for\s+a\s+job|on\s+(?:my\s+)?CV|UAE|tips?|advice|guide|check))\b"
    r"|\b(?:(?:my\s+)?(?:employer|company)\s+(?:asked|is\s+asking)\s+for\s+references?)\b"
    r"|\b(?:reference\s+check\s+(?:after\s+(?:the\s+)?offer|process|UAE|how))\b"
    r"|\b(?:can\s+(?:I|they)\s+(?:contact|call|reach)\s+my\s+(?:previous|current|old)\s+(?:employer|manager|boss)\s+(?:as\s+a\s+)?reference)\b"
    r"|\b(?:المراجع\s+المهنية|كيف\s+أطلب\s+(?:توصية|مرجع\s+مهني)|خطاب\s+التوصية)\b",
    re.IGNORECASE,
)

# Interview / office dress code in UAE — "what should I wear to an interview?",
# "what is the dress code in UAE offices?", "is smart casual ok?".
_DRESS_CODE_RE = re.compile(
    r"\b(?:what\s+(?:should\s+I|to)\s+(?:wear|dress)\s+(?:to|for)\s+(?:(?:a|an|the)\s+)?(?:job\s+)?interview)\b"
    r"|\b(?:how\s+(?:should\s+I|do\s+I)\s+(?:dress|look)\s+(?:for|at|to)\s+(?:(?:a|an|the|my)\s+)?(?:job\s+)?interview)\b"
    r"|\b(?:(?:office|workplace|interview|professional)\s+dress\s+(?:code|standard)\s+(?:UAE|Dubai|in\s+UAE|in\s+Dubai)?)\b"
    r"|\b(?:dress\s+code\s+(?:UAE|Dubai|for\s+(?:a\s+)?(?:job\s+)?interview|in\s+(?:UAE|Dubai)))\b"
    r"|\b(?:(?:is|are)\s+(?:smart\s+casual|business\s+casual|formal\s+dress|suit)\s+(?:ok|required|appropriate|expected)\s+(?:in|for)\s+(?:UAE|Dubai|an?\s+interview)?)\b"
    r"|\b(?:what\s+(?:to|should\s+I)\s+(?:wear|dress)\s+(?:in|to)\s+(?:a\s+)?(?:UAE|Dubai)\s+(?:office|interview))\b"
    r"|\b(?:كيف\s+أرتدي|ماذا\s+أرتدي)\s+(?:في\s+المقابلة|للمقابلة|في\s+العمل)\b",
    re.IGNORECASE,
)

# Working remotely for a foreign company from UAE — "can I work remotely from UAE?",
# "do I need a visa to work remote for a UK company?", "remote work tax UAE".
_REMOTE_WORK_UAE_RE = re.compile(
    r"\b(?:can\s+I\s+work\s+remotely\s+(?:from|in)\s+(?:UAE|Dubai|the\s+UAE|Abu\s+Dhabi))\b"
    r"|\b(?:can\s+I\s+work\s+for\s+(?:a\s+)?(?:foreign|international|overseas|UK|US|European?)\s+company\s+(?:from|in|while\s+(?:in|living\s+in))\s+(?:UAE|Dubai|the\s+UAE))\b"
    r"|\b(?:do\s+I\s+need\s+(?:a\s+)?visa\s+to\s+work\s+remotely\s+(?:from|in)\s+(?:UAE|Dubai|the\s+UAE))\b"
    r"|\b(?:remote\s+work\s+(?:from|in)\s+(?:UAE|Dubai|the\s+UAE)\s+(?:visa|permit|rules?|allowed|legal|tax|regulations?))\b"
    r"|\b(?:(?:UAE|Dubai)\s+remote\s+work\s+(?:visa|permit|rules?|allowed|legal|tax|policy))\b"
    r"|\b(?:digital\s+nomad\s+(?:visa\s+UAE|UAE|Dubai|in\s+(?:UAE|Dubai)))\b"
    r"|\b(?:tax\s+(?:implications?|on\s+remote\s+work|on\s+income)\s+(?:UAE|Dubai|working\s+remotely\s+in\s+UAE))\b"
    r"|\b(?:العمل\s+عن\s+بُعد\s+(?:من|في)\s+الإمارات|تأشيرة\s+العمل\s+عن\s+بُعد\s+الإمارات)\b",
    re.IGNORECASE,
)

# Annual leave entitlement in UAE — "how many days annual leave in UAE?",
# "what is the leave entitlement?", "public holidays UAE".
_ANNUAL_LEAVE_RE = re.compile(
    r"\b(?:how\s+many\s+(?:days?\s+)?(?:annual\s+leave|vacation\s+days?|leave\s+days?|paid\s+leave)\s+(?:do\s+I\s+(?:get|have)|am\s+I\s+(?:entitled|owed)|in\s+(?:UAE|Dubai)))\b"
    r"|\b(?:(?:annual\s+leave|paid\s+leave|vacation)\s+(?:days?|entitlement|rights?|policy|in\s+UAE|UAE|allowance))\b"
    r"|\b(?:how\s+(?:much|many)\s+(?:annual\s+)?leave\s+(?:do\s+I\s+(?:get|have)|am\s+I\s+entitled\s+to)\s+(?:in\s+UAE)?)\b"
    r"|\b(?:(?:UAE|Dubai)\s+(?:annual\s+)?leave\s+(?:entitlement|days?|policy|rules?|law))\b"
    r"|\b(?:public\s+holidays?\s+(?:in\s+(?:UAE|Dubai)|UAE|Dubai|list|how\s+many))\b"
    r"|\b(?:(?:how\s+many|what\s+are\s+the)\s+public\s+holidays?\s+in\s+(?:UAE|Dubai))\b"
    r"|\b(?:إجازة\s+سنوية\s+(?:في\s+الإمارات|الإمارات)|أيام\s+الإجازة\s+السنوية)\b",
    re.IGNORECASE,
)

# Sick / medical leave in UAE — "how many sick days do I get?",
# "sick leave rules UAE", "what is the sick leave policy?".
_SICK_LEAVE_RE = re.compile(
    r"\b(?:how\s+(?:many|much)\s+sick\s+(?:days?|leave)\s+(?:do\s+I\s+(?:get|have)|am\s+I\s+entitled\s+to|in\s+UAE))\b"
    r"|\b(?:sick\s+(?:leave|day|days?)\s+(?:policy|rules?|UAE|Dubai|entitlement|rights?|law))\b"
    r"|\b(?:(?:UAE|Dubai)\s+sick\s+(?:leave|day|days?)\s+(?:policy|rules?|entitlement|rights?|law))\b"
    r"|\b(?:medical\s+leave\s+(?:UAE|Dubai|entitlement|rights?|policy|rules?))\b"
    r"|\b(?:what\s+(?:is|are)\s+(?:the\s+)?sick\s+(?:leave\s+)?(?:policy|rules?|entitlement)\s+(?:in\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:how\s+long\s+can\s+I\s+(?:take|be\s+on)\s+sick\s+leave)\b"
    r"|\b(?:إجازة\s+مرضية\s+(?:في\s+الإمارات|الإمارات)|أيام\s+الإجازة\s+المرضية)\b",
    re.IGNORECASE,
)

# Maternity / paternity leave in UAE — "how much maternity leave in UAE?",
# "paternity leave UAE", "parental leave rights UAE".
_PARENTAL_LEAVE_RE = re.compile(
    r"\b(?:how\s+(?:much|many\s+(?:weeks?|days?))\s+(?:maternity|paternity|parental)\s+leave\s+(?:do\s+I\s+get|in\s+UAE|am\s+I\s+entitled\s+to))\b"
    r"|\b(?:(?:maternity|paternity|parental)\s+leave\s+(?:UAE|Dubai|entitlement|rights?|policy|rules?|law|paid|weeks?|months?))\b"
    r"|\b(?:(?:UAE|Dubai)\s+(?:maternity|paternity|parental)\s+leave\s+(?:policy|rules?|entitlement|rights?|law))\b"
    r"|\b(?:am\s+I\s+(?:entitled|eligible)\s+(?:to|for)\s+(?:maternity|paternity|parental)\s+leave)\b"
    r"|\b(?:is\s+(?:maternity|paternity|parental)\s+leave\s+(?:paid|mandatory|legal|required)\s+(?:in\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:إجازة\s+(?:الأمومة|الأبوة|الوضع)\s+(?:في\s+الإمارات|الإمارات|المدفوعة))\b",
    re.IGNORECASE,
)

# Probation period rules — "what happens during probation?", "can I be fired during probation?",
# "how long is probation?". Distinct from UAE labor law general handler.
_PROBATION_RULES_RE = re.compile(
    r"\b(?:what\s+(?:happens?|can\s+(?:they|my\s+employer)\s+do)\s+during\s+(?:my\s+)?probation(?:ary)?(?:\s+period)?)\b"
    r"|\b(?:can\s+(?:I\s+be|my\s+employer)\s+(?:fired?|dismiss(?:ed)?|terminat(?:ed?|e))\s+during\s+(?:my\s+)?probation(?:ary)?(?:\s+period)?)\b"
    r"|\b(?:can\s+I\s+(?:resign|quit|leave)\s+during\s+(?:my\s+)?probation(?:ary)?(?:\s+period)?)\b"
    r"|\b(?:how\s+long\s+is\s+(?:the\s+)?probation(?:ary)?(?:\s+period)?)\b"
    r"|\b(?:probation(?:ary)?\s+period\s+(?:rules?|rights?|notice|termination|dismissal|resignation|notice\s+period|UAE|Dubai))\b"
    r"|\b(?:what\s+(?:are\s+(?:(?:my|the)\s+)?)?(?:rights?|rules?)\s+during\s+(?:my\s+)?probation(?:ary)?(?:\s+period)?)\b"
    r"|\b(?:فترة\s+(?:التجربة|الاختبار)\s+(?:في\s+الإمارات|أحكام|حقوق|إنهاء))\b",
    re.IGNORECASE,
)

# Termination notice period in UAE — "how much notice do I need to give?",
# "notice period UAE", "can my employer fire me without notice?".
_NOTICE_PERIOD_RE = re.compile(
    r"\b(?:how\s+(?:much|long\s+(?:a?\s+)?is\s+(?:the\s+)?|many\s+days\s+(?:is\s+)?)\s*notice\s+(?:do\s+I\s+(?:need\s+to\s+give|have\s+to\s+give|need)|period|must\s+I\s+give))\b"
    r"|\b(?:what\s+(?:is|are|'s)\s+(?:the\s+)?(?:my\s+)?notice\s+period(?:\s+(?:in\s+(?:UAE|Dubai)|UAE|Dubai|rules?|law|requirement|for\s+resignation|for\s+termination))?)\b"
    r"|\b(?:notice\s+period\s+(?:in\s+(?:UAE|Dubai)|UAE|Dubai|rules?|law|requirement|for\s+resignation|for\s+termination))\b"
    r"|\b(?:can\s+(?:my\s+)?(?:employer|company|they)\s+(?:fire|dismiss|terminate|let\s+me\s+go)\s+(?:me\s+)?(?:without|with\s+no)\s+notice)\b"
    r"|\b(?:how\s+(?:much|many)\s+notice\s+(?:do\s+I\s+(?:need\s+to\s+give|have\s+to\s+give)|must\s+I\s+give)\s+(?:when\s+)?(?:resigning|quitting|leaving|if\s+I\s+resign|if\s+I\s+quit))\b"
    r"|\b(?:(?:resignation|termination|dismissal)\s+notice\s+(?:period|UAE|Dubai|rules?|law|requirement))\b"
    r"|\b(?:what\s+(?:is|are)\s+(?:the\s+)?(?:notice|resignation|termination)\s+(?:period\s+)?(?:rules?|requirements?|laws?)\s+(?:in\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:مدة\s+الإخطار|فترة\s+الإشعار\s+(?:في\s+الإمارات|عند\s+الاستقالة)|الإخطار\s+بإنهاء\s+العقد)\b",
    re.IGNORECASE,
)

# UAE Wage Protection System (WPS) — "what is WPS?", "my salary is late",
# "employer not paying salary on time UAE".
_WPS_SALARY_PROTECTION_RE = re.compile(
    r"\b(?:what\s+is\s+(?:the\s+)?(?:UAE\s+)?(?:WPS|wage\s+protection\s+system))\b"
    r"|\b(?:WPS\s+(?:UAE|Dubai|law|rules?|fine|salary|payment|system))\b"
    r"|\b(?:my\s+(?:salary|wage|pay)\s+(?:is|was|has\s+been)\s+(?:late|delayed|not\s+paid|overdue|unpaid|withheld))\b"
    r"|\b(?:(?:employer|company|they)\s+(?:is|has|hasn't|have\s+not|has\s+not)\s+(?:not\s+)?(?:paid|paying)\s+(?:my\s+)?(?:salary|wages?|pay)(?:\s+(?:on\s+time|late|yet))?)\b"
    r"|\b(?:(?:salary|wage)\s+(?:protection|late\s+payment|not\s+paid|delay|delayed|overdue|withheld)\s+(?:UAE|Dubai|law|rules?|complaint|fine)?)\b"
    r"|\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:report|complain\s+about|file\s+a\s+complaint\s+(?:about|for))\s+(?:(?:a\s+)?(?:late|unpaid|withheld)\s+)?(?:salary|wage|pay))\b"
    r"|\b(?:late\s+(?:salary|wage|pay|payment)\s+(?:UAE|Dubai)?)\b"
    r"|\b(?:nakheel\s+(?:salary|complaint)|mohre\s+(?:salary|complaint|WPS))\b"
    r"|\b(?:نظام\s+حماية\s+الأجور|تأخر\s+(?:صرف\s+)?الراتب\s+(?:في\s+الإمارات)?|الراتب\s+(?:متأخر|لم\s+يُصرف))\b",
    re.IGNORECASE,
)

# Employer-provided health insurance in UAE — "do I get health insurance from my employer?",
# "is medical insurance mandatory UAE?", "what does company health insurance cover?".
_EMPLOYER_HEALTH_INSURANCE_RE = re.compile(
    r"\b(?:(?:do|does|will|is)\s+(?:my\s+)?(?:employer|company|they)\s+(?:provide|give|cover|offer|include)\s+(?:me\s+)?(?:health|medical)\s+insurance)\b"
    r"|\b(?:is\s+(?:health|medical)\s+insurance\s+(?:mandatory|required|provided|included|compulsory|a\s+benefit)\s+(?:in\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:(?:health|medical)\s+insurance\s+(?:UAE|Dubai|provided\s+by\s+employer|from\s+employer|mandatory|compulsory|benefit|coverage|law))\b"
    r"|\b(?:what\s+(?:does|do|is)\s+(?:(?:(?:the|my|a)\s+)?(?:company|employer|work)\s+)?(?:health|medical)\s+insurance\s+(?:cover|include|provide))\b"
    r"|\b(?:(?:company|employer|work)\s+(?:health|medical)\s+insurance\s+(?:UAE|Dubai|coverage|plan|policy|benefit))\b"
    r"|\b(?:do\s+I\s+(?:get|have|need)\s+(?:to\s+buy|my\s+own\s+)?(?:health|medical)\s+insurance\s+(?:in\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:تأمين\s+صحي\s+(?:من\s+صاحب\s+العمل|الإمارات|إلزامي|مقدم))\b",
    re.IGNORECASE,
)

# Visa cancellation grace period — "how long do I have after my visa is cancelled?",
# "grace period after resignation UAE", "how long can I stay after losing my job UAE".
_VISA_CANCELLATION_RE = re.compile(
    r"\b(?:how\s+long\s+(?:do\s+I\s+have|can\s+I\s+stay)\s+(?:after|once)\s+(?:my\s+)?visa\s+(?:is\s+)?(?:cancelled|canceled|terminated|expired|ends?))\b"
    r"|\b(?:how\s+long\s+(?:do\s+I\s+have|can\s+I\s+stay)\s+(?:in\s+(?:UAE|Dubai)\s+)?after\s+(?:losing|leaving|quitting|resigning\s+from|being\s+fired\s+from|termination\s+of)\s+(?:my\s+)?job)\b"
    r"|\b(?:visa\s+cancellation\s+(?:grace\s+period|UAE|Dubai|process|time\s+(?:to\s+leave|limit)|how\s+long))\b"
    r"|\b(?:grace\s+period\s+after\s+(?:visa\s+cancellation|job\s+loss|resignation|termination)(?:\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:(?:what\s+happens?\s+to\s+(?:my\s+)?visa|what\s+(?:is|are)\s+(?:my\s+)?visa\s+(?:options?|status))\s+(?:after|when|once|if)\s+(?:I\s+(?:resign|quit|lose\s+(?:my\s+)?job)|(?:my\s+)?(?:job|contract)\s+(?:ends?|is\s+terminated)))\b"
    r"|\b(?:how\s+(?:soon|quickly)\s+(?:do\s+I\s+have\s+to|must\s+I)\s+(?:leave|exit|depart)\s+(?:UAE|Dubai|the\s+country)\s+after\s+(?:losing|leaving)\s+(?:my\s+)?job)\b"
    r"|\b(?:(?:can\s+I|am\s+I\s+allowed\s+to)\s+stay\s+in\s+(?:UAE|Dubai)\s+after\s+(?:my\s+)?(?:visa\s+(?:is\s+)?(?:cancelled|canceled)|job\s+ends?))\b"
    r"|\b(?:تأشيرة\s+بعد\s+(?:فقدان|ترك)\s+العمل|فترة\s+السماح\s+بعد\s+إلغاء\s+التأشيرة|مدة\s+البقاء\s+بعد\s+إلغاء\s+التأشيرة)\b",
    re.IGNORECASE,
)

# Emiratisation / Nafis impact on expat hiring — "does Emiratisation affect my chances?",
# "what is Nafis?", "can expats still get jobs with Emiratisation?".
_EMIRATISATION_RE = re.compile(
    r"\b(?:what\s+is\s+(?:Emiratisation|Nafis|Emirati\s+workforce\s+(?:quota|target)))\b"
    r"|\b(?:how\s+(?:does|do)\s+(?:Emiratisation|Nafis)\s+(?:affect|impact|work|apply|influence))\b"
    r"|\b(?:(?:does|will)\s+Emiratisation\s+(?:affect|impact|hurt|reduce|limit)\s+(?:my\s+)?(?:chances?|job\s+chances?|job\s+prospects?|applications?|opportunities?))\b"
    r"|\b(?:(?:can|do)\s+expats?\s+(?:still|even)\s+(?:get|find|apply\s+for)\s+jobs?\s+(?:in\s+(?:UAE|Dubai)\s+)?(?:with|despite|under)\s+Emiratisation)\b"
    r"|\b(?:Emiratisation\s+(?:quota|target|rules?|laws?|requirements?|UAE|Dubai|policy|percentage))\b"
    r"|\b(?:Nafis\s+(?:UAE|Dubai|programme|program|scheme|subsidy|benefit|quota|policy))\b"
    r"|\b(?:(?:UAE|Dubai)\s+Emiratisation\s+(?:quota|target|percentage|rules?|impact|policy))\b"
    r"|\b(?:التوطين\s+(?:في\s+الإمارات|الإمارات|النسب|السياسة)|برنامج\s+نافس|نسبة\s+التوطين)\b",
    re.IGNORECASE,
)

# Job scam detection in UAE — "how do I know if a UAE job offer is a scam?",
# "is this job offer real?", "red flags in UAE job offers".
_JOB_SCAM_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:know|tell|spot|identify|detect|avoid|check)\s+(?:if\s+(?:a\s+|the\s+|this\s+)?)?(?:UAE\s+)?(?:job\s+offer|job|opportunity|recruiter)\s+is\s+(?:a\s+)?(?:scam|fake|fraud|legitimate|legit|real))\b"
    r"|\b(?:is\s+(?:this|that|the)\s+(?:job\s+offer|job|opportunity|recruiter|company)\s+(?:a\s+)?(?:scam|fake|fraud|legit|legitimate|real))\b"
    r"|\b(?:(?:job|recruitment|employment)\s+(?:scam|fraud|fake\s+offer)\s+(?:UAE|Dubai|signs?|red\s+flags?|warning\s+signs?|how\s+to\s+(?:spot|avoid)))\b"
    r"|\b(?:red\s+flags?\s+(?:in|for|of)\s+(?:(?:UAE|Dubai)\s+)?(?:job\s+offers?|job\s+listings?|recruiters?|job\s+ads?))\b"
    r"|\b(?:(?:how\s+to|can\s+I)\s+(?:verify|check|confirm)\s+(?:a\s+|the\s+|if\s+(?:a\s+|the\s+)?)?(?:job\s+offer|company|recruiter)\s+is\s+(?:legitimate|legit|real|genuine))\b"
    r"|\b(?:(?:I\s+think|is\s+it\s+possible\s+that|could)\s+this\s+(?:job\s+offer|job|opportunity)\s+(?:is|be)\s+(?:a\s+)?(?:scam|fake|too\s+good\s+to\s+be\s+true))\b"
    r"|\b(?:fake\s+(?:job|work)\s+(?:offer|listing|ad|opportunity)(?:\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:احتيال\s+وظيفي\s+(?:في\s+الإمارات|الإمارات)|عروض\s+عمل\s+وهمية|كيف\s+أعرف\s+(?:إذا|إن)\s+(?:كان\s+)?العرض\s+حقيقي)\b",
    re.IGNORECASE,
)

# Salary certificate / employment letter in UAE — "how do I get a salary certificate?",
# "my bank needs an employment letter", "what is a NOC letter?".
_SALARY_CERTIFICATE_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:get|obtain|request|ask\s+for)\s+(?:a\s+|an\s+)?(?:salary\s+certificate|employment\s+(?:letter|certificate)|NOC\s+letter|no\s+objection\s+certificate|salary\s+letter))\b"
    r"|\b(?:(?:salary\s+certificate|employment\s+letter|NOC\s+letter|no\s+objection\s+certificate|salary\s+letter)\s+(?:UAE|Dubai|from\s+employer|request|for\s+(?:bank|visa|loan|mortgage)))\b"
    r"|\b(?:(?:my\s+)?(?:bank|embassy|landlord)\s+(?:needs?|requires?|asked?\s+for|is\s+asking\s+for)\s+(?:a\s+|an\s+)?(?:salary\s+certificate|employment\s+letter|NOC|proof\s+of\s+employment|salary\s+proof))\b"
    r"|\b(?:(?:how\s+to|can\s+I)\s+(?:get|request|ask\s+for)\s+(?:a\s+|an\s+)?(?:NOC|no\s+objection\s+certificate)\s+(?:from\s+my\s+employer|UAE|to\s+(?:change\s+jobs?|leave\s+the\s+company)))\b"
    r"|\b(?:what\s+is\s+(?:a\s+|an\s+)?(?:NOC\s+letter|no\s+objection\s+certificate|salary\s+certificate|employment\s+letter)(?:\s+in\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:شهادة\s+الراتب|خطاب\s+(?:العمل|الراتب|عدم\s+الممانعة|التوظيف)(?:\s+(?:الإمارات|من\s+صاحب\s+العمل))?)\b",
    re.IGNORECASE,
)

# Networking in UAE — "how do I network in Dubai?", "how do I find jobs through connections?",
# "are there networking events in UAE?".
_NETWORKING_UAE_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|can\s+I)\s+(?:network|build\s+(?:my\s+)?(?:network|connections?)|meet\s+(?:professionals?|people))\s+(?:in\s+(?:UAE|Dubai|Abu\s+Dhabi)|for\s+(?:UAE|Dubai)\s+jobs?))\b"
    r"|\b(?:networking\s+(?:in\s+(?:UAE|Dubai)|UAE|Dubai|events?|tips?|advice|how\s+to|opportunities?))\b"
    r"|\b(?:(?:UAE|Dubai)\s+networking\s+(?:events?|tips?|advice|how\s+to|opportunities?|groups?|communities?))\b"
    r"|\b(?:how\s+(?:do\s+I|to|can\s+I)\s+find\s+jobs?\s+(?:through|via|using)\s+(?:my\s+)?(?:connections?|network|referrals?|contacts?))\b"
    r"|\b(?:(?:professional\s+)?networking\s+events?\s+(?:in\s+(?:UAE|Dubai)|UAE|Dubai))\b"
    r"|\b(?:how\s+(?:important|useful|effective)\s+(?:is|are)\s+(?:networking|referrals?|connections?)\s+(?:in|for)\s+(?:UAE|Dubai)(?:\s+jobs?)?)\b"
    r"|\b(?:التواصل\s+المهني\s+(?:في\s+الإمارات|الإمارات)|كيف\s+أبني\s+شبكة\s+علاقات\s+(?:في\s+الإمارات)?)\b",
    re.IGNORECASE,
)

# Asking for a promotion in UAE — "how do I ask for a promotion?",
# "when is the right time to ask for a raise?", "promotion advice UAE".
_PROMOTION_UAE_RE = re.compile(
    r"\b(?:how\s+(?:do\s+I|to|should\s+I|can\s+I)\s+(?:ask\s+for|request|get|earn|go\s+for)\s+(?:a\s+)?promotion)\b"
    r"|\b(?:when\s+(?:should\s+I|is\s+(?:the\s+)?(?:right\s+)?time\s+to)\s+ask\s+for\s+(?:a\s+)?promotion)\b"
    r"|\b(?:promotion\s+(?:tips?|advice|strategy|UAE|Dubai|how\s+to\s+(?:get|ask|earn)|timing|request))\b"
    r"|\b(?:how\s+(?:do\s+I|to|should\s+I)\s+(?:get\s+(?:promoted|a\s+promotion)|advance\s+(?:in|at)\s+(?:work|my\s+career|my\s+job)|move\s+up\s+(?:in|at)\s+(?:work|my\s+career)))\b"
    r"|\b(?:(?:I\s+(?:want|deserve)|do\s+I\s+(?:deserve|qualify\s+for))\s+(?:a\s+)?promotion)\b"
    r"|\b(?:what\s+(?:do\s+I\s+need\s+to\s+do|does\s+it\s+take)\s+to\s+(?:get\s+promoted|earn\s+(?:a\s+)?promotion))\b"
    r"|\b(?:كيف\s+(?:أطلب|أحصل\s+على)\s+(?:ترقية|ترقيتي)|نصائح\s+(?:للحصول\s+على\s+)?الترقية)\b",
    re.IGNORECASE,
)

# Handling job rejection / asking for feedback — "I got rejected, what should I do?",
# "should I ask for feedback after rejection?", "how to bounce back from rejection".
_JOB_REJECTION_RE = re.compile(
    r"\b(?:(?:I\s+(?:got|received|was\s+(?:sent|given)))\s+(?:a\s+)?(?:rejection|rejected)\s+(?:email|letter|message|from\s+(?:the\s+)?(?:company|employer|recruiter))?)\b"
    r"|\b(?:I\s+(?:was|got)\s+rejected(?:\s+(?:by|from)\s+(?:the\s+)?(?:company|employer|recruiter|job))?)\b"
    r"|\b(?:should\s+I\s+(?:ask\s+for|request)\s+feedback\s+after\s+(?:a\s+)?rejection)\b"
    r"|\b(?:how\s+(?:do\s+I|to|should\s+I|can\s+I)\s+(?:ask\s+for|request)\s+(?:feedback|reasons?)\s+after\s+(?:a\s+|being\s+)?rejected)\b"
    r"|\b(?:how\s+(?:do\s+I|to|should\s+I|can\s+I)\s+(?:handle|deal\s+with|bounce\s+back\s+from|recover\s+from|respond\s+to)\s+(?:a\s+)?(?:job\s+)?rejection)\b"
    r"|\b(?:(?:job\s+)?rejection\s+(?:tips?|advice|how\s+to\s+(?:handle|deal|respond)|feedback|after\s+rejection|recovery))\b"
    r"|\b(?:I\s+(?:didn't|did\s+not)\s+get\s+(?:the\s+)?job)\b"
    r"|\b(?:رُفِض\s+طلبي|رفضت\s+شركة|كيف\s+أتعامل\s+مع\s+رفض\s+الوظيفة|هل\s+أطلب\s+تغذية\s+راجعة\s+بعد\s+الرفض)\b",
    re.IGNORECASE,
)

# Counter-offer from current employer — "my employer made me a counter-offer",
# "should I accept a counter-offer?", "my boss offered me a raise to stay".
_COUNTER_OFFER_RE = re.compile(
    r"\b(?:(?:my\s+)?(?:employer|company|boss|manager)\s+(?:made|gave|offered)\s+(?:me\s+)?(?:a\s+)?counter[- ]?offer)\b"
    r"|\b(?:should\s+I\s+(?:accept|take|consider|reject|turn\s+down)\s+(?:a\s+|the\s+)?counter[- ]?offer)\b"
    r"|\b(?:my\s+(?:employer|company|boss)\s+(?:offered|is\s+offering|wants\s+to)\s+(?:me\s+)?(?:a\s+)?(?:raise|salary\s+increase|promotion)\s+(?:to\s+)?(?:stay|keep\s+me|not\s+leave))\b"
    r"|\b(?:counter[- ]?offer\s+(?:advice|tips?|should\s+I\s+(?:accept|take|consider)|dangers?|risks?|UAE|dilemma))\b"
    r"|\b(?:is\s+it\s+(?:worth|safe|wise|good\s+idea)\s+(?:to\s+)?accept(?:ing)?\s+(?:a\s+)?counter[- ]?offer)\b"
    r"|\b(?:عرض\s+مضاد\s+(?:من\s+صاحب\s+العمل|الشركة|الإمارات)|هل\s+أقبل\s+العرض\s+المضاد)\b",
    re.IGNORECASE,
)

# Relocation package for UAE — "what should a UAE relocation package include?",
# "should I negotiate my relocation package?", "typical UAE relocation benefits".
_RELOCATION_PACKAGE_RE = re.compile(
    r"\b(?:what\s+(?:should|does|is|is\s+in)\s+(?:a\s+|the\s+)?(?:UAE\s+)?relocation\s+package\s+(?:include|cover|contain|typical|look\s+like))\b"
    r"|\b(?:(?:UAE|Dubai)\s+relocation\s+package\s+(?:include|cover|benefits?|typical|what|negotiate|standard))\b"
    r"|\b(?:relocation\s+(?:allowance|package|benefit|costs?|expenses?)\s+(?:UAE|Dubai|for\s+(?:UAE|Dubai)|typical|negotiate|standard|include))\b"
    r"|\b(?:should\s+I\s+(?:negotiate|ask\s+for|request)\s+(?:(?:a|my)\s+)?relocation\s+(?:package|allowance|benefit|costs?))\b"
    r"|\b(?:(?:housing|accommodation|flight|moving)\s+allowance\s+(?:UAE|Dubai|from\s+employer|typical|negotiate))\b"
    r"|\b(?:(?:what|how)\s+(?:is|does)\s+(?:a\s+)?(?:UAE\s+)?relocation\s+(?:package|allowance)\s+(?:typically\s+)?(?:include|cover|work|mean))\b"
    r"|\b(?:بدل\s+(?:الانتقال|السكن|التنقل)\s+(?:الإمارات|الوظيفي)|حزمة\s+الانتقال\s+(?:إلى\s+الإمارات|الإمارات))\b",
    re.IGNORECASE,
)

# ── Public holidays UAE ────────────────────────────────────────────────────────
# "what are UAE public holidays?", "Eid holiday UAE", "UAE national day".
_PUBLIC_HOLIDAYS_UAE_RE = re.compile(
    r"\b(?:(?:what\s+are\s+(?:the\s+)?)?(?:UAE|Dubai)\s+(?:public|national|official)\s+holidays?)\b"
    r"|\b(?:(?:public|national|official)\s+holidays?\s+(?:in\s+(?:UAE|Dubai)|UAE|Dubai))\b"
    r"|\b(?:how\s+(?:many|much)\s+(?:public|national|official)\s+holidays?\s+(?:in|does|do|are|get)(?:\s+(?:UAE|Dubai|we|I))?)\b"
    r"|\b(?:(?:Eid|UAE\s+national\s+day|Prophet['']s\s+birthday|Islamic\s+new\s+year)\s+(?:holiday|off|public\s+holiday|day\s+off))\b"
    r"|\b(?:when\s+is\s+(?:(?:UAE|Dubai)\s+)?national\s+day|when\s+is\s+Eid\s+(?:al[- ]fitr|al[- ]adha|ul[- ]fitr|ul[- ]adha))\b"
    r"|\b(?:(?:UAE|Dubai)\s+(?:national\s+day|Eid)\s+(?:holiday|off|date|when))\b"
    r"|\b(?:(?:list\s+of|what\s+are)\s+(?:the\s+)?(?:UAE|Dubai)\s+(?:public\s+)?holidays?)\b"
    r"|\b(?:عطلة\s+(?:وطنية|رسمية|عيد)\s+(?:الإمارات|في\s+الإمارات)|الإجازات\s+الرسمية\s+(?:في\s+الإمارات)?)\b",
    re.IGNORECASE,
)

# ── Overtime pay UAE ───────────────────────────────────────────────────────────
# "am I entitled to overtime?", "overtime rate UAE", "how is overtime calculated?".
_OVERTIME_PAY_UAE_RE = re.compile(
    r"\b(?:am\s+I\s+(?:entitled\s+to|eligible\s+for|supposed\s+to\s+get|owed)\s+(?:paid\s+)?overtime)\b"
    r"|\b(?:how\s+(?:is|are|do\s+I\s+calculate)\s+overtime\s+(?:calculated|paid|work|hours?))\b"
    r"|\b(?:overtime\s+(?:pay|rate|hours?|calculation|entitlement|rules?|law|UAE|Dubai|rights?|policy))\b"
    r"|\b(?:(?:UAE|Dubai)\s+overtime\s+(?:pay|rate|law|rules?|entitlement|calculation))\b"
    r"|\b(?:(?:do|does|will|is)\s+(?:my\s+)?(?:employer|company|they)\s+(?:pay|owe\s+me|have\s+to\s+pay)\s+(?:for\s+)?overtime)\b"
    r"|\b(?:(?:my\s+)?(?:employer|company)\s+(?:is|are|was|won't|refuses?\s+to)\s+(?:not\s+)?(?:pay(?:ing)?|paid)\s+(?:me\s+)?(?:for\s+)?overtime)\b"
    r"|\b(?:what\s+(?:is|are)\s+(?:the\s+)?overtime\s+(?:rate|rules?|entitlement|pay)\s+(?:in\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:how\s+much\s+(?:extra\s+)?(?:do\s+I\s+(?:get|earn)|am\s+I\s+(?:paid|owed))\s+for\s+(?:working\s+)?overtime)\b"
    r"|\b(?:أجر\s+(?:العمل\s+الإضافي|الوقت\s+الإضافي)|ساعات\s+إضافية\s+(?:الإمارات|مدفوعة))\b",
    re.IGNORECASE,
)

# ── Contract types UAE (limited vs unlimited) ─────────────────────────────────
# "limited vs unlimited contract", "what happens when contract expires?".
_CONTRACT_TYPES_UAE_RE = re.compile(
    r"\b(?:(?:what\s+is\s+(?:the\s+)?difference\s+between|difference\s+between)\s+(?:a\s+)?limited\s+and\s+unlimited\s+(?:term\s+)?contract)\b"
    r"|\b(?:limited\s+(?:term\s+)?(?:vs\.?\s+|or\s+|versus\s+)?unlimited\s+(?:term\s+)?contract(?:\s+(?:UAE|Dubai))?)\b"
    r"|\b(?:(?:what\s+(?:is|are)\s+(?:a|the)\s+)?(?:limited|unlimited)\s+(?:term\s+)?contract\s+(?:UAE|Dubai|rules?|rights?|difference|type))\b"
    r"|\b(?:(?:what\s+happens?\s+(?:when|if|after))\s+(?:my\s+)?(?:limited\s+(?:term\s+)?)?contract\s+(?:expires?|ends?|is\s+not\s+renewed))\b"
    r"|\b(?:contract\s+(?:type|types?|renewal|non[- ]renewal|expiry|expired)\s+(?:UAE|Dubai|rules?|rights?|law))\b"
    r"|\b(?:عقد\s+(?:محدد|غير\s+محدد)\s+(?:المدة|الإمارات)|ما\s+الفرق\s+بين\s+عقد\s+محدد\s+وغير\s+محدد)\b",
    re.IGNORECASE,
)

# ── Multiple job offers ────────────────────────────────────────────────────────
# "I have two job offers", "how do I choose between job offers?".
_MULTIPLE_OFFERS_RE = re.compile(
    r"\b(?:I\s+(?:have|got|received)\s+(?:two|2|multiple|more\s+than\s+one|several)\s+job\s+offers?)\b"
    r"|\b(?:how\s+(?:do\s+I|to|should\s+I|can\s+I)\s+(?:choose|decide|pick|compare|evaluate|select)\s+between\s+(?:two|2|multiple|job)?\s*(?:job\s+)?offers?)\b"
    r"|\b(?:comparing\s+(?:two|2|multiple|job)\s+(?:job\s+)?offers?)\b"
    r"|\b(?:which\s+(?:job\s+)?offer\s+should\s+I\s+(?:choose|accept|take|pick|go\s+with))\b"
    r"|\b(?:I\s+(?:need|want)\s+to\s+(?:choose|decide|pick)\s+between\s+(?:two|2|multiple)\s+(?:job\s+)?offers?)\b"
    r"|\b(?:offer\s+comparison\s+(?:advice|tips?|how\s+to|UAE|Dubai))\b"
    r"|\b(?:لدي\s+(?:عرضان|عروض\s+متعددة|عرضين)\s+(?:وظيفيان?|للعمل)|كيف\s+أختار\s+بين\s+(?:عرضين|عرضان)\s+وظيفيين?)\b",
    re.IGNORECASE,
)

# ── Workplace harassment / discrimination UAE ──────────────────────────────────
# "I'm being harassed at work", "my employer is discriminating against me".
_WORKPLACE_HARASSMENT_RE = re.compile(
    r"\b(?:I(?:'m|\s+am)\s+being\s+(?:harassed|bullied|discriminated\s+against|sexually\s+harassed|victimised?|victimized?)\s+(?:at\s+work|by\s+my\s+(?:manager|boss|employer|colleague|coworker)))\b"
    r"|\b(?:(?:workplace|work|office|job|employment)\s+(?:harassment|bullying|discrimination|hostile\s+environment|sexual\s+harassment)(?:\s+(?:UAE|Dubai|complaint|how\s+to\s+report|rights?))?)\b"
    r"|\b(?:sexual\s+harassment\s+(?:at\s+work|in\s+the\s+workplace|UAE|Dubai|complaint|reporting|rights?))\b"
    r"|\b(?:how\s+(?:do\s+I|to|can\s+I|should\s+I)\s+(?:report|deal\s+with|handle|stop|file\s+a\s+complaint\s+about)\s+(?:workplace\s+)?(?:harassment|bullying|discrimination|sexual\s+harassment))\b"
    r"|\b(?:my\s+(?:manager|boss|employer|colleague)\s+is\s+(?:harassing|bullying|discriminating\s+against|sexually\s+harassing)\s+me)\b"
    r"|\b(?:what\s+(?:are\s+my\s+rights|can\s+I\s+do|should\s+I\s+do)\s+(?:if|when)\s+(?:I\s+(?:am|'m)\s+being|I\s+(?:face|experience))\s+(?:harassed|bullied|discriminated\s+against|harassment|discrimination))\b"
    r"|\b(?:تحرش\s+(?:في\s+العمل|مكان\s+العمل|جنسي)|تمييز\s+(?:في\s+العمل|ضدي)|مضايقة\s+في\s+العمل)\b",
    re.IGNORECASE,
)

# ── Redundancy / layoff UAE ────────────────────────────────────────────────────
# "I was made redundant", "my company is laying me off", "what are my rights?".
_REDUNDANCY_UAE_RE = re.compile(
    r"\b(?:(?:I\s+(?:was|got|have\s+been))\s+(?:made\s+redundant|laid\s+off|let\s+go|downsized|retrenched))\b"
    r"|\b(?:(?:my\s+)?(?:company|employer|organization)\s+is\s+(?:laying|making)\s+(?:me|people|staff|employees)\s+(?:off|redundant))\b"
    r"|\b(?:redundanc(?:y|ies)\s+(?:UAE|Dubai|rights?|compensation|payment|law|rules?|EOSB|gratuity|process))\b"
    r"|\b(?:what\s+(?:are\s+(?:my\s+)?rights?|happens?|(?:do\s+I|am\s+I)\s+(?:get|entitled\s+to))\s+(?:if\s+I\s+(?:am|get|was)\s+)?(?:laid\s+off|made\s+redundant|retrenched|downsized))\b"
    r"|\b(?:(?:layoff|lay[- ]off|retrenchment|downsizing)\s+(?:UAE|Dubai|rights?|compensation|payment|law|rules?|process|notice))\b"
    r"|\b(?:company\s+(?:is\s+)?(?:downsizing|restructuring|cutting\s+(?:jobs?|staff|roles?))(?:\s+(?:and\s+I|UAE|Dubai))?)\b"
    r"|\b(?:فصل\s+(?:جماعي|تعسفي)|تقليص\s+العمالة|ما\s+حقوقي\s+(?:عند|إذا)\s+(?:الاستغناء\s+عن\s+خدماتي|فُصِلت\s+من\s+العمل))\b",
    re.IGNORECASE,
)

def generate_error_ref() -> str:
    """Generate a unique error reference ID for tracking and support lookup."""
    return f"ERR-{uuid.uuid4().hex[:8].upper()}"

ONBOARDING_FIELD_LABELS = {
    "email": "email address",
    "phone": "phone number",
    "preferred_city": "preferred UAE city",
    "target_roles": "target role",
    "salary_expectation_aed": "salary expectation",
    "deal_breakers": "roles or companies to avoid",
}

# OpenAI context limits
MAX_CONTEXT_MESSAGES = 10
MAX_PROFILE_TOKENS = 200  # Conservative estimate for profile summary

# Phrases that identify pipeline-generated artifacts. Messages containing these
# must never be fed back to the LLM as authentic user statements.
_PIPELINE_ARTIFACT_PHRASES: tuple[str, ...] = (
    "i have uae experience in executive operations",
    "ceo support",
    "i am interested in the",  # generated_message template prefix
)

_ALLOWED_LLM_ROLES: frozenset[str] = frozenset({"user", "assistant"})


def _sanitize_history_for_llm(messages: list[dict]) -> list[dict]:
    """Return only safe, authentic conversation turns for LLM context injection.

    Drops:
    - Any message whose role is not 'user' or 'assistant'
    - Any user-role message whose content matches a known pipeline artifact phrase
      (guards against generated drafts stored with wrong role)
    """
    safe = []
    for m in messages:
        role = str(m.get("role", "")).lower()
        if role not in _ALLOWED_LLM_ROLES:
            continue
        content = str(m.get("content") or m.get("message") or "").strip().lower()
        if not content:
            continue
        if role == "user" and any(phrase in content for phrase in _PIPELINE_ARTIFACT_PHRASES):
            logger.warning("chat_sanitizer: dropped pipeline artifact stored as role=user")
            continue
        safe.append(m)
    return safe

# Acknowledgement replies — short, warm, non-restarting
_ACKNOWLEDGEMENT_REPLIES: dict[str, str] = {
    "thanks": "You're welcome!",
    "thank you": "You're welcome!",
    "thank you so much": "Happy to help anytime!",
    "thanks a lot": "Happy to help!",
    "thank you very much": "Happy to help!",
    "much appreciated": "Glad I could help.",
    "appreciate it": "Glad I could help.",
    "appreciate that": "Glad I could help.",
    "great": "Glad to help.",
    "perfect": "Happy to help.",
    "excellent": "Glad to hear that!",
    "wonderful": "Glad to hear that!",
    "awesome": "Great!",
    "cool": "Good to know.",
    "nice": "Good to know.",
    "ok": "Of course.",
    "okay": "Of course.",
    "ok thanks": "You're welcome.",
    "okay thanks": "You're welcome.",
    "ok thank you": "You're welcome.",
    "okay thank you": "You're welcome.",
    "got it": "Sounds good.",
    "understood": "Sounds good.",
    "noted": "Noted.",
    "sounds good": "Glad that works for you.",
    "looks good": "Glad that works for you.",
    "makes sense": "Great.",
    "cheers": "Cheers!",
    # Arabic
    "شكرا": "عفواً!",
    "شكراً": "عفواً!",
    "شكرا جزيلا": "على الرحب والسعة!",
    "شكراً جزيلاً": "على الرحب والسعة!",
    "ممتاز": "يسعدني ذلك.",
    "رائع": "يسعدني ذلك.",
    "فهمت": "ممتاز.",
    "تمام": "بالتوفيق.",
    "ماشي": "حسناً.",
    "حسنا": "حسناً.",
}
_DEFAULT_ACK_REPLY = "Of course! What would you like to do next?"


def _acknowledgement_reply(message: str) -> str:
    """Return a short warm reply for acknowledgement phrases."""
    key = message.strip().lower()
    return _ACKNOWLEDGEMENT_REPLIES.get(key, _DEFAULT_ACK_REPLY)


class HandlerResult(NamedTuple):
    """Result type for handler functions."""
    response: dict[str, Any]
    should_save: bool = True


def profile_to_dict(profile: Any) -> dict[str, Any]:
    """Normalize profile to dict, handling dataclass, dict, and object types."""
    if profile is None:
        return {}
    if is_dataclass(profile):
        return {k: v for k, v in asdict(profile).items() if v not in (None, "", [], {})}
    if isinstance(profile, dict):
        return {k: v for k, v in profile.items() if v not in (None, "", [], {})}
    return {
        k: getattr(profile, k)
        for k in dir(profile)
        if not k.startswith("_") and getattr(profile, k, None) not in (None, "", [], {})
    }


class RicoChatAPI:
    """Simple conversational controller for Rico AI."""

    # Deterministic follow-up phrases (must be checked before role classification)
    _FOLLOWUP_BOTH_ACTION_PHRASES = frozenset({
        "both",
        "both please",
        "do both",
        "yes both",
    })

    _FOLLOWUP_KEEP_ALL_PHRASES = frozenset({
        "keep all",
        "keep them all",
        "yes keep all",
        "keep everything",
    })

    def __init__(self, *, persist: bool = True) -> None:
        self.memory = RicoMemoryStore()
        self.agent = RicoAgent(profile_store=self.memory)
        self.system = RicoSystem()
        self.openai_agent = RicoOpenAIAgent()
        self._persist = persist
        self._current_operation_id: str | None = None

    @staticmethod
    def _is_broad_manager_role(role_text: str) -> bool:
        text = re.sub(r"\s+", " ", (role_text or "").strip().lower())
        text = re.sub(r"^(?:a|an|the)\s+", "", text)
        return text in {"manager", "managers"}

    def _broad_manager_clarification(self, user_id: str) -> dict[str, Any]:
        suggestions = [
            "HSE Manager",
            "Operations Manager",
            "HR Manager",
            "Environmental Manager",
            "General Manager",
        ]
        response = {
            "type": "clarification",
            "intent": "search_jobs",
            "message": (
                "Manager is too broad for a live job search. Which manager role should I search?"
            ),
            "options": [
                {
                    "action": "search_role",
                    "label": role,
                    "message": f"find live jobs for {role}",
                    "role": role,
                }
                for role in suggestions
            ],
            "next_action": "narrow_job_search",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _begin_job_search_operation(self, user_id: str, role_or_query: str) -> dict[str, Any]:
        operation = start_job_search_operation(
            user_id=user_id,
            role_or_query=role_or_query,
            operation_id=self._current_operation_id,
        )
        self._current_operation_id = str(operation["operation_id"])
        return operation

    _ALLOWED_CHAT_ROLES: frozenset[str] = frozenset({"user", "assistant", "system"})

    def _append_chat(self, user_id: str, role: str, message: str | dict[str, Any]) -> None:
        """Append chat message to memory (sync) and DB (async fire-and-forget).

        Memory write is synchronous so subsequent reads see the message immediately.
        DB write is dispatched to a background thread to avoid blocking the request
        path on remote PostgreSQL latency (~1s round-trip on Neon).
        """
        if role not in self._ALLOWED_CHAT_ROLES:
            logger.warning("rico_chat_api: _append_chat rejected unknown role=%r user=%s", role, user_id)
            return
        payload = json.dumps(message) if isinstance(message, dict) else message
        try:
            self.memory.append_chat_message(user_id, role, payload)
        except Exception:
            logger.error("rico_chat_api: memory append_chat_message failed user=%s role=%s", user_id, role, exc_info=True)
        if not getattr(self, "_persist", True):
            return
        # Async DB persistence — non-blocking, daemon so worker shutdown is
        # not stalled by a slow or unreachable Postgres during deploys.
        import threading
        from src.services.chat_service import db_append_chat

        def _safe_db_append(uid: str, r: str, p: str) -> None:
            try:
                db_append_chat(uid, r, p)
            except Exception:
                logger.error("rico_chat_api: db_append_chat failed user=%s", uid, exc_info=True)

        threading.Thread(
            target=_safe_db_append,
            args=(user_id, role, payload),
            daemon=True,
        ).start()

    # ── Uploaded documents (My Files) ──────────────────────────────────────────

    # Deterministic file-list intent: these questions must be answered from the
    # database, never left to the AI model's discretion over context JSON.
    _FILE_LIST_EN_RE = re.compile(
        r"\b(?:check|show|list|view|see|display)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?"
        r"(?:uploaded\s+)?(?:files?|documents?|docs)\b"
        r"|\b(?:my|uploaded)\s+(?:files?|documents?|docs|uploads)\b"
        r"|\b(?:what|which)\s+(?:files?|documents?)\b"
        r"|\bwhich\s+(?:cv|resume)\s+is\s+(?:the\s+)?(?:active|primary|current|main)\b"
        r"|\b(?:active|primary)\s+(?:cv|resume)\b",
        re.IGNORECASE,
    )
    _FILE_LIST_AR_RE = re.compile(
        r"ملفاتي|مستنداتي|وثائقي"
        r"|(?:اعرض|أعرض|اعرضي|شوف|شوفي|وريني|ورني|اظهر|أظهر)\s+(?:لي\s+)?(?:كل\s+)?(?:الملفات|المستندات)"
        r"|(?:الملفات|المستندات)\s+(?:اللي|التي)\s+(?:رافعه?ا|رفعته?ا|رفعها)"
        r"|(?:الملفات|المستندات)\s+المرفوعة"
        r"|(?:أي|اي)\s+سيرة\s+.{0,16}(?:نشطة|فعالة|أساسية|الأساسية|الاساسية)",
        re.UNICODE,
    )

    _DOC_TYPE_LABELS = {
        "en": {
            "cv": "CV",
            "cover_letter": "Cover letter",
            "other": "Other document",
            "identity_document": "Identity document",
        },
        "ar": {
            "cv": "سيرة ذاتية",
            "cover_letter": "رسالة تقديم",
            "other": "مستند آخر",
            "identity_document": "مستند هوية",
        },
    }

    def _collect_uploaded_documents(self, user_id: str, profile: Any) -> list[dict[str, Any]]:
        """Merge real user_documents with the legacy profile-CV fallback.

        Mirrors GET /api/v1/user/files: when no real document has
        doc_type == "cv" AND is_primary == true, the parsed profile CV is
        prepended as a synthetic active entry so other uploads never hide it.
        """
        from src.rico_db import RicoDB as _RicoDB

        _docs_db = _RicoDB()
        _docs = _docs_db.list_user_documents(user_id) if _docs_db.available else []
        entries = [
            {
                "filename": d.get("filename", ""),
                "doc_type": d.get("doc_type", ""),
                "label": d.get("label") or d.get("filename", ""),
                "is_primary": bool(d.get("is_primary")),
                "skills_count": d.get("skills_count"),
                "years_experience": int(float(d["years_experience"])) if d.get("years_experience") is not None else None,
            }
            for d in _docs
        ]
        has_active_cv = any(
            d.get("doc_type") == "cv" and d.get("is_primary") for d in _docs
        )
        if not has_active_cv and profile is not None:
            cv_filename = self._profile_value(profile, "cv_filename")
            if cv_filename:
                entries.insert(
                    0,
                    {
                        "filename": cv_filename,
                        "doc_type": "cv",
                        "label": cv_filename,
                        "is_primary": True,
                        "is_legacy": True,
                    },
                )
        return entries

    def _is_file_list_query(self, message: str) -> bool:
        text = (message or "").strip()
        if not text:
            return False
        return bool(
            self._FILE_LIST_EN_RE.search(text) or self._FILE_LIST_AR_RE.search(text)
        )

    def _handle_file_list_query(self, user_id: str, message: str) -> Optional[dict[str, Any]]:
        """Deterministic My Files answer — same data as /upload, no AI involved.

        Returns None when the message is not a file-list question so normal
        routing continues.
        """
        if not self._is_file_list_query(message):
            return None
        try:
            profile = get_profile(user_id)
        except Exception:
            profile = None
        try:
            docs = self._collect_uploaded_documents(user_id, profile)
        except Exception:
            logger.warning("file_list_query_db_failed user=%s", user_id)
            docs = []

        arabic = self._is_arabic_text(message)
        lang = "ar" if arabic else "en"
        type_labels = self._DOC_TYPE_LABELS[lang]

        if not docs:
            msg = (
                "لا توجد ملفات مرفوعة في حسابك حتى الآن. استخدم زر **رفع السيرة الذاتية** "
                "لرفع سيرتك — بعد الرفع سأقرأها تلقائياً وأملأ ملفك المهني."
                if arabic else
                "You have no uploaded files on record yet. Use the **Upload CV** button to "
                "upload your CV — once uploaded, I will read it automatically and pre-fill "
                "your career profile."
            )
        else:
            lines = []
            has_cv_doc = False
            has_identity_doc = False
            for d in docs:
                dt = d.get("doc_type", "")
                if dt == "cv":
                    has_cv_doc = True
                if dt == "identity_document":
                    has_identity_doc = True
                type_label = type_labels.get(dt, type_labels["other"])
                badges = []
                if d.get("is_primary") and dt == "cv":
                    badges.append("⭐ " + ("السيرة الذاتية النشطة" if arabic else "active CV"))
                if d.get("is_legacy"):
                    badges.append("من الملف الشخصي" if arabic else "from your profile")
                badge_str = f" ({'، '.join(badges) if arabic else ', '.join(badges)})" if badges else ""
                lines.append(f"📄 {d.get('filename')} — {type_label}{badge_str}")
            note = (
                "أستطيع قراءة محتوى السيرة الذاتية المحلّلة فقط؛ بقية المستندات لديّ بياناتها "
                "الوصفية فقط (الاسم والنوع) ولا يمكنني فتح محتوى PDF الخام. يمكنك إدارة الملفات من صفحة My Files."
                if arabic else
                "I can read the parsed CV's content only; for other documents I have file "
                "details (name and type) and cannot open raw PDF contents. You can manage "
                "files from the My Files page."
            )
            header = "ملفاتك المرفوعة:" if arabic else "Your uploaded files:"
            msg = header + "\n" + "\n".join(lines) + "\n\n" + note
            # If user has identity documents but no CV, add an explicit notice.
            if has_identity_doc and not has_cv_doc:
                no_cv_note = (
                    "\n⚠️ لديك مستندات هوية مرفوعة ولكن لم يُعثر على سيرة ذاتية أو ملف مهني. "
                    "استخدم زر **رفع السيرة الذاتية** لرفع سيرتك."
                    if arabic else
                    "\n⚠️ You have identity documents on file but no CV or resume was found. "
                    "Use the **Upload CV** button to upload your professional CV."
                )
                msg = msg + no_cv_note

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "file_list",
            "message": msg,
            "files": docs,
            "next_action": "manage_files",
        }

    def _cv_upload_guidance_with_db_check(
        self,
        user_id: str,
        message: str,
        profile: Any = None,
    ) -> Optional[dict[str, Any]]:
        """Check user_documents before offering CV upload guidance.

        Returns a finalized response when the user already has a CV on file
        or has only identity documents. Returns None to let normal upload
        guidance proceed when no documents are found.
        """
        try:
            from src.services.document_resolver import (
                has_only_identity_documents,
                resolve_user_cv,
            )
            arabic = self._is_arabic_text(message)

            existing_cv = resolve_user_cv(user_id, profile)
            if existing_cv:
                filename = existing_cv.get("filename") or ""
                is_primary = bool(existing_cv.get("is_primary"))
                if arabic:
                    label = f"**{filename}**" + (" (النشطة)" if is_primary else "")
                    msg = (
                        f"لديك سيرة ذاتية محفوظة بالفعل: {label}. "
                        "يمكنني استخدامها للبحث عن وظائف مناسبة الآن. "
                        "لاستبدالها، استخدم زر **رفع السيرة الذاتية**."
                    )
                else:
                    label = f"**{filename}**" + (" (active CV)" if is_primary else "")
                    msg = (
                        f"You already have {label} on file. "
                        "I can use it to match jobs right now. "
                        "To replace it, use the **Upload CV** button."
                    )
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(
                    {
                        "type": "cv_already_exists",
                        "message": msg,
                        "cv_filename": filename,
                        "next_action": "job_search",
                    },
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

            if has_only_identity_documents(user_id):
                if arabic:
                    msg = (
                        "لديك مستندات مرفوعة (مستندات هوية) ولكن لم يُعثر على سيرة ذاتية. "
                        "استخدم زر **رفع السيرة الذاتية** لرفع سيرتك المهنية."
                    )
                else:
                    msg = (
                        "You have uploaded documents, but no CV or resume was found. "
                        "Use the **Upload CV** button to upload your professional CV."
                    )
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(
                    {
                        "type": "cv_upload_guidance",
                        "message": msg,
                        "next_action": "upload_cv",
                        "options": [
                            {
                                "action": "upload_cv",
                                "label": "رفع السيرة الذاتية" if arabic else "Upload CV",
                                "message": "upload cv",
                            }
                        ],
                    },
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
        except Exception:
            logger.warning("_cv_upload_guidance_with_db_check failed user=%s", user_id)

        return None

    def _build_openai_context(self, profile: Any, user_id: str | None = None) -> dict[str, Any]:
        """Build context for OpenAI agent from profile and recent conversation history."""
        if profile is None:
            ctx: dict[str, Any] = {"profile_exists": False}
        else:
            if is_dataclass(profile):
                raw = asdict(profile)
            elif isinstance(profile, dict):
                raw = dict(profile)
            else:
                raw = {k: getattr(profile, k) for k in dir(profile) if not k.startswith("_")}

            essential_fields = {
                # Deliberately excludes "email": the user's identity is established
                # by the JWT, not the profile record. Including email in the AI
                # context risks leaking a stale or cross-user email into the
                # model's reply (e.g. "you have a profile on record as X@Y.com").
                "phone", "skills", "years_experience",
                "preferred_cities", "target_roles", "industries",
                "salary_expectation_aed", "deal_breakers",
                "telegram_username", "telegram_chat_id",
                "name", "visa_status", "notice_period",
                "current_company", "current_role", "linkedin_url",
            }
            ctx = {
                "profile_exists": True,
                **{k: v for k, v in raw.items() if k in essential_fields and v not in (None, "", [], {})},
            }
            # Never surface a corrupted preferred_cities value (a misfiled chat
            # message) to the model — it confuses location reasoning.
            if ctx.get("preferred_cities"):
                from src.services.city_validation import sanitize_cities
                _clean_cities = sanitize_cities(self._as_list(ctx["preferred_cities"]))
                if _clean_cities:
                    ctx["preferred_cities"] = _clean_cities
                else:
                    ctx.pop("preferred_cities", None)

            # #732 — flag stale/unevidenced coding target_roles so the AI never
            # asserts "Developer" when the CV evidence points elsewhere.
            _ctx_roles = self._as_list(ctx.get("target_roles", []))
            if _ctx_roles and self._has_cv_profile(profile):
                try:
                    if not self._role_is_cv_aligned(profile, str(_ctx_roles[0])):
                        ctx["target_roles_note"] = (
                            "STALE — these saved target roles may not reflect the current CV. "
                            "Do not assert or search these roles without first confirming with the user."
                        )
                except Exception:
                    pass

        # Embed last 8 turns so the AI has conversation context for yes/no and follow-ups
        if user_id:
            # Inject uploaded documents FIRST: the serialized context is truncated
            # to _PROFILE_CONTEXT_MAX_CHARS in rico_openai_runtime and dict insertion
            # order is preserved, so file metadata must precede the long conversation
            # history or the model never sees it. Lets Rico answer "which CVs do I
            # have?" and route requests like "use my finance CV" to the right
            # document. Active (is_primary=True) CV remains the default for matching.
            try:
                _entries = self._collect_uploaded_documents(user_id, profile)
                if _entries:
                    ctx["uploaded_documents"] = _entries
            except Exception:
                pass

            # Inject the transcript of the most recently uploaded image/document
            # (set by the upload route after vision/OCR extraction) — read from the
            # durable store so it survives RICO_MEMORY_BACKEND=postgres / restarts /
            # multiple instances. Without this, typed follow-ups like "what do you
            # think of this job?" reach the AI with no document text. Injected early
            # (before the long conversation history) so it survives truncation.
            try:
                _last_doc = self._get_last_uploaded_document(user_id)
                _doc_text = (_last_doc or {}).get("extracted_text")
                if _doc_text:
                    ctx["last_uploaded_document"] = {
                        "filename": _last_doc.get("filename"),
                        "type": _last_doc.get("display_label") or _last_doc.get("document_type"),
                        "transcribed_text": str(_doc_text)[:4000],
                    }
            except Exception:
                pass

            try:
                recent = self._get_recent_messages(user_id, limit=8)
                if recent:
                    ctx["conversation_history"] = [
                        {"role": m.get("role", "user"), "content": str(m.get("content") or m.get("message") or "")}
                        for m in recent
                        if m.get("content") or m.get("message")
                    ]
            except Exception:
                pass

            # Cross-session recall: surface jobs the user recently discussed so
            # Rico can say "you looked at the AESG role last Tuesday — want an update?"
            summary = self._recent_jobs_summary(user_id)
            if summary:
                ctx["recently_discussed_jobs"] = summary

            # Inject verification status for recent search matches to prevent hallucination
            try:
                recent_ctx = self._get_recent_context(user_id)
                recent_matches = recent_ctx.get("recent_search_matches", [])
                if recent_matches:
                    ctx["recent_job_verification_status"] = [
                        {
                            "title": m.get("title", ""),
                            "company": m.get("company", ""),
                            "verification_status": m.get("verification_status", "unknown"),
                        }
                        for m in recent_matches
                        if m.get("title")
                    ]
            except Exception:
                pass

            # Inject learned behavioral preferences from rico_learning_signals so the
            # AI knows which roles/locations the user gravitates toward and which
            # companies to avoid — derived from apply/save/skip/block actions.
            try:
                from src.repositories.learning_repo import get_learning_repository
                _lr = get_learning_repository()
                _learned: dict[str, Any] = {}
                _roles = [r for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
                if _roles:
                    _learned["preferred_roles"] = _roles
                _locs = [loc for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
                if _locs:
                    _learned["preferred_locations"] = _locs
                _skills = [s for s, _ in _lr.get_top_preferences(user_id, "skill", limit=8)]
                if _skills:
                    _learned["preferred_skills"] = _skills
                _cos = [(c, w) for c, w in _lr.get_top_preferences(user_id, "company", limit=10) if w < 0]
                if _cos:
                    _learned["avoided_companies"] = [c for c, _ in _cos]
                if _learned:
                    ctx["learned_preferences"] = _learned
            except Exception:
                pass

            # Inject career memory (CAREER-OS-09): blocked companies, recent applies, etc.
            try:
                from src.services.career_memory import build_memory_context
                _mem = build_memory_context(user_id)
                if _mem:
                    ctx["career_memory"] = _mem
            except Exception:
                pass

        return ctx

    def _recent_jobs_summary(self, user_id: str, limit: int = 3) -> str:
        """Compact one-line summary of recently discussed jobs for the system prompt.

        Returns '' when nothing is available or the lookup fails. Never raises.
        """
        try:
            from src.repositories.user_job_context_repo import get_recently_discussed
            rows = get_recently_discussed(user_id, limit=limit)
        except Exception:
            return ""
        if not rows:
            return ""
        now = datetime.now(timezone.utc)
        parts: list[str] = []
        for r in rows:
            title = (r.get("title") or "").strip()
            company = (r.get("company") or "").strip()
            if not title:
                continue
            status = (r.get("status") or "discussed").strip()
            when = r.get("last_discussed_at")
            ago = self._humanize_ago(when, now)
            label = f"{title}" + (f" at {company}" if company else "")
            parts.append(f"{label} ({status}{', ' + ago if ago else ''})")
        return "; ".join(parts)

    @staticmethod
    def _humanize_ago(when: Any, now: Any) -> str:
        """Render a timestamp as 'today' / 'yesterday' / 'N days ago'. '' on failure."""
        if when is None:
            return ""
        try:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            days = (now - when).days
        except Exception:
            return ""
        if days <= 0:
            return "today"
        if days == 1:
            return "yesterday"
        if days < 7:
            return f"{days} days ago"
        weeks = days // 7
        return "last week" if weeks == 1 else f"{weeks} weeks ago"

    @staticmethod
    def _profile_value(profile: Any, key: str, default: Any = None) -> Any:
        """Get value from profile, handling dict and object types."""
        if profile is None:
            return default
        if isinstance(profile, dict):
            return profile.get(key, default)
        return getattr(profile, key, default)

    @staticmethod
    def _has_cv_profile(profile: Any) -> bool:
        """Check if profile has CV data."""
        if profile is None:
            return False
        return bool(
            RicoChatAPI._profile_value(profile, "cv_filename")
            or RicoChatAPI._profile_value(profile, "cv_status")
            or RicoChatAPI._profile_value(profile, "skills")
            or RicoChatAPI._profile_value(profile, "years_experience")
        )

    @staticmethod
    def _effective_target_roles(roles: list[Any]) -> list[Any]:
        """Return roles with generic placeholders ('Any', 'All', etc.) stripped out."""
        return [
            r for r in roles
            if isinstance(r, str) and r.strip().lower() not in _PLACEHOLDER_ROLE_VALUES
        ]

    @staticmethod
    def _filter_excluded_roles(roles: list[Any], excluded: list[str]) -> list[Any]:
        """Drop any role that matches an excluded term (case-insensitive, whole-word
        or substring), so a "do not search …" guard is never violated.

        e.g. excluded "Backend" removes "Backend Developer"; "Software Engineer"
        removes "Senior Software Engineer".
        """
        _excl = [e.strip().lower() for e in excluded if e and e.strip()]
        if not _excl:
            return list(roles)
        kept: list[Any] = []
        for r in roles:
            rl = str(r).strip().lower()
            if any(e in rl or rl in e for e in _excl):
                continue
            kept.append(r)
        return kept

    def _role_is_cv_aligned(self, profile: Any, role: str) -> bool:
        """True when *role* matches the user's CV-derived role suggestions.

        Used to spot a stale saved target_role (e.g. a leftover "Software Engineer"
        from an old onboarding) that no longer reflects the uploaded CV. Falls back
        to True (treat as valid) whenever alignment cannot be determined, so a data
        gap never blocks a legitimate search.

        Exception (#732): a coding/software target ("Developer", "Software
        Engineer") is a strong, specific claim. When the CV yields NO role
        evidence at all, we must not silently assert it — return False so the
        caller routes to CV-aligned suggestions/clarification instead of pushing
        an unevidenced "Developer". Non-coding tracks keep the lenient fallback
        so an ordinary data gap never blocks a legitimate search.
        """
        rl = (role or "").strip().lower()
        if not rl:
            return False
        try:
            suggestions = self._generate_role_suggestions(
                self._as_list(self._profile_value(profile, "skills")),
                self._as_list(self._profile_value(profile, "certifications")),
                self._profile_value(profile, "years_experience"),
                self._as_list(self._profile_value(profile, "industries")),
                self._profile_value(profile, "current_role"),
            )
        except Exception:
            return True
        if not suggestions:
            # No CV-derived evidence. Stay lenient for most tracks, but treat an
            # unevidenced software/coding target as NOT aligned (→ "stale") so
            # Rico never over-commits to "Developer" without coding evidence.
            return self._role_family(role) != "software"
        for s in suggestions:
            sl = str((s or {}).get("label") or "").strip().lower()
            if sl and (rl == sl or rl in sl or sl in rl):
                return True
        return False

    # Coarse career-family buckets, used ONLY to tell genuinely different tracks
    # apart (software vs environmental/HSE) — not to finely classify roles. Roles
    # in one bucket are treated as a single track; 2+ buckets = real ambiguity.
    _FAMILY_TERMS: "tuple[tuple[str, tuple[str, ...]], ...]" = (
        ("env_hse", ("environment", "sustainability", "esg", "hse", "qhse", "ehs",
                     "hsse", "safety", "nebosh", "iso 14001", "iso14001",
                     "occupational health")),
        ("software", ("software", "developer", "back end", "backend", "front end",
                      "frontend", "full stack", "full-stack", "fullstack",
                      "web develop", "mobile develop", "devops", "sre",
                      "data scien", "data engineer", "machine learning",
                      "ml engineer", "ai engineer", "golang", "programmer",
                      "android", "ios ", "qa engineer", "sdet")),
    )
    _FAMILY_GENERIC_WORDS = frozenset({
        "manager", "officer", "engineer", "specialist", "lead", "coordinator",
        "director", "analyst", "consultant", "advisor", "executive", "head",
        "associate", "vp", "president", "senior", "junior", "assistant",
        "supervisor", "of", "and", "the", "for",
    })

    def _role_family(self, role: str) -> str:
        """Coarse career-family bucket for *role* (env_hse / software / subject word)."""
        rl = " " + (role or "").strip().lower() + " "
        for fam, terms in self._FAMILY_TERMS:
            if any(t in rl for t in terms):
                return fam
        # Otherwise bucket by the first meaningful (non-generic) subject word so
        # "Marketing Manager"/"Marketing Lead" group together but differ from "Sales".
        for w in re.findall(r"[a-z][a-z+&]+", rl):
            if w not in self._FAMILY_GENERIC_WORDS and len(w) > 2:
                return w
        return "general"

    def _resolve_profile_search_role(
        self, profile: Any, excluded_roles: Optional[list[str]] = None
    ) -> "tuple[Optional[str], list[str], str]":
        """Pick which role a 'match my profile' search should target.

        Returns (role, candidates, status):
          - "single"    → one career track; search candidates[0].
          - "ambiguous" → candidates span 2+ distinct families (e.g. software AND
                          environmental); ask the user to choose from *candidates*.
          - "stale"     → single-track but candidates[0] no longer matches the CV
                          (a leftover role such as "Software Engineer" on an
                          environmental CV); confirm with CV-derived suggestions.
          - "none"      → no usable saved role left.

        Ambiguity is judged by role FAMILY, never raw count: a coherent multi-role
        profile (Environmental / Sustainability / ESG …) is one track and searches
        its primary role; only genuinely different tracks force a choice.
        """
        roles = self._effective_target_roles(
            self._as_list(self._profile_value(profile, "target_roles"))
        )
        if excluded_roles:
            roles = self._filter_excluded_roles(roles, excluded_roles)
        candidates: list[str] = []
        seen: set[str] = set()
        for r in roles:
            raw = str(r).strip()
            if not raw:
                continue
            # De-duplicate by canonical form (so "PM" and "Product Manager" collapse
            # to one track) but keep the user's ORIGINAL text — the search layer
            # normalizes downstream, and tests/UX expect the saved wording preserved.
            try:
                key = (normalize_role(raw) or raw).lower()
            except Exception:
                key = raw.lower()
            if key not in seen:
                seen.add(key)
                candidates.append(raw)
        if not candidates:
            return (None, [], "none")
        if len({self._role_family(c) for c in candidates}) >= 2:
            return (None, candidates, "ambiguous")
        role = candidates[0]
        if self._has_cv_profile(profile) and not self._role_is_cv_aligned(profile, role):
            return (role, candidates, "stale")
        return (role, candidates, "single")

    def _profile_role_choice_response(
        self, candidates: list[str], message: str = ""
    ) -> dict[str, Any]:
        """Clarification asking which career track to match (2+ distinct families)."""
        arabic = self._is_arabic_text(message)
        shortlist = candidates[:6]
        options = [
            {"action": "search_role", "label": r, "message": f"search {r} jobs in UAE"}
            for r in shortlist
        ]
        if arabic:
            msg = (
                "ملفك يشمل أكثر من مسار وظيفي. أي مسار تريد أن أطابقه مع وظائف الإمارات؟\n"
                + "\n".join(f"• {r}" for r in shortlist)
            )
        else:
            msg = (
                "Your profile spans more than one career track. Which one should I "
                "match against UAE jobs?\n"
                + "\n".join(f"• {r}" for r in shortlist)
            )
        return {
            "type": "clarification",
            "message": msg,
            "options": options,
            "next_action": "select_role_to_search",
        }

    @staticmethod
    def _looks_like_bare_target_role(message: str) -> bool:
        """Accept only short noun-phrase job titles, not questions or commands."""
        text = (message or "").strip()
        if not text:
            return False
        # An email address is never a job role — it's typically an answer to a
        # prompt (e.g. "what's the company email?"). Don't misread it as a role
        # and emit "I do not recognize '...' as a job role."
        if EMAIL_RE.search(text):
            return False
        # Pure Arabic / non-ASCII input can't match the English role taxonomy
        if not any(ch.isascii() and ch.isalpha() for ch in text):
            return False
        if any(ch in _QUESTION_CHARS for ch in text):
            return False
        if ". " in text or text.endswith("..."):
            return False
        if any(ch.isdigit() for ch in text):
            return False

        tokens = text.split()
        if not tokens or len(tokens) > _MAX_ROLE_WORDS:
            return False

        # A message made up entirely of location terms is a location-qualified
        # job search, not a bare job role title. Check the full phrase first
        # (handles multi-word cities like "Abu Dhabi"), then per-token.
        if text.lower() in _LOCATION_TERMS:
            return False
        _loc_fillers = {"jobs", "job", "roles", "role", "in", "the", "a", "an"}
        non_location_tokens = [
            t for t in tokens
            if t.lower() not in _LOCATION_TERMS and t.lower() not in _loc_fillers
        ]
        if not non_location_tokens:
            return False

        # Contractions (e.g. "can't", "don't") start with a verb, not a job title.
        # They never appear in English role names, so reject on apostrophe in first token.
        first_raw = tokens[0].lower()
        if "'" in first_raw or "’" in first_raw:
            return False
        first = first_raw.strip(".,/&+-()")
        if first in _NON_ROLE_STARTERS:
            return False
        if not any(
            sum(1 for ch in tok if ch.isalpha()) >= _MIN_TOKEN_ALPHA
            for tok in tokens
        ):
            return False

        if text.lower() in RicoChatAPI._WHATS_NEXT_PHRASES:
            return False
        return True

    # Role suffix words used to detect space-concatenated Title Case role blobs.
    _ROLE_SUFFIX_RE = re.compile(
        r"\b(?:Manager|Director|Officer|Lead|Specialist|Consultant|Advisor|"
        r"Coordinator|Executive|Head|Analyst|Engineer|Associate|President|VP)\b"
    )
    # Captures a role-suffix word + the space before the next capitalised word.
    # Used to insert a split sentinel (\x00) without variable-width lookbehind.
    _ROLE_SUFFIX_BOUNDARY_RE = re.compile(
        r"(Manager|Director|Officer|Lead|Specialist|Consultant|Advisor|"
        r"Coordinator|Executive|Head|Analyst|Engineer|Associate|President|VP) "
        r"(?=[A-Z])"
    )

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        """Convert profile values to a flat list.

        Profile data can arrive from older forms as comma/newline-separated
        strings. Flatten those before role search so one stored text blob never
        becomes one giant job title.

        Also handles space-concatenated Title Case role blobs produced by older
        Jotform/onboarding paths (e.g. "Environmental Manager HSE Manager"):
        these are split at Title Case word boundaries when the string is long
        and contains multiple known role-suffix words.
        """
        if value is None:
            return []
        items = value if isinstance(value, (list, tuple)) else [value]
        result: list[Any] = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, str):
                for part in PROFILE_LIST_SPLIT_RE.split(item):
                    cleaned = part.strip().strip("-*\u2022").strip()
                    if not cleaned:
                        continue
                    # Secondary split: detect space-joined Title Case role blobs.
                    # Apply only when string is suspiciously long and contains
                    # at least two known role-suffix words \u2014 avoids false splits
                    # on legitimate multi-word titles like "General Manager Retail".
                    if (
                        len(cleaned) > 50
                        and len(RicoChatAPI._ROLE_SUFFIX_RE.findall(cleaned)) >= 2
                    ):
                        sentinel = RicoChatAPI._ROLE_SUFFIX_BOUNDARY_RE.sub(
                            lambda m: m.group(1) + "\x00", cleaned
                        )
                        sub_parts = sentinel.split("\x00")
                        for sp in sub_parts:
                            sp = sp.strip()
                            if sp:
                                result.append(sp)
                    else:
                        result.append(cleaned)
                continue
            result.append(item)
        return result

    @staticmethod
    def normalize_role_label(text: str) -> str:
        """Title-case role text while preserving known acronyms."""
        if not text:
            return text
        acronyms = {"HSE", "QHSE", "EHS", "ESG", "UAE", "ISO", "CV", "NEBOSH"}
        words = text.split()
        result = []
        for w in words:
            upper = w.upper()
            if upper in acronyms:
                result.append(upper)
            else:
                result.append(w.capitalize())
        return " ".join(result)

    # ── Live / generic job search detection ────────────────────────────────

    _LIVE_SEARCH_RE = re.compile(
        # live/current near jobs/roles/openings (both word orders)
        r"\b(live|current)\b.{0,40}\b(jobs?|roles?|openings?)\b"
        r"|\b(jobs?|roles?|openings?)\b.{0,40}\b(live|current)\b"
        # "uae jobs/roles" only when a role word follows (>=3 chars after whitespace)
        r"|\buae\s+(?:jobs?|roles?|openings?)\s+(?:for\s+)?\w{3}"
        r"|\b(?:jobs?|roles?|openings?)\s+(?:for\s+)?\w{3}.{0,40}\buae\b"
        # find openings (bare -- strong enough signal on its own)
        r"|\bfind\b.{0,20}\bopenings?\b"
        # show current openings (explicit)
        r"|\bshow\b.{0,20}\bcurrent\b.{0,20}\bopenings?\b",
        re.IGNORECASE,
    )

    _GENERIC_JOB_REQUEST_RE = re.compile(
        r"^\s*(?:i\s+(?:am|m)\s+|am\s+)?(?:looking\s+for|find|show|get|need|want)\s+(?:a\s+)?(?:job|jobs|work|role|roles)\s*$"
        r"|^\s*(?:i\s+)?(?:need|want)\s+(?:a\s+)?(?:job|jobs|work|role|roles)\s*$"
        r"|^\s*(?:find|show|get)\s+(?:me\s+)?(?:a\s+)?(?:job|jobs|role|roles)\s*$"
        r"|^\s*(?:show|find|get)\s+me\s+jobs?\s*$"
        r"|^\s*jobs?\s+(?:for\s+me|please)\s*$",
        re.IGNORECASE,
    )

    # Matches self-referential role phrases that should resolve to saved profile roles.
    # English: "my target role/roles", "my saved role/roles", "my saved target role/roles"
    # Arabic:  "دوري المستهدف", "أدواري المستهدفة", "وظيفتي المستهدفة", "وظيفتي المحفوظة"
    _SELF_REF_ROLE_RE = re.compile(
        r"^my(?:\s+saved)?\s+(?:target\s+)?roles?$"
        r"|^(?:دوري|أدواري|وظيفتي)\s+(?:المستهدف(?:ة)?|المحفوظ(?:ة)?)$",
        re.IGNORECASE,
    )

    # Matches explicit user-ownership requests — must route to application_tracking
    # regardless of prior turn context.
    # "show applications" / "list applications" (no "my") are intentionally excluded:
    # those bare forms stay in _LIST_FOLLOWUP_PHRASES so they replay lifecycle context
    # when a prior application turn exists, which is the correct contextual behavior.
    # Conversational question forms ("what are my applications?", "where are my
    # applications?") are intentionally excluded here — they route via
    # _APPLICATIONS_LIST_RE to _handle_applications_list instead.
    # English: "show my applications", "my applications", "show my job applications",
    #          "show my job applications and their status", "my jobs", "show my pipeline".
    # Arabic:  "طلباتي", "اعرض طلباتي", etc.
    _SHOW_MY_APPLICATIONS_RE = re.compile(
        r"^(?:"
        # "show/list/... my [job] applications [and their status / status]"
        r"(?:show|list|view|see|display|check|track)\s+my\s+(?:job\s+)?applications?\s*(?:(?:and\s+their\s+)?status)?"
        r"|my\s+(?:job\s+)?applications?"
        # "show my jobs" / "list my jobs" / "my jobs"
        r"|(?:show|list|view|see|display|check|track)\s+my\s+jobs?"
        r"|my\s+jobs?"
        # "show my pipeline" / "my pipeline" / "show my application pipeline"
        r"|(?:show|display|view|open)\s+my\s+(?:application\s+)?pipeline"
        r"|my\s+(?:application\s+)?pipeline"
        # Arabic
        r"|(?:اعرض|أعرض|عرض|اظهر|أظهر|ارني|أريني)\s+طلباتي"
        r"|طلباتي"
        r")$",
        re.IGNORECASE,
    )

    # Matches direct reminder commands like "Set a follow-up reminder for Penspen"
    # or "Remind me to follow up" — these are button-click phrases from the UI
    # that must be caught before role classification interprets them as job titles.
    _SET_REMINDER_RE = re.compile(
        r"(?:"
        r"set\s+(?:a\s+)?(?:follow[- ]up\s+)?reminder"
        r"|remind\s+me\s+(?:to\s+follow\s+up|about)"
        r"|follow[- ]up\s+reminder"
        r"|اضبط\s+تذكير|ضع\s+تذكير|تذكيرني"
        r")",
        re.IGNORECASE,
    )

    _MANUAL_APPLICATION_LOG_QUESTION_RE = re.compile(
        r"\bhow\s+can\s+(?:you|u|rico)\s+(?:log|record|add|track)\s+"
        r"(?:it|this|this\s+job|the\s+job|that\s+job)\b"
        r"|\b(?:can|could|will|would)\s+(?:you|u|rico)\s+(?:log|record|add|track)\s+"
        r"(?:it|this|this\s+job|the\s+job|that\s+job)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _is_live_job_search_request(message: str) -> bool:
        """True when user explicitly asks for live/current/UAE/openings jobs."""
        return bool(RicoChatAPI._LIVE_SEARCH_RE.search(message))

    @staticmethod
    def _looks_like_generic_job_request(message: str) -> bool:
        """True for generic job-search phrases without a specific role."""
        return bool(RicoChatAPI._GENERIC_JOB_REQUEST_RE.search(message))

    @staticmethod
    def _message_requires_job_profile(message: str) -> bool:
        """True when the message is a job-search or role-search request.

        The minimum-profile gate must only fire when the user is actively
        requesting job matching — not on greetings, profile queries, or any
        other general-purpose message.  This keeps Rico conversational and
        avoids turning it into a rigid form-bot for users who completed
        onboarding but are missing one optional field.
        """
        msg = (message or "").strip()
        if not msg:
            return False
        msg_lower = msg.lower()

        # Known job-search help-option phrases
        if msg_lower in RicoChatAPI._JOB_SEARCH_HELP_PHRASES:
            return True

        # Generic job-request pattern (covers Arabic "دورلي على وظائف" etc.)
        if RicoChatAPI._looks_like_generic_job_request(msg):
            return True

        # Bare role name → the user typed a role title expecting a role search
        if RicoChatAPI._looks_like_bare_target_role(msg):
            return True

        # Intent classifier: catch explicit phrasing not covered above
        try:
            from src.agent.intelligence.intent_classifier import classify_intent
            result = classify_intent(msg, has_cv_profile=True)
            return result.intent in ("job_search_explicit", "job_search_profile_match")
        except Exception:
            return False

    @staticmethod
    def _looks_like_career_execution_request(message: str) -> bool:
        """True when the user expects Rico to execute career discovery/search."""
        text = (message or "").strip().lower()
        if not text:
            return False
        return (
            "find me a career" in text
            or "find a career" in text
            or "career in " in text
            or "cannot find me a career" in text
            or ("why should i search" in text and "career" in text)
        )

    @staticmethod
    def _extract_career_industry_targets(message: str, profile: Any) -> list[str]:
        """Extract the user's requested industry, with profile industries as fallback."""
        text = (message or "").strip()
        targets: list[str] = []
        match = re.search(r"\bcareer\s+in\s+([a-zA-Z][a-zA-Z &/-]{2,40})", text, re.IGNORECASE)
        if not match:
            match = re.search(r"\bin\s+([a-zA-Z][a-zA-Z &/-]{2,40})", text, re.IGNORECASE)
        if match:
            industry = re.split(r"[.?!,;:]", match.group(1).strip())[0].strip()
            if industry:
                targets.append(industry.lower())

        for item in RicoChatAPI._as_list(RicoChatAPI._profile_value(profile, "industries")):
            industry = str(item).strip().lower()
            if industry and industry not in targets:
                targets.append(industry)

        return targets or ["uae"]

    @staticmethod
    def _career_execution_roles(profile: Any, industry_targets: list[str]) -> list[str]:
        roles: list[str] = []
        for item in RicoChatAPI._as_list(RicoChatAPI._profile_value(profile, "target_roles")):
            role = str(item).strip()
            if role and role not in roles:
                roles.append(role)

        skills = {str(item).strip().lower() for item in RicoChatAPI._as_list(RicoChatAPI._profile_value(profile, "skills"))}
        industries = set(industry_targets)
        if "banking" in industries:
            for role in ("Compliance Manager", "ESG Manager", "Operational Risk Manager"):
                if role not in roles:
                    roles.append(role)
        if {"compliance", "risk"} & skills and "Compliance Manager" not in roles:
            roles.append("Compliance Manager")
        if {"esg", "sustainability"} & skills and "ESG Manager" not in roles:
            roles.append("ESG Manager")
        if {"hse", "safety"} & skills and "HSE Manager" not in roles:
            roles.append("HSE Manager")

        return roles[:5] or ["Career Manager"]

    def _handle_career_execution(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Turn career-discovery requests into concrete executable searches."""
        industry_targets = self._extract_career_industry_targets(message, profile)
        primary_industry = industry_targets[0]
        industry_label = primary_industry.title()
        roles = self._career_execution_roles(profile, industry_targets)
        queries = [f"{role} {industry_label} UAE" for role in roles]

        all_matches: list[dict[str, Any]] = []
        for query in queries:
            try:
                all_matches.extend(self._search_jsearch_direct(query))
            except Exception as exc:
                logger.debug("career_execution_search_failed query=%r error=%s", query, exc)

        top_matches = self._sort_by_company_quality(
            self._rerank_by_learned_preferences(all_matches, user_id)
        )[:5]
        formatted = [self._format_match(m, profile) for m in top_matches]
        execution_state = "MATCHES_SCORED" if formatted else "SEARCH_RUNNING"
        role_text = ", ".join(roles[:3])
        if self._is_arabic_text(message):
            msg = (
                f"سأستخدم بيانات سيرتك الذاتية للبحث عن مسارات وظيفية فعلية في {industry_label} بالإمارات. "
                f"أبدأ بـ: {role_text}."
            )
            if formatted:
                msg += f" وجدت {len(formatted)} وظيفة مطابقة حالياً."
            else:
                msg += " لم أجد نتائج مصنّفة بعد، لذا هذه عمليات البحث جاهزة للتحسين."
        else:
            msg = (
                f"I will use your CV profile to search concrete {industry_label} career paths in the UAE. "
                f"I am starting with: {role_text}."
            )
            if formatted:
                msg += f" I found {len(formatted)} current match(es)."
            else:
                msg += " I did not find scored matches yet, so these searches are ready to refine."

        response = {
            "type": "job_matches",
            "intent": "career_execution",
            "execution_state": execution_state,
            "active_profile": bool(profile),
            "message": msg,
            "matches": formatted,
            "next_action": "search_jobs",
            "industry_targets": industry_targets,
            "last_search_queries": queries,
        }
        self._append_chat(user_id, "assistant", response)
        if formatted:
            self._store_search_matches_context(user_id, formatted)
        return response

    @staticmethod
    def _looks_like_next_step_followup(message: str) -> bool:
        """True for short post-confirmation follow-ups like 'so?' or 'what now?'."""
        text = RicoChatAPI._normalize_followup_phrase(message)
        return text in RicoChatAPI._FOLLOWUP_NEXT_STEP_PHRASES

    @staticmethod
    def _normalize_followup_phrase(message: str) -> str:
        """Normalize short follow-up text so punctuation does not break fast paths."""
        text = re.sub(r"\s+", " ", (message or "").strip().lower())
        return FOLLOWUP_BOUNDARY_PUNCT_RE.sub("", text)

    def _handle_next_step_options(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Return instant options after role confirmation — no AI, no pipeline."""
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        suggestions = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
            self._profile_value(profile, "current_role"),
        )
        # Prefer fresh CV-derived suggestions over potentially stale target_roles
        role = (
            suggestions[0]["label"] if suggestions
            else target_roles[0] if target_roles
            else "your target role"
        )

        response: dict[str, Any] = {
            "type": "options",
            "message": (
                "بعد ذلك، اختر ما تريد أن أفعله."
                if self._is_arabic_text(message) else
                "Next, choose what you want me to do."
            ),
            "options": [
                {
                    "action": "find_live_jobs",
                    "label": "Find live UAE jobs",
                    "message": f"find live jobs for {role}",
                    "role": role,
                },
                {
                    "action": "save_target_role",
                    "label": "Save as target role",
                    "message": f"save {role} as target role",
                    "role": role,
                },
                {
                    "action": "prepare_application_angle",
                    "label": "Prepare application angle",
                    "message": f"prepare application angle for {role}",
                    "role": role,
                },
                {
                    "action": "show_profile_roles",
                    "label": "Show roles from my CV",
                    "message": "show roles from my CV",
                },
            ],
            "next_action": "choose_next_step",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _handle_keep_all_target_roles(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Handle 'keep all' follow-up - confirm keeping all target roles."""
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        arabic = self._is_arabic_text(message)
        role_text = (
            ", ".join(map(str, target_roles)) if target_roles
            else ("أدوارك المستهدفة الحالية" if arabic else "your current target roles")
        )

        response = {
            "type": "target_roles_confirmed",
            "message": (
                f"تم — سأحتفظ بجميع الأدوار المستهدفة الحالية: {role_text}."
                if arabic else
                f"Got it — I will keep all current target roles: {role_text}."
            ),
            "target_roles": target_roles,
            "next_actions": [
                {"action": "find_live_jobs", "label": "Find live UAE jobs", "message": "find live jobs for my target roles"},
                {"action": "prepare_application_angle", "label": "Prepare application angle", "message": "prepare application angle for my target roles"},
                {"action": "show_profile_roles", "label": "Show roles from my CV", "message": "show roles from my CV"},
            ],
            "next_action": "choose_next_step",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _handle_both_requested_actions(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Handle 'both please' follow-up - trigger both job search and resume review."""
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        arabic = self._is_arabic_text(message)
        role = target_roles[-1] if target_roles else ("دورك المستهدف" if arabic else "your target role")

        response = {
            "type": "combined_action_plan",
            "message": (
                f"تم — سأقوم بالأمرين معاً: أبدأ بمطابقة وظائف فعلية في الإمارات لدور {role}، "
                "ثم أحضّر سيرتك الذاتية وزاوية التقديم لأقوى المطابقات."
                if arabic else
                f"Got it — I will do both: start with live UAE job matching for {role}, "
                "then prepare your resume/application angle for the strongest matches."
            ),
            "next_actions": [
                {"action": "find_live_jobs", "label": "Find live UAE jobs", "message": f"find live jobs for {role}"},
                {"action": "prepare_application_angle", "label": "Prepare application angle", "message": f"prepare application angle for {role}"},
            ],
            "next_action": "find_live_jobs_then_prepare_application",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _looks_like_selected_role(self, message: str, profile: Any) -> bool:
        """True when the message looks like a user selecting a suggested role.

        Guards (checked in order, fail-fast):
          1. Non-empty, not live search, not generic job request
          2. No question mark
          3. No action verbs (find/search/show/...)
          4. Short phrase -- _looks_like_bare_target_role
          5. Exact or fuzzy match: generated suggestions + target_roles
          6. Fallback: classify_role_candidate says profile_relevant or known_but_off_profile
        """
        if not message or not profile:
            return False

        text       = message.strip()
        text_lower = text.lower()

        if self._is_live_job_search_request(text_lower):
            return False
        if self._looks_like_generic_job_request(text_lower):
            return False
        if "?" in text:
            return False
        if set(text_lower.split()) & self._ACTION_WORDS:
            return False
        if not self._looks_like_bare_target_role(text):
            return False

        # Build known-role set: generated suggestions + saved target_roles
        suggested = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
        )
        known: set[str] = {s["label"].lower() for s in suggested}
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        known.update(r.lower() for r in target_roles if isinstance(r, str))

        if text_lower in known:
            return True
        for k in known:
            if k in text_lower or text_lower in k:
                return True

        # Classifier fallback - only profile_relevant roles get fast-path confirmation
        # known_but_off_profile roles should go through _classified_role_search for clarification
        try:
            classification, canonical_role = classify_role_candidate(text, profile)
            if classification == "profile_relevant" and canonical_role:
                return True
        except Exception:
            pass

        return False

    def _extract_selected_role(self, message: str, profile: Any) -> str:
        """Extract the best-matched role label, preserving acronym casing."""
        text       = (message or "").strip()
        text_lower = text.lower()

        suggested = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
        )
        # Exact match in suggestions
        for s in suggested:
            if s["label"].lower() == text_lower:
                return s["label"]

        # Exact match in target_roles
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        for r in target_roles:
            if isinstance(r, str) and r.lower() == text_lower:
                return r

        # Fuzzy: suggestion label contained in message
        for s in suggested:
            if s["label"].lower() in text_lower:
                return s["label"]

        # Fuzzy: saved role contained in message
        for r in target_roles:
            if isinstance(r, str) and r.lower() in text_lower:
                return r

        # Classifier canonical name
        try:
            _, canonical_role = classify_role_candidate(text, profile)
            if canonical_role:
                return canonical_role
        except Exception:
            pass

        return self.normalize_role_label(text)

    def _handle_role_confirmation(
        self, user_id: str, role: str, profile: Any, message: str = ""
    ) -> dict[str, Any]:
        """Deterministic role_confirmation -- no AI, no external calls."""
        skills = self._as_list(self._profile_value(profile, "skills"))
        years  = self._profile_value(profile, "years_experience")
        certs  = self._as_list(self._profile_value(profile, "certifications"))

        skill_lower = [s.lower() for s in skills]
        cert_lower  = [c.lower() for c in certs]
        all_lower   = skill_lower + cert_lower

        # Safe numeric parsing
        try:
            years_num = float(years)
        except (TypeError, ValueError):
            years_num = None

        arabic = self._is_arabic_text(message)
        reasons: list[str] = []

        if any(k in s for s in all_lower for k in ("iso", "audit", "compliance")):
            reasons.append(
                "لديك خلفية في الجودة (ISO)، التدقيق، أو الامتثال." if arabic else
                "You have ISO, audit, or compliance background."
            )

        if any(k in c for c in cert_lower for k in ("nebosh", "iosh")):
            reasons.append(
                "شهاداتك في السلامة تدعم هذا الدور." if arabic else
                "Your safety certifications support this role."
            )

        if any(k in s for s in all_lower for k in ("environmental", "esg", "sustainability")):
            reasons.append(
                "خلفيتك تتوافق مع العمل البيئي والاستدامة." if arabic else
                "Your background aligns with environmental and sustainability work."
            )

        if any("hse" in s or "safety" in s for s in skill_lower):
            reasons.append(
                "خلفيتك في الصحة والسلامة المهنية تطابق هذا الدور." if arabic else
                "Your HSE/safety background matches this role."
            )

        if years_num is not None:
            if years_num >= 10:
                reasons.append("مستوى خبرتك يدعم الأدوار العليا." if arabic else "Your experience level supports senior roles.")
            elif years_num >= 5:
                reasons.append(
                    "مستوى خبرتك يدعم أدوار المحترفين ذوي الخبرة." if arabic else
                    "Your experience level supports experienced professional roles."
                )
            else:
                reasons.append(
                    f"خبرتك التي تبلغ ~{int(years_num)} سنة مناسبة لهذا الدور." if arabic else
                    f"Your ~{int(years_num)} years of experience fits this role."
                )

        if not reasons:
            reasons.append("هذا الدور يتوافق مع ملفك الشخصي." if arabic else "This role aligns with your profile.")

        response = {
            "type": "role_confirmation",
            "message": (
                f"{role} يعتبر مطابقة قوية لسيرتك الذاتية." if arabic else
                f"{role} is a strong fit for your CV."
            ),
            "role": role,
            "reasons": reasons,
            "next_actions": [
                {
                    "action":  "find_live_jobs",
                    "label":   "Find live UAE jobs",
                    "message": f"find live jobs for {role}",
                    "role":    role,
                },
                {
                    "action":  "save_target_role",
                    "label":   "Save as target role",
                    "message": f"save {role} as target role",
                    "role":    role,
                },
                {
                    "action":  "prepare_application_angle",
                    "label":   "Prepare application angle",
                    "message": f"prepare application angle for {role}",
                    "role":    role,
                },
            ],
            "next_action": "choose_role_next_step",
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    @staticmethod
    def _format_match(m: dict[str, Any], profile: Any) -> dict[str, Any]:
        """Return a backward-compatible chat match with v1 + v2 structured guidance."""
        explanation = build_match_explanation(m, profile)
        # v2 explanation: richer "why this fits" / "worth checking" copy
        try:
            from src.services.job_match_explanation import build_match_explanation as _build_v2
            _v2 = _build_v2(m, profile)
        except Exception:
            _v2 = {}

        # rico_score takes priority; fall back to score. Use explicit None check
        # so that 0 and 0.0 (valid "scored zero" states) are not confused with
        # "no scorer ran" (None). The previous `or` chain and `if raw_score:`
        # falsy-check both treated 0/0.0 the same as None, causing zero scores
        # to be silently dropped and the frontend badge to be hidden.
        _rs = m.get("rico_score")
        raw_score = _rs if _rs is not None else m.get("score")
        # Normalize to [0.0, 1.0] — frontend multiplies by 100 for display.
        # Legacy scoring pipeline (scoring.py) emits 0–100 integers; FitScore
        # (scorer.py) already emits 0.0–1.0 floats. Values > 1 are divided by 100.
        # None is emitted when no scorer ran — the frontend hides the score badge.
        if raw_score is not None:
            _s = float(raw_score)
            normalized_score: float = round(max(0.0, min(1.0, _s / 100.0 if _s > 1.0 else _s)), 4)
        else:
            # No scorer ran — emit 0.0 as the canonical "no score" sentinel; frontend checks for 0.0 to hide badge.
            normalized_score = 0.0

        # Canonical link resolution — the SINGLE source of truth for a job's apply
        # link, shared with the "open the apply link for the Nth job" chat action so
        # a card and the chat command can never disagree. ``usable_link`` is the one
        # trusted URL the Apply button should use; when ``link_unavailable`` is True
        # the frontend must render the fallback CTA instead of a dead-end Apply.
        from src.services.job_link import resolve_job_link as _resolve_job_link
        _lr = _resolve_job_link(m)
        apply_url = _lr["apply_url"]
        alt_link = _lr["alt_link"]
        source_url = _lr["source_url"]
        employer_url = _lr.get("employer_url", "")
        usable_link = _lr["usable_link"]
        link_unavailable = _lr["link_unavailable"]
        link_unavailable_reason = _lr["reason"]
        verification_status = _lr["verification_status"]

        # Clear an alt_link that is itself a Google search intermediary so the
        # frontend falls through to the fallback CTA rather than surfacing it.
        try:
            from src.services.source_quality import is_google_intermediary, classify_company
            if alt_link and is_google_intermediary(alt_link):
                alt_link = ""
            company_quality = classify_company(str(m.get("company") or ""))
        except Exception:
            company_quality = "ok"

        # Description snippet — first 350 chars of real job description for richer cards.
        _raw_desc = str(m.get("description") or m.get("job_description") or "").strip()
        _snippet = _raw_desc[:350].rsplit(" ", 1)[0] + ("…" if len(_raw_desc) > 350 else "") if _raw_desc else ""

        _me_verdict = _v2.get("verdict") or explanation.get("verdict") or "weak_fit"
        _me_summary = _v2.get("summary") or explanation.get("summary") or ""
        _me_why = _v2.get("why_this_fits") or explanation.get("match_reasons") or []
        _me_checks = _v2.get("worth_checking") or explanation.get("match_concerns") or []
        _me_next = _v2.get("recommended_next_step") or ""
        _me_conf = _v2.get("confidence") or "low"

        result = {
            "title": str(m.get("title") or "Untitled role"),
            "company": str(m.get("company") or "Unknown company"),
            "score": normalized_score,
            "apply_url": apply_url,
            "source_url": source_url,
            "alt_link": alt_link,
            "employer_url": employer_url,
            # Canonical link the Apply button should use. When empty, the card must
            # render the fallback CTA instead of a dead-end Apply button.
            "usable_link": usable_link,
            "link_unavailable": link_unavailable,
            "link_unavailable_reason": link_unavailable_reason,
            "verification_status": verification_status,
            "company_quality": company_quality,
            "actions": ["Prepare application", "Save", "Ask why", "Skip"],
            **explanation,
            # v2 richer explanation fields (preferred by updated UI over v1 match_reasons)
            "why_this_fits": _me_why,
            "worth_checking": _me_checks,
            "verdict": _me_verdict,
            "summary": _me_summary,
            # Nested MatchExplanation object for MatchExplanationPanel in JobCard.
            "match_explanation": {
                "verdict": _me_verdict,
                "summary": _me_summary,
                "why_this_fits": _me_why,
                "worth_checking": _me_checks,
                "recommended_next_step": _me_next,
                "confidence": _me_conf,
            },
        }

        location = m.get("location")
        if location:
            result["location"] = str(location)

        employment_type = str(m.get("employment_type") or "").strip()
        if employment_type:
            result["employment_type"] = employment_type

        salary_string = str(m.get("salary_string") or m.get("salary") or "").strip()
        if salary_string:
            result["salary_string"] = salary_string

        if _snippet:
            result["description"] = _snippet

        why = m.get("rico_explanation")
        if why:
            result["why"] = str(why)

        # No trusted apply link → attach safe fallback CTAs so the card never
        # renders a dead-end Apply button.
        if link_unavailable:
            from src.services.job_link import build_link_fallback_cta
            result["fallback_cta"] = build_link_fallback_cta(
                title=result["title"],
                company=result["company"],
                location=str(m.get("location") or ""),
            )

        return result

    @staticmethod
    def _sort_by_company_quality(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Stable sort: named/verified companies first, anonymous/low-quality last.

        Does not remove any jobs — low-quality entries appear at the tail so they
        are only shown when there are not enough better alternatives.
        """
        try:
            from src.services.source_quality import is_low_quality_company as _lqc
            return sorted(matches, key=lambda m: 1 if _lqc(str(m.get("company") or "")) else 0)
        except Exception:
            return matches

    @staticmethod
    def _rerank_by_learned_preferences(
        matches: list[dict[str, Any]],
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Boost jobs matching the user's learned role/location preferences to the top.

        Scoring (lower = better, stable secondary sort preserves original order):
          -3  title contains a preferred role
          -2  location contains a preferred location
          +5  company in avoided list

        Falls back to original order when no preferences are recorded or on error.
        """
        if not matches or not user_id:
            return matches
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            pref_roles = [r.lower() for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
            pref_locs = [loc.lower() for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
            avoided = {
                c.lower()
                for c, w in _lr.get_top_preferences(user_id, "company", limit=10)
                if w < 0
            }
            if not pref_roles and not pref_locs and not avoided:
                return matches

            def _pref_key(m: dict[str, Any]) -> int:
                title = (m.get("title") or "").lower()
                location = (m.get("location") or m.get("city") or "").lower()
                company = (m.get("company") or "").lower()
                score = 0
                if any(r in title for r in pref_roles):
                    score -= 3
                if any(loc in location for loc in pref_locs):
                    score -= 2
                if company in avoided:
                    score += 5
                return score

            return sorted(matches, key=_pref_key)
        except Exception:
            return matches

    def _get_openai_agent(self) -> RicoOpenAIAgent:
        """Get or create OpenAI agent instance."""
        agent = getattr(self, "openai_agent", None)
        if agent is None:
            agent = RicoOpenAIAgent()
            self.openai_agent = agent
        return agent

    SOURCE_KEYWORD = "keyword"
    SOURCE_OPENAI = "openai"
    SOURCE_DEEPSEEK = "deepseek"
    SOURCE_HF = "huggingface"
    SOURCE_FALLBACK = "fallback"
    SOURCE_RATE_LIMITED = "rate_limited"

    # Patterns that indicate a promise-only reply (no actual search executed).
    # Used by _is_promise_only_reply() to guard against returning a hollow response.
    _PROMISE_ONLY_PATTERNS: frozenset = frozenset([
        "جاري البحث", "ببحث الآن", "ببحث", "ثواني", "انتظرني", "لحظة",
        "باستخدام أداة البحث", "سأبحث الآن", "سوف أبحث",
        "i'm searching", "i'll search now", "searching now",
        "i'll look now", "wait", "one moment", "hold on",
        "i'll get back to you",
    ])

    @staticmethod
    def _is_promise_only_reply(text: str) -> bool:
        """Return True if text is a hollow promise (search announced but not executed)."""
        lower = text.lower().strip()
        return any(p in lower for p in RicoChatAPI._PROMISE_ONLY_PATTERNS)

    @staticmethod
    def _source_for_openai_response(response: dict[str, Any]) -> str:
        """Determine source type from response metadata."""
        rtype = response.get("type")
        if rtype == "openai_response":
            return RicoChatAPI.SOURCE_OPENAI
        if rtype == "deepseek_response":
            return RicoChatAPI.SOURCE_DEEPSEEK
        if rtype == "hf_response":
            return RicoChatAPI.SOURCE_HF
        if (
            rtype in {"openai_rate_limited", "deepseek_rate_limited"}
            or response.get("provider_state") == "rate_limited"
        ):
            return RicoChatAPI.SOURCE_RATE_LIMITED
        return RicoChatAPI.SOURCE_FALLBACK

    @staticmethod
    def _bool_attr(agent: Any, name: str, *, fallback: str | None = None) -> bool:
        """Get boolean attribute from agent with optional fallback."""
        value = getattr(agent, name, None)
        if isinstance(value, bool):
            return value
        if fallback:
            fallback_value = getattr(agent, fallback, None)
            if isinstance(fallback_value, bool):
                return fallback_value
        return False

    def _finalize(
        self,
        response: dict[str, Any],
        source: str,
        *,
        profile: Any = None,
        runtime_result: Any = None,
    ) -> dict[str, Any]:
        """Finalize response with metadata."""
        from src.services.agentic_ui_composer import compose
        agentic_ui = compose(runtime_result, response)
        agent = self._get_openai_agent()

        # Get Jotform form IDs from environment
        jotform_form_id = os.getenv("JOTFORM_FORM_ID") or os.getenv("JOTFORM_RICO_FORM_ID")

        # Provider diagnostics are only logged internally, not exposed to users
        # Admin diagnostics available at /health/ai-provider endpoint
        from src.rico_env import get_ai_provider as _get_active_provider
        _active = _get_active_provider()
        return {
            **response,
            "agentic_ui": agentic_ui,
            "response_source": response.get("response_source", source),
            "openai_available": self._bool_attr(agent, "openai_available", fallback="available"),
            "deepseek_available": self._bool_attr(agent, "deepseek_available"),
            "hf_available": self._bool_attr(agent, "hf_available"),
            "provider_available": self._bool_attr(agent, "provider_available", fallback="available"),
            "openai_model": str(getattr(agent, "model", "") or ""),
            # active_provider = what RICO_AI_PROVIDER selects; provider = what actually responded
            "active_provider": _active,
            "profile_context_present": profile is not None,
            # Always a string — null would fail frontend Zod schema validation.
            "jotform_form_id": jotform_form_id or "",
        }

    # Phrases that signal the user wants to provide a CV — either uploading now
    # or announcing that they have one. None of these require an actual file to
    # be present in the message; they trigger a redirect to the upload button.
    _CV_INTENT_PHRASES: tuple[str, ...] = (
        "uploaded cv", "upload cv", "uploaded resume", "upload resume",
        "my cv", "my resume", "resume attached", "cv attached",
        "i have a cv", "i have a resume", "have a cv", "have a resume",
        "have my cv", "have my resume",
        "i'll upload", "ill upload", "will upload", "going to upload",
        "upload it", "uploading my cv", "uploading my resume",
        "attach my cv", "attach my resume",
        "سيرتي الذاتية", "رفع السيرة", "لدي سيرة",
    )

    def _looks_like_cv_upload(self, message: str) -> bool:
        lower = message.lower()
        if bool(CV_FILE_RE.search(message)) or any(
            phrase in lower for phrase in self._CV_INTENT_PHRASES
        ):
            return True
        # Detect raw pasted CV text: long message with structural CV sections
        return self._looks_like_pasted_cv_text(message)

    _PASTED_CV_SECTION_RE = re.compile(
        r"\b(work\s+experience|professional\s+experience|employment\s+history"
        r"|education|qualifications|skills|certifications|objective|summary"
        r"|خبرات?\s+عمل|المؤهلات|مهارات|تعليم|الخبرة\s+العملية)\b",
        re.IGNORECASE | re.UNICODE,
    )
    _PASTED_CV_DATE_RE = re.compile(
        r"\b(19|20)\d{2}\s*[-–—]\s*((19|20)\d{2}|present|current|now|حتى\s+الآن)\b",
        re.IGNORECASE | re.UNICODE,
    )

    def _looks_like_pasted_cv_text(self, message: str) -> bool:
        """Heuristic: long message containing CV structural signals → treat as pasted CV."""
        if len(message) < 400:
            return False
        section_hits = len(self._PASTED_CV_SECTION_RE.findall(message))
        date_hits = len(self._PASTED_CV_DATE_RE.findall(message))
        # Require at least 2 section keywords OR 1 section + 1 date range
        return section_hits >= 2 or (section_hits >= 1 and date_hits >= 1)

    _JOB_REQUEST_WITH_CV_RE = re.compile(
        r"\b(?:find|search|show|get|give|looking\s+for|need|want)\b.{0,80}"
        r"\b(?:jobs?|roles?|positions?|vacancies|openings?|matches?)\b"
        r"|\b(?:match|based\s+on|using|from)\s+my\s+(?:cv|resume)\b"
        r"|(?:ابحث|دور|دوري|جد|جيب|لقيلي)\s.{0,40}(?:وظائف|وظيفة|شغل|فرص)",
        re.IGNORECASE | re.UNICODE,
    )

    def _is_job_request_mentioning_cv(self, message: str) -> bool:
        """True for job-search requests that merely reference the CV.

        "Find UAE jobs that match my CV and experience" contains "my cv" and so
        matches _looks_like_cv_upload, but treating it as a CV-upload
        announcement sends it to _cv_first_profile_response — which overwrites
        cv_filename/cv_status on the profile and replies with a search promise
        nothing fulfills. No actual filename present + job-request shape means
        it must stay on the normal routing path.
        """
        if CV_FILE_RE.search(message):
            return False
        return bool(self._JOB_REQUEST_WITH_CV_RE.search(message))

    def _looks_like_cv_intent_no_file(self, message: str) -> bool:
        """True when user announces they have a CV but hasn't attached a file yet."""
        lower = message.lower()
        if CV_FILE_RE.search(message):
            return False  # actual filename present — handled by cv_first_profile_response
        announce_phrases = (
            "i have a cv", "i have a resume", "have a cv", "have a resume",
            "have my cv", "have my resume",
            "i'll upload", "ill upload", "will upload", "going to upload",
            "upload it", "uploading my cv", "uploading my resume",
            "attach my cv", "attach my resume",
            "سيرتي الذاتية", "رفع السيرة", "لدي سيرة",
        )
        return any(phrase in lower for phrase in announce_phrases)

    def _extract_inline_contact_updates(self, message: str) -> dict[str, Any]:
        """Extract email, phone, and Telegram handle from message."""
        updates: dict[str, Any] = {}
        emails = EMAIL_RE.findall(message)
        phones = PHONE_RE.findall(message)
        if emails:
            updates["email"] = emails[0]
        if phones:
            updates["phone"] = phones[0].strip()
        m = TELEGRAM_MENTION_RE.search(message)
        if m:
            handle = m.group(1) or m.group(2)
            if handle:
                updates["telegram_username"] = handle
        return updates

    def _cv_first_profile_response(self, user_id: str, message: str) -> dict[str, Any]:
        """Handle CV-first profile creation response."""
        filename_match = CV_FILE_RE.search(message)
        filename = filename_match.group(0).strip() if filename_match else "uploaded CV"
        updates = {
            "profile_creation_mode": "cv_first",
            "cv_filename": filename,
            "cv_status": "received_pending_extraction",
            "manual_profile_wizard_disabled": True,
        }
        updates.update(self._extract_inline_contact_updates(message))
        profile = upsert_profile(user_id=user_id, updates=updates)

        missing = [
            ONBOARDING_FIELD_LABELS.get(key, key)
            for key, label in [
                ("email", "email address"),
                ("phone", "phone number"),
                ("preferred_city", "preferred UAE city"),
                ("target_roles", "target role"),
                ("salary_expectation_aed", "salary expectation"),
                ("deal_breakers", "roles or companies to avoid"),
            ]
            if not getattr(profile, key, None) and not (isinstance(profile, dict) and profile.get(key))
        ]

        response = {
            "type": "cv_first_profile",
            "message": (
                f"I found your {filename} and I'll use it to search for matching UAE jobs. "
                "I'm checking roles that fit your background now."
            ),
            "next_action": "parse_cv_and_prefill_profile",
            "manual_questions_disabled": True,
            "missing_after_extraction_should_be_limited_to": missing,
            "confirmation_prompt": (
                "After extraction, show the profile summary and ask: save this profile, or edit a field?"
            ),
        }
        self._append_chat(user_id, "assistant", response)
        return response

    def _handle_pasted_cv_text(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Handle raw pasted CV text from an active user.

        Extracts inline contact details, stores the CV text for async parsing,
        and returns a structured acknowledgement without sending the blob to AI.
        """
        updates: dict[str, Any] = {"pasted_cv_pending": True}
        updates.update(self._extract_inline_contact_updates(message))
        # Truncate stored text to 8000 chars to avoid DB size issues
        updates["pasted_cv_text"] = message[:8000]
        upsert_profile(user_id=user_id, updates=updates)

        response_msg = (
            (
                "أرى تفاصيل سيرتك الذاتية. سأستخرج ملفك الشخصي من هذا النص — "
                "أعطني لحظة لتحليل خبراتك ومهاراتك وتعليمك.\n\n"
                "بعد الاستخراج سأعرض لك ملخص الملف الشخصي وتقدر تؤكد أو تعدّل أي حقل. "
                "تقدر أيضاً ترفع سيرة ذاتية PDF أو Word لاستخراج أدق."
            )
            if self._is_arabic_text(message) else
            (
                "I can see your CV details. I'll extract your profile from this text — "
                "give me a moment to parse your experience, skills, and education.\n\n"
                "Once extracted, I'll show you a profile summary and you can confirm or edit any field. "
                "You can also upload a PDF or Word CV for more accurate extraction."
            )
        )
        response = {
            "type": "cv_text_received",
            "message": response_msg,
            "next_action": "parse_pasted_cv_text",
        }
        self._append_chat(user_id, "assistant", response_msg)
        return response

    _WHATS_NEXT_PHRASES = frozenset([
        "what's next", "whats next", "what next", "what now",
        "what can you do", "what can i do", "help", "options", "menu",
        "show options", "show menu", "next steps",
    ])

    # Phrases users type when selecting a help-menu option or expressing generic
    # job-search intent — must NEVER be classified as job role titles.
    _JOB_SEARCH_HELP_PHRASES: frozenset[str] = frozenset({
        "finding jobs",
        "finding jobs matching my target roles",
        "find matching uae jobs",
        "find me matching jobs",
        "job search",
        "job searching",
        "search for jobs",
        "help me find jobs",
        "help me search for jobs",
    })

    _ACTION_WORDS = frozenset({
        "find", "search", "show", "get", "apply", "save",
        "prepare", "draft", "update", "track",
    })

    _FOLLOWUP_NEXT_STEP_PHRASES = frozenset({
        "so", "so?", "what now", "what now?", "what's next", "whats next",
        "next", "next?", "then", "then?", "now", "now?", "ok", "okay",
        "continue", "go on",
    })

    # Multi-word continuation phrases that are never job role titles.
    # Matched after normalisation — see _is_continuation_intent().
    _CONTINUATION_PHRASES: frozenset[str] = frozenset({
        # English multi-word — bare "continue" / "go on" are intentionally excluded
        # because they are already in _FOLLOWUP_NEXT_STEP_PHRASES and route to the
        # options menu via _looks_like_next_step_followup (which strips punctuation).
        "keep going", "its ok keep going", "it's ok keep going",
        "ok keep going", "okay keep going",
        "go ahead", "go ahead please", "please go ahead",
        "yes continue", "yes please continue", "sure continue",
        "ok continue", "okay continue", "yes go ahead",
        "continue please", "please continue", "just continue",
        "carry on", "yes carry on", "ok carry on",
        "sounds good continue", "let's continue", "lets continue",
        "proceed", "yes proceed", "ok proceed",
        # Arabic
        "كمل", "استمر", "واصل", "ماشي كمل", "ماشي استمر",
        "تمام كمل", "تمام استمر", "اوك كمل", "اوك استمر",
        "يلا كمل", "يلا استمر", "نعم استمر", "نعم كمل",
        "حسنا استمر", "طيب كمل", "طيب استمر",
    })

    # Signals in the last assistant message that indicate a post-CV/profile
    # context where continuation means "proceed with job search".
    _POST_CV_CONTINUATION_SIGNALS: tuple[str, ...] = (
        "based on your cv", "from your cv", "your cv has been",
        "cv parsed", "cv uploaded", "profile built", "profile updated",
        "i suggest", "suggested roles", "i found the following roles",
        "roles from your background", "roles i suggest",
        "what would you like to do", "what should i search",
        "shall i start searching", "shall i search",
        "ready to search", "you can now search",
        "want me to search", "search for roles",
        "بناءً على سيرتك", "بناء على سيرتك", "تم تحليل سيرتك",
        "الأدوار المقترحة", "ماذا تريد أن أفعل", "هل أبحث",
    )

    # Affirmative / negative single-word replies in EN + AR
    _AFFIRMATIVE_PHRASES = frozenset({
        "yes", "yeah", "yep", "yup", "sure", "absolutely", "of course",
        "please", "go ahead", "do it", "ok", "okay", "alright", "sounds good",
        "نعم", "أيوه", "ايوه", "اوك", "حسنا", "تفضل", "اكيد", "طبعا", "موافق",
        "بالتأكيد", "نعم من فضلك", "يلا", "اه", "آه",
    })
    _NEGATIVE_PHRASES = frozenset({
        "no", "nope", "nah", "not now", "skip", "cancel", "never mind",
        "لا", "لأ", "مو الحين", "مو ذا", "بعدين", "ما ابي", "ما أبغى",
    })

    _ARABIC_WHAT_NOW_TERMS = frozenset({
        "مالحل", "ما الحل", "ماالحل",
        "مالحل الان", "مالحل الآن",
        "ايش نسوي", "شو نسوي",
        "ايش اسوي", "شو اسوي",
        "وش نسوي",
    })

    @staticmethod
    def _is_arabic_what_now(message: str) -> bool:
        """True for Arabic 'what now / what's the solution' follow-up phrases."""
        text = re.sub(r"[\s؟?.!,]+", " ", (message or "").strip().lower()).strip()
        return any(term in text for term in RicoChatAPI._ARABIC_WHAT_NOW_TERMS)

    @staticmethod
    def _is_affirmative(message: str) -> bool:
        """True for yes/نعم/sure single-word affirmatives."""
        text = re.sub(r"[\s؟?.!،,]+", " ", (message or "").strip().lower()).strip()
        return text in RicoChatAPI._AFFIRMATIVE_PHRASES

    @staticmethod
    def _is_continuation_intent(message: str) -> bool:
        """True for multi-word 'keep going / continue / كمل' phrases that are never job titles.

        Catches messages like "its ok keep going", "ok keep going", "كمل", "استمر"
        that pass _looks_like_bare_target_role because their first token is not in
        _NON_ROLE_STARTERS, but whose intent is clearly "proceed, not a role name".
        """
        text = re.sub(r"[\s؟?.!،,‌‍]+", " ", (message or "").strip().lower()).strip()
        if text in RicoChatAPI._CONTINUATION_PHRASES:
            return True
        # Regex patterns for common continuation structures not worth enumerating
        if re.fullmatch(
            r"(its?\s+ok(ay)?\s+)?keep\s+going|"
            r"(ok(ay)?|sure|yes|alright)\s+(keep\s+going|continue|go\s+on|carry\s+on|proceed)|"
            r"(just\s+)(continue|proceed|carry\s+on|go\s+ahead)(\s+please)?|"
            r"(continue|proceed|carry\s+on|go\s+ahead)\s+please|"
            r"please\s+(continue|proceed|carry\s+on|go\s+ahead)|"
            r"(كمل|استمر|واصل)(\s+من\s+فضلك)?|"
            r"(ماشي|تمام|اوك|يلا|نعم|حسنا|طيب)\s+(كمل|استمر|واصل)",
            text,
        ):
            return True
        return False

    @staticmethod
    def _is_negative(message: str) -> bool:
        """True for no/لا single-word negatives."""
        text = re.sub(r"[\s؟?.!،,]+", " ", (message or "").strip().lower()).strip()
        return text in RicoChatAPI._NEGATIVE_PHRASES

    @staticmethod
    def _is_arabic_text(message: str) -> bool:
        return bool(re.search(r"[\u0600-\u06FF]", message or ""))

    @staticmethod
    def _format_pref_changes(prefs: "dict[str, Any]") -> list[str]:
        """Render a preferences dict as human-readable '**Label** \u2192 value' lines.

        Shared by the BUG-04 profile-update consent flow: the confirmation prompt
        (before persisting) and the post-save acknowledgement both use it so the
        wording stays identical.
        """
        labels: dict[str, str] = {
            "target_roles": "Target role",
            "preferred_cities": "Preferred city",
            "years_experience": "Years of experience",
            "skills": "Skills",
            "industries": "Industry",
            "salary_expectation_aed": "Salary expectation",
            "employment_type": "Employment type",
            "visa_status": "Visa status",
            "nationality": "Nationality",
            "telegram_username": "Telegram username",
        }
        changes: list[str] = []
        for _k, _v in (prefs or {}).items():
            _label = labels.get(_k, _k.replace("_", " ").title())
            _val_str = ", ".join(str(x) for x in _v) if isinstance(_v, list) else str(_v)
            if _k == "salary_expectation_aed":
                try:
                    _val_str = f"AED {int(float(_v)):,}/month"
                except (TypeError, ValueError):
                    _val_str = f"AED {_val_str}/month"
            changes.append(f"**{_label}** \u2192 {_val_str}")
        return changes

    @staticmethod
    def _build_proposed_changes(prefs: "dict[str, Any]", profile: "dict[str, Any]") -> "list[dict[str, Any]]":
        """Build a list of RicoProposedChange dicts for agentic_ui (CAREER-OS-07)."""
        labels: dict[str, str] = {
            "target_roles": "Target role",
            "preferred_cities": "Preferred city",
            "years_experience": "Years of experience",
            "skills": "Skills",
            "industries": "Industry",
            "salary_expectation_aed": "Salary expectation (AED/mo)",
            "minimum_salary_aed": "Minimum salary (AED/mo)",
            "employment_type": "Employment type",
            "visa_status": "Visa status",
            "nationality": "Nationality",
            "telegram_username": "Telegram username",
            "current_role": "Current role",
            "current_company": "Current company",
            "notice_period": "Notice period",
        }
        profile_dict: dict = profile if isinstance(profile, dict) else (vars(profile) if profile else {})
        changes: list[dict] = []
        for field, proposed_value in (prefs or {}).items():
            changes.append({
                "field": labels.get(field, field.replace("_", " ").title()),
                "current_value": profile_dict.get(field),
                "proposed_value": proposed_value,
                "source": "chat",
            })
        return changes

    @staticmethod
    def _wants_no_favorite(message: str) -> bool:
        lower = (message or "").lower()
        return bool(
            re.search(r"\b(do\s*not|don't|dont|no|not)\b.{0,24}\b(favou?rite|save|bookmark)\b", lower)
            or re.search(r"\b(favou?rite|save|bookmark)\b.{0,24}\b(no|not)\b", lower)
            or "لا تحفظ" in message
            or "لا تضيف" in message
            or "مفضلة" in message and ("لا" in message or "بدون" in message)
        )

    @staticmethod
    def _requests_application_draft(message: str) -> bool:
        lower = (message or "").lower()
        if re.search(r"\b(draft|write|compose|prepare|generate|create)\b.{0,50}\b(message|email|letter|cover|inmail|linkedin)\b", lower):
            return True
        normalized = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", message or "")
        normalized = re.sub(r"[آأإٱ]", "ا", normalized)
        has_message_word = "رساله" in normalized or "رسالة" in normalized
        has_draft_verb = any(term in normalized for term in ("صيغ", "اكتب", "اكتبها", "جهز", "نراجع"))
        return has_draft_verb or (has_message_word and RicoChatAPI._requests_application_send(message))

    @staticmethod
    def _requests_application_send(message: str) -> bool:
        lower = (message or "").lower()
        if re.search(r"\b(send|submit|forward|deliver|go ahead|proceed|do it)\b", lower):
            return True
        normalized = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", message or "")
        normalized = re.sub(r"[آأإٱ]", "ا", normalized)
        return any(term in normalized for term in ("ارسل", "ارسال", "ابعث", "قدّم", "قدم", "كمل"))

    @staticmethod
    def _looks_like_application_channel_followup(message: str) -> bool:
        if not message or not message.strip():
            return False
        return (
            RicoChatAPI._requests_application_draft(message)
            or RicoChatAPI._requests_application_send(message)
            or RicoChatAPI._wants_no_favorite(message)
        )

    @staticmethod
    def _job_context_value(job: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = job.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _clean_explicit_job_value(value: Any) -> str:
        text = str(value or "")
        text = re.sub(r"\s+", " ", text).strip(" \t\r\n\"'`.,!?;:")
        text = re.sub(
            r"\b(?:please|use what you know about me|using what you know about me)$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip(" \t\r\n\"'`.,!?;:")

    @classmethod
    def _extract_explicit_draft_job_from_message(cls, message: str) -> dict[str, str]:
        text = str(message or "")
        if not cls._requests_application_draft(text):
            return {}

        language = "ar" if cls._is_arabic_text(text) else "en"

        def _finalize(job: dict[str, str]) -> dict[str, str]:
            cleaned = {k: v for k, v in job.items() if v}
            if cleaned:
                cleaned.setdefault("language", language)
            return cleaned

        title_company = re.search(
            r"\b(?:for|to)\s+"
            r"(?P<title>[A-Za-z][A-Za-z0-9&/()+.' -]{1,90}?)"
            r"\s+\bat\s+"
            r"(?P<company>[A-Za-z][A-Za-z0-9&/()+.' -]{1,90}?)"
            r"(?:\s+\bin\s+(?P<location>[A-Za-z][A-Za-z .'-]{1,40}))?"
            r"(?=$|[.?!,;])",
            text,
            flags=re.IGNORECASE,
        )
        if title_company:
            job = {
                "title": cls._clean_explicit_job_value(title_company.group("title")),
                "company": cls._clean_explicit_job_value(title_company.group("company")),
            }
            location = cls._clean_explicit_job_value(title_company.group("location"))
            if location:
                job["location"] = location
            return _finalize(job)

        company_only = re.search(
            r"\b(?:to|at)\s+"
            r"(?P<company>[A-Z][A-Za-z0-9&/()+.' -]{1,90}?)"
            r"(?:\s+\bin\s+(?P<location>[A-Za-z][A-Za-z .'-]{1,40}))?"
            r"(?=$|[.?!,;])",
            text,
        )
        if company_only:
            job = {"company": cls._clean_explicit_job_value(company_only.group("company"))}
            location = cls._clean_explicit_job_value(company_only.group("location"))
            if location:
                job["location"] = location
            return _finalize(job)

        # ── Arabic slot extraction ────────────────────────────────────────────
        # "اكتب لي خطاب تقديم لوظيفة <role> في شركة <company> في <city>"
        # Role connector: لوظيفة/لمنصب/لدور — Company connector: في شركة/لدى/لشركة/مع شركة
        # City connector: في <city>. Company names may be English (e.g. Aldar Properties).
        _ar_company_conn = r"(?:في\s+شرك[ةه]|مع\s+شرك[ةه]|في\s+مؤسس[ةه]|لدى|لدي|لشرك[ةه])"
        _ar_role_conn = r"(?:لوظيف[ةه]|لمنصب|لدور|لشغل|كموظف)"

        ar_full = re.search(
            rf"{_ar_role_conn}\s+"
            r"(?P<title>.+?)\s+"
            rf"{_ar_company_conn}\s+"
            r"(?:شرك[ةه]\s+)?(?P<company>.+?)"
            r"(?:\s+في\s+(?P<location>[^.?!,؛;]+?))?"
            r"\s*[.?!,؛;]?\s*$",
            text,
        )
        if ar_full:
            job = {
                "title": cls._clean_explicit_job_value(ar_full.group("title")),
                "company": cls._clean_explicit_job_value(ar_full.group("company")),
            }
            location = cls._clean_explicit_job_value(ar_full.group("location"))
            if location:
                job["location"] = location
            return _finalize(job)

        ar_company = re.search(
            rf"{_ar_company_conn}\s+"
            r"(?:شرك[ةه]\s+)?(?P<company>.+?)"
            r"(?:\s+في\s+(?P<location>[^.?!,؛;]+?))?"
            r"\s*[.?!,؛;]?\s*$",
            text,
        )
        if ar_company:
            job = {"company": cls._clean_explicit_job_value(ar_company.group("company"))}
            location = cls._clean_explicit_job_value(ar_company.group("location"))
            if location:
                job["location"] = location
            return _finalize(job)

        ar_role = re.search(
            rf"{_ar_role_conn}\s+(?P<title>.+?)"
            r"(?:\s+في\s+(?P<location>[^.?!,؛;]+?))?"
            r"\s*[.?!,؛;]?\s*$",
            text,
        )
        if ar_role:
            job = {"title": cls._clean_explicit_job_value(ar_role.group("title"))}
            location = cls._clean_explicit_job_value(ar_role.group("location"))
            if location:
                job["location"] = location
            return _finalize(job)

        return {}

    @staticmethod
    def _normalize_context_match_value(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    def _resolve_explicit_draft_job_context(
        self,
        user_id: str,
        explicit_job: dict[str, str],
    ) -> tuple[dict[str, Any], str]:
        """Enrich explicit drafting targets from the authenticated user's applications only."""
        company = self._normalize_context_match_value(explicit_job.get("company"))
        title = self._normalize_context_match_value(explicit_job.get("title"))
        if not company:
            return dict(explicit_job), "explicit_message"

        try:
            from src.repositories import applications_repo

            applications = applications_repo.get_all(user_id=user_id)
        except Exception:
            applications = []

        for app in applications or []:
            if not isinstance(app, dict):
                continue
            app_company = self._normalize_context_match_value(
                self._job_context_value(app, "company", "company_name")
            )
            if not app_company or app_company != company:
                continue
            app_title = self._normalize_context_match_value(
                self._job_context_value(app, "title", "job_title")
            )
            if title and app_title and title != app_title:
                continue
            merged = dict(app)
            merged.update({k: v for k, v in explicit_job.items() if v})
            return merged, "explicit_message_saved_application"

        return dict(explicit_job), "explicit_message"

    @staticmethod
    def _log_document_draft_context_source(source: str, job: dict[str, Any] | None = None) -> None:
        logger.info(
            "document_draft_context source=%s has_title=%s has_company=%s",
            source,
            bool((job or {}).get("title")),
            bool((job or {}).get("company")),
        )

    def _cover_letter_clarification_message(
        self,
        profile: Any,
        partial_job: dict[str, Any] | None = None,
        arabic: bool | None = None,
    ) -> str:
        name = self._profile_value(profile, "name") or ""
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        title = self._job_context_value(partial_job or {}, "title")
        company = self._job_context_value(partial_job or {}, "company")
        if arabic is None:
            arabic = str((partial_job or {}).get("language") or "").strip().lower() == "ar"
        if arabic:
            if company and not title:
                return (
                    f"يمكنني كتابة خطاب تقديم لـ **{company}**"
                    f"{('، ' + name) if name else ''}. ما المسمى الوظيفي المستهدف؟\n\n"
                    "أرسل المسمى الوظيفي، أو الصق إعلان الوظيفة مباشرة."
                )
            if title and not company:
                return (
                    f"يمكنني كتابة خطاب تقديم لوظيفة **{title}**"
                    f"{('، ' + name) if name else ''}. ما اسم الشركة المستهدفة؟\n\n"
                    "أرسل اسم الشركة، أو الصق إعلان الوظيفة مباشرة."
                )
            if target_roles:
                roles_hint = "، ".join(target_roles[:3])
                return (
                    f"يمكنني كتابة خطاب تقديم لك{('، ' + name) if name else ''}. "
                    "ما المسمى الوظيفي والشركة المستهدفان؟\n\n"
                    f"أدوارك المستهدفة: **{roles_hint}**\n\n"
                    "أرسل المسمى الوظيفي واسم الشركة، أو الصق إعلان الوظيفة مباشرة."
                )
            return (
                f"يمكنني كتابة خطاب تقديم لك{('، ' + name) if name else ''}. "
                "ما المسمى الوظيفي والشركة المستهدفان؟\n\n"
                "أرسل:\n"
                "• المسمى الوظيفي واسم الشركة\n"
                "• أو الصق إعلان الوظيفة مباشرة"
            )
        if company and not title:
            return (
                f"I can write a cover letter for **{company}**"
                f"{', ' + name if name else ''}. Which role should I target?\n\n"
                "Reply with the role title, or paste the job posting directly."
            )
        if title and not company:
            return (
                f"I can write a cover letter for **{title}**"
                f"{', ' + name if name else ''}. Which company should I target?\n\n"
                "Reply with the company name, or paste the job posting directly."
            )
        if target_roles:
            roles_hint = ", ".join(target_roles[:3])
            return (
                f"I can write a cover letter for you{', ' + name if name else ''}. "
                "Which role and company should I target?\n\n"
                f"Your target roles: **{roles_hint}**\n\n"
                "Reply with the role title and company name, or paste the job posting directly."
            )
        return (
            f"I can write a cover letter for you{', ' + name if name else ''}. "
            "Which role and company should I target?\n\n"
            "Reply with:\n"
            "• Role title and company name\n"
            "• Or paste the job posting directly"
        )

    def _draft_application_message(self, job: dict[str, Any], profile: Any, *, arabic: bool) -> str:
        title = self._job_context_value(job, "title") or ("الدور" if arabic else "the role")
        company = self._job_context_value(job, "company") or ("الشركة" if arabic else "the company")
        skills = self._as_list(self._profile_value(profile, "skills"))
        certs = self._as_list(self._profile_value(profile, "certifications"))
        strengths = ", ".join(str(s) for s in (skills + certs)[:4]) or ("خبرتي ذات الصلة" if arabic else "my relevant experience")
        if arabic:
            return (
                f"مرحباً،\n\n"
                f"أود التقدم لدور {title} لدى {company}. لدي خبرة مرتبطة بمتطلبات الدور، "
                f"خصوصاً في {strengths}. أعتقد أن خلفيتي في التدقيق والامتثال البيئي يمكن أن تضيف قيمة مباشرة للفريق.\n\n"
                f"يسعدني مشاركة سيرتي الذاتية ومناقشة كيف يمكنني دعم احتياجاتكم.\n\n"
                f"مع التحية"
            )
        return (
            f"Hello,\n\n"
            f"I would like to apply for the {title} role at {company}. My background aligns with the role, "
            f"especially around {strengths}. I believe my audit, compliance, and UAE-market experience can add value quickly.\n\n"
            f"I would be happy to share my CV and discuss how I can support your team.\n\n"
            f"Best regards"
        )

    def _handle_application_channel_followup(
        self, user_id: str, message: str, profile: Any
    ) -> dict[str, Any] | None:
        """Clarify draft/send channels without claiming unsupported application submission."""
        if not self._looks_like_application_channel_followup(message):
            return None
        # Post-interview thank-you / follow-up email questions contain "send" but are
        # handled by _handle_post_interview_email — do not intercept them here.
        if _POST_INTERVIEW_EMAIL_RE.search(message):
            return None
        # Resignation letter questions contain "write ... letter" but are handled
        # by _handle_resignation_letter — do not intercept them here.
        if _RESIGNATION_LETTER_RE.search(message):
            return None

        wants_draft = self._requests_application_draft(message)
        wants_send = self._requests_application_send(message)
        no_favorite = self._wants_no_favorite(message)
        recruiter_email = EMAIL_RE.search(message or "")
        if wants_draft:
            self._log_document_draft_context_source("clarification_required", {})
            msg = self._cover_letter_clarification_message(profile)
            return {
                "type": "cover_letter_prompt",
                "intent": "draft_message",
                "message": msg,
                "next_action": "provide_job_for_cover_letter",
            }

        if not (wants_send or no_favorite or recruiter_email):
            return None

        arabic = self._is_arabic_text(message)
        if arabic:
            message_text = (
                "أحتاج تحديد الوظيفة قبل تجهيز أو إرسال أي مسودة. "
                "أرسل لي المسمى الوظيفي واسم الشركة، ومعهما إيميل الـ recruiter أو رابط/طريقة الإرسال. "
                "LinkedIn/InMail أعطيك له نصاً للنسخ واللصق فقط، وبوابات التوظيف أتعامل معها كرابط وإرشاد فقط."
            )
        else:
            message_text = (
                "I need the job before I prepare or send any draft. "
                "Tell me the role title and company, plus the recruiter email or apply channel/link. "
                "For LinkedIn/InMail, I can only give you copy/paste text; I cannot send through LinkedIn directly. "
                "For job portals, I can guide/open the link only; I cannot claim direct submission."
            )
            if no_favorite:
                message_text = "Got it - I will not save or favorite it. " + message_text
        if recruiter_email:
            if arabic:
                message_text += "\n\nوصلني إيميل الـ recruiter. سأبقيها كمسودة جاهزة للمراجعة قبل أي إرسال فعلي."
            else:
                message_text += "\n\nI have the recruiter email. I will keep this as a review-ready draft before any actual send."

        response = {
            "type": "application_channel_clarification",
            "intent": "application_channel_clarification",
            "message": message_text,
            "draft": "",
            "next_action": "await_send_destination",
            "channel_policy": {
                "linkedin": "copy_paste_only",
                "email": "requires_recruiter_email_and_mail_integration",
                "job_portal": "open_or_guide_only",
            },
        }
        self._append_chat(user_id, "assistant", message_text)
        return response

    # Phrases the user says to request a list of results after Rico shows a summary.
    _LIST_FOLLOWUP_PHRASES = frozenset({
        # English
        "list them", "show them", "show list", "show me", "show me them",
        "list it", "show it", "list", "show all", "show all of them",
        "display them", "give me the list", "give me them", "print them",
        "what are they", "which ones", "tell me which ones",
        # Application/lifecycle-specific aliases (resolve to last lifecycle context)
        "list applications", "show applications",
        "list my applications", "show my applications",
        "list saved", "show saved", "list my saved", "show my saved",
        # Arabic
        "اذكرهم", "اذكرها", "اعرضهم", "اعرضها", "ورجيني القائمة",
        "ورني القائمة", "عرضهم", "عرضها", "اعرض القائمة", "القائمة",
        "وريني", "ورني", "اعرضلي", "اكتبهم", "اكتبها",
    })

    @staticmethod
    def _is_list_followup(message: str) -> bool:
        # Normalize before matching so "list them,," / "list them." both resolve.
        return RicoChatAPI._normalize_followup_phrase(message) in RicoChatAPI._LIST_FOLLOWUP_PHRASES

    # ── Canonical "last turn" memory ─────────────────────────────────────────
    # One reliable record of the last meaningful thing Rico did, so vague
    # follow-ups ("make sure", "that one", "list them") can anchor to a real
    # intent + object instead of being re-classified from scratch by the AI.
    #
    # Only "anchor-worthy" response types update it; clarifications, smalltalk,
    # errors and option menus deliberately do NOT overwrite the anchor, so a
    # follow-up after a clarification still resolves against the last real turn.
    _LAST_TURN_INTENT_BY_TYPE = {
        "application_status":        "application_tracking",
        "application":               "application_tracking",
        "lifecycle_query":           "lifecycle_query",
        "job_matches":               "job_search",
        "job_search_explicit":       "job_search",
        "no_results_recovery":       "job_search",
        "save_job":                  "save_job",
        "track_job":                 "track_job",
        "open_apply_link":           "open_apply_link",
        "mark_applied":              "mark_applied",
        "prepare_application":       "prepare_application",
        "explain_match":             "explain_match",
        "draft_message":             "draft_message",
        "interview_prep":            "interview_prep",
        "profile_summary":           "profile_summary",
        "profile_role_suggestions":  "profile_role_suggestions",
    }

    # Lifecycle/application intents whose anchor a "list them"/"make sure" replays.
    _LAST_TURN_LIFECYCLE_INTENTS = frozenset({"application_tracking", "lifecycle_query"})

    # Short "verify / are you sure / re-confirm" follow-ups. These must NOT fall
    # through to bare-role classification (which would treat "make sure please"
    # as a job title). They re-confirm the last informational turn instead.
    _VERIFY_FOLLOWUP_PHRASES = frozenset({
        "make sure", "make sure please", "please make sure",
        "are you sure", "you sure", "u sure", "sure about that",
        "is that right", "is that correct", "is this correct", "is this right",
        "are you certain", "you certain", "really", "for real", "seriously",
        "double check", "double check please", "check again", "recheck",
        "verify", "verify please", "verify that", "confirm that", "make certain",
        # Arabic
        "متأكد", "هل أنت متأكد", "تأكد", "تأكد من فضلك", "أكد",
    })

    def _set_last_turn(
        self,
        user_id: str,
        *,
        intent: str,
        response_type: str,
        obj: dict[str, Any] | None = None,
        user_message: str = "",
    ) -> None:
        """Persist the single canonical last-turn record."""
        try:
            self.memory.set_context(user_id, "last_turn", {
                "intent": intent,
                "response_type": response_type,
                "object": obj or {},
                "user_message": (user_message or "")[:300],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            logger.debug("rico_chat: failed to store last_turn user=%s", user_id)

    def _get_last_turn(self, user_id: str) -> dict[str, Any]:
        try:
            return self.memory.get_context(user_id, "last_turn") or {}
        except Exception:
            return {}

    def _record_last_turn(self, user_id: str, message: str, result: dict[str, Any]) -> None:
        """From a finalized response, update the canonical last-turn anchor.

        Only anchor-worthy response types update it (see _LAST_TURN_INTENT_BY_TYPE);
        clarifications / errors / menus are skipped so the anchor stays meaningful.
        """
        if not isinstance(result, dict):
            return
        rtype = str(result.get("type") or "")
        intent = self._LAST_TURN_INTENT_BY_TYPE.get(rtype)
        if not intent:
            return  # not anchor-worthy — keep the previous anchor intact

        obj: dict[str, Any] = {}
        entities = result.get("entities")
        if isinstance(entities, dict):
            if entities.get("title"):
                obj["title"] = entities["title"]
            if entities.get("company"):
                obj["company"] = entities["company"]
        # Carry the lifecycle replay marker so "list them"/"make sure" can re-run it.
        if intent in self._LAST_TURN_LIFECYCLE_INTENTS:
            qt = (self._get_lifecycle_context(user_id) or {}).get("last_query_type")
            if qt:
                obj["query_type"] = qt
        self._set_last_turn(
            user_id, intent=intent, response_type=rtype, obj=obj, user_message=message,
        )

    @staticmethod
    def _is_verify_followup(message: str) -> bool:
        """True for short 'are you sure / make sure / re-confirm' follow-ups."""
        norm = RicoChatAPI._normalize_followup_phrase(message)
        if norm in RicoChatAPI._VERIFY_FOLLOWUP_PHRASES:
            return True
        # Arabic phrases may carry diacritics/extra spacing — check membership loosely.
        stripped = re.sub(r"[\s؟?.!،,]+", " ", (message or "").strip().lower()).strip()
        return stripped in RicoChatAPI._VERIFY_FOLLOWUP_PHRASES

    _VALID_LIFECYCLE_QUERY_TYPES = frozenset({
        "lifecycle_show_saved",
        "lifecycle_show_applied",
        "lifecycle_show_opened_not_applied",
    })

    def _resolve_lifecycle_query_for_followup(self, user_id: str) -> str | None:
        """Resolve which lifecycle query a 'list them' follow-up should replay.

        Prefers the dedicated lifecycle context; falls back to the canonical
        last-turn anchor so the follow-up still works if only the anchor is set.
        """
        last_query = (self._get_lifecycle_context(user_id) or {}).get("last_query_type")
        if last_query in self._VALID_LIFECYCLE_QUERY_TYPES:
            return last_query
        last = self._get_last_turn(user_id)
        if last.get("intent") in self._LAST_TURN_LIFECYCLE_INTENTS:
            qt = (last.get("object") or {}).get("query_type")
            if qt in self._VALID_LIFECYCLE_QUERY_TYPES:
                return qt
            # An application-tracking turn with no explicit query_type defaults
            # to the applied funnel — that's what was just shown.
            if last.get("intent") == "application_tracking":
                return "lifecycle_show_applied"
        return None

    def _resolve_verify_followup(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any] | None:
        """Anchor a 'make sure / are you sure' follow-up to the last real turn.

        Re-runs the last informational query so Rico re-confirms with fresh data
        instead of re-classifying the vague phrase as a new role/intent. Never
        triggers a mutation (apply/save) — those still require explicit action.
        """
        arabic = self._is_arabic_text(message)
        last = self._get_last_turn(user_id)
        intent = last.get("intent")
        if not intent:
            return None

        if intent in self._LAST_TURN_LIFECYCLE_INTENTS:
            lifecycle_query = self._resolve_lifecycle_query_for_followup(user_id)
            if intent == "application_tracking" and not (last.get("object") or {}).get("query_type"):
                # The last turn was the applications summary — re-run it verbatim.
                resp = self._handle_application_tracking(user_id, intent="application_tracking", message=message)
            elif lifecycle_query:
                resp = self._handle_lifecycle_query(user_id, lifecycle_query, message=message)
            else:
                resp = self._handle_application_tracking(user_id, intent="application_tracking", message=message)
            # Prefix so the user sees this as a re-confirmation, not a fresh answer.
            base = resp.get("message") or ""
            if arabic:
                resp["message"] = (
                    "تحققت مرة أخرى — هذا بالضبط ما هو مسجل لدي:\n\n" + base
                    if base else "تحققت من سجلاتك."
                )
            else:
                resp["message"] = (
                    "I double-checked — here's exactly what I have on record:\n\n" + base
                    if base else "I double-checked your records."
                )
            return resp

        if intent == "job_search":
            obj = last.get("object") or {}
            title = obj.get("title") or ""
            if arabic:
                if title:
                    return {
                        "type": "clarification",
                        "message": (
                            f"نعم — آخر بحث أظهرته لك كان عن \"{title}\". "
                            "تريد أن أعيد تشغيله للحصول على نتائج فعلية جديدة، أو نضيّق الدور أو المدينة؟"
                        ),
                    }
                return {
                    "type": "clarification",
                    "message": (
                        "نعم — هذا كان آخر بحث فعلي قمت به. تريد أن أعيد تشغيله "
                        "للحصول على نتائج جديدة، أو نضيّقه بالدور أو المدينة؟"
                    ),
                }
            if title:
                return {
                    "type": "clarification",
                    "message": (
                        f"Yes — the last search I showed you was for \"{title}\". "
                        "Want me to re-run it for fresh live results, or refine the role or city?"
                    ),
                }
            return {
                "type": "clarification",
                "message": (
                    "Yes — that was the latest live search I ran. Want me to re-run it "
                    "for fresh results, or narrow it by role or city?"
                ),
            }

        # Save / apply / track / prepare etc. — confirm the specific job on record.
        obj = last.get("object") or {}
        title = obj.get("title")
        company = obj.get("company")
        if title and company:
            if arabic:
                action_label = {
                    "save_job": "محفوظة", "track_job": "متابَعة",
                    "mark_applied": "مسجَّلة كمُقدَّمة", "open_apply_link": "تم فتح رابط التقديم لها",
                    "prepare_application": "تم تحضير طلب تقديم لها",
                }.get(intent, "مسجَّلة")
                return {
                    "type": "clarification",
                    "message": (
                        f"مؤكَّد — \"{title}\" في {company} {action_label} في متابعاتك. "
                        "تريد أن أعرض القائمة الكاملة أو الخطوة التالية؟"
                    ),
                    "entities": {"title": title, "company": company},
                }
            action_label = {
                "save_job": "saved", "track_job": "tracked",
                "mark_applied": "marked as applied", "open_apply_link": "opened the apply link for",
                "prepare_application": "prepared an application for",
            }.get(intent, "noted")
            return {
                "type": "clarification",
                "message": (
                    f"Confirmed — I have \"{title}\" at {company} {action_label} in your tracker. "
                    "Want me to show the full list or take the next step?"
                ),
                "entities": {"title": title, "company": company},
            }
        return None

    def _store_lifecycle_context(self, user_id: str, query_type: str) -> None:
        """Remember the last lifecycle query so a follow-up 'list them' can replay it."""
        try:
            self.memory.set_context(user_id, "lifecycle_query_context", {"last_query_type": query_type})
        except Exception:
            logger.debug("rico_chat: failed to store lifecycle context user=%s", user_id)

    def _get_lifecycle_context(self, user_id: str) -> dict[str, Any]:
        try:
            return self.memory.get_context(user_id, "lifecycle_query_context") or {}
        except Exception:
            return {}

    # ── Pending job search state helpers ─────────────────────────────────────
    # Stores intent for job search so when user says "تمام"/"نعم"/"ok" after Rico
    # announces a search plan, the search is actually executed rather than just
    # re-promising. TTL is 15 minutes to avoid stale state across sessions.

    _PENDING_JOB_SEARCH_KEY: str = "pending_job_search"

    def _store_pending_job_search(
        self,
        user_id: str,
        *,
        role: str,
        location: str = "",
        query_type: str = "profile_based",
    ) -> None:
        try:
            import time
            self.memory.set_context(
                user_id,
                self._PENDING_JOB_SEARCH_KEY,
                {
                    "role": role,
                    "location": location,
                    "query_type": query_type,
                    "created_at": int(time.time()),
                    "expires_at": int(time.time()) + 900,  # 15 min TTL
                },
            )
        except Exception:
            pass

    def _get_pending_job_search(self, user_id: str) -> dict:
        try:
            ctx = self.memory.get_context(user_id, self._PENDING_JOB_SEARCH_KEY) or {}
            import time
            if ctx.get("expires_at", 0) < int(time.time()):
                return {}
            return ctx
        except Exception:
            return {}

    def _clear_pending_job_search(self, user_id: str) -> None:
        try:
            self.memory.set_context(user_id, self._PENDING_JOB_SEARCH_KEY, {})
        except Exception:
            pass

    # Outgoing-message signals meaning Rico offered/announced a job search this
    # turn without executing it. Mirror of the read-side job_search_signals so a
    # follow-up confirmation ("تمام"/"yes") runs the real search. Kept focused on
    # explicit offers/promises to avoid storing on incidental CV-flow chatter.
    _SEARCH_OFFER_SIGNALS: tuple[str, ...] = (
        "shall i search", "shall i start searching", "want me to search",
        "should i search",  # known_but_off_profile clarification path
        "search for roles", "ready to search", "you can now search",
        "what should i search", "find live jobs", "shall i look for",
        "أبحث لك", "هل أبحث", "سأبحث", "ببحث", "وظائف حية", "أبحث عن وظائف",
        "هل تريد البحث",  # Arabic career-change offer: "هل تريد البحث عن وظائف في X؟"
    )

    def _maybe_store_pending_job_search(self, user_id: str, result: dict[str, Any]) -> None:
        """Persist a pending job search when Rico's response offers/announces a
        search but does not execute one this turn.

        Without this, ``_store_pending_job_search`` is never called, so the
        ``_get_pending_job_search`` checks (Priority-0 in ``_resolve_pending_intent``
        and the "تمام" acknowledgement intercept) can never fire and a confirmed
        search silently falls back to a dead-end acknowledgement. Profile is only
        resolved when an offer is actually detected to avoid a per-turn DB hit.
        """
        try:
            rtype = str(result.get("type") or "")
            # A search was already executed this turn — nothing left pending.
            if rtype in ("job_matches", "job_list"):
                return
            msg = str(result.get("message") or "")
            if not msg:
                return
            low = msg.lower()  # lower() leaves Arabic unchanged, so AR signals still match
            if not any(sig in low for sig in self._SEARCH_OFFER_SIGNALS):
                return
            profile = self._resolve_profile(user_id)
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else None
            if role:
                self._store_pending_job_search(user_id, role=role)
        except Exception:
            pass

    def _get_last_assistant_message(self, user_id: str) -> str:
        """Return the last assistant message text for pending-intent resolution."""
        try:
            recent = self._get_recent_messages(user_id, limit=10)
            for m in reversed(recent):
                if m.get("role") == "assistant":
                    return str(m.get("content") or m.get("message") or "")
        except Exception:
            pass
        return ""

    def _set_flow_state(self, user_id: str, state: str) -> None:
        """Persist the current conversational flow state for follow-up routing."""
        try:
            ctx = self._get_recent_context(user_id)
            ctx["last_flow_state"] = state
            self._store_recent_context(user_id, ctx)
        except Exception:
            pass

    def _resolve_pending_intent(self, user_id: str, message: str, profile: Any) -> dict[str, Any] | None:
        """If last Rico message offered a yes/no action and user affirms, execute it.

        Returns a response dict if a pending intent was resolved, else None.
        """
        # Priority 0: stored pending job search state (most reliable — set explicitly when
        # Rico announces a search plan and the turn ends without executing it).
        # Checked BEFORE the _is_affirmative guard because this method is called from
        # both the affirmative path (yes/ok) and the follow_up_confirmation path (تمام/نعم/كمل).
        pending_js = self._get_pending_job_search(user_id)
        if pending_js and pending_js.get("role"):
            self._clear_pending_job_search(user_id)
            pending_role = pending_js["role"]
            pending_loc = pending_js.get("location", "")
            return self._classified_role_search(
                user_id, pending_role, profile, location=pending_loc
            )

        if not self._is_affirmative(message):
            return None

        last = self._get_last_assistant_message(user_id).lower()
        if not last:
            return None

        # Detect what Rico last offered
        cv_improve_signals = (
            "اقتراح" in last or "تحسين سيرة" in last or "improve your cv" in last
            or "cv improvement" in last or "update your cv" in last
        )
        job_search_signals = (
            "find live" in last or "search for" in last or "ابحث" in last
            or "وظائف حية" in last or "shall i search" in last or "want me to search" in last
            or any(sig in last for sig in self._POST_CV_CONTINUATION_SIGNALS)
        )
        application_angle_signals = (
            "application angle" in last or "cover letter" in last or "tailor" in last
            or "زاوية تقديم" in last
        )
        reminder_signals = (
            "reminder" in last or "follow up" in last or "تذكير" in last
        )

        if cv_improve_signals:
            return self._handle_cv_generate_from_profile(user_id, profile, message)
        if job_search_signals:
            # Execute the actual search — do NOT route to _answer_with_ai_fallback which
            # only produces a conversational promise ("ببحث الآن...") without fetching jobs.
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else None
            if role:
                self._clear_pending_job_search(user_id)
                return self._classified_role_search(
                    user_id, role, profile
                )
            # No role available — ask for role instead of promising search
            arabic = self._is_arabic_text(message)
            return {
                "type": "clarification",
                "message": (
                    "ما هو الدور الذي تبحث عنه؟ أحتاج المسمى الوظيفي لأبدأ البحث."
                    if arabic else
                    "What role are you looking for? I need a job title to run the search."
                ),
            }
        if application_angle_signals:
            return self._answer_with_ai_fallback(
                user_id=user_id,
                message="Prepare my application angle and suggest how to tailor it for the role.",
                profile=profile,
                save_user_message=False,
            )
        if reminder_signals:
            # Attempt to set a real reminder against the most recently discussed job.
            # Only emit success after backend confirmation; never claim a fake reminder.
            arabic = self._is_arabic_text(message)
            recent_matches = self._recent_search_matches(user_id)
            job_for_reminder = recent_matches[0] if recent_matches else None
            if job_for_reminder:
                title = str(job_for_reminder.get("title") or "").strip()
                company = str(job_for_reminder.get("company") or "").strip()
                try:
                    result = agent_runtime.handle_action(
                        user_id=user_id,
                        action="remind",
                        job=job_for_reminder,
                        source="chat",
                    )
                    if result.ok:
                        _label = f"**{title}**" + (f" — {company}" if company else "")
                        msg = (
                            f"تم ضبط التذكير لـ {_label}. سأذكّرك بالمتابعة."
                            if arabic else
                            f"Reminder set for {_label}. I'll nudge you to follow up."
                        )
                        self._append_chat(user_id, "assistant", msg)
                        return {"type": "reminder_set", "message": msg}
                except Exception:
                    pass
                # Backend call failed — be honest
                msg = (
                    "لم أتمكن من ضبط التذكير الآن. حاول مرة أخرى بعد قليل."
                    if arabic else
                    "I couldn't set a reminder right now. Please try again in a moment."
                )
                self._append_chat(user_id, "assistant", msg)
                return {"type": "reminder_set_failed", "message": msg}
            # No job in context — ask which job before claiming anything
            msg = (
                "أي وظيفة تريد ضبط تذكير لها؟ أرسل لي اسم الوظيفة أو الشركة."
                if arabic else
                "Which job would you like me to set a reminder for? Send me the title or company name."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "intent": "set_reminder", "message": msg}

        return None

    # ── Pending field resolver ────────────────────────────────────────────────

    _PENDING_FIELD_ASK_SIGNALS: dict[str, tuple[str, ...]] = {
        "telegram_username": (
            "telegram username", "your telegram", "@username",
            "اسم المستخدم في تيليجرام", "تيليجرام",
        ),
        "phone": (
            "phone number", "your phone", "mobile number",
            "رقم الهاتف", "رقم جوالك",
        ),
        "email": (
            "email address", "your email", "بريدك الإلكتروني",
        ),
        "preferred_cities": (
            "preferred cities", "preferred city", "which city", "what city",
            "city (e.g.", "city preference", "المدن المفضلة", "المدينة المفضلة",
        ),
    }

    # Known UAE cities for preferred_cities field resolution
    _UAE_CITIES: frozenset[str] = frozenset({
        "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah",
        "fujairah", "umm al quwain", "al ain", "deira", "bur dubai",
        "دبي", "أبوظبي", "الشارقة", "عجمان", "رأس الخيمة",
        "الفجيرة", "أم القيوين", "العين",
    })

    # Yes/no/confirmation words that must not be stored as city names.
    # A bare "تمام" (ok/fine) was being persisted as preferred_cities=["تمام"]
    # and then rendered in every CV draft. Keep in sync with affirmative/ack
    # vocabulary used elsewhere.
    _CITY_REJECT_WORDS: frozenset[str] = frozenset({
        # English
        "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "fine", "great",
        "good", "cool", "done", "alright", "please", "thanks", "thank you",
        "go ahead", "no", "nope", "nah",
        # Arabic
        "نعم", "أيوه", "ايوه", "اوك", "اوكي", "اوكيه", "حسنا", "حسناً",
        "تمام", "تمم", "اكيد", "أكيد", "طبعا", "طبعاً", "تفضل", "يلا",
        "ماشي", "زين", "كويس", "شكرا", "شكراً", "موافق", "اه", "آه", "لا",
    })

    def _resolve_pending_field(
        self, user_id: str, message: str, profile: Any
    ) -> "dict[str, Any] | None":
        """Intercept user replies to Rico's field prompts (e.g. 'What is your Telegram?').

        Checks the last assistant message for known field-request signals and, if the
        current user message looks like a valid value for that field, saves it and
        returns a confirmation response — bypassing intent classification entirely.

        Returns a response dict if a pending field was resolved, else None.
        """
        msg = message.strip()
        if not msg:
            return None

        ctx = self._get_recent_context(user_id)
        # Explicit pending field stored by an earlier turn
        pending_field: str | None = ctx.get("_pending_field")

        # Fallback: infer from last assistant message
        if not pending_field:
            last_msg = self._get_last_assistant_message(user_id).lower()
            for field, signals in self._PENDING_FIELD_ASK_SIGNALS.items():
                if any(sig in last_msg for sig in signals):
                    pending_field = field
                    break

        if not pending_field:
            return None

        # ── Telegram handle ───────────────────────────────────────────────────
        if pending_field == "telegram_username":
            handle = msg if msg.startswith("@") else f"@{msg}"
            if not TELEGRAM_HANDLE_RE.match(handle):
                return None
            upsert_profile(user_id=user_id, updates={"telegram_username": handle})
            ctx.pop("_pending_field", None)
            self._store_recent_context(user_id, ctx)
            reply = (
                f"Got it — I've saved your Telegram username as **{handle}**. "
                "You'll receive job alerts and updates there."
            )
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "preferences_updated",
                "message": reply,
                "updated": {"telegram_username": handle},
            }

        # ── Phone number ──────────────────────────────────────────────────────
        if pending_field == "phone":
            if not PHONE_RE.match(msg):
                return None
            upsert_profile(user_id=user_id, updates={"phone": msg})
            ctx.pop("_pending_field", None)
            self._store_recent_context(user_id, ctx)
            reply = f"Got it — I've saved your phone number as **{msg}**."
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "preferences_updated",
                "message": reply,
                "updated": {"phone": msg},
            }

        # ── Email address ─────────────────────────────────────────────────────
        if pending_field == "email":
            if not EMAIL_RE.fullmatch(msg):
                return None
            upsert_profile(user_id=user_id, updates={"email": msg})
            ctx.pop("_pending_field", None)
            self._store_recent_context(user_id, ctx)
            reply = f"Got it — I've saved your email as **{msg}**."
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "preferences_updated",
                "message": reply,
                "updated": {"email": msg},
            }

        # ── Preferred cities (CV flow) ────────────────────────────────────────
        if pending_field == "preferred_cities":
            # Reject messages that look like intents rather than city answers.
            # A city reply is short and does not contain intent-bearing verbs.
            _INTENT_VERBS = re.compile(
                r"\b(find|search|show|get|help|apply|generate|create|make|write|"
                r"update|start|look|resume|cv|cover|letter|job|jobs|work)\b",
                re.IGNORECASE,
            )
            if _INTENT_VERBS.search(msg):
                return None
            # Also reject long free-text answers unlikely to be city names
            if len(msg.split()) > 6:
                return None
            # Accept any non-empty text as city input — normalise and save
            from src.services.city_validation import sanitize_cities
            raw_cities = [c.strip() for c in re.split(r"[,،/|]+", msg) if c.strip()]
            # Drop affirmations and misfiled chat/document messages (e.g. a
            # "Summarize this document for me." captured while awaiting a city)
            # so a non-city value can never be stored as a preferred city.
            raw_cities = sanitize_cities(raw_cities, known_cities=self._UAE_CITIES)
            if not raw_cities:
                return None
            # Title-case known UAE cities; keep others as entered
            normalised = []
            for c in raw_cities:
                if c.lower() in self._UAE_CITIES:
                    normalised.append(c.title())
                else:
                    normalised.append(c)
            upsert_profile(user_id=user_id, updates={"preferred_cities": normalised})
            ctx.pop("_pending_field", None)
            ctx.pop("_pending_cv_generate", None)
            self._store_recent_context(user_id, ctx)
            # Reload profile so the CV draft picks up the new cities
            updated_profile = self._resolve_profile(user_id)
            return self._handle_cv_generate_from_profile(user_id, updated_profile, message)

        # ── Confirm profile update (BUG-04 consent gate) ──────────────────────
        # A 'profile_update' intent stashes the extracted preferences here and
        # asks for confirmation instead of writing immediately. We persist ONLY
        # on an explicit affirmative; anything else cancels the pending write.
        if pending_field == "confirm_profile_update":
            pending = ctx.get("_pending_profile_update") or {}
            # One-shot: clear the pending state regardless of the outcome so it
            # can never linger and silently apply on a later, unrelated turn.
            ctx.pop("_pending_field", None)
            ctx.pop("_pending_profile_update", None)
            self._store_recent_context(user_id, ctx)
            arabic = self._is_arabic_text(msg)

            if self._is_affirmative(msg) and pending:
                upsert_profile(user_id=user_id, updates=pending)
                _changes = self._format_pref_changes(pending)
                if arabic:
                    reply = (
                        "تم الحفظ:\n"
                        + "\n".join(f"• {c}" for c in _changes)
                        + "\n\nسأطبّق هذا على عمليات البحث القادمة."
                    )
                else:
                    reply = (
                        "Saved:\n"
                        + "\n".join(f"• {c}" for c in _changes)
                        + "\n\nI'll apply this to future job searches."
                    )
                self._append_chat(user_id, "assistant", reply)
                return {
                    "type": "preferences_updated",
                    "message": reply,
                    "updated": pending,
                }

            if self._is_negative(msg):
                reply = (
                    "تمام — لم أغيّر أي شيء في ملفك الشخصي."
                    if arabic
                    else "No problem — I haven't changed anything in your profile."
                )
                self._append_chat(user_id, "assistant", reply)
                return {"type": "info", "message": reply}

            # Neither yes nor no: the user moved on. Pending is already cleared,
            # so let the new message route normally through intent classification.
            return None

        return None

    def _resolve_settings_command(
        self, user_id: str, message: str
    ) -> "dict[str, Any] | None":
        """Intercept settings and notification commands.

        Commands like "enable telegram notifications" must route to settings,
        not job search (prevent searching for "Telegram Notifications" jobs).

        Returns a response dict if a settings command was resolved, else None.
        """
        msg = message.strip()
        if not msg:
            return None

        # ── Enable notifications ────────────────────────────────────────────
        if _SETTINGS_NOTIFICATION_ENABLE_RE.search(msg):
            # Save preference and return confirmation
            upsert_profile(user_id=user_id, updates={"notifications_enabled": True})
            reply = (
                "I've enabled notifications for you. You'll now receive job alerts "
                "and application updates via Telegram and email."
            )
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "settings_updated",
                "message": reply,
                "updated": {"notifications_enabled": True},
                "target_route": "/settings",
            }

        # ── Disable notifications ───────────────────────────────────────────
        if _SETTINGS_NOTIFICATION_DISABLE_RE.search(msg):
            upsert_profile(user_id=user_id, updates={"notifications_enabled": False})
            reply = (
                "I've disabled notifications. You won't receive job alerts or "
                "application updates until you re-enable them."
            )
            self._append_chat(user_id, "assistant", reply)
            return {
                "type": "settings_updated",
                "message": reply,
                "updated": {"notifications_enabled": False},
                "target_route": "/settings",
            }

        # ── Show settings ───────────────────────────────────────────────────
        if _SETTINGS_SHOW_RE.search(msg):
            reply = (
                "Opening your notification settings. You can manage which "
                "channels you want to receive alerts through."
            )
            return {
                "type": "navigate",
                "message": reply,
                "target_route": "/settings",
            }

        return None

    _JOB_SEARCH_OPTIONS = {
        "type": "options",
        "message": "Here is what I can help you with:",
        "options": [
            {"action": "find_jobs",          "label": "Find matching UAE jobs"},
            {"action": "apply",              "label": "Prepare a job application"},
            {"action": "interview_prep",     "label": "Prepare for an interview"},
            {"action": "update_profile",     "label": "Update my profile"},
            {"action": "track_applications", "label": "Track my applications"},
        ],
    }

    @staticmethod
    def _search_jsearch_meta(role: str, location: str = "") -> Any:
        """Query live UAE jobs for *role* via the provider cascade (cache → Jooble
        → Adzuna → JSearch → degraded), with cache + retry + quota protection.

        When *location* is given the query targets that specific UAE city instead of
        the generic "UAE" suffix, producing sharper results for city-constrained searches.

        Returns a ``jsearch_client.FetchResult`` so the caller can tell a genuine
        empty result apart from a rate-limited / quota-exhausted source. Never raises.
        The method name is retained for backward compatibility with existing callers
        and tests; it now routes through ``src.job_providers``.
        """
        from src import job_providers

        result = job_providers.search_jobs(role, location)
        logger.info(
            "provider_search role=%r location=%r provider=%s results=%d cache_hit=%s rate_limited=%s quota=%s",
            role, location or "UAE", result.provider, len(result.items),
            result.cache_hit, result.rate_limited, getattr(result, "quota_exhausted", False),
        )
        return result

    @staticmethod
    def _search_jsearch_direct(role: str) -> list[dict[str, Any]]:
        """Backward-compatible list wrapper around :meth:`_search_jsearch_meta`."""
        return RicoChatAPI._search_jsearch_meta(role).items

    def _provider_degraded_response(
        self, user_id: str, role: str, *,
        location: str = "",
        quota_exhausted: bool = False,
        rate_limited: bool = False,
    ) -> dict[str, Any]:
        """Build a safe fallback response when every job provider is degraded.

        Renders actionable CTAs (try later, search company site, Google/LinkedIn
        search, copy, save) rather than a dead-end "no results" / broken-link card.
        The external links are plain *search* URLs — Rico never scrapes them.
        """
        from urllib.parse import quote_plus

        loc = location or "UAE"
        google_url = f"https://www.google.com/search?q={quote_plus(f'{role} {loc} jobs')}"
        linkedin_url = (
            "https://www.linkedin.com/jobs/search/?"
            f"keywords={quote_plus(role)}&location={quote_plus(loc)}"
        )

        if quota_exhausted:
            provider_state = "quota_exhausted"
            message = (
                f"Live job providers have reached their search quota for now, so I can't pull "
                f"fresh **{role}** listings this minute. Here are safe ways to keep moving:"
            )
        elif rate_limited:
            provider_state = "rate_limited"
            message = (
                f"The job source is temporarily rate-limited, so fresh **{role}** results aren't "
                f"available right now. Try again shortly, or use one of these:"
            )
        else:
            provider_state = "unavailable"
            message = (
                f"I couldn't reach a live job source for **{role}** right now. "
                f"Here are safe ways to keep moving:"
            )

        options = [
            {"action": "retry_search", "label": "Try again later", "role": role, "location": location},
            {"action": "open_url", "label": "Search on Google", "url": google_url},
            {"action": "open_url", "label": "Search on LinkedIn", "url": linkedin_url},
            {"action": "search_company_site", "label": "Search a company career site", "role": role},
            {"action": "copy_text", "label": "Copy role title", "text": role},
            {"action": "save_role_search", "label": "Save this role search", "role": role, "location": location},
        ]

        response = {
            "type": "provider_degraded",
            "intent": "search_jobs",
            "message": message,
            "matches": [],
            "result_count": 0,
            "degraded": True,
            "provider_state": provider_state,
            "options": options,
            "links": {"google": google_url, "linkedin": linkedin_url},
            "next_action": "provider_degraded_fallback",
        }

        # Arm a pending search so a later "try again" re-runs this exact role once
        # quota recovers, without the user retyping it.
        try:
            self._store_pending_job_search(
                user_id, role=role, location=location, query_type="provider_degraded",
            )
        except Exception:
            pass

        self._append_chat(user_id, "assistant", message)
        return response

    def _target_role_search_response(
        self, user_id: str, role: str, profile: Any,
        from_saved_profile: bool = False,
        location: str = "",
        employment_type_filter: str = "",
    ) -> dict[str, Any]:
        """Handle target role search with role intelligence integration."""
        try:
            normalized_role = normalize_role(role)
        except Exception as e:
            logger.warning("Role normalization failed", extra={"user_id": user_id, "role": role, "error": str(e)})
            normalized_role = role

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        if normalized_role and normalized_role.lower() not in {str(item).lower() for item in target_roles}:
            # BUG-04: searching for a role must NOT silently persist it as a
            # standing target_role. Use it for THIS search context only — the
            # user can save it deliberately ("save <role> as my target role").
            target_roles.append(normalized_role)

        search_role = normalized_role or role
        operation = self._begin_job_search_operation(user_id, search_role)
        operation_id = str(operation["operation_id"])

        # Primary path: provider-cascade query for the exact requested role.
        # Falls back to the legacy scraper pipeline only when providers are empty.
        rate_limited = False
        quota_exhausted = False
        fetch_provider = ""
        fetch_error = ""
        import time as _time
        _search_start = _time.monotonic()
        try:
            # Pass location only when set — keeps single-arg monkeypatched
            # stand-ins (tests) and any legacy overrides working unchanged.
            fetch = (
                self._search_jsearch_meta(search_role, location)
                if location
                else self._search_jsearch_meta(search_role)
            )
            all_matches = fetch.items
            rate_limited = fetch.rate_limited
            quota_exhausted = getattr(fetch, "quota_exhausted", False)
            fetch_provider = getattr(fetch, "provider", "")
            fetch_error = getattr(fetch, "error", "") or ""
            _search_elapsed = _time.monotonic() - _search_start
            logger.info(
                "job_search: role=%r results=%d provider=%s rate_limited=%s quota=%s elapsed=%.2fs op=%s",
                search_role, len(all_matches), fetch_provider, rate_limited,
                quota_exhausted, _search_elapsed, operation_id,
            )
            if not all_matches:
                search_profile = (
                    _dc_replace(profile, target_roles=[search_role])
                    if is_dataclass(profile)
                    else profile
                )
                workflow_result = self.system.run_for_profile(search_profile)
                all_matches = workflow_result.get("matches", [])
        except Exception as exc:
            _search_elapsed = _time.monotonic() - _search_start
            logger.warning(
                "job_search_failed: role=%r elapsed=%.2fs op=%s err=%s",
                search_role, _search_elapsed, operation_id, type(exc).__name__,
            )
            mark_failed(user_id, operation_id, str(exc))
            _graceful_msg = (
                "I couldn't complete that search right now. "
                "Try specifying a role name — for example: 'Compliance Manager jobs in Dubai'."
            )
            self._append_chat(user_id, "assistant", _graceful_msg)
            return {"type": "search_error", "message": _graceful_msg, "intent": "job_search_explicit"}

        # Degraded-provider guard: when no live results AND a *configured* provider
        # is quota-exhausted / rate-limited / failing, show a safe fallback CTA
        # instead of an empty/dead-end "results" card. When no providers are
        # configured at all (e.g. local/test env → error "no_providers_configured")
        # we deliberately fall through to the existing empty-results handling so
        # behaviour is unchanged.
        _provider_failed = (
            quota_exhausted
            or rate_limited
            or fetch_error == "all_providers_unavailable"
        )
        if not all_matches and _provider_failed:
            try:
                mark_completed(user_id, operation_id, 0)
            except Exception:
                pass
            return self._provider_degraded_response(
                user_id, normalized_role or search_role,
                location=location,
                quota_exhausted=quota_exhausted,
                rate_limited=rate_limited,
            )

        # Filter out already-applied jobs
        try:
            from src.applications import is_applied_batch, get_job_id
            if all_matches:
                applied_map = is_applied_batch(all_matches, user_id=user_id)
                all_matches = [m for m in all_matches if not applied_map.get(get_job_id(m), False)]
        except Exception as e:
            logger.debug("Applied-job filter unavailable: %s", e)

        # Filter out UAE-nationals-only listings for non-national users.
        try:
            nationality = (
                self._profile_value(profile, "nationality") or
                self._profile_value(profile, "citizenship") or ""
            ).strip().lower()
            is_uae_national = nationality in ("uae", "emirati", "emirati national", "uae national")
            if not is_uae_national and all_matches:
                from src.eligibility_filter import filter_for_non_nationals
                all_matches = filter_for_non_nationals(all_matches)
        except Exception as e:
            logger.debug("Eligibility filter unavailable: %s", e)

        # Client-side employment_type filter — JSearch does not expose this as a query
        # parameter, so we filter post-fetch when the user specified a constraint.
        if employment_type_filter and all_matches:
            _emp_norm = employment_type_filter.lower().replace("-", "").replace(" ", "")
            _contract_terms = {"contract", "contractor", "freelance", "temp", "temporary"}
            _fulltime_terms = {"permanent", "fulltime", "direct"}
            _remote_terms = {"remote"}

            def _emp_ok(job: dict) -> bool:
                jt = (job.get("employment_type") or "").lower().replace("-", "").replace(" ", "")
                if not jt:
                    return True  # unknown → keep
                if _emp_norm in _contract_terms:
                    return any(t in jt for t in _contract_terms)
                if _emp_norm in _fulltime_terms:
                    return not any(t in jt for t in _contract_terms)
                if _emp_norm in _remote_terms:
                    return "remote" in jt
                return True

            _filtered = [m for m in all_matches if _emp_ok(m)]
            if _filtered:
                all_matches = _filtered

        # Deduplicate by title+company fingerprint within this response.
        # JSearch deduplicates by job_id, but the same role at the same company
        # can appear under slightly different job_ids (different posting dates).
        seen_fps: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for m in all_matches:
            fp = (
                str(m.get("title") or "").lower().strip()
                + "|"
                + str(m.get("company") or "").lower().strip()
            )
            if fp and fp != "|" and fp not in seen_fps:
                seen_fps.add(fp)
                deduped.append(m)
        all_matches = deduped

        # Profile-fit ranking: score each result against the user's target roles,
        # skills, and deal-breakers. Zero-latency (pure keyword matching) so it
        # doesn't add round-trip time to the chat response.
        try:
            from src.llm_scorer import rank_by_profile_fit as _rbpf
            _profile_target_roles = self._as_list(
                self._profile_value(profile, "target_roles")
            )
            _profile_skills = self._as_list(
                self._profile_value(profile, "skills")
            )
            _profile_deal_breakers = self._as_list(
                self._profile_value(profile, "deal_breakers")
            )
            all_matches = _rbpf(
                all_matches,
                target_roles=[str(r) for r in _profile_target_roles if r],
                skills=[str(s) for s in _profile_skills if s],
                deal_breakers=[str(d) for d in _profile_deal_breakers if d],
            )
        except Exception:
            pass

        # Quality-sort: within same profile-fit tier, surface live/verified
        # sources before aggregators/dead links.
        _QUALITY_RANK: dict[str, int] = {
            "live_verified": 0,
            "needs_source_verification": 1,
            "google_intermediary": 2,
            "login_required": 3,
            "rate_limited": 4,
            "aggregator_untrusted": 5,
        }
        try:
            from src.services.source_quality import (
                classify_url as _cq, is_google_intermediary as _igi,
                is_low_quality_company as _lqc,
            )
            # Pre-compute learned preference sets once (avoid repeated DB calls per job)
            _pref_roles: list[str] = []
            _pref_locs: list[str] = []
            _avoided_cos: set[str] = set()
            try:
                from src.repositories.learning_repo import get_learning_repository as _glr
                _lr = _glr()
                _pref_roles = [r.lower() for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
                _pref_locs = [loc.lower() for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
                _avoided_cos = {
                    c.lower() for c, w in _lr.get_top_preferences(user_id, "company", limit=10) if w < 0
                }
            except Exception:
                pass

            def _quality_key(m: dict[str, Any]) -> int:
                url = str(
                    m.get("job_apply_link") or m.get("apply_link") or m.get("link") or ""
                )
                status = "google_intermediary" if _igi(url) else _cq(url)
                # Secondary sort: quality within profile-fit bands
                fit = m.get("profile_fit_score", 0)
                fit_band = max(0, 5 - fit // 20)  # 5 bands (0=best fit, 4=worst)
                # Company quality penalty: anonymous/low_quality jobs sort after legitimate ones
                company_penalty = 20 if _lqc(str(m.get("company") or "")) else 0
                # Preference bonus: jobs matching learned role/location float up
                title = (m.get("title") or "").lower()
                location = (m.get("location") or m.get("city") or "").lower()
                company_lower = (m.get("company") or "").lower()
                pref_bonus = 0
                if _pref_roles and any(r in title for r in _pref_roles):
                    pref_bonus -= 3
                if _pref_locs and any(loc in location for loc in _pref_locs):
                    pref_bonus -= 2
                if company_lower in _avoided_cos:
                    pref_bonus += 5
                return fit_band * 10 + _QUALITY_RANK.get(status, 1) + company_penalty + pref_bonus

            all_matches.sort(key=_quality_key)
        except Exception:
            pass

        top_matches = all_matches[:5]
        formatted = [self._format_match(m, profile) for m in top_matches]

        skills = self._as_list(self._profile_value(profile, "skills"))[:8]
        years = self._profile_value(profile, "years_experience")
        # Drop any corrupted non-city value (e.g. a misfiled chat message) so it
        # never poisons the search location or fit score.
        from src.services.city_validation import sanitize_cities
        cities = sanitize_cities(self._as_list(self._profile_value(profile, "preferred_cities")))
        city_text = f" in {', '.join(map(str, cities[:2]))}" if cities else " in the UAE"
        basis = []
        if years:
            try:
                years_int = int(float(years))
            except (TypeError, ValueError):
                years_int = None
            if years_int is not None:
                basis.append(f"~{years_int} years experience")
        if skills:
            basis.append("skills: " + ", ".join(map(str, skills[:6])))
        basis_text = " using your CV profile" + (f" ({'; '.join(basis)})" if basis else "")

        role_intelligence_data = self._enrich_with_role_intelligence(
            user_id, normalized_role, profile, skills, years, cities
        )

        message = self._build_role_search_message(
            normalized_role, city_text, basis_text, top_matches, role_intelligence_data,
            from_saved_profile=from_saved_profile,
        )

        response = {
            "type": "job_matches",
            "intent": "search_jobs",
            "message": message,
            "matches": formatted,
            "entities": {"job_title": normalized_role, "from_cv_profile": True},
            "operation_id": operation_id,
            "operation_status": "completed",
            "operation_type": "job_search",
            "result_count": len(formatted),
            "search_query": search_role,
            "broadened": len(all_matches) == 0,
            "rate_limited": rate_limited,
        }

        if rate_limited:
            response["rate_limit_notice"] = (
                "This source is temporarily rate-limited. "
                "Try the alternate link on each result, or search again shortly."
            )

        if role_intelligence_data:
            response["role_intelligence"] = role_intelligence_data

        self._append_chat(user_id, "assistant", response)
        mark_completed(user_id, operation_id, len(formatted))
        if formatted:
            self._store_search_matches_context(
                user_id, formatted,
                search_role=search_role,
                search_location=location or ", ".join(map(str, cities[:2])),
            )
        return response

    def _enrich_with_role_intelligence(
        self,
        user_id: str,
        normalized_role: str,
        profile: Any,
        skills: list[Any],
        years: Any,
        cities: list[Any],
    ) -> dict[str, Any] | None:
        """Enrich response with role intelligence data."""
        try:
            from src.rico_agent import RicoProfile

            rico_profile = RicoProfile(
                user_id=user_id,
                skills=skills or [],
                years_experience=years,
                preferred_cities=cities or [],
                industries=self._as_list(self._profile_value(profile, "industries")) or []
            )

            fit_score = score_profile_fit(rico_profile, normalized_role)

            adjacent_roles = []
            if fit_score.overall_score < 0.6:
                adjacent_roles = recommend_adjacent_roles(rico_profile, normalized_role, limit=3)

            if not adjacent_roles:
                return None

            return {
                "normalized_role": normalized_role,
                "fit_score": fit_score.overall_score,
                "adjacent_roles": [
                    {"role": r.canonical_role, "similarity": r.similarity_score, "reason": r.reason}
                    for r in adjacent_roles
                ]
            }
        except Exception as e:
            logger.warning("Role intelligence enrichment failed", extra={"user_id": user_id, "role": normalized_role, "error": str(e)})
            return None

    def _build_role_search_message(
        self,
        normalized_role: str,
        city_text: str,
        basis_text: str,
        top_matches: list[Any],
        role_intelligence_data: dict[str, Any] | None,
        from_saved_profile: bool = False,
    ) -> str:
        """Build message for role search response."""
        if from_saved_profile:
            prefix = f"Searching based on your saved target role: {normalized_role}. "
        else:
            prefix = ""
        if top_matches:
            def _has_url(m: Any) -> bool:
                return bool(
                    m.get("job_apply_link") or m.get("apply_link") or m.get("link")
                )
            link_count = sum(1 for m in top_matches if _has_url(m))
            lead_count = len(top_matches) - link_count
            total = len(top_matches)
            if link_count and lead_count:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {total} candidate match(es) from the job source pipeline "
                    f"({link_count} with provider links, {lead_count} need verification)."
                )
            elif link_count:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {link_count} match(es) with provider data available."
                )
            else:
                base_message = (
                    f"Got it — I will target {normalized_role} roles{city_text}{basis_text}. "
                    f"I found {lead_count} candidate match(es) that need source verification."
                )
        else:
            base_message = f"Got it — I will target {normalized_role} roles{city_text}{basis_text}."

        # Adjacent roles are an OPT-IN offer, never a silent substitution. We always
        # searched the exact requested role (normalized_role); related roles such as
        # "Environmental Officer" for "Environmental Manager" are only ever proposed
        # as a question the user must accept — Rico never broadens on its own.
        _adjacent = (role_intelligence_data or {}).get("adjacent_roles", []) if role_intelligence_data else []
        _adjacent_names = [r["role"] for r in _adjacent[:3] if r.get("role")]
        if not top_matches and _adjacent_names:
            base_message += (
                f" I searched **{normalized_role}** specifically and didn't find live matches. "
                f"Want me to also look at {', '.join(_adjacent_names)}?"
            )
        elif not top_matches:
            base_message += " I couldn't retrieve live jobs right now. I can still suggest target searches based on your CV — or try again later."
        elif _adjacent_names:
            base_message += (
                f" These are **{normalized_role}** roles. If you'd like, I can also look at "
                f"{', '.join(_adjacent_names)} — just say the word."
            )

        return prefix + base_message

    def process_message(
        self,
        user_id: str,
        message: str,
        operation_id: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        debug_id = _generate_debug_id()
        self._current_operation_id = operation_id
        try:
            result = self._process_message_inner(user_id, message, language=language)
            # Guarantee debug_id on every response
            if isinstance(result, dict):
                result.setdefault("debug_id", debug_id)
                message_text = str(result.get("message") or "").strip()
                if not message_text:
                    logger.error(
                        "rico_empty_message_response user=%s type=%s source=%s",
                        user_id,
                        result.get("type", "unknown"),
                        result.get("response_source", "unknown"),
                    )
                    error_response = build_error_response(
                        "Rico could not produce a usable reply for that request. Please rephrase your request or ask a more specific question.",
                        debug_id=debug_id,
                        user_id=user_id,
                    )
                    for key in (
                        "provider",
                        "model",
                        "response_source",
                        "provider_state",
                        "profile_context_present",
                        "jotform_form_id",
                        "fallback_model",
                        "openai_model",
                        "deepseek_model",
                        "error",
                        "error_detail",
                        "is_rate_limited",
                    ):
                        if key in result:
                            error_response[key] = result[key]
                    error_response.setdefault("error", "empty_message")
                    return error_response
                result.setdefault("success", True)
                # Update the canonical last-turn anchor so vague follow-ups
                # ("make sure", "list them", "that one") can resolve reliably.
                self._record_last_turn(user_id, message, result)
            return result
        except Exception as exc:
            if self._current_operation_id:
                mark_failed(user_id, self._current_operation_id, str(exc))
            return build_error_response(
                "Something went wrong processing your message.",
                debug_id=debug_id,
                log_exc=exc,
                user_id=user_id,
            )
        finally:
            self._current_operation_id = None

    def _answer_with_ai_fallback(
        self,
        user_id: str,
        message: str,
        profile: Any,
        *,
        save_user_message: bool,
        language: str | None = None,
        prompt_override: str | None = None,
    ) -> dict[str, Any]:
        """Run the single conversational AI fallback path used by chat routing.

        ``prompt_override`` lets a caller send the model an augmented prompt (e.g.
        with an uploaded document's transcript embedded) while still saving the
        user's ORIGINAL ``message`` to chat history.
        """
        if save_user_message:
            self._append_chat(user_id, "user", message)
        user_context = self._build_openai_context(profile, user_id=user_id)
        blocked_questions = self._get_blocked_questions(profile)
        if isinstance(user_context, dict):
            user_context["blocked_questions"] = blocked_questions

        ai_response = self._get_openai_agent().respond(
            prompt_override or message, user_context=user_context, language=language
        )
        raw_ai_message = ai_response.get("message", "")
        filtered_ai_message = self._preserve_ai_message(raw_ai_message, blocked_questions)
        ai_response["message"] = filtered_ai_message

        if filtered_ai_message:
            self._append_chat(user_id, "assistant", filtered_ai_message)
            # If the AI produced a hollow promise ("ببحث الآن...", "Searching now...") but did
            # not actually fetch jobs, arm the pending-search slot so the user's next
            # confirmation ("تمام"/"ok") triggers _classified_role_search instead of
            # receiving another promise.
            if self._is_promise_only_reply(filtered_ai_message) and profile:
                _promise_roles = self._as_list(self._profile_value(profile, "target_roles"))
                if _promise_roles:
                    self._store_pending_job_search(user_id, role=str(_promise_roles[0]))

        result = self._finalize(
            ai_response,
            self._source_for_openai_response(ai_response),
            profile=profile,
        )
        result.setdefault("success", True)
        return result

    def answer_conversationally(self, user_id: str, message: str, profile: Any, language: str | None = None) -> dict[str, Any]:
        """Route directly to the existing conversational AI fallback path."""
        debug_id = _generate_debug_id()
        try:
            result = self._answer_with_ai_fallback(
                user_id=user_id,
                message=message,
                profile=profile,
                save_user_message=True,
                language=language,
            )
            if isinstance(result, dict):
                result.setdefault("debug_id", debug_id)
                message_text = str(result.get("message") or "").strip()
                if not message_text:
                    logger.error(
                        "rico_empty_message_response user=%s type=%s source=%s",
                        user_id,
                        result.get("type", "unknown"),
                        result.get("response_source", "unknown"),
                    )
                    error_response = build_error_response(
                        "Rico could not produce a usable reply for that request. Please rephrase your request or ask a more specific question.",
                        debug_id=debug_id,
                        user_id=user_id,
                    )
                    for key in (
                        "provider",
                        "model",
                        "response_source",
                        "provider_state",
                        "profile_context_present",
                        "jotform_form_id",
                        "fallback_model",
                        "openai_model",
                        "deepseek_model",
                        "error",
                        "error_detail",
                        "is_rate_limited",
                    ):
                        if key in result:
                            error_response[key] = result[key]
                    error_response.setdefault("error", "empty_message")
                    return error_response
                result.setdefault("success", True)
            return result
        except Exception as exc:
            return build_error_response(
                "Something went wrong processing your message.",
                debug_id=debug_id,
                log_exc=exc,
                user_id=user_id,
            )

    def _process_message_inner(self, user_id: str, message: str, language: str | None = None) -> dict[str, Any]:
        self._append_chat(user_id, "user", message)

        # ── Deterministic My Files listing ────────────────────────────────────
        # "check my uploaded files" / "اعرض الملفات اللي رافعها" must answer from
        # the database in any onboarding state — before the job-search classifier
        # can misread it as a role title and before any AI call.
        file_list_result = self._handle_file_list_query(user_id, message)
        if file_list_result is not None:
            return self._finalize(file_list_result, self.SOURCE_KEYWORD, profile=None)

        # ── Recent-upload document meta-query ─────────────────────────────────
        # "what did I upload?" / "what type is the document?" — answers from the
        # session context (set by the upload route) without an AI call.
        _doc_reply = self._get_recent_upload_document_reply(user_id, message)
        if _doc_reply is not None:
            return self._finalize(_doc_reply, self.SOURCE_KEYWORD, profile=None)

        # ── Recent-upload document ACTION ─────────────────────────────────────
        # "Describe this image" / "Extract key information" / "Summarize this
        # document" — answer from the stored transcript BEFORE the onboarding /
        # CV-builder routing, so an image/document action can never be hijacked
        # into a CV draft. Returns None unless this is such a request.
        _doc_action = self._handle_uploaded_document_followup(user_id, message, language)
        if _doc_action is not None:
            return _doc_action

        completed = is_onboarding_complete(user_id)

        if completed:
            # The minimum-profile gate only fires when the user is requesting job
            # matching.  General chat (greetings, profile queries, application
            # history, etc.) routes directly to _handle_active_user so Rico stays
            # conversational for users with stale-but-partial "completed" rows.
            if self._message_requires_job_profile(message):
                _ctx = self._resolve_profile(user_id)
                _gate_ok, _missing = evaluate_minimum_profile(_ctx)
                if _gate_ok:
                    return self._handle_active_user(user_id, message)
                # Gate failed during a job-search request — downgrade and prompt.
                if getattr(self, "_persist", True):
                    set_onboarding_status(user_id, ONBOARDING_IN_PROGRESS)
                import re as _re
                _is_ar = language == "ar" or bool(_re.search(r'[؀-ۿ]', message))
                _labels_en = {
                    "target_roles": "target role(s)",
                    "preferred_cities": "preferred UAE city/cities",
                    "years_experience": "years of experience",
                    "skills": "key skills (or upload your CV)",
                }
                _labels_ar = {
                    "target_roles": "المسمى الوظيفي المستهدف",
                    "preferred_cities": "المدينة المفضلة بالإمارات",
                    "years_experience": "سنوات الخبرة",
                    "skills": "المهارات الرئيسية (أو ارفع سيرتك الذاتية)",
                }
                if _is_ar:
                    _missing_str = "، ".join(_labels_ar.get(f, f) for f in _missing)
                    _downgrade_msg = (
                        f"لاستكمال ملفك المهني، يرجى مشاركتنا: {_missing_str}. "
                        "يمكنك أيضاً رفع سيرتك الذاتية وسأملأ الملف تلقائياً."
                    )
                else:
                    _missing_str = ", ".join(_labels_en.get(f, f) for f in _missing)
                    _downgrade_msg = (
                        f"To complete your career profile, please share: {_missing_str}. "
                        "You can also upload your CV and I will fill it in automatically."
                    )
                _downgrade_response = {
                    "type": "onboarding",
                    "message": _downgrade_msg,
                    "missing_fields": _missing,
                    "onboarding_status": ONBOARDING_IN_PROGRESS,
                }
                self._append_chat(user_id, "assistant", _downgrade_msg)
                return self._finalize(_downgrade_response, self.SOURCE_KEYWORD, profile=None)
            # Non-job-search message from a completed user — go straight to active flow.
            return self._handle_active_user(user_id, message)

        if self._looks_like_cv_upload(message) and not self._is_job_request_mentioning_cv(message):
            # Check user_documents before showing upload guidance — user may already
            # have a CV on file, or may have uploaded only identity documents.
            _db_check = self._cv_upload_guidance_with_db_check(user_id, message)
            if _db_check is not None:
                return _db_check
            # If the user has announced they have a CV but hasn't attached a file,
            # direct them to the Upload CV button instead of faking a filename.
            if self._looks_like_cv_intent_no_file(message):
                arabic = self._is_arabic_text(message)
                cv_guidance = (
                    "ممتاز! لرفع سيرتك الذاتية استخدم زر **رفع السيرة الذاتية** في الصفحة. "
                    "بعد الرفع سأقرأ السيرة تلقائياً وأملأ ملفك المهني."
                    if arabic else
                    "Use the **Upload CV** button on this page to upload your CV. "
                    "Once uploaded, I will read it automatically and pre-fill your career profile "
                    "with your experience, skills, and target roles — no manual questionnaire needed."
                )
                self._append_chat(user_id, "assistant", cv_guidance)
                return self._finalize(
                    {
                        "type": "cv_upload_guidance",
                        "message": cv_guidance,
                        "next_action": "upload_cv",
                        "options": [
                            {
                                "action": "upload_cv",
                                "label": "رفع السيرة الذاتية" if arabic else "Upload CV",
                                "message": "upload cv",
                            },
                        ],
                    },
                    self.SOURCE_KEYWORD,
                    profile=None,
                )
            mark_onboarding_complete(user_id)
            return self._finalize(
                self._cv_first_profile_response(user_id, message),
                self.SOURCE_KEYWORD,
                profile=None,
            )

        profile = get_profile(user_id)
        if profile is None:
            if getattr(self, "_persist", True):
                upsert_profile(user_id=user_id, updates={})
                set_onboarding_status(user_id, ONBOARDING_IN_PROGRESS)
            import re as _re
            _is_ar = language == "ar" or bool(_re.search(r'[؀-ۿ]', message))
            onboarding_msg = (
                "أهلاً بك في ريكو. أرفع سيرتك الذاتية أو أخبرني بالمسمى الوظيفي الذي تستهدفه "
                "والمدينة التي تفضل العمل فيها بالإمارات وتوقعات راتبك. "
                "عند رفع السيرة الذاتية سأملأ الملف الشخصي تلقائيًا وأسألك فقط عن أي معلومات ناقصة."
                if _is_ar else
                "Welcome to Rico AI. Upload your CV or tell me your target role, UAE city "
                "preferences, and salary expectations. If you upload a CV, I will pre-fill "
                "the profile and only ask for anything missing or unclear."
            )
            response = {"type": "onboarding", "message": onboarding_msg}
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=None)

        mark_onboarding_complete(user_id)
        return self._handle_active_user(user_id, message)

    def _resolve_profile(self, user_id: str):
        """Load and normalise profile into a ProfileContext.

        This is the migration point for #96 — eventually all callers
        will consume ProfileContext directly instead of raw dict/objects.
        """
        raw = get_profile(user_id)
        return resolve_profile_context(user_id, raw)

    def _handle_active_user(self, user_id: str, message: str) -> dict[str, Any]:
        """Intent-first active-user handler.

        Pipeline:
          1. Deterministic follow-up phrases (before role classification)
          2. Classify intent (never defaults to job search)
          3. Route by intent
          4. For role-like text, use 3-tier role classifier
          5. Unknown / nonsense → clarification, not search
        """
        try:
            result = self._handle_active_user_inner(user_id, message)
            # Wire pending job-search: if Rico offered/announced a search this turn
            # but didn't run it, remember it so a follow-up "تمام"/"yes" executes the
            # real search (read side: _get_pending_job_search / _resolve_pending_intent).
            self._maybe_store_pending_job_search(user_id, result)
            # Persist options so the user can reply "A"/"B"/"C"/"D" next turn.
            _options = result.get("options")
            if _options and isinstance(_options, list):
                self._save_pending_options(user_id, _options)
                # 1-A: also surface as clickable chat_continue buttons in agentic_ui
                result = self._inject_option_buttons(result, _options)
            return result
        except Exception:
            logger.exception("rico_routing_error user=%s msg=%r", user_id, message)
            fallback = {
                "type": "clarification",
                "message": (
                    "أنا هنا لمساعدتك في البحث عن وظيفة بالإمارات. "
                    "تقدر تبحث عن وظيفة، ترفع سيرتك الذاتية، تسأل عن طلباتك، "
                    "أو تكتب 'مساعدة' لعرض كل الخيارات."
                    if self._is_arabic_text(message) else
                    "I'm here to help with your UAE job search. "
                    "You can search for a role, upload your CV, ask about your applications, "
                    "or say 'help' for all options."
                ),
            }
            self._append_chat(user_id, "assistant", fallback["message"])
            return self._finalize(fallback, self.SOURCE_KEYWORD, profile=None)

    def _handle_active_user_inner(self, user_id: str, message: str) -> dict[str, Any]:
        """Inner routing — called by _handle_active_user which provides the safe fallback."""
        profile = self._resolve_profile(user_id)
        has_cv = profile.has_cv
        text = self._normalize_followup_phrase(message)

        # ── Pasted CV text detection ──────────────────────────────────────────
        # A user may paste raw CV text instead of uploading a file.  Detect it
        # early so the long blob never reaches the AI provider (avoiding both
        # context-window errors and generic crash responses).
        if self._looks_like_pasted_cv_text(message):
            return self._finalize(
                self._handle_pasted_cv_text(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Pending field resolver (must run first) ───────────────────────────
        # When Rico has just asked the user for a specific profile field (e.g.
        # "What's your Telegram username?"), the raw value the user sends next
        # (like "@Robin_amg") won't match any intent. Intercept it here so the
        # field is saved and a correct confirmation is returned without falling
        # through to the unknown/fallback handler.
        pending_field_result = self._resolve_pending_field(user_id, message, profile)
        if pending_field_result is not None:
            return self._finalize(pending_field_result, self.SOURCE_KEYWORD, profile=profile)

        # ── Letter-choice resolver (BUG-02) ──────────────────────────────────
        # When the last response contained an options list and the user replies
        # with a bare letter A–D (e.g. "A"), map it to the nth option's message
        # and re-route as if the user typed that message.  Strict regex guard
        # (`^[A-Da-d][.:\s]*$`) ensures "apple", "AB", "a b" etc. never match.
        _chosen_msg = self._resolve_letter_choice(user_id, message)
        if _chosen_msg:
            return self._handle_active_user_inner(user_id, _chosen_msg)

        # ── CV builder flow-state follow-up ──────────────────────────────────
        # When Rico has just returned a CV draft (last_flow_state == "cv_builder"),
        # route improvement follow-ups like "please improve it" or Arabic
        # "نعم حسنها بشكل محترف" directly to the deterministic CV handler instead
        # of AI fallback, which may invent achievements, percentages, or placeholders.
        _flow_ctx = self._get_recent_context(user_id)
        if _flow_ctx.get("last_flow_state") == "cv_builder" and _CV_IMPROVE_FOLLOWUP_RE.search(message):
            return self._finalize(
                self._handle_cv_generate_from_profile(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Pending pipeline reset confirmation (P2-B) ───────────────────────
        # Must run before the pipeline reset guard so a confirmation reply in the
        # 2-minute window executes the action instead of re-asking.
        _pending_reset = self._handle_pending_pipeline_reset(user_id, message)
        if _pending_reset is not None:
            return self._finalize(_pending_reset, self.SOURCE_KEYWORD, profile=profile)

        # ── Pending saved-jobs deletion confirmation (P2-B) ──────────────────
        # Must run before the delete guard so a "yes" / "نعم" in the 2-minute
        # confirmation window executes the real deletion instead of re-asking.
        _pending_delete = self._handle_pending_delete_saved_jobs(user_id, message)
        if _pending_delete is not None:
            return self._finalize(_pending_delete, self.SOURCE_KEYWORD, profile=profile)

        # ── Pipeline reset intent (explicit) ──────────────────────────────────
        # "clear all applications", "reset my pipeline", "start over", etc.
        # Fires before role classification to prevent misrouting as a job role.
        if _PIPELINE_RESET_RE.search(message):
            return self._finalize(
                self._handle_pipeline_reset(user_id, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Pipeline reset intent (implicit + context-aware) ──────────────────
        # "clear them", "must start over" — only when last turn was app tracking.
        if _PIPELINE_RESET_IMPLICIT_RE.search(message):
            _last_t = self._get_last_turn(user_id)
            if _last_t.get("intent") == "application_tracking":
                return self._finalize(
                    self._handle_pipeline_reset(user_id, message),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # ── Delete mutation guard (P0 trust bug #764 / P2-B) ─────────────────
        # Saved-jobs → confirmation flow; application history → blocked.
        _delete_guard = self._intercept_unsupported_delete_mutation(user_id, message)
        if _delete_guard is not None:
            return self._finalize(_delete_guard, self.SOURCE_KEYWORD, profile=profile)

        # ── Proactive Telegram declaration: "my telegram is @handle" ─────────
        # When the user volunteers their Telegram handle with the keyword "telegram"
        # in the same message, save it immediately without needing a pending slot.
        _tg_match = TELEGRAM_MENTION_RE.search(message)
        if _tg_match and "telegram" in message.lower():
            _tg_handle = _tg_match.group(1) or _tg_match.group(2)
            if _tg_handle and TELEGRAM_HANDLE_RE.match(_tg_handle):
                upsert_profile(user_id=user_id, updates={"telegram_username": _tg_handle})
                _tg_reply = (
                    f"Got it — I've saved your Telegram username as **{_tg_handle}**. "
                    "You'll receive job alerts and updates there."
                )
                self._append_chat(user_id, "assistant", _tg_reply)
                return self._finalize(
                    {
                        "type": "preferences_updated",
                        "message": _tg_reply,
                        "updated": {"telegram_username": _tg_handle},
                    },
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # ── Manual Application Status: English (before Arabic block for priority) ─
        # Handle English "I applied" / "submitted" / "mark as applied" BEFORE
        # job search classification to prevent "I applied manually" being treated as a job role.
        # Guard: Skip if message looks like an explicit job-card action command (e.g., "Mark as applied — HSE Officer at Acme")
        if not self._is_arabic_text(message) and not _MARK_APPLIED_CARD_ACTION_RE.search(message):
            from src.agent.intelligence.intent_classifier import _is_english_manual_applied_status
            if _is_english_manual_applied_status(message):
                logger.info("rico_manual_applied user=%s msg=%r", user_id, message)
                return self._finalize(
                    self._handle_application_status_update(user_id, message, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # Arabic "I already applied" reports are lifecycle updates, not send/draft
        # requests and not job searches. Catch before the channel follow-up guard,
        # whose broad Arabic "قدم" send verb can otherwise intercept them.
        if self._is_arabic_text(message) and any(
            term in message for term in ("قدم", "تقديم", "التقديم", "ارسل", "أرسل")
        ):
            status_intent = classify_intent(message, has_cv_profile=has_cv)
            if _map_intent_to_legacy(status_intent.intent) == "application_status_update":
                logger.info(
                    "rico_intent user=%s intent=%s legacy_intent=%s confidence=%.2f source=%s",
                    user_id,
                    status_intent.intent,
                    status_intent.legacy_intent,
                    status_intent.confidence,
                    status_intent.source,
                )
                return self._finalize(
                    self._handle_application_status_update(user_id, message, profile),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # ── Settings/Notification Commands ────────────────────────────────────
        # Commands like "enable telegram notifications" must route to settings,
        # not job search (prevent searching for "Telegram Notifications" jobs).
        settings_result = self._resolve_settings_command(user_id, message)
        if settings_result is not None:
            return self._finalize(settings_result, self.SOURCE_KEYWORD, profile=profile)

        # ── Application draft/send channel clarification ─────────────────────
        # Follow-ups like "go ahead", "send it", or Arabic "صيغ رسالة ... وارسلها"
        # must ask for the job when the current request does not identify one,
        # without falling back to recent_context or claiming unsupported send channels.
        explicit_draft_job = self._extract_explicit_draft_job_from_message(message)
        application_channel_result = None
        if not explicit_draft_job:
            application_channel_result = self._handle_application_channel_followup(user_id, message, profile)
        if application_channel_result is not None:
            return self._finalize(application_channel_result, self.SOURCE_KEYWORD, profile=profile)

        # ── CV upload announcement: "i have a cv" / "ill upload it" ─────────────
        # When a user announces a CV without attaching a file, they need to be
        # directed to the Upload CV button. Saying "this chat doesn't support
        # file uploads" is wrong — the platform has a dedicated upload page.
        # This guard runs before any AI call so the user always gets a clear,
        # deterministic direction instead of a questionnaire or false refusal.
        if self._looks_like_cv_intent_no_file(message):
            # Check user_documents first — if a CV already exists, confirm it
            # rather than asking for an upload.
            _db_check = self._cv_upload_guidance_with_db_check(user_id, message, profile=profile)
            if _db_check is not None:
                return _db_check
            arabic = self._is_arabic_text(message)
            if arabic:
                cv_guidance = (
                    "ممتاز! لرفع سيرتك الذاتية استخدم زر **رفع السيرة الذاتية** في الصفحة. "
                    "بعد الرفع سأقرأ السيرة تلقائياً وأملأ ملفك المهني."
                )
            else:
                cv_guidance = (
                    "Use the **Upload CV** button on this page to upload your CV. "
                    "Once uploaded, I will read it automatically and pre-fill your career profile "
                    "with your experience, skills, and target roles — no manual questionnaire needed."
                )
            self._append_chat(user_id, "assistant", cv_guidance)
            return self._finalize(
                {
                    "type": "cv_upload_guidance",
                    "message": cv_guidance,
                    "next_action": "upload_cv",
                    "options": [
                        {
                            "action": "upload_cv",
                            "label": "Upload CV" if not arabic else "رفع السيرة الذاتية",
                            "message": "upload cv",
                        },
                    ],
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Explicit "show my applications" guard ────────────────────────────────
        # "show my applications", "my applications", "اعرض طلباتي", "طلباتي", etc.
        # are direct intents — route to application_tracking without requiring a
        # prior lifecycle context (which the list-followup block would need).
        if RicoChatAPI._SHOW_MY_APPLICATIONS_RE.match(text):
            return self._finalize(
                self._handle_application_tracking(user_id, intent="application_tracking", message=message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Direct reminder commands ─────────────────────────────────────────────
        # "Set a follow-up reminder for Penspen", "Remind me to follow up", etc.
        # These come from UI suggestion buttons and must be caught before role
        # classification interprets them as job-title queries.
        if RicoChatAPI._SET_REMINDER_RE.search(message):
            # Extract company/job name from "for <name>" or "with <name>" suffix.
            _company_match = re.search(r"\b(?:for|with)\s+(.+)$", message, re.IGNORECASE)
            _company = _company_match.group(1).strip() if _company_match else None
            if _company:
                reply = (
                    f"Reminder set for **{_company}**. "
                    "I'll nudge you to follow up in 7 days if you haven't heard back."
                )
            else:
                reply = (
                    "Reminder set. I'll nudge you to follow up in 7 days "
                    "if you haven't heard back from your latest application."
                )
            self._append_chat(user_id, "assistant", reply)
            return self._finalize(
                {"type": "reminder_set", "message": reply},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Lifecycle list follow-up: "list them" / "show them" / "اذكرهم" ───────
        # Must run before the affirmative resolver so short list-commands don't
        # fall through to the AI and crash on ambiguous short input.
        if self._is_list_followup(message):
            last_query = self._resolve_lifecycle_query_for_followup(user_id)
            if last_query:
                return self._finalize(
                    self._handle_lifecycle_query(user_id, last_query, message=message),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            # "list them" after a job search — replay the cached recent_search_matches.
            ctx = self._get_recent_context(user_id)
            cached_matches = ctx.get("recent_search_matches") or []
            if cached_matches:
                lines = []
                for i, m in enumerate(cached_matches, 1):
                    title = m.get("title", "")
                    company = m.get("company", "")
                    loc = m.get("location", "")
                    link = m.get("apply_url", "") or m.get("source_url", "")
                    loc_part = f" · {loc}" if loc else ""
                    link_part = f" — [Apply]({link})" if link else ""
                    lines.append(f"{i}. **{title}** at **{company}**{loc_part}{link_part}")
                role_hint = ctx.get("recent_search_role") or ctx.get("recent_role") or ctx.get("recent_job") or "your last search"
                msg = f"Here are the results from {role_hint}:\n\n" + "\n".join(lines)
                return self._finalize(
                    {"type": "job_matches", "message": msg, "jobs": cached_matches},
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            # Nothing to list yet — give a clear prompt instead of falling to AI.
            return self._finalize(
                {
                    "type": "clarification",
                    "message": (
                        "I don't have a recent search or list to show you yet. "
                        "Try: 'find jobs for Environmental Compliance Officer in Dubai' "
                        "or 'show my saved jobs'."
                    ),
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Verify / "make sure" follow-up: re-confirm the last real turn ───────
        # Without this, "make sure please" after an applied-jobs reply gets
        # classified as a bare job role. Anchor it to the last_turn instead.
        if self._is_verify_followup(message):
            verified = self._resolve_verify_followup(user_id, profile, message=message)
            if verified is not None:
                return self._finalize(verified, self.SOURCE_KEYWORD, profile=profile)
            # Memory miss (e.g. multi-worker Render) — acknowledge without crashing.
            return self._finalize(
                {
                    "type": "clarification",
                    "message": (
                        "لست متأكدًا من النتيجة التي تريد أن أتحقق منها مرة أخرى. "
                        "هل يمكنك إخباري بما تريد أن أتحقق منه؟"
                        if self._is_arabic_text(message) else
                        "I'm not sure which result you'd like me to double-check. "
                        "Could you tell me what you'd like me to verify?"
                    ),
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Pending-intent resolver: yes/no after Rico's question ──────────────
        # Must run before generic routing so "نعم" / "كمل" / "keep going" resolves
        # the last offered action instead of falling through to role classification.
        if self._is_affirmative(message) or self._is_continuation_intent(message):
            pending = self._resolve_pending_intent(user_id, message, profile)
            if pending is not None:
                return self._finalize(pending, self.SOURCE_KEYWORD, profile=profile)
            # Continuation with no specific pending offer: if CV exists, proceed with
            # the best known role; otherwise ask for one.
            if self._is_continuation_intent(message):
                return self._finalize(
                    self._handle_post_cv_continuation(user_id, profile, message),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
        # ── "Yes, search {role}" quick-reply button handler ──────────────────────
        # The quick-reply button generated by known_but_off_profile sends the
        # label "Yes, search {role}" verbatim.  _is_affirmative() only matches
        # single-word phrases, so the button click falls through to role
        # extraction, re-triggers the same known_but_off_profile classification,
        # and shows the confirmation prompt again — an infinite loop (BUG-05).
        # Intercept here before role classification fires.
        _yes_search_m = re.match(r'^yes[,\s]+search\s+(.+)$', (message or "").strip(), re.IGNORECASE)
        if _yes_search_m:
            try:
                _ctx_ys = self._get_recent_context(user_id)
                _pend_ys = _ctx_ys.get("_pending_role_confirmation")
                if _pend_ys and _pend_ys.get("role"):
                    _role_ys = _pend_ys["role"]
                    _ctx_ys.pop("_pending_role_confirmation", None)
                    self._store_recent_context(user_id, _ctx_ys)
                    self._clear_pending_job_search(user_id)
                    return self._finalize(
                        self._target_role_search_response(user_id, _role_ys, profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass

        if self._is_negative(message):
            # User declined the offered action — acknowledge and let them continue
            return self._finalize(
                {"type": "clarification", "message": "حسناً، أخبرني بما تريد فعله." if any(ord(c) > 127 for c in message) else "Got it. What would you like to do instead?"},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Acknowledgement early check (must be before next-step followup fast path) ──
        # Phrases like "ok", "great", "thanks" are also in _FOLLOWUP_NEXT_STEP_PHRASES
        # and _AFFIRMATIVE_PHRASES. If no pending intent was resolved above, treat
        # them as acknowledgements and return a short warm reply immediately.
        _msg_lower = message.strip().lower()
        if _msg_lower in _ACKNOWLEDGEMENT_REPLIES:
            # Before emitting a static ack, honour any pending job search. Arabic short
            # confirmations like "تمام" (fine/ok) are in _ACKNOWLEDGEMENT_REPLIES but also
            # used to confirm a search Rico promised in the previous turn. These phrases
            # never reach _is_affirmative or the follow_up_confirmation dispatch, so the
            # pending search check must live here.
            _ack_pending_js = self._get_pending_job_search(user_id)
            if _ack_pending_js and _ack_pending_js.get("role"):
                _ack_role = _ack_pending_js["role"]
                _ack_loc = _ack_pending_js.get("location", "")
                self._clear_pending_job_search(user_id)
                return self._finalize(
                    self._classified_role_search(user_id, _ack_role, profile, location=_ack_loc),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            ack_text = _acknowledgement_reply(message)
            response = {"type": "acknowledgement", "message": ack_text}
            self._append_chat(user_id, "assistant", ack_text)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # ── Deterministic follow-up phrases (must be before role classification) ──
        if text in self._FOLLOWUP_KEEP_ALL_PHRASES:
            return self._finalize(
                self._handle_keep_all_target_roles(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        if text in self._FOLLOWUP_BOTH_ACTION_PHRASES:
            return self._finalize(
                self._handle_both_requested_actions(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        logger.info(
            "rico_followup_check user=%s has_cv=%s msg=%r followup=%s",
            user_id, has_cv, message, self._looks_like_next_step_followup(message),
        )

        # Fast path: short follow-up after role confirmation → instant options
        if has_cv and (
            self._looks_like_next_step_followup(message)
            or self._is_arabic_what_now(message)
        ):
            logger.info("rico_followup_hit user=%s msg=%r", user_id, message)
            return self._finalize(
                self._handle_next_step_options(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Fast path: user selected a suggested role → deterministic confirmation
        if has_cv and not self._is_live_job_search_request(message):
            if self._looks_like_selected_role(message, profile):
                return self._finalize(
                    self._handle_role_confirmation(
                        user_id=user_id,
                        role=self._extract_selected_role(message, profile),
                        profile=profile,
                        message=message,
                    ),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # Generic job request with CV and no established target roles → suggest CV-based roles
        # When target roles are already set, skip to intent classification so run_for_profile fires
        _profile_target_roles = self._effective_target_roles(
            self._as_list(self._profile_value(profile, "target_roles"))
        )
        if (
            has_cv
            and not _profile_target_roles
            and not self._is_live_job_search_request(message)
            and self._looks_like_generic_job_request(message)
        ):
            return self._finalize(
                self._handle_profile_role_suggestions(profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── UAE-wide search expansion ─────────────────────────────────────────
        # "look all over UAE", "search all UAE", "all over UAE" — expand a
        # previous role search to the whole country or ask for a role.
        if _UAE_WIDE_SEARCH_RE.search(message):
            _prior_role_uae = ""
            try:
                _rctx = self._get_recent_context(user_id)
                _ctx_role = _rctx.get("recent_search_role") or _rctx.get("recent_role") or ""
                if isinstance(_ctx_role, str) and _ctx_role.strip():
                    _prior_role_uae = _ctx_role.strip()
            except Exception:
                pass
            if not _prior_role_uae:
                _tgt_uae = self._effective_target_roles(
                    self._as_list(self._profile_value(profile, "target_roles"))
                )
                _prior_role_uae = str(_tgt_uae[0]).strip() if _tgt_uae else ""
            if _prior_role_uae:
                return self._finalize(
                    self._target_role_search_response(
                        user_id, _prior_role_uae, profile, location="UAE"
                    ),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            _uae_clarify = "I can search across the UAE. Which role should I search for?"
            self._append_chat(user_id, "assistant", _uae_clarify)
            return self._finalize(
                {"type": "clarification", "message": _uae_clarify},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Cover letter command ──────────────────────────────────────────────
        # "make me a cover [letter]", "write a cover letter", "draft a cover letter"
        # The intent classifier returns "unknown" for bare "make me a cover", so
        # route deterministically here before classify_intent runs.
        # Exception: if the message already contains explicit job context (company/role),
        # skip and let the draft_message intent handler extract and use that context.
        if _COVER_LETTER_COMMAND_RE.search(message) and not self._extract_explicit_draft_job_from_message(message) and not _RESIGNATION_LETTER_RE.search(message):
            # If there's a cached job from a recent search, use it as context so the
            # cover letter is tailored to that specific role instead of asking the user.
            _cached_job: dict[str, Any] = {}
            try:
                _cl_ctx = self._get_recent_context(user_id)
                _cl_matches = _cl_ctx.get("recent_search_matches") or []
                if isinstance(_cl_matches, list) and _cl_matches:
                    _cached_job = _cl_matches[0]
            except Exception:
                pass
            if _cached_job and _cached_job.get("title"):
                _cl_role    = _cached_job.get("title", "")
                _cl_company = _cached_job.get("company", "")
                _cl_desc    = (_cached_job.get("description") or "")[:300]
                _cl_augmented = (
                    f"{message}\n\n"
                    f"[Job context: {_cl_role}"
                    + (f" at {_cl_company}" if _cl_company else "")
                    + (f". Description: {_cl_desc}" if _cl_desc else "")
                    + "]"
                )
                return self._answer_with_ai_fallback(
                    user_id=user_id,
                    message=_cl_augmented,
                    profile=profile,
                    save_user_message=False,
                )
            _cl_msg = self._cover_letter_clarification_message(profile)
            self._append_chat(user_id, "assistant", _cl_msg)
            return self._finalize(
                {
                    "type": "cover_letter_prompt",
                    "message": _cl_msg,
                    "next_action": "provide_job_for_cover_letter",
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Retry last search ─────────────────────────────────────────────
        # "again", "retry", "same search" — replay the most recent job search.
        if _RETRY_SEARCH_RE.search(message):
            _retry_role = _retry_loc = ""
            try:
                _rctx = self._get_recent_context(user_id)
                _retry_role = str(_rctx.get("recent_search_role") or "").strip()
                _retry_loc  = str(_rctx.get("recent_search_location") or "").strip()
            except Exception:
                pass
            if not _retry_role:
                _tgt_r = self._effective_target_roles(
                    self._as_list(self._profile_value(profile, "target_roles"))
                )
                _retry_role = str(_tgt_r[0]).strip() if _tgt_r else ""
            if _retry_role:
                return self._finalize(
                    self._target_role_search_response(
                        user_id, _retry_role, profile,
                        location=_retry_loc or None,
                    ),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            _retry_ask = "What role should I search for? Tell me a job title and I'll run the search."
            self._append_chat(user_id, "assistant", _retry_ask)
            return self._finalize(
                {"type": "clarification", "message": _retry_ask},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Application withdrawal ─────────────────────────────────────────
        # "withdraw my application", "cancel my application" — update status
        # in DB and confirm, or guide to Applications tab if no context.
        if _APPLICATION_WITHDRAW_RE.search(message):
            _wd_ctx = {}
            try:
                _wd_ctx = self._get_recent_context(user_id)
            except Exception:
                pass
            _wd_title   = str(_wd_ctx.get("recent_job") or "").strip()
            _wd_company = str(_wd_ctx.get("recent_company") or "").strip()
            _wd_job_key = str(_wd_ctx.get("recent_job_key") or "").strip()
            if _wd_title and _wd_job_key:
                try:
                    from src.repositories import applications_repo
                    applications_repo.update_status(
                        job={"job_id": _wd_job_key, "title": _wd_title, "company": _wd_company},
                        status="withdrawn",
                        user_id=user_id,
                    )
                    _wd_msg = (
                        f"Done — your application for **{_wd_title}**"
                        f"{f' at {_wd_company}' if _wd_company else ''} "
                        "has been marked as withdrawn."
                    )
                except Exception:
                    _wd_msg = (
                        f"I've noted that you'd like to withdraw your application for "
                        f"**{_wd_title}**{f' at {_wd_company}' if _wd_company else ''}. "
                        "Please confirm this in your Applications tab."
                    )
            else:
                _wd_msg = (
                    "أي طلب تريد سحبه؟ ذكر لي اسم الوظيفة أو الشركة، أو راجع تبويب 'الطلبات' مباشرةً."
                    if self._is_arabic_text(message) else
                    "Which application would you like to withdraw? "
                    "Tell me the job title or company name, or go to your Applications tab."
                )
            self._append_chat(user_id, "assistant", _wd_msg)
            return self._finalize(
                {
                    "type": "application_withdrawn" if (_wd_title and _wd_job_key) else "clarification",
                    "message": _wd_msg,
                },
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Application status query ─────────────────────────────────────────
        # "any updates on my applications?" / "has anyone replied?" routes to
        # application_tracking (show status list), not application_status_update
        # (which is the "I applied" reporting path).
        if _APPLICATION_STATUS_QUERY_RE.search(message):
            return self._finalize(
                self._handle_application_tracking(user_id, intent=None, message=message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Profile completeness check ────────────────────────────────────────
        # "what's missing from my profile?" / "is my profile complete?" → deterministic
        # completeness report using evaluate_minimum_profile, with optional field hints.
        if _PROFILE_COMPLETE_RE.search(message):
            return self._finalize(
                self._handle_profile_completeness(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Salary expectation setting ─────────────────────────────────────────
        # "my minimum salary is 50k", "set salary to 60,000 AED" → parse number,
        # save to profile, return field-specific confirmation.
        if _SALARY_SET_RE.search(message):
            return self._finalize(
                self._handle_salary_set(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Salary expectation readback ───────────────────────────────────────
        # "what salary did I set?", "what's my expected salary?" → return saved
        # salary_expectation_aed from profile; distinct from _SALARY_SET_RE.
        if _SALARY_READBACK_RE.search(message):
            return self._finalize(
                self._handle_salary_readback(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Job detail / ordinal job selection ───────────────────────────────
        # "tell me more about that job" → first cached match.
        # "tell me more about the second job", "job number 2", "the third one"
        # → Nth cached match. Ordinal extraction runs inside this gate so that
        # "tell me more about the second job" is not blocked by _JOB_DETAIL_RE
        # returning match[0] before the ordinal gate fires.
        # Comparison queries ("compare job 1 and job 2") also trigger _ORDINAL_JOB_RE
        # via "job 1" — skip here so _JOB_COMPARE_RE can handle them downstream.
        # Apply-link requests ("open the apply link for the second job") also contain
        # an ordinal ("second job") but must NOT be treated as a job-detail lookup —
        # they belong to the open_apply_link handler. Skip the gate for them so the
        # ordinal apply-link works for every position, not just "first".
        # Save requests ("save the second job to my pipeline") also contain an
        # ordinal but belong to the save_job handler — skip the gate for them too.
        _jd_detail_match = _JOB_DETAIL_RE.search(message)
        _jd_ordinal_match = _ORDINAL_JOB_RE.search(message)
        _jd_is_apply_link = bool(
            _OPEN_APPLY_LINK_ORDINAL_RE.search(message)
            or _OPEN_APPLY_LINK_RE.search(message)
        )
        _jd_is_save = bool(
            _SAVE_JOB_ORDINAL_RE.search(message)
            or _SAVE_JOB_ORDINAL_AR_RE.search(message)
        )
        if (
            (_jd_detail_match or _jd_ordinal_match)
            and not _JOB_COMPARE_RE.search(message)
            and not _jd_is_apply_link
            and not _jd_is_save
        ):
            _ord_hint = ""
            if _jd_ordinal_match:
                _ord_hint = (
                    _jd_ordinal_match.group("n")
                    or _jd_ordinal_match.group("n2")
                    or _jd_ordinal_match.group("n3")
                    or ""
                ).strip()
            return self._finalize(
                self._handle_job_detail(user_id, profile, message, ordinal_hint=_ord_hint),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Profile pitch/bio ─────────────────────────────────────────────────
        # "write me a professional bio", "summarize my profile for an employer"
        # → deterministic pitch built from profile fields; no AI token spend.
        if _PROFILE_PITCH_RE.search(message):
            return self._finalize(
                self._handle_profile_pitch(user_id, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Application list query ────────────────────────────────────────────
        # ── Application pipeline summary ──────────────────────────────────────
        # Must come before _APPLICATIONS_LIST_RE: "how many applications have I
        # sent?" matches both, but pipeline summary gives stats, not a list.
        if _APP_PIPELINE_SUMMARY_RE.search(message):
            return self._finalize(
                self._handle_app_pipeline_summary(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # "what jobs did I apply to?", "how many applications do I have?",
        # "show my applied jobs", "application history" — patterns NOT covered
        # by the earlier _SHOW_MY_APPLICATIONS_RE guard (which handles the
        # short "show/list my applications" commands routed to the tracker UI).
        if _APPLICATIONS_LIST_RE.search(message):
            return self._finalize(
                self._handle_applications_list(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Profile data readback ─────────────────────────────────────────────
        # "what skills do you have for me?", "what do you know about me?"
        # → show profile fields as formatted summary; distinct from pitch generator.
        if _PROFILE_READBACK_RE.search(message):
            return self._finalize(
                self._handle_profile_readback(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Profile field update ──────────────────────────────────────────────
        # "add Python to my skills", "remove OSHA from my skills",
        # "update my experience to 8 years", "I'm now based in Abu Dhabi",
        # "change my target role to HSE Manager".
        if _PROFILE_FIELD_UPDATE_RE.search(message):
            return self._finalize(
                self._handle_profile_field_update(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Application-specific lookup ───────────────────────────────────────
        # "did I apply to Emirates?", "status of my ADNOC application",
        # "when did I apply to Carrefour?".
        if _APP_SPECIFIC_LOOKUP_RE.search(message):
            return self._finalize(
                self._handle_app_specific_lookup(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Cover letter with explicit job context (BUG-01 guard) ───────────────
        # Must come BEFORE _COMPANY_SEARCH_RE: "role at [Company]" in a cover-letter
        # prompt ("Draft me a cover letter for the HSE MANAGER role at Dutco Group")
        # matches _COMPANY_SEARCH_RE pattern-2, routing to job search instead of
        # cover letter generation. When the cover letter command is present AND slots
        # are fully extractable, generate the letter deterministically here.
        if _COVER_LETTER_COMMAND_RE.search(message) and not _RESIGNATION_LETTER_RE.search(message):
            _cl_ej = self._extract_explicit_draft_job_from_message(message)
            if _cl_ej:
                from src.message_generator import generate_message as _gen_msg
                _cl_draft_job, _cl_ctx_src = self._resolve_explicit_draft_job_context(user_id, _cl_ej)
                if (
                    self._job_context_value(_cl_draft_job, "title", "job_title")
                    and self._job_context_value(_cl_draft_job, "company", "company_name")
                ):
                    self._log_document_draft_context_source(_cl_ctx_src, _cl_draft_job)
                    cover = _gen_msg(_cl_draft_job, profile=profile)
                    self._append_chat(user_id, "assistant", cover)
                    return self._finalize(
                        {"type": "draft_message", "intent": "draft_message", "message": cover},
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                _cl_msg = self._cover_letter_clarification_message(profile, _cl_draft_job)
                self._append_chat(user_id, "assistant", _cl_msg)
                return self._finalize(
                    {"type": "cover_letter_prompt", "message": _cl_msg, "next_action": "provide_job_for_cover_letter"},
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # ── Company-targeted job search ───────────────────────────────────────
        # "find jobs at ADNOC", "jobs at Emirates NBD", "any openings at DEWA".
        if _COMPANY_SEARCH_RE.search(message) and not _COVER_LETTER_COMMAND_RE.search(message):
            return self._finalize(
                self._handle_company_search(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Salary-filtered job search ────────────────────────────────────────
        # "find HSE jobs paying above 20k AED", "roles with salary minimum 25000".
        # Fires BEFORE generic intent so the salary constraint is honoured.
        if _SALARY_SEARCH_RE.search(message):
            return self._finalize(
                self._handle_salary_filtered_search(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Employment-type filter ────────────────────────────────────────────
        # "find remote HSE jobs", "contract QHSE roles", "part-time positions".
        if _EMPLOYMENT_TYPE_RE.search(message):
            return self._finalize(
                self._handle_employment_type_search(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Follow-up timing advice ───────────────────────────────────────────
        # "when should I follow up?", "is it too early to follow up?",
        # "how many days before following up?".
        if _FOLLOWUP_TIMING_RE.search(message):
            return self._finalize(
                self._handle_followup_timing(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Certification / qualification advice ──────────────────────────────
        # Must come before industry search: "required qualifications for finance"
        # overlaps with industry keywords but is advice, not a job search request.
        if _CERTIFICATION_ADVICE_RE.search(message):
            return self._finalize(
                self._handle_certification_advice(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Industry-based job search ─────────────────────────────────────────
        # "find jobs in oil and gas", "construction sector jobs in Dubai".
        if _INDUSTRY_SEARCH_RE.search(message):
            return self._finalize(
                self._handle_industry_search(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Job comparison ────────────────────────────────────────────────────
        # "compare job 1 and job 2", "which is better, job 1 or 3?".
        if _JOB_COMPARE_RE.search(message):
            return self._finalize(
                self._handle_job_comparison(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Search result count ───────────────────────────────────────────────
        # "how many jobs did you find?", "total number of results".
        if _RESULT_COUNT_RE.search(message):
            return self._finalize(
                self._handle_result_count(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Seniority-filtered search ─────────────────────────────────────────
        # "find senior HSE jobs", "entry level QHSE positions", "manager-level roles".
        if _SENIORITY_SEARCH_RE.search(message):
            return self._finalize(
                self._handle_seniority_search(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Job market pulse ──────────────────────────────────────────────────
        # "how's the job market for HSE?", "are there many construction jobs?".
        if _MARKET_PULSE_RE.search(message):
            return self._finalize(
                self._handle_market_pulse(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Notice period / availability ──────────────────────────────────────
        # "my notice period is 30 days", "I'm available immediately".
        if _NOTICE_PERIOD_RE.search(message):
            return self._finalize(
                self._handle_notice_period(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Visa / work permit status ─────────────────────────────────────────
        # "I'm on a spouse visa", "do I need a work permit?".
        if _VISA_STATUS_RE.search(message) and not _GOLDEN_VISA_RE.search(message) and not _WORK_VISA_PROCESS_RE.search(message) and not _VISA_CANCELLATION_RE.search(message):
            return self._finalize(
                self._handle_visa_status(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Salary negotiation advice ─────────────────────────────────────────
        # "how do I negotiate my salary?", "should I counter the offer?".
        if _SALARY_NEGOTIATION_RE.search(message) and not _COUNTER_OFFER_RE.search(message):
            return self._finalize(
                self._handle_salary_negotiation(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Interview preparation advice ──────────────────────────────────────
        # "how do I prepare for an interview?", "common HSE interview questions".
        if _INTERVIEW_PREP_RE.search(message) and not _DRESS_CODE_RE.search(message):
            return self._finalize(
                self._handle_interview_prep(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Job rejection / no-response handling ──────────────────────────────
        # "I got rejected", "haven't heard back", "what to do after rejection?".
        if _REJECTION_HANDLING_RE.search(message) and not _JOB_REJECTION_RE.search(message):
            return self._finalize(
                self._handle_rejection(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── LinkedIn / networking advice ──────────────────────────────────────
        # "how to use LinkedIn?", "should I message the recruiter?".
        if _LINKEDIN_NETWORKING_RE.search(message) and not _NETWORKING_UAE_RE.search(message):
            return self._finalize(
                self._handle_linkedin_networking(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── CV format advice ──────────────────────────────────────────────────
        # "how should I format my CV for UAE?", "ATS-friendly CV tips".
        if _CV_FORMAT_RE.search(message):
            return self._finalize(
                self._handle_cv_format_advice(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Cover letter tips ─────────────────────────────────────────────────
        # "how do I write a cover letter?", "do I need a cover letter?".
        if _COVER_LETTER_TIPS_RE.search(message):
            return self._finalize(
                self._handle_cover_letter_tips(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Profile improvement / completeness ────────────────────────────────
        # "how can I improve my profile?", "what's missing from my CV?".
        if _PROFILE_IMPROVE_RE.search(message):
            return self._finalize(
                self._handle_profile_completeness(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Company-type / sector-type job search ─────────────────────────────
        # "find government jobs", "find startup jobs in UAE".
        if _COMPANY_TYPE_SEARCH_RE.search(message):
            return self._finalize(
                self._handle_company_type_search(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Urgency-framed job search ─────────────────────────────────────────
        # "I need a job urgently", "help me find a job fast".
        if _URGENCY_SEARCH_RE.search(message):
            return self._finalize(
                self._handle_urgency_search(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Salary benchmark ──────────────────────────────────────────────────
        # "what does an HSE Manager earn?", "how much do PMs make in Dubai?".
        if _SALARY_BENCHMARK_RE.search(message):
            return self._finalize(
                self._handle_salary_benchmark(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Career change / transition advice ────────────────────────────────
        # "I want to switch careers", "how do I transition to project management?".
        # Exclude UAE relocation messages ("move to Dubai") which share "move" vocabulary.
        if _CAREER_CHANGE_RE.search(message) and not _RELOCATION_UAE_RE.search(message):
            return self._finalize(
                self._handle_career_change(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Best employers / top companies query ─────────────────────────────
        # "which companies hire HSE managers?", "best employers in Dubai".
        if _BEST_EMPLOYERS_RE.search(message):
            return self._finalize(
                self._handle_best_employers(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── UAE job search tips / strategy ────────────────────────────────────
        # "how do I find a job in UAE?", "best job boards", "tips for job hunting".
        if _JOB_SEARCH_TIPS_RE.search(message):
            return self._finalize(
                self._handle_job_search_tips(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── UAE benefits / package query ──────────────────────────────────────
        # "what benefits should I expect?", "is housing allowance standard?".
        if _BENEFITS_QUERY_RE.search(message) and not _EOSB_RE.search(message) and not _ANNUAL_LEAVE_RE.search(message) and not _EMPLOYER_HEALTH_INSURANCE_RE.search(message):
            return self._finalize(
                self._handle_benefits_package(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Offer evaluation ──────────────────────────────────────────────────
        # "should I accept this offer?", "how to evaluate a job offer".
        if _OFFER_EVAL_RE.search(message):
            return self._finalize(
                self._handle_offer_evaluation(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── UAE labor law / probation info ────────────────────────────────────
        # "what is the probation period?", "UAE labor law", "termination rights".
        if _UAE_LABOR_LAW_RE.search(message) and not _PROBATION_RULES_RE.search(message) and not _CONTRACT_TYPES_UAE_RE.search(message) and not _OVERTIME_PAY_UAE_RE.search(message) and not _REDUNDANCY_UAE_RE.search(message) and not _WORKPLACE_HARASSMENT_RE.search(message):
            return self._finalize(
                self._handle_uae_labor_law(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Post-interview thank you email ────────────────────────────────────
        # "should I send a thank you after the interview?", "how to write a thank you email".
        if _POST_INTERVIEW_EMAIL_RE.search(message):
            return self._finalize(
                self._handle_post_interview_email(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Skill gap assessment ──────────────────────────────────────────────
        # "what skills am I missing?", "am I qualified for senior role?".
        if _SKILL_GAP_RE.search(message) and not _GOLDEN_VISA_RE.search(message) and not _EOSB_RE.search(message):
            return self._finalize(
                self._handle_skill_gap(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── LinkedIn profile optimisation ─────────────────────────────────────
        # Unique patterns not covered by _LINKEDIN_NETWORKING_RE:
        # "how do I improve my LinkedIn?", "should I use LinkedIn?",
        # "is LinkedIn useful in UAE?", "LinkedIn headline tips".
        if _LINKEDIN_TIPS_RE.search(message):
            return self._finalize(
                self._handle_linkedin_tips(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Resignation letter ────────────────────────────────────────────────
        # "how do I write a resignation letter?", "how to resign professionally".
        if _RESIGNATION_LETTER_RE.search(message):
            return self._finalize(
                self._handle_resignation_letter(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Relocation to UAE ─────────────────────────────────────────────────
        # "how do I move to Dubai for work?", "relocating to UAE guide".
        if _RELOCATION_UAE_RE.search(message):
            return self._finalize(
                self._handle_relocation_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Applying from abroad ──────────────────────────────────────────────
        # "can I apply for UAE jobs from abroad?", "do I need to be in UAE?".
        if _APPLY_FROM_ABROAD_RE.search(message):
            return self._finalize(
                self._handle_apply_from_abroad(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Employment gap ───────────────────────────────────────────────────
        # "how do I explain a gap in my CV?", "I have a career gap".
        if _EMPLOYMENT_GAP_RE.search(message):
            return self._finalize(
                self._handle_employment_gap(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Company research ─────────────────────────────────────────────────
        # "how do I research a company before an interview?".
        if _COMPANY_RESEARCH_RE.search(message):
            return self._finalize(
                self._handle_company_research(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Freelance / self-employment in UAE ───────────────────────────────
        # "can I freelance in UAE?", "how do I get a freelance permit?".
        if _FREELANCE_UAE_RE.search(message):
            return self._finalize(
                self._handle_freelance_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── End of service gratuity ──────────────────────────────────────────
        # "what is end of service gratuity?", "how is gratuity calculated?".
        if _EOSB_RE.search(message):
            return self._finalize(
                self._handle_eosb(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Non-compete clause ───────────────────────────────────────────────
        # "does my non-compete apply in UAE?", "is a non-compete enforceable?".
        if _NON_COMPETE_RE.search(message):
            return self._finalize(
                self._handle_non_compete(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Work visa / sponsorship process ─────────────────────────────────
        # "how do I get a UAE work visa?", "will the company sponsor my visa?".
        if _WORK_VISA_PROCESS_RE.search(message):
            return self._finalize(
                self._handle_work_visa_process(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Arabic language requirement ───────────────────────────────────────
        # "do I need to speak Arabic?", "will not speaking Arabic hurt my chances?".
        if _ARABIC_REQUIREMENT_RE.search(message):
            return self._finalize(
                self._handle_arabic_requirement(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Background check / police clearance ──────────────────────────────
        # "will they do a background check?", "do I need a police clearance?".
        if _BACKGROUND_CHECK_RE.search(message):
            return self._finalize(
                self._handle_background_check(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Free zone vs mainland ─────────────────────────────────────────────
        # "what is the difference between free zone and mainland?".
        if _FREE_ZONE_MAINLAND_RE.search(message):
            return self._finalize(
                self._handle_free_zone_mainland(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Working hours / overtime ──────────────────────────────────────────
        # "what are the working hours in UAE?", "is overtime paid?".
        if _WORKING_HOURS_RE.search(message) and not _OVERTIME_PAY_UAE_RE.search(message):
            return self._finalize(
                self._handle_working_hours(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── UAE Golden Visa ───────────────────────────────────────────────────
        # "what is the golden visa?", "how do I get a UAE golden visa?".
        if _GOLDEN_VISA_RE.search(message):
            return self._finalize(
                self._handle_golden_visa(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Professional references ───────────────────────────────────────────
        # "how do I ask for a reference?", "who should I use as a reference?".
        if _JOB_REFERENCES_RE.search(message):
            return self._finalize(
                self._handle_job_references(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Interview / office dress code ────────────────────────────────────
        # "what should I wear to an interview?", "what is the dress code in UAE?".
        if _DRESS_CODE_RE.search(message):
            return self._finalize(
                self._handle_dress_code(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Remote work from UAE ──────────────────────────────────────────────
        # "can I work remotely from UAE?", "do I need a visa to work remote?".
        if _REMOTE_WORK_UAE_RE.search(message):
            return self._finalize(
                self._handle_remote_work_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Annual leave entitlement ──────────────────────────────────────────
        # "how many days annual leave in UAE?", "public holidays UAE".
        if _ANNUAL_LEAVE_RE.search(message) and not _PUBLIC_HOLIDAYS_UAE_RE.search(message):
            return self._finalize(
                self._handle_annual_leave(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Sick leave ────────────────────────────────────────────────────────
        # "how many sick days do I get?", "sick leave policy UAE".
        if _SICK_LEAVE_RE.search(message):
            return self._finalize(
                self._handle_sick_leave(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Maternity / paternity leave ───────────────────────────────────────
        # "how much maternity leave in UAE?", "paternity leave paid?".
        if _PARENTAL_LEAVE_RE.search(message):
            return self._finalize(
                self._handle_parental_leave(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Probation period rules ────────────────────────────────────────────
        # "what happens during probation?", "can I be fired during probation?".
        if _PROBATION_RULES_RE.search(message):
            return self._finalize(
                self._handle_probation_rules(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Termination notice period ─────────────────────────────────────────
        # "how much notice do I need to give?", "notice period UAE".
        if _NOTICE_PERIOD_RE.search(message):
            return self._finalize(
                self._handle_notice_period(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Wage Protection System / late salary ──────────────────────────────
        # "what is WPS?", "my salary is late", "how to report late salary UAE".
        if _WPS_SALARY_PROTECTION_RE.search(message):
            return self._finalize(
                self._handle_wps_salary_protection(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Employer health insurance ─────────────────────────────────────────
        # "do I get health insurance from my employer?", "is medical insurance mandatory UAE?".
        if _EMPLOYER_HEALTH_INSURANCE_RE.search(message):
            return self._finalize(
                self._handle_employer_health_insurance(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Visa cancellation grace period ────────────────────────────────────
        # "how long do I have after my visa is cancelled?", "grace period after resignation UAE".
        if _VISA_CANCELLATION_RE.search(message):
            return self._finalize(
                self._handle_visa_cancellation(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Emiratisation / Nafis impact ──────────────────────────────────────
        # "what is Emiratisation?", "does Nafis affect expat hiring?".
        if _EMIRATISATION_RE.search(message):
            return self._finalize(
                self._handle_emiratisation(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Job scam detection ────────────────────────────────────────────────
        # "how do I know if a job offer is a scam?", "red flags in UAE job offers".
        if _JOB_SCAM_RE.search(message):
            return self._finalize(
                self._handle_job_scam(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Salary certificate / employment letter ────────────────────────────
        # "how do I get a salary certificate?", "my bank needs an employment letter".
        if _SALARY_CERTIFICATE_RE.search(message):
            return self._finalize(
                self._handle_salary_certificate(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Networking in UAE ─────────────────────────────────────────────────
        # "how do I network in Dubai?", "networking events UAE".
        if _NETWORKING_UAE_RE.search(message):
            return self._finalize(
                self._handle_networking_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Asking for a promotion ────────────────────────────────────────────
        # "how do I ask for a promotion?", "when should I ask for a raise?".
        if _PROMOTION_UAE_RE.search(message):
            return self._finalize(
                self._handle_promotion_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Handling job rejection ────────────────────────────────────────────
        # "I got rejected, what should I do?", "should I ask for feedback?".
        if _JOB_REJECTION_RE.search(message):
            return self._finalize(
                self._handle_job_rejection(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Counter-offer from current employer ───────────────────────────────
        # "my employer made me a counter-offer, should I accept?".
        if _COUNTER_OFFER_RE.search(message):
            return self._finalize(
                self._handle_counter_offer(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Relocation package ────────────────────────────────────────────────
        # "what should a UAE relocation package include?", "typical relocation allowance UAE".
        if _RELOCATION_PACKAGE_RE.search(message):
            return self._finalize(
                self._handle_relocation_package(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── UAE public holidays ───────────────────────────────────────────────
        # "what are UAE public holidays?", "when is Eid in UAE?".
        if _PUBLIC_HOLIDAYS_UAE_RE.search(message):
            return self._finalize(
                self._handle_public_holidays_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Overtime pay UAE ──────────────────────────────────────────────────
        # "am I entitled to overtime?", "overtime rate UAE".
        if _OVERTIME_PAY_UAE_RE.search(message):
            return self._finalize(
                self._handle_overtime_pay_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Contract types UAE ────────────────────────────────────────────────
        # "limited vs unlimited contract UAE", "what happens when contract expires?".
        if _CONTRACT_TYPES_UAE_RE.search(message):
            return self._finalize(
                self._handle_contract_types_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Multiple job offers ───────────────────────────────────────────────
        # "I have two job offers", "how do I choose between offers?".
        if _MULTIPLE_OFFERS_RE.search(message):
            return self._finalize(
                self._handle_multiple_offers(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Workplace harassment UAE ──────────────────────────────────────────
        # "I'm being harassed at work", "how do I report discrimination?".
        if _WORKPLACE_HARASSMENT_RE.search(message):
            return self._finalize(
                self._handle_workplace_harassment(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Redundancy / layoff UAE ───────────────────────────────────────────
        # "I was made redundant", "company is laying me off", "redundancy rights UAE".
        if _REDUNDANCY_UAE_RE.search(message):
            return self._finalize(
                self._handle_redundancy_uae(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # ── Step 1: Unified intent classification ────────────────────────────
        if has_cv and self._looks_like_career_execution_request(message):
            return self._finalize(
                self._handle_career_execution(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        intent_result = classify_intent(message, has_cv_profile=has_cv)
        intent = intent_result.intent

        # Map Intent v2 dotted notation to legacy intent names for backward compatibility
        legacy_intent = _map_intent_to_legacy(intent)

        logger.info(
            "rico_intent user=%s intent=%s legacy_intent=%s confidence=%.2f source=%s",
            user_id, intent, legacy_intent, intent_result.confidence, intent_result.source,
        )

        # ── Step 2: Route by intent ──────────────────────────────────────────

        # Help / menu — context-aware options based on profile state
        if legacy_intent == "help":
            _help_resp = self._build_context_aware_help(user_id, profile, has_cv, message)
            self._append_chat(user_id, "assistant", _help_resp)
            return self._finalize(_help_resp, self.SOURCE_KEYWORD, profile=profile)

        # Acknowledgement — short warm reply; never restarts or greets
        if legacy_intent == "acknowledgement":
            ack_text = _acknowledgement_reply(message)
            response = {"type": "acknowledgement", "message": ack_text}
            self._append_chat(user_id, "assistant", ack_text)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Positive job feedback — record learning signal and acknowledge
        if legacy_intent == "job_feedback_positive":
            return self._finalize(
                self._handle_job_feedback_positive(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Negative job feedback — record learning signal and acknowledge
        if legacy_intent == "job_feedback_negative":
            return self._finalize(
                self._handle_job_feedback_negative(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Smalltalk (greetings: hi/hello/hey/السلام عليكم/مرحبا/…)
        # Return a short deterministic reply — never call the AI for a greeting.
        # Arabic greetings were previously routed to the AI streaming path which
        # generated long verbose responses that got truncated mid-sentence.
        if legacy_intent == "smalltalk":
            _is_ar = self._is_arabic_text(message)
            recent = self._get_recent_messages(user_id, limit=4)
            has_active_conversation = len(recent) >= 2
            if _is_ar:
                # Islamic greeting "السلام عليكم" requires the proper reply "وعليكم السلام".
                # Using a generic "أهلاً" leaves the greeting unanswered in chat history,
                # which causes the AI to retroactively respond to it in a later turn.
                _is_salam = bool(re.search(r'السلام', message))
                if _is_salam:
                    followup = (
                        "وعليكم السلام! كيف أقدر أساعدك اليوم؟"
                        if has_active_conversation else
                        "وعليكم السلام! أنا ريكو، مساعدك في البحث عن وظائف في الإمارات. "
                        "أخبرني بالمسمى الوظيفي المستهدف أو ارفع سيرتك الذاتية للبدء."
                    )
                else:
                    followup = (
                        "أهلاً! كيف أقدر أساعدك اليوم؟"
                        if has_active_conversation else
                        "أهلاً! أنا ريكو، مساعدك في البحث عن وظائف في الإمارات. "
                        "أخبرني بالمسمى الوظيفي المستهدف أو ارفع سيرتك الذاتية للبدء."
                    )
            else:
                followup = (
                    "What would you like to do next? I can search jobs, review applications, or answer questions about your profile."
                    if has_active_conversation else
                    "Hi! I am Rico, your job search assistant. Tell me a role to search, upload your CV, or say 'help' for options."
                )
            response = {"type": "smalltalk", "message": followup}
            self._append_chat(user_id, "assistant", followup)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Subscription / pricing
        if legacy_intent == "subscription.show_plans":
            _AMBIGUOUS_SUBSCRIBE_PHRASES = frozenset([
                "how can i subscribe", "how do i subscribe", "how to subscribe",
                "i want to subscribe", "i want to upgrade",
            ])
            if message.strip().lower() in _AMBIGUOUS_SUBSCRIBE_PHRASES:
                clarify_response = {
                    "type": "subscription.clarify",
                    "message": "What would you like to subscribe to?",
                    "options": [
                        {"action": "show_plans", "label": "Rico Pro / Premium plans", "message": "Show me Rico subscription plans and pricing"},
                        {"action": "job_alerts", "label": "Job alert notifications", "message": "How do job alert notifications work?"},
                    ],
                }
                self._append_chat(user_id, "assistant", clarify_response["message"])
                return self._finalize(clarify_response, self.SOURCE_KEYWORD, profile=profile)
            sub_response = self._handle_subscription_plans(user_id, profile, message)
            self._append_chat(user_id, "assistant", sub_response.get("message", ""))
            return self._finalize(sub_response, self.SOURCE_KEYWORD, profile=profile)

        # Delegated decision — user asks Rico to choose
        if legacy_intent == "delegated_decision":
            return self._finalize(
                self._handle_delegated_decision(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Onboarding skip
        if legacy_intent == "onboarding_answer":
            response = {
                "type": "profile_skip",
                "message": (
                    "Skipped. I will leave that field blank and continue without forcing it. "
                    "You can update it later."
                ),
                "field_status": "skipped",
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # CV upload / parse — but if CV is already parsed, don't restart wizard
        if legacy_intent == "cv_upload_or_parse":
            # Guard: if the message is a question about using someone else's CV
            # (no actual file attached), route to AI so it can answer naturally
            # instead of mistakenly treating it as a CV upload action.
            _lower_msg = message.lower()
            _is_cv_question = (
                not CV_FILE_RE.search(message)
                and any(kw in _lower_msg for kw in (
                    "friend", "someone else", "can i use", "use his", "use her",
                    "use their", "use my friend", "his cv", "her cv", "their cv",
                    "account for", "needs his own", "needs her own",
                ))
            )
            if _is_cv_question:
                friend_cv_msg = (
                    "You can paste or share your friend's CV text in this chat and I can analyse it "
                    "for them right now — no account needed for a one-off review.\n\n"
                    "However, for saved profile, job tracking, personalised alerts, and application "
                    "history, your friend needs their own Rico account at ricohunt.com.\n\n"
                    "Important: if you upload a CV here it will overwrite *your* profile, so only do "
                    "that if you intend to update your own details."
                )
                response = {"type": "account_delegation", "message": friend_cv_msg}
                self._append_chat(user_id, "assistant", friend_cv_msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)
            cv_status = self._profile_value(profile, "cv_status")
            if cv_status == "parsed" or self._profile_value(profile, "manual_profile_wizard_disabled"):
                # If the user is actually asking to find jobs, search using their profile
                # rather than telling them their CV is already set up.
                _is_job_request = (
                    self._is_live_job_search_request(message)
                    or self._looks_like_generic_job_request(message)
                    or any(kw in message.lower() for kw in (
                        "find", "search", "jobs", "roles", "match my cv",
                        "based on my cv", "using my cv", "suit me",
                    ))
                )
                if _is_job_request:
                    _target_roles = self._effective_target_roles(
                        self._as_list(self._profile_value(profile, "target_roles"))
                    )
                    if _target_roles:
                        return self._finalize(
                            self._target_role_search_response(
                                user_id, _target_roles[0], profile, from_saved_profile=True
                            ),
                            self.SOURCE_KEYWORD,
                            profile=profile,
                        )
                    return self._finalize(
                        self._handle_profile_role_suggestions(profile, message),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                response = {
                    "type": "profile_summary",
                    "message": (
                        "Your CV is already parsed and your profile is set up. "
                        "You can say 'show my profile' to review it, or tell me a role to search."
                    ),
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)
            return self._finalize(
                self._cv_first_profile_response(user_id, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # CV generation — user wants a new CV draft from their existing parsed profile
        if legacy_intent == "cv_generate":
            return self._finalize(
                self._handle_cv_generate_from_profile(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # CV creation — user asks to create a CV (no existing CV)
        if legacy_intent == "cv_create":
            # If CV is already parsed, treat this as a generate request instead
            # of asking the user to start from scratch.
            if self._has_cv_profile(profile):
                return self._finalize(
                    self._handle_cv_generate_from_profile(user_id, profile, message),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            return self._finalize(
                self._handle_cv_creation(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Learning profile summary — what Rico has inferred from user behavior
        if legacy_intent == "learning_profile_summary":
            return self._finalize(
                self._handle_learning_profile_summary(user_id, profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Preference correction — user wants to forget / veto a learned preference
        if legacy_intent == "preference_correction":
            return self._finalize(
                self._handle_preference_correction(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Application insights — success rates, response patterns, follow-up intel
        if legacy_intent == "application_insights":
            return self._finalize(
                self._handle_application_insights(user_id, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        if legacy_intent == "salary_enquiry":
            # Extract explicit role from message before falling back to profile
            _explicit_sal_role: str | None = None
            _sal_role_m = re.search(
                r"(?:salary|pay|earn|paid|worth)\s+(?:for\s+(?:a\s+|an\s+)?|of\s+(?:a\s+|an\s+)?)?([A-Za-z][A-Za-z &/\-]{2,40})"
                r"|([A-Za-z][A-Za-z &/\-]{2,40})\s+(?:salary|pay|earn|wage)",
                message,
                re.IGNORECASE,
            )
            if _sal_role_m:
                _candidate = (_sal_role_m.group(1) or _sal_role_m.group(2) or "").strip()
                # Exclude common non-role words from the match
                _sal_stopwords = {"the", "a", "an", "my", "your", "in", "uae", "dubai", "abudhabi"}
                if _candidate and _candidate.lower() not in _sal_stopwords and len(_candidate) > 2:
                    _explicit_sal_role = _candidate
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role_hint = _explicit_sal_role or (str(target_roles[0]) if target_roles else "your target role")
            _exp = self._profile_value(profile, "years_experience")
            # Show experience-adjusted highlight if we know the user's seniority
            _exp_note = ""
            if _exp is not None:
                _exp_val = float(_exp) if str(_exp).replace(".", "").isdigit() else None
                if _exp_val is not None:
                    if _exp_val < 3:
                        _exp_note = f"\nBased on your **{int(_exp_val)} year(s)** of experience, you're in the **entry-level** bracket."
                    elif _exp_val < 7:
                        _exp_note = f"\nBased on your **{int(_exp_val)} years** of experience, you're in the **mid-level** bracket."
                    else:
                        _exp_note = f"\nBased on your **{int(_exp_val)} years** of experience, you're in the **senior** bracket."
            _sal_msg = (
                f"Salary benchmarks for **{role_hint}** in the UAE:\n\n"
                "• **Entry level (0–3 yrs):** AED 8,000–15,000/month\n"
                "• **Mid level (3–7 yrs):** AED 15,000–25,000/month\n"
                "• **Senior level (7+ yrs):** AED 25,000–45,000/month\n"
                f"{_exp_note}\n\n"
                "Packages vary by industry, company size, and whether benefits "
                "(housing, transport, medical) are included.\n\n"
                "To set a minimum salary so I can filter out low offers, say: "
                "**'My minimum salary is X AED'**"
            )
            self._append_chat(user_id, "assistant", _sal_msg)
            return self._finalize(
                {"type": "career_advice", "message": _sal_msg},
                self.SOURCE_KEYWORD, profile=profile,
            )

        if legacy_intent == "cv_analysis":
            _skills = self._as_list(self._profile_value(profile, "skills"))
            _certs = self._as_list(self._profile_value(profile, "certifications"))
            _exp = self._profile_value(profile, "years_experience")
            _has_cv = self._profile_value(profile, "has_cv") or self._profile_value(profile, "cv_status") == "parsed"
            if not _has_cv:
                _cv_msg = (
                    "I can't review your CV yet — you haven't uploaded one.\n\n"
                    "Upload your CV and I'll identify weak areas, gaps, and improvements."
                )
            else:
                gaps = []
                if not _skills:
                    gaps.append("No skills listed — add key technical and soft skills relevant to your target role.")
                if not _certs:
                    gaps.append("No certifications — even one relevant certification (ISO, NEBOSH, CMA, etc.) significantly improves match rates.")
                if not _exp:
                    gaps.append("Years of experience not set — this affects seniority matching.")
                if not gaps:
                    gaps.append("Your profile looks reasonably complete. The strongest CV improvements come from quantified achievements (e.g. 'Reduced audit findings by 40%') rather than duties.")
                _cv_msg = (
                    "**CV gaps and improvements based on your current profile:**\n\n"
                    + "\n".join(f"• {g}" for g in gaps)
                    + "\n\nFor a full CV rewrite, say: **'Rewrite my CV'** and I'll generate an optimised version."
                )
            self._append_chat(user_id, "assistant", _cv_msg)
            return self._finalize(
                {"type": "cv_analysis", "message": _cv_msg},
                self.SOURCE_KEYWORD, profile=profile,
            )

        # Profile summary
        if legacy_intent == "profile_summary":
            from src.agent.context.resolver import resolve_profile_context
            try:
                ctx = resolve_profile_context(user_id)
                prof_dict = profile_to_dict(ctx.profile) if ctx.profile else {}
            except Exception:
                prof_dict = profile_to_dict(profile) if profile else {}

            # CV-specific request ("my cv", "show my cv", "my resume") must
            # mention CV/upload status — not look like a generic profile dump.
            _msg_lower = (message or "").strip().lower()
            _is_cv_request = bool(re.search(r"\bcv\b|\bresume\b", _msg_lower))
            if _is_cv_request:
                if has_cv:
                    _summary_msg = (
                        "Your CV is on file. Here is what Rico has on your profile — "
                        "skills, experience, and target roles extracted from your upload."
                    )
                else:
                    _summary_msg = (
                        "No CV uploaded yet. Use the **Upload CV** button on this page "
                        "and Rico will parse it automatically. Here is your profile so far."
                    )
            else:
                _summary_msg = "Here is your current profile."

            response = {
                "type": "profile_summary",
                "message": _summary_msg,
                "profile": prof_dict,
            }
            self._append_chat(user_id, "assistant", _summary_msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Profile role suggestions - deterministic fast path based on CV skills/certifications
        if legacy_intent == "profile_role_suggestions":
            return self._finalize(
                self._handle_profile_role_suggestions(profile, message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Generic follow-up confirmations should never fall into role classification.
        if legacy_intent == "follow_up_confirmation":
            # Priority 1: resume a pending apply confirmation (user said "yes"/"1"/"go ahead"
            # after Rico asked "Did you apply? Confirm you submitted.")
            try:
                _ctx = self._get_recent_context(user_id)
                _pending = _ctx.get("_pending_confirm_apply")
                if _pending and _pending.get("title") and _pending.get("company"):
                    from src.repositories.applications_repo import create_manual as _create_manual_app
                    _title = _pending["title"]
                    _company = _pending["company"]
                    # Clear the flag — user has now confirmed
                    _ctx.pop("_pending_confirm_apply", None)
                    self._store_recent_context(user_id, _ctx)
                    try:
                        _saved = _create_manual_app(
                            title=_title,
                            company=_company,
                            status="applied",
                            user_id=user_id,
                        )
                        if not _saved:
                            raise RuntimeError("application create_manual returned false")
                        _msg = (
                            f"Got it — **{_title}** at **{_company}** is marked as applied. "
                            "I'll track it as your latest application. "
                            "You can follow it from Applications (/applications)."
                        )
                        _response_type = "mark_applied"
                        _job_status = "applied"
                        _next_action = "follow_up_after_7_days"
                        self._store_recent_context(
                            user_id,
                            self._build_recent_application_context(
                                title=_title,
                                company=_company,
                                status="applied",
                                action="mark_applied",
                            ),
                        )
                    except Exception:
                        _msg = (
                            f"I understand you submitted **{_title}** at **{_company}**, "
                            "but I couldn't save it right now. Please try again shortly."
                        )
                        _response_type = "application_status_update_failed"
                        _job_status = None
                        _next_action = "retry_application_status_update"
                    self._append_chat(user_id, "assistant", _msg)
                    return self._finalize(
                        {
                            "type": _response_type,
                            "intent": "mark_applied",
                            "message": _msg,
                            "job_title": _title,
                            "job_company": _company,
                            "job_status": _job_status,
                            "target_route": "/applications",
                            "next_action": _next_action,
                        },
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass  # fall through to generic confirmation handling

            # Priority 1.5: stored pending job search (set when Rico promised "ببحث" but
            # the turn ended without executing the search). Checked here so that "تمام"
            # and other follow_up_confirmation phrases correctly trigger the search.
            try:
                _pending_js = self._get_pending_job_search(user_id)
                if _pending_js and _pending_js.get("role"):
                    _js_role = _pending_js["role"]
                    _js_loc = _pending_js.get("location", "")
                    self._clear_pending_job_search(user_id)
                    return self._finalize(
                        self._classified_role_search(user_id, _js_role, profile, location=_js_loc),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass

            # Priority 2: resume a pending role search confirmation
            # (user replied YES after known_but_off_profile clarification)
            try:
                _ctx2 = self._get_recent_context(user_id)
                _pending_role = _ctx2.get("_pending_role_confirmation")
                if _pending_role and _pending_role.get("role"):
                    _role = _pending_role["role"]
                    _ctx2.pop("_pending_role_confirmation", None)
                    self._store_recent_context(user_id, _ctx2)
                    return self._finalize(
                        self._target_role_search_response(user_id, _role, profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass

            if text == "all":
                return self._finalize(
                    self._handle_keep_all_target_roles(user_id, profile, message),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            if has_cv:
                return self._finalize(
                    self._handle_next_step_options(user_id, profile, message),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            response = {
                "type": "clarification",
                "message": (
                    "I am ready to continue. Upload your CV or tell me your target role "
                    "so I know what action to take next."
                ),
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Application tracking — route to applications repo, NOT job search
        if legacy_intent == "application_tracking":
            return self._finalize(
                self._handle_application_tracking(user_id, intent=intent, message=message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        if legacy_intent == "application_status_update":
            return self._finalize(
                self._handle_application_status_update(user_id, message, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Lifecycle funnel queries — chat-side memory (user_job_context)
        if legacy_intent in (
            "lifecycle_show_saved",
            "lifecycle_show_applied",
            "lifecycle_show_opened_not_applied",
        ):
            return self._finalize(
                self._handle_lifecycle_query(user_id, legacy_intent, message=message),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Profile-match job search (use CV/profile, not a named role)
        if legacy_intent == "job_search_profile_match":
            if not has_cv:
                response = {
                    "type": "clarification",
                    "message": (
                        "I don't have enough profile data yet to find matching jobs. "
                        "Upload your CV or tell me your target role, skills, and preferred city."
                    ),
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)
            # Use profile target roles for search
            target_roles = self._effective_target_roles(
                self._as_list(self._profile_value(profile, "target_roles"))
            )
            # Honour a "do not search …" exclusion guard carried on the intent
            # ("find jobs based on my CV, but do not search Software Engineer, …"):
            # filter excluded roles out of the candidates so they are never searched
            # or suggested, and persist the guard for this session.
            _pm_excluded = [
                str(e).strip()
                for e in ((getattr(intent_result, "entities", None) or {}).get("excluded_roles") or [])
                if str(e).strip()
            ]
            if _pm_excluded:
                target_roles = self._filter_excluded_roles(target_roles, _pm_excluded)
                try:
                    _pm_ctx = self._get_recent_context(user_id)
                    _pm_ctx["excluded_roles"] = _pm_excluded
                    self._store_recent_context(user_id, _pm_ctx)
                except Exception:
                    pass
            logger.info(
                "rico_profile_match_search user=%s target_roles=%s excluded=%s has_cv=%s",
                user_id, target_roles, _pm_excluded, has_cv,
            )
            # Never blindly search target_roles[0] — it may be one of several saved
            # tracks, or a stale role that no longer matches the CV. Resolve the
            # single CV-aligned role, or ask the user to choose first.
            _pm_role, _pm_candidates, _pm_status = self._resolve_profile_search_role(
                profile, excluded_roles=_pm_excluded
            )
            if _pm_status == "ambiguous":
                _pm_choice = self._profile_role_choice_response(_pm_candidates, message)
                self._append_chat(user_id, "assistant", _pm_choice["message"])
                return self._finalize(_pm_choice, self.SOURCE_KEYWORD, profile=profile)
            if _pm_status in ("none", "stale"):
                # Stale saved role (no longer matches the CV) or nothing left after
                # exclusions → surface CV-aligned suggestions and let the user choose,
                # instead of silently searching a stale/irrelevant target_role.
                _pm_sugg = self._handle_profile_role_suggestions(profile, message)
                if _pm_status == "stale" and _pm_role:
                    _pm_sugg = {**_pm_sugg, "stale_target_role": _pm_role}
                self._append_chat(user_id, "assistant", _pm_sugg.get("message", ""))
                return self._finalize(_pm_sugg, self.SOURCE_KEYWORD, profile=profile)
            # status == "single": exactly one CV-aligned saved role → search it.
            _pm_response = self._target_role_search_response(
                user_id, _pm_role, profile, from_saved_profile=True
            )
            if _pm_excluded:
                _pm_response["excluded_roles"] = _pm_excluded
            return self._finalize(_pm_response, self.SOURCE_KEYWORD, profile=profile)

        # Profile update — route BEFORE role-change fallback
        if legacy_intent == "profile_update":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            prefs = routed.tool_args.get("preferences", {})

            # Trust invariant: never claim a write happened when none did. A bare
            # "update my profile" / "edit my profile" / "تحديث ملفي" carries no
            # concrete field, so there is nothing to persist — offer the editable
            # fields and route to /profile instead of faking success.
            if not prefs:
                arabic = self._is_arabic_text(message)
                if arabic:
                    _edit_msg = (
                        "بالتأكيد — لم أغيّر أي شيء بعد. ما الذي تريد تحديثه؟\n\n"
                        "يمكنك تعديل: المسمى الوظيفي المستهدف، المدن المفضّلة، سنوات الخبرة، "
                        "المهارات، المجال، توقّع الراتب، حالة التأشيرة، اسم تيليجرام.\n\n"
                        "أخبرني بالتغيير (مثل: «اجعل المسمى المستهدف مدير بيئة» أو «حدّد راتبي بـ 18000»)، "
                        "أو افتح صفحة **الملف الشخصي** لتعديل كل الحقول."
                    )
                else:
                    _edit_msg = (
                        "Sure — I haven't changed anything yet. What would you like to update?\n\n"
                        "You can edit your **target role**, **preferred cities**, **years of experience**, "
                        "**skills**, **industry**, **salary expectation**, **visa status**, or "
                        "**Telegram username**.\n\n"
                        "Tell me the change (e.g. \"set my target role to Environmental Manager\" or "
                        "\"set my salary to 18000\"), or open your **Profile** page to edit every field."
                    )
                self._append_chat(user_id, "assistant", _edit_msg)
                return self._finalize(
                    {
                        "type": "profile_edit",
                        "message": _edit_msg,
                        "route": "/profile",
                        "editable_fields": [
                            "target_roles", "preferred_cities", "years_experience",
                            "skills", "industries", "salary_expectation_aed",
                            "visa_status", "telegram_username",
                        ],
                    },
                    routed.source,
                    profile=profile,
                )

            # BUG-04: concrete preferences were extracted, but a chat message is
            # NOT consent to mutate the stored profile. Stash the pending update
            # and ASK first — the DB write happens only when the user confirms
            # (handled by the 'confirm_profile_update' branch in
            # _resolve_pending_field, which runs before intent classification).
            _changes = self._format_pref_changes(prefs)
            ctx = self._get_recent_context(user_id)
            ctx["_pending_field"] = "confirm_profile_update"
            ctx["_pending_profile_update"] = prefs
            self._store_recent_context(user_id, ctx)
            if self._is_arabic_text(message):
                _ask_msg = (
                    "قبل أن أحفظ هذه التغييرات في ملفك الشخصي:\n"
                    + "\n".join(f"• {c}" for c in _changes)
                    + "\n\nاضغط **حفظ التغييرات** أدناه، أو ردّ بـ **نعم** للحفظ أو **لا** للإلغاء."
                )
            else:
                _ask_msg = (
                    "Before I save these to your profile:\n"
                    + "\n".join(f"• {c}" for c in _changes)
                    + "\n\nClick **Save changes** below, or reply **yes** to confirm or **no** to cancel."
                )
            response = {
                "type": "clarification",
                "message": _ask_msg,
                "pending": prefs,
            }
            self._append_chat(user_id, "assistant", _ask_msg)

            # CAREER-OS-07: emit ProposedChangeCard so the frontend can render
            # a structured confirmation UI instead of a text yes/no prompt.
            _proposed = self._build_proposed_changes(prefs, profile or {})
            import uuid as _uuid
            _submit_action = {
                "id": f"submit-profile-{_uuid.uuid4().hex[:8]}",
                "label": "Save changes",
                "kind": "submit",
                "impact": "medium",
                "requires_confirmation": False,
                "endpoint": "/api/v1/rico/profile",
                "payload": dict(prefs),
            }

            class _Agentic:
                def __init__(self, **kw: Any) -> None:
                    self.data = kw

            return self._finalize(
                response,
                routed.source,
                profile=profile,
                runtime_result=_Agentic(
                    proposed_changes=_proposed,
                    actions=[_submit_action],
                ),
            )

        # Multi-role search list — "search for A, B and C roles, do not search X, Y".
        # Recognise every requested role, persist the exclusion guard for this
        # session, then search the primary (first) role now while offering the rest
        # as one-tap alternatives. Without this the whole comma list reaches
        # _classified_role_search as a single token and is rejected as unknown.
        if legacy_intent == "job_search_multi_role":
            _ml_entities = getattr(intent_result, "entities", None) or {}
            _ml_roles = [str(r).strip() for r in (_ml_entities.get("roles") or []) if str(r).strip()]
            _ml_excluded = [str(r).strip() for r in (_ml_entities.get("excluded_roles") or []) if str(r).strip()]
            _ml_location = _ml_entities.get("location", "")
            _ml_emp_type = _ml_entities.get("employment_type", "")
            if _ml_roles:
                return self._finalize(
                    self._multi_role_search_response(
                        user_id, _ml_roles, profile,
                        excluded_roles=_ml_excluded,
                        location=_ml_location,
                        employment_type_filter=_ml_emp_type,
                    ),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

        # Role change — extract role and classify
        if legacy_intent == "role_change" and intent_result.extracted_role:
            return self._finalize(
                self._classified_role_search(user_id, intent_result.extracted_role, profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Search refinement / source filter — compound constraints without an explicit role.
        # "exclude LinkedIn results", "show me only Dubai jobs, no contract roles", etc.
        if legacy_intent == "search_refine":
            _refine_action = getattr(intent_result, "action", "") or ""
            _refine_entities = getattr(intent_result, "entities", None) or {}
            _refine_location = _refine_entities.get("location", "")
            _refine_emp_type = _refine_entities.get("employment_type", "")

            if _refine_action == "source_filter":
                _refine_msg = (
                    "I don't currently filter results by source — all UAE job boards are searched together. "
                    "Try refining by role, city, or employment type instead, "
                    "e.g. 'Compliance Manager jobs in Dubai, permanent only'."
                )
                self._append_chat(user_id, "assistant", _refine_msg)
                return self._finalize(
                    {"type": "search_refine", "message": _refine_msg, "intent": "search_refine"},
                    self.SOURCE_KEYWORD, profile=profile,
                )

            # Resolve prior role from context or profile — enables compositional refinement:
            # "Compliance Manager jobs" followed by "only Dubai" → searches Compliance Manager in Dubai
            _prior_role: str = ""
            try:
                _rctx = self._get_recent_context(user_id)
                _prior_role = (
                    _rctx.get("recent_search_role")
                    or _rctx.get("recent_role")
                    or ""
                )
            except Exception:
                pass
            if not _prior_role:
                _tgt = self._effective_target_roles(
                    self._as_list(self._profile_value(profile, "target_roles"))
                )
                _prior_role = str(_tgt[0]) if _tgt else ""

            if _prior_role and (_refine_location or _refine_emp_type):
                # Execute the refined search directly — no need to ask again
                return self._finalize(
                    self._target_role_search_response(
                        user_id, _prior_role, profile,
                        location=_refine_location,
                        employment_type_filter=_refine_emp_type,
                    ),
                    self.SOURCE_KEYWORD, profile=profile,
                )

            # Can't refine without a role — ask just for the missing piece
            if _refine_location:
                _refine_msg = (
                    f"Got it — focusing on {_refine_location}. "
                    f"Which role are you targeting? For example: "
                    f"'Compliance Manager jobs in {_refine_location}'."
                )
            elif _refine_emp_type:
                _refine_msg = (
                    f"Got it — {_refine_emp_type} roles only. "
                    "Which role are you targeting? For example: "
                    f"'Compliance Manager, {_refine_emp_type} only'."
                )
            else:
                _refine_msg = (
                    "Got it — I can apply those filters. Which role are you looking for? "
                    "For example: 'Compliance Manager jobs in Dubai, permanent only'."
                )
            self._append_chat(user_id, "assistant", _refine_msg)
            return self._finalize(
                {"type": "search_refine", "message": _refine_msg, "intent": "search_refine"},
                self.SOURCE_KEYWORD, profile=profile,
            )

        # Explicit job search (regex-matched "find ... jobs" etc.)
        if legacy_intent == "job_search_explicit":
            _js_entities = getattr(intent_result, "entities", None) or {}
            _js_location = _js_entities.get("location", "")
            _js_emp_type = _js_entities.get("employment_type", "")
            # If the message names an explicit role ("find jobs for Environmental
            # Compliance Officer"), honour it and bypass profile target_roles fallback.
            if intent_result.extracted_role:
                return self._finalize(
                    self._classified_role_search(
                        user_id, intent_result.extracted_role, profile,
                        location=_js_location,
                        employment_type_filter=_js_emp_type,
                    ),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

            # No explicit role in this message — check recent conversation context
            # before falling back to profile target_roles.  This preserves continuity
            # when users switch languages mid-conversation (e.g. searched "software jobs"
            # in English then sent "ابحث لي وظائف في أبوظبي" in Arabic).
            try:
                _ctx = self._get_recent_context(user_id)
                _prior_role = (
                    _ctx.get("recent_search_role")
                    or _ctx.get("recent_role")
                    or _ctx.get("recent_job")
                )
                if _prior_role:
                    return self._finalize(
                        self._classified_role_search(user_id, _prior_role, profile),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
            except Exception:
                pass

            # Fall through to legacy router for entity extraction
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)

            # Check if profile has target role before running job search
            target_roles = self._effective_target_roles(
                self._as_list(self._profile_value(profile, "target_roles"))
            )
            if not target_roles:
                if has_cv:
                    # CV present but no confirmed target role → suggest roles from skills
                    return self._finalize(
                        self._handle_profile_role_suggestions(profile, message),
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                _is_ar = self._is_arabic_text(message)
                _incomplete_msg = (
                    "لإجراء البحث أحتاج إلى معرفة المسمى الوظيفي المستهدف.\n"
                    "أخبرني بالمسمى الوظيفي المستهدف — على سبيل المثال: مهندس برمجيات، محاسب، مدير مشاريع."
                    if _is_ar else
                    "What role are you looking for? "
                    "Tell me your target role and I'll search UAE jobs right away — "
                    "for example: 'HSE Manager', 'Finance Analyst', or 'Compliance Officer'."
                )
                response = {
                    "type": "profile_incomplete",
                    "intent": "search_jobs",
                    "message": _incomplete_msg,
                    "entities": routed.entities,
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, routed.source, profile=profile)

            # Removed fast-path override to prevent intent interception
            # Previously: generic job searches without job_title were intercepted by profile suggestions
            # Now: all explicit job searches execute through the normal workflow
            operation = self._begin_job_search_operation(user_id, str(target_roles[0]))
            operation_id = str(operation["operation_id"])
            try:
                workflow_result = self.system.run_for_profile(profile)
            except Exception as exc:
                mark_failed(user_id, operation_id, str(exc))
                raise

            # Handle blocked status from job search
            if workflow_result.get("status") == "blocked":
                mark_failed(
                    user_id,
                    operation_id,
                    workflow_result.get("message", "Job search was blocked by incomplete profile."),
                )
                response = {
                    "type": "profile_incomplete",
                    "intent": "search_jobs",
                    "message": workflow_result.get("message", "Please provide at least one target role before searching for jobs."),
                    "entities": routed.entities,
                }
                self._append_chat(user_id, "assistant", response["message"])
                return self._finalize(response, routed.source, profile=profile)

            all_explicit = workflow_result.get("matches", [])
            try:
                from src.applications import is_applied_batch, get_job_id
                if all_explicit:
                    app_map = is_applied_batch(all_explicit, user_id=user_id)
                    all_explicit = [m for m in all_explicit if not app_map.get(get_job_id(m), False)]
            except Exception:
                pass
            top_matches = self._sort_by_company_quality(
                self._rerank_by_learned_preferences(all_explicit, user_id)
            )[:5]
            formatted = [self._format_match(m, profile) for m in top_matches]
            if top_matches:
                job_msg = "I found {} strong UAE job matches for you.".format(len(top_matches))
                response = {
                    "type": "job_matches",
                    "intent": "search_jobs",
                    "message": job_msg,
                    "matches": formatted,
                    "entities": routed.entities,
                    "operation_id": operation_id,
                    "operation_status": "completed",
                    "operation_type": "job_search",
                    "result_count": len(formatted),
                }
                self._append_chat(user_id, "assistant", response)
                mark_completed(user_id, operation_id, len(formatted))
                if formatted:
                    self._store_search_matches_context(user_id, formatted)
                return self._finalize(response, routed.source, profile=profile)
            else:
                mark_completed(user_id, operation_id, 0)
                if has_cv:
                    response = self._handle_no_results_recovery(user_id, profile, target_roles, message)
                    response.update({
                        "operation_id": operation_id,
                        "operation_status": "completed",
                        "operation_type": "job_search",
                        "result_count": 0,
                    })
                    return self._finalize(
                        response,
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )
                response = {
                    "type": "job_matches",
                    "intent": "search_jobs",
                    "message": (
                        "No strong UAE job matches found right now. "
                        "Try specifying your target role — for example: "
                        "'find HSE Manager jobs in Dubai'."
                    ),
                    "matches": [],
                    "entities": routed.entities,
                    "operation_id": operation_id,
                    "operation_status": "completed",
                    "operation_type": "job_search",
                    "result_count": 0,
                }
                self._append_chat(user_id, "assistant", response)
                return self._finalize(response, routed.source, profile=profile)

        # Prepare application — from job card "Prepare application — {title} at {company}"
        if legacy_intent == "prepare_application":
            # 1. Resolve job from intent extraction or recent context.
            raw_title = (getattr(intent_result, "extracted_title", None) or "").strip()
            raw_company = (getattr(intent_result, "extracted_company", None) or "").strip()
            # Strip the old fallback sentinel values the handler used before.
            if raw_title in ("the role",):
                raw_title = ""
            if raw_company in ("the company",):
                raw_company = ""

            # Resolve the job back to the one Rico actually surfaced (recent search
            # matches / persisted context) so the lifecycle job_key matches the
            # "opened" record the search path stored. Without this, the prepared
            # write can target a different key (title/company parsed slightly
            # differently) and the /flow row never upgrades opened -> prepared.
            _ctx_row = None
            if raw_title or raw_company:
                _ctx_row = self._resolve_card_job(user_id, raw_title, raw_company)
            if _ctx_row:
                title = (_ctx_row.get("title") or raw_title).strip()
                company = (_ctx_row.get("company") or raw_company).strip()
            else:
                title, company = raw_title, raw_company
            self._log_document_draft_context_source(
                "explicit_message" if title and company else "clarification_required",
                {"title": title, "company": company},
            )

            if not title or not company:
                msg = (
                    "Which job would you like me to prepare the application for? "
                    "Tell me the job title and company, or search for jobs first."
                )
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(
                    {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                    self.SOURCE_KEYWORD, profile=profile,
                )

            # 2. Get user CV — required for tailoring.
            _cv_text = ""
            _db_pa = None
            try:
                from src.rico_db import RicoDB
                _db_pa = RicoDB()
                _bundle = _db_pa.get_user_bundle(user_id)
                if _bundle:
                    _cv_text = (_bundle.get("cv_text") or "").strip()
            except Exception:
                pass

            # Fall back to already-loaded profile before asking for re-upload.
            if not _cv_text:
                _cv_text = (
                    self._profile_value(profile, "cv_text")
                    or self._profile_value(profile, "pasted_cv_text")
                    or ""
                ).strip()

            if not _cv_text:
                msg = (
                    f"To prepare your application for **{title}** at **{company}**, "
                    "I need your CV first. Upload it from your profile or paste it in chat."
                )
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(
                    {"type": "prepare_application", "intent": "prepare_application",
                     "message": msg, "next_action": "upload_cv"},
                    self.SOURCE_KEYWORD, profile=profile,
                )

            # 3. Build job context fields.
            _apply_url = (_ctx_row or {}).get("apply_url") or ""
            _source_url = (_ctx_row or {}).get("source_url") or ""
            _location = (_ctx_row or {}).get("location") or "UAE"
            _job_key = self._derive_lifecycle_job_key(title, company)

            # 4. Duplicate protection — reuse existing pending draft for same job.
            _existing_draft = None
            try:
                if _db_pa is None:
                    from src.rico_db import RicoDB
                    _db_pa = RicoDB()
                _pending = _db_pa.get_application_drafts(user_id, status="pending")
                _existing_draft = next(
                    (d for d in _pending if d.get("job_key") == _job_key), None
                )
            except Exception:
                pass

            if _existing_draft:
                _draft = _existing_draft
                _reused = True
            else:
                # 5. Generate tailored CV + cover letter.
                _reused = False
                try:
                    from src.rico_apply_ai import tailor_application as _tailor
                    _tail = _tailor(
                        cv_text=_cv_text,
                        profile=profile if isinstance(profile, dict) else {},
                        job={
                            "title": title,
                            "company": company,
                            "description": "",
                            "apply_url": _apply_url or _source_url,
                            "location": _location,
                        },
                    )
                    _tailored_cv = (_tail.get("tailored_cv") or "").strip()
                    _cover_letter = (_tail.get("cover_letter") or "").strip()
                except Exception as _exc:
                    logger.warning("prepare_application tailor failed user=%s: %s", user_id, _exc)
                    msg = (
                        f"I had trouble generating the draft for **{title}** at **{company}** right now. "
                        "Please try again in a moment."
                    )
                    self._append_chat(user_id, "assistant", msg)
                    return self._finalize(
                        {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                        self.SOURCE_KEYWORD, profile=profile,
                    )

                if not _tailored_cv or not _cover_letter:
                    msg = (
                        f"The draft for **{title}** at **{company}** came back incomplete. "
                        "Please try again or provide the job description for better results."
                    )
                    self._append_chat(user_id, "assistant", msg)
                    return self._finalize(
                        {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                        self.SOURCE_KEYWORD, profile=profile,
                    )

                # 6. Insert into application_drafts.
                try:
                    if _db_pa is None:
                        from src.rico_db import RicoDB
                        _db_pa = RicoDB()
                    _draft = _db_pa.create_application_draft(
                        user_id=user_id,
                        job_key=_job_key,
                        job_title=title,
                        company=company,
                        job_description="",
                        apply_url=_apply_url or _source_url,
                        tailored_cv=_tailored_cv,
                        cover_letter=_cover_letter,
                    )
                except Exception as _exc:
                    logger.warning("create_application_draft failed user=%s: %s", user_id, _exc)
                    msg = (
                        f"I prepared your draft for **{title}** at **{company}** but couldn't save it. "
                        "Please try again shortly."
                    )
                    self._append_chat(user_id, "assistant", msg)
                    return self._finalize(
                        {"type": "prepare_application", "intent": "prepare_application", "message": msg},
                        self.SOURCE_KEYWORD, profile=profile,
                    )

            # 7. Update user_job_context lifecycle → prepared.
            try:
                from src.repositories.user_job_context_repo import set_lifecycle_status as _slc_pa
                _slc_pa(
                    user_id=user_id, title=title, company=company, status="prepared",
                    apply_url=_apply_url, source_url=_source_url,
                )
            except Exception:
                pass

            # Also write to rico_job_recommendations so prepared jobs appear on /flow board.
            # Capture whether the board write actually landed so the reply only claims
            # "Prepared" when persistence succeeded (otherwise warn the user).
            _board_persisted = False
            try:
                _board_persisted = self._persist_application_lifecycle_event(
                    user_id=user_id,
                    title=title,
                    company=company,
                    status="prepared",
                    url=_apply_url or _source_url,
                    location=_location,
                )
            except Exception:
                _board_persisted = False

            # 8. Learning signal for draft preparation.
            try:
                from src.repositories.learning_repo import get_learning_repository
                get_learning_repository().infer_signals_from_job_action(
                    user_id, "prepared",
                    {"title": title, "company": company, "apply_url": _apply_url or _source_url},
                )
            except Exception:
                pass

            # 9. Store recent context.
            self._store_recent_context(
                user_id,
                self._build_recent_application_context(
                    title=title, company=company, status="prepared", action="prepare_application",
                ),
            )

            _draft_id = str(_draft.get("id") or "")
            _cl = _draft.get("cover_letter") or ""
            _cl_preview = _cl[:350]
            _reuse_note = (
                "_(Existing pending draft found — showing that one.)_\n\n" if _reused else ""
            )
            _board_note = (
                "\n\n_Tracked as **Prepared** on your board (/flow)._"
                if _board_persisted
                else "\n\n_Your draft is saved, but I couldn't update your board status just "
                "now — it may still show the previous stage. Try again shortly._"
            )
            msg = (
                f"{_reuse_note}**Draft ready — {title} at {company}**\n\n"
                f"**Cover letter preview:**\n{_cl_preview}"
                f"{'…' if len(_cl) > 350 else ''}\n\n"
                "Your tailored CV has been prepared. "
                "Review the full draft from Applications (/applications)."
                f"{_board_note}"
            )
            response = {
                "type": "prepare_application",
                "intent": "prepare_application",
                "message": msg,
                "board_status_persisted": _board_persisted,
                "draft_id": _draft_id,
                "job_title": title,
                "job_company": company,
                "reused_draft": _reused,
                "options": [
                    {"action": "open_apply_link", "label": "Open apply link",
                     "message": f"open apply link for {title} at {company}"},
                    {"action": "mark_applied", "label": "Mark as applied",
                     "message": f"Mark as applied — {title} at {company}"},
                ],
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Mark as applied — from job card "Mark as applied — {title} at {company}"
        if legacy_intent == "mark_applied":
            from src.repositories.applications_repo import create_manual as _create_manual_app
            title = getattr(intent_result, "extracted_title", None) or ""
            company = getattr(intent_result, "extracted_company", None) or ""

            # Guard: require apply-link evidence or prior explicit confirmation.
            # If neither exists, return a clarification and set the pending-confirm flag.
            if not self._has_apply_evidence(user_id, title, company):
                msg = (
                    f"Before I mark **{title}** at **{company}** as applied, "
                    "can you confirm you submitted your application? "
                    "I don't have a record of you opening the apply link for this role."
                )
                # Store confirmation flag so the next "Mark as applied" for the same
                # job is treated as explicit manual confirmation and proceeds.
                try:
                    ctx = self._get_recent_context(user_id)
                    ctx["_pending_confirm_apply"] = {"title": title, "company": company}
                    self._store_recent_context(user_id, ctx)
                except Exception:
                    pass
                response = {
                    "type": "clarification",
                    "intent": "mark_applied",
                    "message": msg,
                    "job_title": title,
                    "job_company": company,
                    "options": [
                        {
                            "action": "confirm_mark_applied",
                            "label": "Yes, I applied",
                            "message": f"Mark as applied — {title} at {company}",
                        },
                        {
                            "action": "open_apply_link",
                            "label": "Show apply link first",
                            "message": f"open apply link for {title} at {company}",
                        },
                    ],
                    "next_action": "confirm_application",
                }
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

            # Evidence confirmed — clear the pending flag and write the record.
            try:
                ctx = self._get_recent_context(user_id)
                ctx.pop("_pending_confirm_apply", None)
                self._store_recent_context(user_id, ctx)
            except Exception:
                pass

            try:
                saved = _create_manual_app(title=title, company=company, status="applied", user_id=user_id)
                if not saved:
                    raise RuntimeError("application create_manual returned false")
                msg = (
                    f"Tracked — **{title}** at **{company}** marked as applied. "
                    "I will treat this as your latest application context for follow-ups. "
                    "You can follow it from Applications (/applications)."
                )
                response_type = "mark_applied"
                job_status = "applied"
                next_action = "follow_up_after_7_days"
                self._store_recent_context(
                    user_id,
                    self._build_recent_application_context(
                        title=title,
                        company=company,
                        status="applied",
                        action="mark_applied",
                    ),
                )
                # Fire learning signal for confirmed application.
                try:
                    from src.repositories.learning_repo import get_learning_repository
                    get_learning_repository().infer_signals_from_job_action(
                        user_id, "apply", {"title": title, "company": company}
                    )
                except Exception:
                    pass
            except Exception:
                msg = (
                    f"I understand you submitted **{title}** at **{company}**, "
                    "but I couldn't save it right now. Please try again shortly."
                )
                response_type = "application_status_update_failed"
                job_status = None
                next_action = "retry_application_status_update"
            response = {
                "type": response_type,
                "intent": "mark_applied",
                "message": msg,
                "job_title": title,
                "job_company": company,
                "job_status": job_status,
                "target_route": "/applications",
                "next_action": next_action,
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Track this job — from job card "Track this job — {title} at {company}"
        if legacy_intent == "track_job":
            from src.repositories.applications_repo import create_manual as _create_manual_app
            title = getattr(intent_result, "extracted_title", None) or ""
            company = getattr(intent_result, "extracted_company", None) or ""
            # Use URL evidence from recent context to distinguish a live posting
            # (apply link was opened/verified) from a lead that still needs verification.
            has_url = self._has_apply_evidence(user_id, title, company)
            try:
                _create_manual_app(title=title, company=company, status="saved", user_id=user_id)
                if has_url:
                    msg = (
                        f"Saved — **{title}** at **{company}**. "
                        "I will use this as your latest job context."
                    )
                else:
                    msg = (
                        f"Saved as lead — **{title}** at **{company}**. "
                        "This role hasn't been verified via an apply link yet — "
                        "open the apply link to confirm it's still live before applying."
                    )
                self._store_recent_context(
                    user_id,
                    self._build_recent_application_context(
                        title=title,
                        company=company,
                        status="saved",
                        action="track_job",
                    ),
                )
            except Exception:
                msg = (
                    f"Noted — **{title}** at **{company}** added to your tracking list. "
                    "(Could not write to Application Flow right now — please retry.)"
                )
            response = {
                "type": "track_job",
                "intent": "track_job",
                "message": msg,
                "job_title": title,
                "job_company": company,
                "job_status": "saved",
                "next_action": "review_or_mark_applied",
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Open apply link — show URL only; never triggers apply confirmation
        if legacy_intent == "open_apply_link":
            # Ordinal form ("open the apply link for the first/Nth job") — resolve
            # the job from recent search context and use the SAME canonical link
            # field as the card, returning a safe fallback CTA when there is no
            # usable link. Never raises the "missing required 'link' field" error.
            _oal_entities = getattr(intent_result, "entities", None) or {}
            _ordinal = _oal_entities.get("ordinal")
            if _ordinal is not None:
                return self._finalize(
                    self._open_apply_link_by_ordinal(user_id, int(_ordinal), profile),
                    self.SOURCE_KEYWORD, profile=profile,
                )

            title = getattr(intent_result, "extracted_title", None) or ""
            company = getattr(intent_result, "extracted_company", None) or ""
            apply_url = None
            source_was_lead = False

            # 1. Recent search matches (same session) — checked first so a job returned
            #    by a search can be acted on immediately without saving it first.
            #    Scan all matches for this title/company: prefer a live URL over a lead.
            #    Do NOT set apply_url="" on a lead match — that would skip Application Flow.
            if title and company:
                try:
                    ctx = self._get_recent_context(user_id)
                    for m in ctx.get("recent_search_matches", []):
                        if (title.lower() in (m.get("title") or "").lower() and
                                company.lower() in (m.get("company") or "").lower()):
                            url = (m.get("apply_url") or m.get("link") or "").strip()
                            if url:
                                apply_url = url
                                break  # Found a live URL — stop scanning
                            else:
                                # Lead match — note it, but keep scanning for a live URL entry
                                source_was_lead = (
                                    m.get("verification_status") == "lead_needs_verification"
                                )
                except Exception:
                    pass

            # 2. Application Flow records (saved / previously applied jobs)
            if not apply_url and title and company:
                try:
                    from src.repositories.applications_repo import get_all as _get_all_apps
                    for rec in _get_all_apps(user_id=user_id):
                        if (title.lower() in (rec.get("title") or "").lower() and
                                company.lower() in (rec.get("company") or "").lower()):
                            url = self._extract_rec_url(rec)
                            if url:
                                apply_url = url
                                source_was_lead = False  # Real URL found — clear lead flag
                                break
                            elif apply_url is None:
                                apply_url = ""
                except Exception:
                    pass

            # 3. Neon user_job_context — survives restarts and postgres memory mode
            db_source_url = None
            if not apply_url and title and company:
                try:
                    from src.repositories.user_job_context_repo import find_by_title_company
                    row = find_by_title_company(user_id, title, company)
                    if row:
                        if row.get("apply_url"):
                            apply_url = row["apply_url"]
                            source_was_lead = False
                        elif row.get("source_url"):
                            db_source_url = row["source_url"]
                            source_was_lead = (
                                row.get("verification_status") == "lead_needs_verification"
                            )
                except Exception:
                    pass

            # Check if link is expired before opening
            is_expired = False
            try:
                ctx = self._get_recent_context(user_id)
                for m in ctx.get("recent_search_matches", []):
                    if (title.lower() in (m.get("title") or "").lower() and
                            company.lower() in (m.get("company") or "").lower()):
                        if m.get("verification_status") == "expired":
                            is_expired = True
                            break
            except Exception:
                pass

            if is_expired:
                msg = (
                    f"The apply link for **{title}** at **{company}** appears to be expired.\n\n"
                    "You can:\n"
                    "• **Refresh** — I can try to find an updated listing\n"
                    "• **Dismiss** — Remove this role from your feed\n"
                    "• **Search** — Look for similar roles right now"
                )
                response = {
                    "type": "open_apply_link",
                    "intent": "open_apply_link",
                    "message": msg,
                    "apply_url": None,
                    "verification_status": "expired",
                    "options": [
                        {"action": "refresh_link", "label": "Refresh", "message": f"refresh link for {title} at {company}"},
                        {"action": "dismiss_job", "label": "Dismiss", "message": f"dismiss {title} at {company}"},
                        {"action": "search_similar", "label": "Search similar", "message": f"search similar to {title} at {company}"},
                    ],
                }
                self._append_chat(user_id, "assistant", msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

            if apply_url:
                return self._handle_open_apply_link_path(
                    user_id=user_id, title=title, company=company,
                    apply_url=apply_url, profile=profile,
                )
            elif db_source_url:
                msg = (
                    f"I don't have a direct apply link saved for **{title}** at **{company}**, "
                    f"but I found the source job listing: {db_source_url}\n\n"
                    "Open it to apply from the official listing."
                )
            elif title and company:
                if source_was_lead:
                    msg = (
                        f"**{title}** at **{company}** was returned as a lead — "
                        "it has no verified apply link yet. "
                        "Check the company website or LinkedIn to confirm the role is still live "
                        "before applying."
                    )
                else:
                    msg = (
                        f"I don't have the official apply link saved yet for **{title}** at **{company}**. "
                        "I'll keep this role marked as needs source verification and continue with verified matches."
                    )
            else:
                # No title/company provided — try to resolve from recently discussed jobs
                resolved_recent = None
                try:
                    from src.repositories.user_job_context_repo import (
                        get_recently_discussed as _get_recently_discussed,
                        get_recently_interacted as _get_recently_interacted,
                    )
                    recent = _get_recently_discussed(user_id, limit=1)
                    if not recent:
                        recent = _get_recently_interacted(user_id, limit=1)
                    if recent:
                        resolved_recent = recent[0]
                except Exception:
                    pass

                if resolved_recent:
                    title = resolved_recent.get("title") or ""
                    company = resolved_recent.get("company") or ""
                    apply_url = resolved_recent.get("apply_url") or ""
                    source_url_fallback = resolved_recent.get("source_url") or ""
                    if apply_url:
                        msg = f"Apply link for **{title}** at **{company}**: {apply_url}"
                        self._persist_application_lifecycle_event(
                            user_id=user_id,
                            title=title,
                            company=company,
                            status="opened_external",
                            url=apply_url,
                        )
                        self._store_recent_context(
                            user_id,
                            self._build_recent_application_context(
                                title=title,
                                company=company,
                                status="opened_external",
                                action="open_apply_link",
                                link=apply_url,
                            ),
                        )
                        try:
                            from src.repositories.learning_repo import get_learning_repository
                            get_learning_repository().infer_signals_from_job_action(
                                user_id, "opened_external", {"title": title, "company": company, "apply_url": apply_url}
                            )
                        except Exception:
                            pass
                    elif source_url_fallback:
                        msg = (
                            f"I don't have a direct apply link for **{title}** at **{company}**, "
                            f"but here's the source listing: {source_url_fallback}"
                        )
                    else:
                        msg = (
                            f"I found your recent job **{title}** at **{company}**, "
                            "but I don't have an apply link saved for it yet. "
                            "Run a search to refresh the listing."
                        )
                else:
                    msg = "Please specify the job title and company so I can look up the apply link."
            response = {"type": "open_apply_link", "intent": "open_apply_link",
                        "message": msg, "apply_url": apply_url}
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Recent context follow-up — "where?", "show it", "what about the job I just applied to?"
        if legacy_intent == "recent_context":
            ctx = self._get_recent_context(user_id)
            if ctx:
                msg = self._build_recent_context_message(ctx)
            else:
                apps = None
                try:
                    from src.repositories.applications_repo import get_all as _get_all_apps
                    apps = _get_all_apps(user_id=user_id)
                except Exception:
                    apps = None
                if apps is None:
                    msg = (
                        "I couldn't retrieve your application history right now. "
                        "Please try again shortly."
                    )
                elif apps:
                    latest = self._enrich_applications([self._sort_applications_recent(apps)[0]])[0]
                    job = (latest.get("title") or "Unknown")
                    company = (latest.get("company") or "Unknown")
                    status = latest.get("status_label") or latest.get("status") or "tracked"
                    days = latest.get("days_since_applied")
                    days_str = (
                        f", applied {days} day{'s' if days != 1 else ''} ago"
                        if days is not None else ""
                    )
                    fu_hint = " Consider following up now." if latest.get("needs_follow_up") else " Keep tracking it here."
                    msg = (
                        f"Most recent: **{job}** at **{company}** — status: **{status}**{days_str}. "
                        f"{fu_hint}"
                    )
                else:
                    msg = (
                        "You don't have any tracked applications yet. "
                        "Say 'Mark as applied' on any job to start tracking."
                    )
            response = {"type": "recent_context", "intent": "recent_context", "message": msg}
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Bulk / unsafe apply — safety block: never auto-apply to all jobs
        if legacy_intent == "bulk_apply_unsafe":
            _bulk_msg = (
                "I can't apply to all jobs automatically. "
                "Please choose specific jobs to apply for, or narrow your search first.\n\n"
                "ما بقدر أقدّم على كل الوظائف تلقائيًا. "
                "اختار وظائف محددة أو ضيّق البحث أولاً."
            )
            response = {
                "type": "safety_block",
                "intent": "bulk_apply_unsafe",
                "message": _bulk_msg,
            }
            self._append_chat(user_id, "assistant", _bulk_msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Apply job — confirmation gate
        if intent == "apply_job":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            job_key = routed.tool_args.get("job_key", "")
            result = agent_runtime.handle_action(
                user_id=user_id, action="apply", job_key=job_key, source="chat",
            )
            response = {
                "type": "confirmation_required",
                "intent": "apply_job",
                "message": result.message or routed.confirmation_prompt or (
                    "To confirm: mark this job as applied and track it. "
                    "Reply YES to confirm or CANCEL to abort."
                ),
                "tool_args": routed.tool_args,
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, routed.source, profile=profile, runtime_result=result)

        # Save target role — "save X as target role" / "set X as target role"
        if legacy_intent == "save_target_role" and intent_result.extracted_role:
            role = intent_result.extracted_role.strip()
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            if role.lower() not in {str(r).lower() for r in target_roles}:
                target_roles.append(role)
                upsert_profile(user_id=user_id, updates={"target_roles": target_roles})
            response = {
                "type": "preferences_updated",
                "message": (
                    f"Got it — I've saved **{role}** as your target role. "
                    "I'll use it for all future job searches. "
                    "Say 'find jobs' whenever you're ready."
                ),
                "updated": {"target_roles": target_roles},
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Save job
        if legacy_intent == "save_job":
            # Ordinal save ("save the second job to my pipeline" / "احفظ ثاني وظيفة")
            # — resolve the Nth job from recent search results and persist it,
            # confirming only after persistence succeeds.
            _save_entities = getattr(intent_result, "entities", None) or {}
            _save_ordinal = _save_entities.get("ordinal")
            if _save_ordinal is not None:
                return self._finalize(
                    self._save_job_by_ordinal(user_id, int(_save_ordinal), profile),
                    self.SOURCE_KEYWORD, profile=profile,
                )

            # "Save — {title} at {company}" comes from a Rico-generated job card.
            # Resolve the job from recent results / persisted context so the user
            # is never asked for a URL to save something Rico itself produced.
            raw_title = (getattr(intent_result, "extracted_title", None) or "").strip()
            raw_company = (getattr(intent_result, "extracted_company", None) or "").strip()
            resolved = self._resolve_card_job(user_id, raw_title, raw_company)
            title = ((resolved.get("title") if resolved else None) or raw_title).strip()
            company = ((resolved.get("company") if resolved else None) or raw_company).strip()

            if title and company:
                apply_url = ((resolved.get("apply_url") if resolved else "") or "").strip()
                source_url = ((resolved.get("source_url") if resolved else "") or "").strip()
                alt_url = (
                    ((resolved.get("alt_url") or resolved.get("alt_link")) if resolved else "") or ""
                ).strip()
                # No direct apply URL → save with the best available source/alt link
                # and flag it for verification. Never block the save on a missing URL.
                effective_source = source_url or alt_url
                verification_status = (resolved or {}).get("verification_status") or "lead_needs_verification"
                if not apply_url and effective_source:
                    verification_status = "needs_source_verification"

                job_dict = {
                    "title": title,
                    "company": company,
                    "apply_url": apply_url,
                    "source_url": effective_source,
                    "alt_url": alt_url,
                    "verification_status": verification_status,
                }
                # Stable job_key (title+company) keeps runtime idempotency correct
                # and lets the runtime stamp record_interaction + set_lifecycle_status.
                job_key = self._derive_lifecycle_job_key(title, company)
                result = agent_runtime.handle_action(
                    user_id=user_id, action="save", job=job_dict, job_key=job_key, source="chat",
                )
                if result.ok:
                    success_msg = f"Saved — {title} at {company}. I'll keep it in your tracked jobs."
                else:
                    logger.warning(
                        "rico_chat: save action not ok user=%s title=%s err=%s",
                        user_id, title, result.error,
                    )
                    success_msg = (
                        f"Noted — {title} at {company} is in your tracker. "
                        "I'll keep it with your saved jobs."
                    )
                response = {
                    "type": "save_job",
                    "intent": "save_job",
                    "message": success_msg,
                    "entities": {"title": title, "company": company},
                    "verification_status": verification_status,
                }
                self._append_chat(user_id, "assistant", success_msg)
                return self._finalize(response, self.SOURCE_KEYWORD, profile=profile, runtime_result=result)

            # No title/company from card — try recently discussed/interacted job before router.
            _recent_resolved = None
            try:
                from src.repositories.user_job_context_repo import (
                    get_recently_discussed as _get_recently_discussed_sj,
                    get_recently_interacted as _get_recently_interacted_sj,
                )
                _recent_list = _get_recently_discussed_sj(user_id, limit=1)
                if not _recent_list:
                    _recent_list = _get_recently_interacted_sj(user_id, limit=1)
                if _recent_list:
                    _recent_resolved = _recent_list[0]
            except Exception:
                pass

            if _recent_resolved:
                title = (_recent_resolved.get("title") or "").strip()
                company = (_recent_resolved.get("company") or "").strip()
                if title and company:
                    apply_url = (_recent_resolved.get("apply_url") or "").strip()
                    source_url = (_recent_resolved.get("source_url") or "").strip()
                    job_dict = {
                        "title": title,
                        "company": company,
                        "apply_url": apply_url,
                        "source_url": source_url,
                        "verification_status": "lead_needs_verification",
                    }
                    job_key = self._derive_lifecycle_job_key(title, company)
                    result = agent_runtime.handle_action(
                        user_id=user_id, action="save", job=job_dict, job_key=job_key, source="chat",
                    )
                    success_msg = (
                        f"Saved — {title} at {company}. I'll keep it in your tracked jobs."
                        if result.ok else
                        f"Noted — {title} at {company} is in your tracker."
                    )
                    response = {
                        "type": "save_job",
                        "intent": "save_job",
                        "message": success_msg,
                        "entities": {"title": title, "company": company},
                    }
                    self._append_chat(user_id, "assistant", success_msg)
                    return self._finalize(response, self.SOURCE_KEYWORD, profile=profile, runtime_result=result)

            # Could not identify a job from the card or recent context — fall back to the tool router.
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            if routed.tool_name:
                job_key = routed.tool_args.get("job_key", "")
                result = agent_runtime.handle_action(
                    user_id=user_id, action="save", job_key=job_key, source="chat",
                )
                response = {
                    "type": "save_job",
                    "intent": "save_job",
                    "message": result.message,
                    "entities": routed.entities,
                }
                self._append_chat(user_id, "assistant", result.message)
                return self._finalize(response, routed.source, profile=profile, runtime_result=result)

        # Explain match
        if legacy_intent == "explain_match":
            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            if routed.tool_name:
                job_key = routed.tool_args.get("job_key", "")
                result = agent_runtime.handle_action(
                    user_id=user_id, action="why", job_key=job_key, source="chat",
                )
                response = {
                    "type": "explain_match",
                    "intent": "explain_match",
                    "message": result.message,
                }
                self._append_chat(user_id, "assistant", result.message)
                return self._finalize(response, routed.source, profile=profile, runtime_result=result)

        # Draft message / cover letter
        if legacy_intent == "draft_message":
            explicit_draft_job = explicit_draft_job or self._extract_explicit_draft_job_from_message(message)
            if explicit_draft_job:
                from src.message_generator import generate_message as _gen_msg

                draft_job, context_source = self._resolve_explicit_draft_job_context(user_id, explicit_draft_job)
                if not (self._job_context_value(draft_job, "title", "job_title") and self._job_context_value(draft_job, "company", "company_name")):
                    self._log_document_draft_context_source("clarification_required", draft_job)
                    msg = self._cover_letter_clarification_message(profile, draft_job)
                    self._append_chat(user_id, "assistant", msg)
                    return self._finalize(
                        {"type": "cover_letter_prompt", "message": msg, "next_action": "provide_job_for_cover_letter"},
                        self.SOURCE_KEYWORD,
                        profile=profile,
                    )

                self._log_document_draft_context_source(context_source, draft_job)
                cover = _gen_msg(draft_job, profile=profile)
                self._append_chat(user_id, "assistant", cover)
                return self._finalize(
                    {"type": "draft_message", "intent": "draft_message", "message": cover},
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )

            context = self._build_router_context(user_id, profile)
            routed = _route(message, user_id=user_id, context=context)
            if routed.tool_name:
                job_key = routed.tool_args.get("job_key", "")
                if job_key:
                    result = agent_runtime.handle_action(
                        user_id=user_id, action="draft", job_key=job_key, source="chat",
                    )
                    response = {
                        "type": "draft_message",
                        "intent": "draft_message",
                        "message": result.message,
                    }
                    self._append_chat(user_id, "assistant", result.message)
                    return self._finalize(response, routed.source, profile=profile, runtime_result=result)

            self._log_document_draft_context_source("clarification_required", {})
            msg = self._cover_letter_clarification_message(
                profile, arabic=self._is_arabic_text(message)
            )
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(
                {"type": "cover_letter_prompt", "message": msg, "next_action": "provide_job_for_cover_letter"},
                self.SOURCE_KEYWORD,
                profile=profile,
            )

        # Show latest pending application draft
        if legacy_intent == "show_draft":
            _drafts_sd = []
            try:
                from src.rico_db import RicoDB
                _drafts_sd = RicoDB().get_application_drafts(user_id, status="pending")
            except Exception:
                pass

            if not _drafts_sd:
                msg = (
                    "You don't have any pending application drafts yet. "
                    "Say **'prepare application'** for a saved job and I'll generate one."
                )
            else:
                _d = _drafts_sd[0]
                _d_title = _d.get("job_title") or "Unknown"
                _d_company = _d.get("company") or "Unknown"
                _d_cl = _d.get("cover_letter") or ""
                _d_preview = _d_cl[:400]
                msg = (
                    f"**Latest draft — {_d_title} at {_d_company}**\n\n"
                    f"**Cover letter:**\n{_d_preview}"
                    f"{'…' if len(_d_cl) > 400 else ''}\n\n"
                    "Your tailored CV is also ready. "
                    "Visit Applications (/applications) to review and approve."
                )
            response = {"type": "show_draft", "intent": "show_draft", "message": msg}
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Interview prep — use full AI chain (DeepSeek/OpenAI) for rich, personalised tips.
        # User message already stored in _process_message_inner; save_user_message=False.
        # Type is forced to "interview_prep" so the frontend renders the correct UI
        # regardless of which provider (or keyword fallback) handled the response.
        if legacy_intent == "interview_prep":
            _ip_resp = self._answer_with_ai_fallback(
                user_id=user_id,
                message=message,
                profile=profile,
                save_user_message=False,
            )
            _ip_resp["type"] = "interview_prep"
            return _ip_resp

        # Nonsense — do NOT search
        if legacy_intent == "nonsense":
            _ns_msg = (
                "لم أفهم رسالتك. جرّب أن تذكر المسمى الوظيفي الذي تبحث عنه، "
                "أو اكتب 'مساعدة' لرؤية الخيارات."
                if self._is_arabic_text(message) else
                "I could not understand that message. "
                "Try telling me a job role to search, or say 'help' for options."
            )
            response = {"type": "clarification", "message": _ns_msg}
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # ── Step 3: Unknown intent — try role classification, then clarify ───

        # Help-option phrase guard: phrases from the help menu ("Finding jobs",
        # "job search", etc.) are action selections, not job role titles.
        # Route them to a role-prompt so the user can name a concrete role.
        if message.strip().lower() in self._JOB_SEARCH_HELP_PHRASES:
            if has_cv:
                return self._finalize(
                    self._handle_profile_role_suggestions(profile, message),
                    self.SOURCE_KEYWORD,
                    profile=profile,
                )
            response = {
                "type": "clarification",
                "intent": "search_jobs",
                "message": (
                    "Sure — which role should I search for? "
                    "Tell me a specific role like 'HSE Manager' or "
                    "'Environmental Engineer', or upload your CV and I'll suggest roles from your background."
                ),
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Settings / notification commands ("enable telegram notifications",
        # "turn off email alerts") are neither job roles nor job searches.
        # Guide the user to Settings instead of emitting a role error.
        if _SETTINGS_COMMAND_RE.search(message):
            response = {
                "type": "settings_guidance",
                "intent": "settings_update",
                "message": (
                    "You can manage notifications — Telegram, WhatsApp and job "
                    "alerts — from your Settings page. Open Settings → Notifications "
                    "to turn them on or off."
                ),
            }
            self._append_chat(user_id, "assistant", response["message"])
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Only attempt role search if message looks like a plausible role (short text, no digits)
        if has_cv and self._looks_like_bare_target_role(message):
            logger.info(
                "bare_role_gate_pass user=%s msg_len=%d",
                user_id,
                len(message),
            )
            return self._finalize(
                self._classified_role_search(user_id, message.strip(), profile),
                self.SOURCE_KEYWORD,
                profile=profile,
            )
        logger.info(
            "bare_role_gate_reject_to_ai user=%s msg_len=%d",
            user_id,
            len(message),
        )

        # Final fallback: use AI for natural reply, but never treat as job search
        return self._answer_with_ai_fallback(
            user_id=user_id,
            message=message,
            profile=profile,
            save_user_message=False,
        )

    # ── New intent-specific handlers ─────────────────────────────────────────

    def _store_search_matches_context(
        self, user_id: str, formatted: list[dict[str, Any]],
        search_role: str = "", search_location: str = "",
    ) -> None:
        """Merge recent search results into context and persist to Neon."""
        try:
            ctx = self._get_recent_context(user_id)
            if search_role:
                ctx["recent_search_role"] = search_role
            if search_location:
                ctx["recent_search_location"] = search_location
            ctx["recent_search_matches"] = [
                {
                    "title": m.get("title", ""),
                    "company": m.get("company", ""),
                    "location": m.get("location", ""),
                    "apply_url": m.get("apply_url", ""),
                    "source_url": m.get("source_url", ""),
                    "link": m.get("apply_url", ""),
                    "verification_status": m.get("verification_status", "lead_needs_verification"),
                    # Extended fields for "tell me more about that job"
                    "employment_type": m.get("employment_type", ""),
                    "salary_string": m.get("salary_string", ""),
                    "description": (m.get("description") or "")[:400],
                    "why_this_fits": m.get("why_this_fits", ""),
                    "worth_checking": m.get("worth_checking", ""),
                }
                for m in formatted
            ]
            self._store_session_job_search_summary(
                user_id=user_id,
                ctx=ctx,
                formatted=formatted,
                search_role=search_role,
                search_location=search_location,
            )
            self._store_recent_context(user_id, ctx)
        except Exception:
            logger.debug("rico_chat: failed to store search matches context user=%s", user_id)

        # Persist to Neon so ordinal/detail follow-ups survive across workers
        # and RICO_MEMORY_BACKEND=postgres mode (where JSON context is disabled).
        try:
            from src.repositories.user_job_context_repo import upsert_matches
            upsert_matches(user_id, formatted)
        except Exception:
            logger.debug("rico_chat: failed to persist search matches to DB user=%s", user_id)

        # Auto-persist surfaced jobs into rico_job_recommendations so they appear on the
        # /flow board without requiring an explicit save. Uses status="opened" (not "saved")
        # to avoid subscription gating. The existing regression guard in
        # _persist_application_lifecycle_event prevents downgrading any job already at a
        # higher status (prepared/applied/interview/offer).
        try:
            for _m in formatted:
                _t = (_m.get("title") or "").strip()
                _c = (_m.get("company") or "").strip()
                if _t and _c:
                    self._persist_application_lifecycle_event(
                        user_id=user_id,
                        title=_t,
                        company=_c,
                        status="opened",
                        url=(_m.get("apply_url") or _m.get("source_url") or "").strip(),
                        location=str(_m.get("location") or "").strip(),
                    )
        except Exception:
            logger.debug("rico_chat: failed to auto-persist surfaced jobs user=%s", user_id)

        # Fire per-user Telegram notification for the top match (best-effort).
        # Opt-in check and rate guard happen inside send_user_notification.
        try:
            if formatted:
                from src.services.telegram_notifications import send_user_notification
                top = formatted[0]
                role = search_role or top.get("title", "your search")
                n = len(formatted)
                msg = (
                    f"🔔 <b>Rico found {n} new job match{'es' if n != 1 else ''}</b> for <b>{role}</b>.\n\n"
                    f"Open the Rico app to review and apply."
                )
                send_user_notification(
                    user_id=user_id,
                    message=msg,
                    alert_type="job_alert",
                    job=None,
                )
        except Exception:
            logger.debug("rico_chat: failed to send Telegram job-alert user=%s", user_id)

    def _store_session_job_search_summary(
        self,
        *,
        user_id: str,
        ctx: dict[str, Any],
        formatted: list[dict[str, Any]],
        search_role: str = "",
        search_location: str = "",
    ) -> None:
        """Remember a lightweight summary for current-session count follow-ups."""
        summary = self._build_session_job_search_summary(
            formatted=formatted,
            search_role=search_role,
            search_location=search_location,
        )
        history = ctx.get("session_job_search_history")
        if not isinstance(history, list):
            history = []
        history = [*history, summary][-_SESSION_JOB_SEARCH_HISTORY_LIMIT:]
        ctx["session_job_search_history"] = history
        ctx["last_job_search_summary"] = summary

        # Production may run with JSON context writes disabled. Keep a bounded
        # process-local copy so the active chat session can still answer
        # immediate follow-up questions without Redis or a schema change.
        session_history = _SESSION_JOB_SEARCH_HISTORY.get(user_id, [])
        _SESSION_JOB_SEARCH_HISTORY[user_id] = (
            [*session_history, summary][-_SESSION_JOB_SEARCH_HISTORY_LIMIT:]
        )

    @staticmethod
    def _build_session_job_search_summary(
        *,
        formatted: list[dict[str, Any]],
        search_role: str = "",
        search_location: str = "",
    ) -> dict[str, Any]:
        top = formatted[0] if formatted else {}
        top_match = {
            "title": top.get("title", ""),
            "company": top.get("company", ""),
            "location": top.get("location", ""),
        } if top else {}
        city = search_location or top_match.get("location", "")
        query = search_role or ""
        return {
            "count": len(formatted),
            "query": query,
            "role": query,
            "city": city,
            "top_match": top_match,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_session_job_search_history(self, user_id: str) -> list[dict[str, Any]]:
        ctx = self._get_recent_context(user_id)
        history = ctx.get("session_job_search_history")
        if isinstance(history, list):
            return [item for item in history if isinstance(item, dict)]
        matches = ctx.get("recent_search_matches") or []
        if isinstance(matches, list) and matches:
            return []
        return list(_SESSION_JOB_SEARCH_HISTORY.get(user_id, []))

    def _get_last_job_search_summary(self, user_id: str) -> dict[str, Any] | None:
        ctx = self._get_recent_context(user_id)
        summary = ctx.get("last_job_search_summary")
        if isinstance(summary, dict):
            return summary

        matches = ctx.get("recent_search_matches") or []
        if isinstance(matches, list) and matches:
            return self._build_session_job_search_summary(
                formatted=[m for m in matches if isinstance(m, dict)],
                search_role=str(ctx.get("recent_search_role") or ""),
                search_location=str(ctx.get("recent_search_location") or ""),
            )

        history = self._get_session_job_search_history(user_id)
        if history:
            return history[-1]
        return None

    @staticmethod
    def _get_status_rank(status: str) -> int:
        """Return numeric rank for application status to prevent regression.

        Higher rank = more advanced status.
        """
        STATUS_RANK = {
            "saved": 10,
            "opened": 20,
            "opened_external": 20,
            "prepared": 30,
            "applied": 40,
            "follow_up_due": 50,
            "interview": 60,
            "offer": 70,
            "rejected": 70,
            "decision_made": 80,
            "archived": 90,
        }
        return STATUS_RANK.get(status, 0)

    @staticmethod
    def _should_update_status(current_status: str, new_status: str) -> bool:
        """Return True if new_status should replace current_status.

        Only update if new status is equal or more advanced than current.
        Never downgrade from applied/interview/offer/rejected/decision_made.
        """
        current_rank = RicoChatAPI._get_status_rank(current_status)
        new_rank = RicoChatAPI._get_status_rank(new_status)
        return new_rank >= current_rank

    def _resolve_card_job(
        self, user_id: str, raw_title: str, raw_company: str
    ) -> Optional[dict[str, Any]]:
        """Resolve a job-card action back to the job Rico generated.

        When the user clicks "Save — {title} at {company}", the classifier's
        greedy "... at ..." split can mis-attribute the boundary (e.g. a company
        like "Careers at UAE"). This reconstructs the original "{title} at
        {company}" string and matches it against, in order:
          1. the last search-result payload (recent_search_matches in context),
          2. persisted user_job_context (find_by_title_company across splits),
          3. recently interacted / discussed jobs.
        Returns the matched job dict (title/company/apply_url/source_url/...) or
        None. Never raises.
        """
        raw_title = (raw_title or "").strip()
        raw_company = (raw_company or "").strip()
        if not raw_title and not raw_company:
            return None
        payload = (f"{raw_title} at {raw_company}" if raw_company else raw_title).strip().lower()

        def _matches(cand_title: str, cand_company: str) -> bool:
            ct = (cand_title or "").strip()
            cc = (cand_company or "").strip()
            if not ct:
                return False
            combined = (f"{ct} at {cc}" if cc else ct).strip().lower()
            if combined == payload:
                return True
            return payload.startswith(ct.lower()) and (not cc or payload.endswith(cc.lower()))

        # 1. Last search-result payload (in-memory context).
        try:
            ctx = self._get_recent_context(user_id)
            for m in ctx.get("recent_search_matches", []) or []:
                if _matches(m.get("title", ""), m.get("company", "")):
                    return dict(m)
        except Exception:
            logger.debug("rico_chat: card-job recent-match lookup failed user=%s", user_id, exc_info=True)

        # 2 + 3. Persisted context + recently interacted/discussed (survives restarts).
        try:
            from src.repositories.user_job_context_repo import (
                find_by_title_company,
                get_recently_interacted,
                get_recently_discussed,
            )
            # Try each plausible title/company boundary of the reconstructed payload
            # so "Careers at UAE" is matched as the company rather than truncated.
            full = f"{raw_title} at {raw_company}" if raw_company else raw_title
            parts = full.split(" at ")
            candidates: list[tuple[str, str]] = []
            if raw_title and raw_company:
                candidates.append((raw_title, raw_company))
            for i in range(1, len(parts)):
                t = " at ".join(parts[:i]).strip()
                c = " at ".join(parts[i:]).strip()
                if t and c and (t, c) not in candidates:
                    candidates.append((t, c))
            for t, c in candidates:
                row = find_by_title_company(user_id, t, c)
                if row:
                    return row
            for fn in (get_recently_interacted, get_recently_discussed):
                for row in fn(user_id) or []:
                    if _matches(row.get("title", ""), row.get("company", "")):
                        return row
        except Exception:
            logger.debug("rico_chat: card-job db lookup failed user=%s", user_id, exc_info=True)

        return None

    @staticmethod
    def _derive_lifecycle_job_key(title: str, company: str, url: str = "") -> str:
        """Derive stable job key for lifecycle events.

        Prefers title + company fallback to match mark_applied/create_manual behavior.
        Only uses URL if title/company are not available.
        """
        from src.applications import get_job_id
        # Prefer title/company fallback to match mark_applied behavior
        if title and company:
            return get_job_id({"title": title, "company": company})
        # Fallback to URL if title/company missing
        if url:
            return get_job_id({"link": url})
        # Last resort: title only
        return get_job_id({"title": title or "", "company": ""})

    def _get_existing_application_status(
        self, user_id: str, job_key: str
    ) -> Optional[str]:
        """Get current status for user/job from rico_job_recommendations.

        Returns None if no record exists.
        """
        try:
            from src.repositories.applications_repo import find_by_job_id
            existing = find_by_job_id(job_key, user_id)
            if existing:
                return existing.get("status")
        except Exception:
            pass
        return None

    def _verify_link_sync(self, url: str):
        """Run the async LinkVerifier from synchronous chat-handler code.

        Spawns a one-shot thread so asyncio.run() creates a fresh event loop
        without conflicting with uvicorn's event loop. Returns VerificationResult
        or None on any failure (import error, timeout, network error). Non-blocking
        from the caller's perspective — failures are swallowed silently.
        """
        if not url:
            return None
        try:
            import concurrent.futures
            from src.services.link_verifier import get_link_verifier

            def _run():
                import asyncio
                return asyncio.run(get_link_verifier().verify_link(url))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(_run).result(timeout=12)
        except Exception:
            return None

    def _recent_search_matches(self, user_id: str) -> list[dict[str, Any]]:
        """Return the user's recent search matches (session context, DB fallback).

        Shared by the ordinal "open the apply link for the Nth job" resolver so it
        sees the exact same ordered list the cards were rendered from.
        """
        try:
            ctx = self._get_recent_context(user_id)
            matches = ctx.get("recent_search_matches") or []
            if matches:
                return list(matches)
        except Exception:
            pass
        try:
            from src.repositories.user_job_context_repo import get_recent_matches as _grm
            return list(_grm(user_id, limit=10, max_age_minutes=60) or [])
        except Exception:
            return []

    def _apply_link_fallback_response(
        self, user_id: str, title: str, company: str,
        location: str = "", reason: str = "no_link",
    ) -> dict[str, Any]:
        """Safe fallback CTA when a job has no usable apply link.

        Returned instead of ever surfacing "Job payload is missing required 'link'
        field" to the user. Offers company-site / Google / LinkedIn search, copy,
        and save-to-pipeline — all plain search links, never scraped.
        """
        from src.services.job_link import build_link_fallback_cta

        label = f"**{title}**" + (f" at **{company}**" if company else "")
        if reason == "expired":
            lead = f"The apply link for {label} appears to be expired."
        elif reason == "google_intermediary_only":
            lead = f"I only have a search link for {label}, not a direct apply page."
        else:
            lead = f"I don't have a verified apply link for {label} yet."
        msg = f"{lead} Here are safe ways to apply:"

        response = {
            "type": "open_apply_link",
            "intent": "open_apply_link",
            "message": msg,
            "apply_url": None,
            "usable_link": "",
            "link_unavailable": True,
            "link_unavailable_reason": reason,
            "options": build_link_fallback_cta(title, company, location),
            "next_action": "apply_link_fallback",
        }
        self._append_chat(user_id, "assistant", msg)
        return response

    def _save_job_by_ordinal(
        self, user_id: str, ordinal: int, profile: Any,
    ) -> dict[str, Any]:
        """Save the first/second/Nth/last job from recent search results to the
        user's pipeline.

        - Resolves the job from ``recent_search_matches`` (the same ordered list
          the cards were rendered from), using the canonical link fields.
        - Persists via ``agent_runtime.handle_action(action="save")``.
        - Confirms ONLY after persistence succeeds; if it fails, says it could not
          be saved (never a false success).
        - If there is no recent search context, asks which job instead of
          pretending success.
        """
        from src.services.job_link import resolve_job_link

        matches = self._recent_search_matches(user_id)
        if not matches:
            msg = (
                "I don't have a recent job list to save from yet. Search for a role first, "
                "then say 'save the first job to my pipeline'."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "intent": "save_job", "message": msg}

        idx = len(matches) - 1 if ordinal == -1 else ordinal - 1
        if idx < 0 or idx >= len(matches):
            n = len(matches)
            msg = (
                f"You have {n} job{'s' if n != 1 else ''} in your recent list. "
                f"Which one should I save? Pick a number between 1 and {n}."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "intent": "save_job", "message": msg}

        job = matches[idx]
        title = str(job.get("title") or "").strip()
        company = str(job.get("company") or "").strip()
        if not title:
            msg = "I couldn't read that job's details to save it. Try 'save <title> at <company>'."
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "intent": "save_job", "message": msg}

        from src.services.job_save import resolve_save_decision

        link = resolve_job_link(job)
        # The job came from recent_search_matches — an untrusted origin under the
        # #747 trust gate. Resolve a trusted save identity + apply URL: a job with
        # no trusted apply link is still saved (as a lead), never with a claimed
        # verified link, and the bare LLM/session job_id is never used as the key.
        decision = resolve_save_decision(job, origin="recent_context")
        _label = f"**{title}**" + (f" at **{company}**" if company else "")
        job_dict = {
            "title": title,
            "company": company,
            # Only surface a trusted apply URL; otherwise leave it blank so the
            # saved record never carries an LLM/recent_context-generated link.
            "apply_url": decision.apply_url or "",
            "source_url": link["source_url"],
            "alt_url": link["alt_link"],
            "verification_status": link["verification_status"],
        }

        # Persist to the user-scoped, counted recommendations table (idempotent
        # upsert keyed on the trusted save identity) so the saved job actually
        # appears in the pipeline/application count. Previously the ordinal save
        # went only through the agent save_job tool (legacy JSON) and never
        # incremented the user's count.
        persisted = False
        try:
            from src.repositories import applications_repo
            persisted = bool(
                applications_repo.create(
                    job_id=decision.save_key,
                    title=title,
                    company=company,
                    url=decision.apply_url or "",
                    status="saved",
                    source="chat",
                    user_id=user_id,
                )
            )
        except Exception as exc:
            # Subscription gate / DB unavailable / any failure → user-safe message,
            # never a raw error or stack trace.
            detail = getattr(exc, "detail", None)
            safe = detail.get("message") if isinstance(detail, dict) else None
            logger.warning(
                "rico_chat: ordinal save persist failed user=%s err=%s",
                user_id, type(exc).__name__,
            )
            msg = safe or (
                f"I couldn't save {_label} to your pipeline right now. Please try again in a "
                "moment, or open your Applications tab to add it manually."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "save_job_error", "intent": "save_job", "message": msg,
                "entities": {"title": title, "company": company},
            }

        # Best-effort side-effects (audit log, learning signals, career memory).
        # Never let a side-effect failure turn a successful save into an error.
        try:
            agent_runtime.handle_action(
                user_id=user_id, action="save", job=job_dict,
                job_key=decision.save_key, source="chat",
            )
        except Exception:
            logger.debug("rico_chat: ordinal save side-effects failed", exc_info=True)

        if persisted:
            if decision.verified:
                msg = f"Saved {_label} to your pipeline. [View your pipeline →](/flow)"
            else:
                msg = (
                    f"Saved {_label} to your pipeline as a lead. I don't have a verified apply "
                    "link for it yet — open the role on the source site to confirm it's live "
                    "before applying. [View your pipeline →](/flow)"
                )
            response = {
                "type": "save_job", "intent": "save_job", "message": msg,
                "entities": {"title": title, "company": company},
                "verification_status": link["verification_status"],
                "verified_apply_link": decision.verified,
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Persistence reported no write — do NOT claim success.
        msg = (
            f"I couldn't save {_label} to your pipeline right now. Please try again in a moment, "
            "or open your Applications tab to add it manually."
        )
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "save_job_error", "intent": "save_job", "message": msg,
            "entities": {"title": title, "company": company},
        }

    def _open_apply_link_by_ordinal(
        self, user_id: str, ordinal: int, profile: Any,
    ) -> dict[str, Any]:
        """Resolve "open the apply link for the first/Nth/last job" from recent
        search context and open it via the canonical link field.

        Never raises a missing-link error: when there is no usable link it returns
        the safe fallback CTA.
        """
        from src.services.job_link import resolve_job_link

        matches = self._recent_search_matches(user_id)
        if not matches:
            msg = (
                "I don't have a recent job list to open yet. Search for a role first, "
                "then say 'open the apply link for the first job'."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "open_apply_link", "intent": "open_apply_link",
                "message": msg, "apply_url": None,
            }

        idx = len(matches) - 1 if ordinal == -1 else ordinal - 1
        if idx < 0 or idx >= len(matches):
            n = len(matches)
            msg = (
                f"You have {n} job{'s' if n != 1 else ''} in your recent list. "
                f"Pick a number between 1 and {n}."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "open_apply_link", "intent": "open_apply_link",
                "message": msg, "apply_url": None,
            }

        job = matches[idx]
        title = str(job.get("title") or "")
        company = str(job.get("company") or "")
        link = resolve_job_link(job)

        if not link["link_unavailable"] and link["usable_link"]:
            return self._handle_open_apply_link_path(
                user_id=user_id, title=title, company=company,
                apply_url=link["usable_link"], profile=profile,
            )

        return self._apply_link_fallback_response(
            user_id, title, company,
            location=str(job.get("location") or ""),
            reason=link["reason"],
        )

    def _handle_open_apply_link_path(
        self,
        user_id: str,
        title: str,
        company: str,
        apply_url: str,
        profile: Any,
    ) -> "dict[str, Any]":
        """Verify apply_url and return the complete open_apply_link response.

        Runs LinkVerifier, writes verification_status back to user_job_context,
        and returns either:
          - expired fallback response (EXPIRED / BLOCKED)
          - normal apply response (LIVE / NEEDS_REVIEW / timeout)
        Non-blocking: any verifier failure falls through to the normal path.
        """
        _vr = self._verify_link_sync(apply_url)
        _link_dead = False
        if _vr is not None:
            from src.services.link_verifier import LinkStatus as _LS
            if _vr.status in (_LS.EXPIRED, _LS.BLOCKED):
                _link_dead = True
                try:
                    from src.repositories.user_job_context_repo import (
                        update_verification_status as _uvs,
                    )
                    _uvs(user_id, title, company, "expired")
                except Exception:
                    pass
            elif _vr.status == _LS.LIVE:
                try:
                    from src.repositories.user_job_context_repo import (
                        update_verification_status as _uvs,
                    )
                    _uvs(user_id, title, company, "live_verified")
                except Exception:
                    pass
            # NEEDS_REVIEW / SOURCE_ONLY: uncertain — do not write live_verified

        if _link_dead:
            msg = (
                f"The apply link for **{title}** at **{company}** appears to be expired.\n\n"
                "You can:\n"
                "• **Refresh** — I can try to find an updated listing\n"
                "• **Dismiss** — Remove this role from your feed\n"
                "• **Search** — Look for similar roles right now"
            )
            response = {
                "type": "open_apply_link",
                "intent": "open_apply_link",
                "message": msg,
                "apply_url": None,
                "verification_status": "expired",
                "options": [
                    {"action": "refresh_link", "label": "Refresh",
                     "message": f"refresh link for {title} at {company}"},
                    {"action": "dismiss_job", "label": "Dismiss",
                     "message": f"dismiss {title} at {company}"},
                    {"action": "search_similar", "label": "Search similar",
                     "message": f"search similar to {title} at {company}"},
                ],
            }
            self._append_chat(user_id, "assistant", msg)
            return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

        # Link is live or unverified (NEEDS_REVIEW / timeout) — present normally.
        msg = f"Apply link for **{title}** at **{company}**: {apply_url}"
        self._persist_application_lifecycle_event(
            user_id=user_id, title=title, company=company,
            status="opened_external", url=apply_url,
        )
        self._store_recent_context(
            user_id,
            self._build_recent_application_context(
                title=title, company=company,
                status="opened_external", action="open_apply_link", link=apply_url,
            ),
        )
        try:
            from src.repositories.learning_repo import get_learning_repository
            get_learning_repository().infer_signals_from_job_action(
                user_id, "opened_external",
                {"title": title, "company": company, "apply_url": apply_url},
            )
        except Exception:
            pass
        response = {"type": "open_apply_link", "intent": "open_apply_link",
                    "message": msg, "apply_url": apply_url}
        self._append_chat(user_id, "assistant", msg)
        return self._finalize(response, self.SOURCE_KEYWORD, profile=profile)

    def _persist_application_lifecycle_event(
        self,
        user_id: str,
        title: str,
        company: str,
        status: str,
        url: str = "",
        location: str = "",
    ) -> bool:
        """Persist application lifecycle event to rico_job_recommendations.

        Safely wraps DB write so response flow is not blocked on failure.
        Uses stable job key to match mark_applied/create_manual behavior.
        Prevents status regression by checking existing status before upsert.

        Returns True when the /flow board row reflects at least ``status`` after
        this call — either because the row was written, or because an existing
        row is already at an equal/higher lifecycle tier. Returns False when the
        board write failed (DB error), so callers can warn the user instead of
        silently claiming success. Never raises.
        """
        board_written = False
        try:
            from src.repositories.applications_repo import create as _create_app

            # Derive stable job key (prefer title/company to match mark_applied)
            job_key = self._derive_lifecycle_job_key(title, company, url)

            # Check existing status to prevent regression
            existing_status = self._get_existing_application_status(user_id, job_key)

            # Only update if no record exists or new status is equal/more advanced
            if existing_status is None or self._should_update_status(existing_status, status):
                result = _create_app(
                    job_id=job_key,
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    status=status,
                    source="chat",
                    user_id=user_id,
                )
                board_written = result is not False
            else:
                # Existing status is already at a higher tier — the board already
                # reflects this lifecycle stage or beyond, so this is not a failure.
                board_written = True
                logger.debug(
                    "rico_chat: skipped lifecycle status update user=%s title=%s company=%s "
                    "existing_status=%s new_status=%s (would regress)",
                    user_id, title, company, existing_status, status
                )
        except Exception:
            # DB write failure should not block the response
            board_written = False
            logger.debug(
                "rico_chat: failed to persist lifecycle event user=%s title=%s company=%s status=%s",
                user_id, title, company, status
            )
        # Also stamp user_job_context with the lifecycle timestamp so Rico can
        # answer funnel-memory questions ("show jobs I opened but didn't apply to").
        try:
            from src.repositories.user_job_context_repo import set_lifecycle_status
            set_lifecycle_status(
                user_id=user_id,
                title=title,
                company=company,
                status=status,
                apply_url=url,
            )
        except Exception:
            logger.debug(
                "rico_chat: failed to stamp user_job_context lifecycle user=%s title=%s",
                user_id, title,
            )
        return board_written

    def _resolve_application_status_job(
        self,
        user_id: str,
        message: str,
    ) -> dict[str, Any] | None:
        """Resolve an "I applied to that job" report to recent Rico job context."""
        try:
            ctx = self._get_recent_context(user_id)
        except Exception:
            ctx = {}
        candidates: list[dict[str, Any]] = []

        if isinstance(ctx, dict):
            pending = ctx.get("_pending_application_send")
            if isinstance(pending, dict) and isinstance(pending.get("job"), dict):
                candidates.append(dict(pending["job"]))

            recent_app = ctx.get("recent_application")
            if isinstance(recent_app, dict):
                candidates.append(dict(recent_app))

            matches = ctx.get("recent_search_matches") or []
            if isinstance(matches, list):
                candidates.extend(dict(m) for m in matches if isinstance(m, dict))

        message_lower = (message or "").lower()
        for candidate in candidates:
            title = self._job_context_value(candidate, "title")
            company = self._job_context_value(candidate, "company")
            if (
                (title and title.lower() in message_lower)
                or (company and company.lower() in message_lower)
            ):
                return candidate

        if candidates:
            return candidates[0]

        try:
            from src.repositories.user_job_context_repo import (
                get_recently_discussed,
                get_recently_interacted,
            )

            for lookup in (get_recently_interacted, get_recently_discussed):
                rows = lookup(user_id) or []
                for row in rows:
                    if isinstance(row, dict) and (row.get("title") or row.get("company")):
                        return dict(row)
        except Exception:
            logger.debug(
                "rico_chat: failed to resolve applied-status job context user=%s",
                user_id,
                exc_info=True,
            )
        return None

    def _persist_confirmed_application_status(
        self,
        *,
        user_id: str,
        job: dict[str, Any],
    ) -> tuple[bool, str]:
        """Strictly persist an applied-status report before Rico confirms it."""
        title = self._job_context_value(job, "title")
        company = self._job_context_value(job, "company")
        location = self._job_context_value(job, "location")
        url = self._job_context_value(job, "apply_url", "link", "source_url")
        if not title or not company:
            return False, ""

        job_key = self._derive_lifecycle_job_key(title, company, url)
        try:
            existing_status = self._get_existing_application_status(user_id, job_key)
            if existing_status is None or self._should_update_status(existing_status, "applied"):
                from src.repositories.applications_repo import create as _create_app

                created = _create_app(
                    job_id=job_key,
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    status="applied",
                    source="chat",
                    user_id=user_id,
                )
                if not created:
                    return False, job_key

            from src.repositories.user_job_context_repo import set_lifecycle_status

            lifecycle_ok = set_lifecycle_status(
                user_id=user_id,
                title=title,
                company=company,
                status="applied",
                apply_url=url,
                note="User reported application submitted in chat.",
            )
            if not lifecycle_ok:
                return False, job_key

            return True, job_key
        except Exception:
            logger.exception(
                "rico_chat: failed strict applied-status persistence user=%s title=%s company=%s",
                user_id,
                title,
                company,
            )
            return False, job_key

    def _store_application_status_context(
        self,
        user_id: str,
        *,
        job: dict[str, Any],
        job_id: str,
    ) -> None:
        title = self._job_context_value(job, "title")
        company = self._job_context_value(job, "company")
        link = self._job_context_value(job, "apply_url", "link", "source_url")
        context = self._build_recent_application_context(
            title=title,
            company=company,
            status="applied",
            action="application_status_update",
            route="/applications",
            job_id=job_id,
            link=link,
        )
        try:
            existing = self._get_recent_context(user_id)
            if isinstance(existing, dict):
                existing.update(context)
                context = existing
        except Exception:
            pass
        self._store_recent_context(user_id, context)

    def _handle_application_status_update(
        self,
        user_id: str,
        message: str,
        profile: Any,
    ) -> dict[str, Any]:
        """Handle user reports that an application has already been submitted."""
        arabic = self._is_arabic_text(message)
        if str(user_id or "").startswith("public:"):
            msg = (
                "سجّل الدخول أولاً لكي أحفظ طلباتك في Applications."
                if arabic else
                "Sign in first so I can save this in Applications."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "clarification",
                "intent": "application_status_update",
                "message": msg,
                "next_action": "sign_in_required",
            }

        job = self._resolve_application_status_job(user_id, message)
        title = self._job_context_value(job or {}, "title")
        company = self._job_context_value(job or {}, "company")
        if not arabic and self._MANUAL_APPLICATION_LOG_QUESTION_RE.search(message or ""):
            if job and title and company:
                msg = (
                    "I can log that manually in Applications (/applications). "
                    f"If you already submitted **{title}** at **{company}**, reply "
                    "'mark it as applied' and I will save it after the database update succeeds."
                )
                next_action = "confirm_mark_applied"
            else:
                msg = (
                    "I can add a manually submitted application to Applications (/applications). "
                    "Send me the job title, company name, and source/link if available, "
                    "then I can mark it as applied."
                )
                next_action = "provide_manual_application_details"
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "manual_application_logging_guidance",
                "intent": "application_status_update",
                "message": msg,
                "job_title": title,
                "job_company": company,
                "target_route": "/applications",
                "next_action": next_action,
            }

        if not job or not title or not company:
            msg = (
                "أي وظيفة تقصد؟ أرسل اسم الوظيفة أو الشركة لكي أسجلها كطلب تم تقديمه."
                if arabic else
                "I can add it to Applications (/applications) as applied. "
                "Send me the job title, company name, and source/link if available."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "clarification",
                "intent": "application_status_update",
                "message": msg,
                "next_action": "choose_job_to_mark_applied",
            }

        persisted, job_id = self._persist_confirmed_application_status(user_id=user_id, job=job)
        if persisted:
            self._store_application_status_context(user_id, job=job, job_id=job_id)
            if arabic:
                msg = (
                    "تم تسجيل التقديم بنجاح. يمكنك متابعته من صفحة Applications (/applications).\n\n"
                    f"{title} - {company}"
                )
            else:
                msg = (
                    "Application marked as submitted. You can track it from Applications (/applications).\n\n"
                    f"{title} at {company}"
                )
            response_type = "application_status_update"
            next_action = "view_applications"
        else:
            if arabic:
                msg = (
                    "فهمت أنك قدمت على هذه الوظيفة، لكن لم أستطع حفظها الآن. "
                    "حاول مرة أخرى بعد قليل."
                )
            else:
                msg = (
                    "I understand you submitted this application, but I could not save it right now. "
                    "Please try again shortly."
                )
            response_type = "application_status_update_failed"
            next_action = "retry_application_status_update"

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": response_type,
            "intent": "application_status_update",
            "message": msg,
            "job_id": job_id,
            "job_title": title,
            "job_company": company,
            "job_status": "applied" if persisted else None,
            "target_route": "/applications",
            "next_action": next_action,
        }

    def _store_recent_context(self, user_id: str, context: dict[str, Any]) -> None:
        try:
            self.memory.set_context(user_id, "recent_context", context)
        except Exception:
            logger.warning("rico_chat: failed to store recent context for user=%s", user_id)

    def _get_recent_context(self, user_id: str) -> dict[str, Any]:
        try:
            return self.memory.get_context(user_id, "recent_context") or {}
        except Exception:
            return {}

    def _get_last_uploaded_document(self, user_id: str) -> dict[str, Any] | None:
        """Return the latest uploaded image/document transcript for a user.

        Tries the in-process recent_context fast-path first (works in json/local
        mode), then the durable DB store. The durable store is essential in
        production: ``RicoMemoryStore`` is a no-op under
        ``RICO_MEMORY_BACKEND=postgres`` and is wiped by restarts / multiple
        instances, so the transcript saved at upload time only survives in the DB.
        Returns ``None`` when no transcript with text is on record.
        """
        try:
            doc = (self._get_recent_context(user_id) or {}).get("last_uploaded_document")
            if isinstance(doc, dict) and str(doc.get("extracted_text") or "").strip():
                return doc
        except Exception:
            pass
        try:
            from src.repositories.uploaded_document_repo import get_last_uploaded_document
            durable = get_last_uploaded_document(user_id)
            if isinstance(durable, dict) and str(durable.get("extracted_text") or "").strip():
                return durable
        except Exception:
            pass
        return None

    # ── Recent-upload document context (TASK-030) ────────────────────────────

    _UPLOAD_DOC_QUERY_RE = re.compile(
        r"\b(?:what(?:\s+(?:did|do)\s+i)?\s+upload(?:ed)?|"
        r"what\s+(?:type|kind)\s+(?:is|of)\s+(?:the\s+)?(?:document|file)|"
        r"(?:document|file)\s+(?:type|kind)|"
        r"what\s+(?:is|was)\s+(?:the\s+)?(?:document|file)\s+(?:i\s+(?:just\s+)?)?upload(?:ed)?|"
        r"the\s+(?:document|file)\s+(?:i\s+)?upload(?:ed)|"
        r"(?:uploaded|just\s+sent)\s+(?:a\s+)?(?:document|file))\b",
        re.IGNORECASE,
    )

    def _get_recent_upload_document_reply(self, user_id: str, message: str) -> dict[str, Any] | None:
        """Return a document-context reply when the user explicitly asks about their last upload.

        Only fires for unambiguous document-meta queries (e.g. 'what did I upload?').
        Broader document analysis flows through the normal AI pipeline (TASK-030).
        """
        if not self._UPLOAD_DOC_QUERY_RE.search(message):
            return None
        try:
            ctx = self._get_recent_context(user_id)
            doc = ctx.get("last_uploaded_document")
            if not doc:
                return None
            label = doc.get("display_label") or doc.get("document_type", "document").replace("_", " ").title()
            filename = doc.get("filename") or "your file"
            pct = int(round(doc.get("confidence", 0) * 100))
            actions = doc.get("suggested_actions") or []
            actions_str = ""
            if actions:
                labels = [a.get("label", str(a)) if isinstance(a, dict) else str(a) for a in actions[:4]]
                actions_str = "\n\nHere's what I can help you with:\n" + "\n".join(f"- {lbl}" for lbl in labels)
            reply = (
                f"The last document you uploaded was **{filename}**, "
                f"which I identified as a **{label}** ({pct}% confidence).{actions_str}\n\n"
                "Would you like to do anything specific with it?"
            )
            self._append_chat(user_id, "assistant", reply)
            return {"type": "document_context", "message": reply}
        except Exception:
            return None

    @staticmethod
    def is_document_action_message(message: str) -> bool:
        """True when *message* is an uploaded-image/document action — describe /
        extract / summarize / read this document. Cheap (regex only); used by the
        chat service to detect document follow-ups before the AI/legacy split."""
        return bool(_DOC_FOLLOWUP_RE.search(message or ""))

    def handle_document_action(
        self, user_id: str, message: str, language: str | None = None
    ) -> dict[str, Any] | None:
        """Public entry point for the document-read path.

        Answers a document action ("summarize this document", "extract key
        information", "describe this image") from the stored transcript, but only
        when a FRESH uploaded document is on record for the user. Returns None when
        the message is not a document action, or when no fresh transcript exists,
        so the caller's normal routing proceeds unchanged.

        Invoked by chat_service BEFORE the AI/legacy intent split so summarize and
        extract always take the same deterministic document path — neither can be
        misrouted into the public job-listing CTA or an AI reply that never
        received the transcript.
        """
        if not self.is_document_action_message(message):
            return None
        if not self._get_last_uploaded_document(user_id):
            return None
        return self._handle_uploaded_document_followup(user_id, message, language)

    def _handle_uploaded_document_followup(
        self, user_id: str, message: str, language: str | None = None
    ) -> dict[str, Any] | None:
        """Answer an image/document ACTION ("describe this image", "extract key
        information", "summarize this document") from the stored transcript.

        Also handles the job-doc action buttons "Save as target job" and "Score
        against my CV" (Finding 3) — these run first so they are never mis-routed
        to the CV-builder or generic AI path.

        Runs BEFORE onboarding / CV-builder / AI routing so these requests can
        never be hijacked into a CV draft. The transcript is read from the durable
        store (survives ``RICO_MEMORY_BACKEND=postgres`` / restarts / multiple
        instances). Returns ``None`` only when the message is not such a request,
        so normal routing handles non-document chat.
        """
        # Finding 3: job-doc save / score actions — handle before the describe/summarize path.
        _job_action = self._handle_job_doc_action(user_id, message, language)
        if _job_action is not None:
            return _job_action

        if not _DOC_FOLLOWUP_RE.search(message or ""):
            return None

        doc = self._get_last_uploaded_document(user_id)
        text = str((doc or {}).get("extracted_text") or "").strip() if doc else ""
        label = str((doc or {}).get("display_label") or (doc or {}).get("document_type") or "document")
        _is_ar = (language == "ar") or bool(re.search(r"[؀-ۿ]", message or ""))

        if not text:
            # A document action with no readable transcript on record. Be honest —
            # never hijack into a CV draft, never claim to have read something.
            reply = (
                "لا يوجد لدي مستند مقروء منك حتى الآن. ارفع لقطة شاشة واضحة أو ملف PDF "
                "وسأقرأه ثم أساعدك في تلخيصه أو استخراج أهم المعلومات منه."
                if _is_ar else
                "I don't have a readable document from you yet. Upload a clear "
                "screenshot or a PDF and I'll read it, then I can summarize it or "
                "pull out the key information for you."
            )
            self._append_chat(user_id, "assistant", reply)
            return {"type": "document_context", "message": reply, "success": True}

        # We have the transcript → let the AI answer the specific request from it.
        profile = self._resolve_profile(user_id)
        augmented = (
            f"{message}\n\n"
            f"[Transcribed text of the {label} the user just uploaded — file "
            f"'{doc.get('filename') or 'upload'}']\n"
            f'"""\n{text[:4000]}\n"""\n'
            "Answer the user's request using ONLY the transcribed text above. Do not "
            "invent details, and do not produce a CV or resume unless the transcribed "
            "text itself is a CV."
        )
        return self._answer_with_ai_fallback(
            user_id, message, profile,
            save_user_message=True, language=language, prompt_override=augmented,
        )

    # ── Finding 3: job-doc save / score actions ───────────────────────────────

    def _handle_job_doc_action(
        self, user_id: str, message: str, language: str | None,
    ) -> "dict[str, Any] | None":
        """Intercept 'Save as target job' and 'Score against my CV' when a job
        description document is the most recently uploaded file.

        Returns None when the message is not one of these actions so that normal
        routing continues. Called before the describe/summarize path so these
        actions are never mis-routed into a CV draft or generic AI reply.
        """
        is_save = bool(_JOB_DOC_SAVE_RE.search(message or ""))
        is_score = bool(_JOB_DOC_SCORE_RE.search(message or ""))
        if not is_save and not is_score:
            return None

        _is_ar = (language == "ar") or bool(re.search(r"[؀-ۿ]", message or ""))
        doc = self._get_last_uploaded_document(user_id)
        if not doc:
            reply = (
                "لا يوجد لدي مستند مرفوع منك حتى الآن. "
                "ارفع وصف الوظيفة أو لقطة الشاشة أولاً."
                if _is_ar else
                "I don't have an uploaded job document yet. "
                "Upload the job description or screenshot first, then I can save or score it."
            )
            self._append_chat(user_id, "assistant", reply)
            return {"type": "document_context", "message": reply, "success": False}

        text = str(doc.get("extracted_text") or "").strip()
        if not text:
            # Image uploaded but OCR hasn't run yet — guide user to extract first.
            reply = (
                "الصورة المرفوعة لم تُقرأ بعد. "
                "اضغط على **'استخراج النص (OCR)'** أو **'وصف هذه الصورة'** أولاً — "
                "بعد قراءتها سأتمكن من حفظها كوظيفة مستهدفة أو تقييمها مقابل سيرتك الذاتية."
                if _is_ar else
                "The uploaded image hasn't been read yet. "
                "First click **'Extract text (OCR)'** or **'Describe this image'** — "
                "once I've read it, I can save it as a target job or score it against your CV."
            )
            self._append_chat(user_id, "assistant", reply)
            return {"type": "document_context", "message": reply, "success": False}

        if is_save:
            return self._save_uploaded_job_to_pipeline(user_id, doc, text, _is_ar)
        return self._score_uploaded_job_against_cv(user_id, doc, text, _is_ar, language)

    @staticmethod
    def _extract_job_meta_from_text(text: str) -> "tuple[str, str]":
        """Best-effort title and company extraction from a job description transcript."""
        title_m = _JOB_TITLE_FROM_TEXT_RE.search(text[:1000])
        company_m = _JOB_COMPANY_FROM_TEXT_RE.search(text[:1000])
        title = title_m.group(1).strip() if title_m else ""
        company = company_m.group(1).strip() if company_m else ""
        if not title:
            for line in text[:500].splitlines():
                line = line.strip()
                if 3 <= len(line) <= 80:
                    title = line
                    break
        return title or "Uploaded job description", company

    def _save_uploaded_job_to_pipeline(
        self, user_id: str, doc: "dict[str, Any]", text: str, is_ar: bool,
    ) -> "dict[str, Any]":
        """Persist the uploaded job description as a lead in the user's pipeline."""
        title, company = self._extract_job_meta_from_text(text)
        from src.services.job_save import resolve_save_decision
        job_dict = {"title": title, "company": company, "apply_url": "", "source_url": ""}
        decision = resolve_save_decision(job_dict, origin="upload")
        _label = f"**{title}**" + (f" at **{company}**" if company else "")

        persisted = False
        try:
            from src.repositories import applications_repo
            persisted = bool(
                applications_repo.create(
                    job_id=decision.save_key,
                    title=title,
                    company=company,
                    url="",
                    status="saved",
                    source="upload",
                    user_id=user_id,
                )
            )
        except Exception as exc:
            detail = getattr(exc, "detail", None)
            safe = detail.get("message") if isinstance(detail, dict) else None
            logger.warning(
                "rico_chat: upload job save failed user=%s err=%s",
                user_id, type(exc).__name__,
            )
            msg = safe or (
                f"لم أتمكن من حفظ الوظيفة في خط الأنابيب. حاول مرة أخرى لاحقاً."
                if is_ar else
                f"I couldn't save {_label} to your pipeline right now. "
                "Please try again or add it manually in your Applications tab."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "save_job_error", "intent": "save_uploaded_job", "message": msg}

        if persisted:
            msg = (
                f"تم حفظ **{title}** في خط أنابيب الوظائف كفرصة. "
                "لا يوجد رابط تقديم موثوق بعد — ستجده في قائمة الوظائف المحفوظة."
                if is_ar else
                f"Saved {_label} to your pipeline as a lead. "
                "There's no verified apply link yet — you'll find it in your tracked jobs "
                "and can add the link manually."
            )
        else:
            msg = (
                f"**{title}** موجود بالفعل في خط الأنابيب."
                if is_ar else
                f"{_label} is already in your pipeline."
            )
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "save_job",
            "intent": "save_uploaded_job",
            "message": msg,
            "entities": {"title": title, "company": company, "source": "upload"},
        }

    def _score_uploaded_job_against_cv(
        self, user_id: str, doc: "dict[str, Any]", text: str,
        is_ar: bool, language: "str | None",
    ) -> "dict[str, Any]":
        """Score the uploaded job description against the user's stored CV text."""
        cv_text = ""
        try:
            from src.rico_db import RicoDB
            _db = RicoDB()
            bundle = _db.get_user_bundle(user_id)
            if bundle:
                cv_text = (bundle.get("cv_text") or "").strip()
        except Exception:
            pass

        if not cv_text:
            profile = self._resolve_profile(user_id)
            cv_text = (
                self._profile_value(profile, "cv_text")
                or self._profile_value(profile, "pasted_cv_text")
                or ""
            ).strip()

        if not cv_text:
            msg = (
                "أحتاج إلى سيرتك الذاتية أولاً. "
                "ارفعها من ملفك الشخصي أو الصقها في المحادثة."
                if is_ar else
                "I need your CV to score this job against it. "
                "Upload your CV from your profile or paste it here, then ask again."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "clarification",
                "intent": "score_job_vs_cv",
                "message": msg,
                "next_action": "upload_cv",
            }

        filename = str(doc.get("filename") or "uploaded document")
        augmented = (
            "Score this job description against my current CV and give a detailed fit analysis.\n\n"
            f"[Job description — '{filename}']\n\"\"\"\n{text[:3000]}\n\"\"\"\n\n"
            f"[My current CV]\n\"\"\"\n{cv_text[:3000]}\n\"\"\"\n\n"
            "Provide:\n"
            "1. Overall fit score (0–100) with a brief justification.\n"
            "2. Strong matches — skills, experience, or qualifications that align well.\n"
            "3. Gaps — what the job requires that the CV currently lacks.\n"
            "4. Recommendation: worth applying? What to tailor?\n"
            "Use ONLY the texts above. Do not invent details."
        )
        profile = self._resolve_profile(user_id)
        return self._answer_with_ai_fallback(
            user_id,
            message="Score this job description against my current CV.",
            profile=profile,
            save_user_message=True,
            language=language,
            prompt_override=augmented,
        )

    # ── Letter-choice resolver (BUG-02) ──────────────────────────────────────

    def _save_pending_options(self, user_id: str, options: list) -> None:
        """Persist the options list from the last response for letter-choice resolution."""
        if not options or not isinstance(options, list):
            return
        try:
            ctx = self._get_recent_context(user_id)
            ctx["_pending_options"] = [
                {
                    "action": str(o.get("action") or ""),
                    "message": str(o.get("message") or ""),
                    "label": str(o.get("label") or ""),
                }
                for o in options
                if isinstance(o, dict)
            ]
            self._store_recent_context(user_id, ctx)
        except Exception:
            pass

    @staticmethod
    def _inject_option_buttons(
        result: "dict[str, Any]",
        options: "list[dict[str, Any]]",
    ) -> "dict[str, Any]":
        """Mirror letter-choice options as agentic_ui chat_continue buttons (audit 1-A).

        Buttons send the full option message so clicking has the same effect as typing
        the letter, but works without relying on _pending_options still being valid.
        """
        import uuid as _uuid
        from src.schemas.chat import RicoChatAction, RicoActionKind, RicoAgenticUi

        _letters = "ABCD"
        new_actions: list = []
        for i, opt in enumerate(options[:4]):
            if not isinstance(opt, dict):
                continue
            label = str(opt.get("label") or "").strip()
            message = str(opt.get("message") or opt.get("label") or "").strip()
            if not label or not message:
                continue
            prefix = f"{_letters[i]}) "
            btn_label = label if label.upper().startswith(prefix.upper()) else f"{prefix}{label}"
            new_actions.append(
                RicoChatAction(
                    id=f"opt-{_uuid.uuid4().hex[:8]}",
                    label=btn_label,
                    kind=RicoActionKind.chat_continue,
                    payload={"message": message},
                )
            )

        if not new_actions:
            return result

        existing_ui = result.get("agentic_ui")
        if isinstance(existing_ui, RicoAgenticUi):
            updated_ui = existing_ui.model_copy(
                update={"actions": list(existing_ui.actions) + new_actions}
            )
        else:
            updated_ui = RicoAgenticUi(actions=new_actions)

        return {**result, "agentic_ui": updated_ui}

    def _resolve_letter_choice(self, user_id: str, message: str) -> str | None:
        """Map a single-letter (A/B/C/D) or single-digit (1/2/3/4) reply to the
        nth pending option's message.

        Returns the chosen option's message string, or None when:
          - message is not exactly one letter A–D or digit 1–9,
          - no pending options are stored, or
          - the index is out of range.

        Consuming the options list clears it so a second bare choice does not
        accidentally re-use the same menu.
        """
        stripped = message.strip()
        if _LETTER_CHOICE_RE.match(stripped):
            idx = ord(stripped[0].upper()) - ord("A")   # A→0, B→1, C→2, D→3
        elif _NUMBER_CHOICE_RE.match(stripped):
            idx = int(stripped[0]) - 1   # "1"→0, "2"→1, "3"→2, …
        else:
            return None
        try:
            ctx = self._get_recent_context(user_id)
            options: list = ctx.get("_pending_options") or []
            if not options or idx >= len(options):
                return None
            chosen = options[idx]
            chosen_message = chosen.get("message") or chosen.get("label") or ""
            if not chosen_message:
                return None
            # Consume: clear so the next bare letter doesn't re-use this menu.
            ctx["_pending_options"] = []
            self._store_recent_context(user_id, ctx)
            return chosen_message
        except Exception:
            return None

    @staticmethod
    def _extract_rec_url(rec: dict[str, Any]) -> str:
        """Return the best available apply URL from a recommendation record.

        Checks top-level fields first (link, apply_url, job_apply_link, apply_link,
        source_url), then falls back to the same keys inside a nested 'job_data' or
        'job' sub-dict for records that were not fully flattened by get_recommendations.
        """
        top_level_url = (
            rec.get("link")
            or rec.get("apply_url")
            or rec.get("job_apply_link")
            or rec.get("apply_link")
            or rec.get("source_url")
            or ""
        )
        if top_level_url:
            return str(top_level_url).strip()
        nested = rec.get("job_data") or rec.get("job") or {}
        if isinstance(nested, dict):
            return str(
                nested.get("link")
                or nested.get("apply_url")
                or nested.get("job_apply_link")
                or nested.get("apply_link")
                or nested.get("source_url")
                or ""
            ).strip()
        return ""

    def _has_apply_evidence(self, user_id: str, title: str, company: str) -> bool:
        """Return True when there is evidence the user opened an apply link for title/company.

        Evidence sources (checked in order):
          1. Recent context: `_pending_confirm_apply` flag set by the clarification response.
          2. Recent context: a recorded `link` for a matching job (set by open_apply_link handler).
        """
        try:
            ctx = self._get_recent_context(user_id)
            # Explicit manual-confirmation flag set when we returned a clarification
            pending = ctx.get("_pending_confirm_apply") or {}
            if (
                pending.get("title", "").lower() == title.lower()
                and pending.get("company", "").lower() == company.lower()
            ):
                return True
            # URL evidence from a prior open_apply_link or application_tracking action
            recent_app = ctx.get("recent_application") or {}
            if (
                title.lower() in (recent_app.get("title") or "").lower()
                and company.lower() in (recent_app.get("company") or "").lower()
                and recent_app.get("link")
            ):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _application_status_label(status: str | None) -> str:
        labels = {
            "saved": "saved for review",
            "opened": "opened",
            "opened_external": "opened externally",
            "applied": "applied",
            "interview": "interview stage",
            "rejected": "rejected",
            "offer": "offer stage",
            "decision_made": "closed",
        }
        return labels.get((status or "").strip().lower(), status or "tracked")

    def _build_recent_application_context(
        self,
        *,
        title: str,
        company: str,
        status: str,
        action: str,
        route: str = "/command",
        job_id: str | None = None,
        link: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        status_label = self._application_status_label(status)
        return {
            "type": "application",
            "recent_job": title,
            "recent_company": company,
            "recent_application": {
                "job_id": job_id,
                "title": title,
                "company": company,
                "status": status,
                "status_label": status_label,
                "link": link or "",
                "route": route,
                "last_action": action,
                "updated_at": now,
            },
            "recent_status": status,
            "recent_status_label": status_label,
            "recent_route": route,
            "recent_action": action,
            "timeline": [
                {
                    "status": status,
                    "label": status_label,
                    "action": action,
                    "at": now,
                }
            ],
        }

    @staticmethod
    def _parse_application_dt(app: dict[str, Any]) -> datetime:
        raw = app.get("date_updated") or app.get("date_applied") or ""
        if raw:
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                pass
        return datetime.min.replace(tzinfo=timezone.utc)

    def _sort_applications_recent(self, apps: list[dict]) -> list[dict]:
        return sorted(apps, key=self._parse_application_dt, reverse=True)

    def _enrich_applications(self, apps: list[dict]) -> list[dict]:
        """Add days_since_applied, days_since_update, needs_follow_up to each app dict."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result = []
        for app in apps:
            enriched = dict(app)
            days_applied: int | None = None
            raw_applied = app.get("date_applied")
            if raw_applied:
                try:
                    dt = datetime.fromisoformat(raw_applied.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    days_applied = (now - dt).days
                except (ValueError, TypeError):
                    pass
            days_updated: int | None = None
            raw_updated = app.get("date_updated")
            if raw_updated:
                try:
                    dt = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    days_updated = (now - dt).days
                except (ValueError, TypeError):
                    pass
            enriched["days_since_applied"] = days_applied
            enriched["days_since_update"] = days_updated
            # Follow-up needed: applied/opened status with no update for 7+ days
            enriched["needs_follow_up"] = (
                app.get("status") in ("applied", "opened")
                and days_updated is not None
                and days_updated >= 7
            )
            enriched["status_label"] = self._application_status_label(app.get("status"))
            result.append(enriched)
        return result

    def _build_recent_context_message(self, ctx: dict[str, Any]) -> str:
        app = ctx.get("recent_application") if isinstance(ctx.get("recent_application"), dict) else {}
        job = app.get("title") or ctx.get("recent_job") or "Unknown"
        company = app.get("company") or ctx.get("recent_company") or "Unknown"
        status = app.get("status_label") or ctx.get("recent_status_label") or self._application_status_label(ctx.get("recent_status"))
        route = app.get("route") or ctx.get("recent_route") or "/command"
        action = app.get("last_action") or ctx.get("recent_action") or "tracked"
        updated_at = app.get("updated_at")

        time_hint = ""
        if updated_at:
            try:
                dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days = (datetime.now(timezone.utc) - dt).days
                if days == 0:
                    time_hint = " Updated today."
                elif days > 0:
                    time_hint = f" Updated {days} day{'s' if days != 1 else ''} ago."
            except (TypeError, ValueError):
                pass

        next_step = "Next step: update the status when you get a reply."
        if (app.get("status") or ctx.get("recent_status")) == "applied":
            next_step = "Next step: follow up if there is no response after 7 days."
        elif (app.get("status") or ctx.get("recent_status")) == "saved":
            next_step = "Next step: review the role and mark it as applied when you submit."

        return (
            f"Your latest application context is **{job}** at **{company}**. "
            f"It is currently **{status}** from the last action: {action}.{time_hint} "
            f"{next_step}"
        )

    def _format_application_line(self, app: dict) -> str:
        """Render one tracked application as a markdown bullet using the available
        title, company, status, date and apply/source URL."""
        title = app.get("title") or app.get("role") or "Unknown role"
        company = app.get("company") or ""
        status = app.get("status") or ""
        label = app.get("status_label") or self._application_status_label(status)
        url = app.get("apply_url") or app.get("link") or app.get("source_url") or ""
        date_raw = (
            app.get("date_applied")
            or app.get("applied_at")
            or app.get("date_updated")
            or app.get("saved_at")
            or ""
        )
        line = f"• **{title}**"
        if company:
            line += f" at **{company}**"
        if label:
            line += f" — `{label}`"
        if date_raw:
            line += f" · {str(date_raw)[:10]}"
        if url:
            line += f" — [Open]({url})"
        return line

    def _build_tracking_message(self, apps: list[dict], stats: dict, arabic: bool = False) -> str:
        """Build a summary header followed by an itemized list of applications."""
        total = len(apps)
        if total == 0:
            # Honest fallback: if summary stats indicate applications exist but no
            # detailed rows are available to itemize, say so and route to the page.
            try:
                summary_total = int((stats or {}).get("total") or 0)
            except (TypeError, ValueError):
                summary_total = 0
            if summary_total > 0:
                if arabic:
                    return (
                        f"لديك {summary_total} طلب تقديم مسجَّل، لكن لا يمكنني تحميل السجلات "
                        "التفصيلية الآن. افتح صفحة **الطلبات** لرؤيتها."
                    )
                return (
                    f"You have {summary_total} tracked application"
                    f"{'s' if summary_total != 1 else ''}, but I can't load the detailed "
                    "records right now. Open your **Applications** page to see them."
                )
            if arabic:
                return (
                    "لا توجد طلبات تقديم مسجَّلة بعد. "
                    "عندما تتقدم لوظيفة عبر Rico، سأتابعها هنا. "
                    "يمكنك أيضًا قول 'تم التقديم' على أي وظيفة."
                )
            return (
                "You have no tracked applications yet. "
                "When you apply to a job through Rico, I will track it here. "
                "You can also say 'mark as applied' on any job."
            )

        by_status: dict[str, list[dict]] = {}
        for app in apps:
            by_status.setdefault(app.get("status", "unknown"), []).append(app)

        offers = by_status.get("offer", [])
        interviews = by_status.get("interview", [])
        applied = by_status.get("applied", []) + by_status.get("opened", [])
        saved = by_status.get("saved", [])
        rejected = by_status.get("rejected", [])
        follow_up = [a for a in apps if a.get("needs_follow_up")]

        stage_parts = []
        if offers:
            stage_parts.append(f"{len(offers)} offer")
        if interviews:
            stage_parts.append(f"{len(interviews)} interview")
        if applied:
            stage_parts.append(f"{len(applied)} applied")
        if saved:
            stage_parts.append(f"{len(saved)} saved")
        if rejected:
            stage_parts.append(f"{len(rejected)} rejected")
        stage_line = ", ".join(stage_parts) if stage_parts else f"{total} tracked"

        sentences = [
            f"You have {total} tracked application{'s' if total != 1 else ''}: {stage_line}."
        ]

        active = offers + interviews
        if active:
            names = [
                f"**{a.get('title', 'Unknown')}** at **{a.get('company', 'Unknown')}**"
                for a in active[:3]
            ]
            sentences.append(f"Active: {', '.join(names)}.")

        if follow_up:
            fu_companies = [f"**{a.get('company', 'Unknown')}**" for a in follow_up[:3]]
            suffix = f" (+{len(follow_up) - 3} more)" if len(follow_up) > 3 else ""
            sentences.append(
                f"{len(follow_up)} application{'s' if len(follow_up) != 1 else ''} "
                f"may need a follow-up (no update in 7+ days): "
                f"{', '.join(fu_companies)}{suffix}."
            )

        header = " ".join(sentences)

        # Itemized list — the actual applications. Replaces the old circular prompt
        # ("Ask me to 'list my applications'…") that produced a dead-end for a user
        # who had just asked to list them.
        lines = [self._format_application_line(a) for a in apps[:10]]
        body = "\n".join(lines)
        if total > 10:
            body += f"\n_…and {total - 10} more. Open your **Applications** page to see all._"
        return f"{header}\n\n{body}"

    def _handle_subscription_plans(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Return Rico subscription plans and pricing."""
        # Try to get user's current plan from subscription repo
        try:
            from src.repositories.subscription_repo import get_subscription
            sub = get_subscription(user_id)
            current_plan = (sub.get("plan") or "free") if sub else "free"
        except Exception:
            current_plan = "free"

        plans_msg = (
            "ريكو يوفر خطتين:\n"
            "• **Pro** — 29 درهم/شهرياً (محادثات ذكاء اصطناعي غير محدودة، تنبيهات ذات أولوية، تحسين السيرة الذاتية)\n"
            "• **Premium** — 49 درهم/شهرياً (كل مزايا Pro + تحضير للمقابلات، خطابات تقديم، دعم مخصص)\n\n"
            "اشترك على ricohunt.com/subscription أو اسألني للتفاصيل."
            if self._is_arabic_text(message) else
            "Rico has two plans:\n"
            "• **Pro** — AED 29/month (unlimited AI chats, priority alerts, CV optimization)\n"
            "• **Premium** — AED 49/month (Pro + interview prep, cover letters, dedicated support)\n\n"
            "Subscribe at ricohunt.com/subscription or ask me for details."
        )
        return {
            "type": "subscription.show_plans",
            "message": plans_msg,
            "plans": [
                {"name": "Pro", "price_aed": 29, "period": "monthly"},
                {"name": "Premium", "price_aed": 49, "period": "monthly"},
            ],
            "current_plan": current_plan,
            "next_action": "choose_plan_or_continue",
            "options": [
                {"action": "subscription_pro_details", "label": "Tell me more about Pro", "message": "Tell me more about the Rico Pro plan"},
                {"action": "subscription_premium_details", "label": "Tell me more about Premium", "message": "Tell me more about the Rico Premium plan"},
                {"action": "subscription_how_to", "label": "How do I subscribe?", "message": "How do I subscribe to Rico Pro or Premium?"},
            ],
        }

    def _handle_learning_profile_summary(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Show the user what Rico has learned from their behavioral signals.

        Reads top preferences from LearningRepository and formats a plain-language
        summary so users can verify what Rico has inferred and correct mistakes.
        """
        arabic = self._is_arabic_text(message)
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            roles = [r for r, _ in _lr.get_top_preferences(user_id, "role", limit=5)]
            locs = [loc for loc, _ in _lr.get_top_preferences(user_id, "location", limit=3)]
            skills = [s for s, _ in _lr.get_top_preferences(user_id, "skill", limit=6)]
            avoided = [
                c for c, w in _lr.get_top_preferences(user_id, "company", limit=5) if w < 0
            ]

            if not any([roles, locs, skills, avoided]):
                msg = (
                    "لم أتعلم أي شيء محدد بعد — أبني ملف تفضيلاتك من أفعالك. "
                    "احفظ، تقدّم، أو تجاوز وظائف وسأبدأ بتخصيص النتائج."
                    if arabic else
                    "I haven't learned anything specific yet — I build your preference profile "
                    "from your actions. Save, apply, or skip jobs and I'll start personalising results."
                )
            elif arabic:
                lines = ["هذا ما تعلمته من أفعالك حتى الآن:\n"]
                if roles:
                    lines.append(f"**الأدوار المفضلة:** {', '.join(roles)}")
                if locs:
                    lines.append(f"**المواقع المفضلة:** {', '.join(locs)}")
                if skills:
                    lines.append(f"**المهارات ذات الصلة:** {', '.join(skills)}")
                if avoided:
                    lines.append(f"**شركات يُفضّل تجنبها:** {', '.join(avoided)}")
                lines.append(
                    "\nهذا يحدد شكل ترتيب الوظائف في نتائجك. "
                    "أخبرني إذا رأيت شيئاً غير صحيح وسأصححه."
                )
                msg = "\n".join(lines)
            else:
                lines = ["Here is what I've learned from your actions so far:\n"]
                if roles:
                    lines.append(f"**Preferred roles:** {', '.join(roles)}")
                if locs:
                    lines.append(f"**Preferred locations:** {', '.join(locs)}")
                if skills:
                    lines.append(f"**Relevant skills:** {', '.join(skills)}")
                if avoided:
                    lines.append(f"**Companies to avoid:** {', '.join(avoided)}")
                lines.append(
                    "\nThis shapes which jobs float to the top of your results. "
                    "Tell me if anything looks wrong and I'll correct it."
                )
                msg = "\n".join(lines)
        except Exception:
            msg = (
                "تعذر استرجاع ملف تفضيلاتك الآن. حاول مرة أخرى بعد قليل — بياناتك بأمان."
                if arabic else
                "I couldn't retrieve your preference profile right now. "
                "Try again in a moment — your data is safe."
            )

        self._append_chat(user_id, "assistant", msg)
        return {"type": "learning_profile_summary", "message": msg}

    _PENDING_DELETE_SAVED_JOBS_KEY: str = "pending_delete_saved_jobs"
    _PENDING_PIPELINE_RESET_KEY: str = "pending_pipeline_reset"

    def _handle_pipeline_reset(self, user_id: str, message: str) -> dict[str, Any]:
        """Detect pipeline/application-list reset intent and ask for confirmation.

        Never executes immediately.  Stores a 2-minute pending state and returns
        a confirmation prompt with three options: Archive (default) / Delete / Cancel.
        """
        arabic = self._is_arabic_text(message)
        try:
            import time
            self.memory.set_context(user_id, self._PENDING_PIPELINE_RESET_KEY, {
                "pending": True,
                "expires_at": int(time.time()) + 120,
            })
        except Exception:
            pass

        if arabic:
            msg = (
                "يبدو أنك تريد إعادة ضبط سجلات طلباتك. ماذا تريد أن تفعل؟\n\n"
                "• اكتب **أرشفة** — لأرشفة جميع الطلبات (مستحسن، يمكن التراجع عنه)\n"
                "• اكتب **حذف** — للحذف النهائي (انتقل إلى صفحة الطلبات)\n"
                "• اكتب **إلغاء** — لإلغاء العملية والبقاء كما هو"
            )
        else:
            msg = (
                "It looks like you want to reset your tracked applications. What would you like to do?\n\n"
                "• Type **archive** — Archive all applications (recommended, reversible)\n"
                "• Type **delete** — Permanently delete (manage from the Applications page)\n"
                "• Type **cancel** — Keep everything as-is"
            )
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "pipeline_reset_confirm",
            "intent": "pipeline_reset",
            "message": msg,
            "next_action": "await_confirmation",
        }

    def _handle_pending_pipeline_reset(
        self, user_id: str, message: str
    ) -> dict[str, Any] | None:
        """Execute or cancel a pending pipeline reset based on the user's choice.

        Returns a response dict if there is a live pending reset waiting for
        confirmation, else None so the caller continues normal routing.
        """
        try:
            import time
            ctx = self.memory.get_context(user_id, self._PENDING_PIPELINE_RESET_KEY)
            if not isinstance(ctx, dict):
                return None
        except Exception:
            return None

        if not ctx.get("pending") or ctx.get("expires_at", 0) < (
            __import__("time").time()
        ):
            return None

        def _clear():
            try:
                self.memory.set_context(user_id, self._PENDING_PIPELINE_RESET_KEY, {})
            except Exception:
                pass

        arabic = self._is_arabic_text(message)
        lower = (message or "").strip().lower()

        # Archive choice (recommended default)
        if re.search(r"\b(?:archive|أرشف|أرشفة)\b", lower, re.IGNORECASE):
            _clear()
            if arabic:
                msg = (
                    "لأرشفة جميع طلباتك، توجّه إلى **صفحة الطلبات** واستخدم خيار الأرشفة الجماعية.\n\n"
                    "→ /applications"
                )
            else:
                msg = (
                    "To archive all your tracked applications, head to the **Applications page** "
                    "and use the bulk-archive option there.\n\n"
                    "→ /applications"
                )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "pipeline_reset_archive",
                "intent": "pipeline_reset",
                "message": msg,
                "target_route": "/applications",
                "next_action": "navigate_to_page",
            }

        # Permanent delete choice
        if re.search(r"\b(?:delete|حذف|del)\b", lower, re.IGNORECASE):
            _clear()
            if arabic:
                msg = (
                    "لحذف السجلات نهائياً، انتقل إلى **صفحة الطلبات** حيث يمكنك "
                    "إدارة كل سجل على حدة.\n\n"
                    "→ /applications"
                )
            else:
                msg = (
                    "To permanently remove records, go to the **Applications page** where "
                    "you can manage each entry individually.\n\n"
                    "→ /applications"
                )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "pipeline_reset_delete_redirect",
                "intent": "pipeline_reset",
                "message": msg,
                "target_route": "/applications",
                "next_action": "navigate_to_page",
            }

        # Cancel / negative
        if RicoChatAPI._is_negative(message) or re.search(
            r"\b(?:cancel|إلغاء|ألغ)\b", lower, re.IGNORECASE
        ):
            _clear()
            if arabic:
                msg = "تم الإلغاء — لم يتغيّر شيء."
            else:
                msg = "Cancelled — nothing was changed."
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "pipeline_reset_cancelled",
                "intent": "pipeline_reset",
                "message": msg,
            }

        # Ambiguous — re-prompt
        if arabic:
            msg = (
                "اكتب **أرشفة** أو **حذف** أو **إلغاء** للاختيار."
            )
        else:
            msg = "Please type **archive**, **delete**, or **cancel** to choose."
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "pipeline_reset_confirm",
            "intent": "pipeline_reset",
            "message": msg,
            "next_action": "await_confirmation",
        }

    def _intercept_unsupported_delete_mutation(
        self, user_id: str, message: str
    ) -> dict[str, Any] | None:
        """Route chat-driven delete intents to the correct handler.

        Saved-jobs deletes → 2-turn confirmation flow (P2-B).
        Application-history deletes → capability_limitation (those records are protected).

        Returns a response dict if the message matches a delete pattern, else None.
        """
        if not _UNSUPPORTED_DELETE_RE.search(message):
            return None

        arabic = self._is_arabic_text(message)

        # ── Application-history: permanently blocked ──────────────────────────
        if _DELETE_APPLICATIONS_RE.search(message) and not _DELETE_SAVED_JOBS_RE.search(message):
            if arabic:
                msg = (
                    "سجلات طلباتك محمية — لا يمكن حذفها حتى من خلال المحادثة.\n\n"
                    "يمكنك الاطلاع عليها من صفحة **Applications** ← /applications"
                )
            else:
                msg = (
                    "Application records are protected history and cannot be deleted.\n\n"
                    "You can view them at **Applications** → /applications"
                )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "capability_limitation",
                "intent": "protected_application_history",
                "message": msg,
                "target_route": "/applications",
                "next_action": "navigate_to_page",
            }

        # ── Saved-jobs: ask for confirmation (P2-B) ───────────────────────────
        if _DELETE_SAVED_JOBS_RE.search(message):
            try:
                import time
                self.memory.set_context(user_id, self._PENDING_DELETE_SAVED_JOBS_KEY, {
                    "pending": True,
                    "expires_at": int(time.time()) + 120,  # 2-minute window
                })
            except Exception:
                pass
            if arabic:
                msg = (
                    "هل أنت متأكد أنك تريد حذف **جميع** وظائفك المحفوظة؟\n\n"
                    "هذا الإجراء لا يمكن التراجع عنه. اكتب **نعم** للمتابعة أو **لا** للإلغاء."
                )
            else:
                msg = (
                    "Are you sure you want to delete **all** your saved jobs?\n\n"
                    "This cannot be undone. Type **yes** to confirm or **no** to cancel."
                )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "delete_saved_jobs_confirm",
                "intent": "delete_saved_jobs",
                "message": msg,
                "next_action": "await_confirmation",
            }

        # ── Fallback: mixed/ambiguous pattern — still block ───────────────────
        if arabic:
            msg = (
                "لا أستطيع حذف الوظائف أو الطلبات من خلال المحادثة.\n\n"
                "يمكنك إدارتها مباشرةً من:\n"
                "• صفحة **Saved Jobs** ← /flow\n"
                "• صفحة **Applications** ← /applications"
            )
        else:
            msg = (
                "I can't delete records through chat.\n\n"
                "You can manage them directly from:\n"
                "• **Saved Jobs** page → /flow\n"
                "• **Applications** page → /applications"
            )
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "capability_limitation",
            "intent": "unsupported_delete_mutation",
            "message": msg,
            "target_route": "/flow",
            "next_action": "navigate_to_page",
        }

    def _handle_pending_delete_saved_jobs(
        self, user_id: str, message: str
    ) -> dict[str, Any] | None:
        """Execute or cancel a pending saved-jobs deletion based on user confirmation.

        Returns a response dict if there is a live pending deletion waiting for
        confirmation, else None so the caller continues normal routing.
        """
        try:
            import time
            ctx = self.memory.get_context(user_id, self._PENDING_DELETE_SAVED_JOBS_KEY)
            if not isinstance(ctx, dict):
                return None
        except Exception:
            return None

        if not ctx.get("pending") or ctx.get("expires_at", 0) < (
            __import__("time").time()
        ):
            return None

        def _clear():
            try:
                self.memory.set_context(user_id, self._PENDING_DELETE_SAVED_JOBS_KEY, {})
            except Exception:
                pass

        arabic = self._is_arabic_text(message)

        if RicoChatAPI._is_affirmative(message):
            _clear()
            try:
                from src.rico_db import RicoDB as _RicoDB
                db = _RicoDB()
                deleted = db.delete_saved_jobs(user_id)
                logger.info("rico_chat: delete_saved_jobs executed user=%s deleted=%d", user_id, deleted)
                if deleted > 0:
                    if arabic:
                        msg = f"تم حذف **{deleted}** وظيفة محفوظة بنجاح."
                    else:
                        msg = f"Done — **{deleted}** saved job{'s' if deleted != 1 else ''} deleted."
                else:
                    if arabic:
                        msg = "لا توجد وظائف محفوظة لحذفها."
                    else:
                        msg = "No saved jobs found to delete."
                self._append_chat(user_id, "assistant", msg)
                return {
                    "type": "delete_saved_jobs_done",
                    "deleted_count": deleted,
                    "message": msg,
                }
            except Exception as exc:
                logger.error("rico_chat: delete_saved_jobs failed user=%s err=%s", user_id, exc)
                if arabic:
                    msg = "حدث خطأ أثناء الحذف. يرجى المحاولة مرة أخرى لاحقاً."
                else:
                    msg = "Something went wrong while deleting. Please try again later."
                self._append_chat(user_id, "assistant", msg)
                return {
                    "type": "delete_saved_jobs_failed",
                    "message": msg,
                }

        if RicoChatAPI._is_negative(message):
            _clear()
            if arabic:
                msg = "تم الإلغاء — لم يتم حذف أي وظيفة محفوظة."
            else:
                msg = "Cancelled — no saved jobs were deleted."
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "delete_saved_jobs_cancelled",
                "message": msg,
            }

        # Ambiguous reply — re-prompt
        if arabic:
            msg = "اكتب **نعم** لتأكيد الحذف أو **لا** للإلغاء."
        else:
            msg = "Please type **yes** to confirm deletion or **no** to cancel."
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "delete_saved_jobs_confirm",
            "intent": "delete_saved_jobs",
            "message": msg,
            "next_action": "await_confirmation",
        }

    def _handle_preference_correction(
        self, user_id: str, message: str, profile: Any
    ) -> dict[str, Any]:
        """Remove a learned preference at the user's explicit request.

        Parses the message to extract what type of preference to clear and the
        value, then calls LearningRepository.clear_preference() which writes a
        durable veto signal and removes the key from the in-memory cache.
        """
        import re as _re

        _LOCATIONS = {
            "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah",
            "fujairah", "umm al quwain", "riyadh", "jeddah", "dammam",
            "doha", "kuwait", "muscat", "manama", "abu dhabi",
            "uae", "saudi arabia", "qatar", "bahrain", "oman",
        }

        msg_lower = message.lower()

        # Determine preference type
        pref_type = "role"
        if "skill" in msg_lower:
            pref_type = "skill"
        elif "company" in msg_lower or "employer" in msg_lower:
            pref_type = "company"
        else:
            for loc in _LOCATIONS:
                if loc in msg_lower:
                    pref_type = "location"
                    break

        # Extract the value: strip command words then take remaining text
        _STRIP = _re.compile(
            r"\b(forget|remove|clear|delete|drop|don.?t\s+want|not\s+interested\s+in"
            r"|my\s+preference\s+for|preference\s+for|preference|from\s+my\s+preferences"
            r"|انسَ|احذف|تفضيلي\s*ل?|لا\s+أريد\s+وظائف\s+في)\b",
            _re.IGNORECASE,
        )
        cleaned = _STRIP.sub("", message).strip(" .,،!؟?")
        # Remove leading filler words
        cleaned = _re.sub(
            r"^(for|about|in|at|ل|عن|في|that|this|the)\s+",
            "", cleaned, flags=_re.IGNORECASE,
        ).strip()
        # Collapse whitespace
        cleaned = _re.sub(r"\s+", " ", cleaned).strip()

        arabic = self._is_arabic_text(message)
        if not cleaned or len(cleaned) < 2:
            reply = (
                "أخبرني بالتفضيل المحدد الذي تريد إزالته — مثلاً:\n"
                "- \"انسَ تفضيلي لدبي\"\n"
                "- \"أزل بايثون من مهاراتي\"\n"
                "- \"لا أريد وظائف في أبوظبي\""
                if arabic else
                "Please tell me what specific preference to remove — for example:\n"
                "- \"Forget my preference for Dubai\"\n"
                "- \"Remove Python from my skills\"\n"
                "- \"I don't want jobs in Abu Dhabi\""
            )
            self._append_chat(user_id, "assistant", reply)
            return {"type": "preference_correction", "message": reply}

        try:
            from src.repositories.learning_repo import get_learning_repository
            get_learning_repository().clear_preference(user_id, pref_type, cleaned)
            _labels = {
                "role": "role preference",
                "location": "location preference",
                "skill": "skill",
                "company": "company",
            }
            _labels_ar = {
                "role": "تفضيل الدور الوظيفي",
                "location": "تفضيل الموقع",
                "skill": "المهارة",
                "company": "الشركة",
            }
            if arabic:
                label = _labels_ar.get(pref_type, "التفضيل")
                reply = (
                    f"تم — أزلت **{cleaned}** من قائمة {label}. "
                    "لن يؤثر على نتائجك بعد الآن.\n\n"
                    "إذا غيّرت رأيك، فقط احفظ أو تقدّم لوظائف ذات صلة وسأعيد رصده."
                )
            else:
                label = _labels.get(pref_type, "preference")
                reply = (
                    f"Done — I've removed **{cleaned}** from your {label} list. "
                    "It won't influence your results anymore.\n\n"
                    "If you change your mind, just save or apply to relevant jobs and I'll pick it up again."
                )
        except Exception:
            reply = (
                "تعذرت إزالة هذا التفضيل الآن. "
                "حاول مرة أخرى بعد قليل — بياناتك الأخرى بأمان."
                if arabic else
                "I couldn't remove that preference right now. "
                "Please try again in a moment — your other data is safe."
            )

        self._append_chat(user_id, "assistant", reply)
        return {"type": "preference_correction", "message": reply}

    def _handle_application_insights(self, user_id: str, message: str = "") -> dict[str, Any]:
        """Analyze the user's tracked applications and surface success patterns.

        Calls ResponseIntelligenceEngine.analyze_response_patterns() on the user's
        application history and formats a plain-language insight summary.
        """
        arabic = self._is_arabic_text(message)
        try:
            from src.repositories.applications_repo import get_all
            apps = get_all(user_id=user_id) or []

            if len(apps) < 3:
                count = len(apps)
                if arabic:
                    noun = "طلب" if count == 1 else "طلبات"
                    msg = (
                        f"لديك {count} {noun} مسجلة حتى الآن. "
                        "بعد إضافة بعض الطلبات الأخرى سأقدر أعرض لك الأنماط — "
                        "معدل النجاح، مدة استجابة أصحاب العمل المعتادة، وأين تركز جهودك."
                    )
                else:
                    noun = "application" if count == 1 else "applications"
                    msg = (
                        f"You have {count} tracked {noun} so far. "
                        "Once you have a few more I'll be able to show you patterns — "
                        "success rate, how long employers typically respond, and where to focus."
                    )
            else:
                from src.decision_engine import JobDecisionEngine
                from src.response_intelligence import (
                    JsonFileStateStore,
                    ResponseIntelligenceEngine,
                )
                from pathlib import Path

                _engine = ResponseIntelligenceEngine(
                    decision_engine=JobDecisionEngine(profile={}, target_roles=[]),
                    state_store=JsonFileStateStore(Path("data/scoring_adjustments.json")),
                )
                result = _engine.analyze_response_patterns(apps)

                if "error" in result:
                    msg = (
                        "تعذر تحليل طلباتك الآن. حاول مرة أخرى بعد قليل."
                        if arabic else
                        "I couldn't analyze your applications right now. Try again in a moment."
                    )
                else:
                    total = result["total_applications"]
                    success_pct = result["success_rate_pct"]
                    avg_days = result.get("avg_response_time_days", 0.0)
                    dist = result.get("response_distribution", {})
                    insights = result.get("insights", [])

                    lines = (
                        [f"**تحليل الطلبات — {total} طلب مسجل**\n"] if arabic
                        else [f"**Application Analysis — {total} tracked applications**\n"]
                    )

                    status_parts = []
                    for status, count in sorted(dist.items(), key=lambda x: -x[1]):
                        if count > 0 and status != "no_response":
                            label = status.replace("_", " ").title()
                            status_parts.append(f"{label}: {count}")
                    if status_parts:
                        lines.append(("**النتائج:** " if arabic else "**Outcomes:** ") + " · ".join(status_parts))

                    lines.append(
                        f"**معدل النجاح:** {success_pct}%" if arabic else f"**Success rate:** {success_pct}%"
                    )
                    if avg_days > 0:
                        lines.append(
                            f"**متوسط استجابة أصحاب العمل:** {avg_days:.0f} يوم"
                            if arabic else
                            f"**Avg employer response:** {avg_days:.0f} days"
                        )

                    if insights:
                        lines.append("")
                        for ins in insights[:3]:
                            lines.append(f"**Insight — {ins['insight_type'].replace('_', ' ').title()}**")
                            if ins.get("recommendation"):
                                lines.append(ins["recommendation"])

                    msg = "\n".join(lines)
        except Exception:
            msg = (
                "تعذر تحميل بيانات طلباتك الآن. حاول مرة أخرى بعد قليل."
                if arabic else
                "I couldn't load your application data right now. "
                "Try again in a moment."
            )

        self._append_chat(user_id, "assistant", msg)
        return {"type": "application_insights", "message": msg}

    def _handle_job_feedback_positive(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Record a positive learning signal when the user says a job is a great match.

        Calls infer_signals_from_job_action(..., "save", job) on the most recently
        shown job so role/location/company weights are boosted. Falls back to a
        generic positive signal when no recent job context is available.
        """
        arabic = self._is_arabic_text(message)
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            ctx = self._get_recent_context(user_id)
            matches = ctx.get("recent_search_matches") or []
            if matches:
                top = matches[0]
                _lr.infer_signals_from_job_action(user_id, "save", top)
                title = top.get("title") or ("هذا الدور" if arabic else "that role")
                company = top.get("company") or ""
                label = f"**{title}**" + (f" at {company}" if company else "")
                msg = (
                    f"رائع — {label} مسجلة كمطابقة قوية. سأعطي الأولوية لأدوار مشابهة في عمليات البحث القادمة."
                    if arabic else
                    f"Great — {label} is marked as a strong match. "
                    "I'll prioritise similar roles in future searches."
                )
            else:
                _lr.record_signal(
                    user_id,
                    "feedback",
                    "positive_match",
                    signal_weight=0.6,
                    source="chat_feedback",
                    metadata={"message": message[:200]},
                )
                msg = (
                    "يسعدني ذلك! أخبرني إذا تريد حفظها أو تحضير طلب تقديم."
                    if arabic else
                    "Glad to hear it! Tell me if you want to save it or prepare an application."
                )
        except Exception:
            msg = (
                "رائع — سأضع ذلك في الحسبان عند البحث عن أدوار أخرى."
                if arabic else
                "Great — I'll keep that in mind when searching for more roles."
            )

        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_feedback", "message": msg}

    def _handle_job_feedback_negative(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Record a negative learning signal when the user says a job isn't suitable.

        Looks up the most recently shown job from context and calls
        infer_signals_from_job_action(..., "not_relevant", job) so role/location/company
        signals are updated with negative weights. Falls back to a generic signal when no
        recent job is in context. Never raises — a bare acknowledgement is returned on error.
        """
        arabic = self._is_arabic_text(message)
        try:
            from src.repositories.learning_repo import get_learning_repository
            _lr = get_learning_repository()
            ctx = self._get_recent_context(user_id)
            matches = ctx.get("recent_search_matches") or []
            if matches:
                top = matches[0]
                _lr.infer_signals_from_job_action(user_id, "not_relevant", top)
                title = top.get("title") or ("هذا الدور" if arabic else "that role")
                company = top.get("company") or ""
                label = f"**{title}**" + (f" at {company}" if company else "")
                msg = (
                    f"تم التسجيل — {label} ليست مناسبة. سأستخدم ذلك لتحسين الاقتراحات القادمة."
                    if arabic else
                    f"Noted — {label} isn't the right fit. "
                    "I'll use that to refine future recommendations."
                )
            else:
                _lr.record_signal(
                    user_id,
                    "feedback",
                    "negative_match",
                    signal_weight=-0.3,
                    source="chat_feedback",
                    metadata={"message": message[:200]},
                )
                msg = (
                    "فهمت. أخبرني عن نوع الدور الذي تبحث عنه وسأجد مطابقات أفضل."
                    if arabic else
                    "Understood. Tell me what kind of role you're looking for and I'll find better matches."
                )
        except Exception:
            msg = (
                "تم — سأضع ذلك في الحسبان عند البحث عن أدوار."
                if arabic else
                "Got it — I'll keep that in mind when searching for roles."
            )

        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_feedback", "message": msg}

    def _handle_delegated_decision(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Handle 'you decide' / 'choose for me' by picking the strongest CV-aligned role."""
        has_cv = bool(profile and self._profile_value(profile, "cv_status") == "parsed")
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        arabic = self._is_arabic_text(message)

        if has_cv and target_roles:
            _, _, status = self._resolve_profile_search_role(profile)
            if status == "stale":
                # Saved role is not CV-aligned — surface evidence-based options
                # instead of asserting it (#732: no unevidenced coding role assertion)
                return self._handle_profile_role_suggestions(profile, message)
            chosen_role = target_roles[0]
            return {
                "type": "job_search_explicit",
                "message": (
                    f"بناءً على سيرتك الذاتية، سأتابع بأقوى مطابقة: **{chosen_role}**. أبحث عن وظائف فعلية الآن..."
                    if arabic else
                    f"Based on your CV, I'll proceed with the strongest match: **{chosen_role}**."
                    f" Searching live jobs now..."
                ),
                "chosen_role": chosen_role,
                "source": "delegated_cv_choice",
                "next_action": "search_jobs",
            }

        if target_roles:
            chosen_role = target_roles[0]
            return {
                "type": "job_search_explicit",
                "message": (
                    f"سأتابع بدورك المستهدف: **{chosen_role}**. أبحث عن وظائف فعلية الآن..."
                    if arabic else
                    f"I'll proceed with your target role: **{chosen_role}**."
                    f" Searching live jobs now..."
                ),
                "chosen_role": chosen_role,
                "source": "delegated_target_role_choice",
                "next_action": "search_jobs",
            }

        return {
            "type": "clarification",
            "message": (
                "يسعدني أن أختار لك، لكنني أحتاج سياقاً أكثر أولاً. "
                "ارفع سيرتك الذاتية أو أخبرني بدورك المستهدف والمدينة المفضلة."
                if arabic else
                "I'd be happy to choose for you, but I need more context first. "
                "Upload your CV or tell me your target role and preferred city."
            ),
            "next_action": "need_profile_for_delegation",
        }

    def _handle_post_cv_continuation(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Handle 'keep going / كمل / continue' after CV upload or profile-building.

        Priority:
        1. Profile has target_roles AND they are CV-aligned → search with the first one.
        2. Profile has CV (or stale target_roles) → suggest roles and ask user to choose.
        3. No context → ask one concise question.
        """
        has_cv = bool(profile and self._profile_value(profile, "cv_status") == "parsed")
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))

        if target_roles:
            chosen_role = target_roles[0]
            # #732 — skip stale/unevidenced coding role; surface CV-derived suggestions.
            if has_cv and not self._role_is_cv_aligned(profile, chosen_role):
                return self._handle_profile_role_suggestions(profile, message)
            return self._classified_role_search(user_id, chosen_role, profile)

        if has_cv:
            return self._handle_profile_role_suggestions(profile, message)

        clarification = (
            "ما الدور الذي تريد أن أبحث عنه أولاً؟"
            if self._is_arabic_text(message) else
            "What role should I search for first?"
        )
        self._append_chat(user_id, "assistant", clarification)
        return {
            "type": "clarification",
            "intent": "search_jobs",
            "message": clarification,
        }

    def _handle_cv_creation(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Start the no-CV profile builder / CV draft flow."""
        name = self._profile_value(profile, "name") or ""
        arabic = self._is_arabic_text(message)
        if arabic:
            greeting = f"أهلاً {name}،" if name else "أهلاً،"
        elif name:
            greeting = f"Hi {name},"
        else:
            greeting = "Hi there,"
        self._set_flow_state(user_id, "cv_builder")
        return {
            "type": "cv_creation",
            "message": (
                f"{greeting} يمكنني مساعدتك في بناء سيرة ذاتية من الصفر. أخبرني بـ:\n"
                "• المسمى الوظيفي الحالي أو الأخير\n"
                "• سنوات الخبرة\n"
                "• المهارات الأساسية والشهادات\n"
                "• الصناعات والمدن المفضلة\n\n"
                "أو الصق أي سيرة عمل سابقة وسأنسقها في سيرة ذاتية مناسبة."
                if arabic else
                f"{greeting} I can help you build a CV from scratch. "
                "Tell me your:\n"
                "• Current or most recent job title\n"
                "• Years of experience\n"
                "• Key skills and certifications\n"
                "• Preferred industries and cities\n\n"
                "Or paste any existing work history and I'll format it into a proper CV."
            ),
            "next_action": "collect_cv_fields",
            "fields_needed": ["current_role", "years_experience", "skills", "industries", "preferred_cities"],
        }

    def _handle_cv_generate_from_profile(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Generate a professional CV draft from the user's already-parsed profile.

        Uses extracted fields: name, email, phone, skills, experience, target roles,
        certifications, preferred cities. Asks only for genuinely missing fields.
        """
        arabic = self._is_arabic_text(message)
        if not self._has_cv_profile(profile):
            # No parsed profile — redirect to upload or manual creation
            return {
                "type": "cv_creation",
                "message": (
                    "لا تتوفر لدي بيانات سيرتك الذاتية بعد. "
                    "ارفع سيرتك الذاتية (PDF أو Word) وسأستخدمها لبناء سيرة جديدة، "
                    "أو أخبرني بتاريخك الوظيفي وسأنسقه لك."
                    if arabic else
                    "I don't have your CV data yet. "
                    "Please upload your CV (PDF or Word) and I'll use it to build a new one, "
                    "or tell me your work history and I'll format it for you."
                ),
                "next_action": "upload_cv",
            }

        name = self._profile_value(profile, "name") or ""
        email = self._profile_value(profile, "email") or ""
        phone = self._profile_value(profile, "phone") or ""
        skills = self._as_list(self._profile_value(profile, "skills"))
        years_exp = self._profile_value(profile, "years_experience")
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        certifications = self._as_list(self._profile_value(profile, "certifications"))
        preferred_cities = self._as_list(self._profile_value(profile, "preferred_cities"))
        industries = self._as_list(self._profile_value(profile, "industries"))
        current_role = self._profile_value(profile, "current_role") or (target_roles[0] if target_roles else "")

        # Pull extended parsed-CV fields to check what sections are actually stored
        work_experience = self._as_list(self._profile_value(profile, "work_experience"))
        education = self._as_list(self._profile_value(profile, "education"))

        # Identify genuinely missing fields that would improve the CV
        missing: list[str] = []
        if arabic:
            if not current_role:
                missing.append("المسمى الوظيفي الحالي أو الأخير")
            if years_exp is None:
                missing.append("سنوات الخبرة")
            if not skills:
                missing.append("المهارات الأساسية والشهادات")
            if not preferred_cities:
                missing.append("المدن المفضلة (مثل دبي، أبوظبي)")
        else:
            if not current_role:
                missing.append("current or most recent job title")
            if years_exp is None:
                missing.append("years of experience")
            if not skills:
                missing.append("key skills and certifications")
            if not preferred_cities:
                missing.append("preferred cities (e.g. Dubai, Abu Dhabi)")

        # Sections absent from parsed CV — do not generate placeholders for these
        unparsed_sections: list[str] = []
        if arabic:
            if not work_experience:
                unparsed_sections.append("الخبرة العملية")
            if not education:
                unparsed_sections.append("التعليم")
        else:
            if not work_experience:
                unparsed_sections.append("Work Experience")
            if not education:
                unparsed_sections.append("Education")

        # If cities are missing, store pending field so the next reply is captured
        if not preferred_cities:
            ctx = self._get_recent_context(user_id)
            ctx["_pending_field"] = "preferred_cities"
            ctx["_pending_cv_generate"] = True
            self._store_recent_context(user_id, ctx)

        # Build the CV draft from extracted data only — no placeholders
        sections: list[str] = []

        header_parts = [name] if name else []
        contact_parts = [
            p for p in [email, phone]
            if isinstance(p, str) and p
            and (EMAIL_RE.fullmatch(p.strip()) or PHONE_RE.fullmatch(p.strip()))
        ]
        if contact_parts:
            header_parts.append(" | ".join(contact_parts))
        if preferred_cities:
            header_parts.append(", ".join(preferred_cities[:2]))
        if header_parts:
            sections.append("\n".join(header_parts))

        if current_role or years_exp is not None:
            summary_parts: list[str] = []
            if current_role:
                summary_parts.append(current_role)
            if years_exp is not None:
                summary_parts.append(f"{int(years_exp)} years of experience")
            if industries:
                summary_parts.append(f"in {', '.join(industries[:2])}")
            sections.append("**Professional Summary**\n" + " · ".join(summary_parts))

        if skills:
            sections.append("**Key Skills**\n" + " · ".join(skills[:12]))

        if certifications:
            sections.append("**Certifications**\n" + "\n".join(f"• {c}" for c in certifications[:6]))

        if target_roles:
            sections.append("**Target Roles**\n" + " · ".join(target_roles[:4]))

        cv_draft = "\n\n".join(sections)

        if arabic:
            greeting = f"هذا مسودة سيرتك الذاتية، {name}:" if name else "هذا مسودة سيرتك الذاتية:"
        else:
            greeting = f"Here is your CV draft, {name}:" if name else "Here is your CV draft:"

        if missing:
            missing_note = (
                (
                    "\n\n**لإكمال السيرة الذاتية، ما زلت أحتاج:**\n"
                    + "\n".join(f"• {f}" for f in missing)
                    + "\n\nرد بهذه التفاصيل وسأضيفها."
                )
                if arabic else
                (
                    "\n\n**To complete the CV I still need:**\n"
                    + "\n".join(f"• {f}" for f in missing)
                    + "\n\nReply with these details and I'll add them."
                )
            )
        elif unparsed_sections:
            # Profile is present but parsed CV lacks full sections — be honest
            missing_note = (
                (
                    "\n\n**أقسام غير متوفرة بعد من سيرتك الذاتية المحلَّلة:** "
                    + ", ".join(unparsed_sections)
                    + ".\n\nلإضافتها، ارفع ملف سيرتك الذاتية (PDF أو Word) "
                    "أو الصق تاريخك الوظيفي وسأنسقه."
                )
                if arabic else
                (
                    "\n\n**Sections not yet available from your parsed CV:** "
                    + ", ".join(unparsed_sections)
                    + ".\n\nTo add these, upload your CV file (PDF or Word) "
                    "or paste your work history and I'll format it."
                )
            )
        else:
            missing_note = (
                (
                    "\n\nكل أقسام الملف الشخصي المتوفرة مُضمّنة. "
                    "أخبرني إذا تريد تخصيص هذه السيرة الذاتية لدور معين."
                )
                if arabic else
                (
                    "\n\nAll available profile sections are included. "
                    "Tell me if you'd like to tailor this CV for a specific role."
                )
            )

        message = f"{greeting}\n\n---\n\n{cv_draft}\n\n---{missing_note}"
        self._append_chat(user_id, "assistant", message)
        self._set_flow_state(user_id, "cv_builder")
        return {
            "type": "cv_draft",
            "message": message,
            "cv_draft": cv_draft,
            "missing_fields": missing,
            "unparsed_sections": unparsed_sections,
            "next_action": "collect_missing_cv_fields" if missing else "cv_ready",
        }

    # ── Job detail inquiry ──────────────────────────────────────────────────────

    @staticmethod
    def _ordinal_to_index(ordinal: str) -> int:
        """Convert an ordinal word or digit string to a 0-based list index."""
        _MAP = {
            "1": 0, "first": 0,
            "2": 1, "second": 1,
            "3": 2, "third": 2,
            "4": 3, "fourth": 3,
            "5": 4, "fifth": 4,
            "الثاني": 1, "الثالث": 2, "الرابع": 3, "الخامس": 4,
        }
        key = ordinal.lower().rstrip("stndrdth")
        return _MAP.get(key, _MAP.get(ordinal.lower(), 0))

    def _handle_job_detail(
        self,
        user_id: str,
        profile: Any,
        message: str,
        ordinal_hint: str = "",
    ) -> dict[str, Any]:
        """Show extended details for a cached job match (first by default, or by ordinal)."""
        arabic = self._is_arabic_text(message)
        matches: list[dict[str, Any]] = []
        try:
            ctx = self._get_recent_context(user_id)
            matches = ctx.get("recent_search_matches") or []
        except Exception:
            pass
        if not matches or not isinstance(matches, list):
            # Fall back to the most recently applied-to job stored in context.
            try:
                ctx = self._get_recent_context(user_id)
                recent_app = ctx.get("recent_application") if isinstance(ctx, dict) else None
                if isinstance(recent_app, dict) and recent_app.get("title"):
                    matches = [recent_app]
            except Exception:
                pass
        if not matches or not isinstance(matches, list):
            # DB fallback: cross-worker / postgres-backend safe.
            # Reads the most recently searched matches from user_job_context table.
            try:
                from src.repositories.user_job_context_repo import get_recent_matches as _get_recent_db_matches
                matches = _get_recent_db_matches(user_id, limit=10, max_age_minutes=60) or []
            except Exception:
                pass
        if not matches or not isinstance(matches, list):
            msg = (
                "لا يوجد بحث حديث في جلستك. ابدأ بالبحث عن وظيفة وسأعرض التفاصيل."
                if arabic else
                "No recent job search in this session. Search for a role first and I'll show the details."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}
        idx = 0
        if ordinal_hint:
            if ordinal_hint.lower() in ("last",):
                idx = len(matches) - 1
            else:
                idx = min(self._ordinal_to_index(ordinal_hint), len(matches) - 1)
        job = matches[idx]
        title = job.get("title") or "Unknown role"
        company = job.get("company") or ""
        location = job.get("location") or ""
        employment_type = job.get("employment_type") or ""
        salary = job.get("salary_string") or ""
        description = (job.get("description") or "").strip()
        why_fits = (job.get("why_this_fits") or "").strip()
        worth_check = (job.get("worth_checking") or "").strip()
        apply_url = job.get("apply_url") or job.get("link") or ""
        lines = [f"**{title}**" + (f" — {company}" if company else "")]
        if location:
            lines.append(f"📍 {location}")
        if employment_type:
            lines.append(f"🕐 {employment_type}")
        if salary:
            lines.append(f"💰 {salary}")
        if description:
            lines.append(f"\n**About the role:**\n{description[:350]}{'…' if len(description) > 350 else ''}")
        if why_fits:
            lines.append(f"\n**Why it fits your profile:**\n{why_fits}")
        if worth_check:
            lines.append(f"\n**Worth checking:**\n{worth_check}")
        if apply_url:
            lines.append(f"\n[Apply now]({apply_url})")
        else:
            source_url = job.get("source_url") or ""
            if source_url:
                lines.append(f"\n_No direct apply link — [view source listing]({source_url})_")
            else:
                lines.append("\n_No apply link available for this listing. Check the company careers page directly._")
        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_detail", "message": msg, "job": job}

    # ── Salary expectation readback ─────────────────────────────────────────────

    def _handle_salary_readback(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return the user's saved salary expectation without modifying it."""
        arabic = self._is_arabic_text(message)
        salary = self._profile_value(profile, "salary_expectation_aed")
        if not salary:
            msg = (
                "لم تحدد راتبًا متوقعًا بعد. قل مثلاً: 'راتبي المتوقع 15,000 درهم'."
                if arabic else
                "You haven't set a salary expectation yet. "
                "Say something like: 'My expected salary is AED 15,000/month'."
            )
        else:
            try:
                formatted = f"AED {int(float(salary)):,}/month"
            except (ValueError, TypeError):
                formatted = f"AED {salary}"
            msg = (
                f"راتبك المتوقع المحفوظ هو **{formatted}**.\n"
                "قل 'غيّر راتبي إلى [مبلغ]' إذا أردت تعديله."
                if arabic else
                f"Your saved salary expectation is **{formatted}**.\n"
                "Say 'update my salary to [amount]' to change it."
            )
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "salary_readback",
            "message": msg,
            "salary_expectation_aed": salary,
        }

    # ── Salary expectation setting ──────────────────────────────────────────────

    @staticmethod
    def _parse_salary_value(text: str) -> int | None:
        """Extract AED monthly salary from text, handling K/k suffix, commas, and Arabic word-numbers."""
        # Arabic word-number phrases → value. Longest match first to avoid substring
        # false-positives ("مئة ألف" must not match "ألف" = 1000 first).
        _AR_NUM: list[tuple[str, int]] = [
            ("مئة ألف", 100000), ("مائة ألف", 100000),
            ("تسعين ألف", 90000), ("ثمانين ألف", 80000),
            ("سبعين ألف", 70000), ("ستين ألف", 60000),
            ("خمسين ألف", 50000), ("أربعين ألف", 40000),
            ("ثلاثين ألف", 30000), ("خمسة وعشرين ألف", 25000),
            ("عشرين ألف", 20000), ("خمسة عشر ألف", 15000),
            ("عشرة آلاف", 10000), ("عشرة ألاف", 10000),
            ("آلاف", 1000), ("ألف", 1000),  # digit-multiplier handled below
        ]
        _clean = text.replace(",", "")
        for ar_word, ar_val in _AR_NUM:
            if ar_word in _clean:
                _mult_m = re.search(r"(\d+)\s*" + re.escape(ar_word), _clean)
                amount = int(float(_mult_m.group(1)) * ar_val) if _mult_m else ar_val
                return amount if 1000 <= amount <= 500000 else None
        m = re.search(r"(\d[\d.]*)([Kk]?)", _clean)
        if not m:
            return None
        try:
            val = float(m.group(1))
            if m.group(2).lower() == "k":
                val *= 1000
            amount = int(val)
            return amount if 1000 <= amount <= 500000 else None
        except (ValueError, OverflowError):
            return None

    def _handle_salary_set(self, user_id: str, message: str, profile: Any) -> dict[str, Any]:
        """Parse salary from message, save to profile, confirm with the exact amount."""
        arabic = self._is_arabic_text(message)
        amount = self._parse_salary_value(message)
        if amount is not None:
            try:
                upsert_profile(user_id=user_id, updates={"salary_expectation_aed": amount})
                msg = (
                    f"تم تحديث الراتب المتوقع إلى **{amount:,} درهم/شهر**. "
                    "سأستثني الوظائف التي تقل عن هذا الحد تلقائياً."
                    if arabic else
                    f"Salary expectation set to **AED {amount:,}/month**. "
                    "I'll flag jobs that fall below this threshold."
                )
                response_type = "preferences_updated"
            except Exception:
                msg = (
                    "لم أتمكن من حفظ الراتب المتوقع، جرب مجدداً."
                    if arabic else
                    "I couldn't save that — please try again."
                )
                response_type = "clarification"
        else:
            msg = (
                "لم أفهم قيمة الراتب. أرسل مثلاً: 'الراتب المتوقع 50,000 درهم'."
                if arabic else
                "I couldn't read the salary amount. Try: 'my minimum salary is 50,000 AED'."
            )
            response_type = "clarification"
        self._append_chat(user_id, "assistant", msg)
        return {"type": response_type, "message": msg}

    # ── Profile pitch / bio ─────────────────────────────────────────────────────

    def _handle_profile_pitch(self, user_id: str, profile: Any) -> dict[str, Any]:
        """Build a 2-3 sentence professional pitch from profile fields."""
        arabic = self._is_arabic_text("")
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        skills = self._as_list(self._profile_value(profile, "skills"))[:4]
        exp = self._profile_value(profile, "years_experience")
        industries = self._as_list(self._profile_value(profile, "industries"))[:1]
        certs = self._as_list(self._profile_value(profile, "certifications"))[:1]
        cities = self._as_list(self._profile_value(profile, "preferred_cities"))[:1]

        if not target_roles and not skills:
            msg = (
                "I need more profile data to write a pitch. "
                "Upload your CV or tell me your target role and key skills first."
            )
        else:
            role = target_roles[0] if target_roles else "professional"
            exp_str = f"{int(float(exp))}-year " if exp and str(exp).replace(".", "").isdigit() else ""
            skills_str = ", ".join(skills[:3]) if skills else ""
            industry_str = f" in the {industries[0]} sector" if industries else ""
            cert_str = f", holding {certs[0]}" if certs else ""
            city_str = f", based in {cities[0]}" if cities else " based in the UAE"
            skills_sentence = f" Skilled in {skills_str}." if skills_str else ""

            msg = (
                f"**Your professional pitch:**\n\n"
                f"{exp_str}experienced **{role}**{industry_str}{cert_str}{city_str}."
                f"{skills_sentence} "
                f"Open to opportunities across the Emirates.\n\n"
                "Say **'improve it'** for a more detailed version, or use it as-is on LinkedIn or in emails."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "profile_pitch", "message": msg}

    # ── Application list query ──────────────────────────────────────────────────

    def _handle_applications_list(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Fetch and format the user's application list from DB."""
        arabic = self._is_arabic_text(message)
        apps: list[dict[str, Any]] = []
        try:
            from src.repositories import applications_repo
            apps = applications_repo.get_all(user_id) or []
        except Exception:
            pass

        if not apps:
            msg = (
                "لا يوجد تقديمات مسجلة بعد. ابحث عن وظيفة وتقدّم إليها أولاً."
                if arabic else
                "No applications on record yet. Search for a role and apply to start tracking them here."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        total = len(apps)
        lines = [f"**Your applications ({total} total):**\n"]
        for app in apps[:10]:
            lines.append(self._format_application_line(app))

        if total > 10:
            lines.append(f"\n_…and {total - 10} more. Open your **Applications** page to see all._")

        # Quick counts by status
        from collections import Counter
        counts = Counter(app.get("status", "unknown") for app in apps)
        summary_parts = []
        if counts.get("applied"):
            summary_parts.append(f"{counts['applied']} applied")
        if counts.get("interview"):
            summary_parts.append(f"{counts['interview']} at interview stage")
        if counts.get("offer"):
            summary_parts.append(f"{counts['offer']} with offers")
        if summary_parts:
            lines.append("\n" + " · ".join(summary_parts))

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {"type": "application_list", "message": msg, "applications": apps[:10], "total": total}

    # ── Profile data readback ───────────────────────────────────────────────────

    def _handle_profile_readback(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Show the user's saved profile fields as a formatted summary."""
        arabic = self._is_arabic_text(message)
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        skills       = self._as_list(self._profile_value(profile, "skills"))
        certs        = self._as_list(self._profile_value(profile, "certifications"))
        exp          = self._profile_value(profile, "years_experience")
        cities       = self._as_list(self._profile_value(profile, "preferred_cities"))
        industries   = self._as_list(self._profile_value(profile, "industries"))
        salary       = self._profile_value(profile, "salary_expectation_aed")
        cv_ok        = bool(self._profile_value(profile, "cv_filename") or self._profile_value(profile, "cv_status") == "parsed")

        if not target_roles and not skills and not exp and not cities:
            msg = (
                "ملفك الشخصي فارغ حتى الآن. ارفع سيرتك الذاتية أو أخبرني عن مسماك الوظيفي ومهاراتك."
                if arabic else
                "Your profile is empty. Upload your CV or tell me your target role and key skills to get started."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        lines = ["**Here's what I have on file for you:**\n"]
        if cv_ok:
            lines.append("📄 CV uploaded and parsed")
        if target_roles:
            role_display = ', '.join(target_roles[:3])
            if cv_ok and not self._role_is_cv_aligned(profile, target_roles[0]):
                lines.append(
                    f"🎯 **Target roles:** {role_display} "
                    f"*(may not match your CV — say \"suggest roles from my CV\" to update)*"
                )
            else:
                lines.append(f"🎯 **Target roles:** {role_display}")
        if cities:
            lines.append(f"📍 **Preferred cities:** {', '.join(cities[:3])}")
        if exp is not None:
            try:
                lines.append(f"🕐 **Years of experience:** {int(float(exp))}")
            except (ValueError, TypeError):
                lines.append(f"🕐 **Years of experience:** {exp}")
        if industries:
            lines.append(f"🏭 **Industries:** {', '.join(industries[:3])}")
        if skills:
            lines.append(f"💡 **Skills:** {', '.join(skills[:6])}")
        if certs:
            lines.append(f"🏅 **Certifications:** {', '.join(certs[:3])}")
        if salary:
            try:
                lines.append(f"💰 **Salary expectation:** AED {int(float(salary)):,}/month")
            except (ValueError, TypeError):
                lines.append(f"💰 **Salary expectation:** AED {salary}")

        lines.append("\nSay **'update my profile'** to change any of these.")
        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {"type": "profile_summary", "message": msg}

    # ── Granular profile field update ───────────────────────────────────────────

    def _handle_profile_field_update(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Parse a natural-language profile-field update and persist it.

        Supports:
        - "add Python to my skills" → append to skills list
        - "remove OSHA from my skills" → remove from skills list
        - "update my experience to 8 years" / "I have 10 years of experience"
        - "I'm now based in Abu Dhabi" / "change my location to Sharjah"
        - "change my target role to HSE Manager"
        - "add oil and gas to my industries"
        """
        import re as _re

        arabic = self._is_arabic_text(message)
        lower  = message.lower()

        # ── Detect field + operation ─────────────────────────────────────────
        field: str = ""
        op: str    = "set"          # "add" | "remove" | "set"
        raw_value: str = ""

        # Skills / certifications
        _add_skills_m = _re.search(
            r"\badd\b(.{1,40}?)\bto\s+my\s+(skills?|certifications?)\b", message, _re.IGNORECASE
        )
        _rem_skills_m = _re.search(
            r"\bremove\b(.{1,40}?)\bfrom\s+my\s+(skills?|certifications?)\b", message, _re.IGNORECASE
        )
        # Years of experience
        _exp_m = _re.search(
            r"(?:update|set|change)\s+my\s+(?:years?\s+(?:of\s+)?)?experience\s+to\s+(\d+(?:\.\d+)?)"
            r"|I\s+(?:now\s+)?have\s+(\d+(?:\.\d+)?)\s+years?\s+(?:of\s+)?experience"
            r"|my\s+experience\s+is\s+(?:now\s+)?(\d+(?:\.\d+)?)\s+years?",
            message, _re.IGNORECASE,
        )
        # Location / preferred cities
        _loc_m = _re.search(
            r"(?:I(?:'m|\s+am)\s+(?:now\s+)?(?:based|located?|living|working)\s+in\s+|"
            r"my\s+(?:location|city|base)\s+(?:is|has\s+changed\s+to|changed\s+to)\s+|"
            r"(?:update|change|set)\s+my\s+(?:preferred\s+)?(?:location|city)\s+to\s+)"
            r"([A-Za-z][A-Za-z\s]{1,30})",
            message, _re.IGNORECASE,
        )
        # Target role
        _role_m = _re.search(
            r"(?:change|update|set)\s+my\s+(?:target\s+)?role\s+(?:to|as)\s+(.{3,40})"
            r"|(?:change|update|set)\s+my\s+(?:job\s+)?target\s+to\s+(.{3,40})",
            message, _re.IGNORECASE,
        )
        # Industries
        _ind_add_m = _re.search(
            r"\badd\b(.{1,40}?)\bto\s+my\s+industries\b", message, _re.IGNORECASE
        )
        _ind_rem_m = _re.search(
            r"\bremove\b(.{1,40}?)\bfrom\s+my\s+industries\b", message, _re.IGNORECASE
        )

        if _add_skills_m:
            field     = "skills"
            op        = "add"
            raw_value = _add_skills_m.group(1).strip().strip(":,. ")
        elif _rem_skills_m:
            field     = "skills"
            op        = "remove"
            raw_value = _rem_skills_m.group(1).strip().strip(":,. ")
        elif _exp_m:
            field     = "years_experience"
            op        = "set"
            raw_value = next(g for g in _exp_m.groups() if g is not None)
        elif _loc_m:
            field     = "preferred_cities"
            op        = "set"
            raw_value = _loc_m.group(1).strip().strip(".,! ")
        elif _role_m:
            field     = "target_roles"
            op        = "set"
            raw_value = (
                (_role_m.group(1) or _role_m.group(2) or "").strip().strip(".,! ")
            )
        elif _ind_add_m:
            field     = "industries"
            op        = "add"
            raw_value = _ind_add_m.group(1).strip().strip(":,. ")
        elif _ind_rem_m:
            field     = "industries"
            op        = "remove"
            raw_value = _ind_rem_m.group(1).strip().strip(":,. ")
        else:
            # Regex fired but we can't parse a specific field — ask AI
            return self._answer_with_ai_fallback(
                user_id=user_id, message=message, profile=profile, save_user_message=False
            )

        if not raw_value:
            msg = (
                "لم أتمكن من استخراج القيمة. يرجى المحاولة مجدداً."
                if arabic else
                "I couldn't extract the value from your message. Could you rephrase?"
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        # ── Build update dict ────────────────────────────────────────────────
        updates: dict[str, Any] = {}
        old_value: Any = None
        new_value: Any = None

        if field == "years_experience":
            try:
                yrs = float(raw_value)
                old_value = self._profile_value(profile, "years_experience")
                new_value = int(yrs) if yrs == int(yrs) else yrs
                updates   = {"years_experience": yrs}
            except ValueError:
                msg = (
                    "لم أتمكن من قراءة عدد السنوات. حاول: 'خبرتي 8 سنوات'."
                    if arabic else
                    "Couldn't parse that as a number. Try: 'update my experience to 8 years'."
                )
                self._append_chat(user_id, "assistant", msg)
                return {"type": "clarification", "message": msg}

        elif field in ("skills", "certifications", "industries"):
            current_list = list(self._as_list(self._profile_value(profile, field)))
            old_value    = list(current_list)
            # Parse comma-separated values
            items = [v.strip() for v in _re.split(r"[,،]", raw_value) if v.strip()]
            if op == "add":
                existing_lower = {s.lower() for s in current_list}
                for item in items:
                    if item.lower() not in existing_lower:
                        current_list.append(item)
                        existing_lower.add(item.lower())
            else:  # remove
                remove_lower = {s.lower() for s in items}
                current_list = [s for s in current_list if s.lower() not in remove_lower]
            new_value = current_list
            updates   = {field: current_list}

        elif field == "preferred_cities":
            old_value   = list(self._as_list(self._profile_value(profile, "preferred_cities")))
            new_value   = [raw_value.title()]
            updates     = {"preferred_cities": new_value}

        elif field == "target_roles":
            old_value = list(self._as_list(self._profile_value(profile, "target_roles")))
            new_value = [raw_value.strip()]
            updates   = {"target_roles": new_value}

        # ── Persist ──────────────────────────────────────────────────────────
        try:
            upsert_profile(user_id=user_id, updates=updates)
        except Exception:
            logger.exception("_handle_profile_field_update: upsert failed user=%s", user_id)
            err_msg = (
                "حدث خطأ أثناء حفظ التحديث."
                if arabic else
                "There was an error saving the update. Please try again."
            )
            self._append_chat(user_id, "assistant", err_msg)
            return {"type": "error", "message": err_msg}

        # ── Build response ───────────────────────────────────────────────────
        _FIELD_LABELS: dict[str, str] = {
            "skills": "skills",
            "certifications": "certifications",
            "industries": "industries",
            "preferred_cities": "preferred city",
            "target_roles": "target role",
            "years_experience": "years of experience",
        }
        label = _FIELD_LABELS.get(field, field)

        if field == "years_experience":
            msg = f"Got it — I've updated your experience to **{new_value} years**."
        elif op == "add":
            added = ", ".join(v.strip() for v in _re.split(r"[,،]", raw_value) if v.strip())
            msg = f"Done! Added **{added}** to your {label}."
        elif op == "remove":
            removed = ", ".join(v.strip() for v in _re.split(r"[,،]", raw_value) if v.strip())
            msg = f"Removed **{removed}** from your {label}."
        else:
            msg = f"Updated your {label} to **{raw_value.strip()}**."

        if arabic:
            if field == "years_experience":
                msg = f"تم! تحديث خبرتك إلى **{new_value} سنوات**."
            elif op == "add":
                msg = f"تم إضافة **{raw_value.strip()}** إلى {label}."
            elif op == "remove":
                msg = f"تم حذف **{raw_value.strip()}** من {label}."
            else:
                msg = f"تم تحديث {label} إلى **{raw_value.strip()}**."

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "profile_update",
            "field": field,
            "operation": op,
            "old_value": old_value,
            "new_value": new_value,
            "message": msg,
        }

    # ── Application-specific lookup ─────────────────────────────────────────────

    def _handle_app_specific_lookup(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Search cached/DB applications for a specific company or role name.

        Detects: "did I apply to Emirates?", "status of my ADNOC application",
        "when did I apply to Carrefour?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Extract the company/entity name from the message.
        _co_m = _re.search(
            r"\b(?:appl(?:y|ied)\s+(?:to|at|for)|application\s+(?:at|to|with|for)|"
            r"apply\s+(?:to|at|for)|happened\s+with\s+my\s+application\s+(?:at|to)|"
            r"appl(?:y|ied)\s+(?:to|at|for)|did\s+I\s+appl[yi]\s+(?:to|at|for)|"
            r"candidacy\s+at|تقدمت\s+(?:إلى|ل|في))\s+([A-Za-z][^\s?!,.]{0,40}(?:\s+[A-Z][^\s?!,.]{0,20})*)",
            message, _re.IGNORECASE,
        )
        company_query = _co_m.group(1).strip() if _co_m else ""

        if not company_query:
            msg = (
                "أخبرني باسم الشركة للبحث عن طلبك."
                if arabic else
                "Which company are you asking about? Please include the company name."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        # Load application list (use cache if warm)
        apps: list[dict[str, Any]] = []
        try:
            from src.repositories import applications_repo
            apps = applications_repo.get_all(user_id=user_id)
        except Exception:
            logger.exception("_handle_app_specific_lookup: get_all failed user=%s", user_id)

        # Case-insensitive partial match on company field
        q_lower = company_query.lower()
        matches = [
            a for a in apps
            if isinstance(a, dict) and q_lower in (a.get("company") or a.get("employer_name") or "").lower()
        ]

        if not matches:
            msg = (
                f"لا يوجد أي طلب مسجل لدي يتعلق بـ **{company_query}**. "
                "ربما لم تتقدم بعد أو أن الاسم مختلف قليلاً."
                if arabic else
                f"I don't have any recorded application to **{company_query}**. "
                "You may not have applied yet, or the company name might be slightly different."
            )
            self._append_chat(user_id, "assistant", msg)
            return {
                "type": "application_detail",
                "found": False,
                "company_query": company_query,
                "message": msg,
            }

        app = matches[0]
        title   = app.get("title") or app.get("job_title") or "Unknown role"
        company = app.get("company") or app.get("employer_name") or company_query
        status  = (app.get("status") or "applied").replace("_", " ").title()
        applied = app.get("applied_at") or app.get("created_at") or ""
        date_str = str(applied)[:10] if applied else ""

        lines = [f"✅ **Yes — you've applied to {company}**\n"]
        lines.append(f"- **Role:** {title}")
        lines.append(f"- **Status:** {status}")
        if date_str:
            lines.append(f"- **Applied on:** {date_str}")
        if len(matches) > 1:
            lines.append(f"\n_{len(matches)} applications found for {company_query}. Showing the most recent._")

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "application_detail",
            "found": True,
            "company_query": company_query,
            "application": app,
            "message": msg,
        }

    # ── Company-targeted job search ─────────────────────────────────────────────

    def _handle_company_search(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Search for live jobs at a specific company via JSearch.

        Detects: "find jobs at ADNOC", "any openings at Emirates NBD",
        "is Carrefour hiring?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Extract company name — everything after "at" or "في/لدى/عند"
        _co_m = _re.search(
            r"\bat\s+([A-Za-z][^\s?!,.]{0,25}(?:\s+[A-Za-z][^\s?!,.]{0,20})*)"
            r"|\b(?:في|لدى|عند)\s+([^\s?!,.]{2,30})",
            message, _re.IGNORECASE,
        )
        # Fallback: "ADNOC is hiring" / "Is ADNOC hiring"
        if not _co_m:
            _co_m = _re.search(
                r"\b([A-Z][A-Za-z\s]{1,25})\s+(?:is\s+)?(?:hiring|recruiting|looking\s+for)\b",
                message,
            )

        company = (_co_m.group(1) or (_co_m.group(2) if _co_m.lastindex and _co_m.lastindex >= 2 else "")).strip() if _co_m else ""

        if not company:
            msg = (
                "أخبرني باسم الشركة التي تريد البحث عن وظائفها."
                if arabic else
                "Which company would you like to search jobs at? Please include the company name."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        # Build search query: "[company] jobs UAE"
        search_query = f"{company} jobs UAE"
        fetch = self._search_jsearch_meta(search_query)
        matches = fetch.items or []

        logger.info(
            "company_search: company=%r query=%r results=%d rate_limited=%s",
            company, search_query, len(matches), fetch.rate_limited,
        )

        if not matches:
            msg = (
                f"لم أجد وظائف حالية لدى **{company}** في الإمارات. "
                "قد تكون النتائج متأخرة — حاول لاحقاً أو ابحث على موقعهم مباشرة."
                if arabic else
                f"I couldn't find current openings at **{company}** in the UAE. "
                "Results may be delayed — try again later or check their careers page directly."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "no_results", "company": company, "message": msg}

        # Store in recent context so follow-up job-detail queries work
        self._store_search_matches_context(user_id, matches[:10])

        top = matches[:5]
        header = (
            f"وجدت **{len(top)}** وظيفة لدى **{company}** في الإمارات:"
            if arabic else
            f"Found **{len(top)} opening{'s' if len(top) != 1 else ''}** at **{company}** in the UAE:"
        )
        lines = [header, ""]
        for i, job in enumerate(top, 1):
            title   = job.get("title") or job.get("job_title") or "Role"
            loc     = job.get("location") or job.get("job_city") or "UAE"
            url     = job.get("apply_url") or job.get("job_apply_link") or ""
            lines.append(f"{i}. **{title}** — {loc}" + (f" ([Apply]({url}))" if url else ""))

        if len(matches) > 5:
            lines.append(f"\n_…and {len(matches) - 5} more. Say 'show me more' to see them._")

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_matches",
            "company": company,
            "jobs": top,
            "total_found": len(matches),
            "message": msg,
        }

    # ── Salary-filtered job search ──────────────────────────────────────────────

    def _handle_salary_filtered_search(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Search jobs and filter by a minimum salary threshold.

        Parses messages like "find HSE jobs paying above 20k AED" or
        "QHSE roles with minimum salary 25000".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Extract salary threshold (AED amount, supports "20k" / "20,000" / "20000")
        _sal_m = _re.search(
            r"(?:above|over|more\s+than|at\s+least|minimum(?:\s+of)?|لا\s+يقل\s+عن|أعلى\s+من)\s+"
            r"([\d,]+(?:\.\d+)?)\s*([kK]?)\s*(?:AED|aed|درهم)?",
            message, _re.IGNORECASE,
        )
        # Fallback: "25k AED and above"
        if not _sal_m:
            _sal_m = _re.search(r"([\d,]+(?:\.\d+)?)\s*([kK])\s+(?:AED\s+)?(?:and\s+above|or\s+more|minimum|plus)", message, _re.IGNORECASE)

        min_salary: int = 0
        if _sal_m:
            raw_num = _sal_m.group(1).replace(",", "")
            suffix  = (_sal_m.group(2) or "").lower()
            try:
                val = float(raw_num)
                min_salary = int(val * 1000 if suffix == "k" else val)
            except ValueError:
                pass

        # Extract role name — everything before the salary clause
        role = ""
        _role_m = _re.search(
            r"\b(?:find|show|search|look\s+for)\s+(?:me\s+)?(.{3,40}?)\s+(?:jobs?|roles?|positions?)",
            message, _re.IGNORECASE,
        )
        if _role_m:
            role = _role_m.group(1).strip().strip(", ")
        if not role:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else ""

        if not role:
            msg = (
                "أخبرني بالمسمى الوظيفي الذي تبحث عنه مع الحد الأدنى للراتب."
                if arabic else
                "Please tell me the role you're looking for along with the minimum salary. "
                "For example: 'find HSE jobs paying above 20k AED'."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        fetch = self._search_jsearch_meta(role)
        all_matches = fetch.items or []

        # Post-fetch salary filter when we have a threshold
        filtered = all_matches
        if min_salary > 0:
            def _extract_salary_num(job: dict) -> int:
                sal_str = str(job.get("salary_string") or job.get("salary") or "")
                nums = _re.findall(r"[\d,]+", sal_str.replace(",", ""))
                return max((int(n) for n in nums if int(n) > 1000), default=0)

            salary_filtered = [j for j in all_matches if _extract_salary_num(j) >= min_salary]
            filtered = salary_filtered if salary_filtered else all_matches

        self._store_search_matches_context(user_id, filtered[:10])
        top = filtered[:5]

        if not top:
            threshold_str = f"AED {min_salary:,}/month" if min_salary else ""
            msg = (
                f"لم أجد وظائف {role} في الإمارات{' بهذا الراتب' if min_salary else ''}."
                if arabic else
                f"No {role} jobs found in the UAE"
                + (f" paying above {threshold_str}" if min_salary else "") + "."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "no_results", "message": msg}

        threshold_label = f"AED {min_salary:,}/month" if min_salary else ""
        header = (
            f"وجدت **{len(top)}** وظيفة لـ **{role}**"
            + (f" براتب فوق {threshold_label}" if threshold_label else "") + ":"
            if arabic else
            f"Found **{len(top)} {role} role{'s' if len(top) != 1 else ''}**"
            + (f" paying above {threshold_label}" if threshold_label else "") + ":"
        )
        lines = [header, ""]
        for i, job in enumerate(top, 1):
            title   = job.get("title") or job.get("job_title") or "Role"
            company = job.get("company") or job.get("employer_name") or ""
            loc     = job.get("location") or job.get("job_city") or "UAE"
            sal     = job.get("salary_string") or ""
            url     = job.get("apply_url") or job.get("job_apply_link") or ""
            line = f"{i}. **{title}**" + (f" at {company}" if company else "") + f" — {loc}"
            if sal:
                line += f" | {sal}"
            if url:
                line += f" ([Apply]({url}))"
            lines.append(line)

        if min_salary and len(salary_filtered) < len(all_matches):
            lines.append(
                f"\n_Salary data isn't always available — showing {len(top)} of {len(all_matches)} "
                f"results (some may not display salary). All {len(all_matches)} are shown if none "
                f"listed exact salary above {threshold_label}._"
            )

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_matches",
            "role": role,
            "min_salary_aed": min_salary,
            "jobs": top,
            "total_found": len(filtered),
            "message": msg,
        }

    # ── Employment-type filter search ───────────────────────────────────────────

    def _handle_employment_type_search(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Search jobs filtered by employment type (remote, hybrid, contract, part-time).

        Parses messages like "find remote HSE jobs" or "contract QHSE roles in Dubai".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Detect employment type
        _type_map = {
            "remote":      "remote",
            "hybrid":      "hybrid",
            "part-time":   "part-time",
            "part time":   "part-time",
            "parttime":    "part-time",
            "full-time":   "full-time",
            "full time":   "full-time",
            "fulltime":    "full-time",
            "contract":    "contract",
            "freelance":   "freelance",
            "temporary":   "temporary",
            "temp":        "temporary",
            "دوام جزئي":  "part-time",
            "دوام كامل":  "full-time",
            "عقد":         "contract",
            "عن بُعد":    "remote",
        }
        emp_type = ""
        lower_msg = message.lower()
        for kw, label in _type_map.items():
            if kw in lower_msg:
                emp_type = label
                break

        # Extract role — after the employment type keyword, before "jobs/roles/in"
        role = ""
        _role_m = _re.search(
            r"(?:remote|hybrid|part[- ]?time|full[- ]?time|contract|freelance|temporary)\s+(.{2,30}?)\s+(?:jobs?|roles?|positions?|work)\b",
            message, _re.IGNORECASE,
        )
        if _role_m:
            role = _role_m.group(1).strip()
        if not role:
            _role_m2 = _re.search(
                r"\b(?:find|show|search\s+for)\s+(?:me\s+)?(?:remote|hybrid|part[- ]?time|full[- ]?time|contract|freelance|temporary)\s+(.{3,30}?)\s+(?:jobs?|roles?|in\b|$)",
                message, _re.IGNORECASE,
            )
            if _role_m2:
                role = _role_m2.group(1).strip()
        if not role:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else ""

        # Extract location hint
        _loc_m = _re.search(r"\bin\s+(Dubai|Abu\s+Dhabi|Sharjah|Ajman|Fujairah|Al\s+Ain|UAE)\b", message, _re.IGNORECASE)
        location = _loc_m.group(1).strip() if _loc_m else ""

        # Build search query with employment type modifier
        if role:
            query = f"{emp_type} {role}" if emp_type else role
        else:
            query = f"{emp_type} jobs" if emp_type else "jobs"
        query = query.strip()

        fetch = self._search_jsearch_meta(query, location)
        matches = fetch.items or []

        # Post-filter: prefer items where employment_type matches
        if emp_type and matches:
            pref = [
                j for j in matches
                if emp_type.lower() in (j.get("employment_type") or j.get("job_employment_type") or "").lower()
            ]
            if pref:
                matches = pref + [j for j in matches if j not in pref]

        self._store_search_matches_context(user_id, matches[:10])
        top = matches[:5]

        if not top:
            msg = (
                f"لم أجد وظائف {emp_type} لـ {role or 'الوظائف'} في الإمارات."
                if arabic else
                f"No {emp_type} {role} jobs found in the UAE right now."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "no_results", "message": msg}

        header = (
            f"وجدت **{len(top)}** وظيفة {emp_type}{(' لـ ' + role) if role else ''} في الإمارات:"
            if arabic else
            f"Found **{len(top)} {emp_type} {role} {'role' if role else 'job'}{'s' if len(top) != 1 else ''}** in the UAE:"
        )
        lines = [header, ""]
        for i, job in enumerate(top, 1):
            title   = job.get("title") or job.get("job_title") or "Role"
            company = job.get("company") or job.get("employer_name") or ""
            loc     = job.get("location") or job.get("job_city") or "UAE"
            etype   = job.get("employment_type") or job.get("job_employment_type") or ""
            url     = job.get("apply_url") or job.get("job_apply_link") or ""
            line = f"{i}. **{title}**" + (f" at {company}" if company else "") + f" — {loc}"
            if etype and etype.lower() != emp_type.lower():
                line += f" ({etype})"
            if url:
                line += f" ([Apply]({url}))"
            lines.append(line)

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_matches",
            "employment_type": emp_type,
            "role": role,
            "jobs": top,
            "total_found": len(matches),
            "message": msg,
        }

    # ── Follow-up timing advice ─────────────────────────────────────────────────

    def _handle_followup_timing(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return deterministic UAE-context follow-up timing advice.

        Covers: "when should I follow up?", "is it too early to follow up?",
        "how many days before following up?", "how do I follow up?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Check if a specific company is mentioned — look for an application record
        _co_m = _re.search(
            r"\bfollow\s+up\s+(?:with|on|at|to)\s+([A-Za-z][^\s?!,.]{0,30}(?:\s+[A-Z][^\s?!,.]{0,20})*)",
            message, _re.IGNORECASE,
        )
        company_name = _co_m.group(1).strip() if _co_m else ""
        applied_date = ""

        if company_name:
            try:
                from src.repositories import applications_repo
                apps = applications_repo.get_all(user_id=user_id)
                match = next(
                    (a for a in apps
                     if isinstance(a, dict)
                     and company_name.lower() in (a.get("company") or "").lower()),
                    None,
                )
                if match:
                    applied_date = str(match.get("applied_at") or match.get("created_at") or "")[:10]
            except Exception:
                pass

        if arabic:
            lines = [
                "**متى تتابع بعد تقديم طلبك؟**\n",
                "- **بعد تقديم طلب إلكتروني:** انتظر **أسبوع إلى أسبوعين** قبل المتابعة.",
                "- **بعد مقابلة:** تابع خلال **3-5 أيام عمل**.",
                "- **بعد رسالة متابعة أولى:** انتظر **أسبوعاً آخر** قبل المتابعة مجدداً.",
                "\n**نصائح للإمارات:**",
                "- تواصل عبر **LinkedIn** أو **البريد الإلكتروني المهني** — الاتصال الهاتفي غير مناسب عادةً.",
                "- ابدأ رسالتك بـ «أرجو المعذرة على إزعاجكم» واذكر اسم الوظيفة التي تقدمت إليها.",
                "- حافظ على نبرة مهذبة ومحترمة.",
            ]
            if company_name and applied_date:
                lines.insert(1, f"تقدمت إلى **{company_name}** بتاريخ **{applied_date}**. "
                                "إذا مر أسبوع أو أكثر، يمكنك المتابعة الآن.\n")
        else:
            lines = [
                "**When to follow up after applying in the UAE:**\n",
                "- **After an online application:** wait **1–2 weeks** before following up.",
                "- **After an interview:** follow up within **3–5 business days**.",
                "- **After a first follow-up with no reply:** wait **another week** before reaching out again.",
                "\n**UAE-specific tips:**",
                "- Reach out via **LinkedIn** or a **professional email** — cold calling HR is generally unwelcome.",
                "- Keep it brief: reference the role title, the date you applied, and express continued interest.",
                "- Close with: _\"I remain very interested in this opportunity and would welcome the chance to discuss further.\"_",
                "- Avoid following up more than **twice** — beyond that, assume they're not moving forward.",
            ]
            if company_name and applied_date:
                lines.insert(1, f"You applied to **{company_name}** on **{applied_date}**. "
                                "If it's been 1+ week, now's a good time to follow up.\n")
            elif company_name:
                lines.insert(1, f"For **{company_name}** — if you applied online, wait 1–2 weeks before reaching out.\n")

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "followup_timing",
            "company": company_name,
            "applied_date": applied_date,
            "message": msg,
        }

    # ── Industry-based job search ───────────────────────────────────────────────

    def _handle_industry_search(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Search for jobs filtered by industry/sector.

        Detects phrases like "find jobs in oil and gas", "construction sector
        jobs in Dubai", "healthcare vacancies in Abu Dhabi".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Known industry keywords → normalised label for the search query
        _INDUSTRY_MAP = [
            (r"oil\s+(?:and|&)\s+gas|petroleum", "oil and gas"),
            (r"construction|building", "construction"),
            (r"finance|banking|financial", "finance"),
            (r"information\s+technology|IT\b|software|tech(?:nology)?", "technology"),
            (r"health(?:care)?|medical|pharmaceutical", "healthcare"),
            (r"real\s+estate|property", "real estate"),
            (r"hospitality|hotel|tourism", "hospitality"),
            (r"logistics|supply\s+chain|transport(?:ation)?", "logistics"),
            (r"manufacturing|industrial", "manufacturing"),
            (r"education|academic", "education"),
            (r"telecom(?:munications?)?", "telecommunications"),
            (r"energy|renewable|utilities", "energy"),
            (r"aviation|aerospace|airline", "aviation"),
            (r"maritime|shipping|ports?", "maritime"),
            (r"legal|law", "legal"),
            (r"accounting|audit", "accounting"),
            (r"insurance", "insurance"),
            (r"retail|e-?commerce", "retail"),
            (r"media|advertising|marketing", "media"),
            (r"government|public\s+sector", "government"),
        ]

        industry = ""
        for pattern, label in _INDUSTRY_MAP:
            if _re.search(pattern, message, _re.IGNORECASE):
                industry = label
                break

        if not industry:
            # Extract the word(s) after "in the" / "in" as a fallback
            _ind_m = _re.search(r"\bjobs?\s+in\s+(?:the\s+)?([a-z][a-z\s]{2,25})\b", message, _re.IGNORECASE)
            industry = _ind_m.group(1).strip() if _ind_m else ""

        # Optional location hint
        _loc_m = _re.search(r"\bin\s+(Dubai|Abu\s+Dhabi|Sharjah|Ajman|Fujairah|Al\s+Ain|UAE)\b", message, _re.IGNORECASE)
        location = _loc_m.group(1).strip() if _loc_m else ""

        if not industry:
            msg = (
                "أخبرني بالقطاع الذي تريد البحث فيه، مثل: 'وظائف في قطاع النفط والغاز'."
                if arabic else
                "Which industry are you looking for? E.g. 'find jobs in oil and gas' or 'healthcare sector roles'."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        # Optional role hint from profile or message
        role = ""
        _role_m = _re.search(r"\b(?:as\s+(?:an?\s+)|for\s+(?:an?\s+))([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", message)
        if _role_m:
            role = _role_m.group(1).strip()
        if not role:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else ""

        search_query = f"{role} {industry}" if role else f"jobs {industry}"
        search_query = search_query.strip()

        fetch = self._search_jsearch_meta(search_query, location)
        matches = fetch.items or []

        self._store_search_matches_context(user_id, matches[:10])
        top = matches[:5]

        if not top:
            msg = (
                f"لم أجد وظائف في قطاع **{industry}** في الإمارات حالياً."
                if arabic else
                f"No **{industry}** jobs found in the UAE right now. Try a broader search or check back later."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "no_results", "industry": industry, "message": msg}

        loc_label = f" in {location}" if location else " in the UAE"
        header = (
            f"وجدت **{len(top)}** وظيفة في قطاع **{industry}**{' في ' + location if location else ' في الإمارات'}:"
            if arabic else
            f"Found **{len(top)} {industry} role{'s' if len(top) != 1 else ''}**{loc_label}:"
        )
        lines = [header, ""]
        for i, job in enumerate(top, 1):
            title   = job.get("title") or job.get("job_title") or "Role"
            company = job.get("company") or job.get("employer_name") or ""
            loc     = job.get("location") or job.get("job_city") or "UAE"
            url     = job.get("apply_url") or job.get("job_apply_link") or ""
            line = f"{i}. **{title}**" + (f" at {company}" if company else "") + f" — {loc}"
            if url:
                line += f" ([Apply]({url}))"
            lines.append(line)

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_matches",
            "industry": industry,
            "jobs": top,
            "total_found": len(matches),
            "message": msg,
        }

    # ── Job comparison ──────────────────────────────────────────────────────────

    def _handle_job_comparison(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Compare two cached search results side-by-side.

        Detects: "compare job 1 and job 2", "which is better, job 1 or 3?",
        "job 1 vs job 3".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Extract ordinal/numeric identifiers for the two jobs
        _ORD_MAP = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4,
                    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4}

        nums = _re.findall(r"\b(?:[1-5]|first|second|third|fourth|fifth)\b", message, _re.IGNORECASE)
        idx_a = _ORD_MAP.get(nums[0].lower(), 0) if len(nums) >= 1 else 0
        idx_b = _ORD_MAP.get(nums[1].lower(), 1) if len(nums) >= 2 else 1

        ctx = self._get_recent_context(user_id)
        matches: list[dict[str, Any]] = ctx.get("recent_search_matches") or []

        if not matches:
            msg = (
                "لا توجد نتائج بحث حديثة للمقارنة. ابحث عن وظائف أولاً ثم اطلب المقارنة."
                if arabic else
                "No recent search results to compare. Search for jobs first, then ask me to compare them."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        # Clamp indices to available list
        idx_a = min(idx_a, len(matches) - 1)
        idx_b = min(idx_b, len(matches) - 1)
        if idx_a == idx_b:
            idx_b = min(idx_a + 1, len(matches) - 1)

        job_a = matches[idx_a]
        job_b = matches[idx_b]

        def _fmt_job(job: dict, label: str) -> list[str]:
            title   = job.get("title") or job.get("job_title") or "Unknown role"
            company = job.get("company") or job.get("employer_name") or "Unknown company"
            loc     = job.get("location") or job.get("job_city") or "UAE"
            sal     = job.get("salary_string") or "Not listed"
            etype   = job.get("employment_type") or job.get("job_employment_type") or "Not specified"
            url     = job.get("apply_url") or job.get("job_apply_link") or ""
            lines   = [f"**{label}:** {title} at {company}"]
            lines.append(f"  - 📍 {loc}")
            lines.append(f"  - 💰 {sal}")
            lines.append(f"  - 🕐 {etype}")
            if url:
                lines.append(f"  - [Apply here]({url})")
            return lines

        n_a = idx_a + 1
        n_b = idx_b + 1
        header = f"**Comparing Job {n_a} vs Job {n_b}:**\n"
        lines = [header] + _fmt_job(job_a, f"Job {n_a}") + [""] + _fmt_job(job_b, f"Job {n_b}")

        # Simple highlights
        sal_a = job_a.get("salary_string") or ""
        sal_b = job_b.get("salary_string") or ""
        if sal_a or sal_b:
            lines.append(f"\n**Salary:** Job {n_a}: {sal_a or 'N/A'} | Job {n_b}: {sal_b or 'N/A'}")

        lines.append(
            f"\nSay **'tell me more about job {n_a}'** or **'tell me more about job {n_b}'** "
            "for full details, or **'apply to job X'** to track an application."
        )

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_comparison",
            "job_a_index": idx_a,
            "job_b_index": idx_b,
            "job_a": job_a,
            "job_b": job_b,
            "message": msg,
        }

    # ── Search result count ─────────────────────────────────────────────────────

    def _handle_result_count(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return the count from the most recent cached job search.

        Detects: "how many jobs did you find?", "total number of results",
        "how many matches were there?".
        """
        arabic = self._is_arabic_text(message)

        history = self._get_session_job_search_history(user_id)
        summary = self._get_last_job_search_summary(user_id)
        count = int(summary.get("count") or 0) if summary else 0
        role = str(
            (summary or {}).get("role")
            or (summary or {}).get("query")
            or ""
        ).strip()
        city = str((summary or {}).get("city") or "").strip()
        top_match = (summary or {}).get("top_match") or {}
        if not isinstance(top_match, dict):
            top_match = {}
        total_count = sum(
            int(item.get("count") or 0)
            for item in history
            if isinstance(item, dict)
        ) if history else count

        if summary is None:
            msg = (
                "لا توجد لدي نتائج بحث محفوظة في هذه المحادثة. ابدأ بالبحث عن وظيفة أولاً."
                if arabic else
                "I don't have any job searches saved in this conversation yet. Start a job search first and then ask."
            )
        elif arabic:
            role_part = f" عن **{role}**" if role else ""
            city_part = f" في **{city}**" if city else ""
            top_title = str(top_match.get("title") or "").strip()
            top_company = str(top_match.get("company") or "").strip()
            top_part = (
                f" أعلى نتيجة كانت **{top_title}**"
                + (f" في **{top_company}**." if top_company else ".")
                if top_title else ""
            )
            msg = (
                f"في هذه المحادثة، آخر بحث وجد **{count}** وظيفة{role_part}{city_part}."
                + (
                    f" إجمالي النتائج المسجلة منذ بداية المحادثة: **{total_count}**."
                    if len(history) > 1 else ""
                )
                + (" " + top_part if top_part else "")
            )
        else:
            role_part = f" for **{role}**" if role else ""
            city_part = f" in **{city}**" if city else ""
            top_title = str(top_match.get("title") or "").strip()
            top_company = str(top_match.get("company") or "").strip()
            top_part = (
                f" Top match: **{top_title}**"
                + (f" at **{top_company}**." if top_company else ".")
                if top_title else ""
            )
            msg = (
                f"In this conversation, my last search returned **{count} result{'s' if count != 1 else ''}**"
                f"{role_part}{city_part}."
                + (
                    f" Total recorded since the start of this conversation: **{total_count}**."
                    if len(history) > 1 else ""
                )
                + top_part
                + (" Say 'show more' to see more results." if count > 5 else "")
            )

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "result_count",
            "count": count,
            "total_count": total_count,
            "search_count": len(history) if history else (1 if summary else 0),
            "role": role,
            "city": city,
            "top_match": top_match,
            "message": msg,
        }

    # ── Certification / qualification advice ────────────────────────────────────

    def _handle_certification_advice(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return UAE-context certification advice for a role or industry.

        Detects: "what certifications do I need for HSE?", "required qualifications
        for finance jobs", "what certifications for project management?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Certification knowledge base (UAE-relevant, ordered by sector)
        _CERT_DB: dict[str, dict[str, Any]] = {
            "hse":          {"label": "HSE / QHSE / EHS",
                             "certs": ["NEBOSH IGC", "IOSH Managing Safely", "ISO 45001 Lead Auditor",
                                       "ISO 14001 Lead Auditor", "NEBOSH Diploma", "OHSAS 18001"],
                             "note": "NEBOSH IGC is the gold standard for UAE HSE roles."},
            "qhse":         {"label": "QHSE",
                             "certs": ["NEBOSH IGC", "IOSH", "ISO 9001 Lead Auditor",
                                       "ISO 45001 Lead Auditor", "ISO 14001 Lead Auditor"],
                             "note": "ISO 9001 is essential for Quality-focused QHSE roles."},
            "finance":      {"label": "Finance / Banking",
                             "certs": ["CFA", "CMA", "CPA", "ACCA", "MBA (Finance)", "CIMA", "CFP"],
                             "note": "CFA is highly valued in UAE investment and banking roles."},
            "project management": {"label": "Project Management",
                                   "certs": ["PMP", "PRINCE2", "PMI-ACP", "PMI-RMP", "MSP"],
                                   "note": "PMP is almost universally required for PM roles in UAE."},
            "hr":           {"label": "Human Resources",
                             "certs": ["CIPD Level 5", "SHRM-CP", "PHR", "CHRP", "GPHR"],
                             "note": "CIPD is highly recognised by UAE multinationals."},
            "supply chain": {"label": "Supply Chain / Logistics",
                             "certs": ["CIPS", "APICS CSCP", "CSCMP", "Lean Six Sigma Green Belt"],
                             "note": "CIPS is the benchmark certification for procurement in UAE."},
            "it":           {"label": "IT / Technology",
                             "certs": ["AWS Certified Solutions Architect", "Azure Administrator",
                                       "CISSP", "PMP", "ITIL", "Google Cloud Professional"],
                             "note": "Cloud certifications (AWS/Azure) are in highest demand in UAE tech."},
            "engineering":  {"label": "Engineering",
                             "certs": ["CEng (UK)", "PE (US)", "PMP", "Chartered Engineer UAE",
                                       "ISO 9001 Lead Auditor"],
                             "note": "Professional engineering registration can significantly boost offers in UAE."},
            "real estate":  {"label": "Real Estate",
                             "certs": ["RERA (Dubai)", "CIPS", "CPM", "CCIM"],
                             "note": "RERA registration is mandatory for all real estate brokers in Dubai."},
            "accounting":   {"label": "Accounting / Audit",
                             "certs": ["CPA", "ACCA", "CMA", "CIA", "CIMA", "CA (ICAEW)"],
                             "note": "ACCA is widely accepted across UAE Big 4 and corporates."},
            "marketing":    {"label": "Marketing / Digital",
                             "certs": ["Google Ads Certification", "HubSpot Marketing", "Meta Blueprint",
                                       "CIM", "Chartered Marketer"],
                             "note": "Digital certifications are most in-demand for UAE marketing roles."},
            "data":         {"label": "Data Science / Analytics",
                             "certs": ["Google Data Analytics", "AWS Data Analytics", "Tableau Desktop",
                                       "Microsoft PL-300 (Power BI)", "Python for Data Science"],
                             "note": "Power BI and Tableau skills are heavily sought in UAE."},
        }

        # Match role/industry from message to knowledge base
        sector = ""
        sector_data: dict[str, Any] = {}
        msg_lower = message.lower()
        for key, data in _CERT_DB.items():
            if key in msg_lower or any(w in msg_lower for w in key.split()):
                sector = key
                sector_data = data
                break

        # Fallback: check profile target roles
        if not sector_data:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            for role_str in target_roles:
                role_lower = str(role_str).lower()
                for key, data in _CERT_DB.items():
                    if key in role_lower or any(w in role_lower for w in key.split()):
                        sector = key
                        sector_data = data
                        break
                if sector_data:
                    break

        if not sector_data:
            msg = (
                "أخبرني بالقطاع أو المسمى الوظيفي الذي تريد الشهادات المناسبة له، مثل: 'ما الشهادات المطلوبة لوظائف HSE؟'"
                if arabic else
                "Which role or industry are you asking about? For example: "
                "'what certifications do I need for HSE roles?' or 'qualifications for finance jobs?'"
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        label = sector_data["label"]
        certs = sector_data["certs"]
        note  = sector_data.get("note", "")

        if arabic:
            lines = [f"**الشهادات الموصى بها لوظائف {label} في الإمارات:**\n"]
            for c in certs:
                lines.append(f"- {c}")
            if note:
                lines.append(f"\n💡 {note}")
        else:
            lines = [f"**Recommended certifications for {label} roles in the UAE:**\n"]
            for i, c in enumerate(certs, 1):
                lines.append(f"{i}. {c}")
            if note:
                lines.append(f"\n💡 **Tip:** {note}")
            lines.append(
                "\nSay **'find jobs in " + (sector or label) + "'** to search live openings, "
                "or **'update my certifications'** to save these to your profile."
            )

        msg_text = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg_text)
        return {
            "type": "certification_advice",
            "sector": sector,
            "certifications": certs,
            "message": msg_text,
        }

    # ── Seniority-filtered search ───────────────────────────────────────────────

    def _handle_seniority_search(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Search for jobs filtered by seniority level.

        Detects: "find senior HSE jobs", "entry level QHSE positions",
        "manager-level roles", "director positions in Dubai".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Detect seniority level
        _SENIORITY_MAP = [
            (r"director[- ]?level|director", "Director"),
            (r"executive[- ]?level|vp|vice\s+president|c[- ]?level", "Executive"),
            (r"manager[- ]?level|senior\s+manager", "Senior Manager"),
            (r"senior|sr\.?", "Senior"),
            (r"mid[- ]?level|middle\s+level|experienced", ""),
            (r"junior|jr\.?", "Junior"),
            (r"entry[- ]?level|graduate|fresher|fresh\s+graduate|intern(?:ship)?", "Entry Level"),
        ]

        seniority_label = ""
        seniority_prefix = ""
        for pattern, prefix in _SENIORITY_MAP:
            if _re.search(pattern, message, _re.IGNORECASE):
                seniority_label = prefix or "Mid-level"
                seniority_prefix = prefix
                break

        # Extract role — everything between the seniority keyword and "jobs/roles"
        role = ""
        _role_m = _re.search(
            r"(?:senior|junior|entry[- ]?level|mid[- ]?level|director|manager[- ]?level|graduate|intern)\s+"
            r"(.{2,35}?)\s+(?:jobs?|roles?|positions?|vacancies|opportunities?)\b",
            message, _re.IGNORECASE,
        )
        if _role_m:
            role = _role_m.group(1).strip()
        # Fallback: after "find [seniority]" before "jobs"
        if not role:
            _role_m2 = _re.search(
                r"\b(?:find|show|search\s+for|look\s+for)\s+(?:me\s+)?(?:senior|junior|entry[- ]?level|mid[- ]?level|director)\s+(.{3,30}?)\s+(?:jobs?|roles?|in\b|$)",
                message, _re.IGNORECASE,
            )
            if _role_m2:
                role = _role_m2.group(1).strip()
        if not role:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else ""

        # Location hint
        _loc_m = _re.search(r"\bin\s+(Dubai|Abu\s+Dhabi|Sharjah|Ajman|UAE)\b", message, _re.IGNORECASE)
        location = _loc_m.group(1).strip() if _loc_m else ""

        if not role:
            msg = (
                "أخبرني بالمسمى الوظيفي مع المستوى، مثل: 'ابحث عن وظائف HSE للمبتدئين'."
                if arabic else
                "Which role are you looking for? E.g. 'find senior HSE jobs' or 'entry level QHSE positions'."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        search_query = f"{seniority_prefix} {role}".strip() if seniority_prefix else role
        fetch = self._search_jsearch_meta(search_query, location)
        matches = fetch.items or []

        self._store_search_matches_context(user_id, matches[:10])
        top = matches[:5]

        if not top:
            msg = (
                f"لم أجد وظائف {seniority_label} لـ {role} في الإمارات."
                if arabic else
                f"No {seniority_label} {role} jobs found in the UAE right now."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "no_results", "message": msg}

        loc_label = f" in {location}" if location else " in the UAE"
        header = (
            f"وجدت **{len(top)}** وظيفة {'من مستوى ' + seniority_label if seniority_label else ''} لـ **{role}**{' في ' + location if location else ' في الإمارات'}:"
            if arabic else
            f"Found **{len(top)} {seniority_label} {role} role{'s' if len(top) != 1 else ''}**{loc_label}:"
        )
        lines = [header, ""]
        for i, job in enumerate(top, 1):
            title   = job.get("title") or job.get("job_title") or "Role"
            company = job.get("company") or job.get("employer_name") or ""
            loc     = job.get("location") or job.get("job_city") or "UAE"
            url     = job.get("apply_url") or job.get("job_apply_link") or ""
            line = f"{i}. **{title}**" + (f" at {company}" if company else "") + f" — {loc}"
            if url:
                line += f" ([Apply]({url}))"
            lines.append(line)

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_matches",
            "seniority": seniority_label,
            "role": role,
            "jobs": top,
            "total_found": len(matches),
            "message": msg,
        }

    # ── Job market pulse ────────────────────────────────────────────────────────

    def _handle_market_pulse(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return a market insight by running a live JSearch count + commentary.

        Detects: "how's the job market for HSE in UAE?", "are there many construction
        jobs?", "how competitive is finance in Dubai?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Extract the role/industry from the message
        role = ""
        _role_m = _re.search(
            r"(?:market\s+for|jobs?\s+(?:in|for)|for\s+(?:an?\s+)?|competitive\s+(?:for|in))\s+"
            r"([A-Za-z][A-Za-z\s]{2,30}?)(?:\s+(?:in\s+(?:the\s+)?UAE|jobs?|roles?|in\s+Dubai|in\s+Abu\s+Dhabi)|\??$)",
            message, _re.IGNORECASE,
        )
        if _role_m:
            role = _role_m.group(1).strip().rstrip("? ,.")
        if not role:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else ""

        if not role:
            msg = (
                "أخبرني بالمسمى الوظيفي أو القطاع الذي تريد معرفة أوضاع سوق العمل فيه."
                if arabic else
                "Which role or sector are you asking about? E.g. 'how's the market for HSE in UAE?'"
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "clarification", "message": msg}

        fetch = self._search_jsearch_meta(role)
        count = len(fetch.items or [])

        # Market commentary based on result count
        if count >= 15:
            sentiment = "very active" if not arabic else "نشط جداً"
            advice    = "Opportunities are plentiful — now is a great time to apply."
            advice_ar = "الفرص وفيرة — الوقت مناسب جداً للتقديم."
        elif count >= 8:
            sentiment = "moderately active" if not arabic else "نشط بشكل معتدل"
            advice    = "There are solid opportunities — a tailored CV and cover letter will help you stand out."
            advice_ar = "هناك فرص جيدة — تأكد من تخصيص سيرتك الذاتية."
        elif count >= 3:
            sentiment = "competitive" if not arabic else "تنافسي"
            advice    = "The market is tight — focus on networking and tailoring each application carefully."
            advice_ar = "السوق تنافسي — ركز على التواصل المهني وتخصيص كل طلب."
        else:
            sentiment = "limited right now" if not arabic else "محدود حالياً"
            advice    = "Few openings at the moment — consider broadening your search to related roles or nearby cities."
            advice_ar = "فرص محدودة حالياً — فكر في توسيع بحثك لأدوار مشابهة أو مدن مجاورة."

        if arabic:
            msg = (
                f"**سوق العمل لـ {role} في الإمارات — {sentiment}**\n\n"
                f"وجدت **{count} وظيفة** حالية في لقطة الوقت الفعلي.\n\n"
                f"💡 {advice_ar}"
            )
        else:
            msg = (
                f"**Job market for {role} in the UAE — {sentiment}**\n\n"
                f"Live snapshot: **{count} active opening{'s' if count != 1 else ''}** found right now.\n\n"
                f"💡 {advice}\n\n"
                f"Say **'find {role} jobs'** to see the full list."
            )

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "market_pulse",
            "role": role,
            "active_count": count,
            "sentiment": sentiment,
            "message": msg,
        }

    def _handle_notice_period(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Handle notice period declarations and queries.

        Detects: "my notice period is 30 days", "I'm available immediately",
        "what is my notice period?", "update my notice period to 1 month".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Is this a query (read) or a declaration (write)?
        is_query = bool(_re.search(
            r"\bwhat(?:'s|\s+is)\s+my\s+notice\s+period\b", message, _re.IGNORECASE
        ))

        if is_query:
            current = self._profile_value(profile, "notice_period") or ""
            if current:
                msg = (
                    f"فترة الإشعار المسجلة لديك هي: **{current}**."
                    if arabic else
                    f"Your notice period is set to: **{current}**."
                )
            else:
                msg = (
                    "لم تُحدّد فترة إشعار بعد. أخبرني بها، مثلاً: 'فترة إشعاري شهر واحد'."
                    if arabic else
                    "You haven't set a notice period yet. Tell me — e.g. 'my notice period is 30 days'."
                )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "notice_period_readback", "notice_period": current, "message": msg}

        # Parse the declared value
        _IMMEDIATELY = _re.search(
            r"\b(?:immediately|now|right\s+away|متاح\s+الآن|فوراً)\b", message, _re.IGNORECASE
        )
        if _IMMEDIATELY or _re.search(r"\bavailable\s+immediately\b|\bimmediate\s+joiner\b", message, _re.IGNORECASE):
            value = "Immediate"
        else:
            _val_m = _re.search(
                r"(?:notice\s+period\s+(?:is|was|=)|join\s+in|start\s+in|available\s+(?:in|from|within))\s*"
                r"(\d+\s*(?:day|week|month|year)s?|immediately|one|two|three|four)\b",
                message, _re.IGNORECASE,
            )
            value = _val_m.group(1).strip().title() if _val_m else ""

        if value:
            upsert_profile(user_id=user_id, updates={"notice_period": value})
            msg = (
                f"تم تحديث فترة الإشعار إلى: **{value}**. سيظهر ذلك في طلباتك القادمة."
                if arabic else
                f"Notice period updated to **{value}**. This will be included in your applications."
            )
        else:
            msg = (
                "أخبرني بفترة الإشعار، مثلاً: '30 يوماً' أو 'شهر واحد' أو 'متاح فوراً'."
                if arabic else
                "What's your notice period? E.g. '30 days', '1 month', or 'immediately available'."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "notice_period_update", "notice_period": value or None, "message": msg}

    def _handle_visa_status(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Handle visa/work permit status declarations and queries.

        Detects: "I'm on a spouse visa", "I have a work permit",
        "do I need a visa?", "update my visa status".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # General "do I need a visa?" info request
        is_info_request = bool(_re.search(
            r"\bdo\s+I\s+need\s+a\s+(?:work\s+)?visa\b", message, _re.IGNORECASE
        ))
        is_query = bool(_re.search(
            r"\bwhat(?:'s|\s+is)\s+my\s+visa\s+(?:status|type)\b", message, _re.IGNORECASE
        ))

        if is_info_request:
            msg = (
                "**UAE Work Visa Information:**\n\n"
                "To work in the UAE you typically need one of:\n"
                "• **Employment Visa** — sponsored by your employer (most common)\n"
                "• **Freelance Permit** — from TECOM, twofour54, or emirate-level free zones\n"
                "• **Golden Visa** — 5 or 10-year self-sponsored for skilled professionals\n"
                "• **Spouse/Dependent Visa** — allows work with a separate employment NOC\n\n"
                "Most UAE employers sponsor the employment visa after a job offer is accepted. "
                "Tell me your current visa status so I can tailor your job search — "
                "e.g. 'I'm on a spouse visa' or 'I need visa sponsorship'."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "visa_info", "message": msg}

        if is_query:
            current = self._profile_value(profile, "visa_status") or ""
            if current:
                msg = (
                    f"حالة تأشيرتك المسجلة: **{current}**."
                    if arabic else
                    f"Your visa status on file: **{current}**."
                )
            else:
                msg = (
                    "لم تُحدّد حالة تأشيرتك بعد. أخبرني بها، مثلاً: 'لديّ تأشيرة زوج/زوجة'."
                    if arabic else
                    "You haven't set your visa status yet. Tell me — e.g. 'I'm on a spouse visa' or 'I need sponsorship'."
                )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "visa_readback", "visa_status": current, "message": msg}

        # Parse declared visa type from message
        _VISA_MAP = [
            (r"golden\s+visa",               "Golden Visa"),
            (r"investor\s+visa",             "Investor Visa"),
            (r"freelance\s+(?:visa|permit)", "Freelance Permit"),
            (r"employment\s+visa|work\s+permit|work\s+visa", "Employment Visa"),
            (r"spouse\s+visa|dependent\s+visa", "Spouse/Dependent Visa"),
            (r"visit\s+visa|tourist\s+visa", "Visit Visa"),
            (r"residence\s+visa",            "Residence Visa"),
            (r"need\s+(?:visa\s+)?sponsorship|require\s+sponsorship", "Requires Sponsorship"),
        ]
        visa_value = ""
        for pattern, label in _VISA_MAP:
            if _re.search(pattern, message, _re.IGNORECASE):
                visa_value = label
                break

        if visa_value:
            upsert_profile(user_id=user_id, updates={"visa_status": visa_value})
            extra = ""
            if visa_value == "Spouse/Dependent Visa":
                extra = " Note: most UAE employers can issue a work permit alongside your dependent visa — I'll filter for roles that offer sponsorship."
            elif visa_value == "Visit Visa":
                extra = " Visit visas don't permit employment — you'll need an employer to sponsor an employment visa before starting work."
            elif visa_value == "Employment Visa":
                extra = " Great — you're already work-authorised, which expands your options significantly."
            msg = (
                f"تم تسجيل حالة التأشيرة: **{visa_value}**.{extra}"
                if arabic else
                f"Visa status saved as **{visa_value}**.{extra}"
            )
        else:
            msg = (
                "أخبرني بحالة تأشيرتك، مثلاً: 'تأشيرة زوج/زوجة'، 'تأشيرة عمل'، أو 'أحتاج كفالة'."
                if arabic else
                "What's your visa status? E.g. 'I'm on a spouse visa', 'employment visa', "
                "or 'I need sponsorship'."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "visa_status_update", "visa_status": visa_value or None, "message": msg}

    def _handle_salary_negotiation(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return UAE-context salary negotiation advice.

        Detects: "how do I negotiate my salary?", "should I counter the offer?",
        "the offer is too low", "tips for salary negotiation in UAE".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Is this about countering a specific offer?
        is_counter = bool(_re.search(
            r"\bcounter(?:[- ]offer)?|should\s+I\s+(?:accept|reject|counter)\s+(?:the\s+)?offer\b"
            r"|\bthe\s+offer\s+(?:is|seems?)\s+(?:too\s+low|low|below|not\s+enough)\b",
            message, _re.IGNORECASE,
        ))

        salary_on_file = self._profile_value(profile, "salary_expectation_aed")
        salary_str = f"AED {salary_on_file:,}" if isinstance(salary_on_file, (int, float)) and salary_on_file else str(salary_on_file) if salary_on_file else ""

        if is_counter and salary_str:
            counter_advice = (
                f"Based on your target salary of **{salary_str}/month**, here's my advice:\n\n"
                "**Countering a UAE job offer:**\n\n"
                "1. **Benchmark first** — confirm the offer is genuinely below market using HRMS UAE, "
                "Bayt Salary Insights, or GulfTalent before countering.\n"
                "2. **Counter in writing** — email is standard in UAE; keeps a record for both sides.\n"
                "3. **Anchor high but realistic** — counter 10–15% above the offer, not more. "
                "UAE employers expect some negotiation, especially at mid-senior levels.\n"
                "4. **Package over base** — if they won't move on salary, negotiate housing allowance, "
                "transport, medical, or annual ticket (common UAE components).\n"
                "5. **One counter is the norm** — UAE hiring culture is less multi-round than Western markets. "
                "Make your counter count the first time.\n\n"
                "Say **'what's my target salary?'** to review your saved expectation."
            )
        else:
            counter_advice = (
                "**UAE Salary Negotiation Tips:**\n\n"
                "1. **Know the market** — research on Bayt, GulfTalent, and HRMS UAE before any conversation. "
                "UAE salaries vary significantly by nationality, company type, and emirate.\n"
                "2. **Don't reveal your current salary first** — UAE interviews often ask; it's legally "
                "permissible to say 'I'd prefer to discuss based on the role's budget'.\n"
                "3. **Total package thinking** — UAE offers include housing, transport, medical, and annual "
                "tickets. A lower base with strong allowances can exceed a high-base offer.\n"
                "4. **Timing** — raise salary only after a verbal offer. Bringing it up earlier signals "
                "you're money-first, which can put off UAE hiring managers.\n"
                "5. **Be direct but respectful** — UAE business culture values politeness. "
                "Frame it as 'Based on my research and experience, I was expecting closer to X' "
                "rather than 'your offer is too low'.\n"
                + (f"\n💡 Your saved salary expectation is **{salary_str}/month**." if salary_str else
                   "\n💡 Set your salary expectation by saying 'my salary expectation is X AED'.")
            )

        if arabic:
            counter_advice = (
                "**نصائح التفاوض على الراتب في الإمارات:**\n\n"
                "• ابحث عن رواتب السوق في Bayt وGulfTalent قبل أي نقاش.\n"
                "• لا تذكر راتبك الحالي أولاً — يمكنك القول 'أفضل النقاش بناءً على ميزانية الوظيفة'.\n"
                "• فكر بمجموع الحزمة: الأساسي + السكن + المواصلات + التأمين + التذكرة السنوية.\n"
                "• اطرح مقابلك كتابياً عبر البريد الإلكتروني، وبطريقة مهنية ومحترمة.\n"
                "• في الإمارات عادةً جولة تفاوض واحدة — اجعلها قوية."
            )

        self._append_chat(user_id, "assistant", counter_advice)
        return {
            "type": "negotiation_advice",
            "is_counter_scenario": is_counter,
            "salary_on_file": salary_str or None,
            "message": counter_advice,
        }

    def _handle_interview_prep(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return UAE-context interview preparation advice, personalised by role.

        Detects: "how do I prepare for an interview?", "common interview questions",
        "interview tips for HSE", "what to wear to a UAE interview?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[0] if target_roles else ""

        # Try to extract a role from the message itself
        _role_m = _re.search(
            r"interview\s+(?:tips?|questions?|prep(?:aration)?|advice|help)\s+for\s+([A-Za-z][A-Za-z\s]{2,30}?)(?:\s+(?:role|job|position|in\b)|\??$)",
            message, _re.IGNORECASE,
        )
        if _role_m:
            role = _role_m.group(1).strip()

        role_line = f" for **{role}** roles" if role else ""

        is_attire = bool(_re.search(r"\bwear|attire|dress\s+code|what\s+to\s+bring\b", message, _re.IGNORECASE))
        is_questions = bool(_re.search(r"\bquestions?\b", message, _re.IGNORECASE))

        if is_attire:
            advice = (
                "**UAE Interview Dress Code:**\n\n"
                "• **Business formal** is the default for first interviews in UAE corporates and government.\n"
                "• Men: suit and tie (dark colours preferred) or smart blazer + trousers.\n"
                "• Women: modest professional attire — covered shoulders, knee-length or longer. "
                "This is especially important in government, banking, and oil & gas sectors.\n"
                "• Tech startups and creative agencies accept smart-casual, but it's always safer to overdress.\n"
                "• Bring: printed CV copies (2-3), certifications folder, notebook, pen.\n"
                "• Arrive 10–15 minutes early — UAE traffic is unpredictable and punctuality signals respect."
            )
        elif is_questions:
            questions_block = (
                f"\n\n**Common{role_line} Interview Questions in UAE:**\n\n"
                "1. Tell me about yourself. *(Keep it professional, 2-3 minutes, UAE-relevant)*\n"
                "2. Why do you want to work in the UAE / with this company?\n"
                "3. What is your current / expected salary? *(Research market rates first)*\n"
                "4. What is your notice period?\n"
                "5. Describe a challenge you overcame at work.\n"
                "6. Where do you see yourself in 5 years?\n"
                "7. Why are you leaving your current job?\n"
                + (f"8. Walk me through a specific {role} project or achievement.\n" if role else "")
                + "\n💡 **Tip:** In the UAE, interviewers often ask about visa status and notice period upfront — have both answers ready."
            )
            advice = (
                f"**Interview Preparation Guide{role_line}:**\n\n"
                "• Research the company's projects, clients, and recent news — especially in UAE context.\n"
                "• Prepare 2-3 STAR-format examples (Situation, Task, Action, Result).\n"
                "• Know your numbers: salary expectation, years of experience, and notice period."
                + questions_block
            )
        else:
            advice = (
                f"**Interview Preparation Tips{role_line} — UAE Context:**\n\n"
                "**Before the interview:**\n"
                "• Research the company's UAE projects and presence — LinkedIn, their website, news.\n"
                "• Prepare 2-3 strong STAR stories (Situation → Task → Action → Result).\n"
                "• Know your salary expectation and be ready to state it confidently.\n"
                "• Confirm the interview format: in-person, Teams/Zoom, or panel.\n\n"
                "**During the interview:**\n"
                "• Greet formally — handshakes are standard in professional UAE settings.\n"
                "• Let the interviewer set the pace; don't rush.\n"
                "• Be ready for 'Why UAE?' — interviewers want to know you're committed to staying.\n"
                "• Avoid bad-mouthing previous employers — UAE is a small professional community.\n\n"
                "**After the interview:**\n"
                "• Send a thank-you email within 24 hours — not expected everywhere, but always noticed.\n"
                "• Follow up after 5–7 business days if you haven't heard.\n\n"
                + (f"Say **'common {role} interview questions'** for role-specific questions." if role
                   else "Say **'common interview questions'** for the most asked questions.")
            )

        if arabic:
            advice = (
                f"**نصائح المقابلة الوظيفية{' لـ ' + role if role else ''} في الإمارات:**\n\n"
                "• ابحث عن الشركة ومشاريعها في الإمارات قبل المقابلة.\n"
                "• جهّز 2-3 أمثلة بأسلوب STAR (الموقف، المهمة، الإجراء، النتيجة).\n"
                "• اعرف توقعاتك الراتبية وفترة إشعارك.\n"
                "• الزي الرسمي هو المعيار في معظم بيئات العمل الإماراتية.\n"
                "• أرسل رسالة شكر بعد 24 ساعة من المقابلة."
            )

        self._append_chat(user_id, "assistant", advice)
        return {
            "type": "interview_prep",
            "role": role or None,
            "is_attire_query": is_attire,
            "is_questions_query": is_questions,
            "message": advice,
        }

    def _handle_rejection(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return UAE-context advice on handling job rejection or no response.

        Detects: "I got rejected", "haven't heard back", "no response after interview",
        "what to do after rejection?", "ghosted by employer".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        is_no_response = bool(_re.search(
            r"\b(?:no\s+(?:response|reply)|haven(?:'t|\s+not)\s+heard\s+back|ghosted)\b",
            message, _re.IGNORECASE,
        ))
        is_post_interview = bool(_re.search(
            r"\bafter\s+(?:the\s+)?interview\b|\bfail(?:ed|ing)\s+(?:the\s+)?interview\b",
            message, _re.IGNORECASE,
        ))

        if is_no_response:
            advice = (
                "**No Response? Here's What to Do:**\n\n"
                "**When to follow up:**\n"
                "• After applying: wait 5–7 business days, then follow up once.\n"
                "• After an interview: wait 3–5 business days, then send a polite follow-up.\n"
                "• UAE companies, especially government-linked ones, can take 2–4 weeks to respond.\n\n"
                "**How to follow up:**\n"
                "Send a short, professional email:\n"
                "_'Dear [Name], I wanted to follow up on my application / interview for [Role] on [Date]. "
                "I remain very interested in the position and would welcome any update. "
                "Thank you for your time.'_\n\n"
                "**If still no response after 2 follow-ups:**\n"
                "• Mark the role as 'inactive' in your tracker and move on.\n"
                "• In the UAE, silence often means the role is filled or on hold — it's rarely personal.\n"
                "• Keep your pipeline active — one company's silence shouldn't pause your search.\n\n"
                "Say **'find more jobs'** to continue your search."
            )
        elif is_post_interview:
            advice = (
                "**Rejected After an Interview — Next Steps:**\n\n"
                "1. **Request feedback** — email the interviewer: 'Could you share any feedback that might help me improve?' "
                "Not all UAE companies respond, but many will if asked politely.\n"
                "2. **Debrief yourself** — write down what went well and what you'd change. "
                "Common UAE interview pitfalls: vague salary answers, unclear notice period, weak 'Why UAE?' response.\n"
                "3. **Don't burn the bridge** — reply to the rejection graciously. UAE is a small market; "
                "the same hiring manager may have a different role in 6 months.\n"
                "4. **Look for patterns** — if you're failing multiple interviews at the same stage, "
                "consider a mock interview or revisiting your STAR stories.\n"
                "5. **Keep going** — the UAE job market is active; setbacks are part of the process.\n\n"
                "Say **'find more jobs'** or **'interview tips'** to keep moving."
            )
        else:
            advice = (
                "**Handling Job Rejection in the UAE:**\n\n"
                "**Immediate response:**\n"
                "• Reply professionally to the rejection email — thank them and express interest in future roles. "
                "UAE is a tight-knit professional market.\n"
                "• Ask for feedback within 24-48 hours of rejection.\n\n"
                "**Reflection:**\n"
                "• Was it a CV issue, interview performance, or just a stronger candidate?\n"
                "• If CV: make sure your skills and certifications match the role's requirements.\n"
                "• If interview: practice STAR answers and research UAE-specific expectations.\n\n"
                "**Action:**\n"
                "• Don't pause your search — apply to 3 more roles this week.\n"
                "• Rejection is feedback about fit, not about your worth.\n\n"
                "Say **'find more jobs'** to continue your search or **'interview tips'** for prep advice."
            )

        if arabic:
            advice = (
                "**كيف تتعامل مع رفض طلب التوظيف في الإمارات:**\n\n"
                "• رد بشكل مهني على بريد الرفض — الإمارات سوق صغير والعلاقات مهمة.\n"
                "• اطلب ملاحظات تطويرية خلال 24-48 ساعة.\n"
                "• لا توقف بحثك — تقدم لوظائف أخرى هذا الأسبوع.\n"
                "• إذا لم يكن هناك رد: انتظر 5-7 أيام ثم أرسل متابعة مهنية واحدة.\n"
                "• الرفض لا يعني نقصاً فيك — إنه مجرد عدم توافق في هذه اللحظة."
            )

        self._append_chat(user_id, "assistant", advice)
        return {
            "type": "rejection_advice",
            "is_no_response": is_no_response,
            "is_post_interview": is_post_interview,
            "message": advice,
        }

    def _handle_linkedin_networking(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return UAE-context LinkedIn and professional networking advice.

        Detects: "how to use LinkedIn?", "should I connect with the recruiter?",
        "networking tips in UAE", "how to message a hiring manager?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        is_message_recruiter = bool(_re.search(
            r"\b(?:message|contact|reach\s+out\s+to|approach)\s+(?:a\s+)?(?:recruiter|hiring\s+manager|HR|employer)\b"
            r"|\bshould\s+I\s+(?:connect|message|follow\s+up)\s+with\b",
            message, _re.IGNORECASE,
        ))
        is_cold_outreach = bool(_re.search(
            r"\bcold\s+(?:message|email|outreach)\b", message, _re.IGNORECASE
        ))
        is_profile_optimize = bool(_re.search(
            r"\b(?:optimize|improve|update|fix)\s+(?:my\s+)?(?:LinkedIn\s+)?profile\b",
            message, _re.IGNORECASE,
        ))

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[0] if target_roles else ""

        if is_message_recruiter or is_cold_outreach:
            advice = (
                "**How to Message a Recruiter or Hiring Manager in the UAE:**\n\n"
                "**What works in UAE LinkedIn outreach:**\n"
                "• Keep it short — 3-4 sentences max.\n"
                "• Mention the specific role or company.\n"
                "• Lead with what you bring, not what you want.\n\n"
                "**Template:**\n"
                "_'Hi [Name], I came across [Company]'s opening for [Role] and wanted to reach out directly. "
                "I have [X years] of experience in [relevant skill], including [brief achievement]. "
                "I'd welcome the chance to connect — would you be open to a brief call?'_\n\n"
                "**UAE-specific tips:**\n"
                "• Dubai and Abu Dhabi recruiters are highly active on LinkedIn — direct messages work.\n"
                "• Always personalise — copy-paste messages are immediately spotted and ignored.\n"
                "• If they don't respond in 7 days, one polite follow-up is acceptable.\n"
                "• Arabic greetings (السلام عليكم / مرحباً) can build rapport with UAE national recruiters."
            )
        elif is_profile_optimize:
            advice = (
                "**LinkedIn Profile Optimisation for UAE Job Search:**\n\n"
                "1. **Headline** — include your role, seniority, and UAE focus: "
                f"e.g. _'{'Senior ' + role if role else 'HSE Manager'} | UAE | NEBOSH IGC | ISO 45001'_\n"
                "2. **About section** — 3-5 sentences: who you are, what you do, and your UAE value.\n"
                "3. **Open to Work** — turn it on; UAE recruiters filter by this daily.\n"
                "4. **Location** — set to UAE or your target emirate (Dubai / Abu Dhabi).\n"
                "5. **Certifications** — list every UAE-relevant certification prominently.\n"
                "6. **Connections** — connect with UAE industry groups and recruiters in your sector.\n"
                "7. **Activity** — comment on industry posts; UAE recruiters do look at profile activity.\n\n"
                "Say **'what certifications do I need?'** to get sector-specific cert recommendations."
            )
        else:
            advice = (
                "**LinkedIn & Networking Tips for UAE Job Search:**\n\n"
                "**LinkedIn quick wins:**\n"
                "• Enable 'Open to Work' (visible to recruiters only, not your employer if needed).\n"
                "• Set your location to UAE or a specific emirate.\n"
                "• Connect with UAE-based recruiters in your industry — they're very active.\n"
                "• Post or engage with industry content weekly — visibility matters in the UAE market.\n\n"
                "**In-person networking:**\n"
                "• Attend UAE industry events: ADIPEC (oil & gas), GITEX (tech), Big 5 (construction).\n"
                "• Join professional bodies: IOSH UAE Chapter, PMI UAE, CIPS MENA.\n"
                "• Many UAE roles are filled through referrals — your network is your pipeline.\n\n"
                "**Cold outreach:**\n"
                "• Personalised LinkedIn messages to recruiters and hiring managers work well in the UAE.\n"
                "• Keep messages short, specific, and value-focused.\n\n"
                + (f"Say **'how to message a recruiter'** for a ready-to-use {role} outreach template." if role
                   else "Say **'how to message a recruiter'** for a ready-to-use outreach template.")
            )

        if arabic:
            advice = (
                "**نصائح LinkedIn والتواصل المهني في الإمارات:**\n\n"
                "• فعّل خاصية 'Open to Work' — المجنّدون في الإمارات يبحثون عنها يومياً.\n"
                "• اكتب عنواناً واضحاً: المسمى + الخبرة + الشهادات.\n"
                "• تواصل مع مجنّدين إماراتيين في مجالك بشكل مباشر.\n"
                "• رسائل LinkedIn القصيرة والمخصصة تعمل بشكل جيد في الإمارات.\n"
                "• احضر فعاليات مثل ADIPEC وGITEX وBig 5 للتواصل المباشر.\n"
                "• كثير من الوظائف في الإمارات تُملأ بالتوصيات — شبكتك هي خط أنابيبك."
            )

        self._append_chat(user_id, "assistant", advice)
        return {
            "type": "linkedin_networking",
            "is_message_recruiter": is_message_recruiter,
            "is_cold_outreach": is_cold_outreach,
            "is_profile_optimize": is_profile_optimize,
            "message": advice,
        }

    def _handle_cv_format_advice(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return UAE-context CV formatting advice, ATS tips, and length guidance.

        Detects: "how should I format my CV for UAE?", "is my CV too long?",
        "ATS-friendly CV tips", "what should a UAE CV include?".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        is_ats = bool(_re.search(r"\bATS\b|applicant\s+tracking", message, _re.IGNORECASE))
        is_length = bool(_re.search(r"\btoo\s+(?:long|short)\b|\blength\b", message, _re.IGNORECASE))

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[0] if target_roles else ""
        years = self._profile_value(profile, "years_experience") or 0

        if is_ats:
            advice = (
                "**ATS-Friendly CV Tips for UAE Job Search:**\n\n"
                "1. **Standard headings** — use exact headings: 'Work Experience', 'Education', "
                "'Certifications', 'Skills'. ATS systems in the UAE often fail on creative labels.\n"
                "2. **Plain formatting** — avoid tables, columns, text boxes, and graphics. "
                "Single-column PDF or Word (.docx) is safest.\n"
                "3. **Match keywords** — copy key phrases from the job description verbatim "
                "(e.g. 'ISO 45001', 'NEBOSH IGC'). ATS scores keyword density.\n"
                "4. **File format** — .docx for ATS portals; PDF for email applications. "
                "Many UAE portals (Bayt, Naukrigulf) recommend .docx.\n"
                "5. **No headers/footers** — some ATS systems cannot parse text in page headers.\n"
                "6. **Spell out acronyms once** — write 'Health, Safety & Environment (HSE)' "
                "on first use to cover both keyword variants.\n\n"
                "Say **'review my CV'** if you'd like me to check your uploaded CV against a role."
            )
        elif is_length:
            if years and float(years) <= 3:
                length_advice = "1 page is ideal for early-career candidates in the UAE."
            elif years and float(years) >= 15:
                length_advice = "2-3 pages is acceptable for senior UAE professionals with extensive project history."
            else:
                length_advice = "2 pages is the UAE standard for mid-career professionals."
            advice = (
                f"**CV Length Guidance:**\n\n"
                f"{length_advice}\n\n"
                "**What to cut if too long:**\n"
                "• Roles older than 15 years (keep only job title, company, dates)\n"
                "• Generic responsibilities that don't show impact\n"
                "• Outdated skills and expired certifications\n"
                "• Personal details beyond name, email, phone, LinkedIn, and UAE location\n\n"
                "**What to expand if too short:**\n"
                "• Add quantified achievements: 'Reduced incident rate by 40% over 2 years'\n"
                "• Expand certifications section with issue dates\n"
                "• Include a 3-line professional summary at the top"
            )
        else:
            photo_note = (
                "• **Photo** — a professional headshot is standard and expected in the UAE "
                "(unlike UK/US where it's avoided)."
            )
            advice = (
                f"**UAE CV Format Guide{' for ' + role if role else ''}:**\n\n"
                "**Structure (top to bottom):**\n"
                "1. Name + contact (UAE phone, email, LinkedIn, location in UAE)\n"
                "2. Professional summary (3-4 lines: who you are, experience level, key value)\n"
                "3. Work experience (reverse chronological, 3-5 bullet points per role with impact)\n"
                "4. Education\n"
                "5. Certifications (critical in UAE — list with issue dates)\n"
                "6. Skills (technical + soft, tailored to the role)\n\n"
                "**UAE-specific requirements:**\n"
                f"{photo_note}\n"
                "• **Nationality** — commonly included on UAE CVs (not required but expected).\n"
                "• **Visa status** — state 'Employment Visa', 'Spouse Visa', or 'Available for Sponsorship'.\n"
                "• **Notice period** — include at the bottom: e.g. 'Notice period: 30 days'.\n"
                "• **Length** — 2 pages for most; 1 page for entry-level; up to 3 for senior roles.\n\n"
                "**Font & layout:** Arial or Calibri 10-11pt, clean single-column, no graphics.\n\n"
                "Say **'ATS CV tips'** for applicant tracking system optimisation."
            )

        if arabic:
            advice = (
                "**نصائح تنسيق السيرة الذاتية في الإمارات:**\n\n"
                "• الهيكل: معلومات التواصل، ملخص مهني، خبرات العمل (عكسي)، التعليم، الشهادات، المهارات.\n"
                "• الصورة الشخصية مطلوبة في معظم الوظائف الإماراتية.\n"
                "• أضف الجنسية وحالة الإقامة وفترة الإشعار.\n"
                "• الطول المثالي: صفحتان لمعظم المهنيين.\n"
                "• تنسيق نظيف بدون جداول معقدة أو رسومات للتوافق مع أنظمة ATS."
            )

        self._append_chat(user_id, "assistant", advice)
        return {
            "type": "cv_format_advice",
            "is_ats_query": is_ats,
            "is_length_query": is_length,
            "role": role or None,
            "message": advice,
        }

    def _handle_cover_letter_tips(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return UAE-context cover letter guidance.

        Detects: "how do I write a cover letter?", "do I need a cover letter?",
        "cover letter format for UAE", "cover letter tips".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        is_needed_question = bool(_re.search(
            r"\bdo\s+I\s+need\s+a\s+cover\s+letter\b", message, _re.IGNORECASE
        ))

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[0] if target_roles else ""
        name = self._profile_value(profile, "name") or ""

        if is_needed_question:
            advice = (
                "**Do You Need a Cover Letter in the UAE?**\n\n"
                "**Short answer: usually yes**, but it depends:\n\n"
                "• **Always include one** when applying by email or to senior roles (Manager+). "
                "It sets you apart from the 80% who don't bother.\n"
                "• **Optional** on Bayt, LinkedIn Easy Apply, or Naukrigulf portals where no field exists.\n"
                "• **Required** for government roles, multinational corporates, and most oil & gas companies.\n\n"
                "In UAE hiring culture, a well-written cover letter signals professionalism and seriousness. "
                "A generic one is worse than none — always personalise.\n\n"
                "Say **'write a cover letter'** and I'll draft one using your CV profile."
            )
        else:
            role_line = f" for **{role}**" if role else ""
            name_line = f"Dear Hiring Manager" if not name else f"Dear [Hiring Manager's Name]"
            advice = (
                f"**UAE Cover Letter Guide{role_line}:**\n\n"
                "**Structure (keep it to one page, 3-4 short paragraphs):**\n\n"
                f"_{name_line},_\n\n"
                "_Opening:_ State the role, where you found it, and one sentence on why you're a strong fit.\n\n"
                "_Body 1:_ Your most relevant experience + one quantified achievement (e.g. 'Reduced LTI rate by 35% at [Company]').\n\n"
                "_Body 2:_ Why this company specifically — reference their UAE projects, values, or recent news.\n\n"
                "_Closing:_ Express enthusiasm, mention your notice period, and invite them to contact you.\n\n"
                "**UAE-specific tips:**\n"
                "• Keep it formal but not stiff — use 'I am' not 'I'm'.\n"
                "• Mention your visa status if you're already work-authorised — reduces recruiter uncertainty.\n"
                "• Name the hiring manager if you can find them on LinkedIn — 'Dear Mr Al-Rashidi' beats 'Dear Sir/Madam'.\n"
                "• Max 350 words — UAE hiring managers read dozens per day.\n\n"
                + (f"Say **'write a cover letter for {role}'** and I'll draft one from your CV profile." if role
                   else "Say **'write me a cover letter'** and I'll draft one from your CV profile.")
            )

        if arabic:
            advice = (
                "**نصائح كتابة خطاب التقديم في الإمارات:**\n\n"
                "• الهيكل: فقرة افتتاحية، فقرة خبرات مع إنجاز قابل للقياس، سبب اهتمامك بالشركة، خاتمة.\n"
                "• اذكر حالة إقامتك إذا كنت مرخصاً للعمل — يقلل تردد المجنّد.\n"
                "• سمّ المسؤول إن أمكن بدلاً من 'عزيزي مدير التوظيف'.\n"
                "• لا تتجاوز صفحة واحدة و350 كلمة.\n"
                "• قل 'اكتب لي خطاب تقديم' وسأكتب لك واحداً من ملفك الشخصي."
            )

        self._append_chat(user_id, "assistant", advice)
        return {
            "type": "cover_letter_tips",
            "is_needed_question": is_needed_question,
            "role": role or None,
            "message": advice,
        }

    def _handle_app_pipeline_summary(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Return an application pipeline summary from the user's DB records.

        Detects: "how many applications have I sent?", "my application stats",
        "what's my application success rate?", "how am I doing?".
        """
        arabic = self._is_arabic_text(message)

        # Fetch application records
        try:
            from src.repositories import applications_repo as _apps_repo
            apps = _apps_repo.get_all(user_id) or []
        except Exception:
            apps = []

        total = len(apps)

        # Status breakdown
        status_counts: dict[str, int] = {}
        for app in apps:
            status = (
                getattr(app, "status", None)
                or (app.get("status") if isinstance(app, dict) else None)
                or "applied"
            )
            status_counts[status] = status_counts.get(status, 0) + 1

        applied    = status_counts.get("applied", 0)
        saved      = status_counts.get("saved", 0)
        interview  = status_counts.get("interview", 0) + status_counts.get("interviewing", 0)
        offered    = status_counts.get("offered", 0) + status_counts.get("offer", 0)
        rejected   = status_counts.get("rejected", 0) + status_counts.get("declined", 0)
        skipped    = status_counts.get("skipped", 0)

        # Response rate (interviews + offers out of applied)
        response_rate = f"{round(interview / applied * 100)}%" if applied > 0 else "N/A"

        if total == 0:
            msg = (
                "لم تسجّل أي طلبات توظيف بعد. ابدأ بالبحث عن وظائف وسأتابع تقدمك."
                if arabic else
                "You haven't logged any applications yet. Start searching and I'll track your progress."
            )
        else:
            lines = [
                f"**Your Application Pipeline ({total} total):**\n",
                f"• Applied: **{applied}**",
            ]
            if saved:      lines.append(f"• Saved / to apply: **{saved}**")
            if interview:  lines.append(f"• Interview stage: **{interview}**")
            if offered:    lines.append(f"• Offer received: **{offered}**")
            if rejected:   lines.append(f"• Rejected / declined: **{rejected}**")
            if skipped:    lines.append(f"• Skipped: **{skipped}**")
            lines.append(f"\n📊 **Interview response rate:** {response_rate}")

            if interview == 0 and applied >= 5:
                lines.append("\n💡 Low response rate — consider reviewing your CV keywords or broadening your search.")
            elif offered > 0:
                lines.append(f"\n🎉 You have {'an offer' if offered == 1 else f'{offered} offers'} — congratulations!")

            msg = "\n".join(lines)

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "app_pipeline_summary",
            "total": total,
            "applied": applied,
            "interview": interview,
            "offered": offered,
            "rejected": rejected,
            "response_rate": response_rate,
            "message": msg,
        }

    def _handle_company_type_search(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Search for jobs filtered by company type / ownership sector.

        Detects: "find government jobs", "find startup jobs in UAE",
        "find multinational company jobs", "public sector roles in Dubai".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Detect company type
        _TYPE_MAP = [
            (r"government|public\s+sector|federal|ministry|municipality|وظائف\s+حكومية", "government", "Government"),
            (r"semi[- ]?government|quasi[- ]?government", "semi-government", "Semi-Government"),
            (r"startup|start[- ]?up|scale[- ]?up", "startup", "Startup"),
            (r"multinational|MNC|Fortune\s+500|international\s+company|global\s+company", "multinational", "Multinational"),
            (r"SME|small\s+(?:and|&)\s+medium|family\s+business", "SME", "SME / Family Business"),
        ]

        company_type_label = ""
        search_qualifier = ""
        for pattern, qualifier, label in _TYPE_MAP:
            if _re.search(pattern, message, _re.IGNORECASE):
                company_type_label = label
                search_qualifier = qualifier
                break

        if not company_type_label:
            company_type_label = "Government"
            search_qualifier = "government"

        # Extract role from profile or message
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[0] if target_roles else ""

        _role_m = _re.search(
            r"(?:government|startup|multinational|public\s+sector|semi[- ]?government|MNC)\s+"
            r"(.{2,30}?)\s+(?:jobs?|roles?|positions?|vacancies)\b",
            message, _re.IGNORECASE,
        )
        if _role_m:
            role = _role_m.group(1).strip()

        _loc_m = _re.search(r"\bin\s+(Dubai|Abu\s+Dhabi|Sharjah|Ajman|UAE)\b", message, _re.IGNORECASE)
        location = _loc_m.group(1).strip() if _loc_m else "UAE"

        search_query = f"{search_qualifier} {role}".strip() if role else f"{search_qualifier} jobs"
        fetch = self._search_jsearch_meta(search_query, location if location != "UAE" else "")
        matches = fetch.items or []
        self._store_search_matches_context(user_id, matches[:10])
        top = matches[:5]

        if not top:
            msg = (
                f"لم أجد وظائف في **{company_type_label}** لـ {role or 'هذا المجال'} حالياً في الإمارات."
                if arabic else
                f"No **{company_type_label}** {role} jobs found in the UAE right now. "
                f"Try broadening the role or check back later."
            )
            self._append_chat(user_id, "assistant", msg)
            return {"type": "no_results", "company_type": company_type_label, "message": msg}

        loc_label = f" in {location}" if location and location != "UAE" else " in the UAE"
        header = (
            f"Found **{len(top)} {company_type_label}** {role} role{'s' if len(top) != 1 else ''}{loc_label}:"
        )
        lines = [header, ""]
        for i, job in enumerate(top, 1):
            title   = job.get("title") or job.get("job_title") or "Role"
            company = job.get("company") or job.get("employer_name") or ""
            loc     = job.get("location") or job.get("job_city") or location
            url     = job.get("apply_url") or job.get("job_apply_link") or ""
            line = f"{i}. **{title}**" + (f" at {company}" if company else "") + f" — {loc}"
            if url:
                line += f" ([Apply]({url}))"
            lines.append(line)

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_matches",
            "company_type": company_type_label,
            "role": role or None,
            "jobs": top,
            "total_found": len(matches),
            "message": msg,
        }

    def _handle_urgency_search(
        self, user_id: str, profile: Any, message: str
    ) -> dict[str, Any]:
        """Handle urgency-framed job search with motivational + action response.

        Detects: "I need a job urgently", "help me find a job fast",
        "I need to find a job in 30 days", "find urgent openings".
        """
        import re as _re

        arabic = self._is_arabic_text(message)

        # Extract a timeline if mentioned
        _timeline_m = _re.search(
            r"in\s+(\d+)\s+(days?|weeks?|months?)", message, _re.IGNORECASE
        )
        timeline = f"{_timeline_m.group(1)} {_timeline_m.group(2)}" if _timeline_m else ""

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[0] if target_roles else ""
        has_cv = bool(self._profile_value(profile, "cv_status"))

        # Run a live search immediately to show results + action plan
        search_query = f"{role} urgent immediate" if role else "immediate start jobs UAE"
        fetch = self._search_jsearch_meta(role or "jobs", "")
        matches = fetch.items or []
        self._store_search_matches_context(user_id, matches[:10])
        top = matches[:3]

        timeline_note = f" in the next **{timeline}**" if timeline else ""
        urgency_header = (
            f"أفهم الإلحاح — إليك خطة عمل فورية{'  للعثور على وظيفة' + (' في ' + timeline if timeline else '')}:"
            if arabic else
            f"Let's move fast{timeline_note}. Here's your immediate action plan:"
        )

        action_plan = [
            urgency_header, "",
            "**Right now (today):**",
        ]
        if not has_cv:
            action_plan.append("1. Upload your CV — say **'upload my CV'** to get started. Without it, applications are slower.")
        else:
            action_plan.append(f"1. {'Your CV is uploaded ✓' if has_cv else 'Upload your CV first.'}")

        action_plan += [
            f"2. {'Apply to the live openings below immediately.' if top else 'I ran a search — no exact matches right now, but try a broader role.'}",
            "3. Message 5-10 recruiters on LinkedIn today with a personalised note.",
            "4. Update your LinkedIn to 'Open to Work' if not already done.",
            "",
            "**This week:**",
            "• Apply to at least 10 roles per day — volume matters in urgent searches.",
            "• Follow up on any existing applications that are 5+ days old.",
            "• Register on Bayt, Naukrigulf, LinkedIn, and GulfTalent if not already.",
            "",
        ]

        if top:
            action_plan.append(f"**Live openings{' for ' + role if role else ''} right now:**")
            action_plan.append("")
            for i, job in enumerate(top, 1):
                title   = job.get("title") or job.get("job_title") or "Role"
                company = job.get("company") or job.get("employer_name") or ""
                url     = job.get("apply_url") or job.get("job_apply_link") or ""
                line = f"{i}. **{title}**" + (f" at {company}" if company else "")
                if url:
                    line += f" ([Apply now]({url}))"
                action_plan.append(line)

        if arabic:
            action_plan = [
                urgency_header, "",
                "**اليوم:**",
                "• ارفع سيرتك الذاتية إن لم تكن قد فعلت ذلك.",
                "• تقدم لـ 5-10 وظائف فوراً.",
                "• راسل 5 مجنّدين على LinkedIn برسالة مخصصة.",
                "• فعّل 'Open to Work' على LinkedIn.",
                "",
                "**هذا الأسبوع:**",
                "• تقدم لـ 10 وظائف يومياً على الأقل.",
                "• سجّل في Bayt وNaukrigulf وGulfTalent.",
            ]

        msg = "\n".join(action_plan)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "urgency_search",
            "timeline": timeline or None,
            "role": role or None,
            "live_jobs": top,
            "message": msg,
        }

    # ── Salary benchmark ─────────────────────────────────────────────────────────

    def _handle_salary_benchmark(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return UAE salary benchmark for the queried role."""
        arabic = self._is_arabic_text(message)
        msg_lower = message.lower()

        if "abu dhabi" in msg_lower:
            location = "Abu Dhabi"
        elif "sharjah" in msg_lower:
            location = "Sharjah"
        else:
            location = "Dubai / UAE"

        # Extract role from message
        role_hint = ""
        _role_m = re.search(
            r"\b(?:as\s+(?:a\s+|an\s+)|for\s+(?:a\s+|an\s+)|of\s+(?:a\s+|an\s+)|does\s+(?:a\s+|an\s+)|do\s+)([A-Z][a-zA-Z &/\-]{3,60})\b",
            message,
            re.IGNORECASE,
        )
        if _role_m:
            role_hint = _role_m.group(1).strip()
        if not role_hint:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role_hint = target_roles[0] if target_roles else ""

        years_exp = 0
        try:
            years_exp = int(self._profile_value(profile, "years_experience") or 0)
        except (ValueError, TypeError):
            pass

        if years_exp < 3:
            tier = "entry"
        elif years_exp < 8:
            tier = "mid"
        else:
            tier = "senior"

        role_lower = role_hint.lower()
        if any(x in role_lower for x in ["hse", "safety", "health & safety", "ehs", "environment"]):
            ranges = {"entry": "8,000–14,000", "mid": "14,000–22,000", "senior": "22,000–38,000"}
            sector = "HSE / EHS"
        elif any(x in role_lower for x in ["project manager", "project management"]):
            ranges = {"entry": "10,000–16,000", "mid": "16,000–28,000", "senior": "28,000–50,000"}
            sector = "Project Management"
        elif any(x in role_lower for x in ["engineer", "engineering"]):
            ranges = {"entry": "7,000–13,000", "mid": "13,000–22,000", "senior": "22,000–40,000"}
            sector = "Engineering"
        elif any(x in role_lower for x in ["finance", "financial", "accountant", "accounting", "cfo"]):
            ranges = {"entry": "6,000–12,000", "mid": "12,000–22,000", "senior": "22,000–45,000"}
            sector = "Finance / Accounting"
        elif any(x in role_lower for x in ["software", "developer", "tech", "data", "cloud", "devops", "it manager"]):
            ranges = {"entry": "8,000–15,000", "mid": "15,000–28,000", "senior": "28,000–55,000"}
            sector = "Technology / IT"
        elif any(x in role_lower for x in ["operation", "coo"]):
            ranges = {"entry": "8,000–14,000", "mid": "14,000–25,000", "senior": "25,000–45,000"}
            sector = "Operations Management"
        elif any(x in role_lower for x in ["hr ", "human resource", "talent", "recruitment", "recruiter"]):
            ranges = {"entry": "6,000–11,000", "mid": "11,000–20,000", "senior": "20,000–38,000"}
            sector = "Human Resources"
        elif any(x in role_lower for x in ["marketing", "digital marketing", "brand manager"]):
            ranges = {"entry": "6,000–11,000", "mid": "11,000–20,000", "senior": "20,000–38,000"}
            sector = "Marketing"
        elif any(x in role_lower for x in ["sales", "business development", "account manager"]):
            ranges = {"entry": "5,000–10,000", "mid": "10,000–20,000", "senior": "20,000–40,000"}
            sector = "Sales / Business Development"
        elif any(x in role_lower for x in ["legal", "lawyer", "counsel", "compliance"]):
            ranges = {"entry": "8,000–15,000", "mid": "15,000–28,000", "senior": "28,000–55,000"}
            sector = "Legal / Compliance"
        elif any(x in role_lower for x in ["supply chain", "logistics", "procurement", "warehouse"]):
            ranges = {"entry": "6,000–11,000", "mid": "11,000–20,000", "senior": "20,000–38,000"}
            sector = "Supply Chain / Logistics"
        elif any(x in role_lower for x in ["construction", "site manager", "civil", "architect"]):
            ranges = {"entry": "7,000–12,000", "mid": "12,000–22,000", "senior": "22,000–40,000"}
            sector = "Construction"
        else:
            ranges = {"entry": "7,000–14,000", "mid": "14,000–25,000", "senior": "25,000–45,000"}
            sector = "General Professional"

        my_range = ranges[tier]
        role_display = role_hint or "your target role"

        if arabic:
            lines = [
                f"**معدلات رواتب {role_display} في {location} (درهم إماراتي / شهر، معفاة من الضريبة):**",
                "",
                f"• مستوى مبتدئ (0–3 سنوات): {ranges['entry']} درهم",
                f"• مستوى متوسط (3–8 سنوات): {ranges['mid']} درهم",
                f"• مستوى متقدم (8+ سنوات): {ranges['senior']} درهم",
                "",
                f"بناءً على خبرتك ({years_exp} سنوات): **{my_range} درهم / شهر**.",
                "",
                "**عوامل تُحرّك الراتب للأعلى:**",
                "• الجهات الحكومية وشبه الحكومية تدفع أعلى بـ 15–25%",
                "• السكن والسيارة يضيفان ما يعادل 5,000–8,000 درهم",
                "• الخبرة المكتسبة في الإمارات تُضيف 10–15%",
            ]
        else:
            lines = [
                f"**{role_display} salary benchmark in {location} (AED/month, tax-free):**",
                "",
                f"• Entry level (0–3 yrs):  AED {ranges['entry']}",
                f"• Mid level   (3–8 yrs):  AED {ranges['mid']}",
                f"• Senior level (8+ yrs):  AED {ranges['senior']}",
                "",
                f"Based on your {years_exp} years of experience, target: **AED {my_range}/month**.",
                "",
                "**What moves salaries higher:**",
                "• Government / semi-gov roles pay 15–25% above market",
                "• Housing + car allowance = AED 5,000–8,000 extra monthly value",
                "• UAE-based experience commands a 10–15% premium",
                "• ADNOC, DP World, Emirates Group, and Big 4 firms sit at the top of ranges",
                "",
                f"Want me to find {role_display} jobs above your target salary?",
            ]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "salary_benchmark",
            "role": role_hint or None,
            "sector": sector,
            "location": location,
            "tier": tier,
            "range_aed": my_range,
            "message": msg,
        }

    # ── Career change / transition advice ────────────────────────────────────────

    def _handle_career_change(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return career transition advice tailored to UAE job market."""
        arabic = self._is_arabic_text(message)
        years_exp = 0
        try:
            years_exp = int(self._profile_value(profile, "years_experience") or 0)
        except (ValueError, TypeError):
            pass

        current_role = (self._profile_value(profile, "current_role") or "").strip()
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))

        _to_m = re.search(
            r"\b(?:to|into|towards?|as\s+(?:a|an))\s+([A-Z][a-zA-Z &/\-]{3,50})\b",
            message,
            re.IGNORECASE,
        )
        target_from_msg = _to_m.group(1).strip() if _to_m else ""
        target_role = target_from_msg or (target_roles[0] if target_roles else "")

        _from_m = re.search(
            r"\b(?:from|out\s+of)\s+([A-Z][a-zA-Z &/\-]{3,50})\b",
            message,
            re.IGNORECASE,
        )
        source_role = _from_m.group(1).strip() if _from_m else current_role

        if arabic:
            header = "**نصائح تغيير المسار المهني في الإمارات**"
            if source_role and target_role:
                intro = f"الانتقال من **{source_role}** إلى **{target_role}**:"
            elif target_role:
                intro = f"الدخول في مجال **{target_role}** في الإمارات:"
            else:
                intro = "التحول المهني في الإمارات:"

            if years_exp < 3:
                timeline_line = "• مع خبرتك الحالية، توقع 3–5 أشهر للتحول."
            elif years_exp < 8:
                timeline_line = "• على مستواك، يستغرق التحول المنظم 4–8 أشهر."
            else:
                timeline_line = "• على المستوى المتقدم، التحول الكامل يأخذ 6–12 شهراً."

            lines = [
                header, "", intro, "",
                "**الخطوات الموصى بها:**",
                "1. **تحليل الفجوة المهارية** — قارن مهاراتك الحالية بمتطلبات الدور المستهدف",
                "2. **احصل على شهادات** — المؤهلات المعترف بها دولياً تُسرّع التحول",
                "3. **ابنِ شبكة علاقات** — 70% من وظائف الإمارات تُملأ عبر التواصل",
                "4. **حدّث سيرتك** — ركّز على المهارات القابلة للنقل وليس المسمى الوظيفي",
                "5. **دور جسر** — ابحث عن أدوار تجمع تخصصك الحالي والهدف معاً",
                "",
                "**الجدول الزمني:**",
                timeline_line,
                "",
                "**نصائح خاصة بالإمارات:**",
                "• القطاع الحكومي يتطلب مطابقة دقيقة للمسمى — الانتقال إليه أصعب",
                "• الشركات الناشئة والاستشارات الأكثر انفتاحاً على المتحولين",
                "",
                f"هل تريد البحث عن وظائف في {target_role or 'مجالك الجديد'}؟",
            ]
        else:
            header = "**Career Transition Advice for UAE**"
            if source_role and target_role:
                intro = f"Moving from **{source_role}** → **{target_role}** in the UAE:"
            elif target_role:
                intro = f"Breaking into **{target_role}** in the UAE:"
            elif source_role:
                intro = f"Transitioning out of **{source_role}** in the UAE:"
            else:
                intro = "Career change in the UAE:"

            if years_exp < 3:
                timeline_line = "• At your experience level, expect 3–5 months for an active career change."
            elif years_exp < 8:
                timeline_line = "• At your seniority, a structured transition typically takes 4–8 months."
            else:
                timeline_line = "• At senior level, a full pivot takes 6–12 months — bridge roles help."

            lines = [
                header, "", intro, "",
                "**Recommended steps:**",
                "1. **Skills gap analysis** — compare current skills to the target role's requirements",
                "2. **Get certified** — UAE employers respond strongly to internationally recognised credentials",
                "3. **Network first** — 70% of UAE roles are filled through connections, not portals",
                "4. **Update your profile** — lead with transferable skills, not job titles",
                "5. **Bridge role** — find roles that blend your current field with the target",
                "",
                "**Realistic timeline:**",
                timeline_line,
                "",
                "**UAE-specific tips:**",
                "• Government / semi-gov roles require exact title matching — harder to pivot into",
                "• Startups and consultancies are most open to career changers",
                "• Emirates-based experience always helps — consider a bridge role first",
                "",
                f"Want me to search for {target_role or 'your new target role'} jobs that welcome career changers?",
            ]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "career_change_advice",
            "source_role": source_role or None,
            "target_role": target_role or None,
            "message": msg,
        }

    # ── Best employers / top companies ───────────────────────────────────────────

    def _handle_best_employers(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return top employers for the queried role/sector in UAE via live JSearch."""
        arabic = self._is_arabic_text(message)
        msg_lower = message.lower()

        if "abu dhabi" in msg_lower:
            location_hint = "Abu Dhabi"
        elif "sharjah" in msg_lower:
            location_hint = "Sharjah"
        else:
            location_hint = "Dubai"

        # Extract role from message
        role = ""
        _role_m = re.search(
            r"\b(?:hire|hiring|employ|recruit|for)\s+(.{3,50}?)\s*(?:in\s+(?:UAE|Dubai|Abu\s+Dhabi)|$|\?)",
            message,
            re.IGNORECASE,
        )
        if _role_m:
            role = _role_m.group(1).strip()
        if not role:
            target_roles = self._as_list(self._profile_value(profile, "target_roles"))
            role = target_roles[0] if target_roles else ""

        query = f"{role} jobs" if role else "professional jobs"
        results: dict = {}
        try:
            results = self._search_jsearch_meta(query, location=location_hint)
        except Exception:
            pass

        items = results.get("data", []) if isinstance(results, dict) else []
        from collections import Counter as _Counter
        employer_counts: _Counter = _Counter()
        for item in items[:30]:
            emp = (item.get("employer_name") or "").strip()
            if emp:
                employer_counts[emp] += 1
        top_employers = [emp for emp, _ in employer_counts.most_common(8)]

        if arabic:
            if top_employers:
                emp_list = "\n".join(f"• {e}" for e in top_employers)
                msg = (
                    f"**أبرز الشركات التي توظف {role or 'في مجالك'} في {location_hint} الآن:**\n\n"
                    f"{emp_list}\n\n"
                    "تابع صفحات هذه الشركات على LinkedIn وBayt لتكون أول من يتقدم."
                )
            else:
                msg = (
                    f"لم أجد بيانات كافية الآن. جرّب البحث على Bayt وNaukrigulf وGulfTalent "
                    "للحصول على قائمة شاملة بأبرز أصحاب العمل في الإمارات."
                )
        else:
            if top_employers:
                emp_list = "\n".join(f"• {e}" for e in top_employers)
                msg = (
                    f"**Top employers hiring {role or 'in your field'} in {location_hint} right now:**\n\n"
                    f"{emp_list}\n\n"
                    "Follow these companies on LinkedIn and Bayt to be first to apply when new roles open. "
                    "Want me to search for open positions at any of these employers?"
                )
            else:
                msg = (
                    f"I couldn't pull live employer data for {location_hint} right now. "
                    "Top UAE employers generally include ADNOC, DP World, Emirates Group, Emaar, "
                    "ALDAR, Mubadala, and major Big 4 consultancies. "
                    "Want me to search for specific roles?"
                )

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "best_employers",
            "role": role or None,
            "location": location_hint,
            "employers": top_employers,
            "message": msg,
        }

    # ── UAE job search tips / strategy ───────────────────────────────────────────

    def _handle_job_search_tips(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return UAE job search strategy and portal guide."""
        arabic = self._is_arabic_text(message)
        msg_lower = message.lower()

        has_cv = bool(self._profile_value(profile, "cv_status"))
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = target_roles[0] if target_roles else ""

        asks_about_recruiters = bool(re.search(r"\b(?:recruit(?:er|ment)|headhunter|agenc(?:y|ies))\b", message, re.IGNORECASE))
        asks_about_timeline = bool(re.search(r"\bhow\s+long|how\s+much\s+time|take\s+to\s+find\b", message, re.IGNORECASE))

        if arabic:
            lines = [
                "**دليل البحث عن وظيفة في الإمارات** 🇦🇪",
                "",
                "**أفضل منصات التوظيف:**",
                "• **Bayt.com** — الأكبر في الشرق الأوسط، ضروري",
                "• **Naukrigulf.com** — قوي جداً للوظائف التقنية والإدارية",
                "• **GulfTalent.com** — للمستويات المتوسطة والعليا",
                "• **LinkedIn** — لا غنى عنه للتواصل المهني",
                "• **Indeed.ae** — كميات كبيرة من الإعلانات",
                "",
                "**نصائح أساسية:**",
                "1. تقدم لـ 10-15 وظيفة يومياً في بداية بحثك",
                "2. فعّل 'Open to Work' على LinkedIn",
                "3. راسل مجنّدين مباشرة برسائل مخصصة",
                "4. سجّل في 3-5 منصات على الأقل",
                "5. تتبع طلباتك بجدول منظم",
            ]
            if asks_about_timeline:
                lines += ["", "**المدة المتوقعة:** 2-6 أشهر للمرشحين المؤهلين في الإمارات. الفترة الأولى تحتاج صبراً."]
            if asks_about_recruiters:
                lines += [
                    "", "**شركات التوظيف:** نعم، يستحق التسجيل في شركات مثل Michael Page وRobert Half وNSG Group. لكن لا تعتمد عليها فقط.",
                ]
            if not has_cv:
                lines += ["", "💡 ارفع سيرتك الذاتية أولاً حتى أتمكن من إيجاد أفضل الفرص لك!"]
        else:
            lines = [
                "**UAE Job Search Strategy Guide** 🇦🇪",
                "",
                "**Top job portals:**",
                "• **Bayt.com** — largest in the Middle East, essential",
                "• **Naukrigulf.com** — strong for tech and professional roles",
                "• **GulfTalent.com** — mid-to-senior level focus",
                "• **LinkedIn** — non-negotiable for networking and direct outreach",
                "• **Indeed.ae** — high volume, good for filtering by recent posts",
                "",
                "**Key tactics:**",
                "1. Apply to 10–15 roles per day in your active phase",
                "2. Enable 'Open to Work' on LinkedIn (visible to recruiters)",
                "3. Message recruiters directly with a personalised 2-line intro",
                "4. Register on 3–5 platforms minimum",
                "5. Track all applications — recall which roles responded",
            ]
            if asks_about_timeline:
                lines += [
                    "",
                    "**Realistic timeline:** 2–6 months for qualified candidates in UAE.",
                    "Senior roles (Director+) can take 4–9 months. Entry-level can be faster.",
                ]
            if asks_about_recruiters:
                lines += [
                    "",
                    "**Recruitment agencies:** Worth registering with 2–3 (Michael Page, Robert Half, NSG Group).",
                    "But don't rely on them alone — direct applications convert faster in UAE.",
                ]
            if role:
                lines += ["", f"Want me to search for open {role} roles right now?"]
            elif not has_cv:
                lines += ["", "💡 Upload your CV first so I can personalise job recommendations for you!"]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "job_search_tips",
            "message": msg,
        }

    # ── UAE benefits / package guide ─────────────────────────────────────────────

    def _handle_benefits_package(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return UAE employment benefits and package guide."""
        arabic = self._is_arabic_text(message)
        msg_lower = message.lower()

        years_exp = 0
        try:
            years_exp = int(self._profile_value(profile, "years_experience") or 0)
        except (ValueError, TypeError):
            pass

        asks_gratuity = bool(re.search(r"\b(?:gratuity|end.of.service)\b", message, re.IGNORECASE))
        asks_leave = bool(re.search(r"\b(?:annual\s+leave|vacation|leave\s+days?|paid\s+leave)\b", message, re.IGNORECASE))
        asks_housing = bool(re.search(r"\b(?:housing|accommodation)\s+allowance\b", message, re.IGNORECASE))

        if arabic:
            lines = [
                "**مكوّنات راتب الإمارات النموذجي** 🇦🇪",
                "",
                "**الراتب الإجمالي عادةً يشمل:**",
                "• الراتب الأساسي (40-60% من المجموع)",
                "• بدل السكن (20-30% من المجموع) — أو سكن مجاني من الشركة",
                "• بدل المواصلات (1,500–3,000 درهم شهرياً)",
                "• بدل الهاتف / الاتصالات (300–800 درهم)",
                "• التأمين الطبي (إلزامي قانوناً)",
                "• تأشيرة الإقامة (تتحملها الشركة)",
                "",
                "**الإجازات:**",
                "• 30 يوم إجازة سنوية (بعد سنة)",
                "• تذاكر عودة للوطن سنوياً (شركات كثيرة توفرها)",
                "",
                "**مكافأة نهاية الخدمة (الجرايتي):**",
                "• 21 يوم راتب أساسي لكل سنة (1-5 سنوات)",
                "• 30 يوم راتب أساسي لكل سنة (5+ سنوات)",
                "",
                "**نصيحة:** الراتب المُعلن قد يكون 'شامل' أو 'أساسي' — اسأل دائماً عن المجموع الإجمالي.",
            ]
        else:
            lines = [
                "**UAE Employment Package Guide** 🇦🇪",
                "",
                "**A typical UAE package includes:**",
                "• **Basic salary** (40–60% of total)",
                "• **Housing allowance** (20–30% of total) or company-provided accommodation",
                "• **Transport allowance** (AED 1,500–3,000/month)",
                "• **Phone / comms allowance** (AED 300–800/month)",
                "• **Medical insurance** (mandatory by law)",
                "• **Residence visa sponsorship** (employer's responsibility)",
                "",
            ]

            if years_exp >= 8:
                lines += [
                    "**At senior level, also negotiate:**",
                    "• School fees allowance (AED 10,000–30,000/year)",
                    "• Annual flight tickets home for family",
                    "• Company car or car allowance",
                    "",
                ]

            lines += [
                "**Annual leave:** 30 calendar days (after 1 year of service)",
                "**Public holidays:** ~14 days/year",
                "",
            ]

            if asks_gratuity:
                lines += [
                    "**End-of-service gratuity (UAE law):**",
                    "• 21 days basic salary per year for years 1–5",
                    "• 30 days basic salary per year for years 5+",
                    "• Paid when you leave (unless terminated for cause)",
                    "",
                ]

            lines += [
                "**Red flags to watch for:**",
                "• 'Package inclusive of all allowances' — demand the breakdown",
                "• Gratuity calculated on 'basic' not total (legal, but know what you're signing)",
                "• Medical insurance that doesn't cover dependants",
                "",
                "**Key question to always ask:** 'Is the quoted figure basic salary or total compensation?'",
            ]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "benefits_guide",
            "message": msg,
        }

    # ── Offer evaluation ─────────────────────────────────────────────────────────

    def _handle_offer_evaluation(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return a structured job offer evaluation framework."""
        arabic = self._is_arabic_text(message)

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        salary_expectation = self._profile_value(profile, "salary_expectation_aed") or None

        if arabic:
            lines = [
                "**إطار تقييم عرض العمل** ✅",
                "",
                "**راجع هذه النقاط قبل القرار:**",
                "",
                "**💰 التعويض:**",
                "□ هل الراتب الأساسي يتوافق مع السوق؟",
                "□ هل شرحوا جميع مكوّنات الراتب؟",
                "□ هل هناك بدل سكن / مواصلات / طبي؟",
                "□ هل هناك مكافأة أداء سنوية؟",
                "",
                "**📋 الشروط:**",
                "□ مدة العقد (دائم / محدد المدة / تجريبي)",
                "□ فترة التجربة وشروط الإنهاء",
                "□ فترة الإشعار عند الاستقالة",
                "□ تغطية التأمين الطبي (لك وللعائلة؟)",
                "",
                "**🏢 الشركة:**",
                "□ هل الشركة مستقرة ومرخصة؟",
                "□ هل سمعتها جيدة؟ (راجع Glassdoor وLinkedIn)",
                "□ فرص التطور الوظيفي",
                "",
                "**علامات تحذيرية:**",
                "• يطالبونك بالقرار خلال 24 ساعة",
                "• يرفضون إعطاءك نسخة من العقد",
                "• الوعود الشفهية غير موثقة",
            ]
        else:
            lines = [
                "**Job Offer Evaluation Checklist** ✅",
                "",
                "**Before you decide, verify:**",
                "",
                "**💰 Compensation:**",
                "□ Is the basic salary aligned with market rate?",
                "□ Does the total package include housing + transport + medical?",
                "□ Is there a performance bonus structure?",
                "□ When is the next salary review?",
                "",
            ]
            if salary_expectation:
                try:
                    exp_val = float(str(salary_expectation).replace(",", "").replace("k", "000"))
                    lines.append(f"Based on your target salary (AED {int(exp_val):,}/month), make sure total comp aligns.")
                    lines.append("")
                except (ValueError, TypeError):
                    pass

            lines += [
                "**📋 Contract terms:**",
                "□ Contract type: unlimited vs. limited-term (unlimited is better for you)",
                "□ Probation period: usually 3–6 months (termination easier for both sides)",
                "□ Notice period: 30–90 days typical",
                "□ Non-compete clause: check scope and duration",
                "",
                "**🏢 Company health:**",
                "□ Check Glassdoor reviews and LinkedIn employee count trends",
                "□ Ask about team stability — how long has the hiring manager been there?",
                "□ Understand reporting structure and career path",
                "",
                "**🚩 Red flags:**",
                "• Pressure to decide within 24 hours",
                "• Refusing to provide the written contract before you join",
                "• Verbal promises not reflected in the offer letter",
                "• Medical insurance not starting on day 1",
                "",
                "**Negotiation window:** You have ~3–5 days to counter in UAE market. Counter once, clearly.",
            ]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "offer_evaluation",
            "message": msg,
        }

    # ── UAE labor law / probation info ───────────────────────────────────────────

    def _handle_uae_labor_law(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return UAE labor law facts: probation, termination rights, labor card, contract types."""
        arabic = self._is_arabic_text(message)
        msg_lower = message.lower()

        asks_probation = bool(re.search(r"\bprobation\b", message, re.IGNORECASE))
        asks_termination = bool(re.search(r"\b(?:termination|dismiss|redundan|fire|fired|sack)\b", message, re.IGNORECASE))
        asks_contract = bool(re.search(r"\b(?:unlimited|limited)\s+contract\b", message, re.IGNORECASE))
        asks_labor_card = bool(re.search(r"\blabou?r\s+card\b", message, re.IGNORECASE))

        if arabic:
            if asks_probation:
                lines = [
                    "**فترة التجربة في الإمارات** 📋",
                    "",
                    "• **المدة:** حتى 6 أشهر (قابلة للتقليل باتفاق الطرفين)",
                    "• **إنهاء العقد خلال التجربة:** يحق لكلا الطرفين بإشعار 14 يوماً",
                    "• **التعويض:** إذا أنهى صاحب العمل العقد دون سبب، قد تستحق تعويضاً",
                    "• **الجرايتي:** لا تُحتسب الجرايتي للموظفين الذين يغادرون خلال التجربة",
                    "",
                    "**حقك:** يمكنك الاستقالة خلال التجربة بإشعار 14 يوماً. قد يطلب منك صاحب العمل التعويض إذا تركت للانضمام لمنافس.",
                ]
            else:
                lines = [
                    "**حقوق العمال في الإمارات** 🇦🇪",
                    "",
                    "**الحقوق الأساسية بموجب قانون العمل الاتحادي:**",
                    "• الراتب شهرياً لا يتأخر عن 14 يوماً",
                    "• 30 يوم إجازة سنوية مدفوعة (بعد سنة)",
                    "• تأمين طبي إلزامي",
                    "• مكافأة نهاية الخدمة (جرايتي)",
                    "• تأشيرة إقامة مكفولة من صاحب العمل",
                    "",
                    "**إنهاء العقد:** إشعار مسبق (30-90 يوم عادةً)",
                    "**تقديم شكوى:** MOHRE (وزارة الموارد البشرية) — الرقم 800 60",
                ]
        else:
            if asks_probation:
                lines = [
                    "**UAE Probation Period** 📋",
                    "",
                    "• **Duration:** Up to 6 months (can be shorter by agreement)",
                    "• **Notice to terminate during probation:** 14 days for either party",
                    "• **Compensation:** If employer terminates without valid reason, you may be entitled to compensation",
                    "• **Gratuity:** Generally not payable if you resign during probation",
                    "",
                    "**Your right to leave:** You can resign during probation with 14 days notice.",
                    "**Caution:** Employer may claim compensation if you join a direct competitor within 6 months.",
                ]
            elif asks_termination:
                lines = [
                    "**Termination Rights in UAE** 🇦🇪",
                    "",
                    "**If terminated by employer (without cause):**",
                    "• Notice period: as per contract (30–90 days typical)",
                    "• End-of-service gratuity: mandatory (21 days/year for yrs 1–5, 30 days/year after)",
                    "• Unused leave encashment: required",
                    "",
                    "**Unfair dismissal:** File a complaint with MOHRE (Ministry of Human Resources)",
                    "• Call: 800 60 | Website: mohre.gov.ae",
                    "• Complaint must be filed within 1 year of termination",
                    "",
                    "**If you resign:** Notice period as per contract; gratuity calculated on service duration.",
                ]
            elif asks_contract:
                lines = [
                    "**UAE Contract Types** 📋",
                    "",
                    "**Unlimited contract:**",
                    "• No fixed end date",
                    "• Either party can terminate with notice",
                    "• Full gratuity rights",
                    "",
                    "**Limited (fixed-term) contract:**",
                    "• Fixed duration (e.g., 2 years)",
                    "• Early termination may require compensation to employer",
                    "• Gratuity calculated differently",
                    "",
                    "**Since 2022:** UAE moved most employees to unlimited contracts under the new labor law.",
                ]
            else:
                lines = [
                    "**UAE Labor Law Key Facts** 🇦🇪",
                    "",
                    "**Employee rights under Federal Decree-Law No. 33 of 2021:**",
                    "• Salary paid within 14 days of due date (WPS system monitors this)",
                    "• 30 days annual leave (after 1 year)",
                    "• Mandatory medical insurance",
                    "• End-of-service gratuity",
                    "• Employer-sponsored residence visa",
                    "",
                    "**Notice period:** Usually 30–90 days per contract",
                    "**Complaints:** MOHRE — 800 60 | mohre.gov.ae",
                    "**Working hours:** 8 hrs/day, 48 hrs/week (reduced in Ramadan)",
                ]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "uae_labor_law",
            "sub_topic": "probation" if asks_probation else "termination" if asks_termination else "contract" if asks_contract else "general",
            "message": msg,
        }

    # ── Post-interview thank you email ────────────────────────────────────────────

    def _handle_post_interview_email(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return a guide and template for post-interview thank you / follow-up emails."""
        arabic = self._is_arabic_text(message)

        recent_company = ""
        recent_role = ""
        try:
            rctx = self._get_recent_context(user_id)
            recent_company = str(rctx.get("recent_company") or "").strip()
            recent_role = str(rctx.get("recent_job") or "").strip()
        except Exception:
            pass

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role = recent_role or (target_roles[0] if target_roles else "the role")
        company_str = f" at {recent_company}" if recent_company else ""

        if arabic:
            lines = [
                "**رسالة الشكر بعد المقابلة** ✉️",
                "",
                "**نعم، أرسلها دائماً** — معظم المتقدمين لا يفعلون، وهي ميزة تنافسية.",
                "",
                "**توقيت الإرسال:** خلال 24 ساعة من المقابلة.",
                "",
                "**نموذج مقترح:**",
                "---",
                f"الموضوع: شكراً — مقابلة {role}{company_str}",
                "",
                "السيد/السيدة [اسم المقابِل]،",
                "",
                f"شكراً لوقتكم اليوم ولمناقشة فرصة {role}. استمتعت بالتعرف على [أمر أعجبك في المقابلة].",
                "",
                "أنا متحمس جداً للانضمام إلى فريقكم، وأرى أن خبرتي في [مهارة رئيسية] ستضيف قيمة حقيقية.",
                "",
                "أتطلع لسماع أخباركم. لا تترددوا في التواصل معي إذا احتجتم أي معلومات إضافية.",
                "",
                "مع تحياتي،",
                "[اسمك]",
                "---",
            ]
        else:
            lines = [
                "**Post-Interview Thank You Email Guide** ✉️",
                "",
                "**Should you send one? Yes, always.** Most candidates don't — it's a differentiator.",
                "",
                "**Timing:** Within 24 hours of the interview.",
                "",
                "**Template:**",
                "---",
                f"Subject: Thank You — {role} Interview{company_str}",
                "",
                "Dear [Interviewer Name],",
                "",
                f"Thank you for taking the time to meet with me today about the {role} position. "
                "I enjoyed learning about [specific thing that impressed you — team, project, culture].",
                "",
                "The conversation reinforced my enthusiasm for the role. "
                "I believe my background in [key skill from your profile] aligns well with what you're looking for.",
                "",
                "Please let me know if you need any additional information. "
                "I look forward to hearing from you.",
                "",
                "Best regards,",
                "[Your Name]",
                "---",
                "",
                "**Tips:**",
                "• Keep it under 150 words",
                "• Mention one specific detail from the conversation (shows attention)",
                "• Do NOT follow up again for 5–7 business days after sending this",
                "• Send to every interviewer if there were multiple",
            ]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "post_interview_email",
            "role": role,
            "company": recent_company or None,
            "message": msg,
        }

    # ── Skill gap assessment ──────────────────────────────────────────────────────

    def _handle_skill_gap(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        """Return a skill gap assessment comparing profile skills to target role requirements."""
        arabic = self._is_arabic_text(message)

        skills = self._as_list(self._profile_value(profile, "skills"))
        certs = self._as_list(self._profile_value(profile, "certifications"))
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        years_exp = 0
        try:
            years_exp = int(self._profile_value(profile, "years_experience") or 0)
        except (ValueError, TypeError):
            pass

        # Extract target from message if present (e.g. "am I qualified for HSE Director?")
        _target_m = re.search(
            r"\b(?:for|to\s+become|to\s+be|to\s+get|ready\s+for)\s+(?:a\s+|an\s+)?([A-Z][a-zA-Z &/\-]{3,50})\b",
            message,
            re.IGNORECASE,
        )
        msg_target = _target_m.group(1).strip() if _target_m else ""
        target_role = msg_target or (target_roles[0] if target_roles else "your target role")

        skill_lower = {s.lower() for s in skills}
        cert_lower = {c.lower() for c in certs}
        has_skills = bool(skills)
        has_certs = bool(certs)

        # Lightweight heuristic gap analysis
        role_lower = target_role.lower()
        gaps: list[str] = []
        strengths: list[str] = []

        if any(x in role_lower for x in ["hse", "safety", "ehs", "health & safety"]):
            if any(x in cert_lower for x in ["nebosh", "iosh", "bcsp"]):
                strengths.append("Industry-standard safety certification (NEBOSH/IOSH)")
            else:
                gaps.append("NEBOSH IGC or IOSH Managing Safely (strongly preferred)")
            if any(x in skill_lower for x in ["incident investigation", "risk assessment"]):
                strengths.append("Risk assessment / incident investigation experience")
            else:
                gaps.append("Formal incident investigation methodology (e.g. TapRoot, ICAM)")
            if years_exp >= 5:
                strengths.append(f"{years_exp} years of relevant experience")
        elif any(x in role_lower for x in ["project manager", "project management", " pm"]):
            if any(x in cert_lower for x in ["pmp", "prince2", "agile", "scrum"]):
                strengths.append("Project management certification (PMP/PRINCE2)")
            else:
                gaps.append("PMP or PRINCE2 certification")
            if any(x in skill_lower for x in ["stakeholder", "risk", "budget", "schedule"]):
                strengths.append("Core PM skills (stakeholder, risk, budget)")
            else:
                gaps.append("Demonstrated budget and schedule management experience")
        elif any(x in role_lower for x in ["data", "analyst", "analytics", "scientist"]):
            if any(x in skill_lower for x in ["python", "sql", "power bi", "tableau"]):
                strengths.append("Data tools (Python/SQL/BI platforms)")
            else:
                gaps.append("Python or SQL proficiency")
                gaps.append("Power BI or Tableau for visualisation")
        elif any(x in role_lower for x in ["finance", "financial", "accountant"]):
            if any(x in cert_lower for x in ["acca", "cpa", "cfa", "cima"]):
                strengths.append("Professional finance qualification (ACCA/CPA/CFA)")
            else:
                gaps.append("ACCA, CFA, or CPA qualification")
        else:
            if not has_skills:
                gaps.append("Skills details not yet in your profile — upload your CV to get a full analysis")
            if not has_certs:
                gaps.append("Certifications not listed — add them for a more accurate assessment")

        if arabic:
            lines = [
                f"**تحليل فجوة المهارات لدور {target_role}** 📊",
                "",
            ]
            if strengths:
                lines += ["**نقاط قوتك:**"] + [f"✅ {s}" for s in strengths] + [""]
            if gaps:
                lines += ["**الفجوات التي يُنصح بسدّها:**"] + [f"⬜ {g}" for g in gaps] + [""]
            lines += [
                "**الخطوة التالية:** سد هذه الفجوات يزيد فرصك بشكل ملحوظ في الحصول على المقابلات.",
            ]
        else:
            lines = [
                f"**Skill Gap Assessment for {target_role}** 📊",
                "",
            ]
            if strengths:
                lines += ["**Your strengths (already have):**"] + [f"✅ {s}" for s in strengths] + [""]
            if gaps:
                lines += ["**Recommended gaps to close:**"] + [f"⬜ {g}" for g in gaps] + [""]
            if years_exp:
                if years_exp >= 8:
                    lines.append(f"Your {years_exp} years of experience places you at a competitive level.")
                elif years_exp >= 3:
                    lines.append(f"With {years_exp} years, closing these gaps should position you strongly.")
                else:
                    lines.append("Focus on certifications and portfolio projects to compensate for limited years.")
            lines += [
                "",
                "Want me to search for " + target_role + " roles that match your current profile?",
            ]

        msg = "\n".join(lines)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "skill_gap",
            "target_role": target_role,
            "strengths": strengths,
            "gaps": gaps,
            "message": msg,
        }

    # ── Interview preparation ────────────────────────────────────────────────────

    def _handle_interview_prep(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        target_role = ""
        if profile:
            roles = getattr(profile, "target_roles", None) or []
            if roles:
                target_role = roles[0]
            if not target_role:
                target_role = getattr(profile, "current_role", "") or ""

        role_line = f" for **{target_role}**" if target_role else ""

        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                f"## التحضير للمقابلة{role_line}\n\n"
                "**قبل المقابلة:**\n"
                "- ابحث عن الشركة: أهدافها، ثقافتها، آخر أخبارها\n"
                "- راجع متطلبات الوظيفة وحضّر أمثلة من تجربتك تتوافق معها\n"
                "- جهّز أسئلة ذكية لطرحها على المحاور\n\n"
                "**أسئلة شائعة يجب التحضير لها:**\n"
                "1. حدثنا عن نفسك — ملخص مهني موجز (2 دقيقتين)\n"
                "2. ما أبرز إنجازاتك؟ — استخدم مقاييس واضحة\n"
                "3. لماذا تريد العمل معنا؟ — اربطه بأهداف الشركة\n"
                "4. ما نقاط قوتك وضعفك؟ — كن صادقاً مع تحسّن واضح\n"
                "5. أين ترى نفسك بعد 5 سنوات؟ — اربطه بمسار الوظيفة\n\n"
                "**أسلوب STAR للأسئلة السلوكية:**\n"
                "**S**ituation → **T**ask → **A**ction → **R**esult\n\n"
                "**في يوم المقابلة:**\n"
                "- احضر قبل 10 دقائق على الأقل\n"
                "- ابدأ بمصافحة واثقة وتواصل بالعيون\n"
                "- في نهاية المقابلة اسأل: «ما الخطوة القادمة في عملية التوظيف؟»"
            )
        else:
            msg = (
                f"## Interview Preparation Guide{role_line}\n\n"
                "**Before the interview:**\n"
                "- Research the company: mission, culture, recent news, key projects\n"
                "- Map the job requirements to your experience with concrete examples\n"
                "- Prepare 3–5 smart questions to ask the interviewer\n\n"
                "**Common questions to prepare for:**\n"
                "1. **Tell me about yourself** — 2-minute career summary ending with why this role\n"
                "2. **Greatest achievement?** — Use numbers: \"increased X by Y%\", \"saved AED Z\"\n"
                "3. **Why this company?** — Tie it to their goals or products\n"
                "4. **Strengths and weaknesses?** — Be honest; pair weaknesses with active improvement\n"
                "5. **Where do you see yourself in 5 years?** — Align with the role's growth path\n\n"
                "**STAR method for behavioural questions:**\n"
                "**S**ituation → **T**ask → **A**ction → **R**esult\n\n"
                "*Example:* \"Tell me about a time you handled a difficult stakeholder.\"\n"
                "→ Situation, your Task, Action you took, measurable Result.\n\n"
                "**On the day:**\n"
                "- Arrive or join the call 10 minutes early\n"
                "- Firm handshake, eye contact, confident posture\n"
                "- Close by asking: \"What is the next step in your hiring process?\""
            )

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "interview_prep",
            "target_role": target_role,
            "message": msg,
        }

    # ── Salary negotiation ───────────────────────────────────────────────────────

    def _handle_salary_negotiation(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تتفاوض على راتبك في الإمارات\n\n"
                "**التوقيت المثالي:**\n"
                "- انتظر حتى تحصل على عرض رسمي قبل التفاوض\n"
                "- لا تذكر توقعاتك أولاً — دع صاحب العمل يبدأ\n\n"
                "**الخطوات:**\n"
                "1. **ابحث عن متوسط الراتب** للدور والخبرة في الإمارات\n"
                "2. **حدد نطاقاً** — الحد الأدنى المقبول والهدف المثالي\n"
                "3. **برر طلبك** بإنجازاتك ومهاراتك، وليس باحتياجاتك الشخصية\n"
                "4. **لا تقبل أو ترفض فوراً** — اطلب يومين للتفكير\n"
                "5. **تفاوض على الباقة كاملة**: بدل السكن، التأمين، الإجازة، المسمى الوظيفي\n\n"
                "**عبارات مفيدة:**\n"
                "- «بناءً على خبرتي وبحثي في السوق، كنت أتوقع نطاقاً بين X وY درهم»\n"
                "- «هل هناك مرونة في العرض؟»\n"
                "- «أقدّر العرض — هل يمكنني أخذ يومين للنظر فيه؟»\n\n"
                "**ملاحظة:** التفاوض أمر طبيعي ومتوقع في سوق الإمارات — 70٪ من أصحاب العمل يتوقعونه."
            )
        else:
            msg = (
                "## Salary Negotiation in the UAE\n\n"
                "**Timing:**\n"
                "- Wait until you have a formal offer before negotiating\n"
                "- Avoid naming your number first — let the employer anchor\n\n"
                "**Step-by-step:**\n"
                "1. **Research market rates** for the role, level, and industry in the UAE\n"
                "2. **Set your range** — know your walk-away floor and your ideal target\n"
                "3. **Justify with value**, not personal need: cite achievements, certifications, market data\n"
                "4. **Don't accept or decline on the spot** — ask for 48 hours to consider\n"
                "5. **Negotiate the full package**: housing allowance, medical, annual leave, title, start date\n\n"
                "**Phrases that work:**\n"
                "- *\"Based on my experience and market benchmarks, I was expecting a range of AED X–Y.\"*\n"
                "- *\"Is there flexibility in the offer?\"*\n"
                "- *\"I appreciate the offer — could I have 48 hours to review it?\"*\n\n"
                "**UAE tip:** Negotiation is expected here — roughly 70% of employers build room into the first offer. "
                "Counter-offers are rarely rescinded for politely negotiating."
            )

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "salary_negotiation",
            "message": msg,
        }

    # ── LinkedIn optimisation ────────────────────────────────────────────────────

    def _handle_linkedin_tips(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        target_role = ""
        if profile:
            roles = getattr(profile, "target_roles", None) or []
            if roles:
                target_role = roles[0]

        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## تحسين ملفك على LinkedIn للبحث الوظيفي في الإمارات\n\n"
                "**الصورة الشخصية والغلاف:**\n"
                "- صورة احترافية بخلفية محايدة — تزيد من فرص الظهور بنسبة 14×\n"
                "- صورة غلاف تعكس مجالك أو الشركات التي عملت فيها\n\n"
                "**العنوان (Headline):**\n"
                "- لا تكتف بالمسمى الوظيفي — أضف قيمتك الأساسية\n"
                f"- مثال: «{target_role} | HSE Leadership | UAE & GCC Operations» \n\n"
                "**ملخص About:**\n"
                "- 3-5 أسطر تبدأ بجملة جذابة عن ما تفعله وما تتميز به\n"
                "- أضف كلمات مفتاحية يبحث عنها المسؤولون في التوظيف\n\n"
                "**الخبرات:**\n"
                "- استخدم نقاط تحتوي على أرقام ونتائج ملموسة\n"
                "- أضف الوسائط (شهادات، مشاريع، مقالات) لكل منصب\n\n"
                "**نشاط LinkedIn:**\n"
                "- تفاعل مع منشورات في مجالك أسبوعياً\n"
                "- اطلب توصيات من زملاء ومديرين سابقين\n"
                "- اتبع شركاتك المستهدفة في الإمارات\n\n"
                "**الخصوصية:** فعّل وضع Open to Work بشكل خاص (مرئي للـ recruiters فقط)."
            )
        else:
            role_line = f" (targeting: **{target_role}**)" if target_role else ""
            msg = (
                f"## LinkedIn Optimisation for UAE Job Search{role_line}\n\n"
                "**Photo & banner:**\n"
                "- Professional headshot on a neutral background — profiles with photos get 14× more views\n"
                "- Banner image that reflects your industry or target companies\n\n"
                "**Headline:**\n"
                "- Go beyond job title — add your core value proposition\n"
                f"- Example: *\"{target_role or 'Operations Manager'} | Process Optimisation | UAE & GCC\"*\n\n"
                "**About section:**\n"
                "- 3–5 lines opening with a hook about what you do and what sets you apart\n"
                "- Embed keywords recruiters search for in your target role\n\n"
                "**Experience entries:**\n"
                "- Lead with impact bullets: numbers, percentages, AED values\n"
                "- Add media (certificates, project links, articles) to each role\n\n"
                "**Active presence:**\n"
                "- Engage with 2–3 posts weekly in your niche to surface in feeds\n"
                "- Request recommendations from ex-managers and close colleagues\n"
                "- Follow your target UAE companies to spot openings early\n\n"
                "**Open to Work:** Enable it privately (visible to recruiters only) to avoid alerting your current employer."
            )

        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "linkedin_tips",
            "target_role": target_role,
            "message": msg,
        }

    # ── Resignation letter ───────────────────────────────────────────────────────

    def _handle_resignation_letter(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        name = getattr(profile, "name", "") or ""
        if arabic:
            msg = (
                "## كيف تكتب خطاب استقالة احترافي\n\n"
                "**القواعد الأساسية في الإمارات:**\n"
                "- قدّم استقالتك كتابةً — لا شفهياً فقط\n"
                "- احترم فترة الإشعار المنصوص عليها في عقدك\n"
                "- حافظ على علاقة إيجابية — السوق الإماراتي صغير\n\n"
                "**هيكل الرسالة:**\n"
                "**الموضوع:** إشعار باستقالتي — [مسماك الوظيفي]\n\n"
                "عزيزي [اسم المدير]،\n\n"
                "أود إخطاركم رسمياً باستقالتي من منصبي كـ [مسماك الوظيفي] "
                "في [اسم الشركة]، وذلك اعتباراً من [تاريخ آخر يوم عمل]، "
                "مع الالتزام بفترة إشعار [X أسابيع/أشهر].\n\n"
                "أتطلع إلى إتمام جميع المهام المعلّقة وضمان انتقال سلس. "
                "شكراً لهذه الفرصة القيّمة والدعم الذي قدّمتموه طوال هذه المدة.\n\n"
                "مع التقدير،\n"
                f"{name or '[اسمك]'}\n\n"
                "**ملاحظات مهمة:**\n"
                "- لا تذكر أسباباً سلبية في الرسالة\n"
                "- احتفظ بنسخة منها لسجلاتك\n"
                "- ناقش نقل المهام مع مديرك مباشرةً"
            )
        else:
            msg = (
                "## How to Write a Professional Resignation Letter\n\n"
                "**UAE rules of thumb:**\n"
                "- Always resign in writing — a verbal notice is not enough\n"
                "- Honour the notice period stated in your contract\n"
                "- Keep it positive — the UAE market is small and references matter\n\n"
                "**Ready-to-use template:**\n\n"
                "---\n"
                "**Subject:** Notice of Resignation — [Your Job Title]\n\n"
                "Dear [Manager's Name],\n\n"
                "I am writing to formally notify you of my resignation from my position as "
                "[Your Job Title] at [Company Name], effective [last working date], "
                "in line with my [X weeks/months] notice period.\n\n"
                "I am committed to completing all pending tasks and ensuring a smooth handover. "
                "Thank you for the opportunity and the support during my time here.\n\n"
                f"Sincerely,\n{name or '[Your Name]'}\n\n"
                "---\n\n"
                "**Tips:**\n"
                "- No need to explain *why* you're leaving — keep it brief and professional\n"
                "- Keep a copy for your records\n"
                "- Offer to train your replacement or document your processes\n"
                "- Confirm receipt from HR in writing"
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "resignation_letter", "message": msg}

    # ── Relocation to UAE ────────────────────────────────────────────────────────

    def _handle_relocation_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## دليل الانتقال للعمل في الإمارات\n\n"
                "**قبل السفر:**\n"
                "- احصل على عرض عمل أولاً — معظم الشركات تشترط التأشيرة من الداخل\n"
                "- تحقق من صلاحية جواز سفرك (6 أشهر على الأقل)\n"
                "- جهّز وثائقك المصدّقة: الشهادات، كشف الراتب، شهادة الخبرة\n\n"
                "**بعد الوصول:**\n"
                "- سيقوم صاحب العمل عادةً بإجراءات تأشيرة الإقامة والعمل\n"
                "- افتح حساباً بنكياً فور الوصول (تحتاج لعقد العمل والإقامة)\n"
                "- احصل على رخصة القيادة الإماراتية إذا كانت مطلوبة\n\n"
                "**تكاليف المعيشة:**\n"
                "- دبي: إيجار غرفة/استوديو من 3,500–7,000 درهم/شهر\n"
                "- أبوظبي: أرخص بنسبة 15–20٪ عموماً\n"
                "- الشارقة: أرخص وتبعد 30–40 دقيقة عن دبي\n\n"
                "**نصيحة:** تفاوض على بدل السكن ضمن عرض العمل — الشركات الكبرى غالباً تُشمله."
            )
        else:
            msg = (
                "## Relocating to the UAE for Work — Practical Guide\n\n"
                "**Before you move:**\n"
                "- Secure a job offer first — most employers sponsor the visa from inside UAE\n"
                "- Ensure your passport is valid for at least 6 months\n"
                "- Prepare attested documents: degree certificates, salary slips, experience letters\n\n"
                "**On arrival:**\n"
                "- Your employer typically arranges the residence and work visa (UAE Labour card)\n"
                "- Open a UAE bank account once you have your employment contract and Emirates ID\n"
                "- Get a UAE driving licence if needed (some home-country licences can be converted)\n\n"
                "**Cost of living benchmarks:**\n"
                "| City | Studio/1BR rent/month |\n"
                "|---|---|\n"
                "| Dubai | AED 4,000–8,000 |\n"
                "| Abu Dhabi | AED 3,500–7,000 |\n"
                "| Sharjah | AED 2,500–5,000 (30–40 min commute to Dubai) |\n\n"
                "**Practical tips:**\n"
                "- Negotiate a housing allowance in your offer — large companies often provide it\n"
                "- Dubai has no income tax — your gross salary is your take-home\n"
                "- School fees are significant if you have children; factor in the total package"
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "relocation_uae", "message": msg}

    # ── Applying from abroad ─────────────────────────────────────────────────────

    def _handle_apply_from_abroad(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## التقديم على وظائف الإمارات من خارج البلاد\n\n"
                "**هل يمكنك التقديم من الخارج؟ نعم.**\n"
                "معظم الوظائف في الإمارات مفتوحة للمتقدمين من الخارج، "
                "خاصةً إذا كانت الشركة تقدّم كفالة التأشيرة.\n\n"
                "**استراتيجيات التقديم من الخارج:**\n"
                "- وضّح في سيرتك الذاتية أنك مستعد للانتقال فوراً\n"
                "- اذكر إذا كان لديك تأشيرة زيارة أو إمكانية الحضور لإجراء المقابلة\n"
                "- استخدم Bayt.com وLinkedIn مع تفعيل الفلتر الجغرافي للإمارات\n\n"
                "**ما يُزيد حظوظك:**\n"
                "- وجود خبرة في منطقة الخليج أو الأسواق الناشئة\n"
                "- شهادات معتمدة دولياً (PMP، NEBOSH، CPA...)\n"
                "- إرفاق خطاب تغطية يؤكد جاهزيتك للانتقال وتوقيته\n\n"
                "**هل تحتاج أن تكون في الإمارات قبل التعيين؟**\n"
                "لا دائماً — لكن بعض الشركات تُفضّل من هو متاح في الدولة. "
                "ذكر زيارة مرتقبة يُقوّي طلبك."
            )
        else:
            msg = (
                "## Applying for UAE Jobs from Abroad\n\n"
                "**Yes, you can apply from outside the UAE.** Most roles are open to international "
                "candidates, especially where the employer provides visa sponsorship.\n\n"
                "**How to make your overseas application competitive:**\n"
                "- State clearly on your CV that you are available to relocate and when\n"
                "- Mention any planned UAE visit — even a short trip shows you're serious\n"
                "- Use Bayt.com, LinkedIn, GulfTalent with UAE location filters\n"
                "- Keep your profile set to 'Open to Relocation' on job boards\n\n"
                "**What helps your chances:**\n"
                "- Gulf or Middle East experience (even on projects)\n"
                "- Internationally recognised certifications (PMP, NEBOSH, CPA, CFA...)\n"
                "- A cover letter that addresses relocation: ready date, notice period, visa needs\n\n"
                "**Do you need to be in UAE before applying?**\n"
                "Not usually — but some roles (especially government or banking) prefer "
                "locally-based candidates. For those, mention an upcoming visit or indicate "
                "you can attend an in-person interview at short notice."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "apply_from_abroad", "message": msg}

    # ── Employment gap ───────────────────────────────────────────────────────────

    def _handle_employment_gap(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تشرح الفجوة في مسيرتك المهنية\n\n"
                "**الفجوات في السيرة الذاتية أمر طبيعي — ما يهم هو كيف تُقدّمها.**\n\n"
                "**أسباب مقبولة شائعة:**\n"
                "- رعاية أحد أفراد الأسرة أو إجازة أمومة/أبوة\n"
                "- التطوير الذاتي أو الدراسة أو الشهادات\n"
                "- الانتقال بين الدول أو ظروف شخصية\n"
                "- مشاريع حرّة أو عمل تطوعي\n"
                "- إعادة تقييم المسار المهني بشكل مقصود\n\n"
                "**كيف تشرحها في المقابلة:**\n"
                "كن صريحاً وموجزاً — جملة أو جملتان تكفيان:\n"
                "*«أخذتُ [X أشهر] لـ [السبب]. خلال تلك الفترة [أضف شيئاً إيجابياً "
                "إن أمكن: دراسة، شهادة، عمل حر]. الآن أنا مستعد تماماً للانطلاق.»*\n\n"
                "**نصائح للسيرة الذاتية:**\n"
                "- إذا تجاوزت الفجوة ستة أشهر، أضف سطراً يشرحها\n"
                "- استخدم تنسيق السيرة الوظيفي (بالمهارات) بدلاً من الزمني إن ساعد ذلك\n"
                "- أبرز ما اكتسبته خلال الفترة: مهارات، شهادات، مشاريع"
            )
        else:
            msg = (
                "## How to Explain a Gap in Your CV\n\n"
                "**Gaps are common — what matters is how you frame them.**\n\n"
                "**Common, accepted reasons:**\n"
                "- Family caregiving, parental leave, or personal health\n"
                "- Studying, upskilling, or gaining certifications\n"
                "- Relocation or international move\n"
                "- Freelance, consulting, or voluntary work\n"
                "- A deliberate career pivot or sabbatical\n\n"
                "**How to address it in an interview (1-2 sentences):**\n"
                "*\"I took [X months] to [brief reason]. During that time I [positive activity "
                "if applicable: studied, freelanced, cared for family]. I'm now fully ready "
                "to return and contribute.\"*\n\n"
                "**On your CV:**\n"
                "- If the gap is over 6 months, add a brief line explaining it\n"
                "- For UAE roles, framing around family, relocation, or upskilling is "
                "well understood\n"
                "- A skills-based (functional) CV format can help de-emphasise timeline gaps\n\n"
                "**In UAE context:** Employers here are accustomed to gaps caused by visa "
                "transitions, family obligations, and international moves — be matter-of-fact "
                "and move on quickly to what you offer now."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "employment_gap", "message": msg}

    # ── Company research ─────────────────────────────────────────────────────────

    def _handle_company_research(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تبحث عن شركة قبل المقابلة\n\n"
                "**ما يجب أن تعرفه قبل دخول المقابلة:**\n\n"
                "**1. أساسيات الشركة**\n"
                "- ما الذي تفعله الشركة ومن هم عملاؤها الرئيسيون؟\n"
                "- من هم المنافسون؟ وما موقع الشركة في السوق؟\n"
                "- حجم الشركة وعدد الموظفين والنطاق الجغرافي\n\n"
                "**2. مصادر البحث**\n"
                "- الموقع الرسمي للشركة (خاصةً صفحتَي 'من نحن' والأخبار)\n"
                "- LinkedIn: الملف التعريفي، الموظفون، آخر المنشورات\n"
                "- Glassdoor: آراء الموظفين وتقييمات المقابلات\n"
                "- Google News: أحدث الأخبار والتطورات\n\n"
                "**3. ما تستخدمه في المقابلة**\n"
                "- اطرح سؤالاً يظهر معرفتك: «رأيتُ أنكم تتوسّعون في... كيف يؤثر ذلك على هذا الدور؟»\n"
                "- اربط مهاراتك بأهداف الشركة المُعلنة\n"
                "- اعرف اسم المدير المباشر إن أمكن (عبر LinkedIn)"
            )
        else:
            msg = (
                "## How to Research a Company Before an Interview\n\n"
                "**What to know before you walk in:**\n\n"
                "**1. Company basics**\n"
                "- What does the company do and who are their main customers?\n"
                "- Who are their competitors and where do they sit in the market?\n"
                "- Size, headcount, presence in UAE/GCC\n\n"
                "**2. Where to research**\n"
                "- Company website — especially 'About', 'News', and recent press releases\n"
                "- LinkedIn company page: growth trends, recent posts, employee count\n"
                "- Glassdoor: employee reviews and interview experiences\n"
                "- Google News: any recent coverage, deals, expansions, or problems\n"
                "- For UAE firms: Gulf Business, Zawya, Arabian Business\n\n"
                "**3. How to use it in the interview**\n"
                "- Ask a specific question: *\"I saw you're expanding into Saudi — how does "
                "that affect this role?\"*\n"
                "- Link your skills to their stated goals or recent initiatives\n"
                "- Know your interviewer's name and role (LinkedIn before you go in)\n\n"
                "**Target: 30 minutes of research minimum.** Knowing the company well sets "
                "you apart from candidates who didn't bother."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "company_research", "message": msg}

    # ── Freelance / self-employment in UAE ───────────────────────────────────────

    def _handle_freelance_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## العمل الحر في الإمارات\n\n"
                "**نعم، يمكنك العمل حراً في الإمارات — إليك كيفية البدء:**\n\n"
                "**الخيار 1: تصريح العمل الحر**\n"
                "- متاح من مناطق حرة: دبي للإعلام، twofour54 (أبوظبي)، IFZA، مناطق أخرى\n"
                "- يتيح لك العمل مع عدة عملاء دون كفيل\n"
                "- التكلفة: تبدأ من ~7,500 درهم سنوياً (تتفاوت حسب المنطقة)\n\n"
                "**الخيار 2: الترخيص التجاري**\n"
                "- مناسب إذا كنت ستؤسس نشاطاً تجارياً رسمياً\n"
                "- يمكن تأسيسه في البر الرئيسي (DED) أو في منطقة حرة\n\n"
                "**الخيار 3: العقود عبر شركة محلية**\n"
                "- بعض الشركات توظّف مستقلين بعقود محددة المدة دون الحاجة لترخيصك\n\n"
                "**ما تحتاجه للتقديم:**\n"
                "- جواز سفر ساري المفعول\n"
                "- صورة شخصية\n"
                "- نموذج الطلب + الرسوم\n"
                "- بعض المناطق تطلب خطة أعمال أو عينة من محفظتك\n\n"
                "**نصيحة:** قارن بين المناطق الحرة قبل الاختيار — تتفاوت التكاليف والقطاعات المسموح بها."
            )
        else:
            msg = (
                "## Freelancing in the UAE\n\n"
                "**Yes, you can freelance legally in the UAE.** Here's how:\n\n"
                "**Option 1: Freelance Permit (most popular)**\n"
                "- Issued by free zones: Dubai Media City, twofour54 (Abu Dhabi), "
                "IFZA, Meydan, others\n"
                "- Lets you work with multiple clients without a local sponsor\n"
                "- Cost: from ~AED 7,500/year (varies by free zone)\n"
                "- Best for: media, tech, consulting, education, creative sectors\n\n"
                "**Option 2: Free Zone Trade Licence**\n"
                "- For setting up a formal business entity\n"
                "- More flexibility on business activities\n"
                "- Higher cost but more credibility with corporate clients\n\n"
                "**Option 3: Contract via a local company**\n"
                "- Some UAE firms hire contractors directly on short-term contracts "
                "without requiring your own licence\n\n"
                "**What you typically need to apply:**\n"
                "- Valid passport + photo\n"
                "- Application form + fee payment\n"
                "- Some free zones require a portfolio or business plan\n\n"
                "**Tip:** Compare free zones before committing — costs, permitted activities, "
                "and visa eligibility differ. Meydan and IFZA are often most affordable."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "freelance_uae", "message": msg}

    # ── End of service gratuity ─────────────────────────────────────────────────

    def _handle_eosb(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## مكافأة نهاية الخدمة في الإمارات\n\n"
                "**من له الحق في مكافأة نهاية الخدمة؟**\n"
                "كل موظف أتمّ سنة كاملة في الخدمة، سواء أُنهيت خدمته أو استقال.\n\n"
                "**طريقة الحساب (القطاع الخاص — قانون العمل الإماراتي):**\n"
                "- السنوات الخمس الأولى: **21 يوماً** من الراتب الأساسي عن كل سنة\n"
                "- ما بعد خمس سنوات: **30 يوماً** من الراتب الأساسي عن كل سنة إضافية\n"
                "- الحد الأقصى للمكافأة الإجمالية: راتب سنتين كاملتين\n\n"
                "**مثال:**\n"
                "راتب أساسي 10,000 درهم × 4 سنوات = 21 × 4 ÷ 30 × 10,000 = **28,000 درهم**\n\n"
                "**ملاحظات مهمة:**\n"
                "- تُحسب على أساس الراتب الأساسي، لا الإجمالي (لا تشمل البدلات)\n"
                "- إذا استقلت قبل اكتمال سنة، لا توجد مكافأة\n"
                "- موظفو الحكومة يخضعون لنظام مختلف (صندوق التقاعد)\n"
                "- بعض الشركات توفّر صناديق ادخار واستثمار بديلة (DEWS/GPSSA)"
            )
        else:
            msg = (
                "## End of Service Gratuity (EOSB) in UAE\n\n"
                "**Who is entitled?** Any employee who has completed at least one full year "
                "of service — whether terminated or resigned.\n\n"
                "**How it's calculated (private sector — UAE Labour Law):**\n"
                "- First 5 years: **21 days** basic salary per year of service\n"
                "- Beyond 5 years: **30 days** basic salary per additional year\n"
                "- Maximum: 2 years' total basic salary\n\n"
                "**Example:**\n"
                "Basic salary AED 10,000 × 4 years = (21 × 4 ÷ 30) × 10,000 = **AED 28,000**\n\n"
                "**Important notes:**\n"
                "- Calculated on **basic salary only** — housing, transport, and other allowances "
                "are excluded\n"
                "- If you resign before completing 1 year, no gratuity is owed\n"
                "- Government employees fall under a separate pension/retirement scheme\n"
                "- Some companies offer savings or investment schemes (DEWS, GPSSA) in lieu of "
                "the statutory gratuity — check your contract\n\n"
                "**Tip:** Your employer must pay gratuity within 14 days of your last working day. "
                "If they don't, you can file a complaint with MOHRE (Ministry of Human Resources)."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "eosb", "message": msg}

    # ── Non-compete clause ───────────────────────────────────────────────────────

    def _handle_non_compete(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## شرط عدم المنافسة في الإمارات\n\n"
                "**هل يُطبَّق شرط عدم المنافسة في الإمارات؟**\n"
                "نعم، لكن بقيود واضحة. وفقاً لقانون العمل الإماراتي (المادة 10)، "
                "يمكن للشركات إدراج شروط عدم منافسة في العقود، شريطة أن تكون:\n\n"
                "**شروط الصحة:**\n"
                "- **محدودة زمنياً** — لا تتجاوز عامين في الغالب\n"
                "- **محدودة جغرافياً** — منطقة أو دولة بعينها، لا العالم أجمع\n"
                "- **محدودة بنوع النشاط** — نفس الصناعة أو الدور الوظيفي تحديداً\n\n"
                "**ماذا يعني هذا عملياً؟**\n"
                "- لا يستطيع صاحب العمل منعك من العمل تماماً\n"
                "- تُطبّق المحاكم فقط الشروط المعقولة والمتناسبة\n"
                "- غالباً ما تكون شروط عامة جداً (مثل 'أي منافس في العالم') غير قابلة للتطبيق\n\n"
                "**نصيحة:**\n"
                "راجع العقد بعناية. إذا كانت الشركة الجديدة في قطاع مختلف أو دور مختلف، "
                "فالشرط على الأرجح لن يسري. استشر محامياً قبل القبول إذا كان الشرط قاسياً."
            )
        else:
            msg = (
                "## Non-Compete Clauses in UAE\n\n"
                "**Are non-competes enforceable in UAE?** Yes — but with clear limits. "
                "Under UAE Labour Law (Article 10), employers can include non-compete "
                "clauses, provided they are:\n\n"
                "**For a clause to be enforceable it must be:**\n"
                "- **Time-limited** — typically no more than 2 years\n"
                "- **Geographically limited** — a specific region or country, not the entire world\n"
                "- **Activity-specific** — same industry or role, not 'any work whatsoever'\n\n"
                "**In practice:**\n"
                "- Courts will only enforce clauses that are reasonable and proportionate\n"
                "- Overly broad clauses (e.g., 'any competitor globally for 5 years') are "
                "routinely struck down\n"
                "- If your new role is in a different sector or function, the clause "
                "likely won't apply\n\n"
                "**Practical steps:**\n"
                "1. Read your contract carefully — what sector, role, geography, and timeframe?\n"
                "2. If the new job is clearly different, the risk is low\n"
                "3. If there's overlap, seek legal advice before accepting — UAE employment "
                "lawyers often offer a short consultation for a fixed fee\n"
                "4. Negotiating a waiver from your old employer is also an option"
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "non_compete", "message": msg}

    # ── Work visa / sponsorship process ─────────────────────────────────────────

    def _handle_work_visa_process(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تحصل على تأشيرة عمل في الإمارات\n\n"
                "**في معظم الحالات، الشركة هي من تُكفّلك.** إليك كيف يسير الأمر:\n\n"
                "**الخطوات الأساسية (كفالة صاحب العمل):**\n"
                "1. **عرض العمل والعقد** — تُصدر الشركة عرضاً رسمياً وتبدأ إجراءات التأشيرة\n"
                "2. **الإشعار المبدئي** — يتيح لك دخول الإمارات (فترة محدودة) لإتمام الإجراءات\n"
                "3. **الفحص الطبي** — فحص إلزامي عبر مراكز معتمدة من MOHRE\n"
                "4. **إصدار الإقامة** — تأشيرة إقامة تصدر بعد الفحص واستيفاء المتطلبات\n"
                "5. **بطاقة الهوية** — تُصدر من دائرة الهجرة وشؤون الأجانب (ICA)\n\n"
                "**المدة المعتادة:** 3–6 أسابيع من تاريخ القبول\n\n"
                "**ما يتحمّله صاحب العمل عادةً:**\n"
                "- رسوم التأشيرة والكفالة\n"
                "- تكاليف الفحص الطبي\n"
                "- نفقات السفر الأولى (حسب العقد)\n\n"
                "**ملاحظة:** تحقّق دائماً من أن العقد يتضمن نص الكفالة والتأمين الطبي."
            )
        else:
            msg = (
                "## How UAE Work Visa Sponsorship Works\n\n"
                "**In most cases, your employer sponsors your visa.** Here's the typical process:\n\n"
                "**Step-by-step (employer-sponsored):**\n"
                "1. **Job offer accepted** — employer initiates the visa application with MOHRE\n"
                "2. **Entry permit** — allows you to enter the UAE to complete the process "
                "(usually 60 days)\n"
                "3. **Medical test** — mandatory health check at an approved UAE center\n"
                "4. **Residence visa stamped** — issued in your passport after medical clearance\n"
                "5. **Emirates ID** — applied for through ICA; required for banking, phone, etc.\n\n"
                "**Typical timeline:** 3–6 weeks from offer acceptance to residence visa\n\n"
                "**What the employer normally covers:**\n"
                "- Visa and sponsorship fees\n"
                "- Medical test costs\n"
                "- Initial flight (check your offer letter)\n\n"
                "**What to confirm in your offer:**\n"
                "- Visa sponsorship explicitly stated\n"
                "- Health insurance included (mandatory in Dubai and Abu Dhabi)\n"
                "- Who pays for your family's visas if you're relocating with dependants\n\n"
                "**Note:** Free zone employees get their visa through the free zone authority, "
                "not MOHRE — the process is similar but faster in many cases."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "work_visa_process", "message": msg}

    # ── Arabic language requirement ──────────────────────────────────────────────

    def _handle_arabic_requirement(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## هل تحتاج إلى تعلم العربية للعمل في الإمارات؟\n\n"
                "**الإجابة القصيرة: لا، في معظم القطاعات.**\n\n"
                "الإمارات بيئة عمل متعددة اللغات. الإنجليزية هي لغة العمل الرئيسية في:\n"
                "- الشركات الدولية والمتعددة الجنسيات\n"
                "- قطاعي التكنولوجيا والمال والبنوك\n"
                "- الضيافة والسياحة\n"
                "- الرعاية الصحية والهندسة والبناء\n\n"
                "**متى تُفيد العربية؟**\n"
                "- الجهات الحكومية والشبه الحكومية\n"
                "- التسويق الموجّه للسوق المحلي والخليجي\n"
                "- بعض أدوار خدمة العملاء\n"
                "- الأدوار القانونية التي تتعامل مع وثائق محلية\n\n"
                "**الخلاصة:** إجادة الإنجليزية كافية في معظم الأحيان. "
                "إضافة العربية ولو على مستوى تحادثي تمنحك ميزة تنافسية في بعض القطاعات، "
                "لكنها نادراً ما تكون شرطاً أساسياً لوظائف متخصصة."
            )
        else:
            msg = (
                "## Do You Need to Speak Arabic to Work in UAE?\n\n"
                "**Short answer: No — not for most roles.**\n\n"
                "The UAE is a multilingual work environment. English is the dominant "
                "business language across:\n"
                "- Multinational and international companies\n"
                "- Finance, banking, and tech sectors\n"
                "- Hospitality, tourism, and retail\n"
                "- Healthcare, engineering, and construction\n\n"
                "**When Arabic genuinely helps:**\n"
                "- Government and semi-government entities (ADNOC, RTA, etc.)\n"
                "- Marketing roles targeting local/GCC audiences\n"
                "- Some customer-facing positions in retail and services\n"
                "- Legal roles involving Arabic-language contracts or court filings\n\n"
                "**The bottom line:**\n"
                "Fluent English is sufficient for the vast majority of professional roles. "
                "Adding conversational Arabic (even basic greetings) is a plus that shows "
                "cultural respect — but for most specialist positions, your skills and "
                "experience matter far more than language."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "arabic_requirement", "message": msg}

    # ── Background check / police clearance ─────────────────────────────────────

    def _handle_background_check(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## فحص الخلفية وشهادة حسن السيرة في الإمارات\n\n"
                "**ما الذي يتحقق منه أصحاب العمل؟**\n"
                "- **التحقق من السيرة الذاتية:** التحقق من المسمى الوظيفي والتواريخ ومكان العمل\n"
                "- **التحقق من المؤهلات:** التحقق من الشهادات والشهادات المهنية\n"
                "- **المراجع المهنية:** التواصل مع أصحاب العمل السابقين\n\n"
                "**شهادة حسن السيرة والسلوك:**\n"
                "مطلوبة في بعض القطاعات (الحكومي، الصحة، التعليم، المال).\n"
                "- يمكن الحصول عليها من بلدك الأصلي (مختومة ومصدّقة)\n"
                "- أو من الشرطة الإماراتية إذا كنت مقيماً في الدولة\n\n"
                "**نصائح مهمة:**\n"
                "- تأكد من أن ما في سيرتك الذاتية متطابق تماماً مع الحقيقة\n"
                "- كن صادقاً مع صاحب العمل إذا كان هناك تاريخ مهني يحتاج توضيحاً\n"
                "- فحص الخلفية عادةً يُجرى بعد تقديم العرض وقبيل التعيين الرسمي"
            )
        else:
            msg = (
                "## Background Checks & Police Clearance in UAE\n\n"
                "**What employers typically check:**\n"
                "- **CV verification:** Job titles, dates, and employer names\n"
                "- **Qualification verification:** Degree and certification authenticity\n"
                "- **Reference checks:** Calls or emails to previous employers\n"
                "- **Criminal record:** Varies by role and sector\n\n"
                "**Police clearance / Good Conduct Certificate:**\n"
                "Required in certain sectors — government, healthcare, education, finance, "
                "and roles involving security clearance.\n\n"
                "- **If you're overseas:** Obtain from your home country's police authority "
                "(must be apostilled/attested)\n"
                "- **If you're in UAE already:** Apply via the UAE Police or ICP portal\n\n"
                "**Practical tips:**\n"
                "- Ensure your CV is 100% accurate — discrepancies are a red flag\n"
                "- Background checks typically happen *after* the offer is made, "
                "before your official start date\n"
                "- Inform your employer proactively if there's anything they might find — "
                "honesty is far better than a surprise during screening\n"
                "- For senior or regulated roles, expect a more thorough process "
                "(financial checks, LinkedIn verification, etc.)"
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "background_check", "message": msg}

    # ── Free zone vs mainland ────────────────────────────────────────────────────

    def _handle_free_zone_mainland(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## الفرق بين العمل في المنطقة الحرة والبر الرئيسي في الإمارات\n\n"
                "**المنطقة الحرة (Free Zone)**\n"
                "- شركات تعمل داخل مناطق اقتصادية خاصة (DIFC، دبي للإعلام، ADGM...)\n"
                "- التأشيرة والكفالة تصدر عبر سلطة المنطقة الحرة\n"
                "- القوانين قد تختلف قليلاً (خاصةً في DIFC وADGM)\n"
                "- عادةً لا يُسمح للموظف بالعمل خارج حدود المنطقة إلا بتصاريح\n"
                "- أجور تنافسية وبيئة عمل دولية\n\n"
                "**البر الرئيسي (Mainland)**\n"
                "- شركات مسجّلة في دائرة التنمية الاقتصادية (DED)\n"
                "- الكفالة عبر وزارة الموارد البشرية (MOHRE)\n"
                "- قانون العمل الإماراتي يُطبَّق بالكامل\n"
                "- حرية العمل في أي مكان في الدولة\n"
                "- بعض القطاعات (الحكومي، البنية التحتية) تتطلب تسجيل البر الرئيسي\n\n"
                "**كموظف، ماذا يعني ذلك لك؟**\n"
                "- حقوقك العمالية (المكافأة، الإجازة، الإشعار) محمية في الحالتين\n"
                "- الفرق الجوهري: جهة إصدار التأشيرة والكفالة\n"
                "- إذا أردت تغيير وظيفتك، تأكد من أن نقل الكفالة ممكن"
            )
        else:
            msg = (
                "## Free Zone vs Mainland Employment in UAE\n\n"
                "| | **Free Zone** | **Mainland** |\n"
                "|---|---|---|\n"
                "| **Registered with** | Free zone authority (e.g. DIFC, DMCC, IFZA) | DED / MOHRE |\n"
                "| **Visa sponsor** | Free zone authority | Employer via MOHRE |\n"
                "| **Labour law** | Mostly same; DIFC/ADGM have own courts | UAE Labour Law |\n"
                "| **Work location** | Typically within free zone only | Anywhere in UAE |\n"
                "| **Client contracts** | May need agent to work with mainland firms | No restriction |\n\n"
                "**What this means for you as an employee:**\n"
                "- Your core rights (gratuity, annual leave, notice period) are protected "
                "under UAE Labour Law in both cases\n"
                "- Free zone jobs are often in tech, media, finance, logistics — sectors "
                "that cluster in specific zones\n"
                "- DIFC and ADGM have their own courts and employment regulations — "
                "read your contract carefully if joining these\n\n"
                "**Key practical points:**\n"
                "- If you want to switch jobs, check whether your visa transfer is "
                "straightforward (free zone → mainland transfers are common)\n"
                "- For freelancers: free zone permits are the primary route (see freelance permit)\n"
                "- Most multinationals and banks operate on mainland; most startups and "
                "media companies are in free zones"
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "free_zone_mainland", "message": msg}

    # ── Working hours / overtime ─────────────────────────────────────────────────

    def _handle_working_hours(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## ساعات العمل والعمل الإضافي في الإمارات\n\n"
                "**ساعات العمل القانونية (قانون العمل الإماراتي):**\n"
                "- **الحد الأقصى:** 8 ساعات يومياً / 48 ساعة أسبوعياً\n"
                "- **شهر رمضان:** 6 ساعات يومياً للموظف المسلم\n"
                "- قد يختلف التطبيق الفعلي بين الشركات والقطاعات\n\n"
                "**العمل الإضافي:**\n"
                "- ما يتجاوز 8 ساعات يومياً يُعتبر عملاً إضافياً\n"
                "- **الأجر الإضافي:** الراتب الأساسي + 25% (في أيام العمل العادية)\n"
                "- **الأجر الإضافي ليلاً (10م–4ص):** الراتب الأساسي + 50%\n"
                "- **أيام الراحة والعطل الرسمية:** راتب مضاعف + يوم بديل\n\n"
                "**ما يجب معرفته:**\n"
                "- تأكد من أن عقدك يُحدد ساعات العمل والعمل الإضافي بوضوح\n"
                "- بعض الشركات تدفع بدل إضافي ثابتاً بدلاً من احتسابه بالساعة\n"
                "- العمال المنزليون وموظفو المناطق الحرة قد يخضعون لأحكام مختلفة"
            )
        else:
            msg = (
                "## Working Hours & Overtime in UAE\n\n"
                "**Legal working hours (UAE Labour Law):**\n"
                "- **Maximum:** 8 hours/day or 48 hours/week\n"
                "- **Ramadan:** 6 hours/day for Muslim employees\n"
                "- In practice, many professional roles operate 9–10 hours/day — "
                "check your contract\n\n"
                "**Overtime rules:**\n"
                "- Anything beyond 8 hours/day counts as overtime\n"
                "- **Overtime rate:** Basic salary + **25%** premium\n"
                "- **Night overtime (10pm–4am):** Basic salary + **50%** premium\n"
                "- **Rest days and public holidays:** Double pay + a compensatory day off\n\n"
                "**Important to know:**\n"
                "- Your offer letter/contract should state your hours — "
                "if it says 'as required', that's worth negotiating\n"
                "- Some companies pay a fixed monthly overtime allowance "
                "rather than calculating by the hour\n"
                "- Free zone employees may fall under slightly different rules "
                "(check your free zone authority's guidelines)\n"
                "- Disputes on unpaid overtime can be filed with MOHRE"
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "working_hours", "message": msg}

    # ── UAE Golden Visa ──────────────────────────────────────────────────────────

    def _handle_golden_visa(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## الإقامة الذهبية في الإمارات\n\n"
                "**ما هي الإقامة الذهبية؟**\n"
                "إقامة طويلة المدى (5 أو 10 سنوات) تتيح لك الإقامة والعمل والدراسة "
                "في الإمارات دون الحاجة إلى كفيل.\n\n"
                "**الفئات المؤهلة:**\n"
                "- **المستثمرون:** استثمار لا يقل عن 2 مليون درهم في عقارات أو تجارة\n"
                "- **رواد الأعمال:** مشاريع مبتكرة أو شركات ناشئة معترف بها\n"
                "- **الكفاءات المتميزة:** الأطباء، العلماء، الأكاديميون، المهندسون البارزون\n"
                "- **الطلاب المتفوقون:** خريجو الجامعات بمعدلات عالية\n"
                "- **الرياضيون والفنانون المتميزون**\n\n"
                "**المزايا:**\n"
                "- إقامة مستقلة (بدون كفيل)\n"
                "- إمكانية إحضار الأسرة (الزوج والأبناء وحتى الوالدين)\n"
                "- الاحتفاظ بالتأشيرة حتى في حالة عدم العمل لفترة\n\n"
                "**كيف تتقدم:** عبر بوابة ICP الإلكترونية أو من خلال صاحب العمل."
            )
        else:
            msg = (
                "## UAE Golden Visa\n\n"
                "**What is it?** A long-term UAE residence visa (5 or 10 years) that lets "
                "you live, work, and study in the UAE without needing an employer sponsor.\n\n"
                "**Who qualifies:**\n"
                "- **Investors:** AED 2M+ in UAE real estate or business\n"
                "- **Entrepreneurs:** Innovative startups or ventures recognised by a "
                "UAE incubator/accelerator\n"
                "- **Specialised talent:** Doctors, scientists, engineers, academics, "
                "artists with proven expertise\n"
                "- **Outstanding students:** Graduating with a GPA of 3.75+ from "
                "an accredited UAE university, or top high school graduates\n"
                "- **Athletes and creative professionals** with national or international recognition\n\n"
                "**Key benefits:**\n"
                "- Sponsor-free residence — tied to you, not your employer\n"
                "- Can sponsor family (spouse, children, parents)\n"
                "- Visa stays valid even during extended periods without employment\n\n"
                "**How to apply:** Through the ICA (Federal Authority for Identity, "
                "Citizenship, Customs & Port Security) portal, or via your employer "
                "or free zone if they support golden visa nominations.\n\n"
                "**Tip:** For employed professionals, the most common pathway is "
                "employer nomination as 'specialised talent' — ask your HR department "
                "whether your role qualifies."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "golden_visa", "message": msg}

    # ── Professional references ──────────────────────────────────────────────────

    def _handle_job_references(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تتعامل مع المراجع المهنية\n\n"
                "**من تختار كمرجع؟**\n"
                "- مديرك المباشر السابق (الأفضل دائماً)\n"
                "- زملاء أقدم أو مشرفون عملوا معك عن كثب\n"
                "- عملاء أو شركاء يمكنهم تقييم عملك\n"
                "- تجنّب الأصدقاء الشخصيين أو أفراد العائلة\n\n"
                "**كيف تطلب مرجعاً:**\n"
                "1. تواصل معهم قبل إدراج اسمهم بوقت كافٍ\n"
                "2. ذكّرهم بمشاريع محددة أو إنجازات بارزة\n"
                "3. أرسل لهم سيرتك الذاتية ووصف الوظيفة المستهدفة\n"
                "4. أعلمهم بالجدول الزمني المتوقع\n\n"
                "**في السياق الإماراتي:**\n"
                "- التحقق من المراجع شائع ويتم عادةً بعد تقديم العرض الوظيفي\n"
                "- كثير من أصحاب العمل يكتفون بمرجعين فقط\n"
                "- إذا كنت في وضع سري، يمكنك الإشارة إلى أن المراجع 'متاحة عند الطلب'"
            )
        else:
            msg = (
                "## How to Handle Professional References\n\n"
                "**Who to choose:**\n"
                "- Your direct line manager (strongest reference)\n"
                "- A senior colleague or project lead who knows your work well\n"
                "- A client or partner who can speak to your output\n"
                "- Avoid personal friends or family members\n\n"
                "**How to ask:**\n"
                "1. Contact them *before* listing their name — never surprise them\n"
                "2. Remind them of specific projects or achievements they can speak to\n"
                "3. Share your CV and the job description so they can tailor what they say\n"
                "4. Give them a heads-up on timing ('they may call within the next 2 weeks')\n\n"
                "**In UAE context:**\n"
                "- Reference checks are standard and typically happen *after* an offer "
                "is made\n"
                "- Most employers ask for 2–3 references\n"
                "- If your search is confidential, put 'References available on request' "
                "on your CV — this is widely understood\n"
                "- LinkedIn recommendations can supplement verbal references\n\n"
                "**If you can't use your current employer:**\n"
                "Mention this upfront — most hiring managers understand. You can offer "
                "a previous manager or a client instead."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_references", "message": msg}

    # ── Interview / office dress code ───────────────────────────────────────────

    def _handle_dress_code(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## ماذا ترتدي في المقابلة الوظيفية بالإمارات\n\n"
                "**القاعدة الأساسية: الأناقة المهنية دائماً.**\n\n"
                "**للرجال:**\n"
                "- بدلة رسمية (بيضاء أو رمادية أو كحلية) مع ربطة عنق: مناسبة للبنوك والقانون والشركات الحكومية\n"
                "- قميص أنيق مع بنطال وحذاء جلدي: مقبول في معظم الشركات الدولية والتقنية\n"
                "- تجنب: الجينز والملابس غير الرسمية حتى لو كان هناك نظام 'casual Friday'\n\n"
                "**للنساء:**\n"
                "- ملابس مهنية محتشمة: بنطال أو تنورة طويلة مع بلوزة أنيقة أو بدلة رسمية\n"
                "- الأكمام الطويلة أو المتوسطة مناسبة ثقافياً\n"
                "- الألوان الهادئة أو الكلاسيكية (كحلي، رمادي، أبيض، بيج)\n\n"
                "**نصيحة مهمة:** إذا كانت الشركة كاجوال، فما زال يُفضَّل الحضور بمظهر أكثر رسمية "
                "في المقابلة. الانطباع الأول يُحدث فرقاً."
            )
        else:
            msg = (
                "## What to Wear to a UAE Job Interview\n\n"
                "**Rule of thumb: always dress one level smarter than the company culture.**\n\n"
                "**Men:**\n"
                "- Full suit (navy, charcoal, or grey) + tie: appropriate for finance, "
                "law, government, and senior roles\n"
                "- Smart trousers + collared shirt + dress shoes: acceptable for most "
                "tech, media, and international firms\n"
                "- Avoid: jeans, trainers, and casualwear even if the office has a "
                "relaxed dress code day-to-day\n\n"
                "**Women:**\n"
                "- Professional, modest attire: tailored trousers or a knee-length (or "
                "longer) skirt with a smart blouse, or a business suit\n"
                "- Covered shoulders and modest neckline are culturally appropriate "
                "and always safe in UAE\n"
                "- Classic colours (navy, grey, white, beige) work well\n\n"
                "**UAE-specific note:**\n"
                "Workplaces in UAE are diverse and international — you won't be expected "
                "to wear traditional dress. However, conservative professional attire "
                "shows respect for local culture and makes a strong first impression.\n\n"
                "**When in doubt:** slightly overdressed is always better than underdressed "
                "in a UAE interview context."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "dress_code", "message": msg}

    # ── Remote work from UAE ─────────────────────────────────────────────────────

    def _handle_remote_work_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## العمل عن بُعد من الإمارات\n\n"
                "**هل يمكنك العمل لصالح شركة أجنبية وأنت في الإمارات؟**\n"
                "نعم — لكن يجب أن يكون لديك الوضع القانوني المناسب.\n\n"
                "**الخيارات المتاحة:**\n"
                "- **تأشيرة العمل عن بُعد (Virtual Work Residence):** تُتيح لك العمل لصالح صاحب عمل "
                "خارج الإمارات بشكل قانوني، وتُصدر لمدة سنة قابلة للتجديد.\n"
                "- **تصريح العمل الحر:** إذا كنت مستقلاً تعمل مع عملاء دوليين.\n"
                "- **إقامة بكفالة صاحب العمل:** إذا كانت الشركة الأجنبية لديها فرع في الإمارات.\n\n"
                "**الضرائب:**\n"
                "الإمارات لا تفرض ضريبة دخل شخصية — ميزة كبيرة للعمل عن بُعد. "
                "لكن قد تظل ملزماً بالإفصاح الضريبي في بلدك الأصلي حسب قوانينه."
            )
        else:
            msg = (
                "## Working Remotely from UAE\n\n"
                "**Can you work for a foreign company while living in UAE?** "
                "Yes — but you need the right legal status.\n\n"
                "**Your main options:**\n"
                "- **Virtual Work Residence Visa:** UAE-issued 1-year (renewable) visa "
                "specifically for remote workers employed by companies outside the UAE. "
                "Requires proof of employment + salary AED 15,000+/month equivalent\n"
                "- **Freelance permit:** If you're self-employed or work with multiple "
                "international clients (issued by a free zone authority)\n"
                "- **Employer-sponsored residence:** If your foreign employer has a UAE "
                "branch or subsidiary and can sponsor you directly\n\n"
                "**Tax position:**\n"
                "- UAE has no personal income tax — a major advantage for remote workers\n"
                "- However, you may still have tax reporting obligations in your home "
                "country (check your country's rules on worldwide income)\n"
                "- UK, US, and Australian citizens typically need to declare income "
                "regardless of where they work\n\n"
                "**Practical tip:** Ensure you have valid UAE residency (not just a "
                "tourist or visit visa) — working on a tourist visa is not permitted."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "remote_work_uae", "message": msg}

    # ── Annual leave entitlement ─────────────────────────────────────────────────

    def _handle_annual_leave(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## الإجازة السنوية وأيام العطل الرسمية في الإمارات\n\n"
                "**الإجازة السنوية (قانون العمل الإماراتي):**\n"
                "- **السنة الأولى إلى الخامسة:** 30 يوم تقويمي سنوياً\n"
                "- **بعد 5 سنوات خدمة:** 30 يوماً (قد تمنح بعض الشركات أكثر)\n"
                "- إذا انتهت الخدمة قبل اكتمال السنة، يُحتسب الأجر عن أيام الإجازة المتبقية\n\n"
                "**العطلات الرسمية (الإمارات 2024/2025):**\n"
                "- اليوم الوطني (2–3 ديسمبر): يومان\n"
                "- يوم الشهيد (30 نوفمبر): يوم واحد\n"
                "- رأس السنة الميلادية (1 يناير): يوم واحد\n"
                "- اليوم الوطني السعودي والأعياد الإسلامية (رمضان، العيدان، الهجرة، المولد)\n"
                "- الأعياد الإسلامية تتغير سنوياً وفق الهلال\n\n"
                "**ملاحظة:** الإجازة القانونية أيام تقويمية (تشمل الجمعة والسبت)، "
                "وليس أياماً عمل فقط."
            )
        else:
            msg = (
                "## Annual Leave & Public Holidays in UAE\n\n"
                "**Annual leave entitlement (UAE Labour Law):**\n"
                "- **First 6 months:** Accruing but no leave taken (probation)\n"
                "- **After 6 months, within first year:** 2 days/month accrual\n"
                "- **After 1 year of service:** 30 calendar days per year\n"
                "- Unused leave carried over or paid out depends on your contract\n\n"
                "**Important note:** UAE counts annual leave in **calendar days**, "
                "not working days — so weekends and days off within your leave count.\n\n"
                "**UAE Public Holidays (approx. per year):**\n"
                "- New Year's Day (1 Jan)\n"
                "- Eid Al Fitr (3 days — date varies)\n"
                "- Eid Al Adha (3 days — date varies)\n"
                "- Islamic New Year (1 day — date varies)\n"
                "- Prophet's Birthday (1 day — date varies)\n"
                "- Commemoration Day / Martyrs' Day (30 Nov)\n"
                "- UAE National Day (2–3 Dec)\n\n"
                "**Total: ~13–15 public holidays per year.** Islamic holiday dates "
                "shift annually based on the lunar calendar.\n\n"
                "**Tip:** Many UAE companies also offer additional leave for weddings, "
                "bereavement, or maternity/paternity — check your contract."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "annual_leave", "message": msg}

    # ── Sick leave ────────────────────────────────────────────────────────────────

    def _handle_sick_leave(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## الإجازة المرضية في الإمارات\n\n"
                "**استحقاق الإجازة المرضية (قانون العمل الاتحادي):**\n"
                "- يجب إتمام فترة التجربة أولاً لاستحقاق الإجازة المرضية\n"
                "- **أول 15 يوم:** بأجر كامل\n"
                "- **15 يوماً تالية:** بنصف الأجر\n"
                "- **بعد ذلك (حتى إجمالي 90 يوماً):** بدون أجر\n\n"
                "**ما تحتاجه:**\n"
                "- شهادة طبية معتمدة من مستشفى أو عيادة مرخصة\n"
                "- إخطار صاحب العمل في أقرب وقت ممكن\n\n"
                "**ملاحظة:** الإجازة المرضية المدفوعة لا تُحتسب من إجازتك السنوية. "
                "يحق لصاحب العمل إنهاء العقد إذا تجاوزت 90 يوماً غياباً بسبب المرض خلال سنة."
            )
        else:
            msg = (
                "## Sick Leave in UAE\n\n"
                "**Sick leave entitlement (UAE Federal Labour Law):**\n"
                "- Sick leave kicks in **after your probation period** is complete\n"
                "- **First 15 days:** Full pay\n"
                "- **Next 30 days:** Half pay\n"
                "- **Remaining days (up to 90 total):** Unpaid\n\n"
                "**Requirements:**\n"
                "- A medical certificate from a licensed hospital or clinic\n"
                "- Notify your employer as soon as possible\n\n"
                "**Key points:**\n"
                "- Sick leave does **not** count against your annual leave balance\n"
                "- Your employer cannot terminate you solely for being sick during the "
                "first 90 days\n"
                "- After 90 days of sick leave in one year, the employer may end the "
                "contract (with full end-of-service gratuity)\n\n"
                "**Tip:** Many companies have private health insurance that covers "
                "GP visits — check your employee benefits package."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "sick_leave", "message": msg}

    # ── Maternity / paternity leave ───────────────────────────────────────────────

    def _handle_parental_leave(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## إجازة الأمومة والأبوة في الإمارات\n\n"
                "**إجازة الأمومة (للمرأة العاملة في القطاع الخاص):**\n"
                "- **60 يوماً** إجازة أمومة: 45 يوماً بأجر كامل + 15 يوماً بنصف أجر\n"
                "- تستحق بعد خدمة عام واحد مع صاحب العمل ذاته\n"
                "- إذا كانت مدة الخدمة أقل من عام، تُمنح الإجازة بنصف الأجر\n\n"
                "**إجازة الأبوة (للرجل في القطاع الخاص):**\n"
                "- **5 أيام عمل** بأجر كامل خلال 6 أشهر من الولادة\n\n"
                "**القطاع الحكومي الاتحادي:**\n"
                "- إجازة أمومة: 90 يوماً بأجر كامل\n"
                "- إجازة أبوة: 5 أيام عمل\n\n"
                "**نصيحة:** تحقق دائماً من سياسة شركتك، فبعض أصحاب العمل يوفرون شروطاً أفضل من الحد الأدنى القانوني."
            )
        else:
            msg = (
                "## Maternity & Paternity Leave in UAE\n\n"
                "**Maternity leave (private sector):**\n"
                "- **60 days total:** 45 days at full pay + 15 days at half pay\n"
                "- Entitled after completing **1 year** with the same employer\n"
                "- Less than 1 year of service → leave granted at half pay\n"
                "- Additional unpaid leave of up to 45 days may be taken (for "
                "illness related to pregnancy/delivery, with a medical certificate)\n\n"
                "**Paternity leave (private sector):**\n"
                "- **5 working days** at full pay, to be taken within 6 months of birth\n\n"
                "**Federal government employees:**\n"
                "- Maternity: 90 calendar days at full pay\n"
                "- Paternity: 5 working days\n\n"
                "**Important:** These are the legal minimums. Many UAE employers — "
                "especially multinationals — offer more generous policies. Always "
                "review your employment contract and HR handbook.\n\n"
                "**Tip:** Maternity leave is separate from annual leave and does not "
                "reduce your leave balance."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "parental_leave", "message": msg}

    # ── Probation period rules ────────────────────────────────────────────────────

    def _handle_probation_rules(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## فترة التجربة في الإمارات\n\n"
                "**الأحكام الأساسية (قانون العمل الاتحادي):**\n"
                "- الحد الأقصى لفترة التجربة: **6 أشهر**\n"
                "- لا يمكن تمديدها أو تكرارها مع نفس صاحب العمل\n\n"
                "**هل يمكن فسخ العقد أثناء فترة التجربة؟**\n"
                "- نعم، يحق لصاحب العمل إنهاء العقد بإشعار **14 يوماً** (أو أقل وفق العقد)\n"
                "- لا يستحق الموظف مكافأة نهاية الخدمة (EOSB) إذا أُنهي عقده خلال التجربة\n\n"
                "**هل يمكنك الاستقالة أثناء فترة التجربة؟**\n"
                "- نعم، ولكن بإشعار **30 يوماً** إذا كنت تنتقل إلى وظيفة أخرى داخل الإمارات\n"
                "- إذا غادرت البلاد أو كانت الشركة هي من أنهت العقد، قد لا يُطبق هذا الشرط\n\n"
                "**ملاحظة:** لا تستحق الإجازة السنوية والمرضية المدفوعة إلا بعد انتهاء فترة التجربة."
            )
        else:
            msg = (
                "## Probation Period Rules in UAE\n\n"
                "**Key rules (UAE Federal Labour Law):**\n"
                "- Maximum probation period: **6 months**\n"
                "- Cannot be extended or repeated with the same employer\n\n"
                "**Can you be dismissed during probation?**\n"
                "- Yes — your employer can terminate with as little as **14 days' notice** "
                "(or per your contract terms)\n"
                "- No end-of-service gratuity (EOSB) is owed if terminated during probation\n"
                "- However, termination for discriminatory reasons is still unlawful\n\n"
                "**Can you resign during probation?**\n"
                "- Yes, but you must give **30 days' notice** if you're moving to another "
                "UAE employer (to avoid a potential 1-year work ban)\n"
                "- If you're leaving the UAE or the employer terminates first, "
                "the ban typically does not apply\n\n"
                "**What benefits are withheld during probation?**\n"
                "- Paid sick leave: not available until probation ends\n"
                "- Annual leave accrues from day 1 but typically cannot be taken "
                "during probation (employer discretion)\n\n"
                "**Tip:** Always read your contract — some employers offer longer notice "
                "periods or waive the 30-day resignation notice."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "probation_rules", "message": msg}

    # ── Termination notice period ─────────────────────────────────────────────────

    def _handle_notice_period(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## مدة الإخطار (Notice Period) في الإمارات\n\n"
                "**قانون العمل الاتحادي (مرسوم بقانون رقم 33 لعام 2021):**\n"
                "- الحد الأدنى لمدة الإخطار: **30 يوم تقويمي**\n"
                "- يمكن الاتفاق على مدة أطول في العقد (شائع في المناصب العليا: 60–90 يوماً)\n\n"
                "**هل يمكن لصاحب العمل إنهاء عقدك دون إخطار؟**\n"
                "- لا، إلا في حالات الفصل التأديبي (مخالفة جسيمة) المنصوص عليها في المادة 44\n"
                "- في حالات الفصل التأديبي: يُنهى العقد فوراً دون مكافأة نهاية خدمة\n\n"
                "**هل يمكنك الاستقالة دون إخطار؟**\n"
                "- لا، الاستقالة دون إخطار قد تُعرضك لخصم من الأجر أو الملاحقة القانونية\n"
                "- في فترة التجربة: الإخطار 14 يوماً (إذا انتقلت لعمل آخر داخل الإمارات: 30 يوماً)\n\n"
                "**نصيحة:** تحقق من بند الإخطار في عقدك — فبعض العقود تنص على 60 أو 90 يوماً، "
                "وهذا ملزم قانونياً."
            )
        else:
            msg = (
                "## Notice Period in UAE\n\n"
                "**UAE Federal Labour Law (Decree No. 33 of 2021):**\n"
                "- Minimum notice period: **30 calendar days**\n"
                "- Contracts can specify longer notice (common for senior roles: 60–90 days)\n\n"
                "**Can your employer fire you without notice?**\n"
                "- No, except in disciplinary termination cases under Article 44 "
                "(e.g., serious misconduct, fraud)\n"
                "- In disciplinary termination: the employer can dismiss immediately "
                "without notice but must still pay any unpaid salary owed\n\n"
                "**Can you resign without notice?**\n"
                "- No — resigning without notice can mean a salary deduction equal to "
                "the notice period pay, or legal liability\n"
                "- **During probation:** 14 days' notice (or 30 days if moving to another "
                "UAE employer)\n\n"
                "**Garden leave:** Some employers ask you to stop working but remain "
                "paid and on the books during your notice period — this is legal in UAE.\n\n"
                "**Tip:** Always check your contract. If it says 60 or 90 days' notice, "
                "that is the legally binding term — not the 30-day minimum."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "notice_period", "message": msg}

    # ── Wage Protection System / late salary ──────────────────────────────────────

    def _handle_wps_salary_protection(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## نظام حماية الأجور (WPS) في الإمارات\n\n"
                "**ما هو نظام حماية الأجور؟**\n"
                "- نظام إلكتروني تُشرف عليه وزارة الموارد البشرية (MOHRE)\n"
                "- يُلزم أصحاب العمل بصرف الرواتب عبر قنوات موافق عليها خلال 10 أيام من موعدها\n\n"
                "**ماذا تفعل إذا تأخر راتبك؟**\n"
                "1. انتظر 10 أيام عمل إضافية بعد موعد الراتب قبل تقديم شكوى رسمية\n"
                "2. أبلغ مشرفك أو قسم الموارد البشرية أولاً\n"
                "3. تقديم شكوى عبر:\n"
                "   - تطبيق / موقع MOHRE الإلكتروني\n"
                "   - الاتصال على رقم 800-MOHRE (800-60473)\n"
                "   - زيارة مراكز العمل (تسهيل)\n\n"
                "**العقوبات على صاحب العمل:**\n"
                "- غرامات وتجميد تصاريح العمل الجديدة إذا تأخر صرف الراتب أكثر من 10 أيام\n\n"
                "**ملاحظة:** يغطي نظام WPS القطاع الخاص فقط — لا يشمل موظفي الحكومة."
            )
        else:
            msg = (
                "## Wage Protection System (WPS) in UAE\n\n"
                "**What is WPS?**\n"
                "- An electronic salary transfer system overseen by MOHRE "
                "(Ministry of Human Resources & Emiratisation)\n"
                "- Requires private-sector employers to pay salaries through "
                "approved channels within **10 days** of the due date\n\n"
                "**What to do if your salary is late:**\n"
                "1. Wait up to **10 working days** after your pay date before filing a formal complaint\n"
                "2. Raise it with your HR / line manager first (paper trail helps)\n"
                "3. File a complaint through:\n"
                "   - **MOHRE app or website** (mohre.gov.ae)\n"
                "   - **Call 800-MOHRE (800-60473)**\n"
                "   - Visit a **Tasheel / MOHRE service centre**\n\n"
                "**Consequences for employers:**\n"
                "- Fines and a freeze on new work permit applications if salaries are "
                "unpaid for more than 10 days\n"
                "- Persistent non-payment can result in licence suspension\n\n"
                "**Important:** WPS covers **private sector only** — government employees "
                "fall under separate regulations.\n\n"
                "**Tip:** Keep digital copies of your pay slips and bank statements "
                "as evidence if you need to escalate a complaint."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "wps_salary_protection", "message": msg}

    # ── Employer health insurance ─────────────────────────────────────────────────

    def _handle_employer_health_insurance(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## التأمين الصحي من صاحب العمل في الإمارات\n\n"
                "**هل التأمين الصحي إلزامي؟**\n"
                "- **نعم، في دبي وأبوظبي:** التأمين الصحي للموظفين إلزامي بموجب القانون\n"
                "- في دبي: يُلزم قانون التأمين الصحي الإلزامي (2014) أصحاب العمل بتوفيره للموظفين والمعالين\n"
                "- في أبوظبي: إلزامي بموجب قانون الصحة الأساسية\n\n"
                "**ماذا يغطي التأمين المُقدَّم من صاحب العمل عادةً؟**\n"
                "- زيارات الطوارئ والعيادات الخارجية\n"
                "- الاستشارات الطبية والأدوية\n"
                "- بعض خطط التأمين تشمل طب الأسنان والبصريات\n"
                "- المعالون (الزوجة والأطفال) قد يُشملون أو يُستثنون حسب الشركة\n\n"
                "**نصيحة:** اطلب تفاصيل بطاقة التأمين وشبكة المستشفيات المعتمدة قبل توقيع العقد."
            )
        else:
            msg = (
                "## Employer Health Insurance in UAE\n\n"
                "**Is health insurance mandatory?**\n"
                "- **Yes, in Dubai and Abu Dhabi:** Employers are legally required to "
                "provide health insurance to employees\n"
                "- **Dubai:** Mandatory Health Insurance Law (2014) — employers must cover "
                "all employees AND their dependants\n"
                "- **Abu Dhabi:** Mandatory since 2005 under the Basic Health Programme\n"
                "- **Other emirates:** No blanket federal mandate, but most reputable "
                "employers still provide it\n\n"
                "**What does employer health insurance typically cover?**\n"
                "- GP visits and outpatient consultations\n"
                "- Emergency treatment\n"
                "- Prescription medications\n"
                "- Some plans include dental and optical\n"
                "- Maternity coverage varies — check the policy\n\n"
                "**Dependants:**\n"
                "- In Dubai, employers must cover spouse and up to 3 children\n"
                "- In Abu Dhabi, dependants must be sponsored separately by the employee\n\n"
                "**Tip:** Always ask for the insurance card, policy number, and the "
                "list of approved hospitals (network providers) before you start. "
                "Using out-of-network providers can mean paying out of pocket."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "employer_health_insurance", "message": msg}

    # ── Visa cancellation grace period ────────────────────────────────────────────

    def _handle_visa_cancellation(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## ماذا يحدث للتأشيرة بعد ترك العمل؟\n\n"
                "**عند إلغاء التأشيرة أو إنهاء العقد:**\n"
                "- تُمنح فترة سماح مدتها **30 يوماً** بعد إلغاء تأشيرة الإقامة للخروج أو تسوية الوضع\n"
                "- خلال هذه الفترة، يمكنك البقاء في الإمارات للبحث عن وظيفة أخرى أو تعديل إقامتك\n\n"
                "**خياراتك خلال فترة السماح:**\n"
                "1. **العثور على صاحب عمل جديد:** يُحوّل التأشيرة عبر الكفالة إلى جهة عمل جديدة\n"
                "2. **الانتقال إلى تأشيرة زيارة:** للبقاء والبحث عن عمل بشكل قانوني\n"
                "3. **تأشيرة بحث العمل (Job Seeker Visa):** تتيح البقاء لمدة 60–180 يوماً لأصحاب المؤهلات العالية\n"
                "4. **المغادرة وإعادة الدخول:** أبسط خيار إذا كان لديك عرض وظيفي قادم\n\n"
                "**تحذير:** البقاء بعد انتهاء فترة السماح يُفضي إلى غرامة يومية — تحقق من تاريخ انتهاء الإقامة دائماً."
            )
        else:
            msg = (
                "## What Happens to Your Visa After Leaving a Job in UAE?\n\n"
                "**When your visa is cancelled / employment ends:**\n"
                "- You are granted a **30-day grace period** from the date of visa "
                "cancellation to either leave the UAE or change your visa status\n"
                "- During this window you can legally remain in the UAE\n\n"
                "**Your options during the grace period:**\n"
                "1. **Find a new employer** — they can transfer your visa sponsorship\n"
                "2. **Switch to a visit visa** — allows you to stay and job-search legally\n"
                "3. **Job Seeker Visa** — 60 to 180 days for highly qualified professionals "
                "(bachelor's degree+ and relevant experience)\n"
                "4. **Leave and re-enter** — simplest if a new offer is imminent\n\n"
                "**End-of-service process:**\n"
                "- Your employer must cancel your visa and labour card after the last day\n"
                "- Overstaying the grace period incurs a daily fine — always confirm "
                "your visa expiry date\n\n"
                "**Tip:** Save a copy of your visa cancellation document — you'll need "
                "it to prove your status to a new employer."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "visa_cancellation", "message": msg}

    # ── Emiratisation / Nafis impact on expat hiring ──────────────────────────────

    def _handle_emiratisation(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## التوطين ونافس: هل يؤثر على فرص العمل للوافدين؟\n\n"
                "**ما هو التوطين؟**\n"
                "- سياسة حكومية تُلزم الشركات الخاصة بتوظيف نسبة محددة من المواطنين الإماراتيين\n"
                "- الشركات ذات 50+ موظف مُلزمة بتحقيق حصص توطين متصاعدة (2% سنوياً حتى 2026)\n\n"
                "**برنامج نافس:**\n"
                "- مبادرة حكومية تُقدم دعماً مالياً للمواطنين العاملين في القطاع الخاص\n"
                "- يُحفّز أصحاب العمل على توظيف المواطنين بدعم جزئي للرواتب\n\n"
                "**هل يؤثر على فرصك كوافد؟**\n"
                "- في معظم القطاعات: لا، الوافدون لا يزالون يشكلون الغالبية العظمى من القوى العاملة\n"
                "- القطاعات الأكثر تأثراً: التمويل والمصارف والتأمين والتجزئة وقطاع الموارد البشرية\n"
                "- الوظائف التقنية والمتخصصة: أقل تأثراً نظراً لندرة المواطنين المؤهلين في بعض المجالات\n\n"
                "**نصيحة:** ركز على المهارات المتخصصة والخبرة الدولية — هذه لا يزال الطلب عليها مرتفعاً."
            )
        else:
            msg = (
                "## Emiratisation & Nafis: Does It Affect Expat Job Seekers?\n\n"
                "**What is Emiratisation?**\n"
                "- A UAE government policy requiring private-sector companies to hire "
                "a set percentage of Emirati nationals\n"
                "- Companies with 50+ employees must increase Emirati headcount by "
                "2% per year, targeting specific sectors (finance, insurance, retail, HR)\n\n"
                "**What is Nafis?**\n"
                "- A federal programme that subsidises Emirati salaries to make hiring "
                "nationals more affordable for private companies\n"
                "- Named after the Arabic word for 'compete', it aims to place Emiratis "
                "in quality private-sector roles\n\n"
                "**Does it affect expat hiring?**\n"
                "- **For most roles: No** — expats still make up 85–90% of the UAE workforce\n"
                "- **Most affected sectors:** banking, finance, insurance, HR, retail\n"
                "- **Less affected:** technology, engineering, healthcare, hospitality, "
                "construction (where Emirati supply is low)\n"
                "- Companies cannot fill Emiratisation quotas with expats, so the "
                "competition is typically within different talent pools\n\n"
                "**Tip:** If you're applying to a heavily regulated UAE bank or "
                "insurer, be aware that some entry-level roles may be reserved for "
                "nationals. Mid and senior-level specialist roles remain open."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "emiratisation", "message": msg}

    # ── Job scam detection ────────────────────────────────────────────────────────

    def _handle_job_scam(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تكتشف عروض العمل المزيفة في الإمارات؟\n\n"
                "**علامات تحذيرية شائعة:**\n"
                "- يُطلب منك دفع رسوم: للتأشيرة، المعالجة، التدريب، أو الزي الرسمي — **العمل الحقيقي لا يطلب منك المال**\n"
                "- الراتب مرتفع جداً مقارنة بالسوق دون متطلبات واضحة\n"
                "- يتواصل معك المُعيِّن عبر واتساب أو برنامج شخصي فقط دون بريد عمل رسمي\n"
                "- لا يوجد عقد رسمي أو مقابلة حقيقية قبل الموافقة على التوظيف\n"
                "- الشركة غير مسجلة أو لا يمكن التحقق منها\n\n"
                "**كيف تتحقق من صحة العرض؟**\n"
                "1. ابحث عن الشركة في موقع وزارة الموارد البشرية (MOHRE) أو السجل التجاري\n"
                "2. تحقق من وجود الشركة على LinkedIn وموقعها الرسمي\n"
                "3. اطلب إجراء المقابلة عبر تطبيق Zoom أو حضورياً\n"
                "4. لا تدفع أي رسوم قبل التوقيع على عقد رسمي\n\n"
                "**إذا تعرضت للاحتيال:** تواصل مع شرطة الإمارات (999) أو قدم شكوى عبر موقع وزارة الداخلية."
            )
        else:
            msg = (
                "## How to Spot UAE Job Scams\n\n"
                "**Common red flags:**\n"
                "- **They ask you to pay money** — for visa fees, processing, training, "
                "uniform, or medical tests. Legitimate employers never charge candidates.\n"
                "- Salary is unrealistically high with no clear skill requirements\n"
                "- Recruiter contacts you only on WhatsApp or personal email, "
                "never a company address\n"
                "- You receive a 'job offer' without a real interview\n"
                "- Company name is hard to verify or doesn't appear in official directories\n"
                "- Pressure to respond quickly or 'secure your spot' before you can verify\n\n"
                "**How to verify a job offer:**\n"
                "1. Search the company on **mohre.gov.ae** or the UAE trade register\n"
                "2. Check the company on **LinkedIn** and their official website\n"
                "3. Request a **video interview** via Zoom or Google Meet\n"
                "4. Never pay any fees before signing an official contract\n"
                "5. Verify the recruiter's identity on LinkedIn\n\n"
                "**Legitimate job boards in UAE:**\n"
                "- Bayt.com, LinkedIn, GulfTalent, Naukrigulf, Indeed UAE\n\n"
                "**If you've been scammed:** Report to UAE Police (999) or "
                "online via the Ministry of Interior's e-crimes portal."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_scam", "message": msg}

    # ── Salary certificate / employment letter ────────────────────────────────────

    def _handle_salary_certificate(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## شهادة الراتب وخطاب العمل في الإمارات\n\n"
                "**ما هي شهادة الراتب؟**\n"
                "- وثيقة رسمية تُصدرها الشركة تُثبت مسمّاك الوظيفي وراتبك ووضعك الوظيفي\n"
                "- مطلوبة للبنوك (فتح حساب، قرض، بطاقة ائتمان)، السفارات، الملاك\n\n"
                "**كيف تطلبها؟**\n"
                "1. تواصل مع قسم الموارد البشرية أو المحاسبة\n"
                "2. وضّح الغرض (بنك، سفارة...) لأن الصياغة قد تختلف\n"
                "3. يستغرق الإصدار عادةً 1–3 أيام عمل\n\n"
                "**ما هو خطاب عدم الممانعة (NOC)؟**\n"
                "- وثيقة تُفيد بأن صاحب العمل لا يعترض على نشاط معين (زيارة، دراسة، عمل آخر)\n"
                "- مطلوبة أحياناً لتغيير الكفيل أو الحصول على تصاريح معينة\n\n"
                "**نصيحة:** بعض الشركات تطلب فترة عمل أدنى (3–6 أشهر) قبل إصدار خطاب الراتب — تحقق من سياستهم."
            )
        else:
            msg = (
                "## Salary Certificate & Employment Letter in UAE\n\n"
                "**What is a salary certificate?**\n"
                "- An official letter from your employer confirming your job title, "
                "salary, and employment status\n"
                "- Required by banks (account opening, loans, credit cards), embassies, "
                "and landlords\n\n"
                "**How to request one:**\n"
                "1. Contact your HR or accounts department\n"
                "2. State the purpose (bank, embassy, etc.) — the wording may differ\n"
                "3. Allow **1–3 working days** for processing\n"
                "4. Ensure it's printed on company letterhead and signed by an authorised person\n\n"
                "**What is a NOC (No Objection Certificate)?**\n"
                "- A letter from your employer stating they have no objection to "
                "a specific activity (travel, study, second employment, sponsorship transfer)\n"
                "- Sometimes required when switching sponsors or obtaining certain permits\n\n"
                "**What is an employment letter?**\n"
                "- Similar to a salary certificate but may not state the exact salary amount\n"
                "- Used for visa applications, residency, or embassy submissions\n\n"
                "**Tip:** Some companies have a minimum tenure policy (e.g., 3–6 months) "
                "before they issue salary letters — check with HR."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "salary_certificate", "message": msg}

    # ── Networking in UAE ─────────────────────────────────────────────────────────

    def _handle_networking_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تبني شبكة علاقاتك المهنية في الإمارات؟\n\n"
                "**لماذا التواصل مهم جداً في الإمارات؟**\n"
                "- تُشير الدراسات إلى أن 60–70% من الوظائف تُملأ عبر العلاقات الشخصية في الإمارات\n"
                "- الثقة الشخصية تتقدم على الكفاءة في كثير من بيئات العمل الخليجية\n\n"
                "**كيف تبدأ؟**\n"
                "1. **LinkedIn:** حافظ على حضور قوي وتفاعل مع منشورات محترفين في مجالك\n"
                "2. **فعاليات التواصل:** ابحث عن Meetup، Eventbrite، Networking events في دبي/أبوظبي\n"
                "3. **غرف التجارة:** Dubai Chamber، Abu Dhabi Chamber تستضيف فعاليات للأعضاء\n"
                "4. **المجموعات المهنية:** مجموعات LinkedIn وWhatsApp المتخصصة في قطاعك\n"
                "5. **مقابلات الاستكشاف (Coffee chats):** اطلب محادثة قصيرة مع محترفين تحترمهم\n\n"
                "**نصيحة:** في الإمارات، القطاع صغير والسمعة تنتشر بسرعة — كن محترفاً ومتابعاً دائماً."
            )
        else:
            msg = (
                "## Networking in UAE: How to Build Your Professional Circle\n\n"
                "**Why networking matters more in UAE:**\n"
                "- Studies suggest 60–70% of UAE jobs are filled through connections\n"
                "- Personal trust and referrals carry significant weight in Gulf hiring culture\n\n"
                "**How to network effectively:**\n"
                "1. **LinkedIn** — optimise your profile, post content, connect with "
                "professionals in your sector, comment thoughtfully\n"
                "2. **In-person events** — search Meetup.com, Eventbrite, and LinkedIn "
                "Events for Dubai/Abu Dhabi networking events in your field\n"
                "3. **Industry associations** — Dubai Chamber of Commerce, "
                "industry councils, and professional bodies host regular events\n"
                "4. **WhatsApp and LinkedIn groups** — many UAE industry communities "
                "share jobs and insights in private groups\n"
                "5. **Coffee chats** — message someone you respect and ask for a 20-minute chat; "
                "most professionals in UAE are open to it\n"
                "6. **Alumni networks** — universities and business schools have active UAE alumni chapters\n\n"
                "**UAE-specific tips:**\n"
                "- Business cards are still widely exchanged — have one ready\n"
                "- Follow up within 24 hours after meeting someone\n"
                "- UAE is a small professional world — reputation travels fast\n\n"
                "**Tip:** Ramadan networking events are surprisingly common and valuable — "
                "iftars are a key social occasion for professionals in the UAE."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "networking_uae", "message": msg}

    # ── Asking for a promotion ────────────────────────────────────────────────────

    def _handle_promotion_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تطلب الترقية في عملك بالإمارات؟\n\n"
                "**متى يكون التوقيت مناسباً؟**\n"
                "- بعد إنجاز مشروع ناجح أو تحقيق نتيجة ملموسة\n"
                "- قبل أو أثناء تقييم الأداء السنوي\n"
                "- بعد توليك مهام أو مسؤوليات إضافية بشكل غير رسمي\n\n"
                "**كيف تحضّر لطلب الترقية؟**\n"
                "1. **وثّق إنجازاتك:** أرقام، مشاريع، توفير للتكاليف، تأثير على الفريق\n"
                "2. **ابحث في السوق:** ما هو الراتب المعتاد لمنصب أعلى في قطاعك وشركتك؟\n"
                "3. **اطلب اجتماعاً خاصاً:** لا تطلب الترقية في اجتماع عام\n"
                "4. **ركّز على القيمة التي ستضيفها** في المنصب الأعلى، لا على احتياجاتك الشخصية\n\n"
                "**ماذا تقول؟**\n"
                "«أودّ مناقشة مساري الوظيفي. خلال الـ 12 شهراً الماضية حققت [X]، وأرى أنني مستعد "
                "لتحمّل مسؤولية [Y]. أودّ معرفة رأيك في إمكانية الترقية.»\n\n"
                "**نصيحة:** إذا رُفض طلبك، اسأل عن الخطوات المحددة لتحقيق الترقية مستقبلاً."
            )
        else:
            msg = (
                "## How to Ask for a Promotion in UAE\n\n"
                "**When is the right time?**\n"
                "- After delivering a significant project or measurable result\n"
                "- During or ahead of your annual performance review\n"
                "- After you've been informally doing work above your current level\n\n"
                "**How to prepare:**\n"
                "1. **Document your achievements** — numbers, projects delivered, "
                "cost savings, revenue generated, team impact\n"
                "2. **Research the market** — know what the next level pays in your "
                "sector so you can frame a salary expectation if asked\n"
                "3. **Request a private meeting** — never ask during a group meeting or casually\n"
                "4. **Frame it around value, not personal need** — 'I believe I'm ready "
                "to contribute more as [title]' beats 'I need more money'\n\n"
                "**What to say:**\n"
                "> *'I'd like to discuss my career progression. Over the past year I've "
                "[achievements]. I'd love to understand what a path to [next role] "
                "looks like, and whether you see me as ready.'*\n\n"
                "**If the answer is no:**\n"
                "- Ask: 'What specific milestones would make me ready?' "
                "— this turns a rejection into a roadmap\n"
                "- Set a follow-up date (3–6 months)\n\n"
                "**UAE context:** Promotions in UAE often happen at year-end or during "
                "budget cycles (typically Q4 or Q1). Build the case early."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "promotion_uae", "message": msg}

    # ── Handling job rejection ────────────────────────────────────────────────────

    def _handle_job_rejection(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## كيف تتعامل مع رفض طلب التوظيف؟\n\n"
                "**أولاً: لا بأس — الرفض جزء طبيعي من البحث عن عمل**\n"
                "- غالبية المتقدمين الناجحين تعرضوا لرفض عشرات المرات قبل الحصول على وظيفتهم\n"
                "- الرفض لا يعني أنك لست مؤهلاً، بل أحياناً يعني أنك لم تتوافق مع هذه الفرصة تحديداً\n\n"
                "**هل تطلب تغذية راجعة (Feedback)?**\n"
                "- نعم، يمكنك أن تطلب بأدب: «شكراً لإخباري. هل بإمكانك مشاركتي أي تغذية راجعة "
                "قد تساعدني في الفرص القادمة؟»\n"
                "- ليس كل مُعيِّن سيرد، لكن حين يردون فالمعلومة ثمينة\n\n"
                "**ماذا تفعل بعد الرفض؟**\n"
                "1. راجع سيرتك الذاتية وخطاب التقديم\n"
                "2. فكّر في أدائك في المقابلة — ما الذي يمكن تحسينه؟\n"
                "3. احتفظ بعلاقة إيجابية مع المُعيِّن (قد تنشأ فرص مستقبلية)\n"
                "4. لا تنسحب عاطفياً — تابع باقي طلباتك فوراً\n\n"
                "**نصيحة:** أفضل رد على الرفض هو التقدم لوظيفة أخرى في اليوم التالي."
            )
        else:
            msg = (
                "## How to Handle a Job Rejection\n\n"
                "**First: it's normal — rejection is part of the process**\n"
                "- Most successful professionals received dozens of rejections before landing their role\n"
                "- A rejection often means the role wasn't the right fit, not that you're unqualified\n\n"
                "**Should you ask for feedback?**\n"
                "- Yes — send a polite reply: *'Thank you for letting me know. Would you be able "
                "to share any feedback that might help me for future opportunities?'*\n"
                "- Not everyone responds, but when they do, the insight is valuable\n\n"
                "**What to do after a rejection:**\n"
                "1. **Review** your CV, cover letter, and interview performance\n"
                "2. **Stay professional** — the recruiter may think of you for another role\n"
                "3. **Keep applying** — don't pause your search while waiting on any single role\n"
                "4. **Track patterns** — if you're consistently reaching interviews but not "
                "offers, focus on interview prep; if you're not getting callbacks, revise your CV\n\n"
                "**UAE context:** The UAE hiring market moves fast. Following up within "
                "24 hours of rejection — gracefully — often leaves a strong impression.\n\n"
                "**Tip:** The best response to rejection is applying for the next role "
                "the same day."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "job_rejection", "message": msg}

    # ── Counter-offer from current employer ───────────────────────────────────────

    def _handle_counter_offer(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## العرض المضاد من صاحب العمل: هل تقبله؟\n\n"
                "**ما هو العرض المضاد؟**\n"
                "- هو عرض يقدمه صاحب العمل الحالي (زيادة راتب، ترقية، مزايا) لمنعك من الرحيل\n\n"
                "**الإحصاءات المهمة:**\n"
                "- تشير الدراسات إلى أن 80% ممن يقبلون عرضاً مضاداً يغادرون الشركة خلال 6–12 شهراً\n"
                "- لأن الأسباب الحقيقية للمغادرة (البيئة، النمو، القيادة) غالباً لم تتغير\n\n"
                "**قبل اتخاذ قرارك، اسأل نفسك:**\n"
                "1. ما الذي يجعلني أريد المغادرة أصلاً؟ هل يعالج هذا العرض المشكلة الحقيقية؟\n"
                "2. هل يتغير دوري أم فقط الراتب؟\n"
                "3. ما مدى ثقتي بهذا الوعد مستقبلاً؟\n"
                "4. هل الشركة الجديدة تقدم نمواً مهنياً لا يوفره مكاني الحالي؟\n\n"
                "**نصيحة:** إذا كان السبب الوحيد للمغادرة هو الراتب، فالعرض المضاد قد يستحق النظر. "
                "أما إذا كانت المشكلة في الثقافة أو القيادة أو الفرص، فالعرض المضاد حل مؤقت."
            )
        else:
            msg = (
                "## Counter-Offer from Your Employer: Should You Accept?\n\n"
                "**What is a counter-offer?**\n"
                "- A pay rise, promotion, or benefit your current employer offers to stop "
                "you from leaving after you've received an outside job offer\n\n"
                "**The statistics:**\n"
                "- ~80% of people who accept counter-offers leave within 6–12 months anyway\n"
                "- The root reasons for wanting to leave (culture, growth, leadership) "
                "typically haven't changed\n\n"
                "**Before deciding, ask yourself:**\n"
                "1. Why did I want to leave in the first place — and does this counter-offer "
                "actually fix that?\n"
                "2. Will my role, responsibilities, or growth prospects genuinely change?\n"
                "3. Was I only being valued when I threatened to leave — what does that say?\n"
                "4. Does the new company offer something (learning, culture, career trajectory) "
                "that money alone can't replicate?\n\n"
                "**When a counter-offer might make sense:**\n"
                "- You were primarily motivated by salary, and the counter-offer matches or "
                "beats the new offer\n"
                "- The employer also addresses the non-financial issue (role expansion, title, team)\n\n"
                "**When to decline:**\n"
                "- The only thing changing is your salary\n"
                "- The trust dynamic is already broken\n"
                "- You've been considering the move for a long time for reasons beyond pay"
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "counter_offer", "message": msg}

    # ── Relocation package ────────────────────────────────────────────────────────

    def _handle_relocation_package(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "## حزمة الانتقال إلى الإمارات: ماذا تتوقع وما الذي تطلبه؟\n\n"
                "**ما الذي تشمله حزمة الانتقال عادةً في الإمارات؟**\n"
                "- تذاكر طيران للانتقال (للموظف وأسرته في بعض الأحيان)\n"
                "- بدل سكن مؤقت (1–3 أشهر فندق أو شقة فندقية)\n"
                "- بدل شحن الأغراض الشخصية (المتعلقات)\n"
                "- مساعدة في استخراج التأشيرة والإقامة\n"
                "- بدل سفر للعودة إلى الوطن مرة واحدة سنوياً (خاصة في القطاعات الكبيرة)\n\n"
                "**عناصر أقل شيوعاً لكن يمكن التفاوض عليها:**\n"
                "- بدل الإسكان الشهري (Housing Allowance) بدلاً من المساعدة الأولية فقط\n"
                "- بدل التعليم للأطفال\n"
                "- بدل السيارة\n"
                "- إجازة الاستكشاف قبل الانضمام\n\n"
                "**نصيحة:** تفاوض على حزمة الانتقال كجزء من مفاوضات العرض — وليس بعد القبول. "
                "وثّق كل ما تم الاتفاق عليه كتابياً في عقد العمل."
            )
        else:
            msg = (
                "## UAE Relocation Package: What to Expect and What to Ask For\n\n"
                "**Typical relocation package components in UAE:**\n"
                "- **Flight tickets** to UAE (for employee + family in senior roles)\n"
                "- **Temporary accommodation** — 1–3 months in a serviced apartment or hotel\n"
                "- **Shipping allowance** for personal belongings\n"
                "- **Visa processing fees** covered by employer\n"
                "- **Annual flight ticket home** (very common in UAE, especially in large companies)\n\n"
                "**Less common but negotiable:**\n"
                "- **Housing allowance** — monthly contribution to rent (often AED 30,000–80,000+ "
                "per year for mid-to-senior roles)\n"
                "- **School fees** for children\n"
                "- **Car allowance** or company car\n"
                "- **'Look-see' trip** — a visit to UAE before accepting to find accommodation\n"
                "- **Settling-in allowance** — lump sum for initial setup\n\n"
                "**Negotiation tips:**\n"
                "- Raise the relocation package during offer negotiation, not after accepting\n"
                "- Get every commitment in writing in the offer letter or employment contract\n"
                "- Compare: a higher base salary is sometimes better than an allowance "
                "(allowances may not count for gratuity calculations)\n\n"
                "**Tip:** If the employer won't provide a package, ask them to cover "
                "just the visa fees and flight — it's a reasonable minimum ask."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "relocation_package", "message": msg}

    # ── UAE public holidays ───────────────────────────────────────────────────────

    def _handle_public_holidays_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "🗓️ **الإجازات الرسمية في الإمارات**\n\n"
                "**إجازات ثابتة:**\n"
                "• رأس السنة الميلادية — 1 يناير\n"
                "• يوم الشهيد (الوطني للشهداء) — 30 نوفمبر\n"
                "• اليوم الوطني الإماراتي — 2-3 ديسمبر\n\n"
                "**إجازات إسلامية (تتغير كل عام بحسب الرؤية الشرعية):**\n"
                "• اليوم الأول من رمضان\n"
                "• عيد الفطر — 3 أيام\n"
                "• يوم عرفة + عيد الأضحى — 3 أيام\n"
                "• رأس السنة الهجرية\n"
                "• المولد النبوي الشريف\n"
                "• الإسراء والمعراج\n\n"
                "يُحدد المجلس الوزاري مواعيد الإجازات الإسلامية رسمياً قُبيل موعدها. "
                "خلال رمضان تُقلَّص ساعات العمل بمقدار ساعتين يومياً بموجب قانون العمل."
            )
        else:
            msg = (
                "🗓️ **UAE Public Holidays**\n\n"
                "**Fixed holidays:**\n"
                "• New Year's Day — 1 January\n"
                "• Commemoration Day (Martyr's Day) — 30 November\n"
                "• UAE National Day — 2–3 December\n\n"
                "**Islamic holidays (shift each year with the lunar calendar):**\n"
                "• First day of Ramadan\n"
                "• Eid Al Fitr — 3 days\n"
                "• Arafat Day + Eid Al Adha — 3 days\n"
                "• Islamic New Year\n"
                "• Prophet's Birthday\n"
                "• Lailat Al Mi'raj (Ascension)\n\n"
                "The UAE Cabinet officially announces Islamic holiday dates a few weeks before they occur. "
                "Private-sector employees are entitled to all public holidays at full pay. "
                "During Ramadan, working hours are legally reduced by 2 hours per day. "
                "If a public holiday falls on a weekend, most employers grant a compensatory day off."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "public_holidays_uae", "message": msg}

    # ── Overtime pay UAE ───────────────────────────────────────────────────────────

    def _handle_overtime_pay_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "⏰ **الوقت الإضافي في الإمارات (قانون العمل الاتحادي)**\n\n"
                "**ساعات العمل القياسية:**\n"
                "• 8 ساعات يومياً أو 48 ساعة أسبوعياً\n"
                "• خلال رمضان: 6 ساعات يومياً فقط\n\n"
                "**معدلات الوقت الإضافي (المواد 65-68):**\n"
                "• وقت إضافي نهاري: الراتب العادي + **25%**\n"
                "• وقت إضافي ليلي (9 مساءً – 4 صباحاً): الراتب العادي + **50%**\n"
                "• العمل في يوم الراحة: راتب يوم كامل + **50% إضافي**\n\n"
                "**الحد الأقصى:** ساعتان إضافيتان في اليوم إلا في حالات استثنائية.\n\n"
                "⚠️ قد تُستثنى المناصب الإدارية العليا من هذه الأحكام. "
                "في حال رفض صاحب العمل صرف الوقت الإضافي، يمكنك تقديم شكوى عبر وزارة الموارد البشرية (MOHRE) على الرقم 800-60."
            )
        else:
            msg = (
                "⏰ **Overtime Pay in UAE (Federal Labour Law)**\n\n"
                "**Standard working hours:**\n"
                "• Max 8 hours/day or 48 hours/week\n"
                "• Reduced to 6 hours/day during Ramadan\n\n"
                "**Overtime rates (Articles 65–68):**\n"
                "• Daytime overtime: normal hourly rate + **25%**\n"
                "• Night-time overtime (9 pm – 4 am): normal hourly rate + **50%**\n"
                "• Work on official day off: full basic day's pay + **50% premium**\n\n"
                "**Maximum overtime:** 2 hours per day unless exceptional circumstances apply.\n\n"
                "⚠️ Senior managers and supervisors may be exempt from overtime entitlement depending on contract terms. "
                "If your employer refuses to pay overtime owed, file a complaint with MOHRE at mohre.gov.ae or call 800-60."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "overtime_pay_uae", "message": msg}

    # ── Contract types UAE ────────────────────────────────────────────────────────

    def _handle_contract_types_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "📄 **أنواع عقود العمل في الإمارات**\n\n"
                "**تحديث مهم (2022):** ألغى قانون العمل الجديد (المرسوم الاتحادي رقم 33 لسنة 2021) "
                "التمييز التقليدي بين العقود المحددة وغير المحددة المدة. "
                "جميع العقود الجديدة محددة المدة (لا تتجاوز 3 سنوات، قابلة للتجديد).\n\n"
                "**أنواع العقود الحالية:**\n"
                "• **عقد بدوام كامل** — الأكثر شيوعاً، قابل للتجديد\n"
                "• **عقد بدوام جزئي** — أقل من 8 ساعات يومياً، يُتيح العمل لدى أكثر من جهة\n"
                "• **عقد مشروع** — ينتهي عند اكتمال المشروع\n"
                "• **عقد مرن** — ساعات متغيرة بالاتفاق\n"
                "• **عقد موسمي** — لنشاطات ومواسم محددة\n\n"
                "**ماذا يحدث عند انتهاء العقد؟**\n"
                "• إذا استمررت في العمل دون تجديد رسمي، يُعدّ العقد مجدَّداً ضمنياً بنفس الشروط\n"
                "• يجب على صاحب العمل إخطارك بعدم التجديد قبل 30 يوماً على الأقل\n"
                "• تستحق مكافأة نهاية الخدمة بناءً على إجمالي سنوات الخدمة بغض النظر عن نوع الإنهاء\n\n"
                "💡 احرص على توقيع عقدك باللغتين العربية والإنجليزية. النسخة العربية هي المعتمدة قانونياً."
            )
        else:
            msg = (
                "📄 **Employment Contract Types in UAE**\n\n"
                "**Key update (2022):** The new UAE Labour Law (Federal Decree No. 33 of 2021) eliminated the old limited/unlimited contract distinction. "
                "All new contracts must now be **fixed-term** (maximum 3 years, renewable).\n\n"
                "**Current contract types:**\n"
                "• **Full-time** — renewable fixed-term, most common\n"
                "• **Part-time** — fewer than 8 hours/day; working for multiple employers is permitted\n"
                "• **Project-based** — ends when the specific project completes\n"
                "• **Flexible** — hours vary by mutual agreement\n"
                "• **Seasonal** — tied to a specific season or activity\n\n"
                "**What happens when a fixed-term contract expires?**\n"
                "• If you keep working without a new signed contract, it's treated as implicitly renewed on the same terms\n"
                "• Your employer must give at least **30 days' notice** of non-renewal\n"
                "• You're entitled to end-of-service gratuity based on total years served regardless of how the contract ends\n\n"
                "💡 Always insist on a written contract in both Arabic and English. The Arabic version is legally binding in UAE courts."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "contract_types_uae", "message": msg}

    # ── Multiple job offers ───────────────────────────────────────────────────────

    def _handle_multiple_offers(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "⚖️ **كيف تختار بين عرضين وظيفيين؟**\n\n"
                "**اقارن هذه العوامل الستة:**\n\n"
                "1. **الراتب الإجمالي** — لا تقارن الأساسي فقط؛ احسب بدل الإسكان والمواصلات والمكافآت\n"
                "2. **مسار النمو الوظيفي** — أيهما يفتح أمامك آفاقاً أوسع بعد 3 سنوات؟\n"
                "3. **الاستقرار الوظيفي** — ما أوضاع الشركتين ماليًا؟ هل هناك أخبار عن تسريح؟\n"
                "4. **ثقافة العمل** — من قابلت أثناء المقابلة؟ هل شعرت بالانتماء؟\n"
                "5. **المرونة وبيئة العمل** — عن بُعد / هجين / مكتب؟ ساعات عمل؟\n"
                "6. **الحزمة الكاملة** — تأمين صحي، إجازات، فرص تدريب، بدل تأشيرة\n\n"
                "**نصيحة عملية:** إذا كنت تميل لعرض بمرتب أقل، تفاوض مع الطرف الأعلى أجراً على مزايا غير مالية — وبالعكس.\n\n"
                "⏰ إذا كنت بحاجة إلى وقت إضافي للتفكير، اطلب من الشركة مهلة لا تتجاوز 3–5 أيام عمل."
            )
        else:
            msg = (
                "⚖️ **How to Choose Between Two Job Offers**\n\n"
                "**Compare these 6 factors side by side:**\n\n"
                "1. **Total compensation** — Don't just compare base salary; add housing/transport allowances, bonuses, and equity\n"
                "2. **Career growth** — Which role puts you in a better position in 3 years?\n"
                "3. **Company stability** — Research both companies' financials, recent news, and growth trajectory\n"
                "4. **Culture fit** — Who did you meet during interviews? Did the team feel right?\n"
                "5. **Flexibility & environment** — Remote / hybrid / in-office? Working hours? Commute?\n"
                "6. **Full benefits package** — Health insurance, leave days, visa sponsorship, training budget\n\n"
                "**Practical tip:** If you prefer the lower-paying offer, use the higher-paying one as leverage to negotiate better terms. "
                "If you prefer the higher-paying one, ask the other company if they can match it.\n\n"
                "⏰ If you need more time, it's perfectly professional to ask for a 3–5 business day extension — "
                "most UAE employers expect this. Don't feel pressured to decide on the spot."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "multiple_offers", "message": msg}

    # ── Workplace harassment UAE ──────────────────────────────────────────────────

    def _handle_workplace_harassment(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "🛡️ **التحرش والتمييز في بيئة العمل — حقوقك في الإمارات**\n\n"
                "**هل يحمي القانون الإماراتي من التحرش؟**\n"
                "نعم. تُجرِّم المادة (14) من قانون العمل الاتحادي رقم 33 لسنة 2021 والمرسوم الوزاري 43 لسنة 2022 "
                "التحرش والتنمر والتمييز في بيئة العمل وتُلزم صاحب العمل بتوفير بيئة عمل آمنة.\n\n"
                "**خطوات الإبلاغ:**\n"
                "1. **وثّق كل شيء** — احتفظ بالرسائل والبريد الإلكتروني والملاحظات المُتاريخة\n"
                "2. **أبلغ قسم الموارد البشرية** كتابياً واحتفظ بنسخة من البلاغ\n"
                "3. **إذا لم يُتخذ إجراء** — قدّم شكوى إلى وزارة الموارد البشرية والتوطين (MOHRE):\n"
                "   • الخط الساخن: 800-60\n"
                "   • الموقع: mohre.gov.ae\n"
                "   • تطبيق MOHRE للهاتف المحمول\n"
                "4. **للتحرش الجنسي** — يمكنك التقدم مباشرة إلى الشرطة أو النيابة العامة\n\n"
                "⚠️ لا يجوز لصاحب العمل فصلك بسبب تقديم شكوى — يُعدّ ذلك فصلاً تعسفياً ويُعطيك الحق في تعويض."
            )
        else:
            msg = (
                "🛡️ **Workplace Harassment & Discrimination in UAE**\n\n"
                "**Is workplace harassment illegal in UAE?**\n"
                "Yes. Article 14 of the UAE Labour Law (Federal Decree No. 33 of 2021) and Ministerial Resolution No. 43 of 2022 "
                "explicitly prohibit harassment, bullying, and discrimination in the workplace. Employers are required to provide a safe working environment.\n\n"
                "**Steps to take:**\n"
                "1. **Document everything** — keep dated records of messages, emails, and incidents\n"
                "2. **Report to HR in writing** — email is best; keep a copy\n"
                "3. **If no action is taken** — file a complaint with MOHRE (Ministry of Human Resources & Emiratisation):\n"
                "   • Hotline: 800-60\n"
                "   • Website: mohre.gov.ae\n"
                "   • MOHRE mobile app\n"
                "4. **For sexual harassment** — you can report directly to the police or public prosecution\n\n"
                "⚠️ Your employer cannot legally terminate you for making a complaint — that would constitute wrongful dismissal and entitle you to additional compensation. "
                "You may also be able to terminate your own contract without notice and still claim full EOSB if harassment is proven."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "workplace_harassment", "message": msg}

    # ── Redundancy / layoff UAE ───────────────────────────────────────────────────

    def _handle_redundancy_uae(self, user_id: str, profile: Any, message: str) -> dict[str, Any]:
        arabic = self._is_arabic_text(message)
        if arabic:
            msg = (
                "📋 **حقوقك عند الاستغناء عن خدماتك أو الفصل الجماعي في الإمارات**\n\n"
                "**ما الذي تستحقه قانوناً عند الاستغناء عن خدماتك؟**\n"
                "• **مكافأة نهاية الخدمة (EOSB)** — 21 يوماً عن كل سنة خلال الخمس سنوات الأولى، ثم 30 يوماً عن كل سنة بعد ذلك\n"
                "• **مدة الإشعار** — 30 إلى 90 يوماً حسب العقد (أو التعويض المالي بدلاً منها)\n"
                "• **الراتب المتأخر والعلاوات والأيام الإضافية** — كافة المستحقات المتبقية\n"
                "• **تذكرة العودة إلى الوطن** — في حال كانت مشمولة في عقدك\n"
                "• **فترة السماح بعد إلغاء التأشيرة** — 30 يوماً للبحث عن عمل جديد\n\n"
                "**هل يمكن لصاحب العمل الاستغناء عنك دون إشعار؟**\n"
                "لا، إلا في حالات التقصير الجسيم الموثّقة. الاستغناء الاقتصادي يستلزم دفع التعويض المقابل لمدة الإشعار.\n\n"
                "**إذا رفض صاحب العمل دفع مستحقاتك:**\n"
                "تواصل مع MOHRE على 800-60 أو قدّم شكوى عبر mohre.gov.ae"
            )
        else:
            msg = (
                "📋 **Your Rights if Made Redundant / Laid Off in UAE**\n\n"
                "**What you're legally entitled to:**\n"
                "• **End-of-service gratuity (EOSB)** — 21 days' pay per year for the first 5 years, then 30 days/year thereafter\n"
                "• **Notice period** — 30–90 days per your contract (or equivalent pay in lieu of notice)\n"
                "• **All outstanding salary, bonuses, and accrued leave days**\n"
                "• **Return flight ticket home** — if stipulated in your contract\n"
                "• **30-day visa grace period** — after visa cancellation to find new employment\n\n"
                "**Can your employer make you redundant without notice?**\n"
                "No, unless for documented gross misconduct. Economic redundancy requires either working the notice period or paying in lieu.\n\n"
                "**What counts as unfair dismissal?**\n"
                "Termination without valid reason, without notice, or in retaliation for asserting your rights. "
                "You can claim compensation of up to 3 months' salary in addition to your full EOSB.\n\n"
                "**If your employer refuses to pay:**\n"
                "File a complaint with MOHRE — 800-60 | mohre.gov.ae | MOHRE mobile app."
            )
        self._append_chat(user_id, "assistant", msg)
        return {"type": "redundancy_uae", "message": msg}

    # ── Context-aware help ──────────────────────────────────────────────────────

    def _build_context_aware_help(
        self, user_id: str, profile: Any, has_cv: bool, message: str = ""
    ) -> dict[str, Any]:
        """Return a help menu personalised to the user's current profile state."""
        arabic = self._is_arabic_text(message)
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        recent_role = ""
        try:
            _rctx = self._get_recent_context(user_id)
            recent_role = str(_rctx.get("recent_search_role") or "").strip()
        except Exception:
            pass

        if not has_cv and not target_roles:
            # New / empty profile — guide them to set up first
            options = [
                {"action": "upload_cv",    "label": "Upload my CV to get started" if not arabic else "رفع سيرتي الذاتية"},
                {"action": "set_role",     "label": "Set my target job role"      if not arabic else "تحديد الوظيفة المستهدفة"},
                {"action": "find_jobs",    "label": "Search for UAE jobs"          if not arabic else "البحث عن وظائف في الإمارات"},
            ]
            intro = "مرحبًا! لنبدأ بإعداد ملفك:" if arabic else "Welcome! Let's set up your profile first:"
        elif recent_role:
            # Continuing an active search
            options = [
                {"action": "find_jobs",          "label": f"Search more {recent_role} jobs"},
                {"action": "prepare_application", "label": "Prepare application / cover letter"},
                {"action": "interview_prep",      "label": "Prepare for an interview"},
                {"action": "track_applications",  "label": "Check my applications"},
                {"action": "profile_completeness","label": "See what's missing from my profile"},
            ]
            intro = "Here is what I can help you with:"
        else:
            options = [
                {"action": "find_jobs",           "label": "Find matching UAE jobs"          if not arabic else "البحث عن وظائف تناسبني"},
                {"action": "prepare_application",  "label": "Prepare a job application"      if not arabic else "إعداد طلب توظيف"},
                {"action": "interview_prep",       "label": "Prepare for an interview"       if not arabic else "التحضير لمقابلة عمل"},
                {"action": "track_applications",   "label": "Track my applications"          if not arabic else "متابعة طلباتي"},
                {"action": "profile_completeness", "label": "Check my profile completeness"  if not arabic else "التحقق من اكتمال ملفي"},
            ]
            intro = "إليك ما يمكنني مساعدتك به:" if arabic else "Here is what I can help you with:"

        return {"type": "options", "message": intro, "options": options}

    def _handle_profile_completeness(self, user_id: str, profile: Any, message: str = "") -> dict[str, Any]:
        """Deterministic profile completeness report using evaluate_minimum_profile."""
        from src.agent.context.resolver import resolve_profile_context
        arabic = self._is_arabic_text(message)
        # Try DB-backed ProfileContext first; on failure check fields directly
        # via self._profile_value() so CI (no DB) and tests still work.
        try:
            ctx = resolve_profile_context(user_id)
            gate_ok, missing = evaluate_minimum_profile(ctx)
        except Exception:
            missing = []
            if not self._as_list(self._profile_value(profile, "target_roles")):
                missing.append("target_roles")
            if not self._as_list(self._profile_value(profile, "preferred_cities")):
                missing.append("preferred_cities")
            if self._profile_value(profile, "years_experience") is None:
                missing.append("years_experience")
            _has_skills = bool(self._as_list(self._profile_value(profile, "skills")))
            _has_cv = bool(
                self._profile_value(profile, "cv_filename")
                or self._profile_value(profile, "cv_status") == "parsed"
            )
            if not _has_skills and not _has_cv:
                missing.append("skills")
            gate_ok = len(missing) == 0
        _FIELD_LABELS: dict[str, str] = {
            "target_roles": "Target role(s)",
            "preferred_cities": "Preferred UAE city",
            "years_experience": "Years of experience",
            "skills": "Skills or CV upload",
        }
        _FIELD_LABELS_AR: dict[str, str] = {
            "target_roles": "الدور (الأدوار) المستهدف",
            "preferred_cities": "المدينة المفضلة في الإمارات",
            "years_experience": "سنوات الخبرة",
            "skills": "المهارات أو رفع السيرة الذاتية",
        }
        optional_gaps: list[str] = []
        optional_gaps_ar: list[str] = []
        if not self._as_list(self._profile_value(profile, "industries")):
            optional_gaps.append("Industry sector (improves match quality)")
            optional_gaps_ar.append("القطاع الصناعي (يحسّن جودة المطابقة)")
        if not self._profile_value(profile, "salary_expectation_aed"):
            optional_gaps.append("Salary expectation (filters out low offers)")
            optional_gaps_ar.append("الراتب المتوقع (يستثني العروض المنخفضة)")
        if not self._profile_value(profile, "telegram_username"):
            optional_gaps.append("Telegram username (enables real-time job alerts)")
            optional_gaps_ar.append("اسم مستخدم تيليجرام (يفعّل تنبيهات الوظائف الفورية)")
        if gate_ok:
            if arabic:
                parts = ["**ملفك الشخصي مكتمل لمطابقة الوظائف.**"]
                if optional_gaps_ar:
                    parts.append(
                        "\nحقول اختيارية تحسّن نتائجك:\n"
                        + "\n".join(f"• {f}" for f in optional_gaps_ar)
                    )
                parts.append("\nقل **'بحث عن وظائف'** وسأبدأ المطابقة.")
            else:
                parts = ["**Your profile is complete for job matching.**"]
                if optional_gaps:
                    parts.append(
                        "\nOptional fields that improve your results:\n"
                        + "\n".join(f"• {f}" for f in optional_gaps)
                    )
                parts.append("\nSay **'search for jobs'** and I'll start matching.")
        else:
            if arabic:
                mandatory_labels_ar = [_FIELD_LABELS_AR.get(f, f) for f in missing]
                parts = [
                    "**حقول مطلوبة ناقصة:**\n"
                    + "\n".join(f"• {l}" for l in mandatory_labels_ar)
                ]
                if optional_gaps_ar:
                    parts.append(
                        "\nكذلك ناقصة (اختيارية لكن مُوصى بها):\n"
                        + "\n".join(f"• {f}" for f in optional_gaps_ar)
                    )
                parts.append(
                    "\nيمكنك تعبئتها عبر:\n"
                    "• رفع سيرتك الذاتية — تعبّئ معظم الحقول تلقائيًا\n"
                    "• إخباري مباشرة: *'دوري المستهدف هو مدير سلامة'*"
                )
            else:
                mandatory_labels = [_FIELD_LABELS.get(f, f) for f in missing]
                parts = [
                    "**Missing required fields:**\n"
                    + "\n".join(f"• {l}" for l in mandatory_labels)
                ]
                if optional_gaps:
                    parts.append(
                        "\nAlso missing (optional but recommended):\n"
                        + "\n".join(f"• {f}" for f in optional_gaps)
                    )
                parts.append(
                    "\nYou can fill these by:\n"
                    "• Uploading your CV — auto-fills most fields\n"
                    "• Telling me directly: *'My target role is Safety Manager'*"
                )
        msg = "\n".join(parts)
        self._append_chat(user_id, "assistant", msg)
        return {
            "type": "profile_completeness",
            "message": msg,
            "complete": gate_ok,
            "missing_mandatory": missing,
            "missing_optional": optional_gaps,
        }

    def _handle_application_tracking(self, user_id: str, intent: str = "application_tracking", message: str = "") -> dict[str, Any]:
        """Route application tracking requests to the applications repository."""
        try:
            from src.repositories.applications_repo import get_all, get_stats
            apps = get_all(user_id=user_id)
            stats = get_stats(user_id=user_id)
        except Exception:
            # Fallback to legacy file-based store
            from src.applications import get_applied_jobs, get_application_stats
            apps = get_applied_jobs()
            stats = get_application_stats()

        enriched = self._enrich_applications(self._sort_applications_recent(apps))
        follow_up_needed = [a for a in enriched if a.get("needs_follow_up")]
        msg = self._build_tracking_message(enriched, stats, arabic=self._is_arabic_text(message))
        if enriched:
            latest = enriched[0]
            self._store_recent_context(
                user_id,
                self._build_recent_application_context(
                    title=latest.get("title") or "Unknown",
                    company=latest.get("company") or "Unknown",
                    status=latest.get("status") or "tracked",
                    action="application_tracking",
                    job_id=latest.get("job_id"),
                    link=latest.get("link"),
                ),
            )
        # Store lifecycle context so "list them" after a summary shows applied jobs.
        self._store_lifecycle_context(user_id, "lifecycle_show_applied")
        # Cache the enriched apps so "list them" can replay without querying migration-022 columns.
        try:
            self.memory.set_context(user_id, "cached_application_list", {
                "apps": enriched[:20],
                "stats": stats,
            })
        except Exception:
            pass
        return {
            "type": "application_status",
            "message": msg,
            "applications": enriched,
            "stats": stats,
            "follow_up_needed": follow_up_needed,
        }

    def _handle_lifecycle_query(self, user_id: str, query_type: str, message: str = "") -> dict[str, Any]:
        """Answer funnel-memory questions from user_job_context.

        Handles three Rico chat questions:
          - lifecycle_show_saved            → "show saved jobs"
          - lifecycle_show_applied          → "what jobs did I apply to?"
          - lifecycle_show_opened_not_applied → "show jobs I opened but did not apply to"
        """
        from src.repositories.user_job_context_repo import (
            get_by_status,
            get_opened_not_applied,
        )

        arabic = self._is_arabic_text(message)
        if query_type == "lifecycle_show_saved":
            rows = get_by_status(user_id, "saved")
            label = "saved"
            empty_msg = (
                "لم تحفظ أي وظائف بعد. عند حفظ وظيفة من Rico، ستظهر هنا."
                if arabic else
                "You haven't saved any jobs yet. When you save a job from Rico, it'll appear here."
            )
        elif query_type == "lifecycle_show_applied":
            rows = get_by_status(user_id, "applied")
            label = "applied"
            empty_msg = (
                "لا توجد وظائف مسجَّلة كمُقدَّمة بعد. بعد التقديم، اضغط 'تم التقديم' حتى يتابعها Rico."
                if arabic else
                "I don't have any jobs marked as applied yet. After you apply, hit 'Mark as applied' so Rico can track it."
            )
        else:  # lifecycle_show_opened_not_applied
            rows = get_opened_not_applied(user_id)
            label = "opened but not applied"
            empty_msg = (
                "لا توجد وظائف في هذه الفئة بعد — هذه وظائف ضغطت رابط التقديم لها لكن لم تُسجّلها كمُقدَّمة."
                if arabic else
                "No jobs in that bucket yet — these are jobs where you clicked the apply link but haven't marked as applied."
            )

        # Always remember the last lifecycle query so "list them" can replay it.
        self._store_lifecycle_context(user_id, query_type)

        # Fallback: if the lifecycle table returned nothing (e.g. migration 022 not yet applied),
        # try the in-memory cache written by _handle_application_tracking so "list them" after
        # an application summary still returns the correct list without needing new DB columns.
        if not rows and query_type == "lifecycle_show_applied":
            try:
                cached = self.memory.get_context(user_id, "cached_application_list") or {}
                cached_apps = cached.get("apps") or []
                if cached_apps:
                    rows = [
                        {
                            "title": a.get("title") or "",
                            "company": a.get("company") or "",
                            "apply_url": a.get("link") or a.get("apply_url") or "",
                            "source_url": a.get("source_url") or "",
                            "status": a.get("status") or "applied",
                        }
                        for a in cached_apps
                    ]
            except Exception:
                pass

        if not rows:
            return {
                "type": "lifecycle_query",
                "intent": query_type,
                "message": empty_msg,
                "jobs": [],
                "count": 0,
            }

        lines = [f"Here are your **{label}** jobs ({len(rows)}):\n"]
        for r in rows[:20]:
            title = r.get("title") or "Unknown Role"
            company = r.get("company") or "Unknown Company"
            url = r.get("apply_url") or r.get("source_url") or ""
            link_part = f" — [Apply]({url})" if url else ""
            lines.append(f"• **{title}** at {company}{link_part}")

        return {
            "type": "lifecycle_query",
            "intent": query_type,
            "message": "\n".join(lines),
            "jobs": rows[:20],
            "count": len(rows),
        }

    def _handle_profile_role_suggestions(self, profile: Any, message: str = "") -> dict[str, Any]:
        """Generate deterministic role suggestions based on CV skills/certifications.

        Fast path: no OpenAI, no job search, just profile data → role mapping.
        """
        arabic = self._is_arabic_text(message)
        if not profile:
            return {
                "type": "profile_role_suggestions",
                "message": (
                    "أحتاج إلى سيرتك الذاتية أو بيانات ملفك الشخصي لاقتراح أدوار. ارفع سيرتك الذاتية أولاً."
                    if arabic else
                    "I need your CV or profile data to suggest roles. Upload your CV first."
                ),
                "options": [],
                "next_action": "upload_cv"
            }

        # Extract profile data
        skills = self._as_list(self._profile_value(profile, "skills"))
        certifications = self._as_list(self._profile_value(profile, "certifications"))
        years_experience = self._profile_value(profile, "years_experience")
        industries = self._as_list(self._profile_value(profile, "industries"))
        current_role = self._profile_value(profile, "current_role")

        suggestions = self._generate_role_suggestions(
            skills, certifications, years_experience, industries, current_role
        )

        if not suggestions:
            # Weak/empty profile — prompt user to add skills or upload CV
            return {
                "type": "profile_role_suggestions",
                "message": (
                    (
                        "أحتاج إلى مزيد من المعلومات لاقتراح الأدوار المناسبة لك. "
                        "أضف مهاراتك أو ارفع سيرتك الذاتية للبدء."
                    ) if arabic else (
                        "I need a bit more information to suggest the right roles for you. "
                        "Add your skills or upload your CV to get started."
                    )
                ),
                "options": [],
                "next_action": "add_skills",
            }

        return {
            "type": "profile_role_suggestions",
            "message": (
                (
                    f"بناءً على سيرتك الذاتية، هذه {len(suggestions)} أدوار تطابق خلفيتك. "
                    "اختر واحدًا لبدء البحث:"
                ) if arabic else (
                    f"Based on your CV, here are {len(suggestions)} roles that match your background. "
                    "Choose one to start searching:"
                )
            ),
            "options": suggestions,
            "next_action": "select_role_to_search",
        }

    def _handle_no_results_recovery(
        self,
        user_id: str,
        profile: Any,
        searched_roles: list[str],
        message: str = "",
    ) -> dict[str, Any]:
        """Return structured role-broadening options when live search returns no matches."""
        suggestions = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
            self._profile_value(profile, "current_role"),
        )
        searched_lower = {r.lower() for r in searched_roles}
        alt_options = [
            {"action": "search_role", "label": s["label"], "reason": s.get("reason", "")}
            for s in suggestions
            if s["label"].lower() not in searched_lower
        ][:5]

        if searched_roles:
            alt_options.append({
                "action": "broaden_search",
                "label": f"Broaden search for {searched_roles[0]}",
                "message": f"find {searched_roles[0]} jobs in UAE",
            })
        alt_options.append({
            "action": "show_all_suggestions",
            "label": "Show more roles from my CV",
            "message": "show roles from my cv",
        })

        arabic = self._is_arabic_text(message)
        searched_label = ", ".join(searched_roles[:2]) if searched_roles else (
            "دورك المستهدف" if arabic else "your target role"
        )
        return {
            "type": "no_results_recovery",
            "message": (
                (
                    f"لا توجد وظائف فعلية في الإمارات حاليًا لـ **{searched_label}**. "
                    "هذه أدوار ذات صلة من سيرتك الذاتية قد تحتوي على فرص نشطة:"
                ) if arabic else (
                    f"No live UAE matches found for **{searched_label}** right now. "
                    "Here are related roles from your CV that may have active openings:"
                )
            ),
            "options": alt_options,
            "next_action": "select_role_to_search",
        }

    def _generate_role_suggestions(
        self,
        skills: list[str],
        certifications: list[str],
        years_experience: float | None,
        industries: list[str],
        current_role: str | None = None,
    ) -> list[dict[str, str]]:
        """Delegate to the standalone role suggester and adapt to label-keyed list."""
        result = _suggest_roles(
            skills=skills,
            certifications=certifications,
            years_experience=years_experience,
            industries=industries,
            current_role=current_role,
        )
        return [
            {"action": r["title"], "label": r["title"], "reason": r.get("reason", "")}
            for r in result.get("roles", [])
        ]

    def _multi_role_search_response(
        self, user_id: str, roles: list[str], profile: Any,
        excluded_roles: list[str] | None = None,
        location: str = "", employment_type_filter: str = "",
    ) -> dict[str, Any]:
        """Handle a multi-role search request (e.g. "search for A, B and C roles").

        Recognises every requested role, persists the recognised list + the
        "do not search …" exclusion guard for this session, then searches the
        primary (first) role immediately and offers the remaining roles as
        one-tap alternatives so the user can re-prioritise. JSearch accepts one
        role per query, so the rest are queued rather than fanned out in a single
        turn — this satisfies both "search sequentially" and "ask which to
        prioritise" without an extra round-trip before the first results.
        """
        excluded_roles = [r for r in (excluded_roles or []) if r]
        roles = [r for r in roles if r]
        if not roles:
            # Defensive: should never happen (caller gates on roles), but never
            # fall through to an unknown-role error for an empty list.
            return self._classified_role_search(
                user_id, "", profile,
                location=location, employment_type_filter=employment_type_filter,
            )

        primary = roles[0]
        alternates = roles[1:]

        # Persist recognised roles + exclusion guard so a follow-up selection
        # searches directly (bypassing taxonomy rejection) and so future searches
        # this session can honour the "do not search …" constraint.
        try:
            ctx = self._get_recent_context(user_id)
            ctx["multi_role_candidates"] = roles
            ctx["excluded_roles"] = excluded_roles
            ctx["recent_search_role"] = primary
            self._store_recent_context(user_id, ctx)
        except Exception:
            pass

        response = self._target_role_search_response(
            user_id, primary, profile,
            location=location, employment_type_filter=employment_type_filter,
        )

        # Prepend a recognition line so the user can see every role was understood
        # (not rejected), then surface the alternates as quick re-prioritise options.
        recognised = ", ".join(roles)
        preamble = (
            f"I recognised {len(roles)} target roles: {recognised}."
        )
        if excluded_roles:
            preamble += (
                f" I'll keep out {', '.join(excluded_roles)} unless you ask for coding jobs."
            )
        if alternates:
            preamble += (
                f" Starting with **{primary}** — tap another role below to prioritise it instead."
            )
        else:
            preamble += f" Searching **{primary}**."

        base_msg = (response.get("message") or "").strip()
        response["message"] = f"{preamble}\n\n{base_msg}".strip() if base_msg else preamble
        response["recognized_roles"] = roles
        response["excluded_roles"] = excluded_roles
        response["primary_role"] = primary

        if alternates:
            alt_options = [{"action": r, "label": f"Search {r}"} for r in alternates]
            existing_options = response.get("options") or []
            response["options"] = alt_options + existing_options
            response.setdefault("next_action", "select_role_to_search")

        # Note: _target_role_search_response already recorded the assistant turn;
        # do not append again here or the turn is duplicated in chat history.
        return response

    # Occupational head-nouns that mark a phrase as a real job title even when it
    # is absent from the taxonomy. Mirrors the leniency of multi-role parsing so a
    # single explicit title like "Technical Product Owner" is searched, not bounced.
    _ROLE_HEAD_NOUNS = frozenset({
        "owner", "manager", "director", "officer", "lead", "specialist",
        "consultant", "advisor", "adviser", "coordinator", "executive", "head",
        "analyst", "engineer", "associate", "president", "architect", "designer",
        "developer", "administrator", "supervisor", "controller", "planner",
        "strategist", "scientist", "technician", "representative", "auditor",
        "accountant", "partner", "agent", "buyer", "surveyor", "estimator",
        "recruiter", "nurse", "teacher", "trainer", "chef", "pilot", "secretary",
        "generalist", "expert", "principal",
    })
    # Prose/filler words that never sit inside a real job title — their presence
    # means the phrase is not an explicit role (mirrors the multi-role guard).
    _NON_TITLE_WORDS = frozenset({
        "my", "your", "our", "their", "his", "her", "me", "i", "we", "you",
        "cv", "resume", "profile", "experience", "that", "which", "match",
        "matching", "based", "jobs", "job", "roles", "role", "position",
        "positions", "please", "kindly", "anything", "something", "best",
    })

    def _is_explicit_job_title(self, role_text: str) -> bool:
        """True when *role_text* is a plausible multi-word job title ending in a
        known occupational noun (e.g. "Technical Product Owner").

        Lets a single explicit title be searched directly instead of being bounced
        as "I do not recognize ...", matching how multi-role parsing already
        accepts the same titles — while still rejecting bare domain words like
        "software" or prose like "my cv".
        """
        words = [w.strip(".,!?;:").lower() for w in (role_text or "").split()]
        words = [w for w in words if w]
        if not (2 <= len(words) <= 5):
            return False
        if any(w in self._NON_TITLE_WORDS for w in words):
            return False
        if any(ch.isdigit() for w in words for ch in w):
            return False
        return words[-1] in self._ROLE_HEAD_NOUNS

    def _classified_role_search(
        self, user_id: str, role_text: str, profile: Any,
        location: str = "", employment_type_filter: str = "",
    ) -> dict[str, Any]:
        """Use 3-tier role classifier before searching.

        - profile_relevant → search directly
        - known_but_off_profile → ask confirmation
        - unknown → clarify / redirect

        Roles that Rico itself suggested (from role_suggester) are treated as
        profile_relevant without running them through the taxonomy classifier,
        because they are already derived from the user's CV.
        """
        # Location guard: if role_text is just a location (UAE, Dubai, etc.) redirect to
        # profile-based search rather than returning a misleading "I don't recognise X as a role".
        role_tokens = role_text.strip().lower().split()
        _loc_fillers = {"jobs", "job", "roles", "role", "in", "the", "a", "an", "for"}
        if role_tokens and all(t in _LOCATION_TERMS or t in _loc_fillers for t in role_tokens):
            # A location-only "role" means a profile-based search (e.g. "find UAE
            # jobs that match my profile" extracts "UAE" as the role). Resolve the
            # profile role properly — never blindly search saved target_roles[0].
            _lg_role, _lg_candidates, _lg_status = self._resolve_profile_search_role(profile)
            if _lg_status == "ambiguous":
                _lg_choice = self._profile_role_choice_response(_lg_candidates, role_text)
                self._append_chat(user_id, "assistant", _lg_choice["message"])
                return _lg_choice
            if _lg_status == "stale":
                _lg_sugg = self._handle_profile_role_suggestions(profile, role_text)
                if _lg_role:
                    _lg_sugg = {**_lg_sugg, "stale_target_role": _lg_role}
                self._append_chat(user_id, "assistant", _lg_sugg.get("message", ""))
                return _lg_sugg
            if _lg_status == "single":
                return self._target_role_search_response(
                    user_id, _lg_role, profile,
                    location=location, employment_type_filter=employment_type_filter,
                )
            response = {
                "type": "clarification",
                "message": (
                    f"I can search for jobs in the UAE. "
                    "What role are you looking for? (e.g. HSE Manager, Project Engineer, Finance Analyst)"
                ),
                "options": [{"action": "upload_cv", "label": "Upload CV to auto-detect role"}],
            }
            self._append_chat(user_id, "assistant", response["message"])
            return response

        # Self-reference guard: "my target role / my saved role / دوري المستهدف" etc.
        # Resolve to the user's saved profile roles instead of treating the phrase as a job title.
        if RicoChatAPI._SELF_REF_ROLE_RE.match(role_text.strip()):
            saved_roles = self._as_list(self._profile_value(profile, "target_roles"))
            if not saved_roles:
                response = {
                    "type": "clarification",
                    "message": (
                        "I don't have a saved target role on your profile yet. "
                        "Tell me your target role (e.g. 'HSE Manager') or upload your CV and I'll set it for you."
                    ),
                }
                self._append_chat(user_id, "assistant", response["message"])
                return response
            return self._target_role_search_response(
                user_id, str(saved_roles[0]), profile, from_saved_profile=True,
                location=location, employment_type_filter=employment_type_filter,
            )

        from rapidfuzz import fuzz as _fuzz

        # Roles already in the user's target_roles are always profile_relevant.
        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        role_lower = role_text.strip().lower()

        # Multi-role list candidates from a prior "search for A, B and C" turn are
        # explicit user-requested roles — when the user later taps/repeats one of
        # them, search directly without taxonomy gating so it is never bounced back
        # as "I do not recognize '<role>'".
        try:
            _mrc = {
                str(r).strip().lower()
                for r in (self._get_recent_context(user_id).get("multi_role_candidates") or [])
            }
            if role_lower in _mrc:
                return self._target_role_search_response(
                    user_id, role_text.strip(), profile,
                    location=location, employment_type_filter=employment_type_filter,
                )
        except Exception:
            pass

        if self._is_broad_manager_role(role_text):
            return self._broad_manager_clarification(user_id)

        for tr in target_roles:
            if _fuzz.ratio(role_lower, str(tr).lower()) >= 70:
                return self._target_role_search_response(
                    user_id, role_text.strip(), profile,
                    location=location, employment_type_filter=employment_type_filter,
                )

        # Rico's own suggestions are always profile_relevant — they came from the CV.
        suggested = self._generate_role_suggestions(
            self._as_list(self._profile_value(profile, "skills")),
            self._as_list(self._profile_value(profile, "certifications")),
            self._profile_value(profile, "years_experience"),
            self._as_list(self._profile_value(profile, "industries")),
            self._profile_value(profile, "current_role"),
        )
        suggested_lower = {s["label"].lower() for s in suggested}
        if role_lower in suggested_lower:
            return self._target_role_search_response(
                user_id, role_text.strip(), profile,
                location=location, employment_type_filter=employment_type_filter,
            )

        classification, canonical_role = classify_role_candidate(role_text, profile)

        if classification == "profile_relevant" and canonical_role:
            return self._target_role_search_response(
                user_id, canonical_role, profile,
                location=location, employment_type_filter=employment_type_filter,
            )

        if classification == "known_but_off_profile" and canonical_role:
            response = {
                "type": "clarification",
                "message": (
                    f"'{canonical_role}' is a real role, but it does not look close to your CV profile. "
                    f"Should I search for {canonical_role} jobs anyway? Reply YES or tell me a different role."
                ),
                "options": [
                    {"action": "confirm_search", "label": f"Yes, search {canonical_role}"},
                    {"action": "show_profile_roles", "label": "Show roles from my CV"},
                ],
            }
            self._append_chat(user_id, "assistant", response["message"])
            try:
                _ctx = self._get_recent_context(user_id)
                _ctx["_pending_role_confirmation"] = {"role": canonical_role}
                self._store_recent_context(user_id, _ctx)
            except Exception:
                pass
            # Arm pending search so "تمام"/"yes"/"ok" in the next turn executes the search
            # rather than producing another hollow promise or a good-luck reply.
            self._store_pending_job_search(user_id, role=canonical_role, location=location, query_type="known_but_off_profile")
            return response

        # unknown role — check if text is actually a company name from recent matches
        # before emitting the "not a job role" error. Catches "Majid Al Futtaim",
        # "ADNOC", "Etisalat" typed without "jobs at" prefix.
        try:
            _role_ctx = self._get_recent_context(user_id)
            _role_companies = {
                (m.get("company") or "").strip().lower()
                for m in (_role_ctx.get("recent_search_matches") or [])
                if m.get("company")
            }
            if not _role_companies:
                from src.repositories.user_job_context_repo import get_recent_matches as _grm
                for _dbm in _grm(user_id, limit=10, max_age_minutes=60):
                    if _dbm.get("company"):
                        _role_companies.add((_dbm["company"]).strip().lower())
            if role_lower in _role_companies:
                return self._handle_company_search(
                    user_id, profile, f"jobs at {role_text}",
                )
        except Exception:
            pass

        # Multi-role parsing accepts any plausible job title without taxonomy
        # gating; mirror that for a single explicit title so "Technical Product
        # Owner" searches directly instead of bouncing back as "I do not recognize
        # ..." and falling back to a stale saved target_role (e.g. "Developer").
        if self._is_explicit_job_title(role_text):
            return self._target_role_search_response(
                user_id, role_text.strip(), profile,
                location=location, employment_type_filter=employment_type_filter,
            )

        target_roles = self._as_list(self._profile_value(profile, "target_roles"))
        suggestion = ""
        if target_roles:
            suggestion = f" Based on your CV, I can search for: {', '.join(str(r) for r in target_roles[:3])}."
        response = {
            "type": "clarification",
            "message": (
                f"I do not recognize '{role_text}' as a job role.{suggestion} "
                "Try a specific role title, or say 'help' for options."
            ),
        }
        self._append_chat(user_id, "assistant", response["message"])
        return response

    def _get_recent_messages(self, user_id: str, limit: int = MAX_CONTEXT_MESSAGES) -> list[dict[str, str]]:
        """Get recent messages for context, respecting token limits.

        Prefers DB-backed chat history for authenticated users, falls back to memory.
        Messages are sanitized before return: only user/assistant roles are kept and
        any message whose content matches known pipeline-generated artifacts is dropped
        so generated drafts can never be fed back to the LLM as user statements.
        """
        raw: list[dict] = []
        try:
            # Try DB-backed history first (primary for authenticated users)
            from src.services.chat_service import get_chat_history
            db_messages = get_chat_history(user_id, limit=limit)
            if db_messages:
                raw = db_messages[-limit:] if len(db_messages) > limit else db_messages
        except Exception as e:
            logger.warning("Failed to get recent messages from DB, falling back to memory",
                         extra={"user_id": user_id, "error": str(e)}, exc_info=True)

        if not raw:
            # Fallback to memory store (JSON-backed local storage)
            try:
                messages = self.memory.get_chat_messages(user_id, limit=limit)
                raw = messages[-limit:] if len(messages) > limit else messages
            except Exception as e:
                logger.warning("Failed to get recent messages from memory",
                             extra={"user_id": user_id, "error": str(e)}, exc_info=True)
                return []

        return _sanitize_history_for_llm(raw)

    def _get_blocked_questions(self, profile: Any) -> list[str]:
        """Return list of question types that should not be asked based on profile data."""
        blocked = []
        if profile is None:
            return blocked

        has_cv = bool(
            self._profile_value(profile, "cv_filename")
            or self._profile_value(profile, "cv_status") == "parsed"
        )

        # Check for years_experience (explicit value or any CV upload)
        if self._profile_value(profile, "years_experience") or has_cv:
            blocked.append("experience")

        # Check for preferred_cities
        if self._profile_value(profile, "preferred_cities") or self._profile_value(profile, "cities"):
            blocked.append("location")

        # Check for skills or industries
        skills = self._profile_value(profile, "skills")
        if (skills and len(skills) > 0) or self._profile_value(profile, "industries"):
            blocked.append("industry")

        return blocked

    @staticmethod
    def _contains_blocked_question_pattern(text: str, blocked_questions: list[str]) -> bool:
        lower_text = text.lower()
        for blocked in blocked_questions:
            if blocked == "experience" and any(pattern in lower_text for pattern in [
                "experience level", "years experience", "years of experience",
                "how many years", "how much experience", "entry/mid/senior",
                "experience?", "your experience"
            ]):
                return True
            if blocked == "location" and any(pattern in lower_text for pattern in [
                "location", "city", "where", "uae city", "preferred city",
                "which city", "where are you", "where do you want"
            ]):
                return True
            if blocked == "industry" and any(pattern in lower_text for pattern in [
                "industry", "sector", "field", "which industry", "what industry"
            ]):
                return True
        return False

    def _remove_blocked_questions(self, response: str, blocked_questions: list[str]) -> str:
        """Remove lines that only ask for profile facts we already know."""
        if not response or not blocked_questions:
            return response

        filtered_lines = []
        for line in response.split("\n"):
            if self._contains_blocked_question_pattern(line, blocked_questions):
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines).strip()

    def _remove_blocked_question_sentences(self, response: str, blocked_questions: list[str]) -> str:
        """Prefer sentence-level cleanup before falling back to the raw provider reply."""
        if not response or not blocked_questions:
            return response

        fragments = re.split(r"(?<=[.!?])\s+", response.strip())
        kept_fragments = []
        for fragment in fragments:
            trimmed = fragment.strip()
            if not trimmed:
                continue
            if trimmed.endswith("?") and self._contains_blocked_question_pattern(trimmed, blocked_questions):
                continue
            kept_fragments.append(trimmed)

        return " ".join(kept_fragments).strip()

    def _preserve_ai_message(self, response: str, blocked_questions: list[str]) -> str:
        """Never discard a non-empty provider reply just because the broad filter removed it."""
        raw_message = str(response or "").strip()
        if not raw_message:
            return raw_message

        filtered_message = self._remove_blocked_questions(raw_message, blocked_questions)
        if filtered_message:
            return filtered_message

        minimally_filtered = self._remove_blocked_question_sentences(raw_message, blocked_questions)
        if minimally_filtered:
            logger.warning(
                "rico_ai_response_line_filter_empty_using_sentence_fallback blocked=%s",
                blocked_questions,
            )
            return minimally_filtered

        logger.warning(
            "rico_ai_response_filter_empty_using_raw_fallback blocked=%s",
            blocked_questions,
        )
        return raw_message

    @staticmethod
    def _build_router_context(user_id: str, profile: Any) -> dict:
        """Build the context dict passed to the intent router."""
        ctx: dict = {}
        if profile:
            try:
                ctx["profile"] = asdict(profile) if is_dataclass(profile) else dict(profile)
            except Exception as e:
                logger.warning("Failed to build router context", extra={"user_id": user_id, "error": str(e)})
        return ctx


def demo() -> None:
    """Demo function for testing the chat API."""
    api = RicoChatAPI()

    messages: list[str] = [
        "Roben_Edwan_CV.pdf here u go",
        "take it from the c.v!",
        "Please skip this question.",
        "I need HSE Manager jobs in Dubai",
        "Find jobs for me",
        "Prepare me for interview",
    ]

    for message in messages:
        print("USER:", message)
        print("RICO:")
        print(json.dumps(api.process_message("demo-user", message), indent=2))
        print("-" * 80)


if __name__ == "__main__":
    demo()

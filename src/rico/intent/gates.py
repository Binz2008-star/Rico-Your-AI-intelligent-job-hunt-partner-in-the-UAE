"""
Phase 1 open-ended question gate.

Pure lexical and punctuation signals. No taxonomy lookup, no model call.
Anything not matched here passes through to the legacy classifier unchanged.
"""
from __future__ import annotations

import re
from typing import Final

_OPENING_TOKENS: Final[frozenset[str]] = frozenset({
    "how", "what", "whats", "what's",
    "why", "when", "where", "who", "whom", "whose", "which",
    "can", "could", "should", "would",
    "explain",
})

_OPENING_PHRASES: Final[tuple[str, ...]] = (
    "do you",
    "did you",
    "are you",
    "is it",
    "tell me",
    "show me",
    "let me know",
)

# Both ASCII/fullwidth ? and Arabic question mark ؟
_QUESTION_CHARS: Final[frozenset[str]] = frozenset("?？؟")
_FIRST_TOKEN_STRIP: Final[str] = ",.!?؟;:()/&+-"
_DIRECT_JOB_REQUEST_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:show me|tell me)\s+(?:new\s+|current\s+|live\s+|some\s+|any\s+)?"
    r"(?:jobs?|roles?|openings?|positions?|vacancies?|matches?)\b"
    r"|^(?:find|find me|search|search for|get|get me|look for|looking for)\b.{0,80}\b"
    r"(?:jobs?|roles?|openings?|positions?|vacancies?|matches?)\b"
    r"|^(?:need|want)\s+(?:a\s+|an\s+|some\s+|any\s+)?(?:job|jobs|role|roles|work)\b",
    re.IGNORECASE,
)

# Carve-out: application-status questions that start with "what"/"which" or end in "?"
# must route to the legacy classifier (which calls _handle_application_tracking),
# not to the conversational AI handler which has no DB access.
_APPLICATION_STATUS_RE: Final[re.Pattern[str]] = re.compile(
    r"\bjobs?\s+i\s+(?:have\s+)?appl(?:ied|y)\b"
    r"|\bwhat\s+(?:did\s+i|have\s+i|i)\s+appl(?:ied|y)\b"
    r"|\b(?:what|which|how\s+many)\b.{0,50}\b(?:jobs?|applications?|roles?)\b.{0,30}\b(?:applied|tracked)\b"
    r"|\b(?:applied|tracked)\b.{0,30}\b(?:jobs?|applications?|roles?)\b",
    re.IGNORECASE,
)

# Carve-out: uploaded-file / My Files questions must route to the legacy
# classifier (which answers deterministically from user_documents), not to the
# conversational AI handler — the model cannot be trusted to enumerate files.
_FILE_LIST_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:my|uploaded)\s+(?:files?|documents?|docs|uploads)\b"
    r"|\b(?:what|which)\s+(?:files?|documents?)\b"
    r"|\bwhich\s+(?:cv|resume)\s+is\s+(?:the\s+)?(?:active|primary|current|main)\b"
    r"|\b(?:active|primary)\s+(?:cv|resume)\b"
    r"|ملفاتي|مستنداتي|الملفات\s+المرفوعة"
    r"|(?:الملفات|المستندات)\s+(?:اللي|التي)\s+(?:رافعه?ا|رفعته?ا|رفعها)",
    re.IGNORECASE | re.UNICODE,
)


def _is_file_list_question(text: str) -> bool:
    """Return True for My Files queries that need the DB, not the AI."""
    return bool(_FILE_LIST_RE.search(text))


# Arabic conversational starters: greetings, open-ended question words, conversational openers.
# These are pure conversational messages — always route to AI.
_ARABIC_GREETING_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:مرحب[اً]?\b|هلا?\b|هال[اً]?\b|السلام|أهل[اً]?\b|اهل[اً]?\b"
    r"|يسعد|صباح|مساء|سلام\b|هاي\b)",
    re.UNICODE,
)

# Arabic question/open-ended words (first token of message)
_ARABIC_OPENING_TOKENS: Final[frozenset[str]] = frozenset({
    "كيف", "ما", "ماذا", "لماذا", "متى", "أين", "اين", "من",
    "هل", "ممكن", "يمكن", "اشرح", "أخبرني", "اخبرني",
    "وش", "شو", "ليش", "وين", "إيش", "ايش",
})

# Arabic imperative job-search commands — keep on legacy classifier (DB access needed)
_ARABIC_JOB_REQUEST_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:ابحث|ابحثي|اعرض|اعرضي|جد\b|جيب|دور|ادور|ادوري|لقيلي|فتش|فتشي|اطلب|طلب)\b",
    re.UNICODE,
)


def _is_imperative_job_request(lowered: str) -> bool:
    """Return True for explicit search commands that should stay off the AI path."""
    return bool(_DIRECT_JOB_REQUEST_RE.search(lowered))


def _is_application_status_question(lowered: str) -> bool:
    """Return True for application-history queries that must reach the DB, not the AI."""
    return bool(_APPLICATION_STATUS_RE.search(lowered))


def _is_arabic_job_request(text: str) -> bool:
    return bool(_ARABIC_JOB_REQUEST_RE.search(text))


# Colloquial Arabic "browse the market / show me what's available" requests.
# These are genuine job-listing requests that _ARABIC_JOB_REQUEST_RE misses
# because they open with a look/show verb ("انظر", "شوف", "ورني", "اعرض") that
# is not in that anchored imperative list, or state an availability phrase
# ("المتوفر في سوق العمل", "وش المتاح من وظائف") with no imperative verb at all.
# Live-QA 2026-07-19: an authenticated user typed "انظر المتوفر بسوق العمل ..."
# and Rico returned a hollow "سأبحث الآن" promise instead of running the real
# search, because this predicate returned False and the search router never
# forced the grounded path. Detection requires BOTH a look/availability signal
# AND a job/market noun so it never fires on unrelated "look at this" chatter.
# Substring matching (not anchored) is intentional: Arabic proclitics glue
# prepositions/conjunctions to the noun ("بسوق", "بالسوق", "والوظائف"), so a
# token-anchored pattern would miss the common phrasings.
_AR_BROWSE_VERB_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:انظر|أنظر|اشوف|أشوف|نشوف|شوف|شوفي|ورني|ورّني|وريني|ورينى"
    r"|اعرض|أعرض|اعرضي|اعرضلي|فرجني|فرجيني)",
    re.UNICODE,
)
_AR_AVAILABILITY_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:المتوفر|المتوفره|المتوفرة|متوفر|متوفرة|المتاح|المتاحة|متاح|متاحة"
    r"|الموجود|الموجوده|الموجودة|موجود|المعروض|معروض)",
    re.UNICODE,
)
# Job/market nouns. Deliberately excludes bare ambiguous tokens like "شغل"
# (appears in "شغلي"/"مشغول"-adjacent chatter) and "فرصة" (generic "chance") so
# a co-occurring availability/browse signal is what actually gates a match.
_AR_JOB_MARKET_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:سوق\s*العمل|السوق|الوظائف|وظائف|وظيفة|الشواغر|شواغر)",
    re.UNICODE,
)


def _is_arabic_browse_market_request(text: str) -> bool:
    """Return True for colloquial Arabic 'show me what's in the job market' asks."""
    if not text or not _AR_JOB_MARKET_RE.search(text):
        return False
    return bool(_AR_AVAILABILITY_RE.search(text) or _AR_BROWSE_VERB_RE.search(text))


# Broader listing-request pattern: catches "show me real job listings", "can you find me
# some openings?", "do you have any PM roles?" — things _DIRECT_JOB_REQUEST_RE misses
# because they have adjectives ("real", "any", "some") between the verb and the noun.
_LISTING_REQUEST_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:show|find|get|search|list|give|have\s+you\s+got|do\s+you\s+have)\b"
    r"(?:\s+\w+){0,4}\s+(?:jobs?|roles?|openings?|positions?|vacancies?|listings?|matches?)\b"
    r"|\b(?:jobs?|roles?|openings?|positions?|listings?)\s+(?:in|for|at)\b",
    re.IGNORECASE,
)


_JOB_SEARCH_INTENTS: Final[frozenset[str]] = frozenset({
    "job_search_explicit",
    "job_search_multi_role",
    "job_search_profile_match",
})


def is_explicit_job_listing_request(message: str) -> bool:
    """Return True when message is asking to be shown actual job listings.

    Catches both imperative commands and broader conversational requests so that
    any session — public OR authenticated — can be intercepted before an AI path
    fabricates listings. The anchored regexes handle the fast common cases; for
    everything else (colloquial Gulf/Egyptian phrasing the regexes miss, e.g.
    "أبغى شغل جديد", "بدي وظيفة", "دورلي على شغل") we defer to the same
    ``classify_intent`` used by the real search router, so this predicate never
    drifts from the actual job-search classification.
    """
    lowered = (message or "").lower()
    if (
        _DIRECT_JOB_REQUEST_RE.search(lowered)
        or _LISTING_REQUEST_RE.search(lowered)
        or _ARABIC_JOB_REQUEST_RE.search(message or "")
        or _is_arabic_browse_market_request(message or "")
    ):
        return True
    # Lazy import keeps this lightweight module free of a load-time dependency on
    # the classifier (and avoids any import cycle).
    try:
        from src.agent.intelligence.intent_classifier import classify_intent
        return classify_intent(message or "").intent in _JOB_SEARCH_INTENTS
    except Exception:
        return False


def is_open_ended_question(message: str) -> tuple[bool, str]:
    """
    Decide whether a message must route to the conversational AI handler.

    Returns:
        (True, reason): route to ConversationalAIHandler
        (False, "ok"): let the legacy classifier handle it
    """

    text = (message or "").strip()
    if not text:
        return True, "empty"

    lowered = text.lower()

    if any(ch in text for ch in _QUESTION_CHARS):
        if _is_application_status_question(lowered):
            return False, "ok"
        if _is_file_list_question(text):
            return False, "ok"
        return True, "question_mark"

    if _is_imperative_job_request(lowered):
        return False, "ok"

    # Arabic greetings are short conversational openers handled by the
    # smalltalk legacy classifier — NOT open-ended questions that need AI.
    # Routing them to AI produces long verbose responses that get truncated.
    if _ARABIC_GREETING_RE.search(text):
        return False, "ok"

    # Arabic job search imperatives stay on legacy (DB needed)
    if _is_arabic_job_request(text):
        return False, "ok"

    for phrase in _OPENING_PHRASES:
        if lowered == phrase or lowered.startswith(phrase + " "):
            if _is_file_list_question(text):
                return False, "ok"
            return True, f"phrase:{phrase.replace(' ', '_')}"

    tokens = lowered.split()
    if not tokens:
        return True, "empty_after_split"

    first = tokens[0].strip(_FIRST_TOKEN_STRIP)
    if first in _OPENING_TOKENS:
        if _is_application_status_question(lowered):
            return False, "ok"
        if _is_file_list_question(text):
            return False, "ok"
        return True, f"token:{first}"

    # Arabic opening tokens (question/open-ended words)
    first_raw = text.split()[0].strip("،,.!?؟;:()/&+-") if text.split() else ""
    if first_raw in _ARABIC_OPENING_TOKENS:
        return True, f"arabic_token:{first_raw}"

    return False, "ok"

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
_LISTING_REQUEST_STRONG_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:show|find|get|search|list|give|have\s+you\s+got|do\s+you\s+have)\b"
    r"(?:\s+\w+){0,4}\s+(?:jobs?|roles?|openings?|positions?|vacancies?|listings?|matches?)\b",
    re.IGNORECASE,
)

# Weak, verb-less listing pattern ("jobs in Dubai", "roles for HSE"). No request verb,
# so it also matches inside advice/informational questions in passing — "What are the
# visa requirements for jobs in Dubai?", "How do salaries for HSE roles in the UAE
# compare to Saudi?" — misclassifying them as listing requests and routing them to the
# deterministic public CTA / legacy classifier instead of actually answering them
# (live-tested 2026-07-23: reproduced on production for exactly these phrasings).
# Only trusted as a listing request when the message doesn't otherwise look like a
# question — see _looks_like_question, which reuses the same signals as
# is_open_ended_question so the two gates never disagree about the same message.
_LISTING_REQUEST_WEAK_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:jobs?|roles?|openings?|positions?|listings?)\s+(?:in|for|at)\b",
    re.IGNORECASE,
)


_JOB_SEARCH_INTENTS: Final[frozenset[str]] = frozenset({
    "job_search_explicit",
    "job_search_multi_role",
    "job_search_profile_match",
})


# Imperative advice / explanation / comparison requests. These are genuine
# model-bound reasoning asks that carry no question mark and no interrogative
# opening token, so the question-shaped signals above miss them entirely and they
# fall through to the legacy classifier — which answers them with a canned
# template. Live-verified 2026-07-25 on production: "Give me one short tip to
# improve my CV for UAE employers" returned the "your CV on file is X" deflection,
# and "List exactly four interview questions a Dubai bank would ask a compliance
# officer" returned an Interview Preparation Guide template that injected a role
# the user never mentioned and ignored the requested count. Both are imperative,
# both are unambiguously reasoning work, neither is a structured lookup.
#
# Anchored at the start so a verb appearing mid-sentence ("I need to list my
# skills") does not flip an otherwise-structured message onto the AI path.
ADVICE_IMPERATIVE_REASON: Final[str] = "advice_imperative"

_ADVICE_IMPERATIVE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:please\s+|kindly\s+|can\s+you\s+|could\s+you\s+)?"
    r"(?:give\s+me|list|write|draft|rewrite|reword|rephrase|suggest|recommend"
    r"|compare|contrast|critique|review|improve|summarize|summarise|outline"
    r"|walk\s+me\s+through|advise|help\s+me)\b",
    re.IGNORECASE,
)


def _is_advice_imperative(text: str, lowered: str) -> bool:
    """True for imperative advice/explanation requests that must reach the model.

    Deliberately conservative: every structured carve-out wins over this check, so
    an imperative that is really a lookup ("list my files", "give me jobs in
    Dubai", "show my applications") stays on its deterministic handler. Only
    messages that survive all of those are treated as reasoning work.
    """
    if not _ADVICE_IMPERATIVE_RE.search(lowered):
        return False
    # Structured intents keep priority — never steal a deterministic lookup.
    if _is_file_list_question(text):
        return False
    if _is_application_status_question(lowered):
        return False
    if _is_imperative_job_request(lowered):
        return False
    if _LISTING_REQUEST_STRONG_RE.search(lowered) or _LISTING_REQUEST_WEAK_RE.search(lowered):
        return False
    return True


def _looks_like_question(text: str) -> bool:
    """True for the same question-shaped signals `is_open_ended_question` uses.

    Shared here so the weak listing-request pattern and the open-ended-question
    gate can never disagree about whether the same message is a question.
    """
    if not text:
        return False
    if any(ch in text for ch in _QUESTION_CHARS):
        return True
    lowered = text.lower()
    for phrase in _OPENING_PHRASES:
        if lowered == phrase or lowered.startswith(phrase + " "):
            return True
    tokens = lowered.split()
    if tokens and tokens[0].strip(_FIRST_TOKEN_STRIP) in _OPENING_TOKENS:
        return True
    return False


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
    text = (message or "").strip()
    if (
        _DIRECT_JOB_REQUEST_RE.search(lowered)
        or _LISTING_REQUEST_STRONG_RE.search(lowered)
        or _ARABIC_JOB_REQUEST_RE.search(message or "")
        or _is_arabic_browse_market_request(message or "")
    ):
        return True
    if _LISTING_REQUEST_WEAK_RE.search(lowered) and not _looks_like_question(text):
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

    # Imperative advice/explanation/comparison requests are reasoning work, not
    # lookups. Checked LAST so every structured carve-out above already returned:
    # only messages that no deterministic handler claimed can land here.
    if _is_advice_imperative(text, lowered):
        return True, ADVICE_IMPERATIVE_REASON

    return False, "ok"


def is_advice_imperative_message(message: str) -> bool:
    """True ONLY for messages newly routed to reasoning by the imperative-advice
    branch — i.e. exactly the set whose classification this change altered.

    Transport decoupling: correcting the SEMANTIC decision ("this needs the
    model") must not simultaneously change the TRANSPORT decision ("this is safe
    to stream"). ``should_stream_ai`` derives eligibility from the same gate, so
    without this predicate the semantic fix would silently divert these prompts
    onto ``call_openai_stream`` as a side effect. That path bypasses the
    whole-text post-processing in ``respond()`` (``_preserve_ai_message``
    blocked-question filtering and promise-only detection/substitution), so the
    safety pass would be skipped for exactly the traffic we just started sending
    to the model. These classes therefore stay BUFFERED here; enabling streaming
    for them is a separate, deliberate change.

    Precise by construction: a message that already qualified for any other
    reason (question mark, opening token/phrase) returns that reason instead, so
    this predicate is a guaranteed no-op for every previously-eligible message.
    """
    is_open, reason = is_open_ended_question(message)
    return is_open and reason == ADVICE_IMPERATIVE_REASON

"""Intent-routing helpers for the Rico conversational AI layer.

Split from ``src.rico_chat_api`` as part of the monolith refactor: intent-gating
predicates, acknowledgement classification, manual-track field recovery, and
UAE multi-city extraction. Every function and constant below is moved verbatim;
``src.rico_chat_api`` re-exports these names so all existing callers and test
patch targets keep resolving unchanged (deprecation wrapper).
"""

from __future__ import annotations

import re

from src.agent.intelligence.intent_classifier import _normalize_arabic
# UAE city names mentioned inline in a message (e.g. a job-search request
# "find HSE jobs in Dubai and Abu Dhabi"). Used at the minimum-profile gate to
# recover a city the user already stated so Rico never re-asks for a city that
# was already provided. Global/data-driven — no per-user special casing.
_UAE_CITY_SCAN_RE = re.compile(
    r"\b(dubai|abu\s+dhabi|sharjah|ajman|ras\s+al\s+khaimah|fujairah|"
    r"al\s+ain|umm\s+al\s+quwain|deira|bur\s+dubai|uae)\b",
    re.IGNORECASE,
)
_UAE_CITY_SCAN_AR_RE = re.compile(
    r"(دبي|أبوظبي|ابوظبي|الشارقة|عجمان|رأس\s+الخيمة|راس\s+الخيمة|"
    r"الفجيرة|أم\s+القيوين|ام\s+القيوين|العين)"
)

# Abbreviations conventionally written with a trailing dot: when a captured
# field ends with one of these and the message has a "." right after the
# capture, the dot belongs to the name ("Acme, Inc."), not the sentence.
_MANUAL_TRACK_ABBREV_DOT_RE = re.compile(
    r"\b(?:inc|ltd|co|corp|jr|sr|st)$", re.IGNORECASE
)


def _manual_track_field(match: "re.Match[str]", message: str) -> str:
    value = match.group(1).strip()
    end = match.end(1)
    if (
        end < len(message)
        and message[end] == "."
        and _MANUAL_TRACK_ABBREV_DOT_RE.search(value)
    ):
        value += "."
    return value

def _gate_is_application_data_request(message: str) -> bool:
    """Shared carve-out: does this message ask for the user's own application records?

    Delegates to ``src.rico.intent.gates`` so the intent gate and the legacy
    handler chain agree by construction — the gate decides whether the message
    reaches this module at all, and this module decides where it lands. Two
    copies of that vocabulary would drift, and a drift here is invisible: the
    message simply gets answered by the wrong handler. Imported lazily, matching
    every other gate import in this module.
    """
    from src.rico.intent.gates import is_application_data_request
    return is_application_data_request(message)


def _gate_is_file_list_question(message: str) -> bool:
    """Shared carve-out: does this message ask for the user's own uploaded files?

    Same contract as ``_gate_is_application_data_request``: the gate decides
    whether the message reaches this module, and this module decides where it
    lands. Imported lazily, matching every other gate import here.
    """
    from src.rico.intent.gates import is_file_list_question
    return is_file_list_question(message)

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

# Acknowledgements that express THANKS and can never also mean "yes, do it".
#
# Deliberately a strict subset of _ACKNOWLEDGEMENT_REPLIES. The rest of that
# map — "ok", "تمام", "sounds good", "got it", "perfect" — genuinely IS how a
# user accepts an offer Rico just made, and several call sites depend on that
# (see the pending-job-search redemption inside the acknowledgement branch).
# Gratitude is different in kind: nobody thanks Rico in order to start work, so
# a turn that is only thanks must never redeem an armed action. Praise words
# are left out on purpose — "perfect" after "shall I broaden?" is plausibly an
# acceptance, and this list is only for phrases where that reading is impossible.
# Stored as CANONICAL keys (see _acknowledgement_key): the Arabic entries are
# normalised at construction so one spelling of a word cannot be a member while
# another is not. Written here in their natural orthography for readability.
_GRATITUDE_ONLY_REPLIES: frozenset[str] = frozenset(
    _normalize_arabic(_p) for _p in {
        "thanks", "thank you", "thank you so much", "thanks a lot",
        "thank you very much", "much appreciated", "appreciate it",
        "appreciate that", "cheers",
        "ok thanks", "okay thanks", "ok thank you", "okay thank you",
        # Arabic
        "شكرا", "شكراً", "شكرا جزيلا", "شكراً جزيلاً",
    }
)
# Trailing sentiment punctuation only — never internal characters, so a phrase
# is normalised without being rewritten into a different one.
_ACK_TRAILING_PUNCT = " \t\r\n!.،؛?؟…"


def _acknowledgement_key(message: str) -> str:
    """Normalise a turn to its acknowledgement lookup key.

    Arabic runs through the same ``_normalize_arabic`` the CV-intent and
    upload-announce gates already use, so orthographic variants of one word
    collapse to one key. That matters here because the variants are not
    equally likely: ``شكرًا`` — tanween BEFORE the alef — is the standard MSA
    spelling and the one a phone keyboard produces, while the literal set held
    ``شكرا`` and ``شكراً``. Matching raw text therefore let the *correct*
    spelling, and any vocalised form such as ``شُكرًا``, slip the gratitude
    guard and spend a real provider call on a search the user never asked for.

    Normalisation is applied to the lookup key only. The raw keys of
    ``_ACKNOWLEDGEMENT_REPLIES`` are deliberately left as they are, so every
    existing exact-match call site keeps its current behaviour.
    """
    key = (message or "").strip().lower().rstrip(_ACK_TRAILING_PUNCT).strip()
    return _normalize_arabic(key)


def _is_gratitude_only(message: str) -> bool:
    """True when the whole turn is thanks and nothing else."""
    return _acknowledgement_key(message) in _GRATITUDE_ONLY_REPLIES


def _acknowledgement_reply(message: str) -> str:
    """Return a short warm reply for acknowledgement phrases."""
    key = message.strip().lower()
    return _ACKNOWLEDGEMENT_REPLIES.get(
        key, _ACKNOWLEDGEMENT_REPLIES.get(_acknowledgement_key(message), _DEFAULT_ACK_REPLY)
    )

# Multi-city detection for a single job-search request. When a user asks for
# several UAE cities at once ("Data Analyst jobs in Dubai and Sharjah"), the
# upstream single-value location extractor keeps only the first city, so Rico
# silently searched (and reported) just one. This scanner recovers every named
# city from the request text so the search covers all of them and the reply is
# honest. Global/data-driven — no city or account is special-cased.
_MULTI_CITY_SCAN_RE = re.compile(
    r"\b(dubai|abu\s+dhabi|sharjah|ajman|ras\s+al\s+khaimah|fujairah|"
    r"al\s+ain|umm\s+al\s+quwain|deira|bur\s+dubai)\b",
    re.IGNORECASE,
)
_MULTI_CITY_SCAN_AR_RE = re.compile(
    r"(دبي|أبوظبي|ابوظبي|الشارقة|عجمان|رأس\s+الخيمة|راس\s+الخيمة|"
    r"الفجيرة|أم\s+القيوين|ام\s+القيوين|العين)"
)


def _requested_cities_from_text(text: str) -> list[str]:
    """Return the distinct UAE cities named in *text*, order-preserving.

    English names are title-cased ("abu dhabi" -> "Abu Dhabi"); Arabic names are
    kept as written. Country-scope words ("UAE") are intentionally excluded — a
    bare "UAE" is not a multi-city request.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in _MULTI_CITY_SCAN_RE.finditer(text or ""):
        canon = re.sub(r"\s+", " ", m.group(1).strip()).lower().title()
        if canon.lower() not in seen:
            seen.add(canon.lower())
            out.append(canon)
    for m in _MULTI_CITY_SCAN_AR_RE.finditer(text or ""):
        canon = re.sub(r"\s+", " ", m.group(1).strip())
        if canon.lower() not in seen:
            seen.add(canon.lower())
            out.append(canon)
    return out


# Canonical UAE-city aliases (EN + AR + common districts) → canonical token.
# Used to filter provider results to the cities the user actually asked for when
# a multi-city request was widened to a single UAE-wide provider call.
_UAE_CITY_CANON: dict[str, str] = {
    "dubai": "dubai", "bur dubai": "dubai", "deira": "dubai",
    "دبي": "dubai", "بر دبي": "dubai", "ديره": "dubai", "ديرة": "dubai",
    "abu dhabi": "abu dhabi", "أبوظبي": "abu dhabi", "ابوظبي": "abu dhabi",
    "أبو ظبي": "abu dhabi", "ابو ظبي": "abu dhabi",
    "sharjah": "sharjah", "الشارقة": "sharjah", "الشارقه": "sharjah",
    "ajman": "ajman", "عجمان": "ajman",
    "ras al khaimah": "ras al khaimah", "rak": "ras al khaimah",
    "رأس الخيمة": "ras al khaimah", "راس الخيمة": "ras al khaimah",
    "fujairah": "fujairah", "الفجيرة": "fujairah", "الفجيره": "fujairah",
    "umm al quwain": "umm al quwain", "أم القيوين": "umm al quwain",
    "ام القيوين": "umm al quwain",
    "al ain": "al ain", "العين": "al ain",
}


def _canonical_requested_cities(cities: list[str]) -> set[str]:
    """Map requested city names to canonical tokens (unknown → lowercased as-is)."""
    out: set[str] = set()
    for c in cities or []:
        key = re.sub(r"\s+", " ", str(c or "").strip()).lower()
        if key:
            out.add(_UAE_CITY_CANON.get(key, key))
    return out


def _location_matches_requested_cities(location: str, canon_cities: set[str]) -> bool:
    """True when *location* names any of the canonical requested cities.

    Alias-aware (EN/AR + districts) substring match, so a "Deira" or "بر دبي"
    job matches a "Dubai" request and vice-versa. Empty *canon_cities* means no
    city constraint (always True).
    """
    if not canon_cities:
        return True
    loc = re.sub(r"\s+", " ", (location or "").strip()).lower()
    if not loc:
        return False
    for alias, canon in _UAE_CITY_CANON.items():
        if canon in canon_cities and alias in loc:
            return True
    for canon in canon_cities:  # unknown-but-requested token appears literally
        if canon and canon in loc:
            return True
    return False

"""Profile location-field hygiene.

A profile's ``preferred_cities`` must hold city names — never a chat sentence.
Production first showed a corrupted English value
(``['Summarize this document for me.']``), then a second incident stored the
Arabic job-search command ``['ابحث عن وظيفه']`` as a city. Both values poisoned
job-search location and the AI context.

#744 (document-action routing) intercepts document messages before the
pending-field resolver. This module provides defense-in-depth for every caller
by rejecting chat/intent language in both English and Arabic and neutralizing
already-stored bad values on read.

Pure and deterministic: no I/O, no LLM, never raises.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

__all__ = ["is_plausible_city", "sanitize_cities"]

# Known cities are always accepted (covers UAE + a few common Gulf hubs). The
# caller may extend this via ``known_cities``.
_KNOWN_CITIES = frozenset({
    # UAE (en)
    "dubai", "abu dhabi", "sharjah", "ajman", "ras al khaimah", "fujairah",
    "umm al quwain", "al ain", "deira", "bur dubai",
    # UAE (ar)
    "دبي", "أبوظبي", "ابوظبي", "الشارقة", "الشارقه", "عجمان",
    "رأس الخيمة", "راس الخيمه", "الفجيرة", "الفجيره", "أم القيوين",
    "ام القيوين", "العين",
    # common regional hubs people legitimately enter
    "doha", "riyadh", "jeddah", "manama", "kuwait city", "muscat", "cairo",
})

# Words that never appear in a city name but do appear in chat/document actions
# and intents. Their presence means the value is a misfiled message, not a city.
_NON_CITY_TOKENS = frozenset({
    # document / chat actions (en)
    "summarize", "summarise", "describe", "extract", "translate", "read",
    "document", "image", "file", "picture", "photo", "screenshot", "please",
    "explain", "analyze", "analyse", "analize",
    # intents (en)
    "search", "find", "show", "apply", "generate", "create", "write", "update",
    "help", "resume", "cv", "cover", "letter", "job", "jobs", "work",
    # document / chat actions (ar)
    "لخص", "لخّص", "صف", "استخرج", "ترجم", "اقرأ", "مستند", "صورة", "ملف",
    # job-search / profile commands (ar) — include common orthographic variants.
    # These exact omissions allowed the production value "ابحث عن وظيفه" to pass
    # the short-value heuristic and become a persisted preferred city.
    "ابحث", "أبحث", "بحث", "دور", "دورلي", "اريد", "أريد", "ابي", "أبي",
    "ابغي", "أبغي", "احتاج", "محتاج", "ساعدني", "ايجاد", "إيجاد", "اعرض",
    "أعرض", "اعرضلي", "أعرضلي", "ارني", "أرني", "وريني", "جيب", "جيبلي",
    "وظيفه", "وظيفة", "وظائف", "وضيفه", "عمل", "شغل", "فرصه", "فرصة",
    "فرص", "شاغر", "شواغر", "منصب", "مناصب", "توظيف",
})

# Job-title nouns — a value containing one of these is a role, not a city
# (#1336 PR2: "Environmental Manager" answering a compound "role + city"
# prompt was captured whole as a preferred city, since no role vocabulary was
# in _NON_CITY_TOKENS). Reuses the existing role-keyword bank from the CV
# parser instead of duplicating a blocklist — kept in sync by import, not copy.
try:
    from src.cv_parser import CVParser as _CVParser
    _ROLE_TITLE_TOKENS = frozenset(w.lower() for w in _CVParser._ROLE_TITLE_KEYWORDS)
except Exception:
    _ROLE_TITLE_TOKENS = frozenset()

# Yes/no/confirmation/acknowledgement words that must never be stored as a city.
# Keep in sync with RicoChatAPI._CITY_REJECT_WORDS.
_REJECT_WORDS = frozenset({
    # English
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "fine", "great",
    "good", "cool", "done", "alright", "please", "thanks", "thank you",
    "go ahead", "no", "nope", "nah",
    # Arabic
    "نعم", "أيوه", "ايوه", "اوك", "اوكي", "اوكيه", "حسنا", "حسناً",
    "تمام", "تمم", "اكيد", "أكيد", "طبعا", "طبعاً", "تفضل", "يلا",
    "ماشي", "زين", "كويس", "شكرا", "شكراً", "موافق", "اه", "آه", "لا",
})

_MAX_CITY_WORDS = 4          # "Ras Al Khaimah" = 3, "Umm Al Quwain" = 3
_MAX_CITY_CHARS = 30


def is_plausible_city(value: str, *, known_cities: Optional[Iterable[str]] = None) -> bool:
    """Return True when *value* looks like a city name rather than a sentence.

    Known cities always pass. Otherwise a value is rejected when it carries the
    hallmarks of a misfiled chat/intent message: a trailing period or ``?``/``!``,
    digits, too many words, excessive length, an affirmation, or any token that
    never occurs in a city name (document/intent words).
    """
    text = (value or "").strip()
    if not text:
        return False

    lowered = text.lower()
    known = set(_KNOWN_CITIES)
    if known_cities:
        known |= {str(c).strip().lower() for c in known_cities}
    if lowered in known:
        return True

    if len(text) > _MAX_CITY_CHARS:
        return False
    if text[-1] in ".?!":           # city names are not sentences
        return False
    if any(ch.isdigit() for ch in text):
        return False
    words = re.findall(r"[^\s,،/|]+", lowered)
    if not words or len(words) > _MAX_CITY_WORDS:
        return False
    if lowered in _REJECT_WORDS:
        return False
    if any(w.strip(".,،!?") in _NON_CITY_TOKENS for w in words):
        return False
    if any(w.strip(".,،!?") in _ROLE_TITLE_TOKENS for w in words):
        return False
    return True


def sanitize_cities(
    cities: Iterable[str], *, known_cities: Optional[Iterable[str]] = None
) -> list[str]:
    """Drop implausible entries (misfiled messages) from a cities list.

    Order-preserving and de-duplicating (case-insensitive). Returns a clean list
    so a corrupted stored value never reaches job-search location or the AI
    context. Returns ``[]`` when nothing plausible remains.
    """
    out: list[str] = []
    seen: set[str] = set()
    for c in cities or []:
        text = str(c or "").strip()
        if not text or not is_plausible_city(text, known_cities=known_cities):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out

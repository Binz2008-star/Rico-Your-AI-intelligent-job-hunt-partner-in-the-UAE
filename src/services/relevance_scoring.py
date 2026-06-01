"""Per-user job relevance scoring.

Scores 0-100 how well a job matches a user's profile without reading any
hardcoded candidate data. All inputs are passed explicitly so this module
is fully testable without a database, API calls, or environment variables.
"""

from __future__ import annotations

import re
from typing import Any

# Tokens that convey seniority/level but not domain. Stripped before comparing
# core role content so "Senior HSE Manager" and "HSE Officer" both match an
# "HSE" target role.
_LEVEL_TOKENS: frozenset[str] = frozenset({
    "senior", "junior", "mid", "lead", "head", "manager", "director",
    "officer", "specialist", "engineer", "developer", "analyst",
    "consultant", "coordinator", "supervisor", "assistant", "principal",
    "staff", "associate", "chief", "vp", "vice", "president", "executive",
    "intern", "trainee", "graduate", "entry", "experienced",
})

# Emirates and common UAE location strings to recognise as "UAE match"
_UAE_LOCATIONS: frozenset[str] = frozenset({
    "uae", "united arab emirates", "dubai", "abu dhabi", "abu_dhabi",
    "sharjah", "ajman", "ras al khaimah", "fujairah", "umm al quwain",
    "al ain", "al-ain",
})


def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _core_tokens(phrase: str) -> frozenset[str]:
    """Return meaningful tokens — drop seniority/level words and short tokens."""
    return frozenset(
        t for t in _tokenise(phrase)
        if len(t) > 2 and t not in _LEVEL_TOKENS
    )


# ---------------------------------------------------------------------------
# Sub-scores
# ---------------------------------------------------------------------------

def _score_title_role(title: str, target_roles: list[str]) -> int:
    """Title vs target-role relevance, 0-50."""
    if not target_roles:
        return 20  # neutral default when profile has no roles yet

    title_lower = title.lower()
    title_tokens = frozenset(_tokenise(title_lower))
    core_title = _core_tokens(title_lower)
    best = 0

    for role in target_roles:
        if not role:
            continue
        role_lower = role.lower().strip()

        # Exact phrase match anywhere in title
        if role_lower in title_lower:
            best = max(best, 50)
            continue

        core_role = _core_tokens(role_lower)
        role_tokens = frozenset(_tokenise(role_lower))

        if core_role and core_title:
            overlap = len(core_role & core_title)
            coverage = overlap / len(core_role)
            best = max(best, int(coverage * 45))
        elif core_role and title_tokens:
            # Fallback when title has no meaningful core tokens (e.g. "Senior Manager"):
            # only award points if a real domain token from the role appears in the title.
            # Using core_role (not role_tokens) ensures level-words like "manager" don't
            # create false matches between "HSE Manager" and "Senior Manager".
            overlap = len(core_role & title_tokens)
            coverage = overlap / len(core_role)
            best = max(best, int(coverage * 30))

    return best


def _score_skills(title: str, description: str, skills: list[str]) -> int:
    """Skill keyword presence in title + first 800 chars of description, 0-30."""
    if not skills:
        return 10  # neutral default when profile has no skills yet

    # Search title fully, description up to 800 chars (avoid scanning huge blobs)
    haystack = (title + " " + description[:800]).lower()
    matched = sum(1 for s in skills if s and s.lower() in haystack)
    cap = min(len(skills), 6)  # diminishing returns after 6 matched skills
    return min(30, int(matched / cap * 30)) if cap else 10


def _score_location(location: str, preferred_cities: list[str]) -> int:
    """Location match: preferred city → 20, anywhere in UAE → 10, else 0."""
    loc_lower = location.lower()

    for city in preferred_cities:
        if city and city.lower() in loc_lower:
            return 20

    for kw in _UAE_LOCATIONS:
        if kw in loc_lower:
            return 10

    return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_relevance(
    job: dict[str, Any],
    target_roles: list[str],
    skills: list[str],
    cities: list[str],
) -> int:
    """Return a 0-100 relevance score for *job* given the user's profile data.

    Parameters
    ----------
    job:          Normalised job dict (keys: title, description, location …).
    target_roles: User's target job titles from their profile.
    skills:       User's skills list from their profile.
    cities:       User's preferred UAE cities from their profile.

    All arguments are pure data — no DB calls, no env-var reads, no I/O.
    """
    if not isinstance(job, dict):
        return 0

    title = str(job.get("title") or "").strip()
    if not title:
        return 0

    description = str(job.get("description") or "")
    location = str(job.get("location") or "")

    score = (
        _score_title_role(title, target_roles)
        + _score_skills(title, description, skills)
        + _score_location(location, cities)
    )
    return min(100, max(0, score))

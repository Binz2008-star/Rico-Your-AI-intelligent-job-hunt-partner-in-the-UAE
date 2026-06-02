"""
src/models/application_status.py

Single source of truth for application/recommendation status values.

Both the chat-side (user_job_context) and the SaaS-side
(rico_job_recommendations) now share this vocabulary.  Any code that needs to
write or validate a status value should import from here rather than defining
inline string sets.

Migration 024 adds a matching CHECK constraint to rico_job_recommendations, so
any value not in this set will be rejected at the DB level too.
"""
from __future__ import annotations

from enum import Enum
from typing import FrozenSet


class ApplicationStatus(str, Enum):
    """Ordered application funnel statuses.

    The string value of each member is the canonical lowercase token stored in
    the database and used in API responses.  Because this inherits from ``str``
    the members are drop-in replacements for string literals:
    ``ApplicationStatus.APPLIED == "applied"`` is True.
    """
    FOUND                   = "found"
    SAVED                   = "saved"
    OPENED_EXTERNAL         = "opened_external"
    PREPARED                = "prepared"
    APPLIED                 = "applied"
    INTERVIEW               = "interview"
    OFFER                   = "offer"
    REJECTED                = "rejected"
    WITHDRAWN               = "withdrawn"
    EXPIRED                 = "expired"
    ARCHIVED                = "archived"
    ON_HOLD                 = "on_hold"
    NEEDS_SOURCE_VERIFICATION = "needs_source_verification"
    NEEDS_REVIEW            = "needs_review"


# Frozen set of valid string values — for O(1) membership tests without
# constructing an enum member (used in hot validation paths).
VALID_STATUSES: FrozenSet[str] = frozenset(s.value for s in ApplicationStatus)

# Legacy alias that was used in job_lifecycle.py before this module existed.
# "interviewing" was a typo/divergence from the canonical "interview".
# Kept here as a mapping so callers can normalise incoming data gracefully.
_LEGACY_ALIASES: dict[str, str] = {
    "interviewing": ApplicationStatus.INTERVIEW,
    "interview_scheduled": ApplicationStatus.INTERVIEW,
    "opened": ApplicationStatus.OPENED_EXTERNAL,
}


def normalise(status: str) -> str | None:
    """Return the canonical status string, resolving legacy aliases.

    Returns ``None`` if the value is not recognised at all (invalid, not just
    aliased).  Callers should treat ``None`` as a validation failure.
    """
    if not status:
        return None
    s = status.strip().lower()
    if s in VALID_STATUSES:
        return s
    return _LEGACY_ALIASES.get(s)


def is_valid(status: str) -> bool:
    """True if status is a canonical or aliased valid value."""
    return normalise(status) is not None

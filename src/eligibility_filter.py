"""
src/eligibility_filter.py
UAE national-only job filter.

Non-UAE-national users must not receive jobs that explicitly restrict to Emirati
citizens as strong matches. This module exposes a single function:

    is_uae_nationals_only(job) -> bool

Returns True when the job description, title, or any text field contains one of
the hard markers below. Callers should exclude or down-rank these jobs for users
who are not UAE nationals.

All markers are checked case-insensitively against a combined text blob of the
title + description + company fields. Arabic markers are matched as-is after
Unicode NFC normalization (no alef-variant collapsing required here since the
canonical forms are listed).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

# Hard markers — any match means "UAE nationals only" regardless of context.
# Kept as a tuple so the compiled regex preserves the order (longest first
# for unambiguous alternation, though `re` handles overlaps correctly).
_UAE_NATIONAL_MARKERS: tuple[str, ...] = (
    # English — explicit restriction phrases
    r"UAE\s+Nationals?\s+only",
    r"UAE\s+Nationals?\s+preferred",
    r"Emirati\s+Nationals?\s+only",
    r"Emirati\s+Nationals?\s+preferred",
    r"for\s+UAE\s+Nationals?",
    r"open\s+to\s+UAE\s+Nationals?",
    r"UAE\s+citizen",
    r"Emirati\s+citizen",
    r"UAE\s+National",   # standalone (catches "UAE National" in job titles)
    r"Emirati",          # standalone — broad but intentional (title "Emirati Graduate")
    # Arabic — UAE national markers
    r"مواطن\s+إماراتي",
    r"مواطنين\s+إماراتيين",
    r"للإماراتيين",
    r"للمواطنين\s+الإماراتيين",
    r"إماراتي",          # standalone — covers "مطلوب إماراتي"
    # Arabic — Khulasat al-Qaid (family book / civil registry, UAE-national proof)
    r"خلاصة\s+القيد",
    r"خلاصه\s+القيد",   # common misspelling with ta marbuta variant
)

_PATTERN = re.compile(
    "|".join(f"(?:{m})" for m in _UAE_NATIONAL_MARKERS),
    re.IGNORECASE | re.UNICODE,
)


def _text_blob(job: Dict[str, Any]) -> str:
    """Concatenate all searchable text fields into one string for a single-pass match."""
    parts = [
        job.get("title") or "",
        job.get("description") or "",
        job.get("job_description") or "",  # raw JSearch field
        job.get("company") or "",
        job.get("employer_name") or "",    # raw JSearch field
    ]
    raw = " ".join(str(p) for p in parts if p)
    # NFC normalisation so Arabic characters compare consistently.
    return unicodedata.normalize("NFC", raw)


def is_uae_nationals_only(job: Optional[Dict[str, Any]]) -> bool:
    """Return True when `job` contains a UAE-nationals-only restriction marker.

    Intended use: callers who know the user is not a UAE national should
    exclude or suppress these jobs as strong matches.

    Returns False for None/empty input and on any processing error.
    """
    if not job:
        return False
    try:
        return bool(_PATTERN.search(_text_blob(job)))
    except Exception:
        return False


def filter_for_non_nationals(jobs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Return `jobs` with UAE-nationals-only listings removed.

    Safe to call on any job list; never raises.
    """
    try:
        return [j for j in (jobs or []) if not is_uae_nationals_only(j)]
    except Exception:
        return jobs or []

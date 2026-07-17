# -*- coding: utf-8 -*-
"""Job Result Integrity Gate — Rico owns the final trust decision.

A provider returning HTTP 200 does NOT make a listing a trustworthy career
opportunity. Before a record may be CV-scored, formatted into a job card, or
admitted to the shortlist, it must pass every mandatory integrity check:

  * MARKET   — a UAE-only search may only surface UAE listings.
  * ROLE     — the requested role family must be supported by the title or the
               body, and the title and body must not describe conflicting
               occupational domains (e.g. "Project Manager" title with a
               "Mental Health Practitioner" body).
  * LISTING  — the listing must not be unavailable/expired and must have a
               usable apply/canonical URL.
  * FRESH    — a present publish date must not be clearly stale.
  * EVIDENCE — a record with no title (or no usable content) is not a listing.

An invalid listing receives no score, no "why it fits", no shortlist slot, no
Apply action. An empty *trustworthy* result set is acceptable; displaying a
corrupt listing to avoid an empty result is not.

This module is intentionally provider-agnostic and self-contained: callers pass
already-normalized records (title/location/description/apply_url/…) plus the
requested-role vocabulary. It never fabricates details and never trusts a record
merely because a provider returned it.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Iterable, Optional

try:  # tokeniser shared with the scorer; degrade gracefully if unavailable.
    from src.llm_scorer import _TOKEN_RE as _WORD_RE  # type: ignore
except Exception:  # pragma: no cover
    _WORD_RE = re.compile(r"[a-z0-9]+")

_ARABIC_RE = re.compile(r"[؀-ۿ]")


class RejectionReason(str, Enum):
    """Explicit internal rejection reasons (never surfaced verbatim to users)."""

    OUTSIDE_REQUESTED_MARKET = "outside_requested_market"
    TITLE_ROLE_MISMATCH = "title_role_mismatch"
    DESCRIPTION_ROLE_MISMATCH = "description_role_mismatch"
    TITLE_DESCRIPTION_CONFLICT = "title_description_conflict"
    LISTING_UNAVAILABLE = "listing_unavailable"
    APPLY_URL_INVALID = "apply_url_invalid"
    SOURCE_PAGE_MISMATCH = "source_page_mismatch"
    STALE_LISTING = "stale_listing"
    INSUFFICIENT_LISTING_EVIDENCE = "insufficient_listing_evidence"


# ── UAE market vocabulary (mirrors jsearch_client UAE detection, EN + AR) ──────
_UAE_MARKERS: frozenset[str] = frozenset({
    "uae", "u.a.e", "u.a.e.", "united arab emirates", "emirates",
    "dubai", "abu dhabi", "abudhabi", "sharjah", "ajman",
    "ras al khaimah", "ras al-khaimah", "rak", "fujairah", "al ain",
    "umm al quwain", "umm al-quwain",
    # Arabic
    "الإمارات", "الامارات", "دبي", "أبوظبي", "ابوظبي",
    "الشارقة", "الشارقه", "عجمان", "رأس الخيمة", "راس الخيمه",
    "الفجيرة", "الفجيره", "أم القيوين", "ام القيوين",
})
# ISO / spoken country tokens that mean UAE (used when a country field is set).
_UAE_COUNTRY_VALUES: frozenset[str] = frozenset({
    "ae", "are", "uae", "u.a.e.", "united arab emirates", "emirates",
})

# ── Distinct protected occupational domains — a body dominated by one of these,
# when the requested role and title do NOT belong to it, is a hard mismatch.
# Deliberately narrow and high-confidence to avoid false rejections of ordinary
# HSE / environment / management / operations listings. ──────────────────────
_PROTECTED_DOMAINS: dict[str, frozenset[str]] = {
    "healthcare": frozenset({
        "nurse", "nursing", "mental health", "practitioner", "clinical",
        "patient", "patients", "ward", "therapy", "therapist", "recovery service",
        "care worker", "support worker", "physician", "midwife", "paramedic",
        "psycholog", "counsell", "caregiver", "healthcare assistant", "dementia",
        "rehabilitation", "clinician",
    }),
    "education": frozenset({
        "classroom", "pupils", "curriculum", "kindergarten", "nursery nurse",
        "teaching assistant", "lesson plan", "safeguarding of children",
    }),
    "legal": frozenset({
        "solicitor", "barrister", "paralegal", "litigation", "conveyancing",
    }),
    "skilled_trades": frozenset({
        "hgv driver", "forklift driver", "warehouse operative", "kitchen porter",
        "care assistant",
    }),
}

_UNAVAILABLE_MARKERS: frozenset[str] = frozenset({
    "unavailable", "expired", "closed", "dead", "removed", "gone",
    "no longer available", "position filled", "inactive",
})

# Freshness: reject a listing whose parseable publish date is older than this.
_MAX_LISTING_AGE_DAYS = 120


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def _is_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text or ""))


def _record_field(rec: dict, *names: str) -> str:
    for n in names:
        v = rec.get(n)
        if v:
            return str(v)
    return ""


def is_uae_market(rec: dict) -> bool:
    """True when the record positively resolves to the UAE market.

    Requires a POSITIVE UAE marker in the location (or an explicit UAE country
    field). A location that names no UAE place is treated as outside the market —
    an empty trustworthy result is preferable to a mis-located one.
    """
    country = _norm(_record_field(rec, "country", "job_country"))
    if country:
        if country in _UAE_COUNTRY_VALUES:
            return True
        # A present, non-UAE country field is decisive.
        return False
    loc = _norm(_record_field(rec, "location", "job_location", "city"))
    if not loc:
        return False
    return any(marker in loc for marker in _UAE_MARKERS)


def _dominant_protected_domain(text: str, *, min_hits: int = 2) -> Optional[str]:
    """Return the protected occupational domain that dominates *text*, or None.

    Requires at least ``min_hits`` distinct strong markers of a single domain so
    a lone incidental word (e.g. "patient safety" in an HSE post) never triggers.
    """
    low = _norm(text)
    if not low:
        return None
    best: Optional[str] = None
    best_hits = 0
    for domain, markers in _PROTECTED_DOMAINS.items():
        hits = sum(1 for m in markers if m in low)
        if hits > best_hits:
            best_hits, best = hits, domain
    return best if best_hits >= min_hits else None


def _role_supported(text: str, single_terms: set[str], phrase_terms: set[str]) -> bool:
    """True when *text* contains any requested-role single token or phrase."""
    low = _norm(text)
    if not low:
        return False
    if phrase_terms and any(p in low for p in phrase_terms):
        return True
    if single_terms and (_tokens(low) & single_terms):
        return True
    return False


def _apply_url_present_but_invalid(rec: dict) -> bool:
    """True only when a URL field is present but is not a usable http(s) URL.

    A *missing* URL is NOT invalid — per the trust contract a listing may be
    "usable OR explicitly marked unverified", so an un-enriched listing with no
    URL yet is allowed (it is marked unverified downstream and offers no Apply
    action). Only a present-but-malformed URL is a hard rejection.
    """
    url = _record_field(
        rec, "apply_url", "apply_link", "link", "url", "canonical_url", "source_url"
    ).strip()
    return bool(url) and not url.lower().startswith(("http://", "https://"))


def _is_unavailable(rec: dict) -> bool:
    for f in ("availability", "status", "verification_status", "listing_state"):
        v = _norm(rec.get(f))
        if v and any(m in v for m in _UNAVAILABLE_MARKERS):
            return True
    return False


def _is_stale(rec: dict) -> bool:
    raw = _record_field(rec, "published_date", "posted_at", "date", "job_posted_at")
    if not raw:
        return False  # unknown date is honest-unknown, not stale
    from datetime import datetime, timezone
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(raw[:19], fmt[:19]) if "T" in raw else datetime.strptime(raw[:10], "%Y-%m-%d")
            age = (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days
            return age > _MAX_LISTING_AGE_DAYS
        except Exception:
            continue
    return False


def validate_listing(
    rec: dict,
    *,
    requested_role: str = "",
    single_terms: Optional[set[str]] = None,
    phrase_terms: Optional[set[str]] = None,
    uae_only: bool = True,
) -> Optional[RejectionReason]:
    """Return the FIRST failing integrity reason for *rec*, or None if it passes.

    The check order mirrors the search pipeline so the returned reason names the
    earliest layer at which the record should have been rejected.
    """
    single_terms = single_terms or set()
    phrase_terms = phrase_terms or set()

    title = _record_field(rec, "title", "job_title")
    description = _record_field(rec, "description", "job_description", "snippet")

    # 0. Evidence — a record with no title is not a listing.
    if not title.strip():
        return RejectionReason.INSUFFICIENT_LISTING_EVIDENCE

    # 1. Market — a UAE-only search may only surface UAE listings.
    if uae_only and not is_uae_market(rec):
        return RejectionReason.OUTSIDE_REQUESTED_MARKET

    # 2. Role integrity. English-only vocabulary; skip for Arabic titles/bodies to
    #    avoid an English-only bias that would wrongly drop a valid Arabic listing.
    role_checkable = bool((single_terms or phrase_terms)) and not _is_arabic(title)
    if role_checkable:
        title_ok = _role_supported(title, single_terms, phrase_terms)
        desc_ok = _role_supported(description, single_terms, phrase_terms) if description and not _is_arabic(description) else False
        desc_domain = _dominant_protected_domain(description) if not _is_arabic(description) else None
        title_domain = _dominant_protected_domain(title)
        # 2a. Requested role supported by neither title nor body → mismatch.
        if not title_ok and not desc_ok:
            if desc_domain and desc_domain != title_domain:
                return RejectionReason.DESCRIPTION_ROLE_MISMATCH
            return RejectionReason.TITLE_ROLE_MISMATCH
        # 2b. Title/body describe conflicting occupational domains — body belongs
        #     to a protected domain the requested role/title do not (e.g. a
        #     "Sustainability Manager" title with a nursing body).
        if desc_domain and desc_domain != title_domain:
            return RejectionReason.TITLE_DESCRIPTION_CONFLICT

    # 3. Source-page agreement (when enrichment fetched the real page title).
    src_title = _record_field(rec, "source_page_title")
    if src_title and not _is_arabic(src_title) and not _is_arabic(title):
        src_domain = _dominant_protected_domain(src_title, min_hits=1)
        ttl_domain = _dominant_protected_domain(title, min_hits=1)
        if src_domain and src_domain != ttl_domain:
            return RejectionReason.SOURCE_PAGE_MISMATCH
        if single_terms or phrase_terms:
            if not _role_supported(src_title, single_terms, phrase_terms) and _role_supported(title, single_terms, phrase_terms):
                # Provider title matches the role but the real page does not.
                if not _tokens(_norm(src_title)) & _tokens(_norm(title)):
                    return RejectionReason.SOURCE_PAGE_MISMATCH

    # 4. Listing availability.
    if _is_unavailable(rec):
        return RejectionReason.LISTING_UNAVAILABLE

    # 5. Usable apply/canonical URL — reject only a present-but-malformed URL;
    #    a missing URL is allowed (marked unverified downstream, no Apply action).
    if _apply_url_present_but_invalid(rec):
        return RejectionReason.APPLY_URL_INVALID

    # 6. Freshness (only when a parseable date is present and clearly old).
    if _is_stale(rec):
        return RejectionReason.STALE_LISTING

    return None


def filter_listings(
    records: Iterable[dict],
    *,
    requested_role: str = "",
    requested_terms: Optional[tuple[set[str], set[str]]] = None,
    uae_only: bool = True,
) -> tuple[list[dict], dict[str, int]]:
    """Split *records* into (trustworthy, rejection-count-by-reason).

    Trustworthy records are returned unchanged and in order. Rejected records are
    dropped entirely and counted by reason for a safe aggregate summary — the
    per-record reasons are never surfaced to the user.
    """
    single_terms, phrase_terms = requested_terms or (set(), set())
    kept: list[dict] = []
    rejected: dict[str, int] = {}
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        reason = validate_listing(
            rec,
            requested_role=requested_role,
            single_terms=single_terms,
            phrase_terms=phrase_terms,
            uae_only=uae_only,
        )
        if reason is None:
            kept.append(rec)
        else:
            rejected[reason.value] = rejected.get(reason.value, 0) + 1
    return kept, rejected

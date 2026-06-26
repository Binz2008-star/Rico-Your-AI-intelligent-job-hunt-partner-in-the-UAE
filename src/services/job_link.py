"""
src/services/job_link.py
Canonical job-link resolution shared by the frontend job cards and the chat
"open the apply link for the Nth job" action.

Production Test 9 failed with:
    "Action failed: Job payload is missing required 'link' field"
because different layers looked at different link fields (``link`` vs
``apply_url`` vs ``job_apply_link`` …) and an Apply button could render with no
usable URL behind it. This module gives every layer ONE normalized view of a
job's link so a card and the chat command always agree, and a job with no
trusted link is flagged explicitly (``link_unavailable`` + ``reason``) instead
of blowing up.

Pure functions only — no network calls (domain classification is table-based via
``source_quality``).
"""
from __future__ import annotations

from typing import Any, Dict

# Source-quality statuses that are NOT a usable apply destination — a Google
# search intermediary or a spammy aggregator is a dead-end, so the Apply button
# must fall back to a CTA instead of linking there.
_UNUSABLE_STATUSES = frozenset({"aggregator_untrusted", "google_intermediary"})

# Statuses that must never be overridden by JSearch's apply_is_direct signal.
# Aggregators, rate-limited walls, and login gates stay as-is regardless of
# what the upstream API claims.
_DIRECT_UPGRADE_BLOCKED = frozenset({
    "aggregator_untrusted", "google_intermediary",
    "login_required", "rate_limited",
})

# Ordered candidate fields for each role, newest provider names first. The legacy
# single ``link`` field is the lowest-priority apply candidate so older callers
# that only set ``link`` still resolve.
_APPLY_FIELDS = ("job_apply_link", "apply_link", "apply_url", "link")
_ALT_FIELDS = ("job_google_link", "alt_link", "alt_url")
_SOURCE_FIELDS = ("source_url",)


def _first_url(job: Dict[str, Any], fields: tuple[str, ...]) -> str:
    for f in fields:
        v = job.get(f)
        if v:
            s = str(v).strip()
            if s:
                return s
    return ""


def _is_http(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def resolve_job_link(job: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized link view for *job*.

    Result keys:
      - ``usable_link``: the single best trusted apply/source URL, or "" if none.
      - ``apply_url`` / ``alt_link`` / ``source_url``: normalized component URLs.
      - ``verification_status``: source-quality status of the chosen link.
      - ``link_unavailable``: True when there is no trusted, usable link.
      - ``reason``: why a link is unavailable ("" when usable). One of
        "expired", "google_intermediary_only", "untrusted_aggregator",
        "no_link".

    Never raises.
    """
    try:
        from src.services.source_quality import classify_url, is_google_intermediary
    except Exception:  # pragma: no cover - defensive; source_quality is always present
        def classify_url(_u: str) -> str:  # type: ignore
            return "needs_source_verification"

        def is_google_intermediary(_u: str) -> bool:  # type: ignore
            return False

    if not isinstance(job, dict):
        return {
            "usable_link": "", "apply_url": "", "alt_link": "", "source_url": "",
            "employer_url": "",
            "verification_status": "lead_needs_verification",
            "link_unavailable": True, "reason": "no_link",
        }

    apply_url = _first_url(job, _APPLY_FIELDS)
    alt_link = _first_url(job, _ALT_FIELDS)
    source_url = _first_url(job, _SOURCE_FIELDS)
    employer_url = str(job.get("employer_url") or "").strip()
    apply_is_direct = bool(job.get("apply_is_direct"))
    explicit_status = str(job.get("verification_status") or "").strip().lower()

    # source_url falls back to a (non-empty) alt_link or apply_url; Google
    # intermediaries are stripped out below. This mirrors the long-standing
    # _format_match contract so existing callers/tests stay correct.
    if not source_url:
        source_url = alt_link or apply_url

    # A Google "search" intermediary is not a real apply link — demote the apply
    # URL to alt and flag it, so the frontend offers it as a secondary option but
    # never as the primary Apply action.
    apply_was_google = False
    if apply_url and is_google_intermediary(apply_url):
        apply_was_google = True
        if not alt_link:
            alt_link = apply_url
        apply_url = ""

    # Neither source_url nor alt_link may surface a Google search intermediary.
    if source_url and is_google_intermediary(source_url):
        source_url = ""
    if alt_link and is_google_intermediary(alt_link):
        alt_link = ""

    if apply_was_google and not apply_url:
        verification_status = "google_intermediary"
    else:
        verification_status = classify_url(apply_url or source_url)

    # JSearch's apply_is_direct=True means the link goes straight to an employer
    # ATS page. Upgrade display status to live_verified for unknown domains, but
    # never override a known-bad classification (aggregator, login wall, etc.).
    if (apply_is_direct and apply_url and _is_http(apply_url)
            and not is_google_intermediary(apply_url)
            and verification_status not in _DIRECT_UPGRADE_BLOCKED):
        verification_status = "live_verified"

    # Choose the single usable link in priority order: direct apply → source.
    usable_link = ""
    for candidate in (apply_url, source_url):
        if not candidate or not _is_http(candidate):
            continue
        if is_google_intermediary(candidate):
            continue
        if classify_url(candidate) in _UNUSABLE_STATUSES:
            continue
        usable_link = candidate
        break

    # Explicitly-expired listings are never usable, regardless of the URL.
    if explicit_status == "expired":
        usable_link = ""
        verification_status = "expired"

    if usable_link:
        reason = ""
        link_unavailable = False
    else:
        link_unavailable = True
        if explicit_status == "expired":
            reason = "expired"
        elif apply_was_google or alt_link:
            reason = "google_intermediary_only"
        elif apply_url or source_url:
            reason = "untrusted_aggregator"
        else:
            reason = "no_link"

    return {
        "usable_link": usable_link,
        "apply_url": apply_url,
        "alt_link": alt_link,
        "source_url": source_url,
        "employer_url": employer_url,
        "verification_status": verification_status,
        "link_unavailable": link_unavailable,
        "reason": reason,
    }


def build_link_fallback_cta(title: str = "", company: str = "", location: str = "") -> list[dict[str, Any]]:
    """Safe fallback CTAs when a job has no trusted apply link.

    Plain *search* URLs only — Rico never scrapes these destinations.
    """
    from urllib.parse import quote_plus

    role = (title or "").strip() or "this role"
    loc = (location or "").strip() or "UAE"
    company_q = (company or "").strip()
    google_terms = " ".join(p for p in [role, company_q, loc, "careers"] if p)
    google_url = f"https://www.google.com/search?q={quote_plus(google_terms)}"
    linkedin_url = (
        "https://www.linkedin.com/jobs/search/?"
        f"keywords={quote_plus(role)}&location={quote_plus(loc)}"
    )
    options: list[dict[str, Any]] = []
    if company_q:
        company_site = f"https://www.google.com/search?q={quote_plus(company_q + ' careers ' + loc)}"
        options.append({"action": "open_url", "label": "Search company career site", "url": company_site})
    options.extend([
        {"action": "open_url", "label": "Search on Google", "url": google_url},
        {"action": "open_url", "label": "Search on LinkedIn", "url": linkedin_url},
        {"action": "copy_text", "label": "Copy title & company",
         "text": " — ".join(p for p in [role, company_q] if p)},
        {"action": "save_job", "label": "Save to pipeline",
         "message": (f"save {role} at {company_q}" if company_q else f"save {role}")},
    ])
    return options

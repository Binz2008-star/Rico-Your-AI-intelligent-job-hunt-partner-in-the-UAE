"""Phase-0 trust gate for job apply URLs.

This module is the ONLY place that decides whether a job's apply URL
is safe to surface in the UI.  All callers must go through
``resolve_trusted_apply_url``; nothing else may construct an apply URL.

Trust chain (all checks are AND-gated)
---------------------------------------
Gate 0  The record's *origin* must NOT be an untrusted source
        (LLM output, chat recent_context, context window, etc.).
        Any payload arriving from those sources is rejected immediately
        regardless of what fields it claims to contain.

Gate 1  URL must be non-empty with an ``http``/``https`` scheme.
        The URL is read from the canonical field set used across the
        codebase (``external_url``, ``alt_url``, ``source_url``, plus the
        DB/ingestion fields ``link``, ``apply_link``, ``job_apply_link``,
        ``apply_url``, ``url``, ``job_url``, ``alt_link``).  Field presence
        alone NEVER grants trust — Gates 0 and 2-4 still apply to whatever
        URL is found.

Gate 2  URL must NOT match known placeholder patterns
        (jk=abc123, template tokens, localhost, etc.).

Gate 3  URL must NOT contain a sequential / obviously-generated
        LinkedIn job ID (< 10 000 000).

Gate 4  The job record must carry at least ONE trusted provenance marker:
            - persisted_job_id   — set by DB upsert after source ingest
            - source_job_id      — set by provider / scraper ingestion
            - provider + source_backed is True — set by ingestion layer

        ``job_id`` alone is NOT trusted.  It can be synthesised by the LLM,
        copied from chat context, or inferred from ordinal references.

        ``provider + source_backed`` is only accepted when the record's origin
        is NOT in UNTRUSTED_ORIGINS (see Gate 0 above).  A recent_context
        payload that happens to include both fields is still rejected at Gate 0.

If the URL fails any gate, ``resolve_trusted_apply_url`` returns ``None``
and the caller must show the no-apply-link safe message.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

from src.services.source_quality import is_placeholder_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"https", "http"})

# All origin values that must be rejected at Gate 0, regardless of what
# provenance fields the payload claims to carry.
# Extend this set if new untrusted delivery channels are added.
UNTRUSTED_ORIGINS: frozenset[str] = frozenset({
    "llm",
    "recent_context",
    "chat",
    "context_window",
    "llm_tool_call",
    "search_match",       # raw recent_search_matches without DB lookup
})

# URL fields checked by Gate 1, in priority order, after the caller's
# url_field. Covers the DB row shape (jobs_repo stores the URL in `link`)
# and provider/scraper payload shapes (JSearch uses `job_apply_link`).
# A URL found in any of these fields still has to clear Gates 0 and 2-4.
_FALLBACK_URL_FIELDS: tuple[str, ...] = (
    "alt_url",
    "source_url",
    "link",
    "apply_link",
    "job_apply_link",
    "apply_url",
    "url",
    "job_url",
    "alt_link",
)

# Regex: sequential / obviously-generated LinkedIn job IDs
_SEQUENTIAL_LINKEDIN_JOB_ID_RE = re.compile(
    r"linkedin\.com/jobs/view/(?P<id>\d{1,6})(?:/|$|\?)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_job_url(raw: Any) -> str:
    """Canonical URL safety check for job links at ingestion and egress.

    Returns the cleaned URL string if it passes all checks, or "" if it
    fails any check.  This is a pure URL-safety gate — it does NOT check
    provenance (use ``resolve_trusted_apply_url`` for that).

    Checks:
      1. Non-empty string after stripping.
      2. Parses as a valid URL.
      3. Scheme is exactly ``http`` or ``https``.
      4. Has a non-empty hostname.
      5. No credentials (user:pass@) in the netloc.
      6. No control characters or whitespace in the URL.
    """
    if not raw or not isinstance(raw, str):
        return ""
    url = raw.strip()
    if not url:
        return ""
    # Reject control characters and embedded null bytes.
    if any(ord(c) < 0x20 for c in url):
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return ""
    if not parsed.hostname:
        return ""
    if parsed.username or parsed.password:
        return ""
    return url


def resolve_trusted_apply_url(
    job: dict[str, Any],
    *,
    url_field: str = "external_url",
    origin: Optional[str] = None,
) -> Optional[str]:
    """Return the apply URL iff it is source-backed, non-fake, and non-LLM.

    Parameters
    ----------
    job:
        The job dict from the DB or ingestion layer.  Must never be raw
        LLM output or a recent_context payload.
    url_field:
        Key checked first for the apply URL inside *job*.  Defaults to
        ``external_url``.  The fields in ``_FALLBACK_URL_FIELDS`` (DB
        ``link``, provider ``job_apply_link``/``apply_link``, etc.) are
        checked next, in order.
    origin:
        Delivery-channel hint.  Pass ``'llm'``, ``'recent_context'``,
        ``'chat'``, or any value in ``UNTRUSTED_ORIGINS`` when the record
        did not originate from the DB / ingestion pipeline.

    Returns
    -------
    str | None
        The verified URL string, or ``None`` when no trusted apply link
        exists.
    """
    job_id_log = job.get("job_id") or job.get("id") or "<unknown>"

    # ------------------------------------------------------------------
    # Gate 0 — Reject any record from an untrusted delivery channel.
    #
    # Callers serving recent_search_matches / chat context MUST pass
    # origin='recent_context' (or similar).  Any record whose origin
    # field is in UNTRUSTED_ORIGINS is rejected here, even if it carries
    # a plausible provider + source_backed=True payload — those fields
    # can be spoofed by LLM output.
    # ------------------------------------------------------------------
    effective_origin: Optional[str] = (
        origin
        or (job.get("origin") if isinstance(job.get("origin"), str) else None)
    )
    if effective_origin and effective_origin.lower() in UNTRUSTED_ORIGINS:
        logger.warning(
            "job_link_trust: rejected at Gate 0 – untrusted origin '%s' job_id=%s",
            effective_origin,
            job_id_log,
        )
        return None

    # ------------------------------------------------------------------
    # Gate 1 — URL presence and scheme.
    # ------------------------------------------------------------------
    raw_url: Any = job.get(url_field)
    if not raw_url or not isinstance(raw_url, str):
        raw_url = next(
            (
                value
                for field in _FALLBACK_URL_FIELDS
                if isinstance(value := job.get(field), str) and value.strip()
            ),
            None,
        )
    if not raw_url or not isinstance(raw_url, str):
        return None
    url = raw_url.strip()
    if not url:
        return None
    scheme = url.split(":", 1)[0].lower()
    if scheme not in _ALLOWED_SCHEMES:
        logger.warning(
            "job_link_trust: rejected at Gate 1 – bad scheme '%s' job_id=%s",
            scheme,
            job_id_log,
        )
        return None

    # ------------------------------------------------------------------
    # Gate 2 — Placeholder / fake URL patterns.
    # ------------------------------------------------------------------
    if is_placeholder_url(url):
        logger.warning(
            "job_link_trust: rejected at Gate 2 – placeholder url '%s' job_id=%s",
            url,
            job_id_log,
        )
        return None

    # ------------------------------------------------------------------
    # Gate 3 — Sequential LinkedIn job ID.
    # ------------------------------------------------------------------
    m = _SEQUENTIAL_LINKEDIN_JOB_ID_RE.search(url)
    if m:
        numeric_id = int(m.group("id"))
        if numeric_id < 10_000_000:
            logger.warning(
                "job_link_trust: rejected at Gate 3 – sequential LinkedIn id %d "
                "url '%s' job_id=%s",
                numeric_id,
                url,
                job_id_log,
            )
            return None

    # ------------------------------------------------------------------
    # Gate 4 — Trusted provenance in the job record.
    # ------------------------------------------------------------------
    if not _has_trusted_provenance(job):
        logger.warning(
            "job_link_trust: rejected at Gate 4 – no trusted provenance "
            "url='%s' job_id=%s persisted_job_id=%s source_job_id=%s "
            "provider=%s source_backed=%s",
            url,
            job_id_log,
            job.get("persisted_job_id"),
            job.get("source_job_id"),
            job.get("provider"),
            job.get("source_backed"),
        )
        return None

    logger.debug(
        "job_link_trust: accepted url='%s' persisted_job_id=%s source_job_id=%s",
        url,
        job.get("persisted_job_id"),
        job.get("source_job_id"),
    )
    return url


def should_show_apply_button(
    job: dict[str, Any],
    *,
    origin: Optional[str] = None,
) -> bool:
    """Return True only if *job* has a trusted apply URL.

    Convenience wrapper for UI composers.  Callers that serve
    recent_search_matches must pass ``origin='recent_context'``.
    """
    return resolve_trusted_apply_url(job, origin=origin) is not None


def safe_no_apply_link_message(job: dict[str, Any]) -> str:
    """Return a user-safe message when no trusted apply link is available.

    Never leaks internal error codes such as ``no_apply_link_available``.
    """
    title = job.get("title") or job.get("job_title") or "this job"
    company = job.get("company") or job.get("company_name") or ""
    label = f"{title} at {company}" if company else title
    return (
        f"I don't have a verified apply link for {label} yet. "
        "I can save it to your pipeline or help you search "
        "the company career page."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_trusted_provenance(job: dict[str, Any]) -> bool:
    """Return True if the job record carries at least one trusted provenance marker.

    This function is called ONLY after Gate 0 has confirmed the record
    did NOT arrive from an untrusted channel.  Therefore
    ``provider + source_backed=True`` here genuinely means the ingestion
    layer set both fields, not that an LLM payload claimed them.

    Trusted markers
    ---------------
    +-----------------------+-------------------------------------------------+
    | Field                 | Set by                                          |
    +=======================+=================================================+
    | persisted_job_id      | DB upsert in jobs_repo after source ingest      |
    | source_job_id         | Provider / scraper ingest (e.g. JSearch)        |
    | provider + bool flag  | Ingestion layer sets source_backed=True         |
    +-----------------------+-------------------------------------------------+

    ``job_id`` alone is NOT trusted: it can be synthesised by the LLM,
    copied from chat context, or inferred from ordinal references in the
    conversation.
    """
    # Condition A: persisted by DB write path
    if job.get("persisted_job_id"):
        return True

    # Condition B: source identifier from provider / scraper
    if job.get("source_job_id"):
        return True

    # Condition C: provider-attributed AND explicitly marked source-backed.
    # Both fields must be truthy.  Crucially, this branch is only reached
    # after Gate 0 has confirmed origin is not in UNTRUSTED_ORIGINS, so
    # a spoofed LLM payload can never reach this check.
    provider = job.get("provider")
    source_backed = job.get("source_backed")
    if provider and source_backed is True:
        return True

    return False

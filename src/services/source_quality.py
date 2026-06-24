"""Source quality helpers for Rico job data.

This module provides lightweight, synchronous predicates used throughout
the pipeline to assess whether a job record's metadata (URL, provider,
source fields) is trustworthy enough to surface in the UI.

Phase-0 additions
-----------------
* ``is_placeholder_url`` — detects known fake / templated apply URLs.
  Used by :mod:`src.services.job_link_trust` as Gate 2 of the trust chain.
* ``is_demo_job_id`` — detects obviously synthetic job identifiers.

Nothing in this module makes network calls or hits the DB.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Placeholder / fake URL detection
# ---------------------------------------------------------------------------

# Indeed job-key placeholder patterns produced by LLMs:
#   https://www.indeed.com/viewjob?jk=abc123
#   https://www.indeed.com/viewjob?jk=def456
#   jk=abc123  jk=xyz789  jk=test123  jk=job123
# The pattern matches any  jk=  value that is purely alphanumeric and
# short (<=16 chars) — real Indeed jk values are 16-char hex strings,
# so a different heuristic (sequential letters/numbers) flags fake ones.
_INDEED_PLACEHOLDER_JK_RE = re.compile(
    r"[?&]jk=(?P<key>[a-z]{2,8}\d{2,6})(?:&|$|\s)",
    re.IGNORECASE,
)

# Generic placeholder token patterns anywhere in a URL:
#   /jobs/abc123, /jobs/def456, /apply/job001, /job/job-123
_GENERIC_PLACEHOLDER_PATH_RE = re.compile(
    r"/(?:jobs?|apply|view|listing)/"
    r"(?:abc|def|xyz|foo|bar|test|sample|example|job|fake|dummy)\d{0,6}"
    r"(?:/|$|\?)",
    re.IGNORECASE,
)

# Sequential numeric LinkedIn job IDs as full URL check (cross-reference
# with job_link_trust for the gate; this predicate is the pattern half).
_SEQUENTIAL_LINKEDIN_RE = re.compile(
    r"linkedin\.com/jobs/view/(?P<id>\d{1,7})(?:/|$|\?)",
    re.IGNORECASE,
)

# Hard-coded localhost / example / placeholder hostnames.
_PLACEHOLDER_HOST_RE = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|example\.com|test\.com|placeholder\.com)",
    re.IGNORECASE,
)

# Template variable tokens: {{url}}, ${apply_link}, [APPLY_URL], <link>
_TEMPLATE_TOKEN_RE = re.compile(
    r"\{\{[^}]+\}\}"  # Handlebars: {{url}}
    r"|\$\{[^}]+\}"  # JS template: ${url}
    r"|\[[A-Z_]{4,}\]"  # Uppercase bracket: [APPLY_URL]
    r"|<[a-z_]+_(?:url|link)>",  # XML-style: <apply_url>
    re.IGNORECASE,
)


def is_placeholder_url(url: Optional[str]) -> bool:
    """Return True if *url* looks like a placeholder or LLM-generated fake.

    This is a heuristic check — it errs on the side of rejection.  A URL
    that passes this check is NOT automatically trusted; the full trust
    chain in :func:`src.services.job_link_trust.resolve_trusted_apply_url`
    must still be satisfied.

    Parameters
    ----------
    url:
        Raw URL string to evaluate.  ``None`` / empty string returns True
        (treated as placeholder/missing).

    Returns
    -------
    bool
        ``True``  → URL is fake / placeholder → do NOT show "View & Apply".
        ``False`` → URL passed heuristic checks → continue to provenance gate.
    """
    if not url or not isinstance(url, str):
        return True  # missing is treated as placeholder
    url = url.strip()
    if not url:
        return True

    if _PLACEHOLDER_HOST_RE.search(url):
        return True
    if _TEMPLATE_TOKEN_RE.search(url):
        return True
    if _INDEED_PLACEHOLDER_JK_RE.search(url):
        return True
    if _GENERIC_PLACEHOLDER_PATH_RE.search(url):
        return True

    # Sequential LinkedIn: IDs below 10 000 000 are too small to be real.
    m = _SEQUENTIAL_LINKEDIN_RE.search(url)
    if m and int(m.group("id")) < 10_000_000:
        return True

    return False


def is_demo_job_id(job_id: Optional[str]) -> bool:
    """Return True if *job_id* looks like a demo / LLM-generated identifier.

    Examples of fake IDs produced by LLMs:
        job_1, job_2, job-001, abc123, demo_job_5
    """
    if not job_id or not isinstance(job_id, str):
        return False
    jid = job_id.strip().lower()
    # Short generic patterns: "job1", "job_1", "job-001", "demo_job_5"
    if re.fullmatch(r"(?:job|demo|fake|test|sample)[_-]?\d{1,5}", jid):
        return True
    # Pure short alphanumeric <= 8 chars with no real entropy signal
    if re.fullmatch(r"[a-z]{2,5}\d{1,5}", jid) and len(jid) <= 8:
        return True
    return False


# ---------------------------------------------------------------------------
# Source-tier classification (pre-existing logic, preserved)
# ---------------------------------------------------------------------------

# Ordered list of tier labels from best (0) to weakest (4).
SOURCE_TIERS: list[str] = [
    "verified_scrape",  # Direct scrape with job ID confirmed from ATS
    "api_ingestion",    # Provider API (JSearch, Adzuna, etc.)
    "aggregator",       # Job board aggregator without direct ATS link
    "llm_enriched",     # LLM-enriched record — no guarantee of accuracy
    "unknown",          # No source metadata at all
]


def classify_source_tier(job: dict) -> str:
    """Return the source tier string for *job*.

    Tier ordering from most to least trustworthy:
        verified_scrape > api_ingestion > aggregator > llm_enriched > unknown
    """
    provider = (job.get("provider") or "").lower()
    source_backed: bool = bool(job.get("source_backed"))
    source_job_id: Optional[str] = job.get("source_job_id")
    persisted: Optional[str] = job.get("persisted_job_id")

    if persisted and source_backed:
        return "verified_scrape"
    if source_job_id and provider:
        return "api_ingestion"
    if provider and not source_job_id:
        return "aggregator"
    if job.get("llm_generated") or job.get("origin") == "llm":
        return "llm_enriched"
    return "unknown"

"""source_quality.py — Domain-based job source quality classification.

Classifies job URLs without network calls using known domain patterns.
Used in _format_match to annotate verification_status before sending
matches to the frontend.

Status values:
    live_verified        — trusted ATS / employer career page
    login_required       — known login-wall domains (GulfTalent, etc.)
    rate_limited         — domains known for 429 responses (trabajo.org, etc.)
    aggregator_untrusted — spammy or low-quality aggregators
    needs_source_verification — unknown domain; frontend shows "Needs verification"

Phase-0 additions (additive — no existing exports changed)
-----------------------------------------------------------
* ``is_placeholder_url`` — detects known fake / templated apply URLs.
  Used by :mod:`src.services.job_link_trust` as Gate 2 of the trust chain.
* ``is_demo_job_id``    — detects obviously synthetic job identifiers.
* ``classify_source_tier`` — returns ordered tier label for a job dict.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Domain classification tables  (pre-existing, must not be removed)
# ---------------------------------------------------------------------------

# Employer / ATS platforms — high-quality, direct apply
_TRUSTED_DOMAINS: frozenset[str] = frozenset(
    {
        # ATS platforms (employer-hosted)
        "greenhouse.io",
        "lever.co",
        "workday.com",
        "myworkdayjobs.com",
        "smartrecruiters.com",
        "taleo.net",
        "icims.com",
        "bamboohr.com",
        "jobvite.com",
        "recruitee.com",
        "ashbyhq.com",
        "rippling.com",
        # Major UAE/GCC job boards
        "naukrigulf.com",
        "bayt.com",
        "gulftalent.com",  # overridden below for login-wall check
        "linkedin.com",
        "indeed.com",
        "dubizzle.com",
        "khaleejiesque.com",
        "monstergulf.com",
    }
)

# Employer career-page subdomains (.careers.acme.com, careers.acme.com)
_CAREER_SUBSTRINGS: tuple[str, ...] = (
    "careers.",
    ".careers.",
    "jobs.",
    ".jobs.",
    "recruit.",
    ".recruit.",
    "talent.",
    ".talent.",
)

# Known login-wall domains — apply link leads to a login form, not the job
_LOGIN_REQUIRED_DOMAINS: frozenset[str] = frozenset(
    {
        "gulftalent.com",   # login-loop redirect
        "glassdoor.com",    # login gate in MENA
        "monster.com",
        "monster.com.qa",
        "careers.monster.com",
    }
)

# Known rate-limited / frequent-429 domains
_RATE_LIMITED_DOMAINS: frozenset[str] = frozenset(
    {
        "trabajo.org",
        "ae.trabajo.org",
        "qa.trabajo.org",
        "sa.trabajo.org",
        "jobtome.com",
        "trovit.com",
    }
)

# Spammy aggregators — index stale / redirect jobs, no direct apply
_AGGREGATOR_UNTRUSTED_DOMAINS: frozenset[str] = frozenset(
    {
        "jooble.org",
        "noknokjobs.com",
        "jobsora.com",
        "jobisite.com",
        "jora.com",
        "adzuna.com",
        "ziprecruiter.com",   # limited in UAE
        "simplyhired.com",
        "totaljobs.com",
        "cvlibrary.co.uk",
        "careerjet.com",
        "jobrapido.com",
        "jobleads.com",       # 404s reported in production
        "neuvoo.com",
        "talent.com",         # redirects to neuvoo; not an employer page
        "joblist.com",
    }
)


# ---------------------------------------------------------------------------
# Pre-existing public functions  (must not be removed or renamed)
# ---------------------------------------------------------------------------

def is_google_intermediary(url: str) -> bool:
    """True when *url* is a Google Jobs search/intermediary page, not a direct apply URL.

    Google Jobs links (jobs.google.com or google.com/search?…) open a Google
    search results page that lists multiple employers — they are not direct
    apply pages and should not be shown as the primary "Apply" action.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().lstrip("www.")
        if hostname == "jobs.google.com":
            return True
        if hostname == "google.com" and "/search" in parsed.path:
            return True
    except Exception:
        pass
    return False


@lru_cache(maxsize=512)
def classify_url(url: str) -> str:
    """Return a source-quality status string for the given URL.

    Uses domain-table lookup only — no network calls.  Results are cached.

    Returns one of:
        "live_verified"            ATS / trusted employer career page
        "login_required"           Known login-wall domain
        "rate_limited"             Known 429 / unreliable domain
        "aggregator_untrusted"     Spammy aggregator
        "needs_source_verification" Unknown domain (default)
    """
    if not url:
        return "needs_source_verification"

    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return "needs_source_verification"

    hostname = hostname.lower().lstrip("www.")

    # Specific overrides take priority over generic trusted list
    if _matches_domain(hostname, _LOGIN_REQUIRED_DOMAINS):
        return "login_required"

    if _matches_domain(hostname, _RATE_LIMITED_DOMAINS):
        return "rate_limited"

    if _matches_domain(hostname, _AGGREGATOR_UNTRUSTED_DOMAINS):
        return "aggregator_untrusted"

    # Trusted ATS or employer career page
    if _matches_domain(hostname, _TRUSTED_DOMAINS):
        return "live_verified"

    # Heuristic: career/jobs subdomain patterns
    if any(sub in hostname for sub in _CAREER_SUBSTRINGS):
        return "live_verified"

    return "needs_source_verification"


def _matches_domain(hostname: str, domain_set: frozenset[str]) -> bool:
    """True if hostname equals or is a subdomain of any domain in the set."""
    for domain in domain_set:
        if hostname == domain or hostname.endswith("." + domain):
            return True
    return False


# Statuses that must never be offered as the alternate apply link
_BAD_ALTERNATE_STATUSES: frozenset[str] = frozenset(
    {"login_required", "rate_limited", "aggregator_untrusted"}
)


def pick_best_alternate_apply_link(primary_url: str, apply_options: object) -> str:
    """Return the most trustworthy alternate apply link from JSearch's
    ``apply_options`` array, or "" when none qualifies.

    JSearch returns one ``job_apply_link`` plus an ``apply_options`` list of
    the same posting on other publishers (``{"publisher", "apply_link",
    "is_direct"}``). When the primary link is login-walled or rate-limited,
    one of those mirrors is often directly usable — surfacing it keeps the
    card's fallback chain honest instead of dead-ending at "Link unavailable".

    Truthfulness rules (never invent a URL):
      * only provider-returned links are considered
      * skip empty links, the primary itself, and Google intermediaries
      * skip links classified login_required / rate_limited / aggregator_untrusted
      * prefer ``is_direct`` options (employer-hosted apply page), then
        ``live_verified`` domains (trusted ATS / major job boards)
      * unknown domains are NOT promoted — trust must be positive
    """
    if not isinstance(apply_options, list):
        return ""
    primary = (primary_url or "").strip()
    direct_pick = ""
    trusted_pick = ""
    for option in apply_options:
        if not isinstance(option, dict):
            continue
        link = str(option.get("apply_link") or "").strip()
        if not link or link == primary or is_google_intermediary(link):
            continue
        status = classify_url(link)
        if status in _BAD_ALTERNATE_STATUSES:
            continue
        if option.get("is_direct") is True and not direct_pick:
            direct_pick = link
        elif status == "live_verified" and not trusted_pick:
            trusted_pick = link
    return direct_pick or trusted_pick


# ---------------------------------------------------------------------------
# Company name quality classification  (pre-existing, must not be removed)
# ---------------------------------------------------------------------------

# Anonymous / placeholder company names that indicate the real employer is hidden
_ANONYMOUS_COMPANY_NAMES: frozenset[str] = frozenset({
    "confidential",
    "unknown",
    "n/a",
    "na",
    "not disclosed",
    "not specified",
    "undisclosed",
    "anonymous",
    "employer confidential",
    "client confidential",
    "withheld",
    "unnamed",
    "unknown company",
    "unknown employer",
})

# Low-quality aggregator / spam company names
_LOW_QUALITY_COMPANY_NAMES: frozenset[str] = frozenset({
    "jobs for humanity",
    "jobs for humanity uae",
    "theuaejobs",
    "talentmate",
    "private company",
    "leading company",
    "reputable company",
    "well known company",
    "multinational company",
    "leading organization",
    "leading organisation",
    "a leading company",
    "a reputable company",
    "a leading organization",
    "a well known company",
})


@lru_cache(maxsize=512)
def classify_company(company: str) -> str:
    """Return a quality label for a company name string.

    Returns one of:
        "ok"          — looks like a real named employer
        "anonymous"   — placeholder (Confidential, Unknown, N/A, …)
        "low_quality" — known spam aggregator or vague filler phrase
    """
    if not company or not company.strip():
        return "anonymous"
    normalized = company.strip().lower()
    if normalized in _ANONYMOUS_COMPANY_NAMES:
        return "anonymous"
    if normalized in _LOW_QUALITY_COMPANY_NAMES:
        return "low_quality"
    # Substring heuristics: "confidential" or "unknown employer" anywhere in name
    if "confidential" in normalized or "unknown employer" in normalized:
        return "anonymous"
    return "ok"


def is_low_quality_company(company: str) -> bool:
    """True when the company name signals an anonymous or low-quality posting."""
    return classify_company(company) in ("anonymous", "low_quality")


# ---------------------------------------------------------------------------
# Phase-0 additions — Placeholder / fake URL detection
# (additive; no existing exports changed)
# ---------------------------------------------------------------------------

# Indeed job-key placeholder patterns produced by LLMs:
#   https://www.indeed.com/viewjob?jk=abc123
#   https://www.indeed.com/viewjob?jk=def456
# The pattern matches jk= values that are short alpha+digit combos, not
# real 16-char hex keys.
_INDEED_PLACEHOLDER_JK_RE = re.compile(
    r"[?&]jk=(?P<key>[a-z]{2,8}\d{2,6})(?:&|$|\s)",
    re.IGNORECASE,
)

# Generic placeholder token patterns anywhere in a URL
_GENERIC_PLACEHOLDER_PATH_RE = re.compile(
    r"/(?:jobs?|apply|view|listing)/"
    r"(?:abc|def|xyz|foo|bar|test|sample|example|job|fake|dummy)\d{0,6}"
    r"(?:/|$|\?)",
    re.IGNORECASE,
)

# Sequential numeric LinkedIn job IDs as full URL check
_SEQUENTIAL_LINKEDIN_RE = re.compile(
    r"linkedin\.com/jobs/view/(?P<id>\d{1,7})(?:/|$|\?)",
    re.IGNORECASE,
)

# Hard-coded localhost / example / placeholder hostnames
_PLACEHOLDER_HOST_RE = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|example\.com|test\.com|placeholder\.com)",
    re.IGNORECASE,
)

# Template variable tokens: {{url}}, ${apply_link}, [APPLY_URL], <link>
_TEMPLATE_TOKEN_RE = re.compile(
    r"\{\{[^}]+\}\}"   # Handlebars: {{url}}
    r"|\$\{[^}]+\}"   # JS template: ${url}
    r"|\[[A-Z_]{4,}\]"  # Uppercase bracket: [APPLY_URL]
    r"|<[a-z_]+_(?:url|link)>",  # XML-style: <apply_url>
    re.IGNORECASE,
)


def is_placeholder_url(url: Optional[str]) -> bool:
    """Return True if *url* looks like a placeholder or LLM-generated fake.

    This is Gate 2 in the trust chain (see job_link_trust.py).  A URL
    that passes this check is NOT automatically trusted; the full trust
    chain must still be satisfied.

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

    Examples of fake IDs produced by LLMs:  job_1, job_2, job-001, abc123
    """
    if not job_id or not isinstance(job_id, str):
        return False
    jid = job_id.strip().lower()
    if re.fullmatch(r"(?:job|demo|fake|test|sample)[_-]?\d{1,5}", jid):
        return True
    if re.fullmatch(r"[a-z]{2,5}\d{1,5}", jid) and len(jid) <= 8:
        return True
    return False


# ---------------------------------------------------------------------------
# Phase-0: Source-tier classification (additive)
# ---------------------------------------------------------------------------

SOURCE_TIERS: list[str] = [
    "verified_scrape",  # Direct scrape with job ID confirmed from ATS
    "api_ingestion",    # Provider API (JSearch, Adzuna, etc.)
    "aggregator",       # Job board aggregator without direct ATS link
    "llm_enriched",     # LLM-enriched record — no guarantee of accuracy
    "unknown",          # No source metadata at all
]


def classify_source_tier(job: dict) -> str:  # type: ignore[type-arg]
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

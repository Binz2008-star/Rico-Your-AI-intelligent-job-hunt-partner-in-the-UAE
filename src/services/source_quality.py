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
"""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Domain classification tables
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
# Company name quality classification
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

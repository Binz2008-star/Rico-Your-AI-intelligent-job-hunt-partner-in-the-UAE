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

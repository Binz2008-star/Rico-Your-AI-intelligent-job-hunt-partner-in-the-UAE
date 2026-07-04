"""role_relevance.py — Requested-role relevance scoring for explicit-title search.

When a user explicitly asks for a role/title in chat (e.g. "ESG Manager jobs"),
the *requested* title must be the primary relevance signal for what gets shown —
independent of whatever roles happen to be saved on their profile. A stale or
empty profile must never pull unrelated jobs to the top of an explicit search.

This module is intentionally small, pure, and provider/DB-agnostic:

    * ``score_role_relevance(title, requested_role)`` → 0..100 for one job title.
    * ``annotate_role_relevance(jobs, requested_role)`` stamps each job dict with
      a ``role_relevance_score`` (primary ranking signal for the caller).
    * ``RELEVANCE_FLOOR`` is the minimum score for a job to count as a real match.

It complements the CV-driven taxonomy in ``src/role_normalization.py`` with a
job-title-oriented role-family map so synonyms match across a family (e.g.
"Sustainability" for an "ESG" query, "EHS"/"Safety" for an "HSE" query) while
unrelated families (Operations noise for an ESG query) score zero and are
filtered out by the caller's relevance floor.

The map is a global, product-wide taxonomy. It is never tuned to one user,
one account, one profile, or one sampled dataset.
"""

from __future__ import annotations

import re
from typing import Any

# A job must reach this score to be treated as a genuine match for the
# requested role. Below it, the caller shows an honest "no strong matches /
# broaden?" response instead of padding the card with irrelevant jobs.
RELEVANCE_FLOOR = 50

_TOKEN_RE = re.compile(r"[a-z0-9+#&]+")

# Generic seniority/format words carry no role identity on their own. "Manager"
# alone must not make a job relevant, or every management listing would match.
_GENERIC_ROLE_TOKENS = {
    "assistant",
    "associate",
    "consultant",
    "coordinator",
    "director",
    "executive",
    "head",
    "junior",
    "lead",
    "manager",
    "officer",
    "principal",
    "senior",
    "specialist",
    "staff",
    "supervisor",
    "the",
    "of",
    "and",
    "for",
    "in",
    "a",
}

# Role-family term sets. Membership is by substring on the lowercased title/role
# so multi-word signals ("supply chain", "iso 14001") work without tokenizing.
# Families are deliberately broad enough to unite real synonyms and narrow
# enough that unrelated families do not bleed together.
ROLE_FAMILIES: dict[str, set[str]] = {
    "esg_environmental": {
        "esg", "environment", "environmental", "sustainability", "sustainable",
        "climate", "carbon", "net zero", "leed", "iso 14001", "green",
        "decarbon", "emissions",
    },
    "hse_safety": {
        "hse", "ehs", "hsse", "qhse", "safety", "occupational health",
        "nebosh", "iosh", "osha", "iso 45001", "fire safety", "loss prevention",
        "health and safety", "hse&s",
    },
    "compliance_audit": {
        "compliance", "audit", "regulatory", "governance", "risk", "aml",
        "kyc", "sox", "internal control", "assurance",
    },
    "quality": {
        "quality", "qa", "qc", "iso 9001", "six sigma", "lean", "inspection",
        "quality assurance", "quality control",
    },
    "finance_accounting": {
        "account", "accountant", "accounting", "finance", "financial",
        "bookkeep", "payable", "receivable", "ledger", "general ledger",
        "tax", "treasury", "fp&a", "controller", "auditor", "payroll finance",
    },
    "operations": {
        "operation", "operations", "ops", "logistics", "supply chain",
        "warehouse", "production", "facility", "facilities", "fleet",
        "dispatch", "distribution",
    },
    "sales_marketing": {
        "sales", "business development", "marketing", "brand", "commercial",
        "account executive", "key account", "digital marketing", "seo",
    },
    "hr_people": {
        "human resources", "recruit", "recruiter", "talent", "people",
        "payroll", "hr ", "hrbp", "learning and development",
    },
    "it_software": {
        "software", "developer", "it ", "data", "devops", "cloud",
        "full stack", "backend", "frontend", "programmer", "qa engineer",
        "systems", "network", "cyber", "security engineer",
    },
    "procurement": {
        "procurement", "purchasing", "buyer", "sourcing", "vendor",
        "category manager",
    },
    "admin_office": {
        "administrative", "secretary", "receptionist", "clerk", "office manager",
        "personal assistant", "front desk",
    },
    "engineering_discipline": {
        "civil engineer", "mechanical engineer", "electrical engineer", "mep",
        "structural", "hvac", "piping", "site engineer", "process engineer",
        "chemical engineer", "instrumentation",
    },
}


def _meaningful_tokens(role: str) -> set[str]:
    """Identity-bearing tokens of a role (drops generic seniority/format words)."""
    return {
        tok
        for tok in _TOKEN_RE.findall(role.lower())
        if len(tok) >= 2 and tok not in _GENERIC_ROLE_TOKENS
    }


def families_for(text: str) -> set[str]:
    """Return the role families whose terms appear in ``text``."""
    low = f" {text.lower()} "
    hits: set[str] = set()
    for family, terms in ROLE_FAMILIES.items():
        if any(term in low for term in terms):
            hits.add(family)
    return hits


def score_role_relevance(title: str, requested_role: str) -> int:
    """Score a job title's relevance to the explicitly requested role (0..100).

    Priority order (requested role is always the primary signal):
      100  the full requested-role phrase appears in the title
       90  every identity-bearing token of the requested role is in the title
       60  some (not all) identity-bearing tokens are in the title
       55  same role family (synonym match, e.g. Sustainability ↔ ESG)
        0  unrelated
    """
    title_l = (title or "").strip().lower()
    role_l = (requested_role or "").strip().lower()
    if not title_l or not role_l:
        return 0

    if role_l in title_l:
        return 100

    role_tokens = _meaningful_tokens(role_l)
    title_tokens = set(_TOKEN_RE.findall(title_l))
    if role_tokens:
        hits = role_tokens & title_tokens
        if hits == role_tokens:
            return 90
        if hits:
            return 60

    req_families = families_for(role_l)
    if req_families and (req_families & families_for(title_l)):
        return 55

    return 0


def annotate_role_relevance(
    jobs: list[dict[str, Any]], requested_role: str
) -> list[dict[str, Any]]:
    """Stamp each job with ``role_relevance_score`` against the requested role.

    Mutates and returns the same list. Job title is read from ``title`` with a
    ``job_title`` fallback so both provider and legacy-pipeline shapes work.
    """
    for job in jobs:
        title = str(job.get("title") or job.get("job_title") or "")
        job["role_relevance_score"] = score_role_relevance(title, requested_role)
    return jobs

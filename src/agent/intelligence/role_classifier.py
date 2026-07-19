"""src/agent/intelligence/role_classifier.py

Three-tier role classification for Rico chat.

Given user text and their profile, determines:
  - "profile_relevant"       → search directly
  - "known_but_off_profile"  → ask confirmation before searching
  - "unknown"                → reject / redirect to profile suggestions

Uses ``src/data/job_role_taxonomy.json`` for real-role validation and the
user's CV/profile data for relevance scoring.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

RoleClassification = Literal["profile_relevant", "known_but_off_profile", "unknown"]

_TAXONOMY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "job_role_taxonomy.json",
)

_PROFILE_RELEVANCE_THRESHOLD = 55  # fuzzy match score for profile relevance


@lru_cache(maxsize=1)
def _load_taxonomy() -> Dict[str, Any]:
    """Load and cache the job role taxonomy file."""
    try:
        with open(_TAXONOMY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Failed to load job role taxonomy: %s", e)
        return {"aliases": {}, "families": {}}


def _get_all_known_roles() -> Tuple[Dict[str, str], Set[str]]:
    """Return (alias_map, canonical_role_set) from taxonomy."""
    tax = _load_taxonomy()
    aliases: Dict[str, str] = {k.lower(): v for k, v in tax.get("aliases", {}).items()}
    canonical: Set[str] = set(tax.get("families", {}).keys())
    # Also add canonical roles lowered to alias map for direct lookup
    for role in canonical:
        aliases.setdefault(role.lower(), role)
    return aliases, canonical


def resolve_taxonomy_role(text: str) -> Optional[str]:
    """Resolve text to a canonical role via taxonomy aliases.

    Returns the canonical role name or None if not found.
    """
    aliases, _ = _get_all_known_roles()
    lower = text.strip().lower()

    # Direct alias match
    if lower in aliases:
        return aliases[lower]

    # Try partial/fuzzy match against aliases
    if len(lower) >= 3:
        best_score = 0
        best_role = None
        for alias, canonical in aliases.items():
            score = fuzz.ratio(lower, alias)
            if score > best_score and score >= 75:
                best_score = score
                best_role = canonical
        if best_role:
            return best_role

    return None


def _extract_profile_terms(profile: Any) -> Set[str]:
    """Extract all searchable terms from a user profile for relevance matching."""
    terms: Set[str] = set()
    if profile is None:
        return terms

    def _get(key: str) -> Any:
        if isinstance(profile, dict):
            return profile.get(key)
        return getattr(profile, key, None)

    # Target roles
    for role in (_get("target_roles") or []):
        terms.add(str(role).lower())

    # Skills
    for skill in (_get("skills") or []):
        terms.add(str(skill).lower())

    # Industries
    for ind in (_get("industries") or []):
        terms.add(str(ind).lower())

    # Current/previous titles (if available)
    current = _get("current_title") or _get("current_job_title") or ""
    if current:
        terms.add(str(current).lower())

    return terms


def _role_family_terms(canonical_role: str) -> Set[str]:
    """Get family terms for a canonical role from taxonomy."""
    tax = _load_taxonomy()
    families = tax.get("families", {})
    terms = set()
    family = families.get(canonical_role, [])
    for t in family:
        terms.add(t.lower())
    terms.add(canonical_role.lower())
    return terms


def cross_family_term_counts() -> Dict[str, int]:
    """How many distinct role families mention each single-word family term.

    Data-driven ambiguity signal for relevance gating: a term shared by many
    families (audit=6, compliance=5, environment=5, risk=3 in the current
    taxonomy) is weak cross-domain vocabulary, while a term concentrated in
    one or two families (sustainability=2, inspection=2, quality=1) is
    discriminating evidence for its domain."""
    tax = _load_taxonomy()
    counts: Dict[str, int] = {}
    for _role, terms in (tax.get("families") or {}).items():
        for t in {str(x).strip().lower() for x in (terms or [])}:
            if t and " " not in t:
                counts[t] = counts.get(t, 0) + 1
    return counts


def role_alias_phrases(canonical_role: str) -> Set[str]:
    """Lowered alias texts that resolve to *canonical_role* in the taxonomy,
    plus the canonical text itself — e.g. {"safety manager", "hse manager"}
    for "HSE Manager". Lets a relevance gate keep genuinely-equivalent titles
    reachable without leaning on cross-family single words. Data-driven from
    job_role_taxonomy.json; empty for blank/unknown roles."""
    canonical = (canonical_role or "").strip()
    if not canonical:
        return set()
    tax = _load_taxonomy()
    out: Set[str] = {canonical.lower()}
    for alias, canon in (tax.get("aliases") or {}).items():
        if str(canon) == canonical:
            out.add(str(alias).strip().lower())
    return {a for a in out if a}


def classify_role_candidate(
    text: str,
    profile: Any,
) -> Tuple[RoleClassification, Optional[str]]:
    """Classify a role candidate against user profile.

    Args:
        text: The role text to classify (e.g., "accountant", "hse manager").
        profile: User profile object or dict.

    Returns:
        Tuple of (classification, canonical_role_or_None).
        - ("profile_relevant", "HSE Officer")  → search directly
        - ("known_but_off_profile", "Accountant") → ask confirmation
        - ("unknown", None) → reject / redirect
    """
    # Step 1: Resolve role from taxonomy
    canonical = resolve_taxonomy_role(text)

    if canonical is None:
        logger.info("role_classify: unknown role text=%r", text)
        return "unknown", None

    # Step 2: Check profile relevance
    profile_terms = _extract_profile_terms(profile)

    if not profile_terms:
        # No profile data — treat known role as off-profile (ask confirmation)
        logger.info(
            "role_classify: known_but_off_profile (no profile data) role=%s", canonical
        )
        return "known_but_off_profile", canonical

    # Check if role or its family terms overlap with profile
    role_terms = _role_family_terms(canonical)
    overlap = role_terms & profile_terms

    if overlap:
        logger.info(
            "role_classify: profile_relevant role=%s overlap=%s", canonical, overlap
        )
        return "profile_relevant", canonical

    # Fuzzy match canonical role against profile target roles
    target_roles = []
    if isinstance(profile, dict):
        target_roles = profile.get("target_roles", []) or []
    else:
        target_roles = getattr(profile, "target_roles", []) or []

    for tr in target_roles:
        score = fuzz.ratio(canonical.lower(), str(tr).lower())
        if score >= _PROFILE_RELEVANCE_THRESHOLD:
            logger.info(
                "role_classify: profile_relevant (fuzzy) role=%s target=%s score=%d",
                canonical, tr, score,
            )
            return "profile_relevant", canonical

    logger.info("role_classify: known_but_off_profile role=%s", canonical)
    return "known_but_off_profile", canonical

"""role_normalization.py — Normalize target roles based on CV evidence.

Prevents broad standalone roles (Engineer, Manager, etc.) from being saved.
Replaces them with specific, CV-supported roles based on skills and experience.

Example:
    Input:  skills=["hse", "iso 14001", "environmental"], target_roles=["Engineer", "Manager"]
    Output: ["Environmental Manager", "HSE Manager", "QHSE Manager", "Environmental Compliance Manager"]
"""

from __future__ import annotations

from typing import Any


# Broad roles that should not be saved standalone without qualification
_BROAD_STANDALONE_ROLES = {
    "engineer",
    "manager",
    "specialist",
    "consultant",
    "officer",
    "operations lead",
    "operations manager",
}


# Skill family mappings to specific target roles
_SKILL_FAMILY_ROLES = {
    "environmental_esg": [
        "Environmental Manager",
        "ESG Manager",
        "Environmental Compliance Manager",
        "Sustainability Manager",
    ],
    "hse_qhse": [
        "HSE Manager",
        "QHSE Manager",
        "Safety Manager",
        "Environmental Manager",
    ],
    "compliance_audit": [
        "Compliance Manager",
        "Audit Manager",
        "Risk & Compliance Officer",
    ],
    "iso_quality": [
        "ISO 14001 Lead Auditor",
        "Quality Manager",
        "QA Manager",
    ],
}


# Skill keywords that map to families
_SKILL_FAMILY_SIGNALS = {
    "environmental_esg": {
        "environmental management",
        "esg",
        "sustainability",
        "iso 14001",
        "carbon footprint",
        "environmental",
        "green building",
        "leed",
        "environmental compliance",
        "climate",
        "net zero",
    },
    "hse_qhse": {
        "hse",
        "safety",
        "ehs",
        "qhse",
        "fire safety",
        "risk assessment",
        "permit to work",
        "incident investigation",
        "nebosh",
        "iosh",
        "osha",
        "safety officer",
        "safety management",
        "iso 45001",
    },
    "compliance_audit": {
        "compliance",
        "audit",
        "internal audit",
        "regulatory",
        "governance",
        "risk management",
        "sox",
        "anti-money laundering",
        "aml",
        "kyc",
        "regulatory affairs",
        "policy",
    },
    "iso_quality": {
        "iso 9001",
        "iso 45001",
        "iso 14001",
        "quality",
        "qc",
        "quality control",
        "quality assurance",
        "six sigma",
        "lean",
        "kaizen",
        "quality management",
        "iso",
        "qa",
    },
}


def normalize_target_roles(
    target_roles: list[str] | None,
    skills: list[str] | None,
    years_experience: float | None = None,
    current_role: str | None = None,
) -> list[str]:
    """Normalize target roles based on CV evidence.

    Args:
        target_roles: Current target roles from profile
        skills: User's skills
        years_experience: Years of experience
        current_role: Current job title

    Returns:
        Normalized list of specific target roles. Broad standalone roles are
        replaced with CV-supported specific roles. If no CV evidence exists,
        returns empty list (better to have no roles than bad ones).
    """
    if not target_roles:
        # If no target roles, infer from skills
        return _infer_roles_from_skills(skills, years_experience, current_role)

    # Check if target_roles contain broad standalone roles
    has_broad_roles = any(
        role.lower().strip() in _BROAD_STANDALONE_ROLES
        for role in target_roles
        if role
    )

    if not has_broad_roles:
        # No broad roles, return as-is
        return [r for r in target_roles if r]

    # Has broad roles - replace with CV-supported specific roles
    inferred = _infer_roles_from_skills(skills, years_experience, current_role)
    if inferred:
        return inferred

    # No CV evidence to infer specific roles - filter out broad ones
    return [
        role
        for role in target_roles
        if role and role.lower().strip() not in _BROAD_STANDALONE_ROLES
    ]


def _infer_roles_from_skills(
    skills: list[str] | None,
    years_experience: float | None = None,
    current_role: str | None = None,
) -> list[str]:
    """Infer specific target roles from skills and experience."""
    if not skills:
        return []

    skill_lower = [s.lower() for s in (skills or [])]
    current_role_lower = current_role.lower() if current_role else None

    # Detect skill families
    family_hits: dict[str, int] = {}
    for skill in skill_lower:
        for family, signals in _SKILL_FAMILY_SIGNALS.items():
            if any(signal in skill for signal in signals):
                family_hits[family] = family_hits.get(family, 0) + 1

    # Check current role for family signals
    if current_role_lower:
        for family, signals in _SKILL_FAMILY_SIGNALS.items():
            if any(signal in current_role_lower for signal in signals):
                family_hits[family] = family_hits.get(family, 0) + 1

    if not family_hits:
        return []

    # Get top families by hit count
    top_families = sorted(family_hits, key=lambda k: -family_hits[k])[:2]

    # Build role list from top families
    roles: list[str] = []
    seen: set[str] = set()

    for family in top_families:
        family_roles = _SKILL_FAMILY_ROLES.get(family, [])
        for role in family_roles:
            if role not in seen:
                roles.append(role)
                seen.add(role)

    # Add Operations Manager - Environmental Services if operations skill present
    if "operations" in skill_lower and any(
        f in top_families for f in ["environmental_esg", "hse_qhse"]
    ):
        if "Operations Manager - Environmental Services" not in seen:
            roles.append("Operations Manager - Environmental Services")

    return roles[:7]  # Limit to top 7 roles


def normalize_profile_updates(updates: dict[str, Any]) -> dict[str, Any]:
    """Normalize target_roles in profile update payload.

    This is a convenience wrapper for use in profile save endpoints.

    Args:
        updates: Profile update dictionary

    Returns:
        Updates dictionary with normalized target_roles
    """
    if "target_roles" not in updates:
        return updates

    normalized = normalize_target_roles(
        target_roles=updates.get("target_roles"),
        skills=updates.get("skills"),
        years_experience=updates.get("years_experience"),
        current_role=updates.get("current_role"),
    )

    updates["target_roles"] = normalized
    return updates


def should_normalize_profile(
    target_roles: list[str] | None,
    skills: list[str] | None = None,
) -> bool:
    """Check if a profile needs normalization (has broad standalone roles).

    Args:
        target_roles: Current target roles
        skills: User's skills (for context)

    Returns:
        True if profile has broad standalone roles that should be normalized
    """
    if not target_roles:
        return False

    has_broad_roles = any(
        role.lower().strip() in _BROAD_STANDALONE_ROLES
        for role in target_roles
        if role
    )

    # Only normalize if we have CV evidence to infer specific roles
    has_cv_evidence = skills and any(
        any(signal in skill.lower() for signal in _SKILL_FAMILY_SIGNALS[family])
        for family in _SKILL_FAMILY_SIGNALS
        for skill in skills
    )

    return has_broad_roles and has_cv_evidence

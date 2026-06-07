"""role_normalization.py — Normalize target roles based on CV evidence.

Prevents broad standalone roles (Engineer, Manager, etc.) from being saved.
Replaces them with specific, CV-supported roles based on skills and experience.

Example:
    Input:  skills=["hse", "iso 14001", "environmental"], target_roles=["Engineer", "Manager"]
    Output: ["Environmental Manager", "HSE Manager", "QHSE Manager", "Environmental Compliance Manager"]
"""

from __future__ import annotations

from typing import Any

# Increment this when normalization logic changes to force re-normalization
NORMALIZATION_VERSION = 2


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

    # Priority families: always include hse_qhse and environmental_esg if they have hits
    priority_families = ["hse_qhse", "environmental_esg"]
    top_families: list[str] = []

    # Add priority families if they have hits
    for family in priority_families:
        if family in family_hits and family not in top_families:
            top_families.append(family)

    # Fill remaining slots with highest-hit families (excluding already-added priority ones)
    remaining_slots = 2 - len(top_families)
    if remaining_slots > 0:
        other_families = sorted(
            [f for f in family_hits if f not in top_families],
            key=lambda k: -family_hits[k]
        )
        top_families.extend(other_families[:remaining_slots])

    # Build role list from top families with round-robin interleaving
    roles: list[str] = []
    seen: set[str] = set()

    # Reserve slot for Operations Manager - Environmental Services if conditions met
    has_ops_manager_slot = (
        "operations" in skill_lower
        and any(f in top_families for f in ["environmental_esg", "hse_qhse"])
    )
    max_roles = 6 if has_ops_manager_slot else 7  # Reserve 1 slot for Ops Manager

    # Round-robin: take one role from each family in sequence
    max_roles_per_family = 4  # Limit to prevent one family from dominating
    family_role_queues: dict[str, list[str]] = {
        family: _SKILL_FAMILY_ROLES.get(family, [])[:max_roles_per_family]
        for family in top_families
    }

    while any(family_role_queues.values()) and len(roles) < max_roles:
        for family in top_families:
            if family_role_queues[family] and len(roles) < max_roles:
                role = family_role_queues[family].pop(0)
                if role not in seen:
                    roles.append(role)
                    seen.add(role)

    # Add Operations Manager - Environmental Services if operations skill present
    if has_ops_manager_slot:
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


# Diverse UAE role suggestions for UI autocomplete
_UAE_ROLE_SUGGESTIONS = [
    "Environmental Manager",
    "HSE Manager",
    "QHSE Manager",
    "Sustainability Manager",
    "ESG Specialist",
    "Operations Manager",
    "Project Manager",
    "QA/QC Manager",
    "Safety Officer",
    "Compliance Manager",
    "Accountant",
    "Sales Executive",
    "HR Officer",
    "Admin Assistant",
    "Customer Service Representative",
    "Procurement Officer",
    "Logistics Coordinator",
    "Civil Engineer",
    "Mechanical Engineer",
    "Electrical Engineer",
]


def get_uae_role_suggestions() -> list[str]:
    """Get diverse UAE role suggestions for UI autocomplete."""
    return _UAE_ROLE_SUGGESTIONS.copy()


def validate_and_normalize_target_roles(
    target_roles: list[str] | None,
) -> list[str]:
    """Validate and normalize target roles for display and save.

    This function:
    - Trims whitespace
    - Removes empty strings
    - Removes duplicates case-insensitively
    - Splits comma-separated role blobs into individual roles
    - Filters out gibberish (very short or random-looking strings)
    - Validates minimum length (2 chars)

    Args:
        target_roles: Raw target roles from user input or profile

    Returns:
        Clean, normalized list of target roles
    """
    if not target_roles:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()

    for role in target_roles:
        # Split comma-separated blobs
        parts = role.split(",") if "," in role else [role]

        for part in parts:
            trimmed = part.strip()
            if not trimmed:
                continue

            # Minimum length check (2 chars)
            if len(trimmed) < 2:
                continue

            # Gibberish check: reject if very short (<4 chars) and not a common role pattern
            # Or if it's a repeated character pattern like "ghhh", "aaaa"
            if len(trimmed) < 4:
                # Very short strings must look like real roles (e.g., "HR", "QA")
                # Reject single-letter or repeated patterns
                if len(set(trimmed.lower())) <= 1:
                    continue

            # Check for repeated character patterns (e.g., "ghhh", "aaaa")
            if len(trimmed) >= 4:
                # If one character appears 75% or more of the time, reject
                char_counts = {c: trimmed.lower().count(c) for c in set(trimmed.lower())}
                max_count = max(char_counts.values())
                if max_count >= len(trimmed) * 0.75:
                    continue

            # Case-insensitive deduplication
            lower = trimmed.lower()
            if lower in seen:
                continue

            seen.add(lower)
            cleaned.append(trimmed)

    return cleaned


def validate_and_normalize_skills(
    skills: list[str] | None,
) -> list[str]:
    """Validate and normalize skills for display and save.

    This function:
    - Trims whitespace
    - Removes empty strings
    - Removes duplicates case-insensitively
    - Splits comma-separated skill blobs into individual skills
    - Filters out gibberish (very short or random-looking strings)
    - Validates minimum length (2 chars)

    Args:
        skills: Raw skills from user input or profile

    Returns:
        Clean, normalized list of skills
    """
    if not skills:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()

    for skill in skills:
        # Split comma-separated blobs
        parts = skill.split(",") if "," in skill else [skill]

        for part in parts:
            trimmed = part.strip()
            if not trimmed:
                continue

            # Minimum length check (2 chars)
            if len(trimmed) < 2:
                continue

            # Gibberish check: reject if very short (<4 chars) and not a common skill pattern
            # Or if it's a repeated character pattern like "ghhh", "aaaa"
            if len(trimmed) < 4:
                # Very short strings must look like real skills (e.g., "HR", "QA", "AI")
                # Reject single-letter or repeated patterns
                if len(set(trimmed.lower())) <= 1:
                    continue

            # Check for repeated character patterns (e.g., "ghhh", "aaaa")
            if len(trimmed) >= 4:
                # If one character appears 75% or more of the time, reject
                char_counts = {c: trimmed.lower().count(c) for c in set(trimmed.lower())}
                max_count = max(char_counts.values())
                if max_count >= len(trimmed) * 0.75:
                    continue

            # Case-insensitive deduplication
            lower = trimmed.lower()
            if lower in seen:
                continue

            seen.add(lower)
            cleaned.append(trimmed)

    return cleaned

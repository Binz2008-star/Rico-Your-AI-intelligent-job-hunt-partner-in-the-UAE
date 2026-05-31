"""test_role_normalization.py — Tests for target role normalization."""

import pytest

from src.role_normalization import (
    normalize_target_roles,
    normalize_profile_updates,
    should_normalize_profile,
)


def test_normalize_hse_environmental_profile():
    """HSE/environmental profile with broad roles becomes specific roles."""
    skills = ["hse", "iso 14001", "audit", "compliance", "esg", "sustainability", "environmental management", "operations"]
    target_roles = ["Engineer", "Manager", "Operations Lead", "Operations Manager"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=10,
    )

    # Should return specific HSE/environmental roles
    assert "Environmental Manager" in normalized or "ESG Manager" in normalized
    # Should include HSE-related roles due to hse skill
    assert any("HSE" in role or "Safety" in role or "Environmental" in role for role in normalized)

    # Should NOT contain broad standalone roles
    assert "Engineer" not in normalized
    assert "Manager" not in [r for r in normalized if r == "Manager"]  # Allow "Environmental Manager" but not standalone "Manager"
    assert "Operations Lead" not in normalized


def test_normalize_no_broad_roles():
    """Profile without broad roles is returned as-is."""
    skills = ["python", "react", "aws"]
    target_roles = ["Senior Python Developer", "Backend Engineer"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=5,
    )

    # Should return unchanged
    assert normalized == target_roles


def test_normalize_no_cv_evidence():
    """Profile with broad roles but no CV evidence filters out broad roles."""
    skills = ["general", "admin"]
    target_roles = ["Engineer", "Manager"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=3,
    )

    # Should filter out broad roles since no CV evidence to infer specific ones
    assert "Engineer" not in normalized
    assert "Manager" not in normalized


def test_normalize_empty_target_roles_infers_from_skills():
    """Empty target_roles infers specific roles from skills."""
    skills = ["hse", "safety", "iso 45001", "nebosh"]
    target_roles = []

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=7,
    )

    # Should infer HSE-specific roles
    assert len(normalized) > 0
    assert any("HSE" in role or "Safety" in role for role in normalized)


def test_normalize_profile_updates_wrapper():
    """normalize_profile_updates wrapper works correctly."""
    updates = {
        "name": "Test User",
        "skills": ["hse", "environmental management"],
        "target_roles": ["Engineer", "Manager"],
        "years_experience": 8,
    }

    normalized = normalize_profile_updates(updates)

    # Should normalize target_roles
    assert "Engineer" not in normalized["target_roles"]
    assert "Manager" not in [r for r in normalized["target_roles"] if r == "Manager"]
    # Should preserve other fields
    assert normalized["name"] == "Test User"
    assert normalized["skills"] == ["hse", "environmental management"]


def test_normalize_profile_updates_no_target_roles():
    """Updates without target_roles are unchanged."""
    updates = {
        "name": "Test User",
        "skills": ["python"],
        "years_experience": 5,
    }

    normalized = normalize_profile_updates(updates)

    # Should return unchanged
    assert normalized == updates


def test_should_normalize_profile_true():
    """Profile with broad roles and CV evidence should be normalized."""
    skills = ["hse", "iso 14001"]
    target_roles = ["Engineer", "Manager"]

    assert should_normalize_profile(target_roles, skills) is True


def test_should_normalize_profile_false_no_broad_roles():
    """Profile without broad roles should not be normalized."""
    skills = ["hse", "iso 14001"]
    target_roles = ["HSE Manager", "Environmental Manager"]

    assert should_normalize_profile(target_roles, skills) is False


def test_should_normalize_profile_false_no_cv_evidence():
    """Profile with broad roles but no CV evidence should not be normalized."""
    skills = ["general"]
    target_roles = ["Engineer", "Manager"]

    assert should_normalize_profile(target_roles, skills) is False


def test_should_normalize_profile_false_empty_roles():
    """Empty target_roles should not trigger normalization."""
    skills = ["hse"]
    target_roles = []

    assert should_normalize_profile(target_roles, skills) is False


def test_normalize_compliance_audit_profile():
    """Compliance/audit profile gets specific roles."""
    skills = ["compliance", "audit", "regulatory", "risk management"]
    target_roles = ["Manager", "Specialist"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=6,
    )

    # Should return compliance-specific roles
    assert any("Compliance" in role or "Audit" in role for role in normalized)
    assert "Manager" not in [r for r in normalized if r == "Manager"]


def test_normalize_iso_quality_profile():
    """ISO/quality profile gets specific roles."""
    skills = ["iso 9001", "iso 14001", "quality assurance", "qa"]
    target_roles = ["Manager", "Officer"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=5,
    )

    # Should return quality-specific roles
    assert any("Quality" in role or "ISO" in role or "QA" in role for role in normalized)
    assert "Manager" not in [r for r in normalized if r == "Manager"]


def test_normalize_operations_with_hse():
    """Operations skill with HSE skills adds Operations Manager - Environmental Services."""
    skills = ["operations", "hse", "safety"]
    target_roles = ["Manager"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=8,
    )

    # Should include operations-specific role
    assert "Operations Manager - Environmental Services" in normalized


def test_normalize_preserves_specific_roles():
    """Already-specific roles are preserved."""
    skills = ["hse", "safety"]
    target_roles = ["HSE Manager", "Safety Officer"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=5,
    )

    # Should preserve specific roles
    assert "HSE Manager" in normalized
    assert "Safety Officer" in normalized


def test_production_profile_exact_match():
    """Exact production profile from ricohunt.com - regression test for #312 fix."""
    skills = ["hse", "iso 14001", "audit", "compliance", "esg", "sustainability", "environmental management", "excel", "operations"]
    target_roles = ["Engineer", "Manager", "Operations Lead", "Operations Manager"]

    normalized = normalize_target_roles(
        target_roles=target_roles,
        skills=skills,
        years_experience=10,
    )

    # Must include HSE and environmental roles (priority families)
    assert "HSE Manager" in normalized, "HSE Manager must be present (priority family)"
    assert "QHSE Manager" in normalized, "QHSE Manager must be present (priority family)"
    assert "Environmental Manager" in normalized, "Environmental Manager must be present (priority family)"

    # Must include ESG/sustainability roles
    assert "ESG Manager" in normalized or "Sustainability Manager" in normalized, "ESG or Sustainability Manager must be present"

    # Must include Operations Manager - Environmental Services (operations skill + HSE/env)
    assert "Operations Manager - Environmental Services" in normalized, "Operations Manager - Environmental Services must be present"

    # Should NOT contain broad standalone roles
    assert "Engineer" not in normalized
    assert "Manager" not in [r for r in normalized if r == "Manager"]
    assert "Operations Lead" not in normalized
    assert "Operations Manager" not in [r for r in normalized if r == "Operations Manager"]

    # Should NOT contain overly generic compliance/audit roles (they're lower priority than HSE/env)
    # With priority logic, HSE and environmental families should dominate
    hse_env_count = sum(1 for r in normalized if any(term in r for term in ["HSE", "QHSE", "Environmental", "ESG", "Sustainability"]))
    assert hse_env_count >= 4, f"Should have at least 4 HSE/environmental roles, got {hse_env_count}: {normalized}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

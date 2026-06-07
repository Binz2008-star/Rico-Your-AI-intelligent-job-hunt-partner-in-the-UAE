"""Tests for target_roles and skills validation and normalization."""

import pytest

from src.role_normalization import (
    get_uae_role_suggestions,
    validate_and_normalize_target_roles,
    validate_and_normalize_skills,
)


class TestValidateAndNormalizeTargetRoles:
    """Test validate_and_normalize_target_roles function."""

    def test_empty_input_returns_empty(self):
        assert validate_and_normalize_target_roles([]) == []
        assert validate_and_normalize_target_roles(None) == []

    def test_trims_whitespace(self):
        result = validate_and_normalize_target_roles(["  HSE Manager  ", "Safety Officer"])
        assert result == ["HSE Manager", "Safety Officer"]

    def test_removes_empty_strings(self):
        result = validate_and_normalize_target_roles(["HSE Manager", "", "Safety Officer", "   "])
        assert result == ["HSE Manager", "Safety Officer"]

    def test_removes_duplicates_case_insensitive(self):
        result = validate_and_normalize_target_roles(["HSE Manager", "hse manager", "HSE MANAGER"])
        assert result == ["HSE Manager"]

    def test_splits_comma_separated_blobs(self):
        result = validate_and_normalize_target_roles(["HSE Manager, Safety Officer, QA Manager"])
        assert result == ["HSE Manager", "Safety Officer", "QA Manager"]

    def test_filters_gibberish_short_strings(self):
        result = validate_and_normalize_target_roles(["ghhh", "x", "HSE Manager"])
        # "ghhh" is rejected (repeated chars), "x" is rejected (single char)
        assert result == ["HSE Manager"]

    def test_filters_gibberish_random_chars(self):
        result = validate_and_normalize_target_roles(["abc123xyz", "HSE Manager"])
        # "abc123xyz" has letters so it passes - this is intentional per current logic
        # Very short non-alpha strings are filtered
        assert "HSE Manager" in result

    def test_minimum_length_check(self):
        result = validate_and_normalize_target_roles(["A", "AB", "HSE Manager"])
        assert "A" not in result
        assert "AB" in result
        assert "HSE Manager" in result

    def test_valid_roles_pass_through(self):
        result = validate_and_normalize_target_roles([
            "Environmental Manager",
            "HSE Manager",
            "Operations Manager",
        ])
        assert result == ["Environmental Manager", "HSE Manager", "Operations Manager"]

    def test_mixed_valid_and_invalid(self):
        result = validate_and_normalize_target_roles([
            "HSE Manager",
            "ghhh",
            "",
            "  Safety Officer  ",
            "x",
            "Operations Manager, Project Manager",
        ])
        assert result == ["HSE Manager", "Safety Officer", "Operations Manager", "Project Manager"]


class TestValidateAndNormalizeSkills:
    """Test validate_and_normalize_skills function."""

    def test_empty_input_returns_empty(self):
        assert validate_and_normalize_skills([]) == []
        assert validate_and_normalize_skills(None) == []

    def test_trims_whitespace(self):
        result = validate_and_normalize_skills(["  Python  ", "FastAPI"])
        assert result == ["Python", "FastAPI"]

    def test_removes_empty_strings(self):
        result = validate_and_normalize_skills(["Python", "", "FastAPI", "   "])
        assert result == ["Python", "FastAPI"]

    def test_removes_duplicates_case_insensitive(self):
        result = validate_and_normalize_skills(["Python", "python", "PYTHON"])
        assert result == ["Python"]

    def test_splits_comma_separated_blobs(self):
        result = validate_and_normalize_skills(["Python, FastAPI, SQL"])
        assert result == ["Python", "FastAPI", "SQL"]

    def test_filters_gibberish_short_strings(self):
        result = validate_and_normalize_skills(["ghhh", "x", "Python"])
        # "ghhh" is rejected (repeated chars), "x" is rejected (single char)
        assert result == ["Python"]

    def test_filters_gibberish_random_chars(self):
        result = validate_and_normalize_skills(["abc123xyz", "Python"])
        # "abc123xyz" has letters so it passes - this is intentional per current logic
        assert "Python" in result

    def test_minimum_length_check(self):
        result = validate_and_normalize_skills(["A", "AB", "Python"])
        assert "A" not in result
        assert "AB" in result
        assert "Python" in result

    def test_valid_skills_pass_through(self):
        result = validate_and_normalize_skills([
            "Python",
            "FastAPI",
            "PostgreSQL",
        ])
        assert result == ["Python", "FastAPI", "PostgreSQL"]

    def test_mixed_valid_and_invalid(self):
        result = validate_and_normalize_skills([
            "Python",
            "ghhh",
            "",
            "  FastAPI  ",
            "x",
            "SQL, React",
        ])
        assert result == ["Python", "FastAPI", "SQL", "React"]


class TestUAERoleSuggestions:
    """Test UAE role suggestions."""

    def test_returns_list(self):
        suggestions = get_uae_role_suggestions()
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

    def test_includes_diverse_roles(self):
        suggestions = get_uae_role_suggestions()
        assert "Environmental Manager" in suggestions
        assert "HSE Manager" in suggestions
        assert "Operations Manager" in suggestions
        assert "Accountant" in suggestions
        assert "Sales Executive" in suggestions

    def test_includes_engineering_roles(self):
        suggestions = get_uae_role_suggestions()
        assert "Civil Engineer" in suggestions
        assert "Mechanical Engineer" in suggestions
        assert "Electrical Engineer" in suggestions

    def test_does_not_include_environmental_only(self):
        """Ensure suggestions are diverse, not only environmental roles."""
        suggestions = get_uae_role_suggestions()
        # Count environmental vs non-environmental
        env_keywords = ["Environmental", "HSE", "QHSE", "Sustainability", "ESG", "Safety", "Compliance"]
        env_count = sum(1 for role in suggestions if any(kw in role for kw in env_keywords))
        non_env_count = len(suggestions) - env_count
        # Should have at least some non-environmental roles
        assert non_env_count >= 5

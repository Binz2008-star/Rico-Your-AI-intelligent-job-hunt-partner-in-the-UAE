"""Unit tests for src/services/cv_quality_warnings.py.

All checks are pure-function; no DB, no external services.
"""
import pytest
from src.services.cv_quality_warnings import build_cv_quality_warnings


def _codes(warnings):
    return [w["code"] for w in warnings]


class TestExtractionQualityWarnings:
    def test_poor_quality_warns(self):
        result = build_cv_quality_warnings(extraction_quality="poor")
        assert "cv_extraction_quality_poor" in _codes(result)

    def test_partial_quality_warns(self):
        result = build_cv_quality_warnings(extraction_quality="partial")
        assert "cv_extraction_quality_partial" in _codes(result)

    def test_good_quality_no_quality_warning(self):
        result = build_cv_quality_warnings(extraction_quality="good")
        assert "cv_extraction_quality_poor" not in _codes(result)
        assert "cv_extraction_quality_partial" not in _codes(result)

    def test_unknown_quality_no_quality_warning(self):
        result = build_cv_quality_warnings(extraction_quality="unknown")
        assert "cv_extraction_quality_poor" not in _codes(result)
        assert "cv_extraction_quality_partial" not in _codes(result)

    def test_warning_shape(self):
        result = build_cv_quality_warnings(extraction_quality="poor")
        w = next(w for w in result if w["code"] == "cv_extraction_quality_poor")
        assert w["severity"] == "warning"
        assert w["field"] == "extraction_quality"
        assert w["message"]
        assert w["suggestion"]
        assert w["message_ar"]
        assert w["suggestion_ar"]


class TestExperienceWarnings:
    def test_high_years_warns(self):
        result = build_cv_quality_warnings(preview={"experience_years": 30})
        assert "cv_years_experience_high" in _codes(result)

    def test_unrealistic_years_warns(self):
        result = build_cv_quality_warnings(preview={"experience_years": 55})
        assert "cv_years_experience_unrealistic" in _codes(result)

    def test_normal_years_no_warning(self):
        result = build_cv_quality_warnings(preview={"experience_years": 10})
        assert "cv_years_experience_high" not in _codes(result)
        assert "cv_years_experience_unrealistic" not in _codes(result)

    def test_zero_years_no_warning(self):
        result = build_cv_quality_warnings(preview={"experience_years": 0})
        assert "cv_years_experience_high" not in _codes(result)

    def test_none_years_no_warning(self):
        result = build_cv_quality_warnings(preview={"experience_years": None})
        assert "cv_years_experience_high" not in _codes(result)

    def test_boundary_26_years_warns(self):
        result = build_cv_quality_warnings(preview={"experience_years": 26})
        assert "cv_years_experience_high" in _codes(result)

    def test_boundary_25_years_no_warning(self):
        result = build_cv_quality_warnings(preview={"experience_years": 25})
        assert "cv_years_experience_high" not in _codes(result)

    def test_warning_message_includes_years(self):
        result = build_cv_quality_warnings(preview={"experience_years": 30})
        w = next(w for w in result if w["code"] == "cv_years_experience_high")
        assert "30" in w["message"]


class TestSkillsWarnings:
    def test_two_skills_warns(self):
        result = build_cv_quality_warnings(preview={"skills_detected": ["Python", "SQL"]})
        assert "cv_skills_low" in _codes(result)

    def test_one_skill_warns(self):
        result = build_cv_quality_warnings(preview={"skills_detected": ["Safety"]})
        assert "cv_skills_low" in _codes(result)

    def test_three_skills_no_warning(self):
        result = build_cv_quality_warnings(preview={"skills_detected": ["A", "B", "C"]})
        assert "cv_skills_low" not in _codes(result)

    def test_empty_skills_no_warning(self):
        # Empty list: no skills at all — different case, no spurious "0 detected" warning
        result = build_cv_quality_warnings(preview={"skills_detected": []})
        assert "cv_skills_low" not in _codes(result)

    def test_no_skills_key_no_warning(self):
        result = build_cv_quality_warnings(preview={})
        assert "cv_skills_low" not in _codes(result)

    def test_warning_message_includes_count(self):
        result = build_cv_quality_warnings(preview={"skills_detected": ["Python"]})
        w = next(w for w in result if w["code"] == "cv_skills_low")
        assert "1" in w["message"]

    def test_skills_fallback_field(self):
        # Falls back to "skills" key when skills_detected is absent
        result = build_cv_quality_warnings(preview={"skills": ["Python"]})
        assert "cv_skills_low" in _codes(result)


class TestRoleMismatchWarnings:
    def test_mismatch_warns(self):
        preview = {"current_role": "Accountant", "target_roles": ["HSE Manager", "Safety Officer"]}
        result = build_cv_quality_warnings(preview=preview)
        assert "cv_role_target_role_mismatch" in _codes(result)

    def test_overlap_no_warning(self):
        preview = {"current_role": "HSE Manager", "target_roles": ["HSE Manager", "Safety Officer"]}
        result = build_cv_quality_warnings(preview=preview)
        assert "cv_role_target_role_mismatch" not in _codes(result)

    def test_partial_word_overlap_no_warning(self):
        preview = {"current_role": "Senior Safety Manager", "target_roles": ["HSE Manager"]}
        result = build_cv_quality_warnings(preview=preview)
        assert "cv_role_target_role_mismatch" not in _codes(result)

    def test_no_current_role_no_warning(self):
        preview = {"target_roles": ["HSE Manager"]}
        result = build_cv_quality_warnings(preview=preview)
        assert "cv_role_target_role_mismatch" not in _codes(result)

    def test_no_target_roles_no_warning(self):
        preview = {"current_role": "Accountant"}
        result = build_cv_quality_warnings(preview=preview)
        assert "cv_role_target_role_mismatch" not in _codes(result)

    def test_uses_stored_profile_target_roles(self):
        preview = {"current_role": "Accountant"}
        profile = {"target_roles": ["HSE Manager", "Safety Officer"]}
        result = build_cv_quality_warnings(preview=preview, profile=profile)
        assert "cv_role_target_role_mismatch" in _codes(result)

    def test_warning_message_includes_cv_role(self):
        preview = {"current_role": "Accountant", "target_roles": ["HSE Manager"]}
        result = build_cv_quality_warnings(preview=preview)
        w = next(w for w in result if w["code"] == "cv_role_target_role_mismatch")
        assert "Accountant" in w["message"]


class TestDeduplication:
    def test_no_duplicate_codes(self):
        # Crafted input that could theoretically trigger the same code twice
        result = build_cv_quality_warnings(
            preview={"experience_years": 30},
            extraction_quality="poor",
        )
        codes = _codes(result)
        assert len(codes) == len(set(codes))


class TestNoWarningsPath:
    def test_clean_cv_no_warnings(self):
        preview = {
            "experience_years": 8,
            "skills_detected": ["HSE", "Python", "SQL", "Excel", "NEBOSH"],
            "current_role": "HSE Manager",
            "target_roles": ["HSE Manager", "Safety Officer"],
        }
        result = build_cv_quality_warnings(
            preview=preview,
            extraction_quality="good",
        )
        assert result == []

    def test_empty_inputs_no_crash(self):
        result = build_cv_quality_warnings()
        assert isinstance(result, list)

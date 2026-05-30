"""Tests for src/eligibility_filter.py — UAE nationals-only job detection.

All tests are pure-Python, no DB, no network.
"""
import pytest

from src.eligibility_filter import filter_for_non_nationals, is_uae_nationals_only


# ── is_uae_nationals_only ──────────────────────────────────────────────────────

class TestIsUAENationalsOnly:
    def test_uae_nationals_only_en(self):
        assert is_uae_nationals_only({"title": "Engineer", "description": "UAE Nationals only"})

    def test_uae_nationals_only_case_insensitive(self):
        assert is_uae_nationals_only({"description": "uae nationals ONLY"})

    def test_emirati_nationals_only(self):
        assert is_uae_nationals_only({"description": "Emirati Nationals only preferred"})

    def test_uae_citizen(self):
        assert is_uae_nationals_only({"description": "Must be UAE citizen"})

    def test_emirati_in_title(self):
        assert is_uae_nationals_only({"title": "Emirati Graduate Programme"})

    def test_uae_national_standalone(self):
        assert is_uae_nationals_only({"title": "UAE National Fresh Graduate"})

    def test_for_uae_nationals(self):
        assert is_uae_nationals_only({"description": "This role is open for UAE Nationals."})

    def test_arabic_emirati(self):
        assert is_uae_nationals_only({"description": "مطلوب إماراتي للعمل في دبي"})

    def test_arabic_uae_national_phrase(self):
        assert is_uae_nationals_only({"description": "يشترط أن يكون مواطن إماراتي"})

    def test_arabic_khulasat_alqaid(self):
        assert is_uae_nationals_only({"description": "يلزم تقديم خلاصة القيد"})

    def test_arabic_khulasat_variant(self):
        assert is_uae_nationals_only({"description": "خلاصه القيد مطلوب"})

    def test_arabic_lil_emarat(self):
        assert is_uae_nationals_only({"description": "للإماراتيين فقط"})

    def test_international_role_not_flagged(self):
        assert not is_uae_nationals_only({
            "title": "Software Engineer",
            "description": "Join our team in Dubai. 5 years experience required.",
        })

    def test_mentions_uae_without_restriction(self):
        assert not is_uae_nationals_only({
            "description": "Work in the UAE office. All nationalities welcome."
        })

    def test_none_input(self):
        assert not is_uae_nationals_only(None)

    def test_empty_dict(self):
        assert not is_uae_nationals_only({})

    def test_checks_description_field(self):
        assert is_uae_nationals_only({
            "title": "Senior Manager",
            "description": "Open to UAE Nationals only.",
        })

    def test_checks_raw_jsearch_field(self):
        # Raw JSearch uses job_description
        assert is_uae_nationals_only({
            "job_title": "Analyst",
            "job_description": "UAE National required.",
        })


# ── filter_for_non_nationals ──────────────────────────────────────────────────

class TestFilterForNonNationals:
    def test_removes_nationals_only_jobs(self):
        jobs = [
            {"title": "Engineer", "description": "UAE Nationals only"},
            {"title": "Developer", "description": "Open to all nationalities"},
        ]
        result = filter_for_non_nationals(jobs)
        assert len(result) == 1
        assert result[0]["title"] == "Developer"

    def test_empty_list(self):
        assert filter_for_non_nationals([]) == []

    def test_none_input(self):
        assert filter_for_non_nationals(None) == []

    def test_all_open_roles_unchanged(self):
        jobs = [
            {"title": "A", "description": "Great role"},
            {"title": "B", "description": "Dubai tech company"},
        ]
        assert filter_for_non_nationals(jobs) == jobs

    def test_all_nationals_only_returns_empty(self):
        jobs = [
            {"description": "UAE Nationals only"},
            {"description": "Emirati citizen required"},
        ]
        assert filter_for_non_nationals(jobs) == []

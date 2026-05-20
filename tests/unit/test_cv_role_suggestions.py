"""
Tests for CV-driven role suggestions and Arabic job-search recovery.

Covers:
1. _generate_role_suggestions with ISO 14001/ESG/compliance/environmental profile
   → HSE/Environmental/ESG/ISO variants in suggestions
2. _extract_name from sample CV text
3. _extract_current_role from sample CV text
4. Generic Arabic job request with CV skills but no target_roles
   → profile_role_suggestions (not dead-end profile_incomplete)
5. No live matches with CV profile
   → no_results_recovery with role options (not dead-end dead message)
6. Arabic "مالحل الآن؟" with CV
   → next-step options (not generic DeepSeek answer)
"""

import pytest
from unittest.mock import MagicMock, patch

from src.cv_parser import CVParser, ParsedCV
from src.agent.intelligence.intent_classifier import classify_intent


# ---------------------------------------------------------------------------
# 1. Role suggestions from ISO 14001/ESG/compliance profile
# ---------------------------------------------------------------------------

class TestGenerateRoleSuggestions:

    def _make_api(self):
        from src.rico_chat_api import RicoChatAPI
        api = object.__new__(RicoChatAPI)
        return api

    def test_iso14001_esg_compliance_yields_hse_and_environmental(self):
        api = self._make_api()
        skills = ["iso 14001", "audit", "compliance", "esg", "environmental management", "excel"]
        suggestions = api._generate_role_suggestions(skills, [], 10.0, [])
        labels = [s["label"] for s in suggestions]
        assert any("HSE" in l or "Environmental" in l for l in labels), (
            f"Expected HSE/Environmental role in suggestions, got: {labels}"
        )
        assert any("ESG" in l or "Sustainability" in l for l in labels), (
            f"Expected ESG/Sustainability role in suggestions, got: {labels}"
        )

    def test_iso14001_cert_adds_iso_specialist(self):
        api = self._make_api()
        skills = ["iso 14001", "audit"]
        certifications = ["iso"]
        suggestions = api._generate_role_suggestions(skills, certifications, 5.0, [])
        labels = [s["label"] for s in suggestions]
        assert any("ISO" in l for l in labels), f"Expected ISO role, got: {labels}"

    def test_10_years_experience_adds_seniority(self):
        api = self._make_api()
        skills = ["hse", "safety"]
        suggestions = api._generate_role_suggestions(skills, [], 10.0, [])
        labels = [s["label"] for s in suggestions]
        assert any("Senior" in l for l in labels), (
            f"Expected Senior prefix for 10yr exp, got: {labels}"
        )

    def test_no_skills_returns_empty(self):
        api = self._make_api()
        suggestions = api._generate_role_suggestions([], [], None, [])
        assert suggestions == []

    @pytest.mark.parametrize("expected_role", [
        "HSE Manager",
        "Environmental Compliance Officer",
        "ESG Specialist",
        "ISO 14001 Lead Auditor",
        "QHSE Manager",
    ])
    def test_environmental_profile_covers_expected_uae_roles(self, expected_role):
        """Each expected UAE role for this CV profile must appear somewhere."""
        api = self._make_api()
        skills = ["iso 14001", "esg", "environmental management", "compliance", "audit"]
        suggestions = api._generate_role_suggestions(skills, ["iso"], 10.0, [])
        labels = [s["label"] for s in suggestions]
        # Accept if any suggestion contains the key role words
        role_words = set(expected_role.lower().split())
        matched = any(
            len(role_words & set(l.lower().split())) >= 2
            for l in labels
        )
        assert matched, (
            f"Expected role variant of '{expected_role}' in suggestions, got: {labels}"
        )


# ---------------------------------------------------------------------------
# 2. Name extraction
# ---------------------------------------------------------------------------

class TestExtractName:
    PARSER = CVParser()

    _SAMPLE_CV = """Ahmed Al-Rashidi
HSE Manager | Dubai

OBJECTIVE
Experienced HSE professional with 10+ years in environmental compliance.

WORK EXPERIENCE
HSE Manager — ABC Energy LLC, Dubai (2018–Present)
"""

    def test_extracts_name_from_first_lines(self):
        result = self.PARSER._extract_name(self._SAMPLE_CV)
        assert result == "Ahmed Al-Rashidi"

    def test_no_name_returns_none_for_sectiononly_doc(self):
        text = "OBJECTIVE\nTo obtain a position.\nEDUCATION\nBSc 2010"
        result = self.PARSER._extract_name(text)
        assert result is None

    def test_name_not_extracted_from_email_line(self):
        text = "ahmed@example.com\nAhmed Rashidi\nHSE Manager"
        result = self.PARSER._extract_name(text)
        # email line is skipped; "Ahmed Rashidi" should be found
        assert result == "Ahmed Rashidi"

    def test_parse_text_populates_name(self):
        result = self.PARSER.parse_text(self._SAMPLE_CV)
        assert result.name == "Ahmed Al-Rashidi"


# ---------------------------------------------------------------------------
# 3. Current role extraction
# ---------------------------------------------------------------------------

class TestExtractCurrentRole:
    PARSER = CVParser()

    _SAMPLE_WITH_PRESENT = """John Smith
Environmental Manager

Work Experience
Environmental Compliance Officer
Green Holdings UAE
Jan 2020 – Present

ISO Auditor
Blue Corp
2015 – 2020
"""

    def test_extracts_role_before_present(self):
        result = self.PARSER._extract_current_role(self._SAMPLE_WITH_PRESENT)
        assert result is not None
        assert "Environmental" in result or "Compliance" in result

    def test_explicit_current_role_marker(self):
        text = "Current Role: HSE Manager\nABC Company\n2019–Present"
        result = self.PARSER._extract_current_role(text)
        assert result is not None
        assert "Hse Manager" in result or "HSE Manager" in result

    def test_no_present_returns_none(self):
        text = "Education\nBSc Environmental Science 2010\nMSc 2012"
        result = self.PARSER._extract_current_role(text)
        assert result is None

    def test_parse_text_populates_current_role(self):
        result = self.PARSER.parse_text(self._SAMPLE_WITH_PRESENT)
        assert result.current_role is not None


# ---------------------------------------------------------------------------
# 4. Arabic generic job request with CV but no target_roles → role suggestions
# ---------------------------------------------------------------------------

class TestArabicJobRequestWithCVNoTargetRoles:

    def _make_profile(self, skills=None, target_roles=None, has_cv_status=True):
        profile = MagicMock()
        profile.has_cv = has_cv_status
        profile.skills = skills or ["iso 14001", "esg", "environmental management", "compliance", "audit"]
        profile.target_roles = target_roles or []
        profile.certifications = ["iso"]
        profile.years_experience = 10.0
        profile.industries = []
        profile.cv_filename = "cv.pdf" if has_cv_status else None
        profile.cv_status = "parsed" if has_cv_status else None
        return profile

    def test_handle_profile_role_suggestions_returns_options(self):
        from src.rico_chat_api import RicoChatAPI
        api = object.__new__(RicoChatAPI)
        profile = self._make_profile()

        with patch.object(api, "_profile_value", side_effect=lambda p, k: getattr(p, k, None)), \
             patch.object(api, "_as_list", side_effect=lambda v: v if isinstance(v, list) else ([] if v is None else [v])):
            result = api._handle_profile_role_suggestions(profile)

        assert result["type"] == "profile_role_suggestions"
        assert len(result["options"]) > 0, "Must suggest roles from CV skills"
        assert result["next_action"] == "select_role_to_search"

    def test_no_dead_end_message_when_has_cv(self):
        """Response type must not be 'profile_incomplete' when has_cv=True."""
        from src.rico_chat_api import RicoChatAPI
        api = object.__new__(RicoChatAPI)
        profile = self._make_profile()

        with patch.object(api, "_profile_value", side_effect=lambda p, k: getattr(p, k, None)), \
             patch.object(api, "_as_list", side_effect=lambda v: v if isinstance(v, list) else ([] if v is None else [v])):
            result = api._handle_profile_role_suggestions(profile)

        assert result.get("type") != "profile_incomplete", (
            "Must not return profile_incomplete dead-end when CV is present"
        )


# ---------------------------------------------------------------------------
# 5. No live matches with CV → no_results_recovery (not dead-end)
# ---------------------------------------------------------------------------

class TestNoResultsRecovery:

    def _make_profile(self):
        profile = MagicMock()
        profile.skills = ["iso 14001", "esg", "environmental management"]
        profile.certifications = ["iso"]
        profile.years_experience = 10.0
        profile.industries = []
        return profile

    def test_no_results_recovery_returns_options(self):
        from src.rico_chat_api import RicoChatAPI
        api = object.__new__(RicoChatAPI)
        profile = self._make_profile()

        with patch.object(api, "_profile_value", side_effect=lambda p, k: getattr(p, k, None)), \
             patch.object(api, "_as_list", side_effect=lambda v: v if isinstance(v, list) else ([] if v is None else [v])):
            result = api._handle_no_results_recovery("user1", profile, ["HSE Manager"])

        assert result["type"] == "no_results_recovery"
        assert len(result["options"]) > 0, "Must offer alternative role options"
        assert result["next_action"] == "select_role_to_search"
        assert "HSE Manager" in result["message"]

    def test_no_results_does_not_fabricate_jobs(self):
        """The recovery response must not claim to have found live matches."""
        from src.rico_chat_api import RicoChatAPI
        api = object.__new__(RicoChatAPI)
        profile = self._make_profile()

        with patch.object(api, "_profile_value", side_effect=lambda p, k: getattr(p, k, None)), \
             patch.object(api, "_as_list", side_effect=lambda v: v if isinstance(v, list) else ([] if v is None else [v])):
            result = api._handle_no_results_recovery("user1", profile, ["HSE Manager"])

        assert result.get("matches") is None or result.get("matches") == [], (
            "Recovery response must not include fabricated job matches"
        )


# ---------------------------------------------------------------------------
# 6. Arabic "مالحل" fast-path detection
# ---------------------------------------------------------------------------

class TestArabicWhatNowDetection:

    def test_malhal_detected_as_what_now(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._is_arabic_what_now("مالحل") is True

    def test_malhal_with_punctuation(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._is_arabic_what_now("مالحل؟") is True
        assert RicoChatAPI._is_arabic_what_now("مالحل الآن؟") is True

    def test_english_what_now_not_detected(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._is_arabic_what_now("what now") is False

    def test_arabic_job_search_not_detected(self):
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._is_arabic_what_now("إبحث لي عن وظيفة") is False

    def test_malhal_classifies_as_help_not_nonsense(self):
        result = classify_intent("مالحل")
        assert result.intent != "nonsense"
        assert result.intent != "unknown"

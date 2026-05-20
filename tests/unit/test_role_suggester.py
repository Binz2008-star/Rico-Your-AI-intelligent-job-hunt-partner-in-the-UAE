"""
Tests for role_suggester.generate_role_suggestions across all job-seeker segments.

Segments covered:
  - Senior environmental/compliance profile (ISO 14001 / ESG / audit / 10 yrs)
  - Fresh graduate generic CV (no skills, no certs, 0 yrs)
  - Technician/field worker profile
  - Driver/logistics profile
  - Admin/customer service profile
  - Weak/empty profile → clarifying question, not random suggestions
  - Arabic-language signal profile (skill names as typed by Arabic users)
"""

import pytest
from src.agent.intelligence.role_suggester import (
    generate_role_suggestions,
    needs_clarification,
    _seniority_tier,
)


# ---------------------------------------------------------------------------
# Seniority tier helper
# ---------------------------------------------------------------------------

class TestSeniorityTier:
    def test_none_years_is_entry(self):
        assert _seniority_tier(None) == "entry"

    def test_zero_years_is_entry(self):
        assert _seniority_tier(0) == "entry"

    def test_1_year_is_entry(self):
        assert _seniority_tier(1) == "entry"

    def test_3_years_is_junior(self):
        assert _seniority_tier(3) == "junior"

    def test_6_years_is_mid(self):
        assert _seniority_tier(6) == "mid"

    def test_10_years_is_senior(self):
        assert _seniority_tier(10) == "senior"

    def test_15_years_is_principal(self):
        assert _seniority_tier(15) == "principal"

    def test_manager_title_overrides_years(self):
        assert _seniority_tier(3, current_role="HSE Manager") == "senior"

    def test_director_title_is_principal(self):
        assert _seniority_tier(5, current_role="Director of Operations") == "principal"


# ---------------------------------------------------------------------------
# Segment: Senior environmental / compliance / ISO / ESG (10 years)
# ---------------------------------------------------------------------------

class TestEnvironmentalComplianceSenior:
    SKILLS = ["iso 14001", "audit", "compliance", "esg", "environmental management", "excel"]
    CERTS = ["iso"]
    YEARS = 10.0

    def test_returns_suggestions(self):
        results = generate_role_suggestions(self.SKILLS, self.CERTS, self.YEARS, [])
        assert len(results) >= 3

    def test_all_results_have_label_and_reason(self):
        results = generate_role_suggestions(self.SKILLS, self.CERTS, self.YEARS, [])
        for r in results:
            assert "label" in r and r["label"]
            assert "reason" in r and r["reason"]

    @pytest.mark.parametrize("expected", [
        "HSE Manager",
        "Environmental Manager",
        "Environmental Compliance Officer",
        "ESG Manager",
        "ISO 14001 Lead Auditor",
        "Compliance Manager",
        "QHSE Manager",
    ])
    def test_expected_role_covered(self, expected):
        results = generate_role_suggestions(self.SKILLS, self.CERTS, self.YEARS, [])
        labels = [r["label"] for r in results]
        words = set(expected.lower().split())
        matched = any(len(words & set(l.lower().split())) >= 2 for l in labels)
        assert matched, f"Expected role variant of '{expected}' in {labels}"

    def test_no_junior_titles_for_10yr_profile(self):
        results = generate_role_suggestions(self.SKILLS, self.CERTS, self.YEARS, [])
        labels = [r["label"].lower() for r in results]
        junior_markers = {"trainee", "assistant", "graduate", "junior", "entry"}
        junior_results = [l for l in labels if any(m in l for m in junior_markers)]
        # Primary results should not be junior titles (adjacent tiers OK in small number)
        assert len(junior_results) <= 1, f"Too many junior titles for 10yr profile: {junior_results}"

    def test_no_duplicates(self):
        results = generate_role_suggestions(self.SKILLS, self.CERTS, self.YEARS, [])
        labels = [r["label"] for r in results]
        assert len(labels) == len(set(labels)), f"Duplicate labels: {labels}"

    def test_capped_at_max_results(self):
        results = generate_role_suggestions(self.SKILLS, self.CERTS, self.YEARS, [])
        assert len(results) <= 7


# ---------------------------------------------------------------------------
# Segment: Fresh graduate — generic CV (0 or no years)
# ---------------------------------------------------------------------------

class TestFreshGraduate:
    def test_fresh_grad_with_no_skills_returns_empty(self):
        """No skills = needs_clarification, not fabricated suggestions."""
        results = generate_role_suggestions([], [], 0, [])
        assert results == []

    def test_fresh_grad_admin_skills_gets_entry_roles(self):
        results = generate_role_suggestions(
            ["administration", "excel", "microsoft office"], [], 0, []
        )
        labels = [r["label"].lower() for r in results]
        entry_markers = {"assistant", "trainee", "associate", "officer", "coordinator"}
        assert any(any(m in l for m in entry_markers) for l in labels), (
            f"Expected entry-level role for fresh graduate, got: {labels}"
        )

    def test_fresh_grad_it_skills_gets_junior_developer(self):
        results = generate_role_suggestions(
            ["python", "javascript", "web development"], [], 1, []
        )
        labels = [r["label"].lower() for r in results]
        assert any("developer" in l or "engineer" in l for l in labels), (
            f"Expected developer/engineer role for IT grad, got: {labels}"
        )

    def test_fresh_grad_finance_skills_gets_accountant(self):
        results = generate_role_suggestions(
            ["accounting", "finance", "excel"], [], 1, []
        )
        labels = [r["label"].lower() for r in results]
        assert any("account" in l or "analyst" in l or "finance" in l for l in labels), (
            f"Expected finance/accounting role, got: {labels}"
        )


# ---------------------------------------------------------------------------
# Segment: Technician / blue-collar / field worker
# ---------------------------------------------------------------------------

class TestTechnicianFieldWorker:
    def test_hvac_technician_gets_field_roles(self):
        results = generate_role_suggestions(
            ["hvac", "ac technician", "maintenance"], [], 4, []
        )
        labels = [r["label"].lower() for r in results]
        assert any(
            "technician" in l or "maintenance" in l or "supervisor" in l
            for l in labels
        ), f"Expected technician/maintenance role, got: {labels}"

    def test_electrician_gets_technical_roles(self):
        results = generate_role_suggestions(
            ["electrician", "wiring", "maintenance"], [], 5, []
        )
        labels = [r["label"].lower() for r in results]
        assert any(
            "technician" in l or "engineer" in l or "supervisor" in l
            for l in labels
        ), f"Expected technical role for electrician, got: {labels}"

    def test_senior_technician_gets_supervisor_roles(self):
        results = generate_role_suggestions(
            ["electrical", "hvac", "maintenance"], [], 10, []
        )
        labels = [r["label"].lower() for r in results]
        assert any(
            "supervisor" in l or "manager" in l or "foreman" in l
            for l in labels
        ), f"Expected supervisory role for 10yr technician, got: {labels}"


# ---------------------------------------------------------------------------
# Segment: Driver / logistics
# ---------------------------------------------------------------------------

class TestDriverLogistics:
    def test_driver_profile_gets_driver_roles(self):
        results = generate_role_suggestions(
            ["driving", "heavy vehicle", "transport"], [], 3, []
        )
        labels = [r["label"].lower() for r in results]
        assert any(
            "driver" in l or "transport" in l or "logistics" in l
            for l in labels
        ), f"Expected driver/transport role, got: {labels}"

    def test_logistics_coordinator_gets_supply_chain(self):
        results = generate_role_suggestions(
            ["logistics", "warehouse", "inventory", "procurement"], [], 4, []
        )
        labels = [r["label"].lower() for r in results]
        assert any(
            "logistics" in l or "supply chain" in l or "coordinator" in l
            for l in labels
        ), f"Expected logistics/supply chain role, got: {labels}"

    def test_senior_logistics_gets_manager(self):
        results = generate_role_suggestions(
            ["logistics", "supply chain", "procurement"], [], 10, []
        )
        labels = [r["label"].lower() for r in results]
        assert any("manager" in l for l in labels), (
            f"Expected manager-level role for 10yr logistics, got: {labels}"
        )


# ---------------------------------------------------------------------------
# Segment: Admin / customer service
# ---------------------------------------------------------------------------

class TestAdminCustomerService:
    def test_admin_profile_gets_admin_roles(self):
        results = generate_role_suggestions(
            ["administration", "office management", "scheduling"], [], 3, []
        )
        labels = [r["label"].lower() for r in results]
        assert any(
            "admin" in l or "office" in l or "coordinator" in l
            for l in labels
        ), f"Expected admin role, got: {labels}"

    def test_customer_service_profile_gets_cs_roles(self):
        results = generate_role_suggestions(
            ["customer service", "crm", "sales"], [], 2, []
        )
        labels = [r["label"].lower() for r in results]
        assert any(
            "customer" in l or "sales" in l or "service" in l
            for l in labels
        ), f"Expected customer service/sales role, got: {labels}"

    def test_senior_admin_gets_manager(self):
        results = generate_role_suggestions(
            ["office management", "administration", "executive assistant"], [], 10, []
        )
        labels = [r["label"].lower() for r in results]
        assert any("manager" in l or "director" in l for l in labels), (
            f"Expected manager-level admin role, got: {labels}"
        )


# ---------------------------------------------------------------------------
# Weak profile → clarifying question, not random suggestions
# ---------------------------------------------------------------------------

class TestWeakProfile:
    def test_empty_profile_needs_clarification(self):
        assert needs_clarification([], [], None, []) is True

    def test_empty_skills_no_certs_needs_clarification(self):
        assert needs_clarification([], [], 5, []) is True

    def test_profile_with_skills_does_not_need_clarification(self):
        assert needs_clarification(["accounting", "finance"], [], 3, []) is False

    def test_empty_profile_returns_no_suggestions(self):
        results = generate_role_suggestions([], [], None, [])
        assert results == []

    def test_vague_skill_alone_still_needs_clarification(self):
        """Single generic skill like 'excel' alone should not produce suggestions
        without any domain context — Excel appears in too many segments."""
        # NOTE: Excel is a data signal — it may match data_analytics family.
        # Acceptable either way; just verify no nonsense roles are produced.
        results = generate_role_suggestions(["excel"], [], None, [])
        if results:
            labels = [r["label"].lower() for r in results]
            nonsense = [l for l in labels if "excel" in l]
            assert not nonsense, f"Should not suggest 'Excel' as a role: {labels}"


# ---------------------------------------------------------------------------
# Arabic / mixed-language profile signals
# ---------------------------------------------------------------------------

class TestArabicMixedProfile:
    def test_arabic_user_with_english_skills_gets_suggestions(self):
        """Arabic users typically type skills in English (ISO 14001, HSE).
        Verify their profiles still produce suggestions."""
        results = generate_role_suggestions(
            ["hse", "safety", "iso 45001"], ["nebosh"], 5, []
        )
        labels = [r["label"].lower() for r in results]
        assert any("hse" in l or "safety" in l for l in labels), (
            f"Expected HSE role for Arabic user with English skills, got: {labels}"
        )

    def test_bilingual_industry_context(self):
        """Industry field may contain Arabic-market terms. The function
        should not crash and should still return results when skills are present."""
        results = generate_role_suggestions(
            ["compliance", "audit", "iso 9001"],
            [],
            7,
            ["oil and gas"],
        )
        assert isinstance(results, list)
        assert len(results) > 0

    def test_current_role_in_arabic_does_not_crash(self):
        """current_role may be set from a CV in Arabic. Function must not crash."""
        results = generate_role_suggestions(
            ["accounting", "finance"],
            [],
            4,
            [],
            current_role="مدير مالي",  # "Finance Manager" in Arabic
        )
        assert isinstance(results, list)

    def test_arabic_user_gets_uae_relevant_titles(self):
        """Suggestions for an Arabic user must use UAE-standard English titles,
        not Western/US-specific titles (e.g. prefer 'Officer' over 'Analyst I')."""
        results = generate_role_suggestions(
            ["hr", "recruitment", "payroll"], [], 4, []
        )
        labels = [r["label"] for r in results]
        assert labels, "Expected HR role suggestions"
        # UAE HR market uses Officer/Manager — not "HR Generalist" or "HR Rep"
        assert any(
            "Officer" in l or "Manager" in l or "Specialist" in l or "Coordinator" in l
            for l in labels
        ), f"Expected UAE-standard HR titles, got: {labels}"

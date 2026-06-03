"""
Unit tests for src/resume_screener.py

These tests are isolated: no external API calls, no database writes,
no AI providers, no imports from rico_agent or job-search modules.
"""

import json
import pytest

# Override the autouse fixture from tests/unit/conftest.py — the resume screener
# module has no dependency on RicoChatAPI, so no mocking is needed here.
@pytest.fixture(autouse=True)
def mock_rico_dependencies():
    yield {}


from src.resume_screener import (
    CandidateProfile,
    JDSummary,
    ScreeningResult,
    _calc_unique_months,
    _extract_cert_keywords,
    _strip_protected_content,
    _token_overlap_match,
    detect_red_flags,
    extract_jd,
    extract_resume,
    screen_resumes,
    screening_result_to_dict,
    EmploymentRecord,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_JD = """\
Senior Safety Engineer
Required:
5 years of experience in occupational health and safety.
NEBOSH certification required.
Experience in UAE regulatory compliance and Dubai municipality approvals.
Preferred:
IOSH membership preferred.
Bachelor degree in Engineering or related field.
"""

CANDIDATE_ALICE = """\
Alice Johnson
alice@example.com | +971 50 123 4567 | linkedin.com/in/alicejohnson

Experience
Safety Manager – ADNOC, Abu Dhabi, UAE
Jan 2018 – Present
Managed HSE compliance for 500-person construction site in Abu Dhabi.
Achieved zero LTI for 24 consecutive months.
Reduced incident rate by 35%.

Safety Officer – Al Futtaim Group, Dubai
Mar 2015 – Dec 2017

Skills
HSE management, risk assessment, incident investigation, permit-to-work,
UAE regulatory compliance, COSHH, toolbox talks

Certifications
NEBOSH IGC – 2016
IOSH Managing Safely – 2015

Education
Bachelor of Engineering, University of Melbourne, 2014
"""

CANDIDATE_BOB = """\
Bob Smith
bob@example.com

Experience
Safety Coordinator
Jan 2022 – Dec 2022
Junior Safety Officer
Feb 2023 – Present

Skills
First aid, basic risk assessment

Education
Diploma in Safety Management, 2021
"""


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_empty_jd_raises_value_error(self):
        with pytest.raises(ValueError, match="Job description is required"):
            screen_resumes("", [CANDIDATE_ALICE])

    def test_whitespace_only_jd_raises_value_error(self):
        with pytest.raises(ValueError, match="Job description is required"):
            screen_resumes("   \n\t  ", [CANDIDATE_ALICE])

    def test_empty_resumes_list_returns_valid_result(self):
        result = screen_resumes(MINIMAL_JD, [])
        assert isinstance(result, ScreeningResult)
        assert result.candidates == []
        assert result.ranking_table == []
        assert "advisory" in result.executive_summary.lower()
        assert result.screened_at

    def test_empty_resume_text_does_not_crash(self):
        result = screen_resumes(MINIMAL_JD, [""])
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.profile.candidate_name == "Not provided"
        assert c.profile.years_of_relevant_experience == "Not provided"
        assert c.total_score >= 0

    def test_whitespace_resume_does_not_crash(self):
        result = screen_resumes(MINIMAL_JD, ["   \n   "])
        assert len(result.candidates) == 1
        assert result.candidates[0].profile.candidate_name == "Not provided"


# ---------------------------------------------------------------------------
# JD extraction — section headings not counted as skills
# ---------------------------------------------------------------------------

class TestJDExtraction:
    def test_section_headings_not_in_must_have(self):
        jd = extract_jd(MINIMAL_JD)
        headings = {"required", "requirements", "mandatory", "preferred", "education"}
        for skill in jd.must_have_skills:
            assert skill.lower().strip(":") not in headings, (
                f"Section heading leaked into must_have_skills: {skill!r}"
            )

    def test_section_headings_not_in_preferred(self):
        jd = extract_jd(MINIMAL_JD)
        for skill in jd.preferred_skills:
            assert not skill.lower().startswith("preferred"), (
                f"Section heading leaked into preferred_skills: {skill!r}"
            )

    def test_bullets_stripped_from_items(self):
        jd_text = """\
Required:
- Python programming
• REST API design
* Docker and Kubernetes
1. SQL databases
"""
        jd = extract_jd(jd_text)
        for skill in jd.must_have_skills:
            assert not skill.startswith(("-", "•", "*", "1.")), (
                f"Bullet not stripped: {skill!r}"
            )

    def test_cert_extracted_separately_from_skills(self):
        jd = extract_jd(MINIMAL_JD)
        assert any("nebosh" in c.lower() for c in jd.certification_requirements), (
            "NEBOSH should appear in certification_requirements"
        )
        for skill in jd.must_have_skills:
            assert "nebosh" not in skill.lower(), (
                "NEBOSH should not appear in must_have_skills"
            )

    def test_gcc_terms_extracted(self):
        jd = extract_jd(MINIMAL_JD)
        assert jd.gcc_uae_requirements, "GCC/UAE requirements should be extracted"

    def test_experience_years_extracted(self):
        jd = extract_jd(MINIMAL_JD)
        assert jd.minimum_experience_years == 5


# ---------------------------------------------------------------------------
# Protected characteristics
# ---------------------------------------------------------------------------

class TestProtectedCharacteristics:
    def test_gender_pronouns_stripped(self):
        text = "He holds a PhD and she manages a team of 10."
        cleaned = _strip_protected_content(text)
        assert " he " not in cleaned.lower()
        assert " she " not in cleaned.lower()

    def test_marital_status_stripped(self):
        text = "Married with two children, available immediately."
        cleaned = _strip_protected_content(text)
        assert "married" not in cleaned.lower()

    def test_age_stripped(self):
        text = "DOB: 1985. Age: 38 years old. Experienced professional."
        cleaned = _strip_protected_content(text)
        assert "dob" not in cleaned.lower()
        assert "38 years old" not in cleaned.lower()

    def test_religion_stripped(self):
        text = "Muslim professional with 10 years experience in finance."
        cleaned = _strip_protected_content(text)
        assert "muslim" not in cleaned.lower()

    def test_protected_not_surfaced_in_output(self):
        """Protected characteristics must not appear in any scored field."""
        cv = """\
John Doe
john@example.com
DOB: 1990. Married. Muslim.
Experience
Safety Engineer – Aramco, Saudi Arabia
Jan 2018 – Present
Skills
HSE, risk assessment, incident investigation
"""
        result = screen_resumes(MINIMAL_JD, [cv])
        candidate = result.candidates[0]
        output_dict = screening_result_to_dict(result)
        output_str = json.dumps(output_dict).lower()

        assert "dob" not in output_str
        assert "married" not in output_str
        assert "muslim" not in output_str

    def test_uae_gcc_evidence_preserved(self):
        """UAE/GCC business context must survive stripping."""
        cv = """\
Sara Ali
sara@example.com
Local compliance officer with 8 years in Dubai municipality approvals.
Experience
HSE Manager – Dubai Airports
Jan 2016 – Present
Expat hire on UAE employment visa, transferable.
Skills
UAE regulatory compliance, local authority liaison, permit-to-work
"""
        cleaned = _strip_protected_content(cv)
        assert "local compliance officer" in cleaned.lower()
        assert "dubai municipality" in cleaned.lower()
        assert "expat hire" in cleaned.lower()
        assert "uae employment visa" in cleaned.lower()

    def test_local_and_expat_preserved_in_output(self):
        cv = """\
Test Candidate
test@example.com
Local hire with transferable visa. Expat package negotiable.
Experience
Safety Officer – Emaar, Dubai
Jan 2020 – Present
Skills
HSE management, local authority coordination
"""
        result = screen_resumes(MINIMAL_JD, [cv])
        output = json.dumps(screening_result_to_dict(result)).lower()
        assert "local" in output or "expat" in output, (
            "UAE business terms 'local'/'expat' should not be stripped from output"
        )


# ---------------------------------------------------------------------------
# Matching — token overlap, no false positives
# ---------------------------------------------------------------------------

class TestMatching:
    def test_short_common_word_does_not_cause_false_positive(self):
        """Single short tokens must not match unrelated JD requirements."""
        # "ISO" is 3 chars and should not match random 3-char tokens
        result = _token_overlap_match("ISO 45001 certification", "risk assessment basics")
        assert result is False

    def test_meaningful_tokens_match(self):
        assert _token_overlap_match("risk assessment", "risk assessment and incident investigation")

    def test_unrelated_requirement_does_not_match(self):
        assert not _token_overlap_match("machine learning tensorflow", "permit-to-work HSE management")

    def test_score_requires_evidence(self):
        """A candidate with no matching skills must score 0 on core job match."""
        from src.resume_screener import score_core_job_match
        profile = CandidateProfile(
            candidate_name="Test",
            contact_info="Not provided",
            years_of_relevant_experience="Not provided",
            skills_inventory=[],
            education=[],
            certifications=[],
            employment_history=[],
            notable_achievements=[],
            gcc_uae_experience="Not provided",
            availability_visa_status="Not provided",
            _raw_text="",
        )
        jd = JDSummary(
            must_have_skills=["HSE management", "risk assessment", "incident investigation"],
            preferred_skills=[],
            minimum_experience_years=5,
            education_requirements=[],
            certification_requirements=[],
            gcc_uae_requirements=[],
            language_requirements=[],
            other_criteria=[],
        )
        dim = score_core_job_match(profile, jd)
        assert dim.score == 0
        assert dim.evidence == "Evidence not found"


# ---------------------------------------------------------------------------
# Certification matching
# ---------------------------------------------------------------------------

class TestCertificationMatching:
    def test_missing_mandatory_cert_flagged(self):
        """NEBOSH in JD but not in CV must produce a missing_mandatory_certifications flag."""
        jd = extract_jd(MINIMAL_JD)
        profile = extract_resume(CANDIDATE_BOB)
        flags = detect_red_flags(profile, jd)
        flag_types = [f.flag_type for f in flags]
        assert "missing_mandatory_certifications" in flag_types

    def test_missing_cert_flag_mentions_cert_name(self):
        jd = extract_jd(MINIMAL_JD)
        profile = extract_resume(CANDIDATE_BOB)
        flags = detect_red_flags(profile, jd)
        cert_flags = [f for f in flags if f.flag_type == "missing_mandatory_certifications"]
        assert cert_flags
        assert "NEBOSH" in cert_flags[0].detail

    def test_present_mandatory_cert_not_flagged(self):
        """Alice has NEBOSH — must_mandatory_certifications flag must NOT appear."""
        jd = extract_jd(MINIMAL_JD)
        profile = extract_resume(CANDIDATE_ALICE)
        flags = detect_red_flags(profile, jd)
        flag_types = [f.flag_type for f in flags]
        assert "missing_mandatory_certifications" not in flag_types

    def test_cert_keyword_extraction(self):
        assert "nebosh" in _extract_cert_keywords("NEBOSH IGC – passed 2016")
        assert "iosh" in _extract_cert_keywords("IOSH Managing Safely")
        assert "pmp" in _extract_cert_keywords("PMP certified project manager")
        assert _extract_cert_keywords("10 years in finance") == set()


# ---------------------------------------------------------------------------
# Experience calculation — no double-counting
# ---------------------------------------------------------------------------

class TestExperienceCalculation:
    def test_overlapping_jobs_not_double_counted(self):
        """Two concurrent 12-month jobs should count as 12 months, not 24."""
        records = [
            EmploymentRecord("Role A", "Employer A", "Jan 2020", "Dec 2020", 11, False),
            EmploymentRecord("Role B", "Employer B", "Jun 2020", "May 2021", 11, False),
        ]
        unique = _calc_unique_months(records)
        assert isinstance(unique, int)
        # Jan 2020 – May 2021 = 16 months, not 22
        assert unique <= 18

    def test_sequential_jobs_counted_fully(self):
        records = [
            EmploymentRecord("Role A", "Employer A", "Jan 2018", "Dec 2019", 23, False),
            EmploymentRecord("Role B", "Employer B", "Jan 2020", "Dec 2021", 23, False),
        ]
        unique = _calc_unique_months(records)
        assert isinstance(unique, int)
        assert unique >= 46  # close to 48 months

    def test_no_dates_returns_not_provided(self):
        records = [
            EmploymentRecord("Role A", "Employer A", "unknown", "unknown", "Not provided", False),
        ]
        unique = _calc_unique_months(records)
        assert unique == "Not provided"

    def test_empty_employment_returns_not_provided(self):
        assert _calc_unique_months([]) == "Not provided"

    def test_overlapping_reflected_in_profile_years(self):
        """Full pipeline: two overlapping roles must not inflate years_of_experience."""
        cv = """\
Overlap Candidate
overlap@example.com

Experience
Jan 2020 – Dec 2022
Employer Alpha
Jan 2021 – Dec 2022
Employer Beta

Skills
project management, stakeholder engagement, reporting
"""
        profile = extract_resume(cv)
        if isinstance(profile.years_of_relevant_experience, int):
            # Should be ~3 years, not ~5
            assert profile.years_of_relevant_experience <= 4


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

class TestRanking:
    def test_candidates_ranked_by_score_descending(self):
        result = screen_resumes(MINIMAL_JD, [CANDIDATE_BOB, CANDIDATE_ALICE])
        scores = [c.total_score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_ranking_table_matches_candidates(self):
        result = screen_resumes(MINIMAL_JD, [CANDIDATE_ALICE, CANDIDATE_BOB])
        assert len(result.ranking_table) == len(result.candidates)
        for i, row in enumerate(result.ranking_table):
            assert row["rank"] == i + 1
            assert row["score"] == result.candidates[i].total_score

    def test_alice_outscores_bob(self):
        """Alice has NEBOSH, UAE experience, and more tenure — must score higher than Bob."""
        result = screen_resumes(MINIMAL_JD, [CANDIDATE_BOB, CANDIDATE_ALICE])
        scores = {c.candidate_name: c.total_score for c in result.candidates}
        assert scores.get("Alice Johnson", 0) > scores.get("Bob Smith", 0)


# ---------------------------------------------------------------------------
# Output safety
# ---------------------------------------------------------------------------

class TestOutputSafety:
    def test_no_raw_text_in_json_output(self):
        result = screen_resumes(MINIMAL_JD, [CANDIDATE_ALICE])
        output = json.dumps(screening_result_to_dict(result))
        assert "_raw_text" not in output

    def test_no_hire_reject_decision_in_output(self):
        result = screen_resumes(MINIMAL_JD, [CANDIDATE_ALICE])
        output = json.dumps(screening_result_to_dict(result)).lower()
        # Check for phrases that would constitute an actual hire/decline decision,
        # not meta-commentary about the absence of such decisions.
        for term in ("hire this candidate", "do not hire", "is rejected", "should be rejected",
                     "reject this candidate", "candidate rejected", "offer declined"):
            assert term not in output, f"Decision term found in output: {term!r}"

    def test_advisory_language_in_executive_summary(self):
        result = screen_resumes(MINIMAL_JD, [CANDIDATE_ALICE])
        assert "advisory" in result.executive_summary.lower()

    def test_no_provider_names_in_output(self):
        result = screen_resumes(MINIMAL_JD, [CANDIDATE_ALICE])
        output = json.dumps(screening_result_to_dict(result)).lower()
        for provider in ("openai", "deepseek", "huggingface", "anthropic", "gpt-"):
            assert provider not in output, f"AI provider name leaked into output: {provider!r}"

"""
Regression tests for CV classification bugs.

Bug 1: Personal CVs misclassified as company_profile when job descriptions
       inside the CV mention "our services", "our mission", employer "ABC LLC", etc.

Bug 2: Strong company signals ("company profile", "corporate profile") must still
       trigger company_profile classification even when combined with CV-like words.
"""

import pytest
from src.cv_parser import CVParser


@pytest.fixture
def parser():
    return CVParser()


# ── Personal CVs that must NOT be misclassified ────────────────────────────────

class TestPersonalCVNotMisclassified:
    def test_cv_with_employer_llc_name(self, parser):
        """Employer name contains 'LLC' — must not trigger company_profile."""
        text = (
            "John Smith\n"
            "Work Experience\n"
            "Senior HSE Manager at XYZ Safety LLC — 2019 to present\n"
            "Managed safety audits and risk assessments.\n"
            "Skills: HSE, ISO 14001, incident investigation\n"
            "Education: BSc Environmental Science\n"
        )
        assert parser.detect_document_type(text) == "cv"

    def test_cv_with_employer_our_services_in_job_desc(self, parser):
        """Job description inside CV mentions 'our services' — must stay as cv."""
        text = (
            "Professional Experience\n"
            "ABC Consulting Ltd — HSE Advisor 2018-2022\n"
            "Our services included environmental audits and safety training.\n"
            "Our mission was zero workplace incidents.\n"
            "Skills: compliance, esg, sustainability\n"
            "Education: MSc Safety Engineering\n"
        )
        assert parser.detect_document_type(text) == "cv"

    def test_cv_with_first_person_markers(self, parser):
        """First-person language is a strong personal-CV signal."""
        text = (
            "I am a certified HSE professional with 10 years of experience.\n"
            "My name is Ahmed Al-Rashid. I have led multiple safety programs.\n"
            "I managed a team of 20 inspectors. Skills: safety, audit, iso 45001\n"
        )
        assert parser.detect_document_type(text) == "cv"

    def test_cv_minimal_signals(self, parser):
        """A CV with minimal signals (only 'skills' + 'education') → 'cv'."""
        text = (
            "Ahmed Al-Rashid\nSkills: python, sql, data analysis\n"
            "Education: BSc Computer Science, UAE University 2015\n"
        )
        assert parser.detect_document_type(text) == "cv"

    def test_cv_with_many_company_mentions_but_personal_language(self, parser):
        """Even if company names appear multiple times, first-person language wins."""
        text = (
            "I am an HSE manager. My experience spans multiple LLC companies.\n"
            "Client base exposure: oil & gas sector. Our vision at my last company "
            "was safety-first. I led teams of 30. Skills: risk assessment, iso 14001\n"
        )
        assert parser.detect_document_type(text) == "cv"


# ── Company profile documents that MUST be classified correctly ────────────────

class TestCompanyProfileClassified:
    def test_explicit_company_profile_heading(self, parser):
        """Document with 'company profile' heading must be classified as company_profile."""
        text = (
            "Company Profile\n"
            "Corporate Profile\n"
            "Company Overview\n"
            "We provide HSE consulting services to the oil & gas sector.\n"
            "Our client base spans the GCC region.\n"
        )
        assert parser.detect_document_type(text) == "company_profile"

    def test_company_profile_with_service_portfolio(self, parser):
        """Service portfolio + company overview + sectors served → company_profile."""
        text = (
            "Company Overview\n"
            "Service Portfolio: safety audits, risk assessments, compliance.\n"
            "Sectors Served: Oil & Gas, Construction, Marine.\n"
            "Core Service Portfolio includes ISO certification support.\n"
        )
        assert parser.detect_document_type(text) == "company_profile"

    def test_corporate_profile_document(self, parser):
        """'corporate profile' alone is a strong signal."""
        text = (
            "Corporate Profile — XYZ Safety Solutions\n"
            "Company Overview: established 2005 in Dubai.\n"
            "Why Clients choose us: proven track record.\n"
        )
        assert parser.detect_document_type(text) == "company_profile"


# ── Edge cases ─────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_text_returns_unknown(self, parser):
        assert parser.detect_document_type("") == "unknown"

    def test_short_text_no_signals_returns_unknown(self, parser):
        assert parser.detect_document_type("Hello world") == "unknown"

    def test_mixed_doc_with_personal_markers_returns_cv(self, parser):
        """If a company brochure is accidentally attached alongside CV text,
        personal markers veto the company_profile classification."""
        text = (
            "Company Profile\n"
            "I am the CEO of this company. My experience spans 20 years.\n"
            "Company Overview — established 2001.\n"
            "Service Portfolio: consulting, training.\n"
        )
        # Personal marker 'i am' vetoes company_profile
        assert parser.detect_document_type(text) != "company_profile"

    def test_two_weak_company_signals_without_strong_insufficient(self, parser):
        """Two weak company signals alone (no 'company profile'/'corporate profile')
        with cv_score ≥ 2 → still cv, not company_profile."""
        text = (
            "Work Experience — Senior Safety Manager at ABC Corporation\n"
            "Service Portfolio: our client base is diverse.\n"
            "Skills: safety, compliance, iso 45001\n"
            "Education: MSc Occupational Health\n"
        )
        result = parser.detect_document_type(text)
        assert result != "company_profile"

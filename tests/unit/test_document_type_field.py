"""Tests for document_type field on ParsedCV and cover letter classification.

Covers:
  - ParsedCV.document_type defaults to "unknown"
  - parse_bytes / parse_file set document_type automatically
  - detect_document_type cover_letter classification
  - cover_letter detection does not regress CV or company_profile cases
"""

import pytest
from src.cv_parser import CVParser, ParsedCV


@pytest.fixture
def parser():
    return CVParser()


# ---------------------------------------------------------------------------
# ParsedCV.document_type default
# ---------------------------------------------------------------------------

class TestParsedCVDocumentTypeDefault:
    def test_default_is_unknown(self):
        p = ParsedCV(
            text="", skills=[], emails=[], phones=[],
            years_experience_hint=None, certifications=[], languages=[],
        )
        assert p.document_type == "unknown"

    def test_field_in_to_dict(self):
        p = ParsedCV(
            text="hello", skills=[], emails=[], phones=[],
            years_experience_hint=None, certifications=[], languages=[],
            document_type="cv",
        )
        d = p.to_dict()
        assert "document_type" in d
        assert d["document_type"] == "cv"


# ---------------------------------------------------------------------------
# parse_bytes sets document_type
# ---------------------------------------------------------------------------

class TestParseBytesDocumentType:
    def test_cv_text_sets_cv(self, parser):
        text = (
            "John Smith\n"
            "Work Experience\nSenior HSE Officer 2019–present\n"
            "Skills: safety, iso 45001\n"
            "Education: BSc Environmental Science\n"
        )
        result = parser.parse_bytes(text.encode(), "cv.txt")
        assert result.document_type == "cv"

    def test_sparse_text_sets_unknown(self, parser):
        result = parser.parse_bytes(b"John Doe\njohn@example.com", "cv.txt")
        assert result.document_type == "unknown"

    def test_company_profile_sets_company_profile(self, parser):
        text = (
            "Company Profile\n"
            "Corporate Profile\n"
            "Company Overview\n"
            "Client base: GCC region. Service portfolio: HSE consulting.\n"
        )
        result = parser.parse_bytes(text.encode(), "doc.txt")
        assert result.document_type == "company_profile"

    def test_cover_letter_sets_cover_letter(self, parser):
        text = (
            "Dear Hiring Manager,\n"
            "I am writing to apply for the HSE Manager position.\n"
            "Sincerely,\nAhmed Al-Rashid\n"
        )
        result = parser.parse_bytes(text.encode(), "cover_letter.txt")
        assert result.document_type == "cover_letter"

    def test_document_type_included_in_to_dict(self, parser):
        text = "Work Experience\nSkills: python\nEducation: BSc CS\n"
        result = parser.parse_bytes(text.encode(), "cv.txt")
        d = result.to_dict()
        assert "document_type" in d
        assert d["document_type"] == result.document_type


# ---------------------------------------------------------------------------
# detect_document_type — cover letter cases
# ---------------------------------------------------------------------------

class TestCoverLetterDetection:
    def test_dear_hiring_manager_plus_sincerely(self, parser):
        text = (
            "Dear Hiring Manager,\n"
            "I am writing to apply for the Safety Officer vacancy.\n"
            "Sincerely,\nMaria Santos\n"
        )
        assert parser.detect_document_type(text) == "cover_letter"

    def test_dear_recruiter_plus_sincerely(self, parser):
        text = (
            "Dear Recruiter,\n"
            "I am applying for the HSE Advisor role advertised on LinkedIn.\n"
            "Please find attached my resume for your consideration.\n"
            "Yours sincerely,\nAhmed Al-Rashid\n"
        )
        assert parser.detect_document_type(text) == "cover_letter"

    def test_two_strong_signals_sufficient(self, parser):
        text = (
            "Dear Hiring Manager,\n"
            "I am applying for the position of Senior Safety Manager.\n"
        )
        assert parser.detect_document_type(text) == "cover_letter"

    def test_three_supporting_signals_without_strong(self, parser):
        text = (
            "To Whom It May Concern,\n"
            "Application for the role of HSE Coordinator.\n"
            "For the position of HSE Coordinator in Dubai.\n"
            "Sincerely,\nFatima Al-Nasser\n"
        )
        assert parser.detect_document_type(text) == "cover_letter"

    def test_cv_with_sincerely_not_classified_cover_letter(self, parser):
        """'Sincerely' alone in a CV (e.g. testimonial) must not trigger cover_letter."""
        text = (
            "John Smith\n"
            "Work Experience\nSafety Manager 2018–2023\n"
            "Skills: iso 45001, audit, risk assessment\n"
            "Education: BSc Environmental Science\n"
            "References available sincerely upon request.\n"
        )
        # Only one supporting signal ("sincerely") with no strong signals — must not be cover_letter
        result = parser.detect_document_type(text)
        assert result != "cover_letter"

    def test_cv_not_reclassified_by_cover_letter_logic(self, parser):
        """A well-formed CV with no salutation/closing stays as 'cv'."""
        text = (
            "Professional Experience\n"
            "HSE Manager at ABC Corp — 2019 to present\n"
            "Skills: safety, compliance, esg\n"
            "Education: MSc Safety Engineering\n"
        )
        assert parser.detect_document_type(text) == "cv"

    def test_company_profile_not_reclassified_by_cover_letter(self, parser):
        """A company profile is never reclassified as cover_letter."""
        text = (
            "Company Profile\n"
            "Corporate Profile\n"
            "Company Overview: established 2005 in Dubai.\n"
            "Why Clients choose us: proven track record.\n"
        )
        assert parser.detect_document_type(text) == "company_profile"


# ---------------------------------------------------------------------------
# Identity document detection
# ---------------------------------------------------------------------------

class TestIdentityDocumentDetection:
    def test_passport_number_classifies_as_identity(self, parser):
        text = (
            "PASSPORT\n"
            "Passport Number: A12345678\n"
            "Date of Birth: 01/01/1990\n"
            "Nationality: United Arab Emirates\n"
            "Expiry Date: 31/12/2029\n"
        )
        assert parser.detect_document_type(text) == "identity_document"

    def test_emirates_id_classifies_as_identity(self, parser):
        text = (
            "Emirates ID\n"
            "Emirates ID: 784-1990-1234567-8\n"
            "Date of Birth: 01/01/1990\n"
            "Nationality: Indian\n"
        )
        assert parser.detect_document_type(text) == "identity_document"

    def test_eid_number_classifies_as_identity(self, parser):
        text = (
            "EID Number: 784-1985-7654321-1\n"
            "Name: Ahmed Al-Rashid\n"
            "Date of Birth: 15/03/1985\n"
        )
        assert parser.detect_document_type(text) == "identity_document"

    def test_national_id_number_classifies_as_identity(self, parser):
        text = (
            "National ID Number: 784-1990-1234567-8\n"
            "Name: Maria Santos\n"
            "Date of Birth: 05/05/1990\n"
            "Nationality: Filipino\n"
        )
        assert parser.detect_document_type(text) == "identity_document"

    def test_cv_with_emirates_id_field_not_reclassified(self, parser):
        """UAE-format CV with Emirates ID in personal details stays as 'cv'."""
        text = (
            "AHMED AL-RASHID\n"
            "Work Experience\n"
            "Senior HSE Manager at ABC Corp — 2019 to present\n"
            "Skills: safety, iso 45001, audit\n"
            "Education: BSc Environmental Science\n"
            "Emirates ID: 784-1985-1234567-1\n"
            "Nationality: UAE\n"
        )
        result = parser.detect_document_type(text)
        assert result == "cv", (
            f"CV with Emirates ID personal field must not be misclassified: got {result!r}"
        )

    def test_cv_with_passport_field_not_reclassified(self, parser):
        """CV that includes passport number in personal details stays as 'cv'."""
        text = (
            "John Smith\n"
            "Work Experience\nSafety Manager 2018-2023\n"
            "Skills: HSE, audit, iso 45001\n"
            "Education: MSc Safety Engineering\n"
            "Passport No: A123456\n"
            "Nationality: British\n"
        )
        result = parser.detect_document_type(text)
        assert result == "cv", (
            f"CV with passport field must not be misclassified: got {result!r}"
        )

    def test_identity_doc_never_classified_as_cv(self, parser):
        """A pure passport scan must never be classified as 'cv'."""
        text = (
            "Passport Number: A12345678\n"
            "Date of Birth: 01/01/1990\n"
            "Nationality: India\n"
            "Expiry Date: 31/12/2029\n"
        )
        result = parser.detect_document_type(text)
        assert result != "cv"
        assert result == "identity_document"

    def test_parse_bytes_sets_identity_document_type(self, parser):
        text = (
            "Emirates ID: 784-1990-1234567-8\n"
            "Name: Fatima Al-Nasser\n"
            "Date of Birth: 10/10/1990\n"
        )
        result = parser.parse_bytes(text.encode(), "id.txt")
        assert result.document_type == "identity_document"

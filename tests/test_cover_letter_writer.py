"""Test cover letter writer identity safety and functionality."""

import pytest
from src.cover_letter_writer import (
    generate_cover_letter,
    generate_cover_letter_with_identity,
    generate_batch_cover_letters,
    generate_batch_cover_letters_with_identity,
    CoverLetterIdentity,
    CoverLetterIdentityError
)


class TestCoverLetterWriter:
    """Test cover letter generation with identity safety."""

    def test_structured_identity_with_complete_profile(self):
        """Test that structured identity object works with complete profile."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "location": "Dubai"
        }

        identity = CoverLetterIdentity(
            name="Verified User",
            location="Dubai, UAE",
            title="Senior HSE Officer",
            company="Current Company",
            years_experience=8.0,
            profile_line="8+ years in HSE leadership and environmental compliance",
            verified_strengths=["NEBOSH certification", "Risk assessment", "Safety management"]
        )

        cover_letter = generate_cover_letter_with_identity(job, identity)

        # Should use verified identity data
        assert "Verified User" in cover_letter
        assert "Dubai, UAE" in cover_letter
        assert "8+ years in HSE leadership" in cover_letter

    def test_structured_identity_requires_verified_data(self):
        """Test that structured identity fails without verified experience data."""
        job = {
            "title": "Test Job",
            "company": "Test Company"
        }

        # Identity with no verified experience data should fail
        identity = CoverLetterIdentity(
            name="Test User",
            location="Dubai, UAE"
            # No years_experience, no profile_line, no verified_strengths
        )

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter_with_identity(job, identity)
        assert "Profile line or verified experience data required" in str(exc_info.value)

    def test_comprehensive_generic_phrase_ban(self):
        """Test that no generic fallback identity phrases appear in output."""
        job = {
            "title": "Safety Manager",
            "company": "Safety Corp"
        }

        identity = CoverLetterIdentity(
            name="Complete User",
            location="Dubai, UAE",
            years_experience=10.0,
            profile_line="10+ years in safety management and environmental compliance",
            verified_strengths=["Safety management", "Risk assessment"]
        )

        cover_letter = generate_cover_letter_with_identity(job, identity)

        # Comprehensive list of forbidden generic phrases
        forbidden_phrases = [
            "Professional Candidate",
            "experienced professional with relevant background",
            "my relevant experience",
            "generic",
            "placeholder",
            "suitable candidate",
            "qualified professional",
            "ideal candidate",
            "appropriate candidate"
        ]

        for phrase in forbidden_phrases:
            assert phrase not in cover_letter, f"Generic phrase '{phrase}' should not appear in output"

    def test_verified_profile_data_in_opening_line(self):
        """Test that opening line uses verified profile data."""
        job = {
            "title": "Environmental Manager",
            "company": "Eco Corp"
        }

        identity = CoverLetterIdentity(
            name="Test User",
            location="Abu Dhabi, UAE",
            profile_line="5+ years in environmental management and sustainability"
        )

        cover_letter = generate_cover_letter_with_identity(job, identity)

        # Opening should contain verified profile line
        assert "5+ years in environmental management" in cover_letter
        # Should not contain generic fallback
        assert "my relevant experience" not in cover_letter

    def test_no_unverified_experience_claims(self):
        """Test that no unverified experience claims are inserted."""
        job = {
            "title": "HSE Manager",
            "company": "Safety Corp",
            "description": "Looking for HSE Manager with safety experience"
        }

        identity = CoverLetterIdentity(
            name="Test User",
            location="Dubai, UAE",
            years_experience=3.0,
            verified_strengths=["HSE management", "Safety protocols"]  # Skills that match job
        )

        cover_letter = generate_cover_letter_with_identity(job, identity)

        # Should only contain verified experience
        assert "3+ years" in cover_letter
        assert "HSE management" in cover_letter or "Safety protocols" in cover_letter

        # Should not contain unverified claims like "80+ locations"
        assert "80+ locations" not in cover_letter
        assert "multi-site operations" not in cover_letter

    def test_batch_with_structured_identity(self):
        """Test batch generation with structured identity object."""
        jobs = [
            {"title": "HSE Manager", "company": "Company A", "location": "Dubai"},
            {"title": "ESG Specialist", "company": "Company B", "location": "Abu Dhabi"}
        ]

        identity = CoverLetterIdentity(
            name="Batch User",
            location="Sharjah, UAE",
            years_experience=5.0,
            profile_line="5+ years in environmental compliance"
        )

        letters = generate_batch_cover_letters_with_identity(jobs, identity)

        assert len(letters) == 2

        # All letters should use verified identity
        for letter in letters.values():
            assert "Batch User" in letter
            assert "Sharjah, UAE" in letter
            assert "5+ years in environmental compliance" in letter

    def test_identity_validation_on_creation(self):
        """Test that CoverLetterIdentity validates required fields."""
        # Missing name should fail
        with pytest.raises(CoverLetterIdentityError):
            CoverLetterIdentity(name="", location="Dubai, UAE")

        with pytest.raises(CoverLetterIdentityError):
            CoverLetterIdentity(name=None, location="Dubai, UAE")

        # Missing location should fail
        with pytest.raises(CoverLetterIdentityError):
            CoverLetterIdentity(name="Test User", location="")

        with pytest.raises(CoverLetterIdentityError):
            CoverLetterIdentity(name="Test User", location=None)

    def test_generate_cover_letter_requires_identity(self):
        """Test that generate_cover_letter fails safely without identity."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "location": "Dubai"
        }

        # Calling without identity should fail
        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(job)
        assert "Verified identity is required" in str(exc_info.value)

    def test_generate_batch_cover_letters_requires_identity(self):
        """Test that generate_batch_cover_letters fails safely without identity."""
        jobs = [
            {"title": "HSE Manager", "company": "Company A"}
        ]

        # Calling without identity should fail
        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_batch_cover_letters(jobs)
        assert "Verified identity is required" in str(exc_info.value)

    def test_no_hardcoded_roben_identity_anywhere(self):
        """Test that safe generated output contains no hardcoded identity."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company"
        }

        identity = CoverLetterIdentity(
            name="Safe User",
            location="Safe Location, UAE",
            years_experience=5.0,
            profile_line="5+ years in environmental management"
        )

        cover_letter = generate_cover_letter_with_identity(job, identity)

        # Comprehensive list of forbidden hardcoded identity phrases
        forbidden_phrases = [
            "Roben Edwan",
            "Ajman, UAE",
            "80+ locations",
            "10+ years in environmental management",
            "Professional Candidate"
        ]

        for phrase in forbidden_phrases:
            assert phrase not in cover_letter, f"Hardcoded phrase '{phrase}' should not appear in safe output"

    def test_no_roben_identity_in_output(self):
        """Test that Roben Edwan identity does not appear unless explicitly passed."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company"
        }

        identity = CoverLetterIdentity(
            name="Different User",
            location="Different Location, UAE",
            years_experience=5.0,
            profile_line="5+ years in environmental management"
        )

        cover_letter = generate_cover_letter_with_identity(job, identity)

        # Should not contain Roben identity
        assert "Roben Edwan" not in cover_letter
        assert "Ajman, UAE" not in cover_letter
        # Should contain the passed identity
        assert "Different User" in cover_letter
        assert "Different Location, UAE" in cover_letter

    def test_no_hardcoded_80_locations(self):
        """Test that 80+ locations does not appear unless from verified profile."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company"
        }

        identity = CoverLetterIdentity(
            name="Test User",
            location="Dubai, UAE",
            years_experience=3.0,
            verified_strengths=["Safety management"]
        )

        cover_letter = generate_cover_letter_with_identity(job, identity)

        # Should not contain hardcoded 80+ locations
        assert "80+ locations" not in cover_letter

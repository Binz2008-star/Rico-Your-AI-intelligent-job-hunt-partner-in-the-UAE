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

    def test_complete_profile_generates_cover_letter_with_actual_user_data(self):
        """Test that complete profile generates cover letter with user's actual data."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "location": "Dubai",
            "description": "Looking for HSE Manager with safety experience",
            "requirements": ["NEBOSH", "5 years experience"]
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="John Doe",
            user_location="Abu Dhabi, UAE",
            user_years_experience=8.5,
            user_skills=["NEBOSH certification", "Risk assessment", "Safety management"]
        )

        # Verify user data is used
        assert "John Doe" in cover_letter
        assert "Abu Dhabi, UAE" in cover_letter
        assert "8+ years of relevant experience" in cover_letter
        assert "NEBOSH certification" in cover_letter

        # Verify job data is included
        assert "HSE Manager" in cover_letter
        assert "Test Company" in cover_letter
        assert "Dubai" in cover_letter

    def test_output_does_not_contain_hardcoded_roben_identity(self):
        """Test that output does not contain 'Roben Edwan' unless passed explicitly."""
        job = {
            "title": "ESG Specialist",
            "company": "Test Corp",
            "location": "Sharjah"
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Jane Smith",
            user_location="Dubai, UAE"
        )

        # Should not contain hardcoded identity
        assert "Roben Edwan" not in cover_letter
        assert "Ajman, UAE" not in cover_letter
        assert "10+ years in environmental management" not in cover_letter

        # Should contain user's actual data
        assert "Jane Smith" in cover_letter
        assert "Dubai, UAE" in cover_letter

    def test_output_does_not_contain_generic_fallback_identity(self):
        """Test that output does not contain generic fallback identity."""
        job = {
            "title": "Environmental Officer",
            "company": "Green Tech",
            "location": "Abu Dhabi"
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Ahmed Hassan",
            user_location="Sharjah, UAE"
        )

        # Should not contain generic fallbacks
        assert "Professional Candidate" not in cover_letter
        assert "experienced professional with relevant background" not in cover_letter
        # Only check against forbidden generic phrases, not normal UAE usage
        assert "Professional Candidate" not in cover_letter

    def test_missing_user_name_fails_safely(self):
        """Test that missing user_name raises CoverLetterIdentityError."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company"
        }

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(
                job,
                user_name="",  # Empty name
                user_location="Dubai, UAE"
            )
        assert "User name is required" in str(exc_info.value)

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(
                job,
                user_name=None,  # None name
                user_location="Dubai, UAE"
            )
        assert "User name is required" in str(exc_info.value)

    def test_missing_user_location_fails_safely(self):
        """Test that missing user_location raises CoverLetterIdentityError."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company"
        }

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(
                job,
                user_name="John Doe",
                user_location=""  # Empty location
            )
        assert "User location is required" in str(exc_info.value)

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(
                job,
                user_name="John Doe",
                user_location=None  # None location
            )
        assert "User location is required" in str(exc_info.value)

    def test_missing_skills_uses_neutral_wording(self):
        """Test that missing skills does not invent HSE/ESG/etc."""
        job = {
            "title": "Safety Manager",
            "company": "Safety Corp",
            "description": "Looking for safety manager"
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Test User",
            user_location="Dubai, UAE",
            user_skills=None  # No skills provided
        )

        # Should use neutral wording, not invent specific skills
        assert "my relevant experience" in cover_letter
        assert "NEBOSH" not in cover_letter
        assert "ISO" not in cover_letter
        assert "risk assessment" not in cover_letter

    def test_job_title_company_included_from_job_data(self):
        """Test that job title and company are included from job data."""
        job = {
            "title": "QHSE Coordinator",
            "company": "Multi-National Corp",
            "location": "Abu Dhabi"
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Test User",
            user_location="Dubai, UAE"
        )

        # Verify job data is included
        assert "QHSE Coordinator" in cover_letter
        assert "Multi-National Corp" in cover_letter
        assert "Abu Dhabi" in cover_letter

    def test_skill_matching_works_with_relevant_skills(self):
        """Test that relevant skills are matched and included."""
        job = {
            "title": "Environmental Compliance Officer",
            "company": "Eco Corp",
            "description": "Looking for someone with environmental compliance and audit experience",
            "requirements": ["Environmental compliance", "Auditing"]
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Test User",
            user_location="Dubai, UAE",
            user_skills=["Environmental compliance", "Risk assessment", "Auditing", "Project management"]
        )

        # Should include relevant skills that match job
        assert "Environmental compliance" in cover_letter
        assert "Auditing" in cover_letter
        assert "expertise in" in cover_letter

    def test_batch_cover_letters_with_profile_data(self):
        """Test batch cover letter generation with profile data."""
        jobs = [
            {
                "title": "HSE Manager",
                "company": "Company A",
                "location": "Dubai"
            },
            {
                "title": "ESG Specialist",
                "company": "Company B",
                "location": "Abu Dhabi"
            }
        ]

        letters = generate_batch_cover_letters(
            jobs,
            user_name="Batch User",
            user_location="Sharjah, UAE",
            user_years_experience=5.0
        )

        assert len(letters) == 2

        # Verify all letters use user data
        for letter in letters.values():
            assert "Batch User" in letter
            assert "Sharjah, UAE" in letter
            assert "5+ years of relevant experience" in letter

        # Verify job-specific content
        assert any("HSE Manager" in letter for letter in letters.values())
        assert any("ESG Specialist" in letter for letter in letters.values())
        assert any("Company A" in letter for letter in letters.values())
        assert any("Company B" in letter for letter in letters.values())

    def test_batch_cover_letters_missing_required_fields_fails(self):
        """Test that batch generation fails with missing required fields."""
        jobs = [{"title": "Test Job", "company": "Test Co"}]

        with pytest.raises(CoverLetterIdentityError):
            generate_batch_cover_letters(
                jobs,
                user_name="",  # Missing name
                user_location="Dubai, UAE"
            )

    def test_role_specific_opening_focus(self):
        """Test that different job roles get appropriate opening focus."""
        base_job = {"company": "Test Co", "location": "Dubai"}

        # ESG role
        esg_job = {**base_job, "title": "ESG Manager"}
        esg_letter = generate_cover_letter(esg_job, "User", "Dubai, UAE")
        assert "ESG, sustainability strategy" in esg_letter

        # HSE role
        hse_job = {**base_job, "title": "HSE Manager"}
        hse_letter = generate_cover_letter(hse_job, "User", "Dubai, UAE")
        assert "HSE leadership, risk control" in hse_letter

        # Environmental role
        env_job = {**base_job, "title": "Environmental Manager"}
        env_letter = generate_cover_letter(env_job, "User", "Dubai, UAE")
        assert "environmental compliance, waste operations" in env_letter

    def test_whitespace_cleaning(self):
        """Test that whitespace is properly cleaned in inputs."""
        job = {
            "title": "  HSE Manager  ",
            "company": "\tTest Company\n",
            "location": "  Dubai  "
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="  John Doe  ",
            user_location="  Abu Dhabi, UAE  "
        )

        # Should not contain excessive whitespace
        assert "  HSE Manager  " not in cover_letter
        assert "\tTest Company\n" not in cover_letter
        assert "  John Doe  " not in cover_letter
        assert "  Abu Dhabi, UAE  " not in cover_letter

        # Should contain cleaned values
        assert "HSE Manager" in cover_letter
        assert "Test Company" in cover_letter
        assert "John Doe" in cover_letter
        assert "Abu Dhabi, UAE" in cover_letter

    def test_verified_name_location_in_first_two_lines(self):
        """Test that verified name and location appear in first two lines of closing."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "location": "Dubai"
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Verified User",
            user_location="Verified Location, UAE"
        )

        lines = cover_letter.split('\n')

        # Find the closing section (Sincerely, name, location)
        closing_section = []
        in_closing = False
        for line in lines:
            if "Sincerely" in line:
                in_closing = True
            if in_closing:
                closing_section.append(line)

        # Verify name and location are in closing section
        closing_text = '\n'.join(closing_section)
        assert "Verified User" in closing_text
        assert "Verified Location, UAE" in closing_text

    def test_no_generic_fallback_phrases_with_complete_profile(self):
        """Test that complete profile eliminates all generic fallback phrases."""
        job = {
            "title": "Safety Manager",
            "company": "Safety Corp",
            "description": "Looking for safety manager"
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Complete User",
            user_location="Dubai, UAE",
            user_years_experience=10.0,
            user_skills=["Safety management", "Risk assessment", "NEBOSH"]
        )

        # Should not contain any generic fallback phrases
        forbidden_phrases = [
            "Professional Candidate",
            "experienced professional with relevant background",
            "my relevant experience",  # Should use actual experience instead
            "generic",
            "placeholder"
        ]

        for phrase in forbidden_phrases:
            assert phrase not in cover_letter, f"Generic phrase '{phrase}' should not appear in output with complete profile"

        # Should contain actual user data
        assert "Complete User" in cover_letter
        assert "Dubai, UAE" in cover_letter
        assert "10+ years" in cover_letter

    def test_exact_opening_sentence_shape(self):
        """Test that opening sentence has consistent shape with verified identity."""
        job = {
            "title": "HSE Manager",
            "company": "Test Company",
            "location": "Dubai"
        }

        cover_letter = generate_cover_letter(
            job,
            user_name="Test User",
            user_location="Dubai, UAE",
            user_years_experience=5.0
        )

        lines = cover_letter.split('\n')

        # Find the opening statement (first non-empty line after "Dear Hiring Manager")
        opening_line = None
        for line in lines:
            if line.strip() and "Dear Hiring Manager" not in line:
                opening_line = line.strip()
                break

        assert opening_line is not None, "Should have an opening line"

        # Opening should follow pattern: "I am writing to express my interest in the {title} position at {company} in {location}"
        assert "I am writing to express my interest in the" in opening_line
        assert "HSE Manager" in opening_line
        assert "Test Company" in opening_line
        assert "Dubai" in opening_line

    def test_hard_failure_on_incomplete_identity(self):
        """Test that incomplete identity causes hard failure without silent degradation."""
        job = {
            "title": "Test Job",
            "company": "Test Company"
        }

        # Test each required field individually
        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(job, "", "Dubai, UAE")
        assert "User name is required" in str(exc_info.value)

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(job, "Test User", "")
        assert "User location is required" in str(exc_info.value)

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(job, None, "Dubai, UAE")
        assert "User name is required" in str(exc_info.value)

        with pytest.raises(CoverLetterIdentityError) as exc_info:
            generate_cover_letter(job, "Test User", None)
        assert "User location is required" in str(exc_info.value)

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
            "company": "Safety Corp"
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

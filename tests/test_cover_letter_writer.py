"""Test cover letter writer identity safety and functionality."""

import pytest
from src.cover_letter_writer import (
    generate_cover_letter,
    generate_batch_cover_letters,
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
        assert "UAE" not in cover_letter or "Sharjah, UAE" in cover_letter  # Only user location
        assert "experienced professional with relevant background" not in cover_letter

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

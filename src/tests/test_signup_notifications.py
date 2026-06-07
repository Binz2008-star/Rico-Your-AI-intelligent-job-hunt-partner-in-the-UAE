"""Unit tests for signup notification email formatting."""
from datetime import datetime, timezone

from src.services.signup_notifications import (
    build_signup_notification_body,
    _calculate_profile_completeness,
)


def test_calculate_profile_completeness_empty():
    """Test completeness calculation with no profile data."""
    percentage, action = _calculate_profile_completeness(None)
    assert percentage == 0
    assert action == "Ask user to complete profile"


def test_calculate_profile_completeness_empty_dict():
    """Test completeness calculation with empty profile dict."""
    percentage, action = _calculate_profile_completeness({})
    assert percentage == 0
    assert action == "Ask user to complete profile"


def test_calculate_profile_completeness_cv_missing():
    """Test recommended action when CV is missing (highest priority)."""
    profile = {
        "target_roles": ["Software Engineer"],
        "preferred_cities": ["Dubai"],
        "years_experience": 5,
        "current_role": "Developer",
        "skills": ["Python", "JavaScript"],
    }
    percentage, action = _calculate_profile_completeness(profile)
    assert percentage == 83  # 5/6 fields filled
    assert action == "Ask user to upload CV"


def test_calculate_profile_completeness_target_roles_missing():
    """Test recommended action when target_roles missing but CV exists."""
    profile = {
        "preferred_cities": ["Dubai"],
        "years_experience": 5,
        "current_role": "Developer",
        "skills": ["Python"],
        "cv_filename": "resume.pdf",
    }
    percentage, action = _calculate_profile_completeness(profile)
    assert percentage == 83  # 5/6 fields filled
    assert action == "Ask user to add target roles"


def test_calculate_profile_completeness_target_roles_empty_list():
    """Test recommended action when target_roles is empty list but CV exists."""
    profile = {
        "target_roles": [],
        "preferred_cities": ["Dubai"],
        "years_experience": 5,
        "current_role": "Developer",
        "skills": ["Python"],
        "cv_filename": "resume.pdf",
    }
    percentage, action = _calculate_profile_completeness(profile)
    assert percentage == 83  # 5/6 fields filled (empty list counts as missing)
    assert action == "Ask user to add target roles"


def test_calculate_profile_completeness_cities_missing():
    """Test recommended action when preferred_cities missing but CV and target_roles exist."""
    profile = {
        "target_roles": ["Software Engineer"],
        "years_experience": 5,
        "current_role": "Developer",
        "skills": ["Python"],
        "cv_filename": "resume.pdf",
    }
    percentage, action = _calculate_profile_completeness(profile)
    assert percentage == 83  # 5/6 fields filled
    assert action == "Ask user to add preferred UAE cities"


def test_calculate_profile_completeness_cities_empty_list():
    """Test recommended action when preferred_cities is empty list but CV and target_roles exist."""
    profile = {
        "target_roles": ["Software Engineer"],
        "preferred_cities": [],
        "years_experience": 5,
        "current_role": "Developer",
        "skills": ["Python"],
        "cv_filename": "resume.pdf",
    }
    percentage, action = _calculate_profile_completeness(profile)
    assert percentage == 83  # 5/6 fields filled (empty list counts as missing)
    assert action == "Ask user to add preferred UAE cities"


def test_calculate_profile_completeness_low_completion():
    """Test recommended action when completeness < 80 but critical fields exist."""
    profile = {
        "target_roles": ["Software Engineer"],
        "preferred_cities": ["Dubai"],
        "cv_filename": "resume.pdf",
    }
    percentage, action = _calculate_profile_completeness(profile)
    assert percentage == 50  # 3/6 fields filled
    assert action == "Ask user to complete remaining profile details"


def test_calculate_profile_completeness_ready():
    """Test recommended action when all critical fields exist and completeness >= 80."""
    profile = {
        "target_roles": ["Software Engineer"],
        "preferred_cities": ["Dubai"],
        "years_experience": 5,
        "current_role": "Developer",
        "skills": ["Python", "JavaScript"],
        "cv_filename": "resume.pdf",
    }
    percentage, action = _calculate_profile_completeness(profile)
    assert percentage == 100
    assert action == "Ready for job matching"


def test_build_signup_notification_body_no_profile():
    """Test email body with no profile data."""
    body = build_signup_notification_body(
        name="John Doe",
        email="john@example.com",
        user_id=123,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        plan="free",
        profile=None,
    )
    assert "Name: John Doe" in body
    assert "Email: john@example.com" in body
    assert "User ID: 123" in body
    assert "Plan: free" in body
    assert "Country: Not provided" in body
    assert "City: Not provided" in body
    assert "Target roles: Not provided" in body
    assert "Industry: Not provided" in body
    assert "Years of experience: Not provided" in body
    assert "CV uploaded: No" in body
    assert "Profile completeness: 0%" in body
    assert "Ask user to complete profile" in body


def test_build_signup_notification_body_with_profile():
    """Test email body with complete profile data."""
    profile = {
        "country": "UAE",
        "preferred_cities": ["Dubai", "Abu Dhabi"],
        "target_roles": ["Software Engineer", "Full Stack Developer"],
        "industries": ["Technology", "Finance"],
        "years_experience": 5,
        "current_role": "Senior Developer",
        "skills": ["Python", "JavaScript", "React"],
        "cv_filename": "resume.pdf",
    }
    body = build_signup_notification_body(
        name="Jane Smith",
        email="jane@example.com",
        user_id=456,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        plan="free",
        profile=profile,
    )
    assert "Name: Jane Smith" in body
    assert "Email: jane@example.com" in body
    assert "Country: UAE" in body
    assert "City: Dubai, Abu Dhabi" in body
    assert "Target roles: Software Engineer, Full Stack Developer" in body
    assert "Industry: Technology, Finance" in body
    assert "Years of experience: 5 years" in body
    assert "CV uploaded: Yes" in body
    assert "Profile completeness: 100%" in body
    assert "Ready for job matching" in body


def test_build_signup_notification_body_partial_profile():
    """Test email body with partial profile data (CV missing)."""
    profile = {
        "preferred_cities": ["Dubai"],
        "target_roles": ["Data Scientist"],
        "years_experience": 3,
    }
    body = build_signup_notification_body(
        name="Bob Johnson",
        email="bob@example.com",
        user_id=789,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        plan="free",
        profile=profile,
    )
    assert "Name: Bob Johnson" in body
    assert "Country: Not provided" in body
    assert "City: Dubai" in body
    assert "Target roles: Data Scientist" in body
    assert "Industry: Not provided" in body
    assert "Years of experience: 3 years" in body
    assert "CV uploaded: No" in body
    assert "Profile completeness: 50%" in body
    assert "Ask user to upload CV" in body


def test_build_signup_notification_body_empty_name():
    """Test email body with empty name (uses email as fallback in subject)."""
    body = build_signup_notification_body(
        name=None,
        email="noname@example.com",
        user_id=999,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        plan="free",
        profile=None,
    )
    assert "Name: Not provided" in body
    assert "Email: noname@example.com" in body


def test_build_signup_notification_body_sections():
    """Test that all required sections are present."""
    body = build_signup_notification_body(
        name="Test User",
        email="test@example.com",
        user_id=1,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        plan="free",
        profile=None,
    )
    assert "Account:" in body
    assert "Location & Language:" in body
    assert "Career Profile:" in body
    assert "Recommended next action:" in body

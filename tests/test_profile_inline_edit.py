"""Test profile inline editing with extended fields."""
import pytest
from fastapi.testclient import TestClient


def test_profile_update_request_schema_includes_extended_fields():
    """Verify ProfileUpdateRequest schema includes new fields."""
    from src.api.routers.rico_chat import ProfileUpdateRequest

    # Verify the schema accepts the new identity/contact fields
    request = ProfileUpdateRequest(
        phone="+971501234567",
        telegram_username="testuser",
        visa_status="Employment Visa",
        notice_period="1 month",
        minimum_salary_aed=15000,
        current_company="Test Company",
        linkedin_url="https://linkedin.com/in/testuser",
        salary_expectation_aed=20000,
    )

    assert request.phone == "+971501234567"
    assert request.telegram_username == "testuser"
    assert request.visa_status == "Employment Visa"
    assert request.notice_period == "1 month"
    assert request.minimum_salary_aed == 15000
    assert request.current_company == "Test Company"
    assert request.linkedin_url == "https://linkedin.com/in/testuser"
    assert request.salary_expectation_aed == 20000


def test_profile_response_schema_includes_extended_fields():
    """Verify ProfileResponse schema includes new fields."""
    from src.api.routers.rico_chat import ProfileResponse

    # Verify the response schema includes the new fields
    response = ProfileResponse(
        profile_exists=True,
        user_id="test@example.com",
        phone="+971501234567",
        telegram_username="testuser",
        visa_status="Employment Visa",
        notice_period="1 month",
        minimum_salary_aed=15000,
        current_company="Test Company",
        linkedin_url="https://linkedin.com/in/testuser",
        salary_expectation_aed=20000,
    )

    assert response.phone == "+971501234567"
    assert response.telegram_username == "testuser"
    assert response.visa_status == "Employment Visa"
    assert response.notice_period == "1 month"
    assert response.minimum_salary_aed == 15000
    assert response.current_company == "Test Company"
    assert response.linkedin_url == "https://linkedin.com/in/testuser"
    assert response.salary_expectation_aed == 20000


def test_profile_update_endpoint_accepts_all_new_fields():
    """Verify update_profile endpoint handler processes all new fields."""
    from src.api.routers.rico_chat import ProfileUpdateRequest

    # Test that all fields are accepted and processed
    request = ProfileUpdateRequest(
        name="Test User",
        phone="+971501234567",
        telegram_username="testuser",
        target_roles=["Engineer"],
        preferred_cities=["Dubai"],
        salary_expectation_aed=20000,
        minimum_salary_aed=15000,
        years_experience=5,
        current_role="Senior Engineer",
        current_company="Test Company",
        linkedin_url="https://linkedin.com/in/testuser",
        visa_status="Employment Visa",
        notice_period="1 month",
        skills=["Python", "React"],
    )

    # Verify model_dump includes all fields
    updates = request.model_dump(exclude_unset=True)
    assert "phone" in updates
    assert "telegram_username" in updates
    assert "visa_status" in updates
    assert "notice_period" in updates
    assert "minimum_salary_aed" in updates
    assert "current_company" in updates
    assert "linkedin_url" in updates
    assert "salary_expectation_aed" in updates


def test_profile_update_regression_target_roles_skills_cities():
    """Regression test: ensure target_roles, skills, preferred_cities still work."""
    from src.api.routers.rico_chat import ProfileUpdateRequest

    # Verify array fields still work correctly
    request = ProfileUpdateRequest(
        target_roles=["Engineer", "Manager"],
        preferred_cities=["Dubai", "Abu Dhabi"],
        skills=["Python", "React", "SQL"],
        salary_expectation_aed=25000,
    )

    updates = request.model_dump(exclude_unset=True)
    assert updates["target_roles"] == ["Engineer", "Manager"]
    assert updates["preferred_cities"] == ["Dubai", "Abu Dhabi"]
    assert updates["skills"] == ["Python", "React", "SQL"]
    assert updates["salary_expectation_aed"] == 25000


def test_profile_patch_calls_upsert_profile_with_extended_fields(monkeypatch):
    """Verify PATCH /api/v1/rico/profile calls upsert_profile with extended fields."""
    from src.api.app import app
    import src.api.routers.rico_chat as rico_chat_router
    from src.rico_agent import RicoProfile

    captured = {}

    def mock_get_user(request):
        user = {"email": "test@example.com", "role": "user"}
        request.state.current_user = user
        request.state.user_id = user["email"]
        return user

    def mock_upsert_profile(user_id, updates, **kwargs):
        captured["user_id"] = user_id
        captured["updates"] = updates
        captured["require_db"] = kwargs.get("require_db")
        # Return RicoProfile as production does
        return RicoProfile(user_id=user_id, email=user_id, **updates)

    # Patch get_current_user in the router module where it's called
    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)
    monkeypatch.setattr(rico_chat_router, "upsert_profile", mock_upsert_profile)

    payload = {
        "phone": "+971501234567",
        "telegram_username": "testuser",
        "visa_status": "Employment Visa",
        "notice_period": "1 month",
        "minimum_salary_aed": 15000,
        "current_company": "Test Company",
        "linkedin_url": "https://linkedin.com/in/testuser",
    }

    client = TestClient(app)
    response = client.patch("/api/v1/rico/profile", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert set(response.json()["updated_fields"]) == set(payload.keys())
    assert captured["user_id"] == "test@example.com"
    assert captured["updates"] == payload


def test_profile_get_returns_extended_fields_from_mocked_profile(monkeypatch):
    """Verify GET /api/v1/rico/profile returns extended fields from mocked profile."""
    from src.api.app import app
    import src.api.routers.rico_chat as rico_chat_router
    from src.rico_agent import RicoProfile

    def mock_get_user(request):
        user = {"email": "test@example.com", "role": "user"}
        request.state.current_user = user
        request.state.user_id = user["email"]
        return user

    def mock_get_profile(user_id):
        return RicoProfile(
            user_id=user_id,
            name="Test User",
            email=user_id,
            phone="+971501234567",
            telegram_username="testuser",
            visa_status="Employment Visa",
            notice_period="1 month",
            minimum_salary_aed=15000,
            current_company="Test Company",
            linkedin_url="https://linkedin.com/in/testuser",
            target_roles=["Engineer"],
            preferred_cities=["Dubai"],
            skills=["Python"],
            salary_expectation_aed=20000,
        )

    # Patch get_current_user in the router module where it's called
    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)
    monkeypatch.setattr(rico_chat_router, "get_profile", mock_get_profile)

    client = TestClient(app)
    response = client.get("/api/v1/rico/profile")

    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "+971501234567"
    assert data["telegram_username"] == "testuser"
    assert data["visa_status"] == "Employment Visa"
    assert data["notice_period"] == "1 month"
    assert data["minimum_salary_aed"] == 15000
    assert data["current_company"] == "Test Company"
    assert data["linkedin_url"] == "https://linkedin.com/in/testuser"
    assert data["salary_expectation_aed"] == 20000

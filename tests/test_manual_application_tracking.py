"""Test manual application tracking via POST /api/v1/applications/manual."""
import pytest
from fastapi.testclient import TestClient


def test_manual_application_create_requires_auth():
    """Verify that manual application creation requires authentication."""
    from src.api.app import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/applications/manual",
        json={
            "title": "Senior Manager Audit Programs",
            "company": "TALENTMATE",
            "location": "Abu Dhabi",
            "status": "applied",
        },
    )
    assert response.status_code in (401, 403)


def test_manual_application_create_calls_repo(monkeypatch):
    """Verify manual application creation calls repository with correct args."""
    from src.api.app import app
    from src.api.deps import get_current_user_id
    import src.api.routers.applications as applications_router

    calls = {}

    def mock_get_user_id():
        return "test@example.com"

    def mock_create_manual(*, title, company, location, url, status, user_id):
        calls.update(
            {
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "status": status,
                "user_id": user_id,
            }
        )
        return True

    original_override = app.dependency_overrides.get(get_current_user_id, None)
    app.dependency_overrides[get_current_user_id] = mock_get_user_id
    monkeypatch.setattr(applications_router, "create_manual", mock_create_manual)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/applications/manual",
            json={
                "title": "Senior Manager Audit Programs",
                "company": "TALENTMATE",
                "location": "Abu Dhabi",
                "url": "https://example.com/job",
                "status": "applied",
            },
        )
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user_id] = original_override
        else:
            app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert response.json()["message"] == "Manual application record created"

    assert calls == {
        "title": "Senior Manager Audit Programs",
        "company": "TALENTMATE",
        "location": "Abu Dhabi",
        "url": "https://example.com/job",
        "status": "applied",
        "user_id": "test@example.com",
    }


def test_manual_application_create_requires_title_and_company(monkeypatch):
    """Verify that title and company are required fields."""
    from src.api.app import app
    from src.api.deps import get_current_user_id
    import src.api.routers.applications as applications_router

    def mock_get_user_id():
        return "test@example.com"

    def mock_create_manual(*, title, company, location, url, status, user_id):
        return True

    original_override = app.dependency_overrides.get(get_current_user_id, None)
    app.dependency_overrides[get_current_user_id] = mock_get_user_id
    monkeypatch.setattr(applications_router, "create_manual", mock_create_manual)

    client = TestClient(app)

    try:
        # Missing title
        response = client.post(
            "/api/v1/applications/manual",
            json={
                "company": "TALENTMATE",
                "status": "applied",
            },
        )
        assert response.status_code == 422

        # Missing company
        response = client.post(
            "/api/v1/applications/manual",
            json={
                "title": "Senior Manager",
                "status": "applied",
            },
        )
        assert response.status_code == 422
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user_id] = original_override
        else:
            app.dependency_overrides.pop(get_current_user_id, None)


def test_manual_application_create_with_default_status(monkeypatch):
    """Verify status defaults to 'applied' when not provided."""
    from src.api.app import app
    from src.api.deps import get_current_user_id
    import src.api.routers.applications as applications_router

    calls = {}

    def mock_get_user_id():
        return "test@example.com"

    def mock_create_manual(*, title, company, location, url, status, user_id):
        calls["status"] = status
        return True

    original_override = app.dependency_overrides.get(get_current_user_id, None)
    app.dependency_overrides[get_current_user_id] = mock_get_user_id
    monkeypatch.setattr(applications_router, "create_manual", mock_create_manual)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/applications/manual",
            json={
                "title": "Senior Manager Audit Programs",
                "company": "TALENTMATE",
                "location": "Abu Dhabi",
            },
        )
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user_id] = original_override
        else:
            app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    assert calls["status"] == "applied"

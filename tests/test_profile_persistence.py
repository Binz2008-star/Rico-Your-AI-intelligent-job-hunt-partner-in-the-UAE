"""Test profile field persistence end-to-end through DB and API."""
import pytest
from fastapi.testclient import TestClient
from src.repositories.profile_repo import upsert_profile, get_profile
from src.rico_agent import RicoProfile
from src.api.app import app


def test_profile_name_persists_through_db():
    """Test that name field persists after upsert and retrieval."""
    user_id = "test_persistence@example.com"

    # Create initial profile
    initial_profile = upsert_profile(user_id, {
        "name": "Test User",
        "email": user_id,
        "phone": "+971501234567"
    })

    assert initial_profile.name == "Test User"

    # Retrieve and verify
    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.name == "Test User", f"Expected 'Test User', got {retrieved.name}"


def test_profile_current_role_persists_through_db():
    """Test that current_role field persists after upsert and retrieval."""
    user_id = "test_role_persistence@example.com"

    upsert_profile(user_id, {
        "email": user_id,
        "current_role": "Sustainability & Environmental Operations Lead"
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.current_role == "Sustainability & Environmental Operations Lead", \
        f"Expected 'Sustainability & Environmental Operations Lead', got {retrieved.current_role}"


def test_profile_current_company_persists_through_db():
    """Test that current_company field persists after upsert and retrieval."""
    user_id = "test_company_persistence@example.com"

    upsert_profile(user_id, {
        "email": user_id,
        "current_company": "Eco Technology Environmental Protection Services LLC"
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.current_company == "Eco Technology Environmental Protection Services LLC", \
        f"Expected 'Eco Technology Environmental Protection Services LLC', got {retrieved.current_company}"


def test_profile_linkedin_url_persists_through_db():
    """Test that linkedin_url field persists after upsert and retrieval."""
    user_id = "test_linkedin_persistence@example.com"

    upsert_profile(user_id, {
        "email": user_id,
        "linkedin_url": "https://linkedin.com/in/robin-edwan-environmental"
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.linkedin_url == "https://linkedin.com/in/robin-edwan-environmental", \
        f"Expected 'https://linkedin.com/in/robin-edwan-environmental', got {retrieved.linkedin_url}"


def test_profile_preferred_cities_persist_through_db():
    """Test that preferred_cities field persists after upsert and retrieval."""
    user_id = "test_cities_persistence@example.com"

    cities = ["Ajman", "Dubai", "Sharjah"]
    upsert_profile(user_id, {
        "email": user_id,
        "preferred_cities": cities
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.preferred_cities == cities, \
        f"Expected {cities}, got {retrieved.preferred_cities}"


def test_profile_salary_fields_persist_through_db():
    """Test that salary fields persist after upsert and retrieval."""
    user_id = "test_salary_persistence@example.com"

    upsert_profile(user_id, {
        "email": user_id,
        "salary_expectation_aed": 15000,
        "minimum_salary_aed": 10000
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.salary_expectation_aed == 15000, \
        f"Expected 15000, got {retrieved.salary_expectation_aed}"
    assert retrieved.minimum_salary_aed == 10000, \
        f"Expected 10000, got {retrieved.minimum_salary_aed}"


def test_profile_visa_status_persists_through_db():
    """Test that visa_status field persists after upsert and retrieval."""
    user_id = "test_visa_persistence@example.com"

    upsert_profile(user_id, {
        "email": user_id,
        "visa_status": "Employment Visa"
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.visa_status == "Employment Visa", \
        f"Expected 'Employment Visa', got {retrieved.visa_status}"


def test_profile_notice_period_persists_through_db():
    """Test that notice_period field persists after upsert and retrieval."""
    user_id = "test_notice_persistence@example.com"

    upsert_profile(user_id, {
        "email": user_id,
        "notice_period": "1 month"
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.notice_period == "1 month", \
        f"Expected '1 month', got {retrieved.notice_period}"


def test_profile_multiple_fields_persist_together():
    """Test that multiple fields persist together in a single upsert."""
    user_id = "test_multi_persistence@example.com"

    updates = {
        "email": user_id,
        "name": "Roben Edwan",
        "current_role": "Sustainability & Environmental Operations Lead",
        "current_company": "Eco Technology Environmental Protection Services LLC",
        "linkedin_url": "https://linkedin.com/in/robin-edwan-environmental",
        "phone": "+971 52 223 3989",
        "visa_status": "Employment Visa",
        "notice_period": "1 month",
        "preferred_cities": ["Ajman", "Dubai"],
        "salary_expectation_aed": 15000,
        "minimum_salary_aed": 10000,
        "years_experience": 10.0,
        "skills": ["hse", "iso 14001", "environmental management"],
        "target_roles": ["HSE Manager", "Environmental Manager"]
    }

    upsert_profile(user_id, updates)

    retrieved = get_profile(user_id)
    assert retrieved is not None

    # Verify all fields
    assert retrieved.name == "Roben Edwan"
    assert retrieved.current_role == "Sustainability & Environmental Operations Lead"
    assert retrieved.current_company == "Eco Technology Environmental Protection Services LLC"
    assert retrieved.linkedin_url == "https://linkedin.com/in/robin-edwan-environmental"
    assert retrieved.phone == "+971 52 223 3989"
    assert retrieved.visa_status == "Employment Visa"
    assert retrieved.notice_period == "1 month"
    assert retrieved.preferred_cities == ["Ajman", "Dubai"]
    assert retrieved.salary_expectation_aed == 15000
    assert retrieved.minimum_salary_aed == 10000
    assert retrieved.years_experience == 10.0
    assert retrieved.skills == ["hse", "iso 14001", "environmental management"]
    assert retrieved.target_roles == ["HSE Manager", "Environmental Manager"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================================
# API Route Tests - PATCH /api/v1/rico/profile → GET /api/v1/rico/profile
# ============================================================================

def test_api_patch_name_persists(monkeypatch):
    """Test PATCH name field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_name_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    # Only mock authentication, use real upsert_profile and get_profile
    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    # PATCH name
    response = client.patch("/api/v1/rico/profile", json={"name": "Roben Edwan"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "name" in response.json()["updated_fields"]

    # GET profile
    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Roben Edwan"


def test_api_patch_current_role_persists(monkeypatch):
    """Test PATCH current_role field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_role_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"current_role": "Sustainability & Environmental Operations Lead"})
    assert response.status_code == 200
    assert "current_role" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["current_role"] == "Sustainability & Environmental Operations Lead"


def test_api_patch_current_company_persists(monkeypatch):
    """Test PATCH current_company field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_company_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"current_company": "Eco Technology Environmental Protection Services LLC"})
    assert response.status_code == 200
    assert "current_company" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["current_company"] == "Eco Technology Environmental Protection Services LLC"


def test_api_patch_linkedin_url_persists(monkeypatch):
    """Test PATCH linkedin_url field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_linkedin_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"linkedin_url": "https://linkedin.com/in/robin-edwan-environmental"})
    assert response.status_code == 200
    assert "linkedin_url" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["linkedin_url"] == "https://linkedin.com/in/robin-edwan-environmental"


def test_api_patch_preferred_cities_persists(monkeypatch):
    """Test PATCH preferred_cities field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_cities_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"preferred_cities": ["Ajman", "Dubai", "Sharjah"]})
    assert response.status_code == 200
    assert "preferred_cities" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["preferred_cities"] == ["Ajman", "Dubai", "Sharjah"]


def test_api_patch_salary_fields_persist(monkeypatch):
    """Test PATCH salary fields persist through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_salary_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"salary_expectation_aed": 15000, "minimum_salary_aed": 10000})
    assert response.status_code == 200
    assert "salary_expectation_aed" in response.json()["updated_fields"]
    assert "minimum_salary_aed" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["salary_expectation_aed"] == 15000
    assert data["minimum_salary_aed"] == 10000


def test_api_patch_visa_status_persists(monkeypatch):
    """Test PATCH visa_status field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_visa_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"visa_status": "Employment Visa"})
    assert response.status_code == 200
    assert "visa_status" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["visa_status"] == "Employment Visa"


def test_api_patch_notice_period_persists(monkeypatch):
    """Test PATCH notice_period field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_notice_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"notice_period": "1 month"})
    assert response.status_code == 200
    assert "notice_period" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["notice_period"] == "1 month"


def test_api_patch_skills_persist(monkeypatch):
    """Test PATCH skills field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_skills_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"skills": ["hse", "iso 14001", "environmental management"]})
    assert response.status_code == 200
    assert "skills" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["skills"] == ["hse", "iso 14001", "environmental management"]


def test_api_patch_target_roles_persist(monkeypatch):
    """Test PATCH target_roles field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_roles_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"target_roles": ["HSE Manager", "Environmental Manager"]})
    assert response.status_code == 200
    assert "target_roles" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["target_roles"] == ["HSE Manager", "Environmental Manager"]


def test_api_patch_industries_persist(monkeypatch):
    """Test PATCH industries field persists through API using real upsert_profile."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_industries_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    response = client.patch("/api/v1/rico/profile", json={"industries": ["Environmental Services", "Construction"]})
    assert response.status_code == 200
    assert "industries" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["industries"] == ["Environmental Services", "Construction"]


def test_api_patch_empty_cities_persist(monkeypatch):
    """Test PATCH empty preferred_cities array persists through API."""
    import src.api.routers.rico_chat as rico_chat_router

    user_id = "api_empty_cities_test@example.com"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    # First set some cities
    client.patch("/api/v1/rico/profile", json={"preferred_cities": ["Dubai"]})

    # Then clear them
    response = client.patch("/api/v1/rico/profile", json={"preferred_cities": []})
    assert response.status_code == 200
    assert "preferred_cities" in response.json()["updated_fields"]

    response = client.get("/api/v1/rico/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["preferred_cities"] == []


# ============================================================================
# Normalization Version Tests
# ============================================================================

def test_normalization_version_persists():
    """Test that normalization_version field persists through upsert and retrieval."""
    user_id = "normalization_version_test@example.com"

    upsert_profile(user_id, {
        "email": user_id,
        "normalization_version": 2
    })

    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.normalization_version == 2, \
        f"Expected normalization_version=2, got {retrieved.normalization_version}"


def test_profile_renormalization_with_versioning():
    """Test that profile re-normalizes when normalization_version changes."""
    from src.role_normalization import NORMALIZATION_VERSION

    user_id = "renormalization_test@example.com"

    # Create profile with old normalization (version 1) and specific-but-wrong roles
    upsert_profile(user_id, {
        "email": user_id,
        "target_roles": ["HSE Manager", "Environmental Manager"],
        "normalization_version": 1,
        "skills": ["hse", "iso 14001"]
    })

    # Get profile - should trigger re-normalization since version < NORMALIZATION_VERSION
    retrieved = get_profile(user_id)
    assert retrieved is not None
    assert retrieved.normalization_version == NORMALIZATION_VERSION, \
        f"Expected normalization_version={NORMALIZATION_VERSION}, got {retrieved.normalization_version}"
    # Roles should still be HSE/environmental (they were already correct)
    assert "HSE Manager" in retrieved.target_roles or "Environmental Manager" in retrieved.target_roles


<<<<<<< HEAD
# ============================================================================
# DB Roundtrip Tests - Diagnostic for production issue
# ============================================================================

=======
>>>>>>> e0f2620 (test(profile): add DB user upsert/read roundtrip test)
def test_db_user_upsert_read_roundtrip():
    """Test that db.upsert_user and db.get_user_bundle use the same identity key."""
    from src.rico_db import RicoDB

    db = RicoDB()
    test_email = "db_roundtrip_test@example.com"
    test_name = "Roben Edwan"

    # Upsert user with name
    user_row = db.upsert_user({
        "external_user_id": test_email,
        "name": test_name,
        "email": test_email
    })
    assert user_row["name"] == test_name, \
        f"Expected name={test_name} after upsert, got {user_row.get('name')}"

    # Read back using the same identity key
    bundle = db.get_user_bundle(test_email)
    assert bundle is not None, "get_user_bundle returned None"
    assert bundle["name"] == test_name, \
        f"Expected name={test_name} in bundle, got {bundle.get('name')}"

    # Cleanup
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_users WHERE external_user_id = %s", (test_email,))
        conn.commit()
<<<<<<< HEAD


def test_api_patch_to_db_to_get_roundtrip(monkeypatch):
    """Test full path: PATCH endpoint -> DB -> GET endpoint."""
    import src.api.routers.rico_chat as rico_chat_router
    from src.rico_db import RicoDB

    user_id = "api_db_roundtrip_test@example.com"
    test_name = "Roben Edwan"

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)
    db = RicoDB()

    # Cleanup before test
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_users WHERE external_user_id = %s", (user_id,))
        conn.commit()

    try:
        # PATCH endpoint
        response = client.patch("/api/v1/rico/profile", json={"name": test_name})
        assert response.status_code == 200
        assert "name" in response.json()["updated_fields"]

        # Direct DB read
        bundle = db.get_user_bundle(user_id)
        assert bundle is not None, "get_user_bundle returned None"
        assert bundle["name"] == test_name, \
            f"Expected name={test_name} in DB bundle, got {bundle.get('name')}"

        # GET endpoint
        response = client.get("/api/v1/rico/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_name, \
            f"Expected name={test_name} in GET response, got {data.get('name')}"
    finally:
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_users WHERE external_user_id = %s", (user_id,))
            conn.commit()

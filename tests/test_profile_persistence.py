"""Test profile field persistence end-to-end through DB and API."""
import os
import pytest
from fastapi.testclient import TestClient
from src.repositories.profile_repo import upsert_profile, get_profile
from src.rico_agent import RicoProfile
from src.api.app import app


def _db_available() -> bool:
    """True only when a live Postgres connection can be opened.

    The DB roundtrip tests issue raw SQL (INSERT/DELETE, ORDER BY semantics) and
    require a real database. They are skipped when no DATABASE_URL/psycopg2 is
    configured so the suite stays runnable in unit-only environments.
    """
    if not os.getenv("DATABASE_URL"):
        return False
    try:
        from src.rico_db import RicoDB
        with RicoDB().connect():
            return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(),
    reason="requires a live DATABASE_URL (DB integration test)",
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Give each test a fresh rate-limit budget.

    The profile PATCH/GET endpoints are rate-limited (20/min) keyed by client IP.
    All TestClient calls share the "testclient" IP, so without a reset the suite's
    cumulative profile calls can exhaust the budget and surface spurious 429s in
    whichever profile test happens to run last.
    """
    from src.api.rate_limit import limiter
    limiter.reset()
    yield


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

    # Establish a real (non-signup-shell) profile so GET returns career fields.
    client.patch("/api/v1/rico/profile", json={"current_role": "HSE Engineer"})

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

    # Establish a real (non-signup-shell) profile so GET returns career fields.
    client.patch("/api/v1/rico/profile", json={"current_role": "HSE Engineer"})

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

    # Establish a real (non-signup-shell) profile so GET returns career fields.
    client.patch("/api/v1/rico/profile", json={"current_role": "HSE Engineer"})

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

    # Establish a real (non-signup-shell) profile so GET returns career fields.
    client.patch("/api/v1/rico/profile", json={"current_role": "HSE Engineer"})

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

    # Establish a real (non-signup-shell) profile so GET returns career fields.
    client.patch("/api/v1/rico/profile", json={"current_role": "HSE Engineer"})

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

    # Establish a real (non-signup-shell) profile so GET returns career fields.
    client.patch("/api/v1/rico/profile", json={"current_role": "HSE Engineer"})

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

    # Establish a real (non-signup-shell) profile so GET returns career fields
    # even after preferred_cities is cleared.
    client.patch("/api/v1/rico/profile", json={"current_role": "HSE Engineer"})

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


def test_get_profile_handles_none_normalization_version(monkeypatch):
    """Profiles written before versioning may have null normalization_version."""
    import src.repositories.profile_repo as profile_repo
    from src.role_normalization import NORMALIZATION_VERSION

    user_id = "null_normalization_version@example.com"
    profile = RicoProfile(
        user_id=user_id,
        target_roles=["HSE Manager"],
        skills=["hse"],
        normalization_version=None,
    )

    class Memory:
        def load_profile(self, _user_id):
            return profile

    monkeypatch.setattr(profile_repo, "_db", lambda: None)
    monkeypatch.setattr(profile_repo, "_memory", lambda: Memory())
    monkeypatch.setattr(profile_repo, "upsert_profile", lambda _user_id, _updates: profile)

    retrieved = profile_repo.get_profile(user_id)

    assert retrieved is profile
    assert retrieved.normalization_version == NORMALIZATION_VERSION


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


# ============================================================================
# DB Roundtrip Tests - Diagnostic for production issue
# ============================================================================

@requires_db
def test_db_user_upsert_read_roundtrip():
    """Test that db.upsert_user and db.get_user_bundle use the same identity key and name persists."""
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
        f"Expected name={test_name} in bundle, got {bundle.get('name')}. This tests the fix for get_user_bundle SELECT."

    # Cleanup
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_users WHERE external_user_id = %s", (test_email,))
        conn.commit()


@requires_db
def test_get_user_bundle_with_duplicate_rows():
    """Test that get_user_bundle returns the latest row when multiple rows match the same email."""
    from src.rico_db import RicoDB
    import uuid

    db = RicoDB()
    test_email = "duplicate_test@example.com"
    test_name = "Roben Edwan"

    # Cleanup before test
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_users WHERE email = %s", (test_email,))
        conn.commit()

    try:
        # Create an old row with NULL name and old profile
        old_user_id = str(uuid.uuid4())
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_users (id, external_user_id, name, email, created_at, updated_at)
                    VALUES (%s, %s, NULL, %s, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
                    """,
                    (old_user_id, test_email, test_email)
                )
                cur.execute(
                    """
                    INSERT INTO rico_profiles (user_id, profile, created_at, updated_at)
                    VALUES (%s, %s, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
                    """,
                    (old_user_id, '{"target_roles": ["Engineer", "Manager"]}')
                )
            conn.commit()

        # Upsert to create/update the current row with name
        user_row = db.upsert_user({
            "external_user_id": test_email,
            "name": test_name,
            "email": test_email
        })
        assert user_row["name"] == test_name, \
            f"Expected name={test_name} after upsert, got {user_row.get('name')}"

        # get_user_bundle must return the latest row (with name, not NULL)
        bundle = db.get_user_bundle(test_email)
        assert bundle is not None, "get_user_bundle returned None"
        assert bundle["name"] == test_name, \
            f"Expected name={test_name} in bundle (latest row), got {bundle.get('name')}. This tests deterministic ORDER BY."
        # Verify profile is also from latest row
        profile_data = bundle.get("profile") or {}
        assert profile_data.get("target_roles") != ["Engineer", "Manager"], \
            "Expected latest profile data, not old profile"

    finally:
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_users WHERE email = %s", (test_email,))
            conn.commit()


@requires_db
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


@requires_db
def test_canonical_row_selection_with_duplicate_emails():
    """Regression test: PATCH and GET must choose same canonical row when duplicate email rows exist.

    Scenario:
    - Row A: canonical UUID external_user_id, has profile data
    - Row B: bad duplicate external_user_id=email, no profile data

    Verify:
    - upsert_profile writes to Row A (canonical)
    - get_profile reads from Row A (canonical)
    - PATCH/GET consistency through API

    Safety: Skips if DATABASE_URL appears to be production.
    """
    import os
    from src.rico_db import RicoDB
    import uuid

    # Safety guard: skip if DATABASE_URL appears to be production
    # Allow override with TEST_MODE=1 for local development testing
    db_url = os.getenv("DATABASE_URL", "")
    test_mode = os.getenv("TEST_MODE", "0")
    if test_mode != "1" and "neondb" in db_url and not ("test" in db_url.lower() or "localhost" in db_url or "127.0.0.1" in db_url):
        pytest.skip("Skipping canonical row test: DATABASE_URL appears to be production")

    db = RicoDB()
    test_email = "canonical_selection_test@example.com"
    canonical_uuid = str(uuid.uuid4())

    # Bootstrap schema if needed
    try:
        db.init()
    except Exception:
        pass  # Schema may already exist

    # Cleanup before test
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_users WHERE email = %s", (test_email,))
        conn.commit()

    try:
        # Step 1: Create canonical row (Row A) with UUID external_user_id and profile data
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_users (id, external_user_id, name, email, created_at, updated_at)
                    VALUES (%s, %s, 'Canonical User', %s, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days')
                    """,
                    (canonical_uuid, canonical_uuid, test_email)
                )
                cur.execute(
                    """
                    INSERT INTO rico_profiles (user_id, profile, created_at, updated_at)
                    VALUES (%s, %s, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days')
                    """,
                    (canonical_uuid, '{"target_roles": ["HSE Manager"], "preferred_cities": ["Dubai"]}')
                )
            conn.commit()

        # Step 2: Create bad duplicate row (Row B) with external_user_id=email, no profile
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_users (external_user_id, name, email, created_at, updated_at)
                    VALUES (%s, NULL, %s, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
                    """,
                    (test_email, test_email)
                )
            conn.commit()

        # Step 3: Verify get_user_bundle returns canonical row (Row A)
        bundle = db.get_user_bundle(test_email)
        assert bundle is not None, "get_user_bundle returned None"
        assert bundle["external_user_id"] == canonical_uuid, \
            f"Expected canonical UUID {canonical_uuid}, got {bundle.get('external_user_id')}"
        assert bundle["name"] == "Canonical User", \
            f"Expected name from canonical row, got {bundle.get('name')}"
        profile_data = bundle.get("profile") or {}
        assert profile_data.get("target_roles") == ["HSE Manager"], \
            f"Expected profile data from canonical row, got {profile_data}"

        # Step 4: Verify upsert_profile writes to canonical row (Row A)
        upsert_profile(test_email, {
            "preferred_cities": ["Dubai", "Abu Dhabi"],
            "notice_period": "1 month"
        })

        # Step 5: Verify the canonical row was updated (not the bad duplicate)
        bundle_after = db.get_user_bundle(canonical_uuid)
        assert bundle_after is not None, "get_user_bundle for canonical UUID returned None"
        profile_after = bundle_after.get("profile") or {}
        assert profile_after.get("preferred_cities") == ["Dubai", "Abu Dhabi"], \
            f"Expected updated cities in canonical row, got {profile_after.get('preferred_cities')}"
        assert profile_after.get("notice_period") == "1 month", \
            f"Expected notice_period in canonical row, got {profile_after.get('notice_period')}"

        # Step 6: Verify get_profile reads from canonical row
        profile = get_profile(test_email)
        assert profile is not None, "get_profile returned None"
        assert profile.preferred_cities == ["Dubai", "Abu Dhabi"], \
            f"Expected updated cities from canonical row, got {profile.preferred_cities}"
        assert profile.notice_period == "1 month", \
            f"Expected notice_period from canonical row, got {profile.notice_period}"

    finally:
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_users WHERE email = %s", (test_email,))
            conn.commit()


@requires_db
def test_email_external_user_id_fallback_row_still_roundtrips():
    """Regression test: email users with only external_user_id=email still PATCH/GET correctly."""
    import os
    from src.rico_db import RicoDB

    db_url = os.getenv("DATABASE_URL", "")
    test_mode = os.getenv("TEST_MODE", "0")
    if test_mode != "1" and "neondb" in db_url and not ("test" in db_url.lower() or "localhost" in db_url or "127.0.0.1" in db_url):
        pytest.skip("Skipping email fallback row test: DATABASE_URL appears to be production")

    db = RicoDB()
    test_email = "email_external_fallback_test@example.com"

    try:
        db.init()
    except Exception:
        pass

    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM rico_users WHERE email = %s OR external_user_id = %s",
                (test_email, test_email),
            )
        conn.commit()

    try:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_users (external_user_id, name, email, created_at, updated_at)
                    VALUES (%s, 'Fallback Email User', NULL, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
                    """,
                    (test_email,),
                )
            conn.commit()

        bundle = db.get_user_bundle(test_email)
        assert bundle is not None, "external_user_id=email fallback row should still resolve"
        assert bundle["external_user_id"] == test_email
        assert bundle["email"] is None

        upsert_profile(test_email, {
            "preferred_cities": ["Dubai", "Sharjah"],
            "notice_period": "Immediate",
        })

        profile = get_profile(test_email)
        assert profile is not None
        assert profile.preferred_cities == ["Dubai", "Sharjah"]
        assert profile.notice_period == "Immediate"

        bundle_after = db.get_user_bundle(test_email)
        assert bundle_after is not None
        assert bundle_after["email"] == test_email
    finally:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM rico_users WHERE email = %s OR external_user_id = %s",
                    (test_email, test_email),
                )
            conn.commit()


@requires_db
def test_non_email_identifiers_still_work():
    """Regression test: non-email identifiers (Telegram/JotForm/external_user_id) path is not broken by canonical email fix.

    Verify:
    - get_user_bundle by external_user_id (UUID) works
    - get_user_bundle by telegram_username works
    - upsert_profile by non-email external_user_id works
    """
    import os
    from src.rico_db import RicoDB
    import uuid

    # Safety guard: skip if DATABASE_URL appears to be production
    # Allow override with TEST_MODE=1 for local development testing
    db_url = os.getenv("DATABASE_URL", "")
    test_mode = os.getenv("TEST_MODE", "0")
    if test_mode != "1" and "neondb" in db_url and not ("test" in db_url.lower() or "localhost" in db_url or "127.0.0.1" in db_url):
        pytest.skip("Skipping non-email identifier test: DATABASE_URL appears to be production")

    db = RicoDB()
    test_uuid = str(uuid.uuid4())
    test_telegram = "test_telegram_user"

    # Bootstrap schema if needed
    try:
        db.init()
    except Exception:
        pass  # Schema may already exist

    # Ensure telegram_notifications_enabled column exists (for older DB schemas)
    try:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE rico_users
                    ADD COLUMN IF NOT EXISTS telegram_notifications_enabled BOOLEAN DEFAULT TRUE
                """)
                conn.commit()
    except Exception:
        pass  # Column may already exist

    # Cleanup before test
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_users WHERE external_user_id = %s", (test_uuid,))
            cur.execute("DELETE FROM rico_users WHERE telegram_username = %s", (test_telegram,))
        conn.commit()

    try:
        # Test 1: upsert by external_user_id (UUID)
        user_row = db.upsert_user({
            "external_user_id": test_uuid,
            "name": "UUID User",
            "email": "uuid@example.com"
        })
        assert user_row["external_user_id"] == test_uuid
        assert user_row["name"] == "UUID User"

        # Test 2: get_user_bundle by external_user_id
        bundle = db.get_user_bundle(test_uuid)
        assert bundle is not None
        assert bundle["external_user_id"] == test_uuid
        assert bundle["name"] == "UUID User"

        # Test 3: upsert by telegram_username
        telegram_row = db.upsert_user({
            "external_user_id": test_telegram,
            "telegram_username": test_telegram,
            "name": "Telegram User"
        })
        assert telegram_row["telegram_username"] == test_telegram
        assert telegram_row["name"] == "Telegram User"

        # Test 4: get_user_bundle by telegram_username
        telegram_bundle = db.get_user_bundle(test_telegram)
        assert telegram_bundle is not None
        assert telegram_bundle["telegram_username"] == test_telegram
        assert telegram_bundle["name"] == "Telegram User"

        # Test 5: upsert_profile by non-email external_user_id
        upsert_profile(test_uuid, {
            "preferred_cities": ["Dubai"],
            "notice_period": "1 month"
        })

        # Test 6: get_profile by non-email external_user_id
        profile = get_profile(test_uuid)
        assert profile is not None
        assert profile.preferred_cities == ["Dubai"]
        assert profile.notice_period == "1 month"

    finally:
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_users WHERE external_user_id = %s", (test_uuid,))
                cur.execute("DELETE FROM rico_users WHERE telegram_username = %s", (test_telegram,))
            conn.commit()


@requires_db
def test_api_patch_get_consistency_with_duplicate_rows(monkeypatch):
    """Regression test: PATCH /api/v1/rico/profile then GET /api/v1/rico/profile must return saved data when duplicate rows exist.

    This tests the full API path with the canonical selection fix.

    Safety: Skips if DATABASE_URL appears to be production.
    """
    import os
    import src.api.routers.rico_chat as rico_chat_router
    from src.rico_db import RicoDB
    import uuid

    # Safety guard: skip if DATABASE_URL appears to be production
    # Allow override with TEST_MODE=1 for local development testing
    db_url = os.getenv("DATABASE_URL", "")
    test_mode = os.getenv("TEST_MODE", "0")
    if test_mode != "1" and "neondb" in db_url and not ("test" in db_url.lower() or "localhost" in db_url or "127.0.0.1" in db_url):
        pytest.skip("Skipping API duplicate test: DATABASE_URL appears to be production")

    db = RicoDB()
    test_email = "api_duplicate_test@example.com"
    canonical_uuid = str(uuid.uuid4())

    def mock_get_user(request):
        user = {"email": test_email, "role": "user"}
        request.state.current_user = user
        request.state.user_id = test_email
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)

    client = TestClient(app)

    # Cleanup before test
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_users WHERE email = %s", (test_email,))
        conn.commit()

    try:
        # Create canonical row with profile data
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_users (id, external_user_id, name, email, created_at, updated_at)
                    VALUES (%s, %s, 'API Test User', %s, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days')
                    """,
                    (canonical_uuid, canonical_uuid, test_email)
                )
                cur.execute(
                    """
                    INSERT INTO rico_profiles (user_id, profile, created_at, updated_at)
                    VALUES (%s, %s, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days')
                    """,
                    (canonical_uuid, '{"target_roles": ["Engineer"]}')
                )
            conn.commit()

        # Create bad duplicate row
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_users (external_user_id, name, email, created_at, updated_at)
                    VALUES (%s, NULL, %s, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
                    """,
                    (test_email, test_email)
                )
            conn.commit()

        # PATCH preferred_cities and notice_period
        response = client.patch("/api/v1/rico/profile", json={
            "preferred_cities": ["Dubai", "Sharjah"],
            "notice_period": "2 months"
        })
        assert response.status_code == 200
        assert "preferred_cities" in response.json()["updated_fields"]
        assert "notice_period" in response.json()["updated_fields"]

        # GET profile and verify data persisted
        response = client.get("/api/v1/rico/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["preferred_cities"] == ["Dubai", "Sharjah"], \
            f"Expected saved cities, got {data.get('preferred_cities')}"
        assert data["notice_period"] == "2 months", \
            f"Expected saved notice_period, got {data.get('notice_period')}"

    finally:
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_users WHERE email = %s", (test_email,))
            conn.commit()


def test_upsert_profile_uses_bundle_resolver_for_email_users(monkeypatch):
    """Unit regression: email PATCH writes to the same bundle row GET resolves."""
    import src.repositories.profile_repo as profile_repo

    captured = {}

    class FakeConn:
        def commit(self):
            captured["committed"] = True

        def rollback(self):
            captured["rolled_back"] = True

        def close(self):
            captured["closed"] = True

    class FakeDB:
        available = True

        def connect(self):
            return FakeConn()

        def get_user_bundle(self, user_id, conn=None):
            captured["bundle_user_id"] = user_id
            captured["bundle_conn"] = conn
            return {
                "id": "canonical-db-user-id",
                "external_user_id": "6d1df84a-e69a-46d1-9f1e-48c44577e380",
                "email": user_id,
                "profile": {"preferred_cities": ["Old City"]},
                "settings": {},
            }

        def upsert_profile(self, user_id, profile_data, conn=None):
            captured["profile_user_id"] = user_id
            captured["profile_data"] = profile_data
            captured["profile_conn"] = conn
            return {"user_id": user_id, "profile": profile_data}

    class FakeMemory:
        def upsert_profile_from_dict(self, user_id, updates):
            return RicoProfile(user_id=user_id, email=user_id, **updates)

    fake_db = FakeDB()
    monkeypatch.setattr(profile_repo, "RicoDB", lambda: fake_db)
    monkeypatch.setattr(profile_repo, "_memory", lambda: FakeMemory())

    profile_repo.upsert_profile(
        "person@example.com",
        {"preferred_cities": ["Dubai"], "notice_period": "Immediate"},
    )

    assert captured["bundle_user_id"] == "person@example.com"
    assert captured["profile_user_id"] == "canonical-db-user-id"
    assert captured["profile_data"] == {
        "preferred_cities": ["Dubai"],
        "notice_period": "Immediate",
    }
    assert captured["committed"] is True
    assert captured["closed"] is True


def test_upsert_profile_creates_email_user_with_email_column(monkeypatch):
    """Unit regression: new web email users are readable by GET after fallback creation."""
    import src.repositories.profile_repo as profile_repo

    captured = {}

    class FakeConn:
        def commit(self):
            captured["committed"] = True

        def rollback(self):
            captured["rolled_back"] = True

        def close(self):
            captured["closed"] = True

    class FakeDB:
        available = True

        def connect(self):
            return FakeConn()

        def get_user_bundle(self, user_id, conn=None):
            captured["bundle_user_id"] = user_id
            return None

        def upsert_user(self, payload, conn=None):
            captured["user_payload"] = payload
            return {"id": "new-db-user-id"}

        def upsert_profile(self, user_id, profile_data, conn=None):
            captured["profile_user_id"] = user_id
            captured["profile_data"] = profile_data
            return {"user_id": user_id, "profile": profile_data}

    class FakeMemory:
        def upsert_profile_from_dict(self, user_id, updates):
            return RicoProfile(user_id=user_id, email=user_id, **updates)

    fake_db = FakeDB()
    monkeypatch.setattr(profile_repo, "RicoDB", lambda: fake_db)
    monkeypatch.setattr(profile_repo, "_memory", lambda: FakeMemory())

    profile_repo.upsert_profile(
        "new-person@example.com",
        {"preferred_cities": ["Abu Dhabi"], "notice_period": "2 weeks"},
    )

    assert captured["user_payload"]["external_user_id"] == "new-person@example.com"
    assert captured["user_payload"]["email"] == "new-person@example.com"
    assert captured["profile_user_id"] == "new-db-user-id"
    assert captured["profile_data"] == {
        "preferred_cities": ["Abu Dhabi"],
        "notice_period": "2 weeks",
    }
    assert captured["committed"] is True
    assert captured["closed"] is True


def test_get_user_bundle_email_path_keeps_external_user_id_fallback():
    """Unit regression: email lookup still sees external_user_id=email rows."""
    from src.rico_db import RicoDB

    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params

        def fetchone(self):
            return {
                "id": "row-id",
                "external_user_id": "person@example.com",
                "email": None,
                "profile": {},
                "settings": {},
            }

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    db = RicoDB("postgresql://unused")
    bundle = db.get_user_bundle("person@example.com", conn=FakeConn())

    assert bundle is not None
    assert bundle["external_user_id"] == "person@example.com"
    assert "LOWER(u.external_user_id) = LOWER(%s)" in captured["sql"]
    assert captured["params"] == (
        "person@example.com",
        "person@example.com",
        "person@example.com",
    )

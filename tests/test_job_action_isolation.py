"""Tests for API job action isolation - ensure server-side job validation."""
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_current_user


@pytest.fixture
def client_with_auth():
    """Create a test client with authentication override."""
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user", "email": "test@example.com"}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestServerSideJobValidation:
    """Test that job actions use server-side job validation, not client-supplied objects."""

    @pytest.fixture
    def mock_jobs_repo(self, monkeypatch):
        """Mock jobs_repo.get_job to return test job."""
        from src.services.jobs_service import get_job

        def mock_get_job(job_id: str):
            if job_id == "123":
                return {
                    "id": "123",
                    "title": "Test Job",
                    "company": "Test Co",
                    "link": "https://example.com/job",
                }
            return None

        monkeypatch.setattr("src.services.jobs_service.get_job", mock_get_job)

    def test_skip_job_returns_404_when_job_not_found(self, client_with_auth):
        """skip endpoint should return 404 when job_id does not exist."""
        response = client_with_auth.post(
            "/api/v1/jobs/999/skip",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_save_job_returns_404_when_job_not_found(self, client_with_auth):
        """save endpoint should return 404 when job_id does not exist."""
        response = client_with_auth.post(
            "/api/v1/jobs/999/save",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_block_job_returns_404_when_job_not_found(self, client_with_auth):
        """block endpoint should return 404 when job_id does not exist."""
        response = client_with_auth.post(
            "/api/v1/jobs/999/block",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestApplyEndpointJobValidation:
    """Test that apply endpoint validates client-supplied job against server-side job_id."""

    @pytest.fixture
    def mock_jobs_repo(self, monkeypatch):
        """Mock jobs_repo.get_job to return test job."""
        def mock_get_job(job_id: str):
            if job_id == "123":
                return {
                    "id": "123",
                    "title": "Test Job",
                    "company": "Test Co",
                    "link": "https://example.com/job",
                }
            return None

        monkeypatch.setattr("src.api.routers.jobs.get_job", mock_get_job)

    def test_apply_returns_404_when_job_not_found(self, client_with_auth):
        """apply endpoint should return 404 when job_id does not exist."""
        response = client_with_auth.post(
            "/api/v1/jobs/999/apply",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_apply_rejects_mismatched_job_id(self, client_with_auth, mock_jobs_repo):
        """apply endpoint should reject when client job_id doesn't match URL job_id."""
        response = client_with_auth.post(
            "/api/v1/jobs/123/apply",
            json={"job": {"id": "456", "title": "Different Job"}},  # Mismatch
        )

        assert response.status_code == 422
        assert "does not match job_id in URL" in response.json()["detail"]

    def test_get_job_finds_job_from_json_history(self, monkeypatch):
        """get_job should find jobs from job_history.json when DB is not available."""
        from src.services.jobs_service import get_job
        from src.job_history import load_job_history

        # Mock DB as unavailable
        monkeypatch.setattr("src.services.jobs_service.is_db_available", lambda: False)

        # Mock load_job_history to return a test job
        test_job = {
            "id": "abc123",
            "title": "Test Job from JSON",
            "company": "Test Company",
            "location": "Remote",
            "link": "https://example.com/job/123",
            "score": 85,
        }
        monkeypatch.setattr("src.job_history.load_job_history", lambda: [test_job])

        # get_job should find the job from JSON history
        job = get_job("abc123")
        assert job is not None
        assert job["title"] == "Test Job from JSON"
        assert job["id"] == "abc123"


class TestJsonBackedJobActions:
    """Regression tests for JSON-backed job action lookup after PR #131."""

    @pytest.fixture
    def mock_json_history(self, monkeypatch):
        """Mock job_history.json to return test jobs."""
        from src.job_history import load_job_history

        listed_job = {
            "id": "json-123",
            "title": "JSON Job",
            "company": "JSON Co",
            "link": "https://example.com/json-123",
        }

        monkeypatch.setattr("src.job_history.load_job_history", lambda: [listed_job])
        # Mock DB as unavailable to force JSON fallback
        monkeypatch.setattr("src.services.jobs_service.is_db_available", lambda: False)
        # Mock get_applied_jobs to return empty
        monkeypatch.setattr("src.applications.get_applied_jobs", lambda: [])

    def test_skip_json_backed_listed_job_succeeds(self, client_with_auth, mock_json_history, monkeypatch):
        """skip endpoint should succeed for jobs listed in job_history.json."""
        from src.services.jobs_service import skip_job
        from src.applications import mark_applied

        # Mock mark_applied to return True
        monkeypatch.setattr("src.applications.mark_applied", lambda *args, **kwargs: True)
        # Mock is_applied to return False
        monkeypatch.setattr("src.applications.is_applied", lambda *args, **kwargs: False)

        response = client_with_auth.post("/api/v1/jobs/json-123/skip")
        assert response.status_code == 200

    def test_save_json_backed_listed_job_succeeds(self, client_with_auth, mock_json_history, monkeypatch):
        """save endpoint should succeed for jobs listed in job_history.json."""
        from src.services.jobs_service import save_job
        from src.applications import mark_applied

        # Mock mark_applied to return True
        monkeypatch.setattr("src.applications.mark_applied", lambda *args, **kwargs: True)
        # Mock is_applied to return False
        monkeypatch.setattr("src.applications.is_applied", lambda *args, **kwargs: False)

        response = client_with_auth.post("/api/v1/jobs/json-123/save")
        assert response.status_code == 200

    def test_block_json_backed_listed_job_succeeds(self, client_with_auth, mock_json_history, monkeypatch):
        """block endpoint should succeed for jobs listed in job_history.json."""
        from src.services.jobs_service import block_company
        from src.applications import mark_applied

        # Mock mark_applied to return True
        monkeypatch.setattr("src.applications.mark_applied", lambda *args, **kwargs: True)
        # Mock is_applied to return False
        monkeypatch.setattr("src.applications.is_applied", lambda *args, **kwargs: False)

        response = client_with_auth.post("/api/v1/jobs/json-123/block")
        assert response.status_code == 200

    def test_apply_json_backed_listed_job_succeeds(self, client_with_auth, mock_json_history, monkeypatch):
        """apply endpoint should succeed for jobs listed in job_history.json."""
        from src.applications import mark_applied

        # Mock mark_applied to return True
        monkeypatch.setattr("src.applications.mark_applied", lambda *args, **kwargs: True)
        # Mock is_applied to return False
        monkeypatch.setattr("src.applications.is_applied", lambda *args, **kwargs: False)

        response = client_with_auth.post(
            "/api/v1/jobs/json-123/apply",
            json={"job": {"id": "json-123", "title": "JSON Job"}}
        )
        assert response.status_code == 200

    def test_unknown_json_backed_job_still_returns_404(self, client_with_auth, mock_json_history, monkeypatch):
        """unknown job_id should still return 404 even with JSON fallback."""
        response = client_with_auth.post("/api/v1/jobs/unknown-999/skip")
        assert response.status_code == 404

    def test_client_body_mismatch_still_returns_422_for_apply(self, client_with_auth, mock_json_history, monkeypatch):
        """apply endpoint should still reject mismatched client job_id with 422."""
        from src.applications import mark_applied

        # Mock mark_applied to return True
        monkeypatch.setattr("src.applications.mark_applied", lambda *args, **kwargs: True)
        # Mock is_applied to return False
        monkeypatch.setattr("src.applications.is_applied", lambda *args, **kwargs: False)

        response = client_with_auth.post(
            "/api/v1/jobs/json-123/apply",
            json={"job": {"id": "different-456", "title": "Different Job"}}
        )
        assert response.status_code == 422

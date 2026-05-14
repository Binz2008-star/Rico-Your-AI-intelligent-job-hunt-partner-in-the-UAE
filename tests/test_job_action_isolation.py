"""Tests for API job action isolation - ensure server-side job validation."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

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

    @patch("src.api.routers.jobs.get_job")
    @patch("src.services.jobs_service.skip_job")
    def test_skip_job_uses_server_side_job_not_client_supplied(
        self, mock_skip_job, mock_get_job, client_with_auth
    ):
        """skip endpoint should fetch job server-side using job_id from URL, not trust client body."""
        mock_get_job.return_value = {
            "id": "123",
            "title": "Test Job",
            "company": "Test Co",
            "link": "https://example.com/job",
        }
        mock_skip_job.return_value = True

        response = client_with_auth.post(
            "/api/v1/jobs/123/skip",
            json={"job": {"id": "456", "title": "Malicious Job"}},  # Client tries to pass different job
        )

        # Should use server-side job (id=123), not client-supplied (id=456)
        mock_get_job.assert_called_once_with("123")
        mock_skip_job.assert_called_once()
        # Verify the job passed to skip_job is the server-side one
        call_args = mock_skip_job.call_args
        assert call_args[0][0]["id"] == "123"
        assert response.status_code == 200
        assert response.json()["status"] == "skipped"

    @patch("src.api.routers.jobs.get_job")
    @patch("src.services.jobs_service.save_job")
    def test_save_job_uses_server_side_job_not_client_supplied(
        self, mock_save_job, mock_get_job, client_with_auth
    ):
        """save endpoint should fetch job server-side using job_id from URL, not trust client body."""
        mock_get_job.return_value = {
            "id": "123",
            "title": "Test Job",
            "company": "Test Co",
            "link": "https://example.com/job",
        }
        mock_save_job.return_value = True

        response = client_with_auth.post(
            "/api/v1/jobs/123/save",
            json={"job": {"id": "456", "title": "Malicious Job"}},  # Client tries to pass different job
        )

        # Should use server-side job (id=123), not client-supplied (id=456)
        mock_get_job.assert_called_once_with("123")
        mock_save_job.assert_called_once()
        # Verify the job passed to save_job is the server-side one
        call_args = mock_save_job.call_args
        assert call_args[0][0]["id"] == "123"
        assert response.status_code == 200
        assert response.json()["status"] == "saved"

    @patch("src.api.routers.jobs.get_job")
    @patch("src.services.jobs_service.block_company")
    def test_block_job_uses_server_side_job_not_client_supplied(
        self, mock_block_company, mock_get_job, client_with_auth
    ):
        """block endpoint should fetch job server-side using job_id from URL, not trust client body."""
        mock_get_job.return_value = {
            "id": "123",
            "title": "Test Job",
            "company": "Test Co",
            "link": "https://example.com/job",
        }
        mock_block_company.return_value = "Test Co"

        response = client_with_auth.post(
            "/api/v1/jobs/123/block",
            json={"job": {"id": "456", "title": "Malicious Job"}},  # Client tries to pass different job
        )

        # Should use server-side job (id=123), not client-supplied (id=456)
        mock_get_job.assert_called_once_with("123")
        mock_block_company.assert_called_once()
        # Verify the job passed to block_company is the server-side one
        call_args = mock_block_company.call_args
        assert call_args[0][0]["id"] == "123"
        assert response.status_code == 200
        assert response.json()["status"] == "blocked"

    @patch("src.api.routers.jobs.get_job")
    def test_skip_job_returns_404_when_job_not_found(self, mock_get_job, client_with_auth):
        """skip endpoint should return 404 when job_id does not exist."""
        mock_get_job.return_value = None

        response = client_with_auth.post(
            "/api/v1/jobs/999/skip",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("src.api.routers.jobs.get_job")
    def test_save_job_returns_404_when_job_not_found(self, mock_get_job, client_with_auth):
        """save endpoint should return 404 when job_id does not exist."""
        mock_get_job.return_value = None

        response = client_with_auth.post(
            "/api/v1/jobs/999/save",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("src.api.routers.jobs.get_job")
    def test_block_job_returns_404_when_job_not_found(self, mock_get_job, client_with_auth):
        """block endpoint should return 404 when job_id does not exist."""
        mock_get_job.return_value = None

        response = client_with_auth.post(
            "/api/v1/jobs/999/block",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestApplyEndpointJobValidation:
    """Test that apply endpoint validates client-supplied job against server-side job_id."""

    @patch("src.api.routers.jobs.get_job")
    @patch("src.services.apply_service.apply_to_job")
    def test_apply_uses_server_side_job_when_client_not_supplied(
        self, mock_apply_to_job, mock_get_job, client_with_auth
    ):
        """apply endpoint should use server-side job when client doesn't supply job object."""
        server_job = {
            "id": "123",
            "title": "Test Job",
            "company": "Test Co",
            "link": "https://example.com/job",
        }
        mock_get_job.return_value = server_job
        mock_apply_to_job.return_value = {"status": "success", "message": "Applied", "job_id": "123"}

        response = client_with_auth.post(
            "/api/v1/jobs/123/apply",
        )

        mock_get_job.assert_called_once_with("123")
        mock_apply_to_job.assert_called_once_with(server_job)
        assert response.status_code == 200

    @patch("src.api.routers.jobs.get_job")
    @patch("src.services.apply_service.apply_to_job")
    def test_apply_validates_client_job_matches_server_job_id(
        self, mock_apply_to_job, mock_get_job, client_with_auth
    ):
        """apply endpoint should reject when client job_id doesn't match URL job_id."""
        server_job = {
            "id": "123",
            "title": "Test Job",
            "company": "Test Co",
            "link": "https://example.com/job",
        }
        mock_get_job.return_value = server_job

        response = client_with_auth.post(
            "/api/v1/jobs/123/apply",
            json={"job": {"id": "456", "title": "Different Job"}},  # Mismatch
        )

        assert response.status_code == 422
        assert "does not match job_id in URL" in response.json()["detail"]
        mock_apply_to_job.assert_not_called()

    @patch("src.api.routers.jobs.get_job")
    @patch("src.services.apply_service.apply_to_job")
    def test_apply_accepts_client_job_when_job_ids_match(
        self, mock_apply_to_job, mock_get_job, client_with_auth
    ):
        """apply endpoint should accept client job when job_id matches URL."""
        server_job = {
            "id": "123",
            "title": "Test Job",
            "company": "Test Co",
            "link": "https://example.com/job",
        }
        mock_get_job.return_value = server_job
        mock_apply_to_job.return_value = {"status": "success", "message": "Applied", "job_id": "123"}

        response = client_with_auth.post(
            "/api/v1/jobs/123/apply",
            json={"job": {"id": "123", "title": "Test Job"}},  # Matching job_id
        )

        assert response.status_code == 200
        mock_apply_to_job.assert_called_once()

    @patch("src.api.routers.jobs.get_job")
    def test_apply_returns_404_when_job_not_found(self, mock_get_job, client_with_auth):
        """apply endpoint should return 404 when job_id does not exist."""
        mock_get_job.return_value = None

        response = client_with_auth.post(
            "/api/v1/jobs/999/apply",
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestUserIdDerivation:
    """Test that user_id is derived from auth, not client-supplied data."""

    @patch("src.api.routers.jobs.get_job")
    @patch("src.services.jobs_service.skip_job")
    def test_user_id_derived_from_auth_token(
        self, mock_skip_job, mock_get_job, client_with_auth
    ):
        """user_id should be derived from auth token, not request body."""
        mock_get_job.return_value = {"id": "123", "title": "Test Job", "company": "Test Co"}
        mock_skip_job.return_value = True

        response = client_with_auth.post(
            "/api/v1/jobs/123/skip",
        )

        # Verify user_id is passed from auth to service layer
        call_args = mock_skip_job.call_args
        # skip_job is called with (job, user_id=user_id) - user_id is keyword arg
        assert call_args[1]["user_id"] == "test-user"
        assert response.status_code == 200

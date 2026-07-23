"""Tests for billing quota fail-open behavior (#1096).

Verifies that quota enforcement functions allow the request (fail open)
when the underlying count/plan resolution raises an exception, rather
than blocking the user behind a transient infrastructure issue.
"""
from unittest.mock import patch


class TestEnforceSavedJobAllowedFailOpen:
    """enforce_saved_job_allowed must not raise when count_saved_jobs errors."""

    @patch("src.services.subscription_gating.count_saved_jobs")
    @patch("src.services.subscription_gating._build_gate_check")
    def test_fail_open_on_count_error(self, mock_gate, mock_count):
        mock_count.side_effect = Exception("DB unavailable")
        mock_gate.side_effect = Exception("should not reach here")

        from src.services.subscription_gating import enforce_saved_job_allowed

        # Should not raise — fail open means allow the request
        enforce_saved_job_allowed("user@example.com")

    @patch("src.services.subscription_gating.count_saved_jobs")
    @patch("src.services.subscription_gating._build_gate_check")
    def test_fail_open_on_gate_check_error(self, mock_gate, mock_count):
        mock_count.return_value = 5
        mock_gate.side_effect = Exception("plan resolution failed")

        from src.services.subscription_gating import enforce_saved_job_allowed

        # Should not raise — fail open
        enforce_saved_job_allowed("user@example.com")


class TestEnforceDocumentQuotaFailOpen:
    """enforce_document_quota must not raise when check_document_quota errors."""

    @patch("src.services.subscription_gating.check_document_quota")
    def test_fail_open_on_check_error(self, mock_check):
        mock_check.side_effect = Exception("DB unavailable")

        from src.services.subscription_gating import enforce_document_quota

        # Should not raise — fail open
        enforce_document_quota("user@example.com", "cv")


class TestCountSavedJobsFailOpen:
    """count_saved_jobs must return 0 when both DB and fallback fail."""

    @patch("src.repositories.applications_repo.count_by_status")
    @patch("src.applications.get_applied_jobs")
    def test_returns_zero_on_all_failures(self, mock_get_jobs, mock_count):
        mock_count.side_effect = Exception("DB unavailable")
        mock_get_jobs.side_effect = Exception("file read error")

        from src.services.subscription_gating import count_saved_jobs

        result = count_saved_jobs("user@example.com")
        assert result == 0

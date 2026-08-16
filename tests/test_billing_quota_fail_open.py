"""Tests for billing quota failure behavior.

Contract (after the production-readiness audit):
  * AI-message usage is the real spend leak (LLM tokens) and FAILS CLOSED:
    usage that cannot be verified raises QuotaUnavailableError and the chat
    layer returns a transient-outage terminal instead of granting unlimited AI.
  * Saved-jobs / document / profile-optimization quotas FAIL OPEN: the writes
    they gate persist to the DB and therefore fail during an outage anyway, so
    allowing here cannot create surviving storage, and the legacy JSON mode
    (no billing relationship) keeps working.
"""
import pytest
from unittest.mock import patch

from src.services.subscription_gating import (
    QuotaUnavailableError,
    count_saved_jobs,
    count_user_documents,
    enforce_document_quota,
    enforce_saved_job_allowed,
)


class TestAiUsageFailClosed:
    """AI usage counting must fail closed: no count means no untracked usage."""

    @patch("src.services.subscription_gating._db_user_uuid")
    def test_raises_when_identity_lookup_fails(self, mock_uuid):
        from datetime import datetime, timezone

        mock_uuid.side_effect = QuotaUnavailableError("db unavailable")
        from src.services.subscription_gating import count_monthly_ai_messages

        with pytest.raises(QuotaUnavailableError):
            count_monthly_ai_messages("user@example.com", datetime.now(timezone.utc))

    @patch("src.services.subscription_gating._db_user_uuid", return_value="uuid-1")
    @patch("src.rico_db.RicoDB")
    def test_raises_when_db_count_fails(self, mock_db_cls, mock_uuid):
        from datetime import datetime, timezone

        mock_db = mock_db_cls.return_value
        mock_db.connect.side_effect = Exception("connection refused")
        from src.services.subscription_gating import count_monthly_ai_messages

        with pytest.raises(QuotaUnavailableError):
            count_monthly_ai_messages("user@example.com", datetime.now(timezone.utc))

    @patch("src.services.subscription_gating._db_user_uuid", return_value=None)
    @patch("src.rico_memory.RicoMemoryStore")
    def test_raises_when_memory_fallback_fails(self, mock_store_cls, mock_uuid):
        from datetime import datetime, timezone

        mock_store = mock_store_cls.return_value
        mock_store.load_chat_history.side_effect = Exception("store read failed")
        from src.services.subscription_gating import count_monthly_ai_messages

        with pytest.raises(QuotaUnavailableError):
            count_monthly_ai_messages("user@example.com", datetime.now(timezone.utc))


class TestCountSavedJobsFailOpen:
    """count_saved_jobs must return 0 when both DB and fallback fail (fail open)."""

    @patch("src.repositories.applications_repo.count_by_status")
    @patch("src.applications.get_applied_jobs")
    def test_returns_zero_on_all_failures(self, mock_get_jobs, mock_count):
        mock_count.side_effect = Exception("DB unavailable")
        mock_get_jobs.side_effect = Exception("file read error")

        result = count_saved_jobs("user@example.com")
        assert result == 0

    @patch("src.repositories.applications_repo.count_by_status")
    @patch("src.applications.get_applied_jobs")
    def test_returns_count_from_db_when_db_works(self, mock_get_jobs, mock_count):
        mock_count.return_value = 7

        assert count_saved_jobs("user@example.com") == 7
        mock_get_jobs.assert_not_called()


class TestEnforceSavedJobAllowedFailOpen:
    """enforce_saved_job_allowed must not raise when usage cannot be verified."""

    @patch("src.services.subscription_gating.count_saved_jobs")
    @patch("src.services.subscription_gating._build_gate_check")
    def test_fail_open_on_count_error(self, mock_gate, mock_count):
        mock_count.side_effect = Exception("DB unavailable")
        mock_gate.side_effect = Exception("should not reach here")

        enforce_saved_job_allowed("user@example.com")

    @patch("src.services.subscription_gating.count_saved_jobs")
    @patch("src.services.subscription_gating._build_gate_check")
    def test_fail_open_on_gate_check_error(self, mock_gate, mock_count):
        mock_count.return_value = 5
        mock_gate.side_effect = Exception("plan resolution failed")

        enforce_saved_job_allowed("user@example.com")


class TestCountUserDocumentsFailOpen:
    """count_user_documents must return 0 when the DB is unavailable."""

    @patch("src.rico_db.RicoDB", autospec=True)
    def test_returns_zero_when_db_unavailable(self, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.available = False

        assert count_user_documents("user@example.com", "cv") == 0


class TestEnforceDocumentQuotaFailOpen:
    """enforce_document_quota must not raise when the check errors."""

    @patch("src.services.subscription_gating.check_document_quota")
    def test_fail_open_on_check_error(self, mock_check):
        mock_check.side_effect = Exception("DB unavailable")

        enforce_document_quota("user@example.com", "cv")

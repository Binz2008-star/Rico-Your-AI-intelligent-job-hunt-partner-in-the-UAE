"""tests/unit/test_write_audit_log.py

Unit tests for write_audit_log() in src/repositories/audit_repo.py
Tests the compatibility wrapper for general audit logging (e.g., profile questions).
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime


class TestWriteAuditLog:
    """write_audit_log() must handle DB availability and column migration gracefully."""

    @patch("src.repositories.audit_repo.is_db_available", return_value=False)
    @patch("src.repositories.audit_repo.logger")
    def test_logs_to_info_when_db_unavailable(self, mock_logger, mock_db_available):
        """When DB is unavailable, write_audit_log should log to info and return."""
        from src.repositories.audit_repo import write_audit_log
        
        write_audit_log(
            user_id="test@example.com",
            event_type="profile_question",
            data={"field_name": "experience"}
        )
        
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        assert "audit_log" in args[0]
        assert "test@example.com" in args[1]
        assert "profile_question" in args[2]

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.get_db_connection", return_value=None)
    @patch("src.repositories.audit_repo.logger")
    def test_returns_early_when_connection_fails(self, mock_logger, mock_get_conn, mock_db_available):
        """When get_db_connection returns None, should return early."""
        from src.repositories.audit_repo import write_audit_log
        
        write_audit_log(
            user_id="test@example.com",
            event_type="profile_question",
            data={"field_name": "experience"}
        )
        
        # Should not call logger.info since connection failed
        mock_logger.info.assert_not_called()

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_checks_and_adds_columns_if_missing(self, mock_logger, mock_db_available):
        """write_audit_log should check for event_type and data columns and add them if missing."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []  # No columns exist
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"}
            )
        
        # Should have checked for columns
        assert mock_cursor.execute.call_count >= 3  # Check + 2 ALTER TABLE + INSERT

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_skips_column_add_if_already_exists(self, mock_logger, mock_db_available):
        """write_audit_log should not add columns if they already exist."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        # Both columns already exist
        mock_cursor.fetchall.return_value = [("event_type",), ("data",)]
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"}
            )
        
        # Should have checked for columns but not added them
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        alter_calls = [c for c in execute_calls if "ALTER TABLE" in c]
        assert len(alter_calls) == 0

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_inserts_audit_log_entry(self, mock_logger, mock_db_available):
        """write_audit_log should insert the audit log entry with correct values."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("event_type",), ("data",)]
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"}
            )
        
        # Should have called INSERT
        insert_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any("INSERT INTO action_audit_log" in c for c in insert_calls)

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_logs_success_on_successful_write(self, mock_logger, mock_db_available):
        """write_audit_log should log success on successful write."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("event_type",), ("data",)]
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"}
            )
        
        # Should log success
        success_calls = [call for call in mock_logger.info.call_args_list]
        assert any("audit_log_written" in str(call) for call in success_calls)

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_logs_exception_on_write_failure(self, mock_logger, mock_db_available):
        """write_audit_log should log exception on write failure."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("DB error")
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"}
            )
        
        # Should log exception
        mock_logger.exception.assert_called_once()
        args = mock_logger.exception.call_args[0]
        assert "audit_log_write_failed" in args[0]

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_closes_connection_on_completion(self, mock_logger, mock_db_available):
        """write_audit_log should close connection after use."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("event_type",), ("data",)]
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"}
            )
        
        mock_conn.close.assert_called_once()

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_closes_connection_on_exception(self, mock_logger, mock_db_available):
        """write_audit_log should close connection even on exception."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("DB error")
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"}
            )
        
        mock_conn.close.assert_called_once()

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_uses_provided_timestamp(self, mock_logger, mock_db_available):
        """write_audit_log should use provided timestamp if given."""
        from src.repositories.audit_repo import write_audit_log
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("event_type",), ("data",)]
        
        test_timestamp = datetime(2026, 5, 15, 12, 0, 0)
        
        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            write_audit_log(
                user_id="test@example.com",
                event_type="profile_question",
                data={"field_name": "experience"},
                timestamp=test_timestamp
            )
        
        # Should have used the provided timestamp
        insert_calls = [call for call in mock_cursor.execute.call_args_list]
        assert len(insert_calls) > 0
        # The last call should be the INSERT with the timestamp
        last_call_args = insert_calls[-1][0]
        assert "2026-05-15T12:00:00" in str(last_call_args)


class TestLogActionPersists:
    """log_action() -> _db_write() must COMMIT, otherwise psycopg2 rolls back
    the INSERT when the connection closes and the action audit trail (including
    permission-denied records) is silently lost."""

    def _log(self):
        return {
            "action_id": "abc123",
            "action_type": "apply",
            "user_email": "test@example.com",
            "job_id": "job-1",
            "job_title": "QHSE Manager",
            "job_company": "ACME",
            "timestamp": "2026-05-15T12:00:00",
            "result_status": "success",
            "result_message": "ok",
            "duration_ms": 12,
            "failure_reason": None,
        }

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_commits_after_insert(self, mock_logger, mock_db_available):
        """Without commit, the INSERT is discarded on close. Regression guard."""
        from src.repositories.audit_repo import log_action

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            log_action(self._log())

        # INSERT issued AND committed AND connection closed
        insert_calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("INSERT INTO action_audit_log" in c for c in insert_calls)
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_denied_record_is_committed(self, mock_logger, mock_db_available):
        """A permission-denied audit row must persist just like a success row."""
        from src.repositories.audit_repo import log_action

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        denied = self._log()
        denied["result_status"] = "denied"
        denied["failure_reason"] = "permission_denied"

        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            log_action(denied)

        mock_conn.commit.assert_called_once()

    @patch("src.repositories.audit_repo.is_db_available", return_value=True)
    @patch("src.repositories.audit_repo.logger")
    def test_no_commit_on_write_failure(self, mock_logger, mock_db_available):
        """On INSERT failure the exception is logged and no commit is attempted."""
        from src.repositories.audit_repo import log_action

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("DB error")

        with patch("src.repositories.audit_repo.get_db_connection", return_value=mock_conn):
            log_action(self._log())

        mock_conn.commit.assert_not_called()
        mock_logger.exception.assert_called_once()
        mock_conn.close.assert_called_once()

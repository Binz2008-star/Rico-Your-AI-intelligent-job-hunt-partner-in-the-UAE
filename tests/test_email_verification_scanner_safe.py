"""Tests for scanner-safe email verification flow (#1095).

Verifies that GET /verify-email validates without consuming the token,
and POST /verify-email performs the actual consumption.
"""
from unittest.mock import patch, MagicMock


class TestCheckVerificationToken:
    """check_verification_token must NOT mutate the DB — only SELECT."""

    @patch("src.db.get_db_connection")
    def test_check_does_not_consume(self, mock_conn_factory):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_conn_factory.return_value = conn
        cur.fetchone.return_value = ("user@example.com",)

        from src.repositories.email_verification_repo import check_verification_token

        result = check_verification_token("some-token")
        assert result == "user@example.com"

        # Verify only a SELECT was executed — no UPDATE
        executed_sql = cur.execute.call_args[0][0]
        assert "SELECT" in executed_sql.upper()
        assert "UPDATE" not in executed_sql.upper()

    @patch("src.db.get_db_connection")
    def test_check_returns_none_for_invalid(self, mock_conn_factory):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_conn_factory.return_value = conn
        cur.fetchone.return_value = None

        from src.repositories.email_verification_repo import check_verification_token

        result = check_verification_token("bad-token")
        assert result is None


class TestConsumeVerificationToken:
    """consume_verification_token must atomically UPDATE and mark used."""

    @patch("src.db.get_db_connection")
    def test_consume_marks_used(self, mock_conn_factory):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_conn_factory.return_value = conn
        cur.fetchone.return_value = ("user@example.com",)

        from src.repositories.email_verification_repo import consume_verification_token

        result = consume_verification_token("some-token")
        assert result == "user@example.com"

        # Verify an UPDATE was executed
        executed_sql = cur.execute.call_args[0][0]
        assert "UPDATE" in executed_sql.upper()
        assert "used_at" in executed_sql.lower()

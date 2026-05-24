"""
tests/test_password_reset_repo.py

Unit tests for password_reset_repo.consume_reset_token.

These tests exercise the repo directly (no FastAPI TestClient) and verify
that the atomic UPDATE…RETURNING pattern correctly handles valid, expired,
already-used, and concurrent token consumption without a TOCTOU window.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_GET_DB = "src.db.get_db_connection"


def _make_conn(fetchone_return):
    """Build a mock connection whose cursor().fetchone() returns `fetchone_return`."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_return

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestConsumeResetToken:
    def test_valid_token_returns_email(self):
        conn, cursor = _make_conn(("alice@rico.ai",))
        with patch(_GET_DB, return_value=conn):
            from src.repositories.password_reset_repo import consume_reset_token
            result = consume_reset_token("valid-token")
        assert result == "alice@rico.ai"
        conn.commit.assert_called_once()
        conn.close.assert_called_once()

    def test_expired_or_used_token_returns_none(self):
        """UPDATE WHERE expires_at > now AND used_at IS NULL matches nothing → fetchone None."""
        conn, cursor = _make_conn(None)
        with patch(_GET_DB, return_value=conn):
            from src.repositories.password_reset_repo import consume_reset_token
            result = consume_reset_token("stale-token")
        assert result is None
        conn.commit.assert_called_once()
        conn.close.assert_called_once()

    def test_unknown_token_returns_none(self):
        conn, cursor = _make_conn(None)
        with patch(_GET_DB, return_value=conn):
            from src.repositories.password_reset_repo import consume_reset_token
            result = consume_reset_token("no-such-token")
        assert result is None

    def test_db_unavailable_returns_none(self):
        with patch(_GET_DB, return_value=None):
            from src.repositories.password_reset_repo import consume_reset_token
            result = consume_reset_token("any-token")
        assert result is None

    def test_db_exception_returns_none_and_rollbacks(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(side_effect=Exception("boom"))
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        with patch(_GET_DB, return_value=conn):
            from src.repositories.password_reset_repo import consume_reset_token
            result = consume_reset_token("any-token")
        assert result is None
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_atomic_update_uses_single_execute(self):
        """Verify only one SQL statement is sent — no SELECT before the UPDATE."""
        conn, cursor = _make_conn(("bob@rico.ai",))
        with patch(_GET_DB, return_value=conn):
            from src.repositories.password_reset_repo import consume_reset_token
            consume_reset_token("tok")
        assert cursor.execute.call_count == 1
        sql = cursor.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()
        assert "RETURNING" in sql.upper()
        assert "SELECT" not in sql.upper()

    def test_concurrent_calls_only_one_wins(self):
        """
        Simulate two workers calling consume_reset_token at the same time.

        The DB correctly gives the row to the first caller and None to the second
        (the UPDATE WHERE used_at IS NULL only matches once).  Verify that the
        function propagates this: first call returns email, second returns None.
        """
        conn_a, _ = _make_conn(("alice@rico.ai",))
        conn_b, _ = _make_conn(None)

        connections = iter([conn_a, conn_b])
        with patch(_GET_DB, side_effect=connections):
            from src.repositories.password_reset_repo import consume_reset_token
            result_a = consume_reset_token("tok")
            result_b = consume_reset_token("tok")

        assert result_a == "alice@rico.ai"
        assert result_b is None

"""Regression: whatsapp_requests_repo closes its DB connection on every path.

src.db.get_db_connection() opens a fresh psycopg2 connection each call (there is
no pool), so a function that returns without closing strands a real Neon
connection. Before this fix none of the three repo functions closed their
connection — under a burst they exhausted Neon's connection ceiling and started
failing unrelated endpoints with "too many connections". These tests mock the
connection and assert close() is called on the success, existing-row, and
exception paths.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import src.repositories.whatsapp_requests_repo as repo


def _mock_conn_with_cursor(fetch_sequence):
    """Build a mock connection whose cursor.fetchone() yields from a sequence."""
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.side_effect = list(fetch_sequence)
    cur.rowcount = 1
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def test_get_or_create_closes_on_insert_success():
    row = ("RICO-AAAA", "u@x.com", "pro", 21.5, "USD", "pending", "en", None)
    conn, _ = _mock_conn_with_cursor([None, row])  # no existing, then insert RETURNING
    with patch.object(repo, "get_db_connection", return_value=conn):
        repo.get_or_create_pending_request(
            "u@x.com", plan="pro", price_usd=21.5, currency="USD"
        )
    conn.close.assert_called_once()


def test_get_or_create_closes_when_existing_row():
    row = ("RICO-BBBB", "u@x.com", "pro", 21.5, "USD", "pending", "en", None)
    conn, _ = _mock_conn_with_cursor([row])  # existing pending row short-circuits
    with patch.object(repo, "get_db_connection", return_value=conn):
        repo.get_or_create_pending_request(
            "u@x.com", plan="pro", price_usd=21.5, currency="USD"
        )
    conn.close.assert_called_once()


def test_get_or_create_closes_on_exception():
    conn = MagicMock()
    conn.cursor.side_effect = RuntimeError("db exploded")
    with patch.object(repo, "get_db_connection", return_value=conn):
        result = repo.get_or_create_pending_request(
            "u@x.com", plan="pro", price_usd=21.5, currency="USD"
        )
    assert result is None
    conn.close.assert_called_once()


def test_get_request_by_reference_closes():
    row = ("RICO-CCCC", "u@x.com", "pro", 21.5, "USD", "pending", "en", None)
    conn, _ = _mock_conn_with_cursor([row])
    with patch.object(repo, "get_db_connection", return_value=conn):
        repo.get_request_by_reference("RICO-CCCC")
    conn.close.assert_called_once()


def test_get_request_by_reference_closes_on_exception():
    conn = MagicMock()
    conn.cursor.side_effect = RuntimeError("db exploded")
    with patch.object(repo, "get_db_connection", return_value=conn):
        assert repo.get_request_by_reference("RICO-CCCC") is None
    conn.close.assert_called_once()


def test_mark_request_status_closes():
    conn, _ = _mock_conn_with_cursor([None])
    with patch.object(repo, "get_db_connection", return_value=conn):
        repo.mark_request_status("RICO-DDDD", "approved", approved_by="owner")
    conn.close.assert_called_once()


def test_mark_request_status_closes_on_exception():
    conn = MagicMock()
    conn.cursor.side_effect = RuntimeError("db exploded")
    with patch.object(repo, "get_db_connection", return_value=conn):
        assert repo.mark_request_status("RICO-DDDD", "approved") is False
    conn.close.assert_called_once()


def test_no_connection_is_safe():
    # When the DB is unavailable get_db_connection() returns None; the functions
    # must return their fail-closed sentinel without touching .close().
    with patch.object(repo, "get_db_connection", return_value=None):
        assert repo.get_or_create_pending_request(
            "u@x.com", plan="pro", price_usd=21.5, currency="USD"
        ) is None
        assert repo.get_request_by_reference("RICO-EEEE") is None
        assert repo.mark_request_status("RICO-EEEE", "approved") is False

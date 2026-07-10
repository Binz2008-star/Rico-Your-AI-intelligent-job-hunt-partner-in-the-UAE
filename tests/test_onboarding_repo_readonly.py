"""
tests/test_onboarding_repo_readonly.py

Contract tests for get_onboarding_state_readonly — the STRICT read-only reader
backing GET /api/v1/onboarding/status.

Guarantees under test:
  * never creates the table (_ensure_table is never called)
  * never issues DDL/DML and never commits
  * always closes the connection
  * table absent (legacy env) → None (does NOT create it)
  * table present + no row → None
  * row present → OnboardingState
  * DB unavailable → raises OnboardingStateUnavailable
  * SELECT/query failure → raises OnboardingStateUnavailable (never a silent None)

All DB calls are mocked — no real database.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.onboarding import ONBOARDING_COMPLETED, OnboardingState
from src.repositories.onboarding_repo import (
    OnboardingStateUnavailable,
    get_onboarding_state_readonly,
)

_TABLE_PRESENT = ("rico_onboarding_states",)
_TABLE_ABSENT = (None,)


def _conn_with_fetches(fetches):
    """Build a mock connection whose cursor.fetchone yields *fetches* in order."""
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = list(fetches)
    return conn, cur


def _run(conn):
    with patch("src.db.is_db_available", return_value=True), \
         patch("src.db.get_db_connection", return_value=conn):
        return get_onboarding_state_readonly("u@test.com")


class TestReadonlyReader:
    def test_never_calls_ensure_table(self):
        conn, _ = _conn_with_fetches([_TABLE_PRESENT, (ONBOARDING_COMPLETED, None, None)])
        with patch("src.repositories.onboarding_repo._ensure_table") as ensure:
            _run(conn)
        ensure.assert_not_called()

    def test_table_absent_returns_none_without_creating(self):
        conn, cur = _conn_with_fetches([_TABLE_ABSENT])
        result = _run(conn)
        assert result is None
        # Only the read-only existence probe ran — no CREATE/INSERT/etc.
        executed = " ".join(str(c.args[0]).upper() for c in cur.execute.call_args_list)
        assert "TO_REGCLASS" in executed
        assert "CREATE" not in executed
        conn.commit.assert_not_called()

    def test_table_present_no_row_returns_none(self):
        conn, _ = _conn_with_fetches([_TABLE_PRESENT, None])
        assert _run(conn) is None

    def test_row_present_returns_state(self):
        conn, _ = _conn_with_fetches([_TABLE_PRESENT, (ONBOARDING_COMPLETED, None, None)])
        result = _run(conn)
        assert isinstance(result, OnboardingState)
        assert result.status == ONBOARDING_COMPLETED
        assert result.is_complete() is True

    def test_db_unavailable_raises(self):
        with patch("src.db.is_db_available", return_value=False):
            with pytest.raises(OnboardingStateUnavailable):
                get_onboarding_state_readonly("u@test.com")

    def test_no_connection_raises(self):
        with patch("src.db.is_db_available", return_value=True), \
             patch("src.db.get_db_connection", return_value=None):
            with pytest.raises(OnboardingStateUnavailable):
                get_onboarding_state_readonly("u@test.com")

    def test_select_failure_raises_not_none(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.execute.side_effect = RuntimeError("boom: query blew up")
        with pytest.raises(OnboardingStateUnavailable):
            _run(conn)
        conn.close.assert_called_once()

    def test_never_commits_on_success(self):
        conn, _ = _conn_with_fetches([_TABLE_PRESENT, (ONBOARDING_COMPLETED, None, None)])
        _run(conn)
        conn.commit.assert_not_called()

    def test_connection_closed_on_success(self):
        conn, _ = _conn_with_fetches([_TABLE_PRESENT, (ONBOARDING_COMPLETED, None, None)])
        _run(conn)
        conn.close.assert_called_once()

    def test_connection_closed_on_no_row(self):
        conn, _ = _conn_with_fetches([_TABLE_PRESENT, None])
        _run(conn)
        conn.close.assert_called_once()

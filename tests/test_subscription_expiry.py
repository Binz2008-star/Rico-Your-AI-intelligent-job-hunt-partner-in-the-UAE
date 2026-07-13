"""Tests for daily subscription expiry maintenance task."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# expire_stale_paddle_subscriptions
# ---------------------------------------------------------------------------

class TestExpireStaleSubscriptions:

    def _run(self, rowcount: int):
        from src.repositories.paddle_repo import expire_stale_paddle_subscriptions

        mock_cur = MagicMock()
        mock_cur.rowcount = rowcount
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        return expire_stale_paddle_subscriptions(conn=mock_conn), mock_cur

    def test_returns_updated_count(self):
        result, _ = self._run(3)
        assert result == 3

    def test_returns_zero_when_nothing_expired(self):
        result, _ = self._run(0)
        assert result == 0

    def test_sql_targets_only_active_subscriptions(self):
        _, mock_cur = self._run(0)
        sql = mock_cur.execute.call_args[0][0]
        assert "status             = 'active'" in sql
        assert "current_period_end < NOW()" in sql
        assert "current_period_end IS NOT NULL" in sql

    def test_sql_sets_status_to_inactive(self):
        _, mock_cur = self._run(0)
        sql = mock_cur.execute.call_args[0][0]
        assert "status     = 'inactive'" in sql
        assert "updated_at = NOW()" in sql

    def test_returns_minus_one_when_db_unavailable(self):
        from src.repositories.paddle_repo import expire_stale_paddle_subscriptions

        with patch("src.repositories.paddle_repo._get_conn", side_effect=RuntimeError("DB unavailable")):
            result = expire_stale_paddle_subscriptions()

        assert result == -1

    def test_returns_minus_one_on_db_exception(self):
        from src.repositories.paddle_repo import expire_stale_paddle_subscriptions

        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("DB down")

        result = expire_stale_paddle_subscriptions(conn=mock_conn)

        assert result == -1


# ---------------------------------------------------------------------------
# _expire_subscriptions (run_daily wrapper)
# ---------------------------------------------------------------------------

class TestExpireSubscriptionsWrapper:

    def test_logs_count_when_rows_updated(self, caplog):
        import logging
        from src.run_daily import _expire_subscriptions

        with patch("src.run_daily.expire_stale_paddle_subscriptions", return_value=5):
            with caplog.at_level(logging.INFO, logger="run_daily"):
                _expire_subscriptions()

        assert "expired_count=5" in caplog.text

    def test_warns_when_db_unavailable(self, caplog):
        import logging
        from src.run_daily import _expire_subscriptions

        with patch("src.run_daily.expire_stale_paddle_subscriptions", return_value=-1):
            with caplog.at_level(logging.WARNING, logger="src.run_daily"):
                _expire_subscriptions()

        assert "db_unavailable" in caplog.text

    def test_does_not_raise_on_exception(self):
        from src.run_daily import _expire_subscriptions

        with patch("src.run_daily.expire_stale_paddle_subscriptions", side_effect=RuntimeError("boom")):
            _expire_subscriptions()  # must not raise

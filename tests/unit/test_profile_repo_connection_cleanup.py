"""
tests/unit/test_profile_repo_connection_cleanup.py

Regression coverage for the profile_repo.py DB connection-leak fix.

Several profile_repo functions used `with db.connect() as conn:` directly.
psycopg2 connections only commit/rollback on `__exit__` — they do NOT close
the physical connection. That leaked one Neon connection per call. The fix
routes these functions through the existing `_db_transaction()` context
manager, which always calls `conn.close()` in a `finally` block.

These tests patch `src.repositories.profile_repo.RicoDB` (the class used by
both `_db()` and `_db_transaction()`) with a fake that hands back a
controllable MagicMock connection, then assert `conn.close()` is called on
both the success path and the exception path.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_fake_ricodb(conn, bundle=None):
    class _FakeRicoDB:
        available = True

        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *, ensure_schema=True):
            return conn

        def get_user_bundle(self, user_id, conn=None):
            return bundle if bundle is not None else {"id": "db-uuid-1"}

    return _FakeRicoDB


def _make_conn(rows=None, execute_side_effect=None):
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__.return_value = cur
    cur.__exit__.return_value = False
    cur.fetchall.return_value = rows or []
    cur.fetchone.return_value = (rows or [None])[0]
    cur.rowcount = 1
    if execute_side_effect:
        cur.execute.side_effect = execute_side_effect
    conn.cursor.return_value = cur
    return conn, cur


class TestConnectionAlwaysClosedOnSuccess:
    def test_list_saved_searches_closes_connection(self):
        from src.repositories.profile_repo import list_saved_searches
        conn, _ = _make_conn(rows=[])
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            list_saved_searches("u@x.com")
        conn.close.assert_called_once()

    def test_delete_search_closes_connection(self):
        from src.repositories.profile_repo import delete_search
        conn, _ = _make_conn()
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            delete_search("u@x.com", "search-1")
        conn.close.assert_called_once()

    def test_get_search_by_id_closes_connection(self):
        from src.repositories.profile_repo import get_search_by_id
        conn, cur = _make_conn()
        cur.fetchone.return_value = None
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            get_search_by_id("u@x.com", "search-1")
        conn.close.assert_called_once()

    def test_get_profiles_by_role_closes_connection(self):
        from src.repositories.profile_repo import get_profiles_by_role
        conn, _ = _make_conn(rows=[])
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            get_profiles_by_role("HSE Manager")
        conn.close.assert_called_once()

    def test_find_profiles_by_email_closes_connection(self):
        from src.repositories.profile_repo import find_profiles_by_email
        conn, _ = _make_conn(rows=[])
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)), \
             patch("src.repositories.profile_repo._memory") as mem:
            mem.return_value.list_profiles.return_value = []
            find_profiles_by_email("u@x.com")
        conn.close.assert_called_once()

    def test_find_profiles_by_phone_closes_connection(self):
        from src.repositories.profile_repo import find_profiles_by_phone
        conn, _ = _make_conn(rows=[])
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)), \
             patch("src.repositories.profile_repo._memory") as mem:
            mem.return_value.list_profiles.return_value = []
            find_profiles_by_phone("+971501234567")
        conn.close.assert_called_once()

    def test_find_profiles_by_telegram_username_closes_connection(self):
        from src.repositories.profile_repo import find_profiles_by_telegram_username
        conn, _ = _make_conn(rows=[])
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)), \
             patch("src.repositories.profile_repo._memory") as mem:
            mem.return_value.list_profiles.return_value = []
            find_profiles_by_telegram_username("someuser")
        conn.close.assert_called_once()

    def test_health_check_closes_connection(self):
        from src.repositories.profile_repo import health_check
        conn, _ = _make_conn()
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            result = health_check()
        conn.close.assert_called_once()
        assert result["status"] == "healthy"


class TestConnectionClosedOnException:
    def test_list_saved_searches_closes_connection_on_query_error(self):
        from src.repositories.profile_repo import list_saved_searches
        conn, _ = _make_conn(execute_side_effect=RuntimeError("boom"))
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            result = list_saved_searches("u@x.com")
        assert result == []
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_get_search_by_id_closes_connection_on_query_error(self):
        from src.repositories.profile_repo import get_search_by_id
        conn, _ = _make_conn(execute_side_effect=RuntimeError("boom"))
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            result = get_search_by_id("u@x.com", "search-1")
        assert result is None
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_health_check_closes_connection_on_query_error(self):
        from src.repositories.profile_repo import health_check
        conn, _ = _make_conn(execute_side_effect=RuntimeError("boom"))
        with patch("src.repositories.profile_repo.RicoDB", _make_fake_ricodb(conn)):
            result = health_check()
        assert result["status"] == "unhealthy"
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()


class TestNoConnectionOpenedWhenDbUnavailable:
    def test_health_check_degraded_when_unavailable(self):
        from src.repositories.profile_repo import health_check

        class _UnavailableRicoDB:
            available = False

            def __init__(self, *args, **kwargs):
                pass

        with patch("src.repositories.profile_repo.RicoDB", _UnavailableRicoDB):
            result = health_check()
        assert result == {
            "status": "degraded",
            "db_available": False,
            "fallback_active": True,
        }

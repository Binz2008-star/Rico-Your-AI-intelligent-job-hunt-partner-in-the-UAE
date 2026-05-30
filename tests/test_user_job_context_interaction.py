"""Tests for the job-context interaction persistence layer.

Covers the new functions added for Job Context Persistence:
- record_interaction() — upserts per-job interaction state
- get_recently_interacted() / get_recently_discussed() — recall readers
- _status_for_action() — action→status mapping

DB is fully mocked; no live Neon connection is opened.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import src.repositories.user_job_context_repo as repo


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, rows=None):
        self.cursor_obj = _FakeCursor(rows)
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


# ── _status_for_action ──────────────────────────────────────────────────────

class TestStatusForAction:
    def test_apply_maps_to_applied(self):
        assert repo._status_for_action("apply") == "applied"

    def test_save_maps_to_saved(self):
        assert repo._status_for_action("save") == "saved"

    def test_skip_maps_to_skipped(self):
        assert repo._status_for_action("skip") == "skipped"

    def test_block_maps_to_blocked(self):
        assert repo._status_for_action("block") == "blocked"

    def test_why_maps_to_discussed(self):
        assert repo._status_for_action("why") == "discussed"

    def test_unknown_defaults_to_discussed(self):
        assert repo._status_for_action("frobnicate") == "discussed"

    def test_case_insensitive(self):
        assert repo._status_for_action("APPLY") == "applied"


# ── record_interaction ───────────────────────────────────────────────────────

class TestRecordInteraction:
    def test_skips_when_missing_title(self):
        # Returns before touching the DB — patch get_db_connection to assert it's untouched.
        with patch("src.db.get_db_connection") as gdc:
            repo.record_interaction("u1", "", "ACME", "apply")
            gdc.assert_not_called()

    def test_skips_when_missing_user(self):
        with patch("src.db.get_db_connection") as gdc:
            repo.record_interaction("", "Eng", "ACME", "apply")
            gdc.assert_not_called()

    def test_upserts_and_commits(self):
        conn = _FakeConn()
        with patch("src.db.get_db_connection", return_value=conn):
            repo.record_interaction("u1", "Systems Engineer", "AESG", "apply", note="great fit")
        assert conn.committed is True
        assert conn.closed is True
        sql, params = conn.cursor_obj.executed[0]
        assert "INSERT INTO user_job_context" in sql
        assert "ON CONFLICT" in sql
        # action lowercased, status mapped, note passed through
        assert params[3] == "apply"
        assert params[4] == "great fit"
        assert params[5] == "applied"

    def test_swallows_db_error(self):
        conn = _FakeConn()
        conn.cursor_obj.execute = MagicMock(side_effect=RuntimeError("boom"))
        with patch("src.db.get_db_connection", return_value=conn):
            # must not raise
            repo.record_interaction("u1", "Eng", "ACME", "save")
        assert conn.closed is True

    def test_no_db_connection_is_safe(self):
        with patch("src.db.get_db_connection", return_value=None):
            repo.record_interaction("u1", "Eng", "ACME", "save")  # no raise


# ── recall readers ────────────────────────────────────────────────────────────

class TestRecentReaders:
    def _row(self, title="Eng", company="ACME"):
        return (
            title, company, "Dubai", "apply",
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            "applied", "https://apply", "https://src",
        )

    def test_get_recently_interacted_maps_rows(self):
        conn = _FakeConn(rows=[self._row("Systems Engineer", "AESG")])
        with patch("src.db.get_db_connection", return_value=conn):
            out = repo.get_recently_interacted("u1")
        assert len(out) == 1
        assert out[0]["title"] == "Systems Engineer"
        assert out[0]["company"] == "AESG"
        assert out[0]["status"] == "applied"
        assert out[0]["apply_url"] == "https://apply"
        # ordered by last_action_at
        sql, _ = conn.cursor_obj.executed[0]
        assert "last_action_at" in sql

    def test_get_recently_discussed_orders_by_discussed(self):
        conn = _FakeConn(rows=[self._row()])
        with patch("src.db.get_db_connection", return_value=conn):
            repo.get_recently_discussed("u1")
        sql, _ = conn.cursor_obj.executed[0]
        assert "last_discussed_at" in sql

    def test_empty_user_returns_empty(self):
        out = repo.get_recently_interacted("")
        assert out == []

    def test_no_db_returns_empty(self):
        with patch("src.db.get_db_connection", return_value=None):
            assert repo.get_recently_discussed("u1") == []

    def test_db_error_returns_empty(self):
        conn = _FakeConn()
        conn.cursor_obj.execute = MagicMock(side_effect=RuntimeError("boom"))
        with patch("src.db.get_db_connection", return_value=conn):
            assert repo.get_recently_interacted("u1") == []

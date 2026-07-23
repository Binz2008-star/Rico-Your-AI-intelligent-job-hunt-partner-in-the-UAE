"""Tests for atomic application-draft decisions (#1075).

Verifies that update_draft_status and update_draft_status_returning
only transition drafts from 'pending' status, preventing double-approve
and TOCTOU races.
"""
from unittest.mock import patch, MagicMock


class TestUpdateDraftStatusAtomic:
    """update_draft_status must only transition pending → approved/rejected."""

    @patch("src.rico_db.RicoDB.connect")
    def test_update_only_pending(self, mock_connect):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_connect.return_value = conn

        # Simulate successful update (row found)
        cur.fetchone.return_value = MagicMock()

        from src.rico_db import RicoDB
        db = RicoDB()
        result = db.update_draft_status("draft-123", "user@example.com", "approved")

        assert result is True
        # Verify the SQL includes status = 'pending' guard
        sql = cur.execute.call_args[0][0]
        assert "status = 'pending'" in sql

    @patch("src.rico_db.RicoDB.connect")
    def test_update_returns_false_for_non_pending(self, mock_connect):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_connect.return_value = conn

        # Simulate no row updated (already approved/rejected)
        cur.fetchone.return_value = None

        from src.rico_db import RicoDB
        db = RicoDB()
        result = db.update_draft_status("draft-123", "user@example.com", "approved")

        assert result is False


class TestUpdateDraftStatusReturning:
    """update_draft_status_returning must atomically transition and return row."""

    @patch("src.rico_db.RicoDB.connect")
    def test_returns_row_on_success(self, mock_connect):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_connect.return_value = conn

        row_data = {"id": "draft-123", "status": "approved", "job_title": "Engineer", "company": "Acme"}
        cur.fetchone.return_value = row_data

        from src.rico_db import RicoDB
        db = RicoDB()
        result = db.update_draft_status_returning("draft-123", "user@example.com", "approved")

        assert result is not None
        assert result["status"] == "approved"
        sql = cur.execute.call_args[0][0]
        assert "status = 'pending'" in sql
        assert "RETURNING *" in sql

    @patch("src.rico_db.RicoDB.connect")
    def test_returns_none_for_non_pending(self, mock_connect):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_connect.return_value = conn

        cur.fetchone.return_value = None

        from src.rico_db import RicoDB
        db = RicoDB()
        result = db.update_draft_status_returning("draft-123", "user@example.com", "approved")

        assert result is None

"""tests/unit/test_identity_merge_db.py

DB-side tests for identity merge service.

All DB calls are mocked — no real database required.
This matches the existing repo test style (see test_jotform_webhook.py,
test_user_isolation.py).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.public_identity import make_guest_proof
from src.services.identity_merge_service import (
    merge_public_identity_into_auth,
    _get_db_user_id,
    _read_profile_jsonb,
    _write_profile_jsonb,
    _mark_guest_profile_merged,
    _migrate_user_scoped_rows,
)

_UTC = timezone.utc

# Browser-bound guest capability proof (#1070): every legitimate claim in these
# tests presents the proof for its exact session id.
_PROOF = make_guest_proof("web-guest")


def _mock_cursor(rows=None):
    """Return a mock cursor that yields rows from fetchone/fetchall."""
    cur = MagicMock()
    if rows is not None:
        it = iter(rows)

        def _fetchone():
            try:
                return next(it)
            except StopIteration:
                return None

        cur.fetchone = _fetchone
    return cur


def _mock_conn(cur):
    """Wrap a mock cursor in a minimal mock connection."""
    conn = MagicMock()
    # Properly mock the context manager protocol on cursor()
    cursor_ctx = MagicMock()
    cursor_ctx.__enter__ = MagicMock(return_value=cur)
    cursor_ctx.__exit__ = MagicMock(return_value=None)
    conn.cursor.return_value = cursor_ctx
    return conn


class TestGetDbUserId:
    def test_found_by_external_user_id(self):
        cur = _mock_cursor(rows=[{"id": "uuid-123"}])
        result = _get_db_user_id(cur, "public:web-test")
        assert result == "uuid-123"
        cur.execute.assert_called_once()
        args = cur.execute.call_args[0][1]
        assert args[0] == "public:web-test"

    def test_found_by_email(self):
        cur = _mock_cursor(rows=[{"id": "uuid-456"}])
        result = _get_db_user_id(cur, "alice@example.com")
        assert result == "uuid-456"

    def test_not_found_returns_none(self):
        cur = _mock_cursor(rows=[])
        result = _get_db_user_id(cur, "nobody@example.com")
        assert result is None


class TestReadProfileJsonb:
    def test_reads_profile(self):
        cur = _mock_cursor(rows=[{"profile": {"skills": ["python"]}}])
        result = _read_profile_jsonb(cur, "uuid-123")
        assert result == {"skills": ["python"]}

    def test_missing_row_returns_empty(self):
        cur = _mock_cursor(rows=[])
        result = _read_profile_jsonb(cur, "uuid-123")
        assert result == {}

    def test_json_string_parsed(self):
        cur = _mock_cursor(rows=[{"profile": '{"skills": ["js"]}'}])
        result = _read_profile_jsonb(cur, "uuid-123")
        assert result == {"skills": ["js"]}


class TestWriteProfileJsonb:
    def test_upserts_with_merge(self):
        cur = MagicMock()
        _write_profile_jsonb(cur, "uuid-123", {"skills": ["go"]})
        sql = cur.execute.call_args[0][0]
        assert "ON CONFLICT (user_id) DO UPDATE" in sql
        assert "rico_profiles.profile || EXCLUDED.profile" in sql


class TestMarkGuestProfileMerged:
    def test_sets_merged_marker(self):
        cur = MagicMock()
        _mark_guest_profile_merged(cur, "uuid-guest", "uuid-auth")
        sql = cur.execute.call_args[0][0]
        assert "ON CONFLICT (user_id) DO UPDATE" in sql
        data = cur.execute.call_args[0][1]
        # data[1] is the Json object
        assert data[1].adapted["profile_status"] == "merged"
        assert data[1].adapted["merged_into_user_id"] == "uuid-auth"
        assert "merged_at" in data[1].adapted


class TestMigrateUserScopedRows:
    def test_migrates_confirmed_table(self):
        cur = MagicMock()
        # Simulate table exists
        cur.fetchone.side_effect = [
            {"exists": True},  # table exists check
            {"exists": True},  # column exists check
        ]
        _migrate_user_scoped_rows(cur, "uuid-guest", "uuid-auth")
        # Find the UPDATE call among execute calls
        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c[0][0])]
        assert len(update_calls) > 0
        sql_str = str(update_calls[-1][0][0])
        assert "rico_saved_searches" in sql_str

    def test_skips_nonexistent_table(self):
        cur = MagicMock()
        cur.fetchone.return_value = None  # table does not exist
        _migrate_user_scoped_rows(cur, "uuid-guest", "uuid-auth")
        # Should only call the existence check, not an UPDATE
        calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c[0][0])]
        assert len(calls) == 0


class TestMergePublicIdentityIntoAuth:
    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_non_public_source(self, MockDB):
        result = merge_public_identity_into_auth("alice@example.com", "bob@example.com", guest_proof=_PROOF)
        assert result is False
        MockDB.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_malformed_public_source(self, MockDB):
        result = merge_public_identity_into_auth("public:has/slash", "bob@example.com", guest_proof=_PROOF)
        assert result is False
        MockDB.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_same_user_id(self, MockDB):
        result = merge_public_identity_into_auth(
            "public:same-session", "public:same-session",
            guest_proof=make_guest_proof("same-session"),
        )
        assert result is False
        MockDB.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_missing_guest_profile(self, MockDB):
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [
            {"pg_try_advisory_xact_lock": True},  # guest-scoped advisory lock
            None,                                  # guest not found
        ]

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_proof=_PROOF)
        assert result is False

    @patch("src.services.identity_merge_service.RicoDB")
    def test_successful_merge(self, MockDB):
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        cur = conn.cursor.return_value.__enter__.return_value
        # Sequence: advisory lock, guest id, auth id, guest profile, auth profile, table checks
        cur.fetchone.side_effect = [
            {"pg_try_advisory_xact_lock": True},   # advisory xact lock
            {"id": "uuid-guest"},          # guest lookup
            {"id": "uuid-auth"},           # auth lookup
            {"profile": {"skills": ["hse"]}},  # guest profile
            {"profile": {"years_experience": 5}},  # auth profile
            {"exists": True},              # table check 1
            {"exists": True},              # column check 1
        ]

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_proof=_PROOF)
        assert result is True
        conn.commit.assert_called_once()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_unproved_claim(self, MockDB):
        """A formatted public ID without the browser-bound proof is rejected (#1070)."""
        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com")
        assert result is False
        MockDB.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_wrong_proof(self, MockDB):
        """A proof minted for a DIFFERENT session cannot claim this guest."""
        result = merge_public_identity_into_auth(
            "public:web-guest", "auth@example.com",
            guest_proof=make_guest_proof("web-other"),
        )
        assert result is False
        MockDB.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_claim_by_second_account(self, MockDB):
        """A guest already claimed by another account is never merged again."""
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [
            {"pg_try_advisory_xact_lock": True},
            {"id": "uuid-guest"},
            {"id": "uuid-second-account"},
            {"profile": {"profile_status": "merged", "merged_into_user_id": "uuid-first-owner"}},
            {"profile": {}},
        ]

        result = merge_public_identity_into_auth(
            "public:web-guest", "second@example.com", guest_proof=_PROOF
        )
        assert result is False
        conn.commit.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rollback_on_error(self, MockDB):
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        cur = conn.cursor.return_value.__enter__.return_value
        cur.execute.side_effect = RuntimeError("DB exploded")

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_proof=_PROOF)
        assert result is False
        conn.rollback.assert_called_once()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_idempotent_second_merge(self, MockDB):
        """Second merge of same guest into same auth should succeed and commit."""
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [
            {"pg_try_advisory_xact_lock": True},   # advisory xact lock
            {"id": "uuid-guest"},
            {"id": "uuid-auth"},
            {"profile": {"profile_status": "merged", "merged_into_user_id": "uuid-auth"}},
            {"profile": {"skills": ["hse"]}},
            {"exists": True},
            {"exists": True},
        ]

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_proof=_PROOF)
        assert result is True
        # Replay by the SAME owner is a no-op success: no data is
        # re-copied and nothing needs to commit (#1070 one-time claim).
        conn.commit.assert_not_called()

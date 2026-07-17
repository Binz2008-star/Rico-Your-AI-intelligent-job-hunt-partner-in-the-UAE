"""tests/unit/test_identity_merge_db.py

DB-side tests for identity merge service.

All DB calls are mocked — no real database required.
This matches the existing repo test style (see test_jotform_webhook.py,
test_user_isolation.py).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.public_identity import make_guest_capability_for_sid
from src.services.identity_merge_service import (
    merge_public_identity_into_auth,
    _get_db_user_id,
    _read_profile_jsonb,
    _write_profile_jsonb,
    _mark_guest_profile_merged,
    _migrate_user_scoped_rows,
)

_UTC = timezone.utc

# Server-authoritative guest capability (#1070): every legitimate claim in
# these tests presents the signed token whose sid IS the merge source.
_TOKEN = make_guest_capability_for_sid("web-guest")


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
    def test_client_value_never_selects_source(self, MockDB):
        """The body value is correlation-only: whatever the client sends
        (another guest, malformed junk, an email), the merge source is the
        TOKEN identity — never rotated, overwritten, or selected by the
        client (#1070 locked design)."""
        for client_value in (
            "public:web-other-guest1",   # a different guest
            "alice@example.com",          # not a guest id at all
            "public:has/slash",           # malformed
        ):
            db = MagicMock()
            db.available = True
            conn = _mock_conn(MagicMock())
            db.connect.return_value = conn
            MockDB.return_value = db

            cur = conn.cursor.return_value.__enter__.return_value
            lookups = []

            real_execute = MagicMock()

            def _spy_execute(sql, params=None, _lookups=lookups):
                if params and "rico_users" in sql and "SELECT" in sql:
                    _lookups.append(params[0])

            cur.execute.side_effect = _spy_execute
            cur.fetchone.side_effect = [
                {"pg_try_advisory_xact_lock": True},
                {"id": "uuid-guest"},
                {"id": "uuid-auth"},
                {"profile": {}},
                {"profile": {}},
                {"claimed_by_user_id": "uuid-auth"},
                {"exists": True},
                {"exists": True},
            ]

            result = merge_public_identity_into_auth(
                client_value, "auth@example.com", guest_capability_token=_TOKEN
            )
            assert result is True
            # The guest looked up is the TOKEN's guest — not the client value.
            assert lookups[0] == "public:web-guest"
            assert client_value not in lookups

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_same_user_id(self, MockDB):
        result = merge_public_identity_into_auth(
            "public:same-session", "public:same-session",
            guest_capability_token=make_guest_capability_for_sid("same-session"),
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

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_capability_token=_TOKEN)
        assert result is False

    @patch("src.services.identity_merge_service.RicoDB")
    def test_successful_merge(self, MockDB):
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        cur = conn.cursor.return_value.__enter__.return_value
        # Sequence: advisory lock, guest id, auth id, guest profile,
        # auth profile, durable claim INSERT (returns our row = we own it),
        # table checks
        cur.fetchone.side_effect = [
            {"pg_try_advisory_xact_lock": True},   # advisory xact lock
            {"id": "uuid-guest"},          # guest lookup
            {"id": "uuid-auth"},           # auth lookup
            {"profile": {"skills": ["hse"]}},  # guest profile
            {"profile": {"years_experience": 5}},  # auth profile
            {"claimed_by_user_id": "uuid-auth"},  # claim INSERT ... RETURNING
            {"exists": True},              # table check 1
            {"exists": True},              # column check 1
        ]

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_capability_token=_TOKEN)
        assert result is True
        conn.commit.assert_called_once()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_merge_success_log_redacts_guest_sid(self, MockDB, caplog):
        """#1070 hardening: the merge_success log emits a hashed tag, never the
        raw guest SID."""
        secret_sid = "websecretsid987654"
        token = make_guest_capability_for_sid(secret_sid)
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [
            {"pg_try_advisory_xact_lock": True},
            {"id": "uuid-guest"},
            {"id": "uuid-auth"},
            {"profile": {"skills": ["hse"]}},
            {"profile": {"years_experience": 5}},
            {"claimed_by_user_id": "uuid-auth"},
            {"exists": True},
            {"exists": True},
        ]
        with caplog.at_level(logging.INFO, logger="src.services.identity_merge_service"):
            result = merge_public_identity_into_auth(
                f"public:{secret_sid}", "auth@example.com", guest_capability_token=token
            )
        assert result is True
        blob = "\n".join(r.getMessage() for r in caplog.records)
        assert "merge_success" in blob          # the success path DID log
        assert secret_sid not in blob           # ...but never the raw guest SID
        assert "guest:" in blob                  # a redacted tag is emitted instead

    @patch("src.services.identity_merge_service.RicoDB")
    def test_already_claimed_log_redacts_guest_sid(self, MockDB, caplog):
        """#1070 hardening: the already-claimed rejection log never carries the
        raw guest SID."""
        secret_sid = "websecretsid987654"
        token = make_guest_capability_for_sid(secret_sid)
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
        with caplog.at_level(logging.INFO, logger="src.services.identity_merge_service"):
            result = merge_public_identity_into_auth(
                f"public:{secret_sid}", "second@example.com", guest_capability_token=token
            )
        assert result is False
        blob = "\n".join(r.getMessage() for r in caplog.records)
        assert "already_claimed" in blob
        assert secret_sid not in blob
        assert "guest:" in blob

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_unproved_claim(self, MockDB):
        """A formatted public ID with no capability token is rejected (#1070)."""
        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com")
        assert result is False
        MockDB.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_rejects_tampered_token(self, MockDB):
        token = make_guest_capability_for_sid("web-guest")
        payload, _, sig = token.partition(".")
        bad = payload + "." + ("0" if sig[0] != "0" else "1") + sig[1:]
        result = merge_public_identity_into_auth(
            "public:web-guest", "auth@example.com", guest_capability_token=bad
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
            "public:web-guest", "second@example.com", guest_capability_token=_TOKEN
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

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_capability_token=_TOKEN)
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

        result = merge_public_identity_into_auth("public:web-guest", "auth@example.com", guest_capability_token=_TOKEN)
        assert result is True
        # Replay by the SAME owner is a no-op success: no data is
        # re-copied and nothing needs to commit (#1070 one-time claim).
        conn.commit.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_claim_row_owned_by_other_account_rejected(self, MockDB):
        """No profile marker, but the DURABLE claim row names another owner —
        the DB uniqueness authority wins even without a profile row (#1070)."""
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [
            {"pg_try_advisory_xact_lock": True},
            {"id": "uuid-guest"},
            {"id": "uuid-second"},
            {"profile": {}},                       # guest has NO profile marker
            {"profile": {}},
            None,                                   # claim INSERT: conflict, no row
            {"claimed_by_user_id": "uuid-first"},  # existing owner lookup
        ]

        result = merge_public_identity_into_auth(
            "public:web-guest", "second@example.com", guest_capability_token=_TOKEN
        )
        assert result is False
        conn.commit.assert_not_called()

    @patch("src.services.identity_merge_service.RicoDB")
    def test_claims_table_missing_fails_closed(self, MockDB):
        """Migration 044 not applied → merge fails closed, nothing copied."""
        db = MagicMock()
        db.available = True
        conn = _mock_conn(MagicMock())
        db.connect.return_value = conn
        MockDB.return_value = db

        class _UndefinedTable(Exception):
            pgcode = "42P01"

        cur = conn.cursor.return_value.__enter__.return_value
        responses = [
            {"pg_try_advisory_xact_lock": True},
            {"id": "uuid-guest"},
            {"id": "uuid-auth"},
            {"profile": {}},
            {"profile": {}},
        ]
        cur.fetchone.side_effect = responses

        def _execute(sql, *args, **kwargs):
            if "guest_identity_claims" in sql:
                raise _UndefinedTable()

        cur.execute.side_effect = _execute

        result = merge_public_identity_into_auth(
            "public:web-guest", "auth@example.com", guest_capability_token=_TOKEN
        )
        assert result is False
        conn.rollback.assert_called()
        conn.commit.assert_not_called()

"""
tests/test_chat_identity_contamination.py

Regression tests for P0 cross-user identity contamination and chat history
integrity bugs.

Coverage:
- Sanitizer drops pipeline artifact phrases stored as role=user
- Sanitizer drops messages with non-user/assistant roles
- Sanitizer passes clean messages unchanged
- None job title never produces "None role" from message_generator
- Role validation at every write layer (memory, DB, chat_api)
- Cross-user isolation: user A cannot see user B profile data via get_user_bundle ordering
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# _sanitize_history_for_llm
# ---------------------------------------------------------------------------

from src.rico_chat_api import _sanitize_history_for_llm


class TestSanitizeHistoryForLLM:
    def test_passes_clean_user_and_assistant_messages(self):
        messages = [
            {"role": "user", "content": "I want a job in Dubai"},
            {"role": "assistant", "content": "Sure, let me search."},
        ]
        result = _sanitize_history_for_llm(messages)
        assert len(result) == 2

    def test_drops_unknown_role(self):
        messages = [
            {"role": "tool", "content": "some tool output"},
            {"role": "function", "content": "fn result"},
            {"role": "user", "content": "hello"},
        ]
        result = _sanitize_history_for_llm(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_drops_system_role(self):
        messages = [
            {"role": "system", "content": "You are Rico."},
            {"role": "user", "content": "hi"},
        ]
        result = _sanitize_history_for_llm(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_drops_pipeline_artifact_stored_as_user(self):
        """generate_message() output must never reach the LLM as a user statement."""
        messages = [
            {
                "role": "user",
                "content": "I have UAE experience in executive operations and CEO support. Interested in Engineer role.",
            },
            {"role": "assistant", "content": "Great, I found some matches."},
        ]
        result = _sanitize_history_for_llm(messages)
        # Only the assistant message should survive
        assert len(result) == 1
        assert result[0]["role"] == "assistant"

    def test_drops_interested_in_none_role_artifact(self):
        messages = [
            {"role": "user", "content": "I am interested in the None role and would like to apply."},
            {"role": "user", "content": "search jobs in Abu Dhabi"},
        ]
        result = _sanitize_history_for_llm(messages)
        assert len(result) == 1
        assert "Abu Dhabi" in result[0]["content"]

    def test_drops_empty_content(self):
        messages = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "   "},
            {"role": "user", "content": "real message"},
        ]
        result = _sanitize_history_for_llm(messages)
        assert len(result) == 1
        assert "real message" in result[0]["content"]

    def test_handles_message_key_instead_of_content(self):
        """Memory store uses 'message' key; DB uses 'content'."""
        messages = [
            {"role": "user", "message": "help me find a job"},
        ]
        result = _sanitize_history_for_llm(messages)
        assert len(result) == 1

    def test_pipeline_artifact_in_assistant_is_kept(self):
        """Pipeline phrases in *assistant* output are legitimate (Rico explaining a draft)."""
        messages = [
            {
                "role": "assistant",
                "content": "Here is a draft: I am interested in the Engineer role and would like to apply.",
            },
        ]
        result = _sanitize_history_for_llm(messages)
        assert len(result) == 1


class TestOpenAIContextIdentitySafety:
    def test_profile_email_is_not_sent_to_openai_context(self):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        ctx = api._build_openai_context({
            "email": "private@rico.ai",
            "phone": "+971501234567",
            "skills": ["Python", "Compliance"],
        })

        assert ctx["profile_exists"] is True
        assert "email" not in ctx
        assert ctx["phone"] == "+971501234567"
        assert ctx["skills"] == ["Python", "Compliance"]


# ---------------------------------------------------------------------------
# message_generator — no "None role"
# ---------------------------------------------------------------------------

from src.message_generator import generate_message


class TestMessageGenerator:
    def test_normal_title(self):
        msg = generate_message({"title": "Software Engineer"})
        assert "Software Engineer" in msg
        assert "None" not in msg

    def test_none_title_does_not_produce_none_role(self):
        msg = generate_message({"title": None})
        assert "None" not in msg
        assert "this" in msg or "role" in msg

    def test_missing_title_key(self):
        msg = generate_message({})
        assert "None" not in msg

    def test_no_hardcoded_executive_operations(self):
        msg = generate_message({"title": "HSE Manager"})
        assert "executive operations" not in msg.lower()
        assert "CEO support" not in msg


# ---------------------------------------------------------------------------
# Role validation at write layers
# ---------------------------------------------------------------------------

class TestRoleValidationMemoryLayer:
    def test_valid_roles_are_accepted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_BACKEND", "json")
        import src.rico_memory as rm
        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        monkeypatch.setattr(rm, "_JSON_WRITE_ENABLED", True)

        store = rm.RicoMemoryStore()
        store.append_chat_message("test@example.com", "user", "hello")
        store.append_chat_message("test@example.com", "assistant", "hi there")
        history = store.load_chat_history("test@example.com")
        assert len(history) == 2

    def test_unknown_role_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_BACKEND", "json")
        import src.rico_memory as rm
        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        monkeypatch.setattr(rm, "_JSON_WRITE_ENABLED", True)

        store = rm.RicoMemoryStore()
        store.append_chat_message("test@example.com", "tool", "tool output")
        history = store.load_chat_history("test@example.com")
        assert len(history) == 0


class TestRoleValidationDBAppend:
    def test_unknown_role_is_rejected_before_db_call(self):
        from src.services.chat_service import db_append_chat
        with patch("src.services.chat_service._resolve_db_user_id") as mock_resolve:
            db_append_chat("test@example.com", "tool_result", "some output")
            mock_resolve.assert_not_called()

    def test_valid_role_proceeds_to_db(self):
        from src.services.chat_service import db_append_chat
        mock_db = MagicMock()
        # available is a property; patch at the class level for the instance
        type(mock_db).available = property(lambda self: True)
        with patch("src.services.chat_service._resolve_db_user_id", return_value="uuid-123"), \
             patch("src.rico_db.RicoDB", return_value=mock_db):
            db_append_chat("test@example.com", "user", "hello")
            # session_id is threaded from the ambient chat session (#1197); no
            # active session writes NULL, which is the legacy default thread.
            mock_db.append_chat.assert_called_once_with(
                "uuid-123", "user", "hello", session_id=None,
            )


class TestRoleValidationRicoDBLayer:
    def test_unknown_role_is_rejected(self):
        from src.rico_db import RicoDB
        db = RicoDB.__new__(RicoDB)
        from unittest.mock import PropertyMock
        with patch.object(type(db), "available", new_callable=PropertyMock, return_value=True):
            with patch.object(db, "_transaction") as mock_tx:
                db.append_chat("some-uuid", "pipeline_draft", "artifact text")
                mock_tx.assert_not_called()

    def test_valid_role_calls_insert(self):
        from src.rico_db import RicoDB
        db = RicoDB.__new__(RicoDB)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        from unittest.mock import PropertyMock
        with patch.object(type(db), "available", new_callable=PropertyMock, return_value=True):
            with patch.object(db, "_transaction", return_value=mock_conn):
                db.append_chat("some-uuid", "assistant", "hello")
        mock_cursor.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_user_bundle: ownership resolves through the validated auth identifier
# ---------------------------------------------------------------------------

class TestGetUserBundleOwnership:
    """Authenticated resolution binds to the identifier the caller authenticated with.

    REPLACES an earlier assertion here that required the ORDER BY to rank a match on the
    mutable contact column *ahead* of a match on the authenticated identifier. That
    ordering was introduced to stop intake-sourced rows shadowing web users, which was a
    real problem, but it made a mutable column the effective ownership key: any row
    carrying an account's contact value outranked the account's own row.

    The invariant is now the inverse, and the reason is recorded here so the old
    assertion is not reinstated by someone reading it as a regression:

      * the authenticated identifier decides ownership;
      * a public/guest row is never a candidate;
      * more than one surviving candidate fails closed rather than being ranked.

    The contact column stays in the WHERE clause so legacy accounts that never had an
    external identifier populated still resolve -- it simply cannot select a row on its
    own any more. Fixtures are synthetic.
    """

    def _run(self, rows):
        from src.rico_db import RicoDB
        db = RicoDB.__new__(RicoDB)
        captured_sql = []

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchmany.return_value = rows
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = lambda sql, params: captured_sql.append(sql)

        with patch.object(RicoDB, "available", new_callable=lambda: property(lambda self: True)), \
             patch.object(db, "connect", return_value=mock_conn):
            result = db.get_user_bundle("owner@synthetic.test")
        return result, (captured_sql[0] if captured_sql else "")

    def test_authenticated_identifier_is_ranked_first(self):
        _, sql = self._run([{"id": "owned-row"}])
        order_section = sql.lower()[sql.lower().find("order by"):]
        assert "u.external_user_id" in order_section, (
            "ownership must be decided by the authenticated identifier"
        )

    def test_public_rows_are_excluded_from_authenticated_resolution(self):
        _, sql = self._run([{"id": "owned-row"}])
        assert "not like 'public:" in sql.lower(), (
            "a guest row must never be a candidate for authenticated resolution"
        )

    def test_legacy_account_without_external_identifier_still_resolves(self):
        result, sql = self._run([{"id": "legacy-row", "external_user_id": None}])
        assert result["id"] == "legacy-row"
        assert "u.email" in sql, "the contact column must remain in the predicate"

    def test_multiple_candidates_fail_closed(self):
        from src.models.principal import IdentityOwnershipAmbiguous

        with pytest.raises(IdentityOwnershipAmbiguous):
            self._run([{"id": "row-1"}, {"id": "row-2"}])

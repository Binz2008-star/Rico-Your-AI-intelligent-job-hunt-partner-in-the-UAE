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
            mock_db.append_chat.assert_called_once_with("uuid-123", "user", "hello")


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
# get_user_bundle ordering: email > external_user_id
# ---------------------------------------------------------------------------

class TestGetUserBundleOrdering:
    """Verify that the SQL ORDER BY was patched to prefer email match."""

    def test_order_by_prefers_email_over_external_user_id(self):
        """The fixed ORDER BY must rank email=0 before external_user_id=0."""
        from src.rico_db import RicoDB
        db = RicoDB.__new__(RicoDB)

        captured_sql = []

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cur

        def capture_execute(sql, params):
            captured_sql.append(sql)

        mock_cur.execute.side_effect = capture_execute

        with patch.object(RicoDB, "available", new_callable=lambda: property(lambda self: True)), \
             patch.object(db, "connect", return_value=mock_conn):
            db.get_user_bundle("robenedwan.1@icloud.com")

        assert captured_sql, "expected a SQL query to be executed"
        sql = captured_sql[0].lower()
        # Only look within the ORDER BY clause, not the WHERE clause
        order_by_start = sql.find("order by")
        assert order_by_start != -1, "SQL must contain ORDER BY"
        order_section = sql[order_by_start:]
        email_pos = order_section.find("u.email =")
        ext_pos = order_section.find("u.external_user_id =")
        assert email_pos != -1, "ORDER BY must reference u.email"
        assert ext_pos != -1, "ORDER BY must reference u.external_user_id"
        assert email_pos < ext_pos, (
            "In ORDER BY, email match must appear before external_user_id match to prevent "
            "Jotform/Telegram rows shadowing web users"
        )

"""Test chat history persistence for authenticated users."""
import pytest
from unittest.mock import patch, MagicMock
from src.rico_db import RicoDB
from src.services.chat_service import send_message, get_chat_history, db_append_chat
from src.api.routers.rico_chat import RicoSessionContext
from src.rico_chat_api import RicoChatAPI


def test_db_append_chat_direct():
    """Test direct DB append function for chat history."""
    db = RicoDB()
    test_user_id = "db_append_test@example.com"

    # Cleanup before test
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s", (test_user_id,))
        conn.commit()

    try:
        # Directly append messages to DB
        db_append_chat(test_user_id, "user", "Test user message")
        db_append_chat(test_user_id, "assistant", "Test assistant message")

        # Retrieve history
        history = get_chat_history(test_user_id, limit=10)
        assert len(history) == 2, f"Expected 2 messages, got {len(history)}"

        # Verify message content
        user_msg = [msg for msg in history if msg.get("role") == "user"][0]
        assert user_msg.get("content") == "Test user message", f"User message mismatch: {user_msg}"

        assistant_msg = [msg for msg in history if msg.get("role") == "assistant"][0]
        assert assistant_msg.get("content") == "Test assistant message", f"Assistant message mismatch: {assistant_msg}"

    finally:
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s", (test_user_id,))
            conn.commit()


def test_rico_chat_api_get_recent_messages_db_first():
    """Test that RicoChatAPI._get_recent_messages prefers DB-backed history."""
    db = RicoDB()
    test_user_id = "db_first_test@example.com"

    # Cleanup before test
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s", (test_user_id,))
        conn.commit()

    try:
        # Add messages to DB
        db_append_chat(test_user_id, "user", "DB user message")
        db_append_chat(test_user_id, "assistant", "DB assistant message")

        # Create RicoChatAPI instance
        api = RicoChatAPI(persist=True)

        # Get recent messages - should return DB messages
        messages = api._get_recent_messages(test_user_id, limit=10)

        assert len(messages) == 2, f"Expected 2 messages from DB, got {len(messages)}"

        # Verify DB messages are returned
        user_msg = [msg for msg in messages if msg.get("role") == "user"][0]
        assert user_msg.get("content") == "DB user message", f"Expected DB user message, got: {user_msg}"

    finally:
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s", (test_user_id,))
            conn.commit()


def test_rico_chat_api_get_recent_messages_memory_fallback():
    """Test that RicoChatAPI._get_recent_messages falls back to memory when DB fails."""
    test_user_id = "memory_fallback_test@example.com"

    # Create RicoChatAPI instance
    api = RicoChatAPI(persist=True)

    # Add messages to memory
    api.memory.append_chat_message(test_user_id, "user", "Memory user message")
    api.memory.append_chat_message(test_user_id, "assistant", "Memory assistant message")

    # Mock get_chat_history to raise exception (simulating DB failure)
    with patch('src.rico_chat_api.get_chat_history', side_effect=Exception("DB connection failed")):
        messages = api._get_recent_messages(test_user_id, limit=10)

        # Should fall back to memory
        assert len(messages) == 2, f"Expected 2 messages from memory fallback, got {len(messages)}"

        user_msg = [msg for msg in messages if msg.get("role") == "user"][0]
        assert user_msg.get("content") == "Memory user message", f"Expected memory user message, got: {user_msg}"


def test_rico_chat_api_get_recent_messages_empty_when_both_fail():
    """Test that RicoChatAPI._get_recent_messages returns empty when both DB and memory fail."""
    test_user_id = "both_fail_test@example.com"

    # Create RicoChatAPI instance
    api = RicoChatAPI(persist=True)

    # Mock both DB and memory to fail
    with patch('src.rico_chat_api.get_chat_history', side_effect=Exception("DB failed")):
        with patch.object(api.memory, 'get_chat_messages', side_effect=Exception("Memory failed")):
            messages = api._get_recent_messages(test_user_id, limit=10)

            assert len(messages) == 0, f"Expected empty list when both fail, got {len(messages)}"


def test_chat_history_empty_for_new_user():
    """Test that chat history is empty for a new user."""
    test_user_id = "new_user_history_test@example.com"

    history = get_chat_history(test_user_id, limit=10)
    assert len(history) == 0, f"Expected empty history for new user, got {len(history)} messages"

"""Unit tests for clear chat history endpoint and service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestClearChatHistoryService:
    """chat_service.clear_chat_history deletes chat rows, leaves profile untouched."""

    def test_clear_calls_db_delete(self):
        """DB delete runs with the resolved user_id."""
        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_db = MagicMock()
        mock_db.available = True
        mock_db.connect.return_value = mock_conn

        with (
            patch("src.services.chat_service._resolve_db_user_id", return_value="uuid-123"),
            patch("src.rico_db.RicoDB", return_value=mock_db),
            patch("src.rico_memory.RicoMemoryStore"),
        ):
            from src.services.chat_service import clear_chat_history
            clear_chat_history("test@example.com")

        mock_cur.execute.assert_called_once_with(
            "DELETE FROM rico_chat_history WHERE user_id = %s",
            ("uuid-123",),
        )

    def test_clear_no_op_when_db_unavailable(self):
        """When DB is unavailable, clear_chat_history should not raise."""
        mock_db = MagicMock()
        mock_db.available = False

        with (
            patch("src.services.chat_service._resolve_db_user_id", return_value="uuid-123"),
            patch("src.rico_db.RicoDB", return_value=mock_db),
            patch("src.rico_memory.RicoMemoryStore"),
        ):
            from src.services.chat_service import clear_chat_history
            clear_chat_history("test@example.com")  # must not raise

    def test_clear_no_op_when_user_not_found(self):
        """When user_id cannot be resolved, clear_chat_history should not raise."""
        with (
            patch("src.services.chat_service._resolve_db_user_id", return_value=None),
            patch("src.rico_memory.RicoMemoryStore"),
        ):
            from src.services.chat_service import clear_chat_history
            clear_chat_history("ghost@example.com")  # must not raise

    def test_clear_swallows_db_exception(self):
        """DB errors are swallowed so the API never returns 500 for a clear."""
        mock_db = MagicMock()
        mock_db.available = True
        mock_db.connect.side_effect = RuntimeError("DB down")

        with (
            patch("src.services.chat_service._resolve_db_user_id", return_value="uuid-123"),
            patch("src.rico_db.RicoDB", return_value=mock_db),
            patch("src.rico_memory.RicoMemoryStore"),
        ):
            from src.services.chat_service import clear_chat_history
            clear_chat_history("test@example.com")  # must not raise



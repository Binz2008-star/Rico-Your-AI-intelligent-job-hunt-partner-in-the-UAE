from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.services.chat_service import get_chat_history


def test_get_chat_history_skips_invalid_fallback_timestamps():
    api = MagicMock()
    api.memory.get_chat_messages.return_value = [
        {"role": "user", "content": "bad", "timestamp": "not-a-date"},
        {"role": "assistant", "content": "old", "timestamp": "2026-05-01T00:00:00"},
        {"role": "assistant", "content": "new", "timestamp": "2026-05-20T00:00:00"},
    ]

    with patch("src.services.chat_service._resolve_db_user_id", return_value=None), \
         patch("src.rico_chat_api.RicoChatAPI", return_value=api):
        result = get_chat_history(
            "alice@example.com",
            limit=50,
            before=datetime.fromisoformat("2026-05-10T00:00:00"),
        )

    assert result == [
        {"role": "assistant", "content": "old", "timestamp": "2026-05-01T00:00:00"}
    ]

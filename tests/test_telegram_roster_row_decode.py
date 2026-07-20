"""Regression: get_users_with_telegram_alerts returns real row values.

RicoDB.connect() uses RealDictCursor, so each fetched row is already a dict.
The previous code did ``dict(zip(cols, row))``; iterating a dict yields its
KEYS, so it produced ``{"telegram_chat_id": "telegram_chat_id", ...}`` — the
real chat ids were lost and the daily per-user Telegram sender addressed a
bogus id (silent non-delivery). The fix uses ``dict(row)`` like the sibling
email-roster function.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import src.repositories.profile_repo as repo


def _db_returning(rows):
    """A mock RicoDB whose cursor.fetchall() yields RealDictCursor-style dicts."""
    cur = MagicMock()
    cur.fetchall.return_value = rows
    # Present a description too, so a resurrected dict(zip(cols, row)) would
    # still misbehave (proving the test discriminates fix from bug).
    cur.description = [
        ("external_user_id",),
        ("name",),
        ("telegram_chat_id",),
        ("telegram_username",),
    ]
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db = MagicMock()
    db.connect.return_value = conn
    return db


def test_roster_returns_real_chat_ids_not_column_names():
    rows = [
        {
            "external_user_id": "u1",
            "name": "Alice",
            "telegram_chat_id": "123456789",
            "telegram_username": "alice",
        },
        {
            "external_user_id": "u2",
            "name": "Bob",
            "telegram_chat_id": "987654321",
            "telegram_username": None,
        },
    ]
    with patch.object(repo, "_db", return_value=_db_returning(rows)):
        result = repo.get_users_with_telegram_alerts()

    assert len(result) == 2
    # The exact bug: value equalled the column name. Guard against it explicitly.
    assert result[0]["telegram_chat_id"] == "123456789"
    assert result[0]["telegram_chat_id"] != "telegram_chat_id"
    assert result[0]["name"] == "Alice"
    assert result[0]["external_user_id"] == "u1"
    assert result[1]["telegram_chat_id"] == "987654321"
    assert result[1]["telegram_username"] is None


def test_roster_empty_when_db_unavailable():
    with patch.object(repo, "_db", return_value=None):
        assert repo.get_users_with_telegram_alerts() == []


def test_roster_empty_on_query_exception():
    db = MagicMock()
    db.connect.side_effect = RuntimeError("db down")
    with patch.object(repo, "_db", return_value=db):
        assert repo.get_users_with_telegram_alerts() == []

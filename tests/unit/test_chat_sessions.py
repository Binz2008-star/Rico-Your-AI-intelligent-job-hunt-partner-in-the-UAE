"""Multi-session chat threads (#1193): context helpers + session-scoped service behavior.

Synthetic users and mocked repositories only — no live DB, no live providers.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.chat_service import clear_chat_history, get_chat_history
from src.services.chat_session_context import (
    DEFAULT_SESSION,
    derive_session_title,
    get_active_chat_session,
    normalize_chat_session_id,
    reset_active_chat_session,
    run_generator_with_session,
    set_active_chat_session,
)

UUID_A = "0b6f3c1e-8b1a-4f6e-9c3d-2a1b4c5d6e7f"


# ── normalize_chat_session_id ────────────────────────────────────────────────

def test_normalize_accepts_default_and_uuid_and_none():
    assert normalize_chat_session_id(None) is None
    assert normalize_chat_session_id("") is None
    assert normalize_chat_session_id("default") == DEFAULT_SESSION
    assert normalize_chat_session_id("DEFAULT") == DEFAULT_SESSION
    assert normalize_chat_session_id(UUID_A.upper()) == UUID_A


@pytest.mark.parametrize("bad", ["not-a-uuid", "1; DROP TABLE", "x" * 65, "public:abc"])
def test_normalize_rejects_garbage(bad):
    with pytest.raises(ValueError):
        normalize_chat_session_id(bad)


# ── ambient context + generator wrapper ──────────────────────────────────────

def test_set_reset_active_chat_session():
    assert get_active_chat_session() is None
    token = set_active_chat_session(UUID_A)
    assert get_active_chat_session() == UUID_A
    reset_active_chat_session(token)
    assert get_active_chat_session() is None


def test_run_generator_with_session_pins_every_segment():
    seen: list[str | None] = []

    def inner():
        seen.append(get_active_chat_session())
        yield 1
        seen.append(get_active_chat_session())
        yield 2

    assert list(run_generator_with_session(inner(), UUID_A)) == [1, 2]
    assert seen == [UUID_A, UUID_A]
    # The caller's own context is untouched.
    assert get_active_chat_session() is None


def test_run_generator_with_session_runs_inner_finally_on_close():
    finalized: list[str | None] = []

    def inner():
        try:
            yield 1
            yield 2
        finally:
            # Mirrors the SSE assistant-persist finally block: must still see
            # the pinned session on early client disconnect.
            finalized.append(get_active_chat_session())

    gen = run_generator_with_session(inner(), UUID_A)
    assert next(gen) == 1
    gen.close()
    assert finalized == [UUID_A]


# ── derive_session_title ─────────────────────────────────────────────────────

def test_derive_session_title_trims_and_caps():
    assert derive_session_title(None) is None
    assert derive_session_title("   ") is None
    assert derive_session_title("  find\n environmental   roles ") == "find environmental roles"
    long = "a" * 200
    title = derive_session_title(long)
    assert title is not None and len(title) <= 80 and title.endswith("…")


# ── get_chat_history session scoping ─────────────────────────────────────────

def test_named_session_empty_db_is_authoritative_no_json_bleed():
    """A UUID thread with no DB rows must NOT fall back to the user-scoped
    JSON memory — that would leak other threads' turns into a fresh session."""
    api = MagicMock()
    api.memory.get_chat_messages.return_value = [
        {"role": "user", "content": "from another thread", "timestamp": "2026-05-01T00:00:00"},
    ]
    with patch("src.services.chat_service._resolve_db_user_id", return_value="uid-1"), \
         patch("src.services.chat_service._db_get_chat_history", return_value=[]), \
         patch("src.rico_chat_api.RicoChatAPI", return_value=api):
        assert get_chat_history("synthetic@example.com", session_id=UUID_A) == []


def test_named_session_db_unavailable_yields_empty_thread():
    with patch("src.services.chat_service._resolve_db_user_id", return_value=None):
        assert get_chat_history("synthetic@example.com", session_id=UUID_A) == []


def test_default_session_keeps_json_fallback():
    api = MagicMock()
    api.memory.get_chat_messages.return_value = [
        {"role": "user", "content": "legacy turn", "timestamp": "2026-05-01T00:00:00"},
    ]
    with patch("src.services.chat_service._resolve_db_user_id", return_value=None), \
         patch("src.rico_chat_api.RicoChatAPI", return_value=api):
        result = get_chat_history("synthetic@example.com", session_id=DEFAULT_SESSION)
    assert [m["content"] for m in result] == ["legacy turn"]


def test_ambient_session_scopes_ai_context_reads():
    """_get_recent_messages calls get_chat_history with no session arg — the
    ambient active session must scope it so AI context never crosses threads."""
    captured: dict = {}

    def fake_db_get(db_uid, limit=50, before=None, session_id=None):
        captured["session_id"] = session_id
        return [{"role": "user", "content": "hi", "timestamp": None}]

    token = set_active_chat_session(UUID_A)
    try:
        with patch("src.services.chat_service._resolve_db_user_id", return_value="uid-1"), \
             patch("src.services.chat_service._db_get_chat_history", side_effect=fake_db_get):
            get_chat_history("synthetic@example.com", limit=8)
    finally:
        reset_active_chat_session(token)
    assert captured["session_id"] == UUID_A


# ── clear_chat_history session scoping ───────────────────────────────────────

def _run_clear(session_id):
    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    db = MagicMock()
    db.available = True
    db.connect.return_value = conn
    with patch("src.services.chat_service._resolve_db_user_id", return_value="uid-1"), \
         patch("src.rico_db.RicoDB", return_value=db), \
         patch("src.rico_memory.RicoMemoryStore") as store_cls:
        store_cls.return_value._chat_path.return_value.exists.return_value = False
        clear_chat_history("synthetic@example.com", session_id=session_id)
    return cursor.execute.call_args[0], store_cls.called


def test_clear_named_session_is_scoped_and_leaves_json_memory():
    (sql, params), json_touched = _run_clear(UUID_A)
    assert "session_id = %s" in sql
    assert params == ("uid-1", UUID_A)
    assert json_touched is False


def test_clear_default_session_targets_null_rows():
    (sql, params), _ = _run_clear(DEFAULT_SESSION)
    assert "session_id IS NULL" in sql
    assert params == ("uid-1",)


def test_clear_all_remains_unscoped():
    (sql, params), _ = _run_clear(None)
    assert "session_id" not in sql
    assert params == ("uid-1",)

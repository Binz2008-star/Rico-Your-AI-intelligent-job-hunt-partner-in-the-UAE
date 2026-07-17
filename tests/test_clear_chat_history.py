"""Truthful erasure contracts for chat/memory clear (#1088 wiring).

Replaces the pre-#1088 suite that locked in swallow-then-204 behavior. The
current contract: every erasure surface goes through the shared orchestrator
(src/services/erasure_service.py); failure to verifiably erase RAISES and the
HTTP surface returns a retryable 503 — never a success claim; success returns
a content-free deletion receipt.

All DB access is mocked here; the real-Postgres proof lives in
tests/integration/test_erasure_wiring_postgres.py.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.services.erasure_service import (
    ErasureError,
    erase_account_data,
    erase_conversation_data,
    erase_memory_data,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from src.api.rate_limit import limiter

    limiter.reset()
    yield


def _mock_rico_db(*, available=True, connect_error=None, resolve_row=("uuid-123",),
                  delete_rowcount=3):
    """A RicoDB double: one cursor serving the strict-resolve SELECT and the
    chat DELETE."""
    db = MagicMock()
    db.available = available
    if connect_error:
        db.connect.side_effect = connect_error
        return db
    cur = MagicMock()
    cur.fetchone.return_value = resolve_row
    cur.rowcount = delete_rowcount
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db.connect.return_value = conn
    return db


def _fake_store(tmp_path, user_id: str, memories=None, chat=True, signals=False):
    """Point RicoMemoryStore at tmp_path and seed per-user files."""
    import src.rico_memory as rm

    safe = rm._safe_key(user_id)
    if chat:
        (tmp_path / f"chat_{safe}.json").write_text("[]", encoding="utf-8")
    if signals:
        (tmp_path / f"signals_{safe}.json").write_text("[]", encoding="utf-8")
    if memories is not None:
        (tmp_path / f"memories_{safe}.json").write_text(
            json.dumps(memories), encoding="utf-8"
        )
    return rm


def _memories_file(rm, tmp_path, user_id: str):
    return tmp_path / f"memories_{rm._safe_key(user_id)}.json"


class TestConversationScope:
    def test_erases_db_rows_chat_file_and_conversation_memories(self, tmp_path, monkeypatch):
        rm = _fake_store(
            tmp_path,
            "u@test.com",
            memories=[
                {"memory_type": "conversation", "content": "secret sentence"},
                {"memory_type": "preference", "content": "likes Dubai"},
            ],
        )
        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)

        db = _mock_rico_db(delete_rowcount=4)
        with patch("src.services.erasure_service._rico_db", return_value=db):
            receipt = erase_conversation_data("u@test.com")

        assert receipt["scope"] == "chat"
        assert receipt["chat_rows_deleted"] == 4
        assert receipt["chat_file_removed"] is True
        assert receipt["conversation_memories_deleted"] == 1
        # Non-conversation memories are retained by the chat scope.
        remaining = json.loads(
            _memories_file(rm, tmp_path, "u@test.com").read_text(encoding="utf-8")
        )
        assert [m["memory_type"] for m in remaining] == ["preference"]

    def test_db_unavailable_raises_no_success(self, tmp_path, monkeypatch):
        import src.rico_memory as rm

        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db(available=False)
        with patch("src.services.erasure_service._rico_db", return_value=db):
            with pytest.raises(ErasureError):
                erase_conversation_data("u@test.com")

    def test_delete_failure_raises(self, tmp_path, monkeypatch):
        import src.rico_memory as rm

        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db()
        # First connect serves resolution; second raises on chat delete.
        good_conn = db.connect.return_value
        db.connect.side_effect = [good_conn, RuntimeError("DB down")]
        with patch("src.services.erasure_service._rico_db", return_value=db):
            with pytest.raises(ErasureError):
                erase_conversation_data("u@test.com")

    def test_no_db_account_is_successful_noop_for_rows(self, tmp_path, monkeypatch):
        rm = _fake_store(tmp_path, "ghost@test.com", memories=[
            {"memory_type": "conversation", "content": "x"},
        ], chat=False)
        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db(resolve_row=None)
        with patch("src.services.erasure_service._rico_db", return_value=db):
            receipt = erase_conversation_data("ghost@test.com")
        assert receipt["chat_rows_deleted"] == 0
        assert receipt["conversation_memories_deleted"] == 1

    def test_never_provisions_rows(self, tmp_path, monkeypatch):
        """Strict resolution must not INSERT/upsert anything."""
        import src.rico_memory as rm

        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db(resolve_row=None)
        with patch("src.services.erasure_service._rico_db", return_value=db):
            erase_conversation_data("new@test.com")
        cur = db.connect.return_value.cursor.return_value.__enter__.return_value
        executed_sql = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
        assert "INSERT" not in executed_sql.upper()


class TestMemoryScope:
    def test_erases_memory_file_and_purges_engine(self, tmp_path, monkeypatch):
        rm = _fake_store(tmp_path, "u@test.com", memories=[
            {"memory_type": "conversation", "content": "a"},
            {"memory_type": "preference", "content": "b"},
        ], chat=False)
        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db()
        engine_receipt = {
            "account_id": "uuid-123", "provisioned": True,
            "deletion_generation": 1, "events_deleted": 2, "facts_deleted": 1,
            "purged_at": "2026-07-17T00:00:00+00:00",
        }
        with patch("src.services.erasure_service._rico_db", return_value=db), patch(
            "src.repositories.career_memory_repo.purge_account_memory",
            return_value=engine_receipt,
        ) as mock_purge:
            receipt = erase_memory_data("u@test.com")

        assert receipt["scope"] == "memory"
        assert receipt["memory_entries_deleted"] == 2
        assert receipt["engine"]["events_deleted"] == 2
        mock_purge.assert_called_once_with(account_id="uuid-123", missing_ok=True)
        assert not _memories_file(rm, tmp_path, "u@test.com").exists()

    def test_engine_purge_failure_raises(self, tmp_path, monkeypatch):
        import src.rico_memory as rm

        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db()
        with patch("src.services.erasure_service._rico_db", return_value=db), patch(
            "src.repositories.career_memory_repo.purge_account_memory",
            side_effect=RuntimeError("engine db down"),
        ):
            with pytest.raises(ErasureError):
                erase_memory_data("u@test.com")

    def test_engine_not_provisioned_is_successful_noop(self, tmp_path, monkeypatch):
        """Migration 042 unapplied (42P01) → provisioned False, still success."""
        import src.rico_memory as rm

        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db()
        unprovisioned = {
            "account_id": "uuid-123", "provisioned": False,
            "deletion_generation": None, "events_deleted": 0,
            "facts_deleted": 0, "purged_at": None,
        }
        with patch("src.services.erasure_service._rico_db", return_value=db), patch(
            "src.repositories.career_memory_repo.purge_account_memory",
            return_value=unprovisioned,
        ):
            receipt = erase_memory_data("u@test.com")
        assert receipt["engine"]["provisioned"] is False

    def test_erasure_ignores_memory_engine_flag(self, tmp_path, monkeypatch):
        """Deletion is honored while RICO_MEMORY_ENGINE_ENABLED is unset/off."""
        import src.rico_memory as rm

        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        monkeypatch.delenv("RICO_MEMORY_ENGINE_ENABLED", raising=False)
        db = _mock_rico_db()
        with patch("src.services.erasure_service._rico_db", return_value=db), patch(
            "src.repositories.career_memory_repo.purge_account_memory",
            return_value={"provisioned": True, "deletion_generation": 1,
                          "events_deleted": 0, "facts_deleted": 0,
                          "account_id": "uuid-123", "purged_at": None},
        ) as mock_purge:
            erase_memory_data("u@test.com")
        mock_purge.assert_called_once()


class TestAccountScope:
    def test_account_scope_erases_all_storage_classes(self, tmp_path, monkeypatch):
        rm = _fake_store(tmp_path, "u@test.com", memories=[
            {"memory_type": "conversation", "content": "a"},
        ], chat=True, signals=True)
        monkeypatch.setattr(rm, "RICO_MEMORY_DIR", tmp_path)
        db = _mock_rico_db(delete_rowcount=2)
        with patch("src.services.erasure_service._rico_db", return_value=db), patch(
            "src.repositories.career_memory_repo.purge_account_memory",
            return_value={"provisioned": True, "deletion_generation": 3,
                          "events_deleted": 5, "facts_deleted": 2,
                          "account_id": "uuid-123", "purged_at": None},
        ):
            receipt = erase_account_data("u@test.com")

        assert receipt["scope"] == "account"
        assert receipt["chat_rows_deleted"] == 2
        assert receipt["chat_file_removed"] is True
        assert receipt["memory_entries_deleted"] == 1
        assert receipt["signals_file_removed"] is True
        assert receipt["engine"]["deletion_generation"] == 3


class TestHttpSurfaces:
    def _auth_client(self, monkeypatch, user_id="clear@test.com"):
        import src.api.routers.rico_chat as rico_chat_router

        def mock_get_user(request):
            user = {"email": user_id, "role": "user"}
            request.state.current_user = user
            request.state.user_id = user_id
            return user

        monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)
        return TestClient(app)

    def test_clear_history_returns_receipt(self, monkeypatch):
        client = self._auth_client(monkeypatch)
        receipt = {"scope": "chat", "chat_rows_deleted": 2,
                   "chat_file_removed": False, "conversation_memories_deleted": 1,
                   "completed_at": "2026-07-17T00:00:00+00:00"}
        with patch(
            "src.services.erasure_service.erase_conversation_data",
            return_value=receipt,
        ):
            r = client.delete("/api/v1/rico/chat/history")
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "chat"
        assert body["chat_rows_deleted"] == 2

    def test_clear_history_failure_returns_503(self, monkeypatch):
        client = self._auth_client(monkeypatch)
        with patch(
            "src.services.erasure_service.erase_conversation_data",
            side_effect=ErasureError("db down"),
        ):
            r = client.delete("/api/v1/rico/chat/history")
        assert r.status_code == 503

    def test_clear_memory_returns_receipt(self, monkeypatch):
        client = self._auth_client(monkeypatch)
        receipt = {"scope": "memory", "memory_entries_deleted": 3,
                   "engine": {"provisioned": True, "deletion_generation": 1,
                              "events_deleted": 0, "facts_deleted": 0},
                   "completed_at": "2026-07-17T00:00:00+00:00"}
        with patch(
            "src.services.erasure_service.erase_memory_data",
            return_value=receipt,
        ):
            r = client.delete("/api/v1/rico/memory")
        assert r.status_code == 200
        assert r.json()["memory_entries_deleted"] == 3

    def test_clear_memory_failure_returns_503(self, monkeypatch):
        client = self._auth_client(monkeypatch)
        with patch(
            "src.services.erasure_service.erase_memory_data",
            side_effect=ErasureError("engine db down"),
        ):
            r = client.delete("/api/v1/rico/memory")
        assert r.status_code == 503

    def test_unauthenticated_memory_clear_rejected(self):
        client = TestClient(app, raise_server_exceptions=False)
        assert client.delete("/api/v1/rico/memory").status_code == 401


class TestChatServiceShim:
    def test_clear_chat_history_delegates_and_propagates(self):
        from src.services import chat_service

        with patch(
            "src.services.erasure_service.erase_conversation_data",
            return_value={"scope": "chat"},
        ) as mock_erase:
            assert chat_service.clear_chat_history("u@test.com") == {"scope": "chat"}
        mock_erase.assert_called_once_with("u@test.com")

        with patch(
            "src.services.erasure_service.erase_conversation_data",
            side_effect=ErasureError("down"),
        ):
            with pytest.raises(ErasureError):
                chat_service.clear_chat_history("u@test.com")

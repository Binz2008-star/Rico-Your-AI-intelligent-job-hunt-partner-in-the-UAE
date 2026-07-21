"""Mandatory-Postgres fail-closed contract (DEC-20260721-001 slice 4).

Under RICO_OPERATION_STORE=postgres the shared store is MANDATORY: a store
failure must NEVER fall back to the in-process memory backend (that is the
duplicate-cascade hazard slice 1 removed under multiple live workers). It must
raise OperationStoreUnavailable, which the chat entrypoint surfaces as an
honest temporary-unavailable reply — no raw 500, no unguarded cascade.

These are fast unit tests (RepoUnavailable is mocked); the real multi-process
race proof lives in tests/integration/test_operation_multiworker_postgres.py.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.services import operation_state as ops
from src.repositories.chat_operations_repo import RepoUnavailable


@pytest.fixture()
def mandatory_mode(monkeypatch):
    monkeypatch.setenv("RICO_OPERATION_STORE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused/for_mode_only")
    yield


@pytest.fixture()
def auto_mode(monkeypatch):
    monkeypatch.setenv("RICO_OPERATION_STORE", "auto")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused/for_mode_only")
    # Isolate the memory backend so the auto-fallback assertions are clean.
    monkeypatch.setattr(ops, "_OPERATIONS", {})
    monkeypatch.setattr(ops, "_LATEST_BY_USER", {})

    class _NullMemory:
        def set_context(self, *a, **k): return None
        def get_context(self, *a, **k): return None
    monkeypatch.setattr(ops, "_memory", _NullMemory())
    yield


# ── mandatory mode: every store operation fails closed, never memory ─────────

def test_start_raises_and_never_touches_memory(mandatory_mode):
    with patch.object(ops._repo, "claim", side_effect=RepoUnavailable("table missing")), \
         patch.object(ops, "_memory_start", side_effect=AssertionError("memory fallback must not run")):
        with pytest.raises(ops.OperationStoreUnavailable):
            ops.start_job_search_operation(user_id="u@test.com", role_or_query="hse", operation_id="op_x")


def test_get_operation_raises_not_memory(mandatory_mode):
    with patch.object(ops._repo, "get", side_effect=RepoUnavailable("conn down")), \
         patch.object(ops, "_memory_get", side_effect=AssertionError("memory fallback must not run")):
        with pytest.raises(ops.OperationStoreUnavailable):
            ops.get_operation("u@test.com", "op_x")


def test_get_operation_absent_row_returns_none_not_memory(mandatory_mode):
    """A genuinely absent row is None — it must NOT resurrect memory state."""
    with patch.object(ops._repo, "get", return_value=None), \
         patch.object(ops, "_memory_get", side_effect=AssertionError("memory must not run")):
        assert ops.get_operation("u@test.com", "op_x") is None


def test_get_latest_raises_not_memory(mandatory_mode):
    with patch.object(ops._repo, "get_latest", side_effect=RepoUnavailable("down")):
        with pytest.raises(ops.OperationStoreUnavailable):
            ops.get_latest_job_search_operation("u@test.com")


def test_update_operation_raises_not_memory(mandatory_mode):
    with patch.object(ops._repo, "update_status", side_effect=RepoUnavailable("down")), \
         patch.object(ops, "_memory_get", side_effect=AssertionError("memory must not run")):
        with pytest.raises(ops.OperationStoreUnavailable):
            ops.update_operation(user_id="u@test.com", operation_id="op_x", status="failed")


def test_build_status_response_is_honest_when_store_down(mandatory_mode):
    with patch.object(ops._repo, "get_latest", side_effect=RepoUnavailable("down")):
        resp = ops.build_status_response("u@test.com")
    assert resp is not None
    assert resp["service_unavailable"] is True
    assert resp["error"] == "operation_store_unavailable"


# ── auto mode (default): the memory fallback is preserved (single-worker) ─────

def test_auto_mode_still_falls_back_to_memory(auto_mode):
    """The single-worker default is unchanged: a store failure falls back to
    the in-process memory backend and returns a claimed operation."""
    with patch.object(ops._repo, "claim", side_effect=RepoUnavailable("down")):
        op = ops.start_job_search_operation(user_id="u@test.com", role_or_query="hse", operation_id="op_y")
    assert op["claimed"] is True
    assert op["operation_id"] == "op_y"
    # It's a memory record (process-nonce ownership), not a db record.
    assert op.get("ownership") != "db"


def test_timing_overrides_are_ignored_without_pytest_marker(monkeypatch):
    """The lease/heartbeat env overrides are honored ONLY under an active
    pytest run (PYTEST_CURRENT_TEST present). Without it — i.e. in production —
    a stray RICO_OPERATION_LEASE_SECONDS is IGNORED and the production defaults
    stand, so it can never shrink the lease to a takeover-racy value."""
    monkeypatch.setenv("RICO_OPERATION_LEASE_SECONDS", "1")
    monkeypatch.setenv("RICO_OPERATION_HEARTBEAT_SECONDS", "0.1")

    # With the pytest marker present, the override is honored (test path).
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "dummy::test")
    assert ops._lease_seconds() == 1
    assert ops._heartbeat_interval() == 0.1

    # Simulate production: no pytest marker → overrides ignored, defaults win.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert ops._lease_seconds() == ops.LEASE_SECONDS      # 60, not 1
    assert ops._heartbeat_interval() == ops.HEARTBEAT_INTERVAL_SECONDS  # 10, not 0.1


def test_ownership_lost_self_fence_flag(monkeypatch):
    """The self-fence flag is set/read/cleared as a cooperative checkpoint."""
    ops._mark_ownership_lost("op_fence", 1)
    assert ops.ownership_lost("op_fence", 1) is True
    assert ops.ownership_lost("op_fence", 2) is False
    ops.reset_for_tests()
    assert ops.ownership_lost("op_fence", 1) is False


def test_mode_helpers():
    with patch.dict(os.environ, {"RICO_OPERATION_STORE": "postgres"}):
        assert ops._mandatory_db() is True
        assert ops._db_mode() is True
    with patch.dict(os.environ, {"RICO_OPERATION_STORE": "auto", "DATABASE_URL": "postgresql://x"}):
        assert ops._mandatory_db() is False
        assert ops._db_mode() is True
    with patch.dict(os.environ, {"RICO_OPERATION_STORE": "memory"}):
        assert ops._mandatory_db() is False
        assert ops._db_mode() is False


# ── the chat entrypoint surfaces it as an honest 503-mappable reply ──────────

def test_process_message_returns_service_unavailable(mandatory_mode):
    """RicoChatAPI.process_message maps OperationStoreUnavailable to an honest
    service_unavailable reply (no cascade, no 500)."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI.__new__(RicoChatAPI)
    with patch.object(
        RicoChatAPI, "_process_message_inner",
        side_effect=ops.OperationStoreUnavailable("store down"),
    ), patch.object(RicoChatAPI, "_record_last_turn"):
        result = api.process_message(
            user_id="u@test.com", message="find hse jobs", operation_id="op_z"
        )
    assert result["type"] == "service_unavailable"
    assert result["service_unavailable"] is True
    assert result["success"] is False
    assert result["response_source"] == "operation_store_unavailable"

"""GET /api/v1/rico/operations/{operation_id} — contract pins (owner item 7).

The read-only status endpoint used by the command surface to WAIT on a slow
search instead of re-sending it:

1. Requires authentication (401 without a JWT cookie).
2. Enforces ownership (another user's operation → 404, indistinguishable
   from non-existent — no cross-user observability).
3. Exposes status/ownership metadata ONLY — never the stored role/query
   text, provider payloads, CV text, or any profile field.
4. Applies the expired transition on read so a dead execution's record
   settles terminal without a write path.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.services import operation_state as ops

_OWNER = "op-owner@test.com"
_OTHER = "op-intruder@test.com"
_OP = "op_test_endpoint_01"

# The FULL public surface of a status response. Adding a key here is a
# review-worthy event — it must never grow to include query/role text.
_ALLOWED_KEYS = {
    "operation_id", "status", "active", "stale", "terminal", "result_count",
    "age_seconds",
}


def _client(email: str | None):
    from src.api.app import app
    tc = TestClient(app, raise_server_exceptions=False)
    if email:
        from src.api.auth import create_access_token
        tc.cookies.set("access_token", create_access_token({"sub": email, "role": "user"}))
    return tc


@pytest.fixture(autouse=True)
def _isolated_operation_store(monkeypatch):
    monkeypatch.setattr(ops, "_OPERATIONS", {})
    monkeypatch.setattr(ops, "_LATEST_BY_USER", {})

    class _NullMemory:
        def set_context(self, *a, **k):
            return None

        def get_context(self, *a, **k):
            return None

    monkeypatch.setattr(ops, "_memory", _NullMemory())


def test_requires_authentication():
    ops.start_job_search_operation(user_id=_OWNER, role_or_query="hse", operation_id=_OP)
    res = _client(None).get(f"/api/v1/rico/operations/{_OP}")
    assert res.status_code == 401


def test_owner_reads_status_with_narrow_key_set():
    ops.start_job_search_operation(
        user_id=_OWNER, role_or_query="hse manager dubai", operation_id=_OP
    )
    res = _client(_OWNER).get(f"/api/v1/rico/operations/{_OP}")
    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) == _ALLOWED_KEYS
    assert body["operation_id"] == _OP
    assert body["status"] == "running"
    assert body["active"] is True
    assert body["terminal"] is False
    # The search text is stored on the record but must never leave the server.
    assert "hse" not in str(body).lower()


def test_other_user_gets_404_not_the_operation():
    ops.start_job_search_operation(
        user_id=_OWNER, role_or_query="hse manager", operation_id=_OP
    )
    res = _client(_OTHER).get(f"/api/v1/rico/operations/{_OP}")
    assert res.status_code == 404


def test_unknown_and_malformed_ids_are_404():
    c = _client(_OWNER)
    assert c.get("/api/v1/rico/operations/op_never_existed_1").status_code == 404
    assert c.get("/api/v1/rico/operations/x").status_code == 404  # < 8 chars


def test_completed_operation_reports_terminal():
    ops.start_job_search_operation(user_id=_OWNER, role_or_query="hse", operation_id=_OP)
    ops.mark_completed(_OWNER, _OP, result_count=4, attempt=1)
    body = _client(_OWNER).get(f"/api/v1/rico/operations/{_OP}").json()
    assert body["status"] == "completed"
    assert body["terminal"] is True
    assert body["active"] is False
    assert body["result_count"] == 4


def test_stale_owned_operation_stays_active_and_reports_stale():
    """Age never releases ownership: an over-threshold record owned by this
    live process reads active+stale, NOT expired — the client stops waiting
    but a same-id re-send stays blocked."""
    from datetime import datetime, timedelta, timezone
    ops.start_job_search_operation(user_id=_OWNER, role_or_query="hse", operation_id=_OP)
    ops._OPERATIONS[_OP]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=ops.STALE_AFTER_SECONDS + 1)
    ).isoformat()
    body = _client(_OWNER).get(f"/api/v1/rico/operations/{_OP}").json()
    assert body["status"] == "running"
    assert body["active"] is True
    assert body["stale"] is True
    assert body["terminal"] is False


def test_read_settles_dead_process_records_to_expired():
    """A record whose executor process is dead (nonce mismatch — e.g. after
    a restart) settles to the terminal expired state on read."""
    ops.start_job_search_operation(user_id=_OWNER, role_or_query="hse", operation_id=_OP)
    ops._OPERATIONS[_OP]["process_nonce"] = "dead-process-nonce"
    body = _client(_OWNER).get(f"/api/v1/rico/operations/{_OP}").json()
    assert body["status"] == "expired"
    assert body["terminal"] is True
    assert body["active"] is False

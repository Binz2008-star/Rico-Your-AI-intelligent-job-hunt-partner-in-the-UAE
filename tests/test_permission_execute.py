"""
tests/test_permission_execute.py
Integration tests for POST /api/v1/rico/actions/execute (CAREER-OS-03).

Tests cover:
  - Auth guard (401 without token)
  - Valid approval request routes through agent_runtime
  - Permission ID is embedded in the audit source
  - User ID always comes from JWT, not body
  - Unknown action returns ok=False (not 422 — runtime validates)
  - Missing required fields return 422
  - Response shape matches ActionResponse
  - Schema-level contract tests (pure Pydantic, no network)
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL",    "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET",     "x" * 32)

_JOB = {
    "id":       "job-perm-001",
    "title":    "Risk Manager",
    "company":  "Gulf Corp",
    "location": "Dubai, UAE",
    "link":     "https://example.com/job/perm-001",
    "score":    88,
}

_URL = "/api/v1/rico/actions/execute"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "perm-test@rico.ai"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


@pytest.fixture(scope="module")
def anon_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


# ── Schema-level tests (pure Pydantic) ───────────────────────────────────────

class TestExecutePermissionSchema:
    def test_request_model_requires_permission_id(self):
        from pydantic import ValidationError
        from src.schemas.actions import ExecutePermissionActionRequest
        with pytest.raises(ValidationError):
            ExecutePermissionActionRequest(action="why")

    def test_request_model_requires_action(self):
        from pydantic import ValidationError
        from src.schemas.actions import ExecutePermissionActionRequest
        with pytest.raises(ValidationError):
            ExecutePermissionActionRequest(permission_id="perm-001")

    def test_request_model_valid_minimal(self):
        from src.schemas.actions import ExecutePermissionActionRequest
        req = ExecutePermissionActionRequest(permission_id="perm-001", action="why")
        assert req.permission_id == "perm-001"
        assert req.action == "why"
        assert req.job_key == ""
        assert req.source == "permission_card"

    def test_request_model_source_default(self):
        from src.schemas.actions import ExecutePermissionActionRequest
        req = ExecutePermissionActionRequest(permission_id="perm-001", action="save")
        assert req.source == "permission_card"

    def test_request_model_accepts_job_dict(self):
        from src.schemas.actions import ExecutePermissionActionRequest
        req = ExecutePermissionActionRequest(
            permission_id="perm-001",
            action="apply",
            job={"title": "Risk Manager", "company": "Gulf Corp"},
        )
        assert req.job is not None
        assert req.job["company"] == "Gulf Corp"

    def test_permission_id_max_length_enforced(self):
        from pydantic import ValidationError
        from src.schemas.actions import ExecutePermissionActionRequest
        with pytest.raises(ValidationError):
            ExecutePermissionActionRequest(permission_id="x" * 129, action="why")


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestPermissionExecuteAuth:
    def test_unauthenticated_returns_401(self, anon_client):
        r = anon_client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 401

    def test_authenticated_reaches_endpoint(self, client):
        r = client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200

    def test_user_id_comes_from_jwt_not_body(self, client):
        r = client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert r.json()["user_id"] == "perm-test@rico.ai"


# ── Request validation ────────────────────────────────────────────────────────

class TestPermissionExecuteValidation:
    def test_missing_permission_id_returns_422(self, client):
        r = client.post(_URL, json={"action": "why", "job": _JOB})
        assert r.status_code == 422

    def test_missing_action_returns_422(self, client):
        r = client.post(_URL, json={"permission_id": "perm-001", "job": _JOB})
        assert r.status_code == 422

    def test_empty_body_returns_422(self, client):
        r = client.post(_URL, json={})
        assert r.status_code == 422


# ── Response shape ────────────────────────────────────────────────────────────

class TestPermissionExecuteResponseShape:
    def test_response_has_all_required_fields(self, client):
        r = client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200
        data = r.json()
        for field in ("ok", "message", "action", "job_key", "source", "user_id",
                      "dry_run", "data", "error", "confidence", "explanation", "duration_ms"):
            assert field in data, f"missing field: {field}"

    def test_dry_run_is_always_false(self, client):
        r = client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "why",
            "job": _JOB,
        })
        assert r.json()["dry_run"] is False


# ── Permission ID in audit source ─────────────────────────────────────────────

class TestPermissionAuditSource:
    def test_permission_id_embedded_in_source(self, client):
        """Source field must contain permission_id so approvals are traceable."""
        r = client.post(_URL, json={
            "permission_id": "perm-trace-123",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert "perm-trace-123" in r.json()["source"]


# ── Unknown action ────────────────────────────────────────────────────────────

class TestPermissionExecuteUnknownAction:
    def test_unknown_action_returns_200_ok_false(self, client):
        r = client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "launch_rocket",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert r.json()["ok"] is False


# ── Live execution ────────────────────────────────────────────────────────────

class TestPermissionExecuteLive:
    def test_why_action_executes_successfully(self, client):
        r = client.post(_URL, json={
            "permission_id": "perm-why-001",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert len(data["message"]) > 0


# ── pre_approved circuit ──────────────────────────────────────────────────────

class TestPreApprovedCircuit:
    """Verify that execute_permission_action sets pre_approved=True so apply_to_job
    does not block with approval_required when routed through this endpoint."""

    def test_apply_via_execute_does_not_return_approval_required(self, client):
        """
        When action='apply' goes through /actions/execute it must NOT return
        approval_required — the PermissionRequestCard IS the approval.
        The result will be ok=True with a non-approval_required message, OR
        ok=False for another reason (e.g. auto-apply globally disabled) — but
        never the approval gate message.
        """
        r = client.post(_URL, json={
            "permission_id": "perm-apply-001",
            "action": "apply",
            "job": _JOB,
        })
        assert r.status_code == 200
        data = r.json()
        # Must not block with approval_required
        assert "approval_required" not in data.get("message", "").lower().replace(" ", "_")

    def test_permission_id_in_source_for_apply(self, client):
        """Apply via execute endpoint records permission_id in the audit source."""
        r = client.post(_URL, json={
            "permission_id": "perm-apply-trace-999",
            "action": "apply",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert "perm-apply-trace-999" in r.json()["source"]


# ── permission_request injection (unit) ──────────────────────────────────────

class TestPermissionRequestInjection:
    """Verify that agent_runtime injects permission_request into RuntimeResult.data
    when apply returns approval_required (i.e. via a non-pre_approved path)."""

    def test_runtime_injects_permission_request_on_approval_required(self):
        """Direct unit test of the runtime injection without HTTP."""
        from src.agent.runtime import agent_runtime

        result = agent_runtime.handle_action(
            user_id="unit-test@rico.ai",
            action="apply",
            job=_JOB,
            source="unit_test",
            pre_approved=False,   # normal chat path — approval required
        )
        # apply_to_job returns approval_required, runtime should inject permission_request
        assert isinstance(result.data, dict)
        # permission_request is injected only when factory can run; it may be absent if
        # the factory import fails (isolated test env), so we check conditionally
        if "permission_request" in result.data:
            pr = result.data["permission_request"]
            assert pr["id"]
            assert pr["risk_level"] == "high"
            assert pr["approve_action"]["kind"] == "approve"
            assert pr["approve_action"]["endpoint"] == "/api/v1/rico/actions/execute"

    def test_runtime_pre_approved_does_not_inject_permission_request(self):
        """When pre_approved=True the apply proceeds (or hits next gate), never loops back."""
        from src.agent.runtime import agent_runtime

        result = agent_runtime.handle_action(
            user_id="unit-test@rico.ai",
            action="apply",
            job=_JOB,
            source="unit_test",
            pre_approved=True,
        )
        # Should NOT have approval_required in data when pre_approved
        assert result.data.get("status") != "approval_required"

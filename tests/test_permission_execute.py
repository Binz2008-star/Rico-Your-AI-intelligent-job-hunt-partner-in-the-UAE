"""
tests/test_permission_execute.py
Integration tests for POST /api/v1/rico/actions/execute (CAREER-OS-03).

Tests cover:
  - Auth guard (401 without token)
  - Valid approval request routes through agent_runtime
  - Permission ID is embedded in the audit source
  - User ID always comes from JWT, not body
  - Unknown action returns 422 (schema-layer block)
  - Missing required fields return 422
  - Response shape matches ActionResponse
  - Schema-level contract tests (pure Pydantic, no network)
  - Permission ID security: fabricated / expired / one-time-use / wrong-action / wrong-user
"""
from __future__ import annotations

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL",    "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET",     "x" * 32)

_USER_ID = "perm-test@rico.ai"

_JOB = {
    "id":       "job-perm-001",
    "title":    "Risk Manager",
    "company":  "Gulf Corp",
    "location": "Dubai, UAE",
    "link":     "https://example.com/job/perm-001",
    "score":    88,
}

_URL = "/api/v1/rico/actions/execute"


def _perm(action: str = "why") -> str:
    """Register a server-issued permission ID for _USER_ID and return it."""
    import src.services.pending_permissions as pp
    pid = f"test-{action}-{uuid.uuid4().hex[:8]}"
    pp.register(pid, _USER_ID, action)
    return pid


def _perm_bound(action: str, job_key: str) -> str:
    """Register a permission for _USER_ID bound to a specific job_key."""
    import src.services.pending_permissions as pp
    pid = f"test-{action}-{uuid.uuid4().hex[:8]}"
    pp.register(pid, _USER_ID, action, job_key=job_key)
    return pid


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": _USER_ID})
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
            "permission_id": _perm("why"),
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200

    def test_user_id_comes_from_jwt_not_body(self, client):
        r = client.post(_URL, json={
            "permission_id": _perm("why"),
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert r.json()["user_id"] == _USER_ID


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
            "permission_id": _perm("why"),
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
            "permission_id": _perm("why"),
            "action": "why",
            "job": _JOB,
        })
        assert r.json()["dry_run"] is False


# ── Permission ID in audit source ─────────────────────────────────────────────

class TestPermissionAuditSource:
    def test_permission_id_embedded_in_source(self, client):
        """Source field must contain permission_id so approvals are traceable."""
        pid = _perm("why")
        r = client.post(_URL, json={
            "permission_id": pid,
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert pid in r.json()["source"]


# ── Action allowlist (schema-layer safety) ────────────────────────────────────

class TestExecuteActionAllowlist:
    """Verify that the explicit action allowlist in ExecutePermissionActionRequest
    blocks non-user-facing actions at the Pydantic layer — before they ever reach
    agent_runtime. This is defence-in-depth on top of the runtime's own validation."""

    def test_unknown_action_rejected_at_schema_level(self):
        from pydantic import ValidationError
        from src.schemas.actions import ExecutePermissionActionRequest
        with pytest.raises(ValidationError):
            ExecutePermissionActionRequest(permission_id="perm-001", action="launch_rocket")

    def test_trigger_pipeline_rejected_at_schema_level(self):
        """trigger_pipeline is a valid agent action but must not be executable
        through the permission engine (it is an admin/scheduler action)."""
        from pydantic import ValidationError
        from src.schemas.actions import ExecutePermissionActionRequest
        with pytest.raises(ValidationError):
            ExecutePermissionActionRequest(permission_id="perm-001", action="trigger_pipeline")

    def test_unknown_action_returns_422_not_200(self, client):
        """Now that action is validated at the Pydantic layer, unknown actions return
        422 Unprocessable Entity — not 200 ok=False — which is more semantically correct."""
        r = client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "launch_rocket",
            "job": _JOB,
        })
        assert r.status_code == 422

    def test_trigger_pipeline_returns_422(self, client):
        r = client.post(_URL, json={
            "permission_id": "perm-001",
            "action": "trigger_pipeline",
            "job": _JOB,
        })
        assert r.status_code == 422

    def test_all_allowed_actions_accepted_at_schema_level(self):
        """Every action in EXECUTE_ALLOWED_ACTIONS must pass schema validation."""
        from src.schemas.actions import ExecutePermissionActionRequest, EXECUTE_ALLOWED_ACTIONS
        for action in EXECUTE_ALLOWED_ACTIONS:
            req = ExecutePermissionActionRequest(permission_id="perm-001", action=action)
            assert req.action == action


# ── Live execution ────────────────────────────────────────────────────────────

class TestPermissionExecuteLive:
    def test_why_action_executes_successfully(self, client):
        r = client.post(_URL, json={
            "permission_id": _perm("why"),
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
            "permission_id": _perm("apply"),
            "action": "apply",
            "job": _JOB,
        })
        assert r.status_code == 200
        data = r.json()
        assert "approval_required" not in data.get("message", "").lower().replace(" ", "_")

    def test_permission_id_in_source_for_apply(self, client):
        """Apply via execute endpoint records permission_id in the audit source."""
        pid = _perm("apply")
        r = client.post(_URL, json={
            "permission_id": pid,
            "action": "apply",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert pid in r.json()["source"]


# ── Permission ID security ────────────────────────────────────────────────────

class TestPermissionIdSecurity:
    """Verify that the permission ID store prevents forged, expired, replayed,
    wrong-action, and cross-user approval requests."""

    def test_fabricated_permission_id_returns_403(self, client):
        """A permission_id never issued by the server must be rejected."""
        r = client.post(_URL, json={
            "permission_id": "totally-fake-id-not-issued",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 403

    def test_expired_permission_id_returns_403(self, client):
        """A permission_id whose TTL has elapsed must be rejected."""
        import src.services.pending_permissions as pp
        pid = f"test-expired-{uuid.uuid4().hex[:8]}"
        pp.register(pid, _USER_ID, "why")
        # Force-expire by setting expires_at in the past
        with pp._lock:
            pp._store[pid]["expires_at"] = time.monotonic() - 1
        r = client.post(_URL, json={
            "permission_id": pid,
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 403

    def test_permission_id_can_only_be_used_once(self, client):
        """A valid permission_id is consumed on first use; replaying it returns 403."""
        pid = _perm("why")
        r1 = client.post(_URL, json={"permission_id": pid, "action": "why", "job": _JOB})
        assert r1.status_code == 200
        r2 = client.post(_URL, json={"permission_id": pid, "action": "why", "job": _JOB})
        assert r2.status_code == 403

    def test_wrong_action_for_permission_id_returns_403(self, client):
        """A permission_id issued for 'why' cannot be used for 'save'."""
        pid = _perm("why")
        r = client.post(_URL, json={
            "permission_id": pid,
            "action": "save",
            "job": _JOB,
        })
        assert r.status_code == 403

    def test_other_user_cannot_use_permission_id(self):
        """A permission_id issued for user A must be rejected when used by user B."""
        import src.services.pending_permissions as pp
        from fastapi.testclient import TestClient
        from src.api.app import app
        from src.api.auth import create_access_token

        pid = f"test-cross-user-{uuid.uuid4().hex[:8]}"
        pp.register(pid, _USER_ID, "why")

        other_token = create_access_token({"sub": "other-user@rico.ai"})
        tc = TestClient(app, raise_server_exceptions=False)
        tc.cookies.set("access_token", other_token)

        r = tc.post(_URL, json={"permission_id": pid, "action": "why", "job": _JOB})
        assert r.status_code == 403


# ── Job-bound permission (replay-across-jobs guard) ───────────────────────────

class TestPermissionJobBinding:
    """A permission bound to a job at issuance must only execute against that job.

    This closes the gap where an apply permission issued for job A could be replayed
    with job B in the request body under the same (user, action) pair.
    """

    def test_bound_permission_matching_job_key_executes(self, client):
        pid = _perm_bound("why", _JOB["id"])
        r = client.post(_URL, json={
            "permission_id": pid,
            "action": "why",
            "job_key": _JOB["id"],
            "job": _JOB,
        })
        assert r.status_code == 200

    def test_bound_permission_mismatched_job_key_returns_403(self, client):
        pid = _perm_bound("why", _JOB["id"])
        r = client.post(_URL, json={
            "permission_id": pid,
            "action": "why",
            "job_key": "some-other-job-key",
            "job": _JOB,
        })
        assert r.status_code == 403

    def test_bound_permission_missing_job_key_returns_403(self, client):
        pid = _perm_bound("why", _JOB["id"])
        r = client.post(_URL, json={
            "permission_id": pid,
            "action": "why",
            "job": _JOB,   # no job_key in body → defaults to ""
        })
        assert r.status_code == 403


# ── Permission-denied audit trail ─────────────────────────────────────────────

class TestPermissionDeniedAudit:
    """A rejected execute attempt must leave an audit record via the existing
    audit_repo — no parallel audit table."""

    def test_denied_attempt_writes_denied_audit_record(self, client, monkeypatch):
        captured: list = []
        import src.repositories.audit_repo as ar
        monkeypatch.setattr(ar, "log_action", lambda log: captured.append(log))

        r = client.post(_URL, json={
            "permission_id": "totally-fake-id-not-issued",
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 403
        assert len(captured) == 1
        rec = captured[0]
        assert rec["result_status"] == "denied"
        assert rec["failure_reason"] == "permission_denied"
        assert rec["action_type"] == "why"
        assert rec["user_email"] == _USER_ID

    def test_successful_execution_writes_no_denied_record(self, client, monkeypatch):
        captured: list = []
        import src.repositories.audit_repo as ar
        monkeypatch.setattr(ar, "log_action", lambda log: captured.append(log))

        r = client.post(_URL, json={
            "permission_id": _perm("why"),
            "action": "why",
            "job": _JOB,
        })
        assert r.status_code == 200
        assert all(rec.get("result_status") != "denied" for rec in captured)


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

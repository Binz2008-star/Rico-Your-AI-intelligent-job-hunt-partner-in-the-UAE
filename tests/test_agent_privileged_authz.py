"""
Privileged agent-tool authorization (#1093 P0).

The global pipeline (and any PRIVILEGED_TOOLS) must never execute for a non-admin
actor on ANY surface: the /actions/run action path, the /agent/chat direct-action
path, or the /agent/chat NL-detected-intent path. Only an admin JWT may run them.
The admin HTTP /pipeline/trigger route (require_admin) is unaffected.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


def _client(role: str | None = None):
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    claims: dict = {"sub": "priv-test@example.com"}
    if role:
        claims["role"] = role
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", create_access_token(claims))
    return tc


@pytest.fixture(autouse=True)
def _reset_limiter():
    from src.api.rate_limit import limiter

    limiter.reset()
    yield


class TestPrivilegedToolAuthzDenied:
    """A normal user must never start the global pipeline via any agent surface."""

    def test_nonadmin_agent_chat_action_denied(self):
        c = _client(role=None)
        with patch("src.services.pipeline_service.trigger") as mock_trigger:
            r = c.post("/api/v1/agent/chat", json={
                "message": "run now",
                "action": {"type": "trigger_pipeline", "label": "Trigger"},
            })
        assert r.status_code == 200
        assert r.json()["success"] is False
        mock_trigger.assert_not_called()

    def test_nonadmin_agent_chat_nl_intent_denied(self):
        c = _client(role=None)
        with patch("src.services.pipeline_service.trigger") as mock_trigger:
            r = c.post("/api/v1/agent/chat", json={"message": "trigger the pipeline"})
        assert r.status_code == 200
        assert r.json()["success"] is False
        mock_trigger.assert_not_called()

    def test_nonadmin_actions_run_denied(self):
        c = _client(role=None)
        with patch("src.services.pipeline_service.trigger") as mock_trigger:
            r = c.post("/api/v1/actions/run", json={"action": "trigger_pipeline"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body.get("error") == "admin_required"
        mock_trigger.assert_not_called()

    def test_runtime_defaults_fail_closed(self):
        # A direct runtime call that omits actor_is_admin defaults to non-admin.
        from src.agent.runtime import agent_runtime

        with patch("src.services.pipeline_service.trigger") as mock_trigger:
            result = agent_runtime.handle_action(user_id="x@example.com", action="trigger_pipeline")
        assert result.ok is False
        assert result.error == "admin_required"
        mock_trigger.assert_not_called()


class TestPrivilegedToolAuthzAllowed:
    """An admin actor may run privileged tools; non-privileged actions are unaffected."""

    def test_admin_agent_chat_action_allowed(self):
        c = _client(role="admin")
        with patch("src.services.pipeline_service.trigger", return_value=None) as mock_trigger:
            r = c.post("/api/v1/agent/chat", json={
                "message": "run now",
                "action": {"type": "trigger_pipeline", "label": "Trigger"},
            })
        assert r.status_code == 200
        assert r.json()["success"] is True
        mock_trigger.assert_called_once()

    def test_admin_actions_run_allowed(self):
        c = _client(role="admin")
        with patch("src.services.pipeline_service.trigger", return_value=None) as mock_trigger:
            r = c.post("/api/v1/actions/run", json={"action": "trigger_pipeline"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        mock_trigger.assert_called_once()

    def test_nonadmin_nonprivileged_action_unaffected(self):
        # A non-privileged action (dry-run save) still works for a normal user.
        c = _client(role=None)
        r = c.post("/api/v1/actions/run", json={"action": "save", "job_key": "k", "dry_run": True})
        assert r.status_code == 200
        assert r.json()["ok"] is True

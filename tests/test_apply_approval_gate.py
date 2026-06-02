"""
Tests for the application-submission approval gate (C4).

Bug: RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS was surfaced in the health report but never
enforced in code — the only thing stopping Rico from auto-submitting applications was two
feature flags being off (RICO_ENABLE_AUTO_APPLY / NG_ENABLED). apply_to_job() is the single
chokepoint for real submission.

Fix: apply_to_job blocks (returns "approval_required") unless the caller passes an explicit
approved=True. Only the authenticated, per-job apply route opts in; agent/automation paths
leave approved=False and therefore can never auto-submit on the user's behalf.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


@pytest.fixture(autouse=True)
def _approval_on(monkeypatch):
    """Default these tests to approval-required; individual tests override where needed."""
    monkeypatch.setenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", "true")


# ── Chokepoint: apply_to_job ─────────────────────────────────────────────────

def test_apply_blocked_without_approval():
    from src.services.apply_service import apply_to_job
    with patch("src.services.apply_service._apply_naukrigulf") as engine:
        res = apply_to_job({"link": "https://naukrigulf.com/job1", "title": "X"})
    assert res["status"] == "approval_required"
    engine.assert_not_called()  # never reaches the real submission engine


def test_apply_proceeds_with_explicit_approval():
    from src.services.apply_service import apply_to_job
    # An unsupported source proves we got PAST the gate (the gate would have returned
    # "approval_required" before any source routing).
    res = apply_to_job({"link": "https://unknown-board.com/job", "title": "X"}, approved=True)
    assert res["status"] == "unsupported"


def test_apply_proceeds_when_approval_disabled(monkeypatch):
    monkeypatch.setenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", "false")
    from src.services.apply_service import apply_to_job
    res = apply_to_job({"link": "https://unknown-board.com/job", "title": "X"})  # not approved
    assert res["status"] == "unsupported"


def test_default_is_safe_when_env_unset(monkeypatch):
    """A missing/blank env var must NOT enable auto-submit — default is approval-required."""
    monkeypatch.delenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", raising=False)
    from src.services.apply_service import apply_to_job
    res = apply_to_job({"link": "https://naukrigulf.com/job1", "title": "X"})
    assert res["status"] == "approval_required"


def test_missing_link_still_validated_when_approved():
    from src.services.apply_service import apply_to_job
    res = apply_to_job({"title": "X"}, approved=True)
    assert res["status"] == "error"
    assert "link" in res["message"].lower()


# ── Agent runtime path must be gated ─────────────────────────────────────────

def test_agent_apply_tool_is_gated():
    """The agent apply tool must not auto-submit; it surfaces approval_required."""
    from src.agent.tools.job_tools import apply_job
    res = apply_job({"link": "https://naukrigulf.com/job1", "title": "X"})
    assert res.success is True            # the tool wrapper itself succeeds
    assert res.data["status"] == "approval_required"   # but submission is gated


# ── Authenticated per-job route opts in ──────────────────────────────────────

def test_jobs_apply_route_passes_approved():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", create_access_token({"sub": "alice@rico.ai", "role": "user"}))

    with patch("src.api.routers.jobs.apply_to_job", return_value={"status": "applied", "message": "ok"}) as mock_apply, \
         patch("src.api.routers.jobs._resolve_action_job",
               return_value={"title": "X", "company": "Y", "link": "https://x.com/j"}):
        r = tc.post(
            "/api/v1/jobs/abc123/apply",
            json={"job": {"title": "X", "link": "https://x.com/j"}},
        )

    assert r.status_code == 200, r.text
    # The explicit user route must opt in to approval.
    assert mock_apply.call_args.kwargs.get("approved") is True

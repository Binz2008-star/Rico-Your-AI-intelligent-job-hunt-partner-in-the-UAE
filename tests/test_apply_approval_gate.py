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
    # The gate was passed — result must not be "approval_required"
    res = apply_to_job({"link": "https://unknown-board.com/job", "title": "X"}, approved=True)
    assert res["status"] != "approval_required"


def test_apply_proceeds_when_approval_disabled(monkeypatch):
    monkeypatch.setenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", "false")
    from src.services.apply_service import apply_to_job
    res = apply_to_job({"link": "https://unknown-board.com/job", "title": "X"})  # not approved
    assert res["status"] != "approval_required"


def test_default_is_safe_when_env_unset(monkeypatch):
    """A missing/blank env var must NOT enable auto-submit — default is approval-required."""
    monkeypatch.delenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", raising=False)
    from src.services.apply_service import apply_to_job
    res = apply_to_job({"link": "https://naukrigulf.com/job1", "title": "X"})
    assert res["status"] == "approval_required"


def test_missing_link_still_validated_when_approved(monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_AUTO_APPLY", "true")
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


# ── Scheduled pipeline path must honor the same approval contract ────────────

class TestScheduledAutoApplyApprovalGate:
    """run_daily._auto_apply_naukrigulf calls the NaukriGulf engine DIRECTLY,
    not through apply_to_job(), so the approval chokepoint above never sees it.
    The scheduled pipeline has no user in the loop and can never collect the
    per-application approval RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS demands —
    so while approval is required (the default), the scheduled path must not
    submit. Autonomous scheduled submission requires the owner's explicit
    double opt-in: RICO_ENABLE_AUTO_APPLY=true AND
    RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=false.
    """

    def _run_scheduled_apply(self, monkeypatch, *, flag_on: bool, approval: str | None):
        import src.run_daily as rd

        # The flag is read at module import; patch the module constant the
        # function actually consults.
        monkeypatch.setattr(rd, "RICO_ENABLE_AUTO_APPLY", flag_on)
        if approval is None:
            monkeypatch.delenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", raising=False)
        else:
            monkeypatch.setenv("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", approval)

        with patch("src.naukrigulf_apply.run_naukrigulf_apply", return_value=[]) as engine, \
             patch.object(rd, "get_applied_jobs_count", return_value=0):
            rd._auto_apply_naukrigulf([])
        return engine

    def test_scheduled_apply_blocked_while_approval_required(self, monkeypatch):
        """Flag on + approval required (explicit true) → engine never runs."""
        engine = self._run_scheduled_apply(monkeypatch, flag_on=True, approval="true")
        engine.assert_not_called()

    def test_scheduled_apply_blocked_by_default_when_env_unset(self, monkeypatch):
        """Flag on + approval env missing → default is approval-required → no submit."""
        engine = self._run_scheduled_apply(monkeypatch, flag_on=True, approval=None)
        engine.assert_not_called()

    def test_scheduled_apply_runs_only_with_double_opt_in(self, monkeypatch):
        """Owner explicitly set BOTH flags → the autonomous engine may run."""
        engine = self._run_scheduled_apply(monkeypatch, flag_on=True, approval="false")
        engine.assert_called_once()

    def test_scheduled_apply_skipped_when_flag_off(self, monkeypatch):
        """Approval disabled but auto-apply flag off → still no engine run."""
        engine = self._run_scheduled_apply(monkeypatch, flag_on=False, approval="false")
        engine.assert_not_called()

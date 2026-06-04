"""
tests/test_apply_subscription_gate.py

Tests for the Premium subscription gate on automated apply (PR #420).

Covers:
- apply_to_job() returns manual_required when RICO_ENABLE_AUTO_APPLY=false (all plans)
- apply_to_job() raises HTTP 402 for Free/Pro when global flag is on
- apply_to_job() proceeds for Premium when global flag is on
- handle_action("apply") returns RuntimeResult(ok=False, error="subscription_limit")
  for Free/Pro via the agent/Telegram path, with a clean user-facing message
- handle_action("apply") message field is the human-readable upgrade prompt,
  NOT a raw HTTPException repr
- Non-apply actions (save/skip/block) are not affected by the subscription gate
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_resolved(enabled: bool):
    """Build a minimal resolve_effective_user_plan() return value."""
    entitlements = MagicMock()
    entitlements.application_automation_enabled = enabled
    plan = MagicMock()
    plan.value = "free" if not enabled else "premium"
    subscription = MagicMock()
    subscription.entitlements = entitlements
    subscription.plan = plan
    resolved = MagicMock()
    resolved.subscription = subscription
    return resolved


JOB = {"link": "https://naukrigulf.com/hse-1", "title": "HSE Manager", "company": "Acme"}


# ── apply_to_job: global flag off ────────────────────────────────────────────

class TestGlobalFlagOff:

    def setup_method(self):
        os.environ["RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS"] = "false"
        os.environ["RICO_ENABLE_AUTO_APPLY"] = "false"

    def teardown_method(self):
        os.environ.pop("RICO_ENABLE_AUTO_APPLY", None)
        os.environ.pop("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", None)

    def test_returns_manual_required_for_any_user(self):
        from src.services.apply_service import apply_to_job
        with patch("src.subscription_plans.resolve_effective_user_plan") as mock_plan:
            result = apply_to_job(JOB, approved=True, user_id="user-free")
        mock_plan.assert_not_called()  # subscription check never reached
        assert result["status"] == "manual_required"

    def test_no_upgrade_prompt_when_feature_cannot_run(self):
        from src.services.apply_service import apply_to_job
        result = apply_to_job(JOB, approved=True, user_id="user-free")
        # Must not return HTTP 402 detail when global flag is off
        assert result.get("status") != "subscription_limit"
        assert "402" not in str(result)


# ── apply_to_job: global flag on, subscription check ─────────────────────────

class TestSubscriptionCheck:

    def setup_method(self):
        os.environ["RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS"] = "false"
        os.environ["RICO_ENABLE_AUTO_APPLY"] = "true"

    def teardown_method(self):
        os.environ.pop("RICO_ENABLE_AUTO_APPLY", None)
        os.environ.pop("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", None)

    def test_free_user_raises_402(self):
        from src.services.apply_service import apply_to_job
        with patch("src.subscription_plans.resolve_effective_user_plan",
                   return_value=_make_resolved(False)):
            with pytest.raises(HTTPException) as exc_info:
                apply_to_job(JOB, approved=True, user_id="user-free")
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["feature"] == "application_automation"
        assert exc_info.value.detail["type"] == "subscription_limit"

    def test_pro_user_raises_402(self):
        from src.services.apply_service import apply_to_job
        resolved = _make_resolved(False)
        resolved.subscription.plan.value = "pro"
        with patch("src.subscription_plans.resolve_effective_user_plan",
                   return_value=resolved):
            with pytest.raises(HTTPException) as exc_info:
                apply_to_job(JOB, approved=True, user_id="user-pro")
        assert exc_info.value.status_code == 402

    def test_premium_user_reaches_engine(self):
        from src.services.apply_service import apply_to_job
        with patch("src.subscription_plans.resolve_effective_user_plan",
                   return_value=_make_resolved(True)):
            with patch("src.services.apply_service._apply_naukrigulf",
                       return_value={"status": "submitted", "message": "ok"}) as engine:
                result = apply_to_job(JOB, approved=True, user_id="user-premium")
        engine.assert_called_once()
        assert result["status"] == "submitted"

    def test_no_user_id_skips_subscription_check(self):
        """user_id=None (anonymous/legacy callers) bypasses subscription gate."""
        from src.services.apply_service import apply_to_job
        with patch("src.subscription_plans.resolve_effective_user_plan") as mock_plan:
            with patch("src.services.apply_service._apply_naukrigulf",
                       return_value={"status": "submitted", "message": "ok"}):
                apply_to_job(JOB, approved=True, user_id=None)
        mock_plan.assert_not_called()


# ── runtime.py: handle_action("apply") agent/Telegram path ───────────────────

class TestRuntimeSubscriptionGate:

    def setup_method(self):
        os.environ["RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS"] = "false"
        os.environ["RICO_ENABLE_AUTO_APPLY"] = "true"

    def teardown_method(self):
        os.environ.pop("RICO_ENABLE_AUTO_APPLY", None)
        os.environ.pop("RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS", None)

    def _handle(self, user_plan_enabled: bool, action: str = "apply"):
        from src.agent import runtime as runtime_mod
        from src.agent.registry import tool_registry as reg_mod

        tool_def = MagicMock()
        tool_def.execute.return_value = MagicMock(success=True, data={})

        with patch.object(reg_mod, "get", return_value=tool_def):
            with patch("src.subscription_plans.resolve_effective_user_plan",
                       return_value=_make_resolved(user_plan_enabled)):
                result = runtime_mod.agent_runtime.handle_action(
                    action=action,
                    job_key="hse-manager::acme-corp",
                    user_id="user-test",
                    source="telegram",
                    job=JOB,
                )
        return result

    def test_free_user_returns_subscription_limit(self):
        result = self._handle(user_plan_enabled=False)
        assert result.ok is False
        assert result.error == "subscription_limit"

    def test_message_is_human_readable_not_http_repr(self):
        """RuntimeResult.message must be the upgrade prompt, not '402: {...}'."""
        result = self._handle(user_plan_enabled=False)
        assert "402" not in result.message
        assert "{" not in result.message  # no raw dict repr
        assert len(result.message) > 10  # not empty

    def test_message_contains_upgrade_guidance(self):
        result = self._handle(user_plan_enabled=False)
        msg_lower = result.message.lower()
        assert any(word in msg_lower for word in ["plan", "upgrade", "premium", "automated"])

    def test_save_action_not_gated(self):
        """save/skip/block must never hit the subscription check."""
        from src.agent import runtime as runtime_mod
        from src.agent.registry import tool_registry as reg_mod

        tool_def = MagicMock()
        tool_def.execute.return_value = MagicMock(success=True, data={})

        with patch.object(reg_mod, "get", return_value=tool_def):
            with patch("src.subscription_plans.resolve_effective_user_plan") as mock_plan:
                runtime_mod.agent_runtime.handle_action(
                    action="save",
                    job_key="hse-manager::acme-corp",
                    user_id="user-free",
                    source="web",
                    job=JOB,
                )
        mock_plan.assert_not_called()

"""Tests for Rico's autonomous AI loop system.

Covers:
  - Journey state machine (derive_state, generate_daily_plan, transitions)
  - Auto-save service (score threshold, dedup, rate limit, exclusions)
  - Autonomous draft service (budget, dry-run, error handling)
  - Autonomous notification composer (formatting, HTML escaping)
  - Autonomous loop engine (mode gating, dry-run, skip conditions)
  - Safety guardrails (autonomous action allow/block list)
  - Background task wrappers (rico_tasks autonomous functions)

No live API calls, no DB writes, no Telegram sends.
All external dependencies are mocked.
"""
from __future__ import annotations

import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock


# ── Journey State Machine ────────────────────────────────────────────────────


class TestJourneyState:
    def test_discovery_state(self):
        from src.agent.context.journey_state import derive_state
        state = derive_state(user_id="u1", saved_count=0, applied_count=0, interviewing_count=0)
        assert state.state == "discovery"

    def test_searching_state(self):
        from src.agent.context.journey_state import derive_state
        state = derive_state(user_id="u1", saved_count=5, applied_count=0, interviewing_count=0)
        assert state.state == "searching"

    def test_applying_state(self):
        from src.agent.context.journey_state import derive_state
        state = derive_state(user_id="u1", saved_count=5, applied_count=3, interviewing_count=0)
        assert state.state == "applying"

    def test_interviewing_state(self):
        from src.agent.context.journey_state import derive_state
        state = derive_state(user_id="u1", saved_count=5, applied_count=3, interviewing_count=1)
        assert state.state == "interviewing"

    def test_valid_transitions(self):
        from src.agent.context.journey_state import is_valid_transition
        assert is_valid_transition("discovery", "searching")
        assert is_valid_transition("searching", "applying")
        assert is_valid_transition("applying", "interviewing")
        assert is_valid_transition("interviewing", "negotiating")
        assert is_valid_transition("negotiating", "offer")

    def test_invalid_transitions(self):
        from src.agent.context.journey_state import is_valid_transition
        assert not is_valid_transition("discovery", "interviewing")
        assert not is_valid_transition("offer", "discovery")

    def test_daily_plan_discovery(self):
        from src.agent.context.journey_state import derive_state, generate_daily_plan
        state = derive_state(user_id="u1")
        plan = generate_daily_plan("u1", state)
        assert len(plan.actions) >= 1
        assert plan.actions[0]["action"] == "search"

    def test_daily_plan_searching_with_matches(self):
        from src.agent.context.journey_state import derive_state, generate_daily_plan
        state = derive_state(user_id="u1", saved_count=5)
        plan = generate_daily_plan("u1", state, new_matches_count=3)
        assert any(a["action"] == "review_matches" for a in plan.actions)

    def test_daily_plan_applying_with_followups(self):
        from src.agent.context.journey_state import derive_state, generate_daily_plan
        state = derive_state(user_id="u1", saved_count=5, applied_count=3)
        plan = generate_daily_plan("u1", state, followups_due_count=2, drafts_ready_count=1)
        assert any(a["action"] == "follow_up" for a in plan.actions)
        assert any(a["action"] == "review_drafts" for a in plan.actions)

    def test_daily_plan_interviewing(self):
        from src.agent.context.journey_state import derive_state, generate_daily_plan
        state = derive_state(user_id="u1", applied_count=3, interviewing_count=1)
        plan = generate_daily_plan("u1", state)
        assert any(a["action"] == "interview_prep" for a in plan.actions)

    def test_daily_plan_empty_fallback(self):
        from src.agent.context.journey_state import JourneyState, generate_daily_plan
        state = JourneyState(user_id="u1", state="offer")
        plan = generate_daily_plan("u1", state, new_matches_count=0, followups_due_count=0, drafts_ready_count=0)
        assert len(plan.actions) == 1
        assert plan.actions[0]["action"] == "check_in"


# ── Auto-Save Service ────────────────────────────────────────────────────────


class TestAutoSaveService:
    def test_save_high_score_job(self):
        from src.services.auto_save_service import auto_save_jobs
        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}]
        with patch("src.services.auto_save_service.create_application" if False else "src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            result = auto_save_jobs("u1", jobs, existing_job_keys=set())
            assert result.saved_count == 1

    def test_skip_low_score_job(self):
        from src.services.auto_save_service import auto_save_jobs
        jobs = [{"title": "Junior Role", "company": "Corp", "score": 50, "link": "https://example.com/2"}]
        result = auto_save_jobs("u1", jobs, existing_job_keys=set(), dry_run=True)
        assert result.saved_count == 0
        assert result.skipped_count == 1

    def test_skip_already_saved(self):
        from src.services.auto_save_service import auto_save_jobs, _get_job_key
        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        job_key = _get_job_key(job)
        result = auto_save_jobs("u1", [job], existing_job_keys={job_key}, dry_run=True)
        assert result.saved_count == 0
        assert result.skipped_count == 1

    def test_daily_limit_enforced(self):
        from src.services.auto_save_service import auto_save_jobs
        jobs = [{"title": f"Role {i}", "company": "Corp", "score": 80, "link": f"https://example.com/{i}"} for i in range(5)]
        result = auto_save_jobs("u1", jobs, existing_job_keys=set(), daily_save_count=10, dry_run=True)
        assert result.saved_count == 0

    def test_exclusion_keywords(self, monkeypatch):
        monkeypatch.setenv("EXCLUDE_KEYWORDS", "scam,fake")
        from src.services.auto_save_service import auto_save_jobs
        jobs = [{"title": "Scam Job", "company": "Fake Corp", "score": 90, "link": "https://example.com/scam"}]
        result = auto_save_jobs("u1", jobs, existing_job_keys=set(), dry_run=True)
        assert result.saved_count == 0
        assert result.skipped_count == 1

    def test_dry_run_no_saves(self):
        from src.services.auto_save_service import auto_save_jobs
        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}]
        result = auto_save_jobs("u1", jobs, existing_job_keys=set(), dry_run=True)
        assert result.saved_count == 1
        assert result.saved[0].get("dry_run") is True

    def test_minimum_threshold_enforced(self, monkeypatch):
        monkeypatch.setenv("RICO_AUTONOMOUS_AUTO_SAVE_THRESHOLD", "50")
        from src.services.auto_save_service import _get_score_threshold
        assert _get_score_threshold() == 70  # minimum floor


# ── Autonomous Draft Service ─────────────────────────────────────────────────


class TestAutonomousDraftService:
    def test_dry_run_draft(self):
        from src.services.autonomous_draft_service import generate_drafts_for_jobs
        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        result = generate_drafts_for_jobs("u1", jobs, dry_run=True)
        assert result.draft_count == 1
        assert result.drafts[0]["dry_run"] is True

    def test_draft_budget_enforced(self):
        from src.services.autonomous_draft_service import generate_drafts_for_jobs
        jobs = [{"title": f"Role {i}", "company": "Corp", "score": 85} for i in range(5)]
        result = generate_drafts_for_jobs("u1", jobs, daily_draft_count=3, dry_run=True)
        assert result.draft_count == 0

    def test_draft_generation_with_mock(self):
        from src.services.autonomous_draft_service import generate_drafts_for_jobs
        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", return_value="Dear Hiring Manager, ..."):
            result = generate_drafts_for_jobs("u1", jobs, dry_run=False)
        assert result.draft_count == 1
        assert "Dear Hiring Manager" in result.drafts[0]["draft"]

    def test_draft_empty_message_skipped(self):
        from src.services.autonomous_draft_service import generate_drafts_for_jobs
        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", return_value=""):
            result = generate_drafts_for_jobs("u1", jobs, dry_run=False)
        assert result.draft_count == 0

    def test_draft_error_handled(self):
        from src.services.autonomous_draft_service import generate_drafts_for_jobs
        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", side_effect=Exception("API down")):
            result = generate_drafts_for_jobs("u1", jobs, dry_run=False)
        assert result.draft_count == 0
        assert len(result.errors) == 1


# ── Autonomous Notification Composer ──────────────────────────────────────────


class TestAutonomousNotifications:
    def test_daily_digest_with_saves(self):
        from src.agent.responses.autonomous_notifications import format_daily_digest
        saved = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        msg = format_daily_digest("Roben", saved, new_matches_count=5, drafts_ready_count=2, followups_due_count=1)
        assert "Roben" in msg
        assert "HSE Manager" in msg
        assert "ADNOC" in msg
        assert "5" in msg
        assert "2" in msg
        assert "1" in msg

    def test_daily_digest_empty(self):
        from src.agent.responses.autonomous_notifications import format_daily_digest
        msg = format_daily_digest("Roben", [])
        assert "No new matches" in msg

    def test_high_match_alert(self):
        from src.agent.responses.autonomous_notifications import format_high_match_alert
        job = {"title": "Safety Manager", "company": "Gulf Corp", "score": 92, "location": "Dubai", "link": "https://example.com"}
        msg = format_high_match_alert(job)
        assert "Safety Manager" in msg
        assert "Gulf Corp" in msg
        assert "92" in msg
        assert "Dubai" in msg

    def test_followup_reminder(self):
        from src.agent.responses.autonomous_notifications import format_followup_reminder
        msg = format_followup_reminder("HSE Manager", "ADNOC", 14, draft_preview="Dear Recruiter, ...")
        assert "HSE Manager" in msg
        assert "ADNOC" in msg
        assert "14" in msg
        assert "Dear Recruiter" in msg

    def test_followup_reminder_no_draft(self):
        from src.agent.responses.autonomous_notifications import format_followup_reminder
        msg = format_followup_reminder("HSE Manager", "ADNOC", 14)
        assert "draft a follow-up" in msg.lower()

    def test_daily_plan_format(self):
        from src.agent.responses.autonomous_notifications import format_daily_plan
        actions = [{"action": "search", "message": "Find jobs", "priority": "high"}]
        msg = format_daily_plan("Roben", "searching", actions)
        assert "Roben" in msg
        assert "searching" in msg
        assert "Find jobs" in msg

    def test_html_escaping(self):
        from src.agent.responses.autonomous_notifications import format_daily_digest
        saved = [{"title": "<script>alert(1)</script>", "company": "Corp", "score": 85}]
        msg = format_daily_digest("Roben", saved)
        assert "<script>" not in msg
        assert "&lt;script&gt;" in msg


# ── Safety Guardrails ────────────────────────────────────────────────────────


class TestAutonomousSafety:
    def test_apply_blocked_in_autonomous(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("apply")
        assert not result.allowed
        assert "high" in result.severity

    def test_save_allowed_in_autonomous(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("save")
        assert result.allowed

    def test_draft_allowed_in_autonomous(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("draft")
        assert result.allowed

    def test_block_blocked_in_autonomous(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("block")
        assert not result.allowed

    def test_send_recruiter_message_blocked(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("send_recruiter_message")
        assert not result.allowed

    def test_share_cv_blocked(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("share_cv")
        assert not result.allowed

    def test_unknown_action_blocked(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("delete_everything")
        assert not result.allowed

    def test_skip_allowed(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("skip")
        assert result.allowed

    def test_remind_allowed(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("remind")
        assert result.allowed


# ── Autonomous Loop Engine ───────────────────────────────────────────────────


class TestAutonomousLoop:
    def test_mode_disabled_skips(self):
        from src.agent.autonomous_loop import run_for_user
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=False):
            result = run_for_user("u1")
        assert result.skipped
        assert result.skip_reason == "autonomous_mode_disabled"

    def test_dry_run_no_side_effects(self):
        from src.agent.autonomous_loop import run_for_user
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            result = run_for_user("u1", dry_run=True, scored_jobs=[({"title": "Test", "company": "Corp", "link": "https://x.com"}, 85)])
        assert result.new_matches_count == 1
        assert result.telegram_sent is False

    def test_run_for_all_users_mode_disabled(self):
        from src.agent.autonomous_loop import run_for_all_users
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=False):
            results = run_for_all_users()
        assert results == []

    def test_run_for_all_users_no_users(self):
        from src.agent.autonomous_loop import run_for_all_users
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.repositories.profile_repo.get_users_with_telegram_alerts", return_value=[]):
                results = run_for_all_users()
        assert results == []

    def test_run_for_all_users_with_mock_users(self):
        from src.agent.autonomous_loop import run_for_all_users
        mock_users = [{"external_user_id": "u1", "telegram_chat_id": "123", "name": "User 1"}]
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.repositories.profile_repo.get_users_with_telegram_alerts", return_value=mock_users):
                with patch("src.agent.autonomous_loop.run_for_user") as mock_run:
                    mock_run.return_value = MagicMock(saved_jobs=[], drafts=[], followups_due=[], to_dict=lambda: {})
                    results = run_for_all_users(dry_run=True)
        assert len(results) == 1

    def test_high_match_threshold_constant(self):
        from src.agent.autonomous_loop import HIGH_MATCH_ALERT_THRESHOLD
        assert HIGH_MATCH_ALERT_THRESHOLD == 90


# ── Background Task Wrappers ─────────────────────────────────────────────────


class TestAutonomousTasks:
    def test_run_autonomous_loop_task_mode_disabled(self):
        from src.rico_tasks import run_autonomous_loop_task
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=False):
            with patch("src.agent.autonomous_loop.run_for_all_users", return_value=[]):
                result = run_autonomous_loop_task()
        assert result["task"] == "run_autonomous_loop"
        assert result["users_processed"] == 0

    def test_run_autonomous_loop_for_user_task(self):
        from src.rico_tasks import run_autonomous_loop_for_user_task
        with patch("src.agent.autonomous_loop.run_for_user") as mock_run:
            mock_result = MagicMock()
            mock_result.to_dict.return_value = {"user_id": "u1", "saved_count": 0}
            mock_run.return_value = mock_result
            result = run_autonomous_loop_for_user_task("u1", dry_run=True)
        assert result["task"] == "run_autonomous_loop_for_user"
        assert result["result"]["user_id"] == "u1"


# ── Run Daily Integration ────────────────────────────────────────────────────


class TestRunDailyIntegration:
    def test_run_autonomous_loop_function_exists(self):
        from src.run_daily import _run_autonomous_loop
        assert callable(_run_autonomous_loop)

    def test_run_autonomous_loop_skipped_when_disabled(self):
        from src.run_daily import _run_autonomous_loop
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=False):
            _run_autonomous_loop([])

    def test_run_autonomous_loop_called_with_matches(self):
        from src.run_daily import _run_autonomous_loop
        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop.run_for_all_users", return_value=[]) as mock_run:
                _run_autonomous_loop([({"title": "Test"}, 85)])
                mock_run.assert_called_once()

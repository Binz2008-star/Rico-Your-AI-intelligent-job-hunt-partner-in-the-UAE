"""Comprehensive audit tests for Rico's autonomous AI loop.

Covers all 12 required scenarios:
  1. Two different users (user isolation)
  2. Guest/public user rejection
  3. Complete and incomplete profiles
  4. Arabic and English input
  5. DB unavailable
  6. Concurrent duplicate runs
  7. Retry after partial failure
  8. Subscription limit reached
  9. Telegram opt-out
  10. Timezone/day-boundary behavior
  11. Draft grounding/no fabricated claims
  12. No sending or applying without explicit approval

No live API calls, no DB writes, no Telegram sends.
All external dependencies are mocked.
"""
from __future__ import annotations

import os
import threading
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, call


_UTC = timezone.utc


# ── 1. Two Different Users (User Isolation) ─────────────────────────────────


class TestUserIsolation:
    def test_two_users_get_separate_saves(self):
        """User A's saves must not appear in User B's pipeline."""
        from src.services.auto_save_service import auto_save_jobs, _get_job_key

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        job_key = _get_job_key(job)

        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            result_a = auto_save_jobs("user_a", [job], existing_job_keys=set())
            result_b = auto_save_jobs("user_b", [job], existing_job_keys=set())

        assert result_a.saved_count == 1
        assert result_b.saved_count == 1
        # Verify create was called with different user_ids
        assert mock_create.call_count == 2
        call_a = mock_create.call_args_list[0]
        call_b = mock_create.call_args_list[1]
        assert call_a.kwargs["user_id"] == "user_a"
        assert call_b.kwargs["user_id"] == "user_b"

    def test_user_a_existing_keys_do_not_block_user_b(self):
        """User A's job keys must not be checked against User B's pipeline."""
        from src.services.auto_save_service import auto_save_jobs, _get_job_key

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        job_key = _get_job_key(job)

        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            # User A already has this job
            result_a = auto_save_jobs("user_a", [job], existing_job_keys={job_key})
            # User B does not
            result_b = auto_save_jobs("user_b", [job], existing_job_keys=set())

        assert result_a.saved_count == 0  # already in A's pipeline
        assert result_b.saved_count == 1  # B can still save it

    def test_two_users_separate_loop_runs(self):
        """Running the loop for user_a must not affect user_b's state."""
        from src.agent.autonomous_loop import run_for_user
        import src.services.auto_save_service as auto_save_module

        scored = [({"title": "HSE Manager", "company": "ADNOC", "link": "https://example.com/1"}, 85)]

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", return_value=None):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", return_value=set()):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", return_value={"saved": 0, "applied": 0, "interview": 0}):
                        with patch.object(auto_save_module, "auto_save_jobs") as mock_save:
                            mock_save.return_value = MagicMock(saved=[], errors=[], skipped=[])
                            run_for_user("user_a", scored_jobs=scored, dry_run=False)
                            run_for_user("user_b", scored_jobs=scored, dry_run=False)

        # Verify auto_save was called with different user_ids
        user_ids = [c.kwargs.get("user_id", c.args[0] if c.args else "") for c in mock_save.call_args_list]
        assert "user_a" in user_ids
        assert "user_b" in user_ids


# ── 2. Guest/Public User Rejection ───────────────────────────────────────────


class TestGuestUserRejection:
    def test_empty_user_id_rejected(self):
        from src.services.auto_save_service import auto_save_jobs
        result = auto_save_jobs("", [{"title": "Test", "company": "Corp", "score": 90}])
        assert result.saved_count == 0
        assert "authenticated" in result.errors[0].lower()

    def test_anonymous_user_rejected(self):
        from src.services.auto_save_service import auto_save_jobs
        result = auto_save_jobs("anonymous", [{"title": "Test", "company": "Corp", "score": 90}])
        assert result.saved_count == 0
        assert "authenticated" in result.errors[0].lower()

    def test_guest_user_rejected(self):
        from src.services.auto_save_service import auto_save_jobs
        result = auto_save_jobs("guest", [{"title": "Test", "company": "Corp", "score": 90}])
        assert result.saved_count == 0
        assert "authenticated" in result.errors[0].lower()

    def test_public_user_rejected(self):
        from src.services.auto_save_service import auto_save_jobs
        result = auto_save_jobs("public", [{"title": "Test", "company": "Corp", "score": 90}])
        assert result.saved_count == 0
        assert "authenticated" in result.errors[0].lower()

    def test_public_prefix_colon_rejected(self):
        from src.services.auto_save_service import auto_save_jobs
        result = auto_save_jobs("public:someuser@example.com", [{"title": "Test", "company": "Corp", "score": 90}])
        assert result.saved_count == 0
        assert "authenticated" in result.errors[0].lower()

    def test_public_prefix_underscore_rejected(self):
        from src.services.auto_save_service import auto_save_jobs
        result = auto_save_jobs("public_someuser", [{"title": "Test", "company": "Corp", "score": 90}])
        assert result.saved_count == 0
        assert "authenticated" in result.errors[0].lower()

    def test_none_user_id_rejected(self):
        from src.services.auto_save_service import auto_save_jobs
        result = auto_save_jobs(None, [{"title": "Test", "company": "Corp", "score": 90}])
        assert result.saved_count == 0
        assert len(result.errors) >= 1


# ── 3. Complete and Incomplete Profiles ──────────────────────────────────────


class TestProfileCompleteness:
    def test_complete_profile_processes_jobs(self):
        from src.agent.autonomous_loop import run_for_user

        mock_profile = MagicMock()
        mock_profile.target_roles = ["HSE Manager", "Safety Officer"]
        mock_profile.preferred_cities = ["Dubai", "Abu Dhabi"]

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", return_value=mock_profile):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", return_value=set()):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", return_value={"saved": 0, "applied": 0, "interview": 0}):
                        with patch("src.services.auto_save_service.auto_save_jobs") as mock_save:
                            mock_save.return_value = MagicMock(saved=[], errors=[], to_dict=lambda: {})
                            result = run_for_user("u1", dry_run=True, scored_jobs=[({"title": "Test"}, 85)])
        assert result.new_matches_count == 1

    def test_incomplete_profile_still_runs(self):
        """Users without a profile should still get the loop — just with less personalization."""
        from src.agent.autonomous_loop import run_for_user

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", return_value=None):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", return_value=set()):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", return_value={"saved": 0, "applied": 0, "interview": 0}):
                        result = run_for_user("u1", dry_run=True, scored_jobs=[({"title": "Test"}, 85)])
        assert result.skipped is False
        assert result.new_matches_count == 1


# ── 4. Arabic and English ────────────────────────────────────────────────────


class TestArabicEnglish:
    def test_arabic_job_title_saved(self):
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "مدير السلامة", "company": "أدنوك", "score": 85, "link": "https://example.com/ar"}
        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            result = auto_save_jobs("u1", [job], existing_job_keys=set())
        assert result.saved_count == 1

    def test_english_job_title_saved(self):
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "Safety Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/en"}
        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            result = auto_save_jobs("u1", [job], existing_job_keys=set())
        assert result.saved_count == 1

    def test_arabic_notification_format(self):
        from src.agent.responses.autonomous_notifications import format_daily_digest

        saved = [{"title": "مدير السلامة", "company": "أدنوك", "score": 85}]
        msg = format_daily_digest("محمد", saved, new_matches_count=3)
        assert "محمد" in msg
        assert "مدير السلامة" in msg

    def test_mixed_arabic_english(self):
        from src.services.auto_save_service import auto_save_jobs

        jobs = [
            {"title": "Safety Manager", "company": "أدنوك", "score": 85, "link": "https://example.com/1"},
            {"title": "مدير السلامة", "company": "ADNOC", "score": 80, "link": "https://example.com/2"},
        ]
        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            result = auto_save_jobs("u1", jobs, existing_job_keys=set())
        assert result.saved_count == 2


# ── 5. DB Unavailable ────────────────────────────────────────────────────────


class TestDBUnavailable:
    def test_auto_save_db_error_captured(self):
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        with patch("src.repositories.applications_repo.create", side_effect=Exception("DB connection refused")):
            result = auto_save_jobs("u1", [job], existing_job_keys=set())
        assert result.saved_count == 0
        assert len(result.errors) == 1
        assert "DB connection refused" in result.errors[0]

    def test_loop_continues_on_db_error(self):
        """The loop must not crash when DB is unavailable."""
        from src.agent.autonomous_loop import run_for_user

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", side_effect=Exception("DB down")):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", side_effect=Exception("DB down")):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", side_effect=Exception("DB down")):
                        result = run_for_user("u1", dry_run=True)
        # Loop should not crash — errors captured
        assert result.skipped is False

    def test_recommendation_keys_empty_on_db_error(self):
        from src.agent.autonomous_loop import _get_user_recommendation_keys

        with patch("src.rico_db.RicoDB", side_effect=Exception("DB down")):
            keys = _get_user_recommendation_keys("u1")
        assert keys == set()


# ── 6. Concurrent Duplicate Runs ─────────────────────────────────────────────


class TestConcurrentDuplicates:
    def test_concurrent_same_job_not_double_saved(self):
        """Two threads saving the same job for the same user — only one should succeed."""
        from src.services.auto_save_service import auto_save_jobs, _get_job_key

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        shared_existing: set[str] = set()
        save_count = 0
        count_lock = threading.Lock()

        def mock_create_fn(**kwargs):
            nonlocal save_count
            with count_lock:
                save_count += 1
            return True

        def run_save():
            return auto_save_jobs("u1", [job], existing_job_keys=shared_existing)

        with patch("src.repositories.applications_repo.create", side_effect=mock_create_fn):
            threads = []
            results = []

            def thread_target():
                r = run_save()
                results.append(r)

            for _ in range(5):
                t = threading.Thread(target=thread_target)
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

        # Only one thread should have actually called create_application
        successful = sum(1 for r in results if r.saved_count > 0)
        assert successful == 1, f"Expected 1 successful save, got {successful}"

    def test_retry_after_save_is_idempotent(self):
        """Running auto_save twice with the same job — second run skips as duplicate."""
        from src.services.auto_save_service import auto_save_jobs, _get_job_key

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        job_key = _get_job_key(job)
        existing: set[str] = set()

        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            first = auto_save_jobs("u1", [job], existing_job_keys=existing)
            # Simulate the first save adding the key
            existing.add(job_key)
            second = auto_save_jobs("u1", [job], existing_job_keys=existing)

        assert first.saved_count == 1
        assert second.saved_count == 0
        assert second.skipped_count == 1
        assert "already_in_pipeline" in second.skipped[0]["reason"]


# ── 7. Retry After Partial Failure ───────────────────────────────────────────


class TestRetryAfterFailure:
    def test_partial_failure_then_retry_succeeds(self):
        """If the first job fails but the second succeeds, retrying the first should work."""
        from src.services.auto_save_service import auto_save_jobs

        job1 = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        job2 = {"title": "Safety Officer", "company": "Gulf Corp", "score": 80, "link": "https://example.com/2"}

        call_count = 0
        def mock_create_fn(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient DB error")
            return True

        with patch("src.repositories.applications_repo.create", side_effect=mock_create_fn):
            first_run = auto_save_jobs("u1", [job1, job2], existing_job_keys=set())
            # job1 failed, job2 succeeded
            assert first_run.saved_count == 1
            assert len(first_run.errors) == 1

            # Retry — job1 should now succeed
            second_run = auto_save_jobs("u1", [job1], existing_job_keys=set())
            assert second_run.saved_count == 1

    def test_all_failures_captured(self):
        from src.services.auto_save_service import auto_save_jobs

        jobs = [
            {"title": f"Role {i}", "company": "Corp", "score": 85, "link": f"https://example.com/{i}"}
            for i in range(3)
        ]
        with patch("src.repositories.applications_repo.create", side_effect=Exception("DB down")):
            result = auto_save_jobs("u1", jobs, existing_job_keys=set())
        assert result.saved_count == 0
        assert len(result.errors) == 3


# ── 8. Subscription Limit Reached ────────────────────────────────────────────


class TestSubscriptionLimit:
    def test_subscription_limit_blocks_save(self):
        """When enforce_saved_job_allowed raises HTTP 402, the save is blocked."""
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}

        # Simulate the subscription gate raising HTTP 402
        from fastapi import HTTPException

        with patch("src.repositories.applications_repo.create", side_effect=HTTPException(status_code=402, detail="Limit reached")):
            result = auto_save_jobs("u1", [job], existing_job_keys=set())
        assert result.saved_count == 0
        assert len(result.errors) == 1
        assert "402" in result.errors[0] or "Limit" in result.errors[0]

    def test_subscription_limit_error_audit_logged(self):
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        from fastapi import HTTPException

        with patch("src.repositories.applications_repo.create", side_effect=HTTPException(status_code=402, detail="Limit reached")):
            with patch("src.repositories.audit_repo.log_action") as mock_log:
                auto_save_jobs("u1", [job], existing_job_keys=set())
        # Verify failure was audit logged
        mock_log.assert_called()
        log_entry = mock_log.call_args[0][0]
        assert log_entry["result_status"] == "failure"


# ── 9. Telegram Opt-Out ──────────────────────────────────────────────────────


class TestTelegramOptOut:
    def test_no_telegram_when_chat_id_empty(self):
        from src.agent.autonomous_loop import run_for_user

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", return_value=None):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", return_value=set()):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", return_value={"saved": 0, "applied": 0, "interview": 0}):
                        with patch("src.telegram_bot.send_telegram_to_user") as mock_send:
                            result = run_for_user("u1", telegram_chat_id="", dry_run=False)
        assert result.telegram_sent is False
        mock_send.assert_not_called()

    def test_skip_telegram_flag_prevents_send(self):
        from src.agent.autonomous_loop import run_for_user

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", return_value=None):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", return_value=set()):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", return_value={"saved": 0, "applied": 0, "interview": 0}):
                        with patch("src.telegram_bot.send_telegram_to_user") as mock_send:
                            result = run_for_user("u1", telegram_chat_id="123", dry_run=False, skip_telegram=True)
        assert result.telegram_sent is False
        mock_send.assert_not_called()

    def test_telegram_sent_when_enabled(self):
        from src.agent.autonomous_loop import run_for_user

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", return_value=None):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", return_value=set()):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", return_value={"saved": 0, "applied": 0, "interview": 0}):
                        with patch("src.services.auto_save_service.auto_save_jobs", return_value=MagicMock(saved=[], errors=[])):
                            with patch("src.telegram_bot.send_telegram_to_user", return_value=True):
                                result = run_for_user("u1", telegram_chat_id="123", dry_run=False, skip_telegram=False)
        assert result.telegram_sent is True

    def test_run_daily_skips_telegram_in_loop(self):
        """Verify run_daily passes skip_telegram=True to avoid duplicate notifications."""
        from src.run_daily import _run_autonomous_loop

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop.run_for_all_users") as mock_run:
                mock_run.return_value = []
                _run_autonomous_loop([])
                mock_run.assert_called_once()
                assert mock_run.call_args.kwargs.get("skip_telegram") is True


# ── 10. Timezone/Day-Boundary Behavior ───────────────────────────────────────


class TestTimezoneDayBoundary:
    def test_followup_cutoff_uses_utc(self):
        from src.agent.autonomous_loop import _check_followups

        now = datetime.now(_UTC)
        old_date = (now - timedelta(days=15)).isoformat()
        recent_date = (now - timedelta(days=5)).isoformat()

        apps = [
            {"title": "Old Job", "company": "Corp", "status": "applied", "date_applied": old_date},
            {"title": "Recent Job", "company": "Corp", "status": "applied", "date_applied": recent_date},
        ]
        due = _check_followups("u1", apps)
        assert len(due) == 1
        assert due[0]["title"] == "Old Job"

    def test_followup_exactly_at_boundary(self):
        from src.agent.autonomous_loop import _check_followups

        cutoff = datetime.now(_UTC) - timedelta(days=14)
        apps = [
            {"title": "Boundary Job", "company": "Corp", "status": "applied",
             "date_applied": cutoff.isoformat()},
        ]
        due = _check_followups("u1", apps)
        assert len(due) == 1

    def test_followup_naive_datetime_handled(self):
        """Naive datetimes (no tzinfo) should be treated as UTC."""
        from src.agent.autonomous_loop import _check_followups

        old_naive = (datetime.utcnow() - timedelta(days=20)).isoformat()
        apps = [
            {"title": "Naive Job", "company": "Corp", "status": "applied", "date_applied": old_naive},
        ]
        due = _check_followups("u1", apps)
        assert len(due) == 1

    def test_journey_state_timestamps_are_utc(self):
        from src.agent.context.journey_state import derive_state

        state = derive_state("u1", saved_count=5)
        assert state.entered_at.endswith("+00:00") or "Z" in state.entered_at


# ── 11. Draft Grounding/No Fabricated Claims ─────────────────────────────────


class TestDraftGrounding:
    def test_draft_uses_message_generator(self):
        """Drafts must come from message_generator, not fabricated."""
        from src.services.autonomous_draft_service import generate_drafts_for_jobs

        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", return_value="Dear Hiring Manager, I am writing to apply...") as mock_gen:
            result = generate_drafts_for_jobs("u1", jobs, dry_run=False)
        assert result.draft_count == 1
        mock_gen.assert_called_once()
        assert "Dear Hiring Manager" in result.drafts[0]["draft"]

    def test_draft_empty_string_not_stored(self):
        from src.services.autonomous_draft_service import generate_drafts_for_jobs

        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", return_value=""):
            result = generate_drafts_for_jobs("u1", jobs, dry_run=False)
        assert result.draft_count == 0

    def test_draft_whitespace_only_not_stored(self):
        from src.services.autonomous_draft_service import generate_drafts_for_jobs

        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", return_value="   \n  "):
            result = generate_drafts_for_jobs("u1", jobs, dry_run=False)
        assert result.draft_count == 0

    def test_draft_status_is_prepared_not_applied(self):
        """Drafts must be stored as 'prepared', never 'applied'."""
        from src.services.autonomous_draft_service import generate_drafts_for_jobs

        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", return_value="Dear Sir, ..."):
            result = generate_drafts_for_jobs("u1", jobs, dry_run=False)
        assert result.drafts[0]["status"] == "prepared"

    def test_draft_does_not_send(self):
        """Draft generation must never call any send/apply function."""
        from src.services.autonomous_draft_service import generate_drafts_for_jobs

        jobs = [{"title": "HSE Manager", "company": "ADNOC", "score": 85}]
        with patch("src.message_generator.generate_message", return_value="Dear Sir, ..."):
            with patch("src.telegram_bot.send_telegram_to_user") as mock_send:
                with patch("src.services.apply_service.apply_to_job") as mock_apply:
                    generate_drafts_for_jobs("u1", jobs, dry_run=False)
        mock_send.assert_not_called()
        mock_apply.assert_not_called()


# ── 12. No Sending or Applying Without Explicit Approval ─────────────────────


class TestNoApplyWithoutApproval:
    def test_auto_save_never_calls_apply(self):
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            with patch("src.services.apply_service.apply_to_job") as mock_apply:
                auto_save_jobs("u1", [job], existing_job_keys=set())
        mock_apply.assert_not_called()

    def test_autonomous_loop_never_calls_apply(self):
        from src.agent.autonomous_loop import run_for_user

        with patch("src.agent.autonomous_loop.is_autonomous_mode_enabled", return_value=True):
            with patch("src.agent.autonomous_loop._load_user_profile", return_value=None):
                with patch("src.agent.autonomous_loop._get_user_recommendation_keys", return_value=set()):
                    with patch("src.agent.autonomous_loop._get_user_application_counts", return_value={"saved": 0, "applied": 0, "interview": 0}):
                        with patch("src.services.apply_service.apply_to_job") as mock_apply:
                            with patch("src.services.auto_save_service.auto_save_jobs", return_value=MagicMock(saved=[], errors=[])):
                                run_for_user("u1", dry_run=False)
        mock_apply.assert_not_called()

    def test_safety_guard_blocks_apply_in_autonomous(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("apply")
        assert not result.allowed
        assert "high" in result.severity

    def test_safety_guard_blocks_send_recruiter_message(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("send_recruiter_message")
        assert not result.allowed

    def test_safety_guard_blocks_share_cv(self):
        from src.rico_safety import RicoSafetyGuard
        guard = RicoSafetyGuard()
        result = guard.check_autonomous_action("share_cv")
        assert not result.allowed

    def test_auto_save_writes_status_saved_only(self):
        """Verify create_application is called with status='saved', never 'applied'."""
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        with patch("src.repositories.applications_repo.create") as mock_create:
            mock_create.return_value = True
            auto_save_jobs("u1", [job], existing_job_keys=set())
        assert mock_create.call_args.kwargs["status"] == "saved"


# ── Audit Logging Coverage ───────────────────────────────────────────────────


class TestAuditLogging:
    def test_successful_save_is_audit_logged(self):
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        with patch("src.repositories.applications_repo.create", return_value=True):
            with patch("src.repositories.audit_repo.log_action") as mock_log:
                auto_save_jobs("u1", [job], existing_job_keys=set())
        mock_log.assert_called()
        log_entry = mock_log.call_args[0][0]
        assert log_entry["result_status"] == "success"
        assert log_entry["action_type"] == "save"

    def test_duplicate_save_is_audit_logged(self):
        from src.services.auto_save_service import auto_save_jobs, _get_job_key

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        job_key = _get_job_key(job)
        with patch("src.repositories.applications_repo.create") as mock_create:
            with patch("src.repositories.audit_repo.log_action") as mock_log:
                auto_save_jobs("u1", [job], existing_job_keys={job_key})
        mock_create.assert_not_called()
        mock_log.assert_called()
        log_entry = mock_log.call_args[0][0]
        assert log_entry["result_status"] == "duplicate"

    def test_failed_save_is_audit_logged(self):
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        with patch("src.repositories.applications_repo.create", side_effect=Exception("DB error")):
            with patch("src.repositories.audit_repo.log_action") as mock_log:
                auto_save_jobs("u1", [job], existing_job_keys=set())
        mock_log.assert_called()
        log_entry = mock_log.call_args[0][0]
        assert log_entry["result_status"] == "failure"
        assert log_entry["failure_reason"] is not None

    def test_audit_log_failure_does_not_crash(self):
        """If audit logging itself fails, the save should still succeed."""
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        with patch("src.repositories.applications_repo.create", return_value=True):
            with patch("src.repositories.audit_repo.log_action", side_effect=Exception("Audit DB down")):
                result = auto_save_jobs("u1", [job], existing_job_keys=set())
        assert result.saved_count == 1  # save succeeded despite audit failure


# ── Safety Fail-Closed ───────────────────────────────────────────────────────


class TestSafetyFailClosed:
    def test_safety_guard_load_failure_blocks_save(self):
        """If the safety guard cannot load, NO mutation must occur."""
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        with patch("src.rico_safety.RicoSafetyGuard", side_effect=ImportError("Module missing")):
            with patch("src.repositories.applications_repo.create") as mock_create:
                result = auto_save_jobs("u1", [job], existing_job_keys=set())
        assert result.saved_count == 0
        assert "fail-closed" in result.errors[0].lower()
        mock_create.assert_not_called()

    def test_safety_guard_exception_blocks_save(self):
        """If check_autonomous_action raises, NO mutation must occur."""
        from src.services.auto_save_service import auto_save_jobs

        job = {"title": "HSE Manager", "company": "ADNOC", "score": 85, "link": "https://example.com/1"}
        guard_mock = MagicMock()
        guard_mock.check_autonomous_action.side_effect = RuntimeError("Guard crashed")
        with patch("src.rico_safety.RicoSafetyGuard", return_value=guard_mock):
            with patch("src.repositories.applications_repo.create") as mock_create:
                result = auto_save_jobs("u1", [job], existing_job_keys=set())
        assert result.saved_count == 0
        assert "fail-closed" in result.errors[0].lower()
        mock_create.assert_not_called()

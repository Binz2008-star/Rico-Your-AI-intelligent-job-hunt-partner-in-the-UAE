"""Autonomous loop engine for Rico AI.

This is the core orchestrator for Rico's proactive push-based operation.
For each user with autonomous mode enabled, it:

  1. Loads user profile + preferences
  2. Fetches/scores new matching jobs
  3. Auto-saves high-match jobs to the user's pipeline
  4. Drafts cover letters for top matches
  5. Sends Telegram digest notification
  6. Checks follow-up schedule
  7. Generates daily action plan
  8. Logs all autonomous actions to audit trail

NEVER submits applications. NEVER sends recruiter messages.
All high-impact actions require explicit user approval.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.rico_env import env_bool

logger = logging.getLogger(__name__)

_UTC = timezone.utc

FOLLOWUP_DAYS_DEFAULT = 14
HIGH_MATCH_ALERT_THRESHOLD = 90


@dataclass
class AutonomousLoopResult:
    user_id: str
    user_name: str = ""
    new_matches_count: int = 0
    saved_jobs: List[Dict[str, Any]] = field(default_factory=list)
    drafts: List[Dict[str, Any]] = field(default_factory=list)
    followups_due: List[Dict[str, Any]] = field(default_factory=list)
    plan_actions: List[Dict[str, str]] = field(default_factory=list)
    journey_state: str = "discovery"
    telegram_sent: bool = False
    errors: List[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "new_matches_count": self.new_matches_count,
            "saved_count": len(self.saved_jobs),
            "draft_count": len(self.drafts),
            "followups_due_count": len(self.followups_due),
            "plan_actions": self.plan_actions,
            "journey_state": self.journey_state,
            "telegram_sent": self.telegram_sent,
            "errors": self.errors,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


def is_autonomous_mode_enabled() -> bool:
    """Master switch for autonomous mode. Default off."""
    return env_bool("RICO_AUTONOMOUS_MODE", False)


def _get_followup_days() -> int:
    return int(os.getenv("RICO_AUTONOMOUS_FOLLOWUP_DAYS", FOLLOWUP_DAYS_DEFAULT))


def _load_user_profile(user_id: str) -> Optional[Any]:
    """Load a user's profile from the profile repository."""
    try:
        from src.repositories.profile_repo import get_profile
        return get_profile(user_id)
    except Exception:
        logger.exception("autonomous_loop: profile load failed user=%s", user_id)
        return None


def _get_user_recommendation_keys(user_id: str) -> set[str]:
    """Get the set of job keys already in the user's pipeline."""
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db:
            return set()
        recs = db.get_recommendations(user_id)
        return {r.get("job_key", "") for r in recs if r.get("job_key")}
    except Exception:
        logger.debug("autonomous_loop: recommendation keys fetch failed user=%s", user_id)
        return set()


def _get_user_application_counts(user_id: str) -> Dict[str, int]:
    """Get application counts by status for journey state derivation."""
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db:
            return {"saved": 0, "applied": 0, "interview": 0}
        recs = db.get_recommendations(user_id)
        counts = {"saved": 0, "applied": 0, "interview": 0}
        for rec in recs:
            status = rec.get("status", "")
            if status == "saved":
                counts["saved"] += 1
            elif status == "applied":
                counts["applied"] += 1
            elif status == "interview":
                counts["interview"] += 1
        return counts
    except Exception:
        logger.debug("autonomous_loop: application counts fetch failed user=%s", user_id)
        return {"saved": 0, "applied": 0, "interview": 0}


def _check_followups(user_id: str, applications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check for applications that need follow-up (applied N+ days ago)."""
    days = _get_followup_days()
    cutoff = datetime.now(_UTC) - timedelta(days=days)
    due = []
    for app in applications:
        status = app.get("status", "")
        if status not in {"applied", "saved", "decision_made"}:
            continue
        raw_date = app.get("date_applied") or app.get("applied_at") or app.get("created_at")
        if not raw_date:
            continue
        try:
            applied_at = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            if applied_at.tzinfo is None:
                applied_at = applied_at.replace(tzinfo=_UTC)
            if applied_at <= cutoff:
                due.append(app)
        except (ValueError, TypeError):
            continue
    return due


def run_for_user(
    user_id: str,
    user_name: str = "",
    telegram_chat_id: str = "",
    scored_jobs: Optional[List[tuple]] = None,
    dry_run: bool = False,
) -> AutonomousLoopResult:
    """Run the autonomous loop for a single user.

    Args:
        user_id: The user's external ID.
        user_name: Display name for notifications.
        telegram_chat_id: Telegram chat ID for notifications (empty = skip Telegram).
        scored_jobs: Pre-scored jobs from the pipeline (list of (job_dict, score) tuples).
                     If None, the loop skips job search (assumes pipeline already ran).
        dry_run: When True, no actual saves/drafts/notifications are performed.

    Returns:
        AutonomousLoopResult with all actions taken.
    """
    result = AutonomousLoopResult(user_id=user_id, user_name=user_name)

    if not is_autonomous_mode_enabled():
        result.skipped = True
        result.skip_reason = "autonomous_mode_disabled"
        logger.info("autonomous_loop_skipped user=%s reason=mode_disabled", user_id)
        return result

    # 1. Load user profile
    profile = _load_user_profile(user_id)

    # 2. Process scored jobs from pipeline
    jobs_list: List[Dict[str, Any]] = []
    if scored_jobs:
        for job, score in scored_jobs:
            job_with_score = {**job, "score": score} if isinstance(job, dict) else {"score": score, **(job or {})}
            jobs_list.append(job_with_score)

    result.new_matches_count = len(jobs_list)

    # 3. Auto-save high-match jobs
    existing_keys = _get_user_recommendation_keys(user_id)
    if jobs_list and not dry_run:
        try:
            from src.services.auto_save_service import auto_save_jobs
            save_result = auto_save_jobs(
                user_id=user_id,
                jobs=jobs_list,
                existing_job_keys=existing_keys,
                daily_save_count=0,
            )
            result.saved_jobs = save_result.saved
            result.errors.extend(save_result.errors)
        except Exception as exc:
            logger.exception("autonomous_loop: auto_save failed user=%s", user_id)
            result.errors.append(f"Auto-save failed: {exc}")
    elif jobs_list and dry_run:
        result.saved_jobs = [{"job": j, "dry_run": True} for j in jobs_list[:10]]

    # 4. Generate drafts for top saved jobs
    if result.saved_jobs and not dry_run:
        try:
            from src.services.autonomous_draft_service import generate_drafts_for_jobs
            top_jobs = [s.get("job", s) for s in result.saved_jobs[:3]]
            draft_result = generate_drafts_for_jobs(
                user_id=user_id,
                jobs=top_jobs,
                profile=profile,
                daily_draft_count=0,
            )
            result.drafts = draft_result.drafts
            result.errors.extend(draft_result.errors)
        except Exception as exc:
            logger.exception("autonomous_loop: draft generation failed user=%s", user_id)
            result.errors.append(f"Draft generation failed: {exc}")

    # 5. Check follow-ups
    try:
        from src.applications import get_applied_jobs
        all_apps = get_applied_jobs()
        user_apps = [a for a in all_apps if isinstance(a, dict)]
        result.followups_due = _check_followups(user_id, user_apps)
    except Exception as exc:
        logger.debug("autonomous_loop: followup check failed user=%s", user_id)
        result.errors.append(f"Follow-up check failed: {exc}")

    # 6. Derive journey state + generate daily plan
    try:
        from src.agent.context.journey_state import derive_state, generate_daily_plan
        counts = _get_user_application_counts(user_id)
        state = derive_state(
            user_id=user_id,
            saved_count=counts["saved"],
            applied_count=counts["applied"],
            interviewing_count=counts["interview"],
        )
        result.journey_state = state.state
        plan = generate_daily_plan(
            user_id=user_id,
            state=state,
            new_matches_count=result.new_matches_count,
            followups_due_count=len(result.followups_due),
            drafts_ready_count=len(result.drafts),
        )
        result.plan_actions = plan.actions
    except Exception as exc:
        logger.debug("autonomous_loop: journey state failed user=%s", user_id)
        result.errors.append(f"Journey state failed: {exc}")

    # 7. Send Telegram notification
    if telegram_chat_id and not dry_run:
        try:
            from src.agent.responses.autonomous_notifications import (
                format_daily_digest,
                format_high_match_alert,
            )
            from src.telegram_bot import send_telegram_to_user

            # Immediate alert for very high matches
            for job in jobs_list:
                score = job.get("score", 0)
                try:
                    score = int(score)
                except (TypeError, ValueError):
                    score = 0
                if score >= HIGH_MATCH_ALERT_THRESHOLD:
                    try:
                        send_telegram_to_user(telegram_chat_id, format_high_match_alert(job))
                    except Exception:
                        logger.debug("autonomous_loop: high match alert failed user=%s", user_id)

            # Daily digest
            digest = format_daily_digest(
                user_name=user_name or "there",
                saved_jobs=result.saved_jobs,
                new_matches_count=result.new_matches_count,
                drafts_ready_count=len(result.drafts),
                followups_due_count=len(result.followups_due),
            )
            result.telegram_sent = send_telegram_to_user(telegram_chat_id, digest)
        except Exception as exc:
            logger.exception("autonomous_loop: telegram notification failed user=%s", user_id)
            result.errors.append(f"Telegram notification failed: {exc}")

    logger.info(
        "autonomous_loop_complete user=%s matches=%d saved=%d drafts=%d followups=%d state=%s telegram=%s",
        user_id, result.new_matches_count, len(result.saved_jobs),
        len(result.drafts), len(result.followups_due),
        result.journey_state, result.telegram_sent,
    )
    return result


def run_for_all_users(
    scored_jobs: Optional[List[tuple]] = None,
    dry_run: bool = False,
) -> List[AutonomousLoopResult]:
    """Run the autonomous loop for all users with Telegram alerts enabled.

    Args:
        scored_jobs: Pre-scored jobs from the pipeline.
        dry_run: When True, no actual actions are performed.

    Returns:
        List of AutonomousLoopResult, one per user.
    """
    if not is_autonomous_mode_enabled():
        logger.info("autonomous_loop_all_users_skipped reason=mode_disabled")
        return []

    try:
        from src.repositories.profile_repo import get_users_with_telegram_alerts
        users = get_users_with_telegram_alerts()
    except Exception:
        logger.exception("autonomous_loop: failed to fetch telegram alert users")
        return []

    if not users:
        logger.info("autonomous_loop_all_users_skipped reason=no_opted_in_users")
        return []

    results: List[AutonomousLoopResult] = []
    for user in users:
        user_id = user.get("external_user_id", "")
        chat_id = user.get("telegram_chat_id", "")
        name = user.get("name", "")
        if not user_id or not chat_id:
            continue

        try:
            result = run_for_user(
                user_id=user_id,
                user_name=name,
                telegram_chat_id=chat_id,
                scored_jobs=scored_jobs,
                dry_run=dry_run,
            )
            results.append(result)
        except Exception:
            logger.exception("autonomous_loop: user loop failed user=%s", user_id)
            results.append(AutonomousLoopResult(
                user_id=user_id, user_name=name,
                errors=["Loop crashed unexpectedly"],
            ))

    logger.info(
        "autonomous_loop_all_users_complete users=%d results=%d",
        len(users), len(results),
    )
    return results

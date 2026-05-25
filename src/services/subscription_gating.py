"""Subscription entitlement enforcement helpers."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from src.schemas.chat import RicoSessionContext
from src.subscription_plans import resolve_effective_user_plan

logger = logging.getLogger(__name__)
_UTC = timezone.utc


@dataclass(frozen=True)
class GateCheck:
    allowed: bool
    feature: str
    usage: int
    limit: int | None
    remaining: int | None
    plan: str
    message: str

    def to_response(self) -> dict[str, Any]:
        return {
            "type": "subscription_limit",
            "intent": "subscription_limit",
            "message": self.message,
            "response_source": "subscription_gate",
            "feature": self.feature,
            "usage": self.usage,
            "limit": self.limit,
            "remaining": self.remaining,
            "plan": self.plan,
            "next_action": "upgrade_subscription",
            "options": [
                {
                    "action": "upgrade_subscription",
                    "label": "View plans",
                    "message": "upgrade plan",
                },
                {
                    "action": "subscription_status",
                    "label": "Check current plan",
                    "message": "what is my plan?",
                },
            ],
        }


def _usage_window_start(resolved: Any) -> datetime:
    start = getattr(resolved.subscription, "current_period_start", None)
    if start:
        if start.tzinfo is None:
            return start.replace(tzinfo=_UTC)
        return start.astimezone(_UTC)
    now = datetime.now(_UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _build_gate_check(user_id: str, feature: str, usage: int) -> GateCheck:
    resolved = resolve_effective_user_plan(user_id)
    entitlements = resolved.subscription.entitlements
    limit = getattr(entitlements, feature, None)
    plan = resolved.subscription.plan.value

    if limit is None:
        return GateCheck(
            allowed=True,
            feature=feature,
            usage=usage,
            limit=None,
            remaining=None,
            plan=plan,
            message="No limit configured",
        )

    limit_int = int(limit)
    remaining = max(0, limit_int - int(usage))
    allowed = int(usage) < limit_int
    feature_label = feature.replace("_", " ")
    message = (
        f"You have reached your {feature_label} limit on the {plan.title()} plan "
        f"({usage}/{limit_int}). Upgrade to continue."
        if not allowed
        else f"{remaining} remaining for {feature_label}."
    )
    return GateCheck(
        allowed=allowed,
        feature=feature,
        usage=int(usage),
        limit=limit_int,
        remaining=remaining,
        plan=plan,
        message=message,
    )


def _db_user_uuid(user_id: str) -> str | None:
    try:
        from src.rico_db import RicoDB

        db = RicoDB()
        if not db.available:
            return None
        bundle = db.get_user_bundle(user_id)
        return str(bundle["id"]) if bundle else None
    except Exception:
        logger.debug("subscription_gating: db user lookup failed user=%s", user_id, exc_info=True)
        return None


def count_monthly_ai_messages(user_id: str, since: datetime) -> int:
    db_user_id = _db_user_uuid(user_id)
    if db_user_id:
        try:
            from src.rico_db import RicoDB

            db = RicoDB()
            conn = db.connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM rico_chat_history
                        WHERE user_id = %s AND role = 'user' AND created_at >= %s
                        """,
                        (db_user_id, since),
                    )
                    row = cur.fetchone()
                    return int(row["count"] if isinstance(row, dict) else row[0])
            finally:
                conn.close()
        except Exception:
            logger.debug("subscription_gating: DB chat usage count failed user=%s", user_id, exc_info=True)

    try:
        from src.rico_memory import RicoMemoryStore

        count = 0
        for item in RicoMemoryStore().load_chat_history(user_id):
            if not isinstance(item, dict) or item.get("role") != "user":
                continue
            raw = item.get("created_at") or item.get("timestamp")
            if not raw:
                continue
            try:
                ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=_UTC)
            except (TypeError, ValueError):
                continue
            if ts >= since:
                count += 1
        return count
    except Exception:
        logger.debug("subscription_gating: memory chat usage count failed user=%s", user_id, exc_info=True)
        return 0


def count_saved_jobs(user_id: str) -> int:
    try:
        from src.repositories.applications_repo import get_all

        apps = get_all(user_id=user_id)
    except Exception:
        from src.applications import get_applied_jobs

        apps = [
            app for app in get_applied_jobs()
            if not app.get("user_id") or app.get("user_id") == user_id
        ]
    return sum(1 for app in apps if isinstance(app, dict) and app.get("status") == "saved")


def count_profile_optimizations(user_id: str, since: datetime) -> int:
    try:
        from src.db import get_db_connection, is_db_available

        if not is_db_available():
            return 0
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM learning_signals
                    WHERE canonical_user_id = %s
                      AND signal_type = 'profile_optimization'
                      AND timestamp >= %s
                    """,
                    (user_id, since),
                )
                row = cur.fetchone()
                return int(row["count"] if isinstance(row, dict) else row[0])
        finally:
            conn.close()
    except Exception:
        logger.debug("subscription_gating: profile optimization count failed user=%s", user_id, exc_info=True)
        return 0


def check_ai_message_allowed(ctx: RicoSessionContext) -> GateCheck | None:
    if ctx.auth_type != "authenticated":
        return None
    resolved = resolve_effective_user_plan(ctx.user_id)
    since = _usage_window_start(resolved)
    usage = count_monthly_ai_messages(ctx.user_id, since)
    return _build_gate_check(ctx.user_id, "monthly_ai_message_limit", usage)


def enforce_saved_job_allowed(user_id: str) -> None:
    check = _build_gate_check(user_id, "saved_jobs_limit", count_saved_jobs(user_id))
    if not check.allowed:
        raise HTTPException(status_code=402, detail=check.to_response())


def enforce_profile_optimization_allowed(user_id: str) -> None:
    resolved = resolve_effective_user_plan(user_id)
    since = _usage_window_start(resolved)
    check = _build_gate_check(
        user_id,
        "profile_optimization_limit",
        count_profile_optimizations(user_id, since),
    )
    if not check.allowed:
        raise HTTPException(status_code=402, detail=check.to_response())


def record_profile_optimization_usage(user_id: str) -> None:
    try:
        from src.repositories.learning_repo import get_learning_repository

        get_learning_repository().record_signal(
            canonical_user_id=user_id,
            signal_type="profile_optimization",
            signal_value="cv_profile_confirm",
            signal_weight=1.0,
            source="subscription_gate",
            metadata={"feature": "profile_optimization_limit"},
        )
    except Exception:
        logger.debug("subscription_gating: profile optimization usage record failed user=%s", user_id, exc_info=True)

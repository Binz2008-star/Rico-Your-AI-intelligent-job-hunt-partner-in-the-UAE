"""Subscription entitlement enforcement helpers."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from src.schemas.chat import RicoSessionContext
from src.schemas.subscription import SubscriptionTier
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
    # When the usage window rolls over and the allowance refills. For the Free
    # AI-message allowance this is the next 00:00 UTC (daily reset); for a paid
    # plan it is the current billing-period end. None when not applicable.
    reset_at: datetime | None = None

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
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
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


def _build_gate_check(user_id: str, feature: str, usage: int, resolved: Any | None = None) -> GateCheck:
    resolved = resolved or resolve_effective_user_plan(user_id)
    entitlements = resolved.subscription.entitlements
    limit = getattr(entitlements, feature, None)
    plan = resolved.subscription.plan.value

    if limit is None:
        return GateCheck(
            allowed=True,
            feature=feature,
            usage=int(usage),
            limit=None,
            remaining=None,
            plan=plan,
            message="No limit configured",
        )

    limit_int = int(limit)
    usage_int = int(usage)
    remaining = max(0, limit_int - usage_int)
    allowed = usage_int < limit_int
    feature_label = feature.replace("_", " ")
    message = (
        f"You have reached your {feature_label} limit on the {plan.title()} plan "
        f"({usage_int}/{limit_int}). Upgrade to continue."
        if not allowed
        else f"{remaining} remaining for {feature_label}."
    )
    return GateCheck(
        allowed=allowed,
        feature=feature,
        usage=usage_int,
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
    """Count a user's AI chat messages sent at/after ``since``.

    Window-agnostic despite the historical name: callers pass the window start
    (start-of-day for the Free daily allowance, or the billing-period start for
    a paid plan). Kept named for patch/import compatibility.
    """
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
        from src.repositories.applications_repo import count_by_status

        # Canonical DB-side count (#1092): the full logical record set, not a
        # capped in-memory snapshot — quota decisions see every saved job.
        return count_by_status(user_id, "saved")
    except Exception:
        from src.applications import get_applied_jobs

        # Fallback path: count only rows that belong to *this* user. Rows with a
        # missing/empty user_id are NOT this user's and must not inflate their
        # saved-jobs quota (a multi-user product must never charge one account
        # for unowned legacy rows).
        apps = [
            app for app in get_applied_jobs()
            if app.get("user_id") == user_id
        ]
        return sum(
            1 for app in apps if isinstance(app, dict) and app.get("status") == "saved"
        )


def count_profile_optimizations(user_id: str, since: datetime) -> int:
    try:
        from src.db import get_db_connection, is_db_available

        if not is_db_available():
            return 0
        conn = get_db_connection()
        if conn is None:
            return 0
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


def _humanize_reset(reset_at: datetime, now: datetime) -> str:
    """Render the time until ``reset_at`` as e.g. "6 hours and 24 minutes"."""
    total_minutes = max(0, int((reset_at - now).total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if minutes or not hours:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
    return " and ".join(parts)


def check_ai_message_allowed_for_user(user_id: str) -> GateCheck:
    """AI-message allowance check keyed purely by ``user_id``.

    Independent of how the request was authenticated. The public chat endpoint uses this
    to enforce the cap on a *registered* user identified only by email, who would otherwise
    dodge the limit by routing through /chat/public instead of the authenticated /chat.

    Free tier is a DAILY allowance that resets at 00:00 UTC (not a monthly cap);
    paid tiers keep their monthly billing-cycle window. The returned GateCheck
    carries ``reset_at`` so callers can surface a "resets in …" countdown.
    """
    resolved = resolve_effective_user_plan(user_id)
    now = datetime.now(_UTC)
    is_free = (not resolved.is_active) or resolved.subscription.plan == SubscriptionTier.FREE

    if is_free:
        # Daily free allowance: window is the current UTC day; refills at 00:00 UTC.
        window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        reset_at: datetime | None = window_start + timedelta(days=1)
    else:
        window_start = _usage_window_start(resolved)
        reset_at = getattr(resolved.subscription, "current_period_end", None)

    usage = count_monthly_ai_messages(user_id, window_start)
    base = _build_gate_check(user_id, "monthly_ai_message_limit", usage, resolved)

    if base.limit is None:
        return replace(base, reset_at=reset_at)

    # Compose Free-tier copy in daily terms — never "monthly", never "24 hours"
    # (the window is the fixed UTC calendar day, not a rolling 24h span).
    if is_free:
        if base.allowed:
            message = f"{base.remaining} free AI messages remaining today."
        elif reset_at:
            message = (
                f"You've used your {base.limit} free AI messages for today. "
                f"Your allowance resets in {_humanize_reset(reset_at, now)}."
            )
        else:
            message = (
                f"You've used your {base.limit} free AI messages for today. "
                f"Your allowance resets daily at 00:00 UTC."
            )
        return replace(base, message=message, reset_at=reset_at)

    return replace(base, reset_at=reset_at)


def check_ai_message_allowed(ctx: RicoSessionContext) -> GateCheck | None:
    if ctx.auth_type != "authenticated":
        return None
    return check_ai_message_allowed_for_user(ctx.user_id)


def enforce_saved_job_allowed(user_id: str) -> None:
    from fastapi import HTTPException
    check = _build_gate_check(user_id, "saved_jobs_limit", count_saved_jobs(user_id))
    if not check.allowed:
        raise HTTPException(status_code=402, detail=check.to_response())


def enforce_profile_optimization_allowed(user_id: str, *, is_first_upload: bool = False) -> None:
    """Raise HTTP 402 if the user has exceeded their CV analysis limit.

    Pass ``is_first_upload=True`` during the initial onboarding CV confirm so that
    brand-new users are never blocked on their very first upload regardless of plan.
    Subsequent uploads are gated normally.
    """
    from fastapi import HTTPException
    resolved = resolve_effective_user_plan(user_id)
    since = _usage_window_start(resolved)
    usage = count_profile_optimizations(user_id, since)

    # Always allow the very first CV upload — blocking onboarding is never correct.
    if is_first_upload and usage == 0:
        return

    check = _build_gate_check(
        user_id,
        "profile_optimization_limit",
        usage,
        resolved,
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


# ── Document storage quota ─────────────────────────────────────────────────────

# No Premium tier exists (issue #1067): Rico Monthly is the only paid plan, and
# it does not offer unlimited storage. Hints state the enforced Rico Monthly
# ceiling only.
_UPGRADE_HINTS: dict[str, str] = {
    "cv_storage_limit": "Upgrade to Rico Monthly for up to 5 CVs",
    "other_document_limit": "Upgrade to Rico Monthly for up to 10 documents",
}


def count_user_documents(user_id: str, doc_type: str) -> int:
    """Count documents of *doc_type* stored for *user_id* using RicoDB.

    Returns 0 when DB is unavailable so callers can still proceed.
    """
    try:
        from src.rico_db import RicoDB

        db = RicoDB()
        if not db.available:
            return 0
        return db.count_user_documents(user_id, doc_type)
    except Exception:
        logger.debug(
            "subscription_gating: document count failed user=%s doc_type=%s",
            user_id,
            doc_type,
            exc_info=True,
        )
        return 0


def _feature_for_doc_type(doc_type: str) -> str:
    """Map a document type to its entitlement attribute name."""
    return "cv_storage_limit" if doc_type == "cv" else "other_document_limit"


def check_document_quota(user_id: str, doc_type: str) -> GateCheck:
    """Return a GateCheck for uploading a new document of *doc_type*."""
    feature = _feature_for_doc_type(doc_type)
    usage = count_user_documents(user_id, doc_type)
    resolved = resolve_effective_user_plan(user_id)
    return _build_gate_check(user_id, feature, usage, resolved)


def enforce_document_quota(user_id: str, doc_type: str) -> None:
    """Raise HTTP 422 with a structured detail dict if the document quota is reached.

    Uses 422 (Unprocessable Entity) rather than 402 so the frontend can inspect
    the detail without triggering a global payment-required redirect.
    """
    from fastapi import HTTPException

    check = check_document_quota(user_id, doc_type)
    if check.allowed:
        return

    plan = check.plan
    used = check.usage
    limit = check.limit
    feature = _feature_for_doc_type(doc_type)
    doc_label = "CV" if doc_type == "cv" else "document"

    # A user already on a paid plan has hit the ceiling of the plan they OWN —
    # prompting them to "upgrade" to that same plan is contradictory (a Pro user
    # at 5/5 CVs was told "Upgrade to Rico Monthly for up to 5 CVs"). Guide them
    # to free a slot instead. Only Free users are offered an upgrade.
    if plan != SubscriptionTier.FREE.value:
        hint = f"Delete or replace an existing {doc_label} to add another"
    else:
        hint = _UPGRADE_HINTS.get(feature, "Upgrade your plan for more storage")

    raise HTTPException(
        status_code=422,
        detail={
            "detail": f"{feature}_exceeded",
            "plan": plan,
            "used": used,
            "limit": limit,
            "upgrade_hint": hint,
            "doc_type": doc_type,
            "message": (
                f"You have reached your {doc_label} storage limit "
                f"({used}/{limit}) on the {plan.title()} plan. {hint}."
            ),
        },
    )

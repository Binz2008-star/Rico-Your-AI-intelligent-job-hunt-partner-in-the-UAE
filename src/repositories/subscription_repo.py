"""src/repositories/subscription_repo.py
DB-backed subscription persistence.

Read path:  DB first; returns None when DB unavailable or no record exists.
            Callers (resolve_effective_user_plan) treat None as Free tier.
Write path: DB primary; logs and returns None on failure — callers decide
            whether to surface the error.

Webhook idempotency helpers (event_already_processed / record_subscription_event)
are stubbed here for Phase 2 to wire in without touching this interface.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from src.rico_db import RicoDB

logger = logging.getLogger(__name__)


@contextmanager
def _db_transaction():
    db = RicoDB()
    if not db.available:
        yield None
        return
    conn = db.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _db() -> RicoDB | None:
    db = RicoDB()
    return db if db.available else None


# ── Read ──────────────────────────────────────────────────────────────────────

def get_subscription(user_id: str) -> dict[str, Any] | None:
    """Return the subscription row as a plain dict, or None if not found / DB unavailable."""
    db = _db()
    if not db:
        return None
    try:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, plan, status,
                           stripe_customer_id, stripe_subscription_id,
                           current_period_start, current_period_end,
                           cancel_at, canceled_at,
                           monthly_ai_message_limit, saved_jobs_limit, profile_optimization_limit,
                           premium_recommendations_enabled, application_automation_enabled,
                           created_at, updated_at
                    FROM user_subscriptions
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("subscription_repo: get_subscription failed user_id=%s", user_id)
        return None


def get_subscription_by_stripe_customer(stripe_customer_id: str) -> dict[str, Any] | None:
    """Look up a subscription by Stripe customer ID (for webhook processing)."""
    db = _db()
    if not db:
        return None
    try:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, plan, status,
                           stripe_customer_id, stripe_subscription_id,
                           current_period_start, current_period_end,
                           cancel_at, canceled_at,
                           monthly_ai_message_limit, saved_jobs_limit, profile_optimization_limit,
                           premium_recommendations_enabled, application_automation_enabled,
                           created_at, updated_at
                    FROM user_subscriptions
                    WHERE stripe_customer_id = %s
                    """,
                    (stripe_customer_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception(
            "subscription_repo: get_subscription_by_stripe_customer failed cus=%s",
            stripe_customer_id,
        )
        return None


# ── Write ─────────────────────────────────────────────────────────────────────

def upsert_subscription(
    user_id: str,
    *,
    plan: str,
    status: str,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
    cancel_at: datetime | None = None,
    canceled_at: datetime | None = None,
    monthly_ai_message_limit: int | None = None,
    saved_jobs_limit: int | None = None,
    profile_optimization_limit: int | None = None,
    premium_recommendations_enabled: bool = False,
    application_automation_enabled: bool = False,
) -> dict[str, Any] | None:
    """Create or update a subscription record.

    Stripe ID fields use COALESCE so an upsert without IDs never clears
    an existing customer/subscription ID — only an explicit non-None value
    will overwrite.

    Returns the persisted row dict, or None if DB is unavailable/fails.
    """
    try:
        with _db_transaction() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                from psycopg2.extras import Json  # noqa: PLC0415 — deferred to avoid eager psycopg2 dep
                cur.execute(
                    """
                    INSERT INTO user_subscriptions
                        (user_id, plan, status,
                         stripe_customer_id, stripe_subscription_id,
                         current_period_start, current_period_end,
                         cancel_at, canceled_at,
                         monthly_ai_message_limit, saved_jobs_limit, profile_optimization_limit,
                         premium_recommendations_enabled, application_automation_enabled)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        plan                           = EXCLUDED.plan,
                        status                         = EXCLUDED.status,
                        stripe_customer_id             = COALESCE(
                            EXCLUDED.stripe_customer_id,
                            user_subscriptions.stripe_customer_id
                        ),
                        stripe_subscription_id         = COALESCE(
                            EXCLUDED.stripe_subscription_id,
                            user_subscriptions.stripe_subscription_id
                        ),
                        current_period_start           = COALESCE(
                            EXCLUDED.current_period_start,
                            user_subscriptions.current_period_start
                        ),
                        current_period_end             = COALESCE(
                            EXCLUDED.current_period_end,
                            user_subscriptions.current_period_end
                        ),
                        cancel_at                      = COALESCE(
                            EXCLUDED.cancel_at,
                            user_subscriptions.cancel_at
                        ),
                        canceled_at                    = COALESCE(
                            EXCLUDED.canceled_at,
                            user_subscriptions.canceled_at
                        ),
                        monthly_ai_message_limit        = COALESCE(
                            EXCLUDED.monthly_ai_message_limit,
                            user_subscriptions.monthly_ai_message_limit
                        ),
                        saved_jobs_limit               = COALESCE(
                            EXCLUDED.saved_jobs_limit,
                            user_subscriptions.saved_jobs_limit
                        ),
                        profile_optimization_limit     = COALESCE(
                            EXCLUDED.profile_optimization_limit,
                            user_subscriptions.profile_optimization_limit
                        ),
                        premium_recommendations_enabled = COALESCE(
                            EXCLUDED.premium_recommendations_enabled,
                            user_subscriptions.premium_recommendations_enabled
                        ),
                        application_automation_enabled = COALESCE(
                            EXCLUDED.application_automation_enabled,
                            user_subscriptions.application_automation_enabled
                        ),
                        updated_at                     = NOW()
                    RETURNING user_id, plan, status,
                              stripe_customer_id, stripe_subscription_id,
                              current_period_start, current_period_end,
                              cancel_at, canceled_at,
                              monthly_ai_message_limit, saved_jobs_limit, profile_optimization_limit,
                              premium_recommendations_enabled, application_automation_enabled,
                              created_at, updated_at
                    """,
                    (
                        user_id, plan, status,
                        stripe_customer_id, stripe_subscription_id,
                        current_period_start, current_period_end,
                        cancel_at, canceled_at,
                        monthly_ai_message_limit, saved_jobs_limit, profile_optimization_limit,
                        premium_recommendations_enabled, application_automation_enabled,
                    ),
                )
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("subscription_repo: upsert_subscription failed user_id=%s", user_id)
        return None


# ── Webhook idempotency ───────────────────────────────────────────────────────

def event_already_processed(stripe_event_id: str) -> bool:
    """Return True if this Stripe event has already completed successfully."""
    db = _db()
    if not db:
        return False
    try:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                      FROM subscription_events
                     WHERE stripe_event_id = %s
                       AND status = 'processed'
                    """,
                    (stripe_event_id,),
                )
                return cur.fetchone() is not None
    except Exception:
        logger.exception(
            "subscription_repo: event_already_processed failed event_id=%s", stripe_event_id
        )
        return False


def record_subscription_event(
    stripe_event_id: str,
    event_type: str,
    *,
    user_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Atomically claim a Stripe webhook event for processing.

    Returns True when the caller should proceed with side effects:
      - newly inserted (first time we've seen this event_id), OR
      - re-claimed from 'failed' (previous attempt errored; eligible for retry).

    Returns False (skip) when:
      - existing status is 'processed' — already handled successfully.
      - existing status is 'pending' — another worker is in-flight.
      - DB is unavailable or an exception occurred.

    After processing, callers MUST call update_subscription_event_status() to
    transition from 'pending' to 'processed' or 'failed'. An event left as
    'pending' permanently blocks retries for that event_id.
    """
    try:
        inserted = False
        with _db_transaction() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                from psycopg2.extras import Json  # noqa: PLC0415
                cur.execute(
                    """
                    INSERT INTO subscription_events
                        (stripe_event_id, event_type, user_id, payload, status)
                    VALUES (%s, %s, %s, %s, 'pending')
                    ON CONFLICT (stripe_event_id) DO UPDATE
                        SET status       = 'pending',
                            error_detail = NULL
                      WHERE subscription_events.status = 'failed'
                    """,
                    (stripe_event_id, event_type, user_id, Json(payload or {})),
                )
                inserted = cur.rowcount > 0
        return inserted
    except Exception:
        logger.exception(
            "subscription_repo: record_subscription_event failed event_id=%s", stripe_event_id
        )
        return False


def update_subscription_event_status(
    stripe_event_id: str,
    status: str,
    *,
    error_detail: str | None = None,
) -> None:
    """Close out a claimed event with its final status.

    Call with status='processed' on handler success, 'failed' on exception.
    Failed events are re-claimable by record_subscription_event on the next retry.
    Sets processed_at timestamp when status='processed'.
    """
    try:
        with _db_transaction() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                if status == "processed":
                    cur.execute(
                        """
                        UPDATE subscription_events
                           SET status = %s, error_detail = %s, processed_at = NOW()
                         WHERE stripe_event_id = %s
                        """,
                        (status, error_detail, stripe_event_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE subscription_events
                           SET status = %s, error_detail = %s
                         WHERE stripe_event_id = %s
                        """,
                        (status, error_detail, stripe_event_id),
                    )
    except Exception:
        logger.exception(
            "subscription_repo: update_subscription_event_status failed event_id=%s", stripe_event_id
        )

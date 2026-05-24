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
                         current_period_start, current_period_end)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        plan                   = EXCLUDED.plan,
                        status                 = EXCLUDED.status,
                        stripe_customer_id     = COALESCE(
                            EXCLUDED.stripe_customer_id,
                            user_subscriptions.stripe_customer_id
                        ),
                        stripe_subscription_id = COALESCE(
                            EXCLUDED.stripe_subscription_id,
                            user_subscriptions.stripe_subscription_id
                        ),
                        current_period_start   = COALESCE(
                            EXCLUDED.current_period_start,
                            user_subscriptions.current_period_start
                        ),
                        current_period_end     = COALESCE(
                            EXCLUDED.current_period_end,
                            user_subscriptions.current_period_end
                        ),
                        updated_at             = NOW()
                    RETURNING user_id, plan, status,
                              stripe_customer_id, stripe_subscription_id,
                              current_period_start, current_period_end,
                              created_at, updated_at
                    """,
                    (
                        user_id, plan, status,
                        stripe_customer_id, stripe_subscription_id,
                        current_period_start, current_period_end,
                    ),
                )
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("subscription_repo: upsert_subscription failed user_id=%s", user_id)
        return None


# ── Webhook idempotency ───────────────────────────────────────────────────────

def event_already_processed(stripe_event_id: str) -> bool:
    """Return True if this Stripe event has already been recorded."""
    db = _db()
    if not db:
        return False
    try:
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM subscription_events WHERE stripe_event_id = %s",
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
    """Idempotently record a Stripe webhook event.

    Returns True if the event was newly inserted, False if it already existed
    (duplicate) or if the DB is unavailable/failed. Callers use this to decide
    whether to run side effects — only the worker that gets True should proceed.
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
                        (stripe_event_id, event_type, user_id, payload)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (stripe_event_id) DO NOTHING
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

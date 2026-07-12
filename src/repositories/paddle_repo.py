"""Repository layer for Paddle billing tables.

Wraps paddle_customers, paddle_subscriptions, and paddle_webhook_events.
All functions accept an optional ``conn`` parameter to allow callers to
reuse an existing connection (unit-test injection).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_conn(db_module: Any):
    """Return a fresh connection from the shared pool."""
    return db_module.get_connection()


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

def upsert_paddle_customer(
    db_module: Any,
    user_id: str,
    paddle_customer_id: str,
    email: Optional[str] = None,
    conn=None,
) -> Dict[str, Any]:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paddle_customers (user_id, paddle_customer_id, email)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET paddle_customer_id = EXCLUDED.paddle_customer_id,
                        email              = COALESCE(EXCLUDED.email, paddle_customers.email),
                        updated_at         = NOW()
                RETURNING *
                """,
                (user_id, paddle_customer_id, email),
            )
            row = dict(cur.fetchone())
        if should_close:
            conn.commit()
        return row
    except Exception:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if should_close:
            conn.close()


def get_paddle_customer_by_user(
    db_module: Any,
    user_id: str,
    conn=None,
) -> Optional[Dict[str, Any]]:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM paddle_customers WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def get_paddle_customer_by_paddle_id(
    db_module: Any,
    paddle_customer_id: str,
    conn=None,
) -> Optional[Dict[str, Any]]:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM paddle_customers WHERE paddle_customer_id = %s",
                (paddle_customer_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def upsert_paddle_subscription(
    db_module: Any,
    user_id: str,
    paddle_subscription_id: str,
    paddle_customer_id: str,
    plan: str,
    status: str,
    billing_cycle: str = "monthly",
    price_id: Optional[str] = None,
    current_period_start=None,
    current_period_end=None,
    cancel_at=None,
    canceled_at=None,
    occurred_at=None,
    conn=None,
) -> Dict[str, Any]:
    """Upsert a subscription row with stale-event protection.

    If ``occurred_at`` is provided, the UPDATE branch only applies when
    the incoming event is *newer* than the stored ``last_event_occurred_at``.
    This prevents out-of-order or replayed events from overwriting fresher state.
    """
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paddle_subscriptions
                    (user_id, paddle_subscription_id, paddle_customer_id, plan, status,
                     billing_cycle, price_id, current_period_start, current_period_end,
                     cancel_at, canceled_at, last_event_occurred_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET paddle_subscription_id = EXCLUDED.paddle_subscription_id,
                        paddle_customer_id     = EXCLUDED.paddle_customer_id,
                        plan                   = EXCLUDED.plan,
                        status                 = EXCLUDED.status,
                        billing_cycle          = EXCLUDED.billing_cycle,
                        price_id               = EXCLUDED.price_id,
                        current_period_start   = EXCLUDED.current_period_start,
                        current_period_end     = EXCLUDED.current_period_end,
                        cancel_at              = EXCLUDED.cancel_at,
                        canceled_at            = EXCLUDED.canceled_at,
                        last_event_occurred_at = EXCLUDED.last_event_occurred_at,
                        updated_at             = NOW()
                    WHERE (
                        EXCLUDED.last_event_occurred_at IS NULL
                        OR paddle_subscriptions.last_event_occurred_at IS NULL
                        OR EXCLUDED.last_event_occurred_at > paddle_subscriptions.last_event_occurred_at
                    )
                RETURNING *
                """,
                (
                    user_id,
                    paddle_subscription_id,
                    paddle_customer_id,
                    plan,
                    status,
                    billing_cycle,
                    price_id,
                    current_period_start,
                    current_period_end,
                    cancel_at,
                    canceled_at,
                    occurred_at,
                ),
            )
            row = cur.fetchone()
            result = dict(row) if row else {}
        if should_close:
            conn.commit()
        return result
    except Exception:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if should_close:
            conn.close()


# ---------------------------------------------------------------------------
# Checkout sessions (server-owned checkout attribution)
# ---------------------------------------------------------------------------

def create_checkout_session(
    db_module: Any,
    user_id: str,
    plan: str,
    billing_cycle: str,
    session_token: str,
    conn=None,
) -> Dict[str, Any]:
    """Insert a new checkout session correlation record."""
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paddle_checkout_sessions
                    (session_token, user_id, plan, billing_cycle)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (session_token, user_id, plan, billing_cycle),
            )
            row = dict(cur.fetchone())
        if should_close:
            conn.commit()
        return row
    except Exception:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if should_close:
            conn.close()


def get_checkout_session(
    db_module: Any,
    session_token: str,
    conn=None,
) -> Optional[Dict[str, Any]]:
    """Look up a checkout session by token. Returns None if not found or expired."""
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM paddle_checkout_sessions
                WHERE session_token = %s
                  AND expires_at > NOW()
                  AND used = FALSE
                """,
                (session_token,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def mark_checkout_session_used(
    db_module: Any,
    session_token: str,
    conn=None,
) -> None:
    """Mark a checkout session as consumed so it cannot be replayed."""
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE paddle_checkout_sessions
                SET used = TRUE
                WHERE session_token = %s
                """,
                (session_token,),
            )
        if should_close:
            conn.commit()
    except Exception:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if should_close:
            conn.close()


def get_paddle_subscription_by_user(
    db_module: Any,
    user_id: str,
    conn=None,
) -> Optional[Dict[str, Any]]:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM paddle_subscriptions WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def get_paddle_subscription_by_paddle_id(
    db_module: Any,
    paddle_subscription_id: str,
    conn=None,
) -> Optional[Dict[str, Any]]:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM paddle_subscriptions WHERE paddle_subscription_id = %s",
                (paddle_subscription_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def get_paddle_subscription_by_customer_id(
    db_module: Any,
    paddle_customer_id: str,
    conn=None,
) -> Optional[Dict[str, Any]]:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM paddle_subscriptions WHERE paddle_customer_id = %s LIMIT 1",
                (paddle_customer_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


# ---------------------------------------------------------------------------
# Webhook idempotency
# ---------------------------------------------------------------------------

def paddle_event_already_processed(
    db_module: Any,
    paddle_event_id: str,
    conn=None,
) -> bool:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status FROM paddle_webhook_events
                WHERE paddle_event_id = %s
                """,
                (paddle_event_id,),
            )
            row = cur.fetchone()
        if row is None:
            return False
        return row["status"] == "processed"
    finally:
        if should_close:
            conn.close()


def record_paddle_webhook_event(
    db_module: Any,
    paddle_event_id: str,
    event_type: str,
    user_id: Optional[str] = None,
    payload=None,
    conn=None,
) -> bool:
    """Insert a new event row. Returns True if newly inserted, False if duplicate."""
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paddle_webhook_events
                    (paddle_event_id, event_type, user_id, status, payload)
                VALUES (%s, %s, %s, 'pending', %s)
                ON CONFLICT (paddle_event_id) DO NOTHING
                """,
                (paddle_event_id, event_type, user_id, payload),
            )
            inserted = cur.rowcount > 0
        if should_close:
            conn.commit()
        return inserted
    except Exception:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if should_close:
            conn.close()


def mark_paddle_event_processed(
    db_module: Any,
    paddle_event_id: str,
    conn=None,
) -> None:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE paddle_webhook_events
                SET status = 'processed', processed_at = NOW()
                WHERE paddle_event_id = %s
                """,
                (paddle_event_id,),
            )
        if should_close:
            conn.commit()
    except Exception:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if should_close:
            conn.close()


def mark_paddle_event_failed(
    db_module: Any,
    paddle_event_id: str,
    error_detail: str,
    conn=None,
) -> None:
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE paddle_webhook_events
                SET status = 'failed', error_detail = %s
                WHERE paddle_event_id = %s
                """,
                (error_detail, paddle_event_id),
            )
        if should_close:
            conn.commit()
    except Exception:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if should_close:
            conn.close()

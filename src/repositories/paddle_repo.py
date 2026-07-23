"""Repository layer for Paddle billing tables.

Wraps paddle_customers, paddle_subscriptions, paddle_webhook_events, and
paddle_checkout_sessions. All functions accept an optional ``conn``
parameter to allow callers to reuse an existing connection (unit-test
injection).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# A 'pending' webhook-event row older than this is treated as abandoned — the
# worker that claimed it crashed before marking it processed/failed — and may be
# reclaimed for reprocessing. Comfortably longer than real handler latency
# (sub-second) and far shorter than Paddle's multi-hour retry backoff, so a
# normal in-flight event is never double-claimed.
_PENDING_RECLAIM_SECONDS = 900  # 15 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rico_db():
    from src.rico_db import RicoDB
    return RicoDB()


def _get_conn(db_module: Any = None):
    """Return a connection with dict-row cursors (RealDictCursor).

    ``db_module`` is accepted for call-site compatibility but is no longer
    used for connection acquisition: ``src.db.get_db_connection()`` returns
    a plain-tuple-cursor connection, which is incompatible with this
    module's ``dict(row)`` / ``row["field"]`` access pattern. RicoDB is the
    connection helper the rest of the app's repositories use and always
    sets cursor_factory=RealDictCursor.
    """
    return _rico_db().connect()


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
    past_due_since=None,
    clear_past_due: bool = False,
    conn=None,
) -> Dict[str, Any]:
    """Upsert a subscription row with stale-event protection.

    If ``occurred_at`` is provided, the UPDATE branch only applies when
    the incoming event is *newer* than the stored ``last_event_occurred_at``.
    This prevents out-of-order or replayed events from overwriting fresher state.

    ``past_due_since`` stamps when a subscription first became past_due (for
    the 7-day payment-retry grace period). Pass ``clear_past_due=True`` when
    the subscription is no longer past_due, to NULL the column back out.
    """
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    past_due_sql = "NULL" if clear_past_due else "COALESCE(%(past_due_since)s, paddle_subscriptions.past_due_since)"
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO paddle_subscriptions
                    (user_id, paddle_subscription_id, paddle_customer_id, plan, status,
                     billing_cycle, price_id, current_period_start, current_period_end,
                     cancel_at, canceled_at, last_event_occurred_at, past_due_since)
                VALUES (%(user_id)s, %(paddle_subscription_id)s, %(paddle_customer_id)s, %(plan)s, %(status)s,
                        %(billing_cycle)s, %(price_id)s, %(current_period_start)s, %(current_period_end)s,
                        %(cancel_at)s, %(canceled_at)s, %(occurred_at)s, %(past_due_since)s)
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
                        past_due_since         = {past_due_sql},
                        updated_at             = NOW()
                    WHERE (
                        EXCLUDED.last_event_occurred_at IS NULL
                        OR paddle_subscriptions.last_event_occurred_at IS NULL
                        OR EXCLUDED.last_event_occurred_at > paddle_subscriptions.last_event_occurred_at
                    )
                RETURNING *
                """,
                {
                    "user_id": user_id,
                    "paddle_subscription_id": paddle_subscription_id,
                    "paddle_customer_id": paddle_customer_id,
                    "plan": plan,
                    "status": status,
                    "billing_cycle": billing_cycle,
                    "price_id": price_id,
                    "current_period_start": current_period_start,
                    "current_period_end": current_period_end,
                    "cancel_at": cancel_at,
                    "canceled_at": canceled_at,
                    "occurred_at": occurred_at,
                    "past_due_since": past_due_since,
                },
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
                WHERE session_token = %s AND used = FALSE
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
    """Atomically CLAIM a webhook event for processing.

    Returns True if THIS caller now owns the event and must run its handler,
    False if it must be skipped.

    Claim rules (a single atomic upsert, so two concurrent deliveries of the
    same event can never both win):
      - brand-new event id            -> insert 'pending', claim  -> True
      - existing 'failed' event       -> reclaim, reset 'pending'  -> True
      - existing abandoned 'pending'  -> reclaim                   -> True
        (claimed_at older than _PENDING_RECLAIM_SECONDS: the previous worker
         crashed before marking it processed/failed)
      - existing 'processed' event    -> skip                      -> False
      - existing in-flight 'pending'  -> skip (no double-run)      -> False

    This replaces the previous ``INSERT ... ON CONFLICT DO NOTHING``, which
    returned False for ANY pre-existing row and therefore silently dropped
    Paddle's retries of failed/crashed events — a paid subscription could then
    never be written to the DB. The event handler is idempotent (subscription
    upsert keyed by user_id, with an occurred_at stale-guard), so a rare
    over-claim inside the reclaim window is safe.
    """
    should_close = conn is None
    if conn is None:
        conn = _get_conn(db_module)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paddle_webhook_events
                    (paddle_event_id, event_type, user_id, status, payload, claimed_at)
                VALUES (%s, %s, %s, 'pending', %s, NOW())
                ON CONFLICT (paddle_event_id) DO UPDATE
                    SET status       = 'pending',
                        event_type   = EXCLUDED.event_type,
                        error_detail = NULL,
                        claimed_at   = NOW()
                    WHERE paddle_webhook_events.status = 'failed'
                       OR (
                            paddle_webhook_events.status = 'pending'
                            AND (
                                paddle_webhook_events.claimed_at IS NULL
                                OR paddle_webhook_events.claimed_at
                                     < NOW() - make_interval(secs => %s)
                            )
                          )
                RETURNING id
                """,
                (paddle_event_id, event_type, user_id, payload, _PENDING_RECLAIM_SECONDS),
            )
            claimed = cur.fetchone() is not None
        if should_close:
            conn.commit()
        return claimed
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


# ---------------------------------------------------------------------------
# Expiry maintenance
# ---------------------------------------------------------------------------

def expire_stale_paddle_subscriptions(db_module: Any = None, conn=None) -> int:
    """Mark subscriptions whose current_period_end has passed as inactive.

    Daily hygiene pass — entitlement resolution (resolve_effective_user_plan)
    already independently enforces current_period_end at read time, so this
    is not correctness-critical, but keeps the stored status column truthful
    for admin/reporting views. Only touches rows still 'active' whose period
    has ended; never touches canceled_at or admin-set fields.

    Returns the number of rows updated, or -1 if DB is unavailable.
    """
    should_close = conn is None
    if conn is None:
        try:
            conn = _get_conn(db_module)
        except Exception:
            return -1
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE paddle_subscriptions
                   SET status     = 'inactive',
                       updated_at = NOW()
                 WHERE status             = 'active'
                   AND current_period_end IS NOT NULL
                   AND current_period_end < NOW()
                """,
            )
            updated = cur.rowcount
        if should_close:
            conn.commit()
        return updated
    except Exception:
        logger.exception("paddle_repo: expire_stale_paddle_subscriptions failed")
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        return -1
    finally:
        if should_close:
            conn.close()

"""Repository for WhatsApp-assisted subscription requests (migration 049).

ENTITLEMENT BOUNDARY: nothing in this module reads or writes subscription
entitlement. A pending/approved row here is bookkeeping for the assisted
channel only — entitlement activation happens exclusively through
paddle_repo.upsert_paddle_subscription (Paddle webhook or the admin-only
manual activation endpoint).

Identity: user_id is the authenticated account identifier (email) — always
taken from the JWT dependency by the caller, never from the browser body.
Plan/price/currency are the server-side snapshot passed by the router.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional

from src.db import get_db_connection

logger = logging.getLogger(__name__)

_ALLOWED_STATUSES = ("pending", "approved", "rejected")


def _new_reference() -> str:
    """Opaque request reference shared with the user over WhatsApp.

    Not a database id and carries no identity — safe to appear in a chat
    message. Format: RICO-XXXXXXXXXX (10 hex chars, uppercase).
    """
    return f"RICO-{secrets.token_hex(5).upper()}"


def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    reference, user_id, plan, price_usd, currency, status, language, created_at = row
    return {
        "reference": reference,
        "user_id": user_id,
        "plan": plan,
        "price_usd": float(price_usd),
        "currency": currency,
        "status": status,
        "requested_language": language,
        "created_at": created_at,
    }


_SELECT_COLS = (
    "reference, user_id, plan, price_usd, currency, status, "
    "requested_language, created_at"
)


def get_or_create_pending_request(
    user_id: str,
    *,
    plan: str,
    price_usd: float,
    currency: str,
    language: str = "en",
) -> Optional[Dict[str, Any]]:
    """Return the user's pending request, creating one if none exists.

    Idempotent by design: the partial unique index
    uq_whatsapp_sub_requests_user_pending guarantees at most one pending row
    per user; a lost insert race falls back to re-selecting the winner.
    Returns None on any DB failure (caller fails closed).
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_SELECT_COLS} FROM whatsapp_subscription_requests "
                "WHERE user_id = %s AND status = 'pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
            existing = cur.fetchone()
            if existing:
                conn.rollback()
                return _row_to_dict(existing)

            reference = _new_reference()
            cur.execute(
                "INSERT INTO whatsapp_subscription_requests "
                "  (reference, user_id, plan, price_usd, currency, status, requested_language) "
                "VALUES (%s, %s, %s, %s, %s, 'pending', %s) "
                "ON CONFLICT DO NOTHING "
                f"RETURNING {_SELECT_COLS}",
                (reference, user_id, plan, price_usd, currency, language),
            )
            inserted = cur.fetchone()
            if inserted:
                conn.commit()
                return _row_to_dict(inserted)

            # Insert race lost against a concurrent click — reuse the winner.
            conn.rollback()
            cur.execute(
                f"SELECT {_SELECT_COLS} FROM whatsapp_subscription_requests "
                "WHERE user_id = %s AND status = 'pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
            return _row_to_dict(cur.fetchone())
    except Exception as exc:
        logger.warning("whatsapp_request_get_or_create failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        # get_db_connection() opens a fresh psycopg2 connection each call (no
        # pool); without this close every request strands a Neon connection.
        try:
            conn.close()
        except Exception:
            pass


def get_request_by_reference(reference: str) -> Optional[Dict[str, Any]]:
    """Fetch one request by its opaque reference. None if absent/DB down."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_SELECT_COLS} FROM whatsapp_subscription_requests "
                "WHERE reference = %s",
                (reference,),
            )
            row = cur.fetchone()
        conn.rollback()
        return _row_to_dict(row)
    except Exception as exc:
        logger.warning("whatsapp_request_lookup failed: %s", exc)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mark_request_status(
    reference: str,
    status: str,
    *,
    approved_by: Optional[str] = None,
) -> bool:
    """Transition a request's status (audit bookkeeping only — no entitlement).

    Idempotent: transitioning to the same status is a no-op success. Only the
    statuses in _ALLOWED_STATUSES are accepted.
    """
    if status not in _ALLOWED_STATUSES:
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE whatsapp_subscription_requests "
                "SET status = %s, "
                "    approved_by = CASE WHEN %s = 'approved' THEN %s ELSE approved_by END, "
                "    approved_at = CASE WHEN %s = 'approved' THEN now() ELSE approved_at END, "
                "    updated_at = now() "
                "WHERE reference = %s",
                (status, status, approved_by, status, reference),
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    except Exception as exc:
        logger.warning("whatsapp_request_mark_status failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass

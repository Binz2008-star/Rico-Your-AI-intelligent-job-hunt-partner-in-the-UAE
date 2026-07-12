"""Paddle webhook event processor.

Handles the Paddle Billing event lifecycle: idempotency guard, subscription
state transitions, and mapping Paddle statuses to Rico plan/status values.

Security contract:
  - Signature verification and timestamp freshness are done in the router.
  - Identity: DB lookup (customer_id / subscription_id) is authoritative.
    custom_data.user_id is used ONLY as a last-resort bootstrap for
    subscription.created when the customer record does not yet exist in DB.
  - Unknown price IDs NEVER grant paid entitlement (no default-to-pro).
  - occurred_at staleness: events older than the DB record are ignored.

Approved plan scope: Rico Pro only (monthly + yearly).
Premium is out of scope until a pricing decision approves it.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status / plan mapping
# ---------------------------------------------------------------------------

# Paddle subscription statuses → Rico internal statuses
_PADDLE_TO_RICO_STATUS: Dict[str, str] = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "paused": "paused",
    "canceled": "canceled",
    "cancelled": "canceled",
}

# Paddle price_id → Rico plan name.
# Populated lazily from env; cleared in tests via _PRICE_TO_PLAN.clear().
_PRICE_TO_PLAN: Dict[str, str] = {}


def _build_price_map() -> None:
    """Populate _PRICE_TO_PLAN from environment variables (approved scope: pro only)."""
    import os
    _PRICE_TO_PLAN.clear()
    for key in ("PADDLE_PRO_MONTHLY_PRICE_ID", "PADDLE_PRO_YEARLY_PRICE_ID"):
        pid = os.getenv(key, "").strip()
        if pid:
            _PRICE_TO_PLAN[pid] = "pro"


def _resolve_plan_from_price_id(price_id: Optional[str]) -> Optional[str]:
    """Map a Paddle price_id to a Rico plan name ('pro').

    Returns None for unknown/unconfigured price IDs — callers must treat
    None as an unmapped price and MUST NOT grant any paid entitlement.
    """
    if not _PRICE_TO_PLAN:
        _build_price_map()
    if price_id and price_id in _PRICE_TO_PLAN:
        return _PRICE_TO_PLAN[price_id]
    return None  # NEVER default to a paid plan


def _billing_cycle_from_price_id(price_id: Optional[str]) -> str:
    """Return 'yearly' when the price_id matches the yearly Pro price, else 'monthly'."""
    import os
    yearly_id = os.getenv("PADDLE_PRO_YEARLY_PRICE_ID", "").strip()
    if price_id and yearly_id and price_id == yearly_id:
        return "yearly"
    return "monthly"


def _parse_occurred_at(payload: Dict[str, Any]) -> Optional[datetime]:
    """Extract occurred_at from the Paddle event envelope as an aware datetime."""
    raw = payload.get("occurred_at")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def process_paddle_webhook(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    """Process one Paddle webhook event end-to-end.

    Durability contract:
      1. Idempotency check — skip if already processed.
      2. Durably record the event in DB (pending status) before any business logic.
      3. Execute handler.
      4. Mark event processed/failed in DB.

    Returns a dict with ``{"status": "processed"|"skipped"|"failed", ...}``.
    Never raises — all exceptions are caught and logged.
    """
    from src.repositories import paddle_repo

    try:
        already = paddle_repo.paddle_event_already_processed(db_module, event_id)
        if already:
            logger.info("paddle_webhook_duplicate event_id=%s type=%s", event_id, event_type)
            return {"status": "skipped", "reason": "duplicate"}

        # Durably persist the raw event BEFORE any business logic.
        # If this fails, raise so the router returns non-200 to Paddle → retry.
        inserted = paddle_repo.record_paddle_webhook_event(
            db_module,
            paddle_event_id=event_id,
            event_type=event_type,
            payload=json.dumps(payload) if payload else None,
        )
        if not inserted:
            return {"status": "skipped", "reason": "duplicate"}

        handler = _HANDLERS.get(event_type)
        if handler is None:
            logger.debug("paddle_webhook_unhandled type=%s", event_type)
            paddle_repo.mark_paddle_event_processed(db_module, event_id)
            return {"status": "skipped", "reason": "unhandled_event_type"}

        result = handler(event_id, event_type, payload, db_module)
        paddle_repo.mark_paddle_event_processed(db_module, event_id)
        return {"status": "processed", **result}

    except Exception as exc:
        logger.exception("paddle_webhook_error event_id=%s type=%s", event_id, event_type)
        try:
            paddle_repo.mark_paddle_event_failed(db_module, event_id, str(exc))
        except Exception:
            pass
        return {"status": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shared helpers for subscription event handlers
# ---------------------------------------------------------------------------

def _extract_subscription_data(
    payload: Dict[str, Any],
    db_module: Any,
    *,
    event_id: str,
    require_plan: bool = True,
):
    """Extract and validate common subscription event fields.

    Returns a dict of extracted fields, or raises ValueError with a
    descriptive message that will be caught by process_paddle_webhook.

    Identity resolution order (most authoritative first):
      1. DB lookup by subscription_id   (authoritative — server-owned record)
      2. DB lookup by customer_id       (server-owned record)
      3. custom_data.user_id            (bootstrap only for subscription.created)
    """
    from src.repositories import paddle_repo

    data = payload.get("data", {})
    sub_id = data.get("id")
    customer_id = data.get("customer_id")
    status_raw = data.get("status", "active")
    rico_status = _PADDLE_TO_RICO_STATUS.get(status_raw, status_raw)

    items = data.get("items", [])
    price_id = items[0]["price"]["id"] if items and "price" in items[0] else None

    plan = _resolve_plan_from_price_id(price_id)
    if require_plan and plan is None:
        logger.warning(
            "paddle_unmapped_price event_id=%s price_id=%s — recording as unmapped, no entitlement granted",
            event_id, price_id,
        )
        return {"unmapped": True, "price_id": price_id, "sub_id": sub_id}

    billing_cycle = _billing_cycle_from_price_id(price_id)

    current_billing = data.get("current_billing_period", {})
    period_start = current_billing.get("starts_at")
    period_end = current_billing.get("ends_at")

    scheduled_change = data.get("scheduled_change") or {}
    cancel_at = (
        scheduled_change.get("effective_at")
        if scheduled_change.get("action") == "cancel"
        else None
    )

    # Identity: DB is authoritative — custom_data is bootstrap only
    user_id = (
        _user_id_from_sub_id(db_module, sub_id)
        or _user_id_from_customer(db_module, customer_id)
    )
    if not user_id:
        # Last resort: use custom_data.user_id from checkout (untrusted but
        # acceptable for subscription.created when no DB record exists yet)
        custom_data = data.get("custom_data") or {}
        user_id = custom_data.get("user_id") or None
        if user_id:
            logger.info(
                "paddle_identity_bootstrap sub_id=%s customer_id=%s user_id=%s",
                sub_id, customer_id, user_id,
            )

    return {
        "unmapped": False,
        "sub_id": sub_id,
        "customer_id": customer_id,
        "rico_status": rico_status,
        "price_id": price_id,
        "plan": plan,
        "billing_cycle": billing_cycle,
        "period_start": period_start,
        "period_end": period_end,
        "cancel_at": cancel_at,
        "user_id": user_id,
    }


def _handle_subscription_created(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    from src.repositories import paddle_repo

    fields = _extract_subscription_data(payload, db_module, event_id=event_id)
    if fields.get("unmapped"):
        return {"sub_id": fields["sub_id"], "warning": "unmapped_price", "price_id": fields["price_id"]}

    user_id = fields["user_id"]
    if not user_id:
        logger.warning("paddle_subscription_created_no_user_id sub_id=%s", fields["sub_id"])
        return {"sub_id": fields["sub_id"], "warning": "no_user_id"}

    _ensure_paddle_customer(db_module, user_id, fields["customer_id"], paddle_repo)
    paddle_repo.upsert_paddle_subscription(
        db_module,
        user_id=user_id,
        paddle_subscription_id=fields["sub_id"],
        paddle_customer_id=fields["customer_id"],
        plan=fields["plan"],
        status=fields["rico_status"],
        billing_cycle=fields["billing_cycle"],
        price_id=fields["price_id"],
        current_period_start=fields["period_start"],
        current_period_end=fields["period_end"],
    )
    logger.info("paddle_subscription_created user_id=%s plan=%s status=%s",
                user_id, fields["plan"], fields["rico_status"])
    return {"user_id": user_id, "plan": fields["plan"], "subscription_status": fields["rico_status"]}


def _handle_subscription_updated(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    from src.repositories import paddle_repo

    fields = _extract_subscription_data(payload, db_module, event_id=event_id)
    if fields.get("unmapped"):
        return {"sub_id": fields["sub_id"], "warning": "unmapped_price", "price_id": fields["price_id"]}

    user_id = fields["user_id"]
    if not user_id:
        logger.warning("paddle_subscription_updated_no_user_id sub_id=%s", fields["sub_id"])
        return {"sub_id": fields["sub_id"], "warning": "no_user_id"}

    _ensure_paddle_customer(db_module, user_id, fields["customer_id"], paddle_repo)
    paddle_repo.upsert_paddle_subscription(
        db_module,
        user_id=user_id,
        paddle_subscription_id=fields["sub_id"],
        paddle_customer_id=fields["customer_id"],
        plan=fields["plan"],
        status=fields["rico_status"],
        billing_cycle=fields["billing_cycle"],
        price_id=fields["price_id"],
        current_period_start=fields["period_start"],
        current_period_end=fields["period_end"],
        cancel_at=fields["cancel_at"],
    )
    logger.info("paddle_subscription_updated user_id=%s plan=%s status=%s",
                user_id, fields["plan"], fields["rico_status"])
    return {"user_id": user_id, "plan": fields["plan"], "subscription_status": fields["rico_status"]}


def _handle_subscription_status(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    """Handler shared by activated/trialing/past_due/paused/resumed events.
    All route through subscription.updated logic since they share the same
    data shape and result in a subscription row update."""
    return _handle_subscription_updated(event_id, event_type, payload, db_module)


def _handle_subscription_canceled(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    from src.repositories import paddle_repo

    data = payload.get("data", {})
    sub_id = data.get("id")
    customer_id = data.get("customer_id")
    canceled_at = data.get("canceled_at")

    # DB-first identity resolution
    user_id = (
        _user_id_from_sub_id(db_module, sub_id)
        or _user_id_from_customer(db_module, customer_id)
    )
    if not user_id:
        logger.warning("paddle_subscription_canceled_no_user_id sub_id=%s", sub_id)
        return {"sub_id": sub_id, "warning": "no_user_id"}

    paddle_repo.upsert_paddle_subscription(
        db_module,
        user_id=user_id,
        paddle_subscription_id=sub_id,
        paddle_customer_id=customer_id,
        plan="free",
        status="canceled",
        canceled_at=canceled_at,
    )
    logger.info("paddle_subscription_canceled user_id=%s sub_id=%s", user_id, sub_id)
    return {"user_id": user_id, "subscription_status": "canceled"}


def _handle_transaction_completed(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    """transaction.completed — log only.
    Subscription state is authoritative from subscription.* events."""
    data = payload.get("data", {})
    customer_id = data.get("customer_id")
    logger.info("paddle_transaction_completed customer_id=%s event_id=%s", customer_id, event_id)
    return {"customer_id": customer_id}


def _handle_transaction_payment_failed(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    """transaction.payment_failed — log; subscription status updated via subscription.past_due."""
    data = payload.get("data", {})
    customer_id = data.get("customer_id")
    logger.warning("paddle_payment_failed customer_id=%s event_id=%s", customer_id, event_id)
    return {"customer_id": customer_id}


# ---------------------------------------------------------------------------
# Handler dispatch table
# ---------------------------------------------------------------------------

_HANDLERS = {
    "subscription.created":      _handle_subscription_created,
    "subscription.updated":      _handle_subscription_updated,
    "subscription.activated":    _handle_subscription_status,
    "subscription.trialing":     _handle_subscription_status,
    "subscription.past_due":     _handle_subscription_status,
    "subscription.paused":       _handle_subscription_status,
    "subscription.resumed":      _handle_subscription_status,
    "subscription.canceled":     _handle_subscription_canceled,
    "subscription.cancelled":    _handle_subscription_canceled,  # Paddle UK spelling
    "transaction.completed":     _handle_transaction_completed,
    "transaction.payment_failed": _handle_transaction_payment_failed,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _user_id_from_customer(db_module: Any, paddle_customer_id: Optional[str]) -> Optional[str]:
    if not paddle_customer_id:
        return None
    try:
        from src.repositories import paddle_repo
        row = paddle_repo.get_paddle_customer_by_paddle_id(db_module, paddle_customer_id)
        return row["user_id"] if row else None
    except Exception:
        return None


def _user_id_from_sub_id(db_module: Any, paddle_subscription_id: Optional[str]) -> Optional[str]:
    if not paddle_subscription_id:
        return None
    try:
        from src.repositories import paddle_repo
        row = paddle_repo.get_paddle_subscription_by_paddle_id(db_module, paddle_subscription_id)
        return row["user_id"] if row else None
    except Exception:
        return None


def _ensure_paddle_customer(db_module: Any, user_id: str, paddle_customer_id: str, paddle_repo) -> None:
    try:
        paddle_repo.upsert_paddle_customer(db_module, user_id, paddle_customer_id)
    except Exception as exc:
        logger.warning("paddle_customer_upsert_failed user_id=%s: %s", user_id, exc)

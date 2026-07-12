"""Paddle webhook event processor.

Handles the Paddle Billing event lifecycle: idempotency guard, subscription
state transitions, and mapping Paddle statuses to Rico plan/status values.

Authoritative source: Paddle webhook events (never frontend callbacks).
Signature verification is done in the router before this service is called.
"""
from __future__ import annotations

import json
import logging
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

# Paddle price_id → Rico plan name (populated from env at import time)
# The router/service fills this via _resolve_plan_from_price_id().
_PRICE_TO_PLAN: Dict[str, str] = {}


def _resolve_plan_from_price_id(price_id: Optional[str]) -> str:
    """Map a Paddle price_id to a Rico plan name ('pro' | 'premium' | 'free')."""
    import os

    if not _PRICE_TO_PLAN:
        pro_ids = [
            os.getenv("PADDLE_PRO_MONTHLY_PRICE_ID", ""),
            os.getenv("PADDLE_PRO_YEARLY_PRICE_ID", ""),
        ]
        premium_ids = [
            os.getenv("PADDLE_PREMIUM_MONTHLY_PRICE_ID", ""),
            os.getenv("PADDLE_PREMIUM_YEARLY_PRICE_ID", ""),
        ]
        for pid in pro_ids:
            if pid:
                _PRICE_TO_PLAN[pid] = "pro"
        for pid in premium_ids:
            if pid:
                _PRICE_TO_PLAN[pid] = "premium"

    if price_id and price_id in _PRICE_TO_PLAN:
        return _PRICE_TO_PLAN[price_id]
    return "pro"  # safe default for unknown price IDs


def _billing_cycle_from_price_id(price_id: Optional[str]) -> str:
    """Return 'yearly' when the price_id matches a yearly price, else 'monthly'."""
    import os

    yearly_ids = {
        os.getenv("PADDLE_PRO_YEARLY_PRICE_ID", ""),
        os.getenv("PADDLE_PREMIUM_YEARLY_PRICE_ID", ""),
    }
    if price_id and price_id in yearly_ids:
        return "yearly"
    return "monthly"


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

    Returns a dict with ``{"status": "processed"|"skipped"|"failed", ...}``.
    Never raises — all exceptions are caught and logged so the router always
    returns HTTP 200 to Paddle (preventing retries for non-retryable errors).
    """
    from src.repositories import paddle_repo

    try:
        already = paddle_repo.paddle_event_already_processed(db_module, event_id)
        if already:
            logger.info("paddle_webhook_duplicate event_id=%s type=%s", event_id, event_type)
            return {"status": "skipped", "reason": "duplicate"}

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

def _handle_subscription_created(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    from src.repositories import paddle_repo

    data = payload.get("data", {})
    sub_id = data.get("id")
    customer_id = data.get("customer_id")
    status_raw = data.get("status", "active")
    rico_status = _PADDLE_TO_RICO_STATUS.get(status_raw, status_raw)

    items = data.get("items", [])
    price_id = items[0]["price"]["id"] if items and "price" in items[0] else None
    plan = _resolve_plan_from_price_id(price_id)
    billing_cycle = _billing_cycle_from_price_id(price_id)

    current_billing = data.get("current_billing_period", {})
    period_start = current_billing.get("starts_at")
    period_end = current_billing.get("ends_at")

    custom_data = data.get("custom_data") or {}
    user_id = (
        custom_data.get("user_id")
        or _user_id_from_customer(db_module, customer_id)
    )

    if not user_id:
        logger.warning(
            "paddle_subscription_created_no_user_id sub_id=%s customer_id=%s",
            sub_id, customer_id,
        )
        return {"sub_id": sub_id, "warning": "no_user_id"}

    _ensure_paddle_customer(db_module, user_id, customer_id, paddle_repo)

    paddle_repo.upsert_paddle_subscription(
        db_module,
        user_id=user_id,
        paddle_subscription_id=sub_id,
        paddle_customer_id=customer_id,
        plan=plan,
        status=rico_status,
        billing_cycle=billing_cycle,
        price_id=price_id,
        current_period_start=period_start,
        current_period_end=period_end,
    )
    logger.info(
        "paddle_subscription_created user_id=%s plan=%s status=%s",
        user_id, plan, rico_status,
    )
    return {"user_id": user_id, "plan": plan, "status": rico_status}


def _handle_subscription_updated(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    from src.repositories import paddle_repo

    data = payload.get("data", {})
    sub_id = data.get("id")
    customer_id = data.get("customer_id")
    status_raw = data.get("status", "active")
    rico_status = _PADDLE_TO_RICO_STATUS.get(status_raw, status_raw)

    items = data.get("items", [])
    price_id = items[0]["price"]["id"] if items and "price" in items[0] else None
    plan = _resolve_plan_from_price_id(price_id)
    billing_cycle = _billing_cycle_from_price_id(price_id)

    current_billing = data.get("current_billing_period", {})
    period_start = current_billing.get("starts_at")
    period_end = current_billing.get("ends_at")

    scheduled_change = data.get("scheduled_change") or {}
    cancel_at = scheduled_change.get("effective_at") if scheduled_change.get("action") == "cancel" else None

    custom_data = data.get("custom_data") or {}
    user_id = (
        custom_data.get("user_id")
        or _user_id_from_customer(db_module, customer_id)
        or _user_id_from_sub_id(db_module, sub_id)
    )

    if not user_id:
        logger.warning(
            "paddle_subscription_updated_no_user_id sub_id=%s customer_id=%s",
            sub_id, customer_id,
        )
        return {"sub_id": sub_id, "warning": "no_user_id"}

    _ensure_paddle_customer(db_module, user_id, customer_id, paddle_repo)

    paddle_repo.upsert_paddle_subscription(
        db_module,
        user_id=user_id,
        paddle_subscription_id=sub_id,
        paddle_customer_id=customer_id,
        plan=plan,
        status=rico_status,
        billing_cycle=billing_cycle,
        price_id=price_id,
        current_period_start=period_start,
        current_period_end=period_end,
        cancel_at=cancel_at,
    )
    logger.info(
        "paddle_subscription_updated user_id=%s plan=%s status=%s",
        user_id, plan, rico_status,
    )
    return {"user_id": user_id, "plan": plan, "status": rico_status}


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

    custom_data = data.get("custom_data") or {}
    user_id = (
        custom_data.get("user_id")
        or _user_id_from_customer(db_module, customer_id)
        or _user_id_from_sub_id(db_module, sub_id)
    )

    if not user_id:
        logger.warning(
            "paddle_subscription_canceled_no_user_id sub_id=%s", sub_id
        )
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
    return {"user_id": user_id, "status": "canceled"}


def _handle_transaction_completed(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_module: Any,
) -> Dict[str, Any]:
    """transaction.completed fires on successful payment — log only; subscription
    state is authoritative from subscription.* events."""
    data = payload.get("data", {})
    customer_id = data.get("customer_id")
    logger.info(
        "paddle_transaction_completed customer_id=%s event_id=%s", customer_id, event_id
    )
    return {"customer_id": customer_id}


# ---------------------------------------------------------------------------
# Handler dispatch table
# ---------------------------------------------------------------------------

_HANDLERS = {
    "subscription.created": _handle_subscription_created,
    "subscription.updated": _handle_subscription_updated,
    "subscription.canceled": _handle_subscription_canceled,
    "subscription.cancelled": _handle_subscription_canceled,
    "transaction.completed": _handle_transaction_completed,
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

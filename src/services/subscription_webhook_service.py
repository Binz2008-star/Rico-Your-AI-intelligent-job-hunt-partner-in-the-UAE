"""src/services/subscription_webhook_service.py

Paddle Billing webhook event processing for subscription lifecycle management.

Idempotency flow:
  1. record_subscription_event() atomically claims the event with status='pending'
     via INSERT ON CONFLICT DO UPDATE WHERE status='failed'.
     - Returns True  → caller is the designated processor.
     - Returns False → skip (already 'processed', another worker is 'pending', or DB down).
  2. Handler runs.
  3. update_subscription_event_status() closes the event as 'processed' or 'failed'.
     Failed events are re-claimable by the next Paddle retry or internal replay.

Price ID → Rico plan mapping reads env vars at call time so no restart is
needed when price IDs are rotated.

Supported events (data is the Paddle webhook "data" object directly — Paddle's
envelope is {event_id, event_type, data}, unlike Stripe's nested data.object):
  transaction.completed        → activate subscription (initial checkout or renewal)
  transaction.payment_failed   → set past_due
  subscription.created         → sync new subscription state
  subscription.updated         → sync plan / status / period
  subscription.canceled        → mark canceled
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.repositories.subscription_repo import (
    get_subscription,
    get_subscription_by_paddle_customer,
    get_subscription_event_status,
    record_subscription_event,
    update_subscription_event_status,
    upsert_subscription,
)
from src.subscription_plans import PAID_PLANS

logger = logging.getLogger(__name__)

# ── Paddle status → Rico status ────────────────────────────────────────────────

_PADDLE_STATUS_MAP: dict[str, str] = {
    "active":    "active",
    "trialing":  "active",  # trial counts as active for entitlement purposes
    "past_due":  "past_due",
    "paused":    "inactive",
    "canceled":  "canceled",
}


def _paddle_status(status: str) -> str:
    return _PADDLE_STATUS_MAP.get(status, "inactive")


# ── Price ID → plan name ──────────────────────────────────────────────────────

def _price_id_to_plan(price_id: str) -> str | None:
    """Map a Paddle price ID to 'pro' or 'premium' using env var config."""
    if not price_id:
        return None
    for env_name, plan in [
        ("PADDLE_PRO_PRICE_ID",     "pro"),
        ("PADDLE_PREMIUM_PRICE_ID", "premium"),
    ]:
        configured = os.getenv(env_name, "").strip()
        if configured and configured == price_id:
            return plan
    return None


# ── Extraction helpers ────────────────────────────────────────────────────────

def _extract_user_id(obj: dict[str, Any]) -> str | None:
    custom_data = obj.get("custom_data") or {}
    return custom_data.get("user_id") or None


def _extract_price_id(obj: dict[str, Any]) -> str | None:
    try:
        return obj["items"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def _parse_iso8601(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_period(obj: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    period = obj.get("current_billing_period") or {}
    return _parse_iso8601(period.get("starts_at")), _parse_iso8601(period.get("ends_at"))


def _resolve_user_id(obj: dict[str, Any]) -> str | None:
    """Return user_id from custom_data, or fall back to customer-ID DB lookup."""
    user_id = _extract_user_id(obj)
    if user_id:
        return user_id
    customer_id = obj.get("customer_id")
    if customer_id:
        row = get_subscription_by_paddle_customer(customer_id)
        if row:
            return row["user_id"]
    return None


def _subscription_matches_transaction(existing: dict[str, Any], obj: dict[str, Any]) -> bool:
    transaction_subscription_id = obj.get("subscription_id")
    stored_subscription_id = existing.get("paddle_subscription_id")
    return bool(
        transaction_subscription_id
        and stored_subscription_id
        and transaction_subscription_id == stored_subscription_id
    )


# ── Event handlers ────────────────────────────────────────────────────────────

def _handle_transaction_completed(obj: dict[str, Any]) -> bool:
    """transaction.completed — payment confirmed (initial checkout or renewal)."""
    customer_id = obj.get("customer_id")
    subscription_id = obj.get("subscription_id")

    user_id = _resolve_user_id(obj)
    if not user_id:
        logger.warning("webhook: transaction.completed missing user_id customer=%s", customer_id)
        return False

    custom_data = obj.get("custom_data") or {}
    plan = custom_data.get("plan")
    if plan not in ("pro", "premium"):
        plan = _price_id_to_plan(_extract_price_id(obj) or "")
    if plan not in ("pro", "premium"):
        existing = get_subscription_by_paddle_customer(customer_id) if customer_id else None
        plan = existing["plan"] if existing and existing.get("plan") in ("pro", "premium") else None
    if plan not in PAID_PLANS:
        logger.warning("webhook: transaction.completed unknown plan=%r user_id=%s", plan, user_id)
        return False

    existing = get_subscription_by_paddle_customer(customer_id) if customer_id else None
    if (
        existing
        and existing.get("paddle_subscription_id") == subscription_id
        and existing.get("status") not in (None, "active")
    ):
        logger.info(
            "webhook: transaction completed ignored stale active write user_id=%s subscription=%s status=%s",
            user_id, subscription_id, existing.get("status"),
        )
        return True

    row = upsert_subscription(
        user_id,
        plan=plan,
        status="active",
        paddle_customer_id=customer_id,
        paddle_subscription_id=subscription_id,
    )
    if row is None:
        logger.warning("webhook: transaction completed upsert failed user_id=%s", user_id)
        return False
    logger.info("webhook: transaction completed user_id=%s plan=%s", user_id, plan)
    return True


def _handle_transaction_payment_failed(obj: dict[str, Any]) -> bool:
    """transaction.payment_failed — renewal payment failed, set past_due."""
    customer_id = obj.get("customer_id")
    if not customer_id:
        return False

    existing = get_subscription_by_paddle_customer(customer_id)
    if not existing:
        # Permanent skip: no subscription row for this customer yet. Paddle
        # ordering guarantees transaction.completed precedes renewal failures,
        # so this means a customer whose checkout we never processed.
        logger.warning(
            "webhook: transaction.payment_failed no subscription found for customer=%s — skipping permanently",
            customer_id,
        )
        return True
    if not _subscription_matches_transaction(existing, obj):
        logger.info(
            "webhook: transaction.payment_failed ignored non-matching subscription customer=%s",
            customer_id,
        )
        return True

    row = upsert_subscription(existing["user_id"], plan=existing["plan"], status="past_due")
    if row is None:
        logger.warning("webhook: transaction.payment_failed upsert failed user_id=%s", existing["user_id"])
        return False
    logger.info("webhook: transaction.payment_failed user_id=%s", existing["user_id"])
    return True


def _handle_subscription_upsert(obj: dict[str, Any]) -> bool:
    """subscription.created/updated — sync plan, status, and period."""
    user_id = _resolve_user_id(obj)
    if not user_id:
        logger.warning("webhook: subscription event missing user_id customer=%s", obj.get("customer_id"))
        return False

    # Paddle item price is authoritative for upgrades/downgrades. custom_data is only a fallback.
    custom_data = obj.get("custom_data") or {}
    plan = _price_id_to_plan(_extract_price_id(obj) or "")
    if plan not in ("pro", "premium"):
        plan = custom_data.get("plan")
    if not plan:
        logger.warning("webhook: cannot determine plan user_id=%s", user_id)
        return False

    status = _paddle_status(obj.get("status", ""))
    period_start, period_end = _extract_period(obj)

    row = upsert_subscription(
        user_id,
        plan=plan,
        status=status,
        paddle_customer_id=obj.get("customer_id"),
        paddle_subscription_id=obj.get("id"),
        current_period_start=period_start,
        current_period_end=period_end,
    )
    if row is None:
        logger.warning("webhook: subscription upsert failed user_id=%s", user_id)
        return False
    logger.info("webhook: subscription upserted user_id=%s plan=%s status=%s", user_id, plan, status)
    return True


def _handle_subscription_canceled(obj: dict[str, Any]) -> bool:
    """subscription.canceled — mark canceled, preserve plan label."""
    user_id = _resolve_user_id(obj)
    if not user_id:
        logger.warning("webhook: subscription.canceled missing user_id customer=%s", obj.get("customer_id"))
        return False

    existing = get_subscription(user_id)
    plan = existing["plan"] if existing else "free"

    row = upsert_subscription(
        user_id,
        plan=plan,
        status="canceled",
    )
    if row is None:
        logger.warning("webhook: subscription canceled upsert failed user_id=%s", user_id)
        return False
    logger.info("webhook: subscription canceled user_id=%s", user_id)
    return True


# ── Public dispatcher ─────────────────────────────────────────────────────────

_HANDLERS = {
    "transaction.completed":       _handle_transaction_completed,
    "transaction.payment_failed":  _handle_transaction_payment_failed,
    "subscription.created":        _handle_subscription_upsert,
    "subscription.updated":        _handle_subscription_upsert,
    "subscription.canceled":       _handle_subscription_canceled,
}


def process_paddle_event(
    event_id: str,
    event_type: str,
    event_data: dict[str, Any],
) -> bool:
    """Idempotently process a verified Paddle webhook event.

    Returns True  → event newly claimed and handler succeeded, OR event was
                    already processed (idempotent ack), OR another worker is
                    in-flight (avoid Paddle retry storm).
    Returns False → handler failed/raised, event is 'failed' and re-claimable,
                    or DB is unavailable.

    On handler failure the event is marked 'failed' so the next Paddle retry
    (or an internal replay) can re-claim and re-run it. Paddle always gets 200;
    retries are driven by our internal failed-event state, not HTTP status.
    """
    obj = event_data.get("data", {})
    user_id = _extract_user_id(obj)

    claimed = record_subscription_event(
        event_id, event_type, user_id=user_id, payload=event_data
    )
    if not claimed:
        status = get_subscription_event_status(event_id)
        if status == "processed":
            logger.info("webhook: event skipped (already processed) event_id=%s", event_id)
            return True
        if status == "pending":
            logger.info("webhook: event skipped (already in-flight) event_id=%s", event_id)
            return True
        if status == "failed":
            logger.info("webhook: event skipped (failed, retryable) event_id=%s", event_id)
            return False
        logger.info("webhook: event skipped (DB unavailable or unknown status) event_id=%s status=%s", event_id, status)
        return False

    handler = _HANDLERS.get(event_type)
    if handler is None:
        update_subscription_event_status(event_id, "processed")
        logger.info("webhook: unhandled event_type=%s event_id=%s", event_type, event_id)
        return True

    try:
        result = handler(obj)
        if result:
            if not update_subscription_event_status(event_id, "processed"):
                logger.warning("webhook: failed to mark event processed event_id=%s", event_id)
                return False
        else:
            update_subscription_event_status(event_id, "failed", error_detail="handler returned false")
        return result
    except Exception as exc:
        logger.exception("webhook: handler failed event_id=%s type=%s", event_id, event_type)
        update_subscription_event_status(event_id, "failed", error_detail=str(exc))
        return False

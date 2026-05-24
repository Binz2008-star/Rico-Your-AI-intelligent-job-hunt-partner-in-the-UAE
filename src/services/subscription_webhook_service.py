"""src/services/subscription_webhook_service.py

Stripe webhook event processing for subscription lifecycle management.

Idempotency flow:
  1. record_subscription_event() atomically claims the event with status='pending'
     via INSERT ON CONFLICT DO UPDATE WHERE status='failed'.
     - Returns True  → caller is the designated processor.
     - Returns False → skip (already 'processed', another worker is 'pending', or DB down).
  2. Handler runs.
  3. update_subscription_event_status() closes the event as 'processed' or 'failed'.
     Failed events are re-claimable by the next Stripe retry or internal replay.

Price ID → Rico plan mapping reads env vars at call time so no restart is
needed when price IDs are rotated.

Supported events:
  checkout.session.completed          → create active subscription
  customer.subscription.created       → sync new subscription state
  customer.subscription.updated       → sync plan / status / period
  customer.subscription.deleted       → mark canceled
  invoice.paid                        → confirm active + update period dates
  invoice.payment_failed              → set past_due
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.repositories.subscription_repo import (
    get_subscription,
    get_subscription_by_stripe_customer,
    get_subscription_event_status,
    record_subscription_event,
    update_subscription_event_status,
    upsert_subscription,
)
from src.subscription_plans import PAID_PLANS

logger = logging.getLogger(__name__)

# ── Stripe status → Rico status ───────────────────────────────────────────────

_STRIPE_STATUS_MAP: dict[str, str] = {
    "active":             "active",
    "trialing":           "active",    # trial counts as active for entitlement purposes
    "past_due":           "past_due",
    "canceled":           "canceled",
    "cancelled":          "canceled",  # Stripe uses both spellings
    "incomplete":         "inactive",
    "incomplete_expired": "inactive",
    "unpaid":             "past_due",
    "paused":             "inactive",
}


def _stripe_status(stripe_status: str) -> str:
    return _STRIPE_STATUS_MAP.get(stripe_status, "inactive")


# ── Price ID → plan name ──────────────────────────────────────────────────────

def _price_id_to_plan(price_id: str) -> str | None:
    """Map a Stripe price ID to 'pro' or 'premium' using env var config."""
    if not price_id:
        return None
    for env_primary, env_legacy, plan in [
        ("STRIPE_PRO_PRICE_ID",     "STRIPE_PRICE_PRO",     "pro"),
        ("STRIPE_PREMIUM_PRICE_ID", "STRIPE_PRICE_PREMIUM", "premium"),
    ]:
        for env in (env_primary, env_legacy):
            configured = os.getenv(env, "").strip()
            if configured and configured == price_id:
                return plan
    return None


# ── Extraction helpers ────────────────────────────────────────────────────────

def _extract_user_id(obj: dict[str, Any]) -> str | None:
    meta = obj.get("metadata") or {}
    return meta.get("user_id") or None


def _extract_price_id(obj: dict[str, Any]) -> str | None:
    try:
        return obj["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def _extract_period(obj: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    def _ts(v: Any) -> datetime | None:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        return None

    return _ts(obj.get("current_period_start")), _ts(obj.get("current_period_end"))


def _resolve_user_id(obj: dict[str, Any]) -> str | None:
    """Return user_id from metadata, or fall back to customer-ID DB lookup."""
    user_id = _extract_user_id(obj)
    if user_id:
        return user_id
    customer_id = obj.get("customer")
    if customer_id:
        row = get_subscription_by_stripe_customer(customer_id)
        if row:
            return row["user_id"]
    return None


def _subscription_matches_invoice(existing: dict[str, Any], obj: dict[str, Any]) -> bool:
    invoice_subscription_id = obj.get("subscription")
    stored_subscription_id = existing.get("stripe_subscription_id")
    return bool(invoice_subscription_id and stored_subscription_id and invoice_subscription_id == stored_subscription_id)


# ── Event handlers ────────────────────────────────────────────────────────────

def _handle_checkout_completed(obj: dict[str, Any]) -> bool:
    """checkout.session.completed — payment confirmed, activate subscription."""
    user_id = _extract_user_id(obj)
    if not user_id:
        logger.warning("webhook: checkout.session.completed missing user_id")
        return False

    meta = obj.get("metadata") or {}
    plan = meta.get("plan")
    if plan not in ("pro", "premium"):
        logger.warning("webhook: checkout.session.completed unknown plan=%r user_id=%s", plan, user_id)
        return False

    plan_obj = PAID_PLANS.get(plan)
    if not plan_obj:
        logger.warning("webhook: checkout.session.completed plan not found=%r user_id=%s", plan, user_id)
        return False

    customer_id = obj.get("customer")
    subscription_id = obj.get("subscription")
    existing = get_subscription_by_stripe_customer(customer_id) if customer_id else None
    if (
        existing
        and existing.get("stripe_subscription_id") == subscription_id
        and existing.get("status") not in (None, "active")
    ):
        logger.info(
            "webhook: checkout completed ignored stale active write user_id=%s subscription=%s status=%s",
            user_id,
            subscription_id,
            existing.get("status"),
        )
        return True

    row = upsert_subscription(
        user_id,
        plan=plan,
        status="active",
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
    )
    if row is None:
        logger.warning("webhook: checkout completed upsert failed user_id=%s", user_id)
        return False
    logger.info("webhook: checkout completed user_id=%s plan=%s", user_id, plan)
    return True


def _handle_subscription_upsert(obj: dict[str, Any]) -> bool:
    """customer.subscription.created/updated — sync plan, status, and period."""
    user_id = _resolve_user_id(obj)
    if not user_id:
        logger.warning("webhook: subscription event missing user_id customer=%s", obj.get("customer"))
        return False

    # Stripe item price is authoritative for upgrades/downgrades. Metadata is only a fallback.
    meta = obj.get("metadata") or {}
    plan = _price_id_to_plan(_extract_price_id(obj) or "")
    if plan not in ("pro", "premium"):
        plan = meta.get("plan")
    if not plan:
        logger.warning("webhook: cannot determine plan user_id=%s", user_id)
        return False

    status = _stripe_status(obj.get("status", ""))
    period_start, period_end = _extract_period(obj)
    
    row = upsert_subscription(
        user_id,
        plan=plan,
        status=status,
        stripe_customer_id=obj.get("customer"),
        stripe_subscription_id=obj.get("id"),
        current_period_start=period_start,
        current_period_end=period_end,
    )
    if row is None:
        logger.warning("webhook: subscription upsert failed user_id=%s", user_id)
        return False
    logger.info("webhook: subscription upserted user_id=%s plan=%s status=%s", user_id, plan, status)
    return True


def _handle_subscription_deleted(obj: dict[str, Any]) -> bool:
    """customer.subscription.deleted — mark canceled, preserve plan label."""
    user_id = _resolve_user_id(obj)
    if not user_id:
        logger.warning("webhook: subscription.deleted missing user_id customer=%s", obj.get("customer"))
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


def _handle_invoice_paid(obj: dict[str, Any]) -> bool:
    """invoice.paid — confirm active status and refresh billing period."""
    customer_id = obj.get("customer")
    if not customer_id:
        return False

    existing = get_subscription_by_stripe_customer(customer_id)
    if not existing:
        logger.info("webhook: invoice.paid no subscription found customer=%s", customer_id)
        return False
    if not _subscription_matches_invoice(existing, obj):
        logger.info(
            "webhook: invoice.paid ignored non-matching subscription customer=%s invoice_subscription=%s stored_subscription=%s",
            customer_id,
            obj.get("subscription"),
            existing.get("stripe_subscription_id"),
        )
        return True

    # Extract period from first invoice line
    period_start = period_end = None
    try:
        lines = obj.get("lines", {}).get("data", [])
        if lines:
            period = lines[0].get("period", {})
            if isinstance(period.get("start"), (int, float)):
                period_start = datetime.fromtimestamp(period["start"], tz=timezone.utc)
            if isinstance(period.get("end"), (int, float)):
                period_end = datetime.fromtimestamp(period["end"], tz=timezone.utc)
    except Exception:
        pass

    row = upsert_subscription(
        existing["user_id"],
        plan=existing["plan"],
        status="active",
        current_period_start=period_start,
        current_period_end=period_end,
    )
    if row is None:
        logger.warning("webhook: invoice.paid upsert failed user_id=%s", existing["user_id"])
        return False
    logger.info("webhook: invoice.paid user_id=%s", existing["user_id"])
    return True


def _handle_invoice_payment_failed(obj: dict[str, Any]) -> bool:
    """invoice.payment_failed — set subscription to past_due."""
    customer_id = obj.get("customer")
    if not customer_id:
        return False

    existing = get_subscription_by_stripe_customer(customer_id)
    if not existing:
        logger.info("webhook: invoice.payment_failed no subscription found customer=%s", customer_id)
        return False
    if not _subscription_matches_invoice(existing, obj):
        logger.info(
            "webhook: invoice.payment_failed ignored non-matching subscription customer=%s invoice_subscription=%s stored_subscription=%s",
            customer_id,
            obj.get("subscription"),
            existing.get("stripe_subscription_id"),
        )
        return True

    row = upsert_subscription(existing["user_id"], plan=existing["plan"], status="past_due")
    if row is None:
        logger.warning("webhook: invoice.payment_failed upsert failed user_id=%s", existing["user_id"])
        return False
    logger.info("webhook: invoice.payment_failed user_id=%s", existing["user_id"])
    return True


# ── Public dispatcher ─────────────────────────────────────────────────────────

_HANDLERS = {
    "checkout.session.completed":       _handle_checkout_completed,
    "customer.subscription.created":    _handle_subscription_upsert,
    "customer.subscription.updated":    _handle_subscription_upsert,
    "customer.subscription.deleted":    _handle_subscription_deleted,
    "invoice.paid":                     _handle_invoice_paid,
    "invoice.payment_failed":           _handle_invoice_payment_failed,
}


def process_stripe_event(
    event_id: str,
    event_type: str,
    event_data: dict[str, Any],
) -> bool:
    """Idempotently process a verified Stripe webhook event.

    Returns True  → event newly claimed and handler succeeded, OR event was
                    already processed (idempotent ack), OR another worker is
                    in-flight (avoid Stripe retry storm).
    Returns False → handler failed/raised, event is 'failed' and re-claimable,
                    or DB is unavailable.

    On handler failure the event is marked 'failed' so the next Stripe retry
    (or an internal replay) can re-claim and re-run it. Stripe always gets 200;
    retries are driven by our internal failed-event state, not HTTP status.
    """
    obj = event_data.get("object", {})
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

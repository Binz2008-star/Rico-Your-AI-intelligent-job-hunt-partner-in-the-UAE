"""FastAPI router for Paddle Billing endpoints.

Endpoints:
  POST /api/v1/billing/paddle/webhook   — Paddle webhook receiver (no auth, raw body)
  GET  /api/v1/billing/status           — Current Paddle subscription status (auth required)
  POST /api/v1/billing/customer-portal  — Generate Paddle customer portal URL (auth required)

PADDLE_API_KEY is read server-side only and NEVER returned to the client.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.api.deps import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["paddle-billing"])
payload_router = router  # alias used by tests
paddle_billing_router = router  # canonical name imported by app.py

_PADDLE_TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Unauthenticated config endpoint — safe for smoke-test health checks
# ---------------------------------------------------------------------------

@router.get("/config")
async def billing_config() -> Dict[str, Any]:
    """Return public billing configuration. No auth required, no secrets exposed.

    Used by smoke tests and the frontend to confirm the billing mode is active
    before attempting an authenticated checkout. Returns only non-secret flags.
    """
    from src.billing_mode import is_paddle_billing_mode
    sandbox = os.getenv("PADDLE_SANDBOX", "true").strip().lower() != "false"
    return {
        "billing_mode": "paddle" if is_paddle_billing_mode() else os.getenv("BILLING_MODE", "manual"),
        "paddle_active": is_paddle_billing_mode(),
        "sandbox": sandbox,
    }


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_paddle_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    *,
    _test_mode: bool = False,
) -> bool:
    """Verify Paddle-Signature header against the exact raw request body.

    Header format: ts=<unix_seconds>;h1=<hex-hmac-sha256>

    Security guarantees:
    - PADDLE_WEBHOOK_SECRET missing → FAIL CLOSED (returns False).
      Exception: _test_mode=True skips the check (unit tests only).
    - Timestamp must be within _PADDLE_TIMESTAMP_TOLERANCE_SECONDS of now.
    - HMAC is computed over "<ts>:<raw_body>" as specified by Paddle.
    - Comparison uses hmac.compare_digest to prevent timing attacks.
    """
    secret = os.getenv("PADDLE_WEBHOOK_SECRET", "").strip()
    if not secret:
        if _test_mode:
            return True
        logger.error("paddle_sig_fail: PADDLE_WEBHOOK_SECRET not configured — rejecting webhook")
        return False

    if not signature_header:
        return False

    ts_match = re.search(r"ts=(\d+)", signature_header)
    h1_match = re.search(r"h1=([0-9a-f]+)", signature_header)
    if not ts_match or not h1_match:
        return False

    ts_str = ts_match.group(1)
    received_hmac = h1_match.group(1)

    # Timestamp freshness check — prevents replay attacks
    try:
        ts_int = int(ts_str)
    except ValueError:
        return False
    age = abs(int(time.time()) - ts_int)
    if age > _PADDLE_TIMESTAMP_TOLERANCE_SECONDS:
        logger.warning("paddle_sig_stale ts=%s age=%ds", ts_str, age)
        return False

    # HMAC is over "<ts>:<raw_body>" — use raw bytes, not decoded string
    signed_payload = ts_str.encode("utf-8") + b":" + raw_body
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, received_hmac)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/paddle/webhook", include_in_schema=False)
async def paddle_webhook(request: Request) -> JSONResponse:
    """Receive and process Paddle webhook events.

    - Verifies Paddle-Signature against raw body.
    - Guards idempotency via paddle_webhook_events table.
    - Always returns 200 to Paddle (prevents unneeded retries for non-retryable errors).
    """
    raw_body = await request.body()
    sig_header = request.headers.get("Paddle-Signature")

    if not _verify_paddle_signature(raw_body, sig_header):
        logger.warning("paddle_webhook_invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paddle signature",
        )

    try:
        payload: Dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    event_id: str = payload.get("event_id", "")
    event_type: str = payload.get("event_type", "")

    if not event_id or not event_type:
        logger.warning("paddle_webhook_missing_fields payload_keys=%s", list(payload.keys()))
        return JSONResponse({"ok": False, "reason": "missing_event_id_or_type"}, status_code=200)

    try:
        import sys
        db_module = sys.modules.get("src.db") or __import__("src.db", fromlist=["get_db_connection"])
    except Exception:
        db_module = None

    if db_module is None:
        logger.error("paddle_webhook_no_db event_id=%s — returning 503 so Paddle will retry", event_id)
        # Return 503 (not 200) — Paddle will retry, preserving durability
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    from src.services.paddle_webhook_service import process_paddle_webhook

    result = process_paddle_webhook(
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        db_module=db_module,
    )

    processing_status = result.get("status")
    logger.info(
        "paddle_webhook_done event_id=%s type=%s result=%s",
        event_id, event_type, processing_status,
    )

    if processing_status == "failed":
        # Return 500 so Paddle retries the event — the event row is already
        # recorded in paddle_webhook_events with status='failed' for replay.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed; Paddle should retry",
        )

    return JSONResponse({"ok": True, **result}, status_code=200)


# ---------------------------------------------------------------------------
# Billing status endpoint
# ---------------------------------------------------------------------------

@router.get("/status")
async def billing_status(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Return the authenticated user's current Paddle subscription status.

    Falls back to free plan when no Paddle subscription exists.
    """
    try:
        import sys
        db_module = sys.modules.get("src.db") or __import__("src.db", fromlist=["get_db_connection"])
    except Exception:
        db_module = None

    if db_module is None:
        return _free_status(user_id)

    try:
        from src.repositories.paddle_repo import get_paddle_subscription_by_user
        row = get_paddle_subscription_by_user(db_module, user_id)
    except Exception as exc:
        logger.warning("billing_status_db_error user_id=%s: %s", user_id, exc)
        return _free_status(user_id)

    if not row:
        return _free_status(user_id)

    return {
        "user_id": user_id,
        "plan": row.get("plan", "free"),
        "status": row.get("status", "inactive"),
        "billing_cycle": row.get("billing_cycle", "monthly"),
        "current_period_start": _isoformat(row.get("current_period_start")),
        "current_period_end": _isoformat(row.get("current_period_end")),
        "cancel_at": _isoformat(row.get("cancel_at")),
        "canceled_at": _isoformat(row.get("canceled_at")),
        "paddle_subscription_id": row.get("paddle_subscription_id"),
        "provider": "paddle",
    }


def _free_status(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "plan": "free",
        "status": "inactive",
        "billing_cycle": None,
        "current_period_start": None,
        "current_period_end": None,
        "cancel_at": None,
        "canceled_at": None,
        "paddle_subscription_id": None,
        "provider": "paddle",
    }


def _isoformat(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Checkout session endpoint (server-owned checkout attribution)
# ---------------------------------------------------------------------------

@router.post("/paddle/checkout-session")
async def create_checkout_session(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Create a server-owned checkout session correlation record.

    Returns a ``session_token`` that the frontend passes as
    ``custom_data.checkout_session_id`` in the Paddle.js checkout overlay.
    The webhook resolves the Rico user via this DB record — never via
    browser-supplied ``custom_data.user_id``.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    plan = body.get("plan", "").strip()
    billing_cycle = body.get("billing_cycle", "monthly").strip()

    if plan not in ("pro",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported plan: {plan!r}. Allowed: pro",
        )
    if billing_cycle != "monthly":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported billing_cycle: {billing_cycle!r}. Allowed: monthly",
        )

    session_token = secrets.token_urlsafe(32)

    try:
        import sys
        db_module = sys.modules.get("src.db") or __import__("src.db", fromlist=["get_db_connection"])
        from src.repositories.paddle_repo import create_checkout_session as _create
        _create(
            db_module,
            user_id=user_id,
            plan=plan,
            billing_cycle=billing_cycle,
            session_token=session_token,
        )
    except Exception as exc:
        logger.error("checkout_session_create_error user_id=%s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create checkout session",
        )

    price_id = _resolve_price_id(plan, billing_cycle)
    return {
        "session_token": session_token,
        "price_id": price_id,
        "plan": plan,
        "billing_cycle": billing_cycle,
    }


def _resolve_price_id(plan: str, billing_cycle: str) -> Optional[str]:
    """Return the Paddle price_id for the given plan/cycle, or None."""
    if plan == "pro" and billing_cycle == "monthly":
        return os.getenv("PADDLE_PRO_MONTHLY_PRICE_ID", "").strip() or None
    return None


# ---------------------------------------------------------------------------
# Customer portal endpoint
# ---------------------------------------------------------------------------

@router.post("/customer-portal")
async def customer_portal(user_id: str = Depends(get_current_user_id)) -> Dict[str, Any]:
    """Generate a Paddle customer portal URL for the authenticated user.

    Uses the Paddle API (server-side key only) to create a customer portal
    transaction. Never exposes PADDLE_API_KEY to the client.
    """
    api_key = os.getenv("PADDLE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing portal is not configured",
        )

    try:
        import sys
        db_module = sys.modules.get("src.db") or __import__("src.db", fromlist=["get_db_connection"])
        from src.repositories.paddle_repo import get_paddle_subscription_by_user
        row = get_paddle_subscription_by_user(db_module, user_id)
    except Exception as exc:
        logger.warning("customer_portal_db_error user_id=%s: %s", user_id, exc)
        row = None

    if not row or not row.get("paddle_subscription_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Paddle subscription found",
        )

    paddle_customer_id = row.get("paddle_customer_id")
    sub_id = row["paddle_subscription_id"]

    if not paddle_customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Paddle customer record found",
        )

    sandbox = os.getenv("PADDLE_SANDBOX", "true").strip().lower() != "false"
    base_url = (
        "https://sandbox-api.paddle.com"
        if sandbox
        else "https://api.paddle.com"
    )

    try:
        import urllib.request

        # Correct Paddle API: POST /customers/{customer_id}/portal-sessions
        # body: {"subscription_ids": ["sub_..."]}
        req_body = json.dumps({"subscription_ids": [sub_id]}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/customers/{paddle_customer_id}/portal-sessions",
            data=req_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))

        urls = resp_body.get("data", {}).get("urls", {})
        portal_url = (
            urls.get("general", {}).get("overview")
            or urls.get("general", {}).get("payment_method_update")
            or urls.get("general", {}).get("cancel_subscription")
        )
        if not portal_url:
            raise ValueError("No portal URL in Paddle response")

        return {"portal_url": portal_url}

    except Exception as exc:
        logger.error("customer_portal_paddle_api_error user_id=%s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create billing portal session",
        )

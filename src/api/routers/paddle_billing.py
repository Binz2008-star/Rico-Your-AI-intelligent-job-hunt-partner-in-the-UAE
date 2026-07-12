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
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.api.deps import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["paddle-billing"])


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_paddle_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Verify Paddle-Signature header against raw request body.

    Header format: ts=<timestamp>;h1=<hex-hmac>
    PADDLE_WEBHOOK_SECRET must be set; if absent, verification is skipped
    (dev/test only — never skip in production).
    """
    secret = os.getenv("PADDLE_WEBHOOK_SECRET", "").strip()
    if not secret:
        logger.warning("paddle_sig_skip: PADDLE_WEBHOOK_SECRET not set — skipping verification")
        return True

    if not signature_header:
        return False

    ts_match = re.search(r"ts=(\d+)", signature_header)
    h1_match = re.search(r"h1=([0-9a-f]+)", signature_header)
    if not ts_match or not h1_match:
        return False

    ts = ts_match.group(1)
    received_hmac = h1_match.group(1)

    signed_payload = f"{ts}:{raw_body.decode('utf-8', errors='replace')}"
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
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
        from src.db import get_db_connection as _get_conn
        import sys
        db_module = sys.modules.get("src.db") or __import__("src.db", fromlist=["get_db_connection"])
    except Exception:
        db_module = None

    if db_module is None:
        logger.error("paddle_webhook_no_db event_id=%s", event_id)
        return JSONResponse({"ok": False, "reason": "db_unavailable"}, status_code=200)

    from src.services.paddle_webhook_service import process_paddle_webhook

    result = process_paddle_webhook(
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        db_module=db_module,
    )

    logger.info(
        "paddle_webhook_done event_id=%s type=%s result=%s",
        event_id, event_type, result.get("status"),
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

    sub_id = row["paddle_subscription_id"]
    sandbox = os.getenv("PADDLE_SANDBOX", "true").strip().lower() != "false"
    base_url = (
        "https://sandbox-api.paddle.com"
        if sandbox
        else "https://api.paddle.com"
    )

    try:
        import urllib.request

        req_body = json.dumps({"subscription_id": sub_id}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/customers/portal-sessions",
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

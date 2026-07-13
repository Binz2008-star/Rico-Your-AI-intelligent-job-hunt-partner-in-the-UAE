"""src/services/paddle_client.py

Paddle Billing REST API client used by src/subscription_plans.py.

Environment variables:
  PADDLE_API_KEY        -- server-side API key (Bearer auth)
  PADDLE_ENVIRONMENT     -- "sandbox" (default) or "production"
  PADDLE_WEBHOOK_SECRET  -- notification-destination secret for signature verification

Webhook signature scheme (Paddle-Signature header: "ts=<unix_ts>;h1=<hex_hmac>"):
  hash = HMAC-SHA256(webhook_secret, f"{ts}:{raw_body}")
Paddle recommends rejecting signatures whose timestamp is stale to guard
against replay; we allow a 5 minute window like Stripe's default tolerance.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 15
_SIGNATURE_TOLERANCE_S = 300


def _api_key() -> str:
    return os.getenv("PADDLE_API_KEY", "").strip()


def _base_url() -> str:
    environment = os.getenv("PADDLE_ENVIRONMENT", "sandbox").strip().lower()
    if environment == "production":
        return "https://api.paddle.com"
    return "https://sandbox-api.paddle.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def is_configured() -> bool:
    return bool(_api_key())


def create_transaction_checkout(
    *,
    price_id: str,
    user_id: str,
    plan: str,
    success_url: str,
) -> str:
    """Create a Paddle transaction and return its hosted checkout URL.

    Raises RuntimeError on any failure (missing config, HTTP error, or a
    response that doesn't include a checkout URL) — callers translate that
    into a user-facing error the same way the prior Stripe path did.
    """
    if not _api_key():
        raise RuntimeError("Paddle API key is not configured")

    resp = requests.post(
        f"{_base_url()}/transactions",
        json={
            "items": [{"price_id": price_id, "quantity": 1}],
            "custom_data": {"user_id": user_id, "plan": plan},
            "checkout": {"url": success_url},
        },
        headers=_headers(),
        timeout=_REQUEST_TIMEOUT,
    )
    if not resp.ok:
        logger.warning(
            "paddle_client: create_transaction failed status=%s body=%s",
            resp.status_code, resp.text[:500],
        )
        raise RuntimeError(f"Paddle transaction request failed (status {resp.status_code})")

    data = resp.json().get("data", {})
    checkout_url = (data.get("checkout") or {}).get("url")
    if not checkout_url:
        raise RuntimeError("Paddle transaction response did not include a checkout URL")
    return checkout_url


def verify_webhook_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify a Paddle-Signature header against the raw request body.

    Returns False (never raises) for any malformed header, mismatched hash,
    or stale timestamp — callers treat False as "reject the webhook".
    """
    if not signature_header or not secret:
        return False

    parts: dict[str, str] = {}
    for fragment in signature_header.split(";"):
        if "=" not in fragment:
            continue
        key, _, value = fragment.partition("=")
        parts[key.strip()] = value.strip()

    ts = parts.get("ts")
    h1 = parts.get("h1")
    if not ts or not h1:
        return False

    try:
        ts_int = int(ts)
    except ValueError:
        return False
    if abs(time.time() - ts_int) > _SIGNATURE_TOLERANCE_S:
        logger.warning("paddle_client: webhook signature timestamp outside tolerance")
        return False

    signed_payload = f"{ts}:{raw_body.decode('utf-8')}"
    expected = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, h1)

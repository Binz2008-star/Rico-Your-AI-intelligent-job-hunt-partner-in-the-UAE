"""WhatsApp-assisted subscription channel (DEC-20260719-003).

PRODUCT RULE: Paddle stays the primary automated payment provider. WhatsApp
is an ASSISTED/MANUAL subscription channel, not a payment processor. Nothing
in this router reads or writes entitlement: creating a request, opening
WhatsApp, sending a message, or uploading a screenshot NEVER activates a
subscription. Activation happens exclusively through the existing admin-only
manual path (POST /api/v1/admin/subscriptions/activate) after the owner
verifies payment out-of-band.

FAIL-CLOSED CONFIGURATION (server-controlled, never client-supplied):
  WHATSAPP_SUBSCRIPTIONS_ENABLED  — default false; anything but "true" is off
  WHATSAPP_SUBSCRIPTION_NUMBER    — E.164; missing/invalid disables the
                                    channel (Paddle is unaffected either way)

Endpoints:
  GET  /api/v1/billing/whatsapp/config             — public capability flag
  POST /api/v1/billing/whatsapp-subscription-request — authenticated; creates
       or reuses the user's single pending request and returns the sanitized
       wa.me URL with the prefilled message

Response NEVER contains: JWTs, secrets, database ids, profile/CV data. The
opaque request reference is the only correlation token.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.deps import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["whatsapp-billing"])
billing_whatsapp_router = router  # canonical name imported by app.py

# E.164: optional '+', 8–15 digits, no leading zero.
_E164_RE = re.compile(r"^\+?[1-9]\d{7,14}$")

_ALLOWED_LANGUAGES = ("en", "ar")

# Prefilled message templates — reference/plan/price ONLY. No email, no
# phone, no CV data, no credentials (owner-approved copy, 2026-07-19).
_MESSAGE_TEMPLATES = {
    "en": (
        "Hello Rico Support, I want to subscribe to Rico.\n"
        "Request reference: {reference}\n"
        "Plan: {plan}\n"
        "Price: {price} {currency}\n"
        "Please send me the verified payment instructions."
    ),
    "ar": (
        "مرحبًا فريق ريكو، أرغب بالاشتراك في ريكو.\n"
        "مرجع الطلب: {reference}\n"
        "الباقة: {plan}\n"
        "السعر: {price} {currency}\n"
        "يرجى إرسال تعليمات الدفع المعتمدة."
    ),
}


def _whatsapp_number() -> Optional[str]:
    """Validated subscription WhatsApp number as wa.me digits, or None.

    Never hard-coded: comes only from WHATSAPP_SUBSCRIPTION_NUMBER. An
    invalid value is treated as missing (fail closed) and logged once per
    call site without echoing the raw value length games — the number itself
    is not a secret but validation failures should be visible.
    """
    raw = os.getenv("WHATSAPP_SUBSCRIPTION_NUMBER", "").strip().replace(" ", "")
    if not raw:
        return None
    if not _E164_RE.match(raw):
        logger.warning("whatsapp_billing: WHATSAPP_SUBSCRIPTION_NUMBER is not valid E.164 — channel disabled")
        return None
    return raw.lstrip("+")


def _whatsapp_enabled() -> bool:
    return os.getenv("WHATSAPP_SUBSCRIPTIONS_ENABLED", "false").strip().lower() == "true"


def _whatsapp_active() -> bool:
    """True only when the flag is on AND a valid number is configured."""
    return _whatsapp_enabled() and _whatsapp_number() is not None


@router.get("/whatsapp/config")
async def whatsapp_billing_config() -> Dict[str, Any]:
    """Public capability flag for the assisted channel. Boolean only — the
    number and templates are returned exclusively by the authenticated
    request endpoint."""
    return {"whatsapp_active": _whatsapp_active()}


@router.post("/whatsapp-subscription-request")
async def create_whatsapp_subscription_request(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Create (or reuse) the authenticated user's pending assisted request.

    Server-authoritative: plan, price, and currency come from
    src/subscription_plans.py — any plan/price/currency fields in the browser
    body are ignored. The only accepted client field is ``language``
    ("en" | "ar", cosmetic, defaults to "en").

    Creating a request does NOT modify subscription tier or entitlement.
    """
    if not _whatsapp_active():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp subscription channel is not available",
        )

    number = _whatsapp_number()
    if not number:  # re-check between config read races — fail closed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp subscription channel is not available",
        )

    language = "en"
    try:
        body = await request.json()
        if isinstance(body, dict):
            candidate = str(body.get("language", "en")).strip().lower()
            if candidate in _ALLOWED_LANGUAGES:
                language = candidate
    except Exception:
        pass  # empty/invalid body → defaults; nothing else is client-supplied

    # SERVER-side plan snapshot — the single approved plan.
    from src.subscription_plans import RICO_MONTHLY_PLAN

    plan_name = RICO_MONTHLY_PLAN.name
    plan_key = RICO_MONTHLY_PLAN.plan.value if hasattr(RICO_MONTHLY_PLAN.plan, "value") else str(RICO_MONTHLY_PLAN.plan)
    price = float(RICO_MONTHLY_PLAN.price_monthly)
    currency = RICO_MONTHLY_PLAN.currency

    from src.repositories import whatsapp_requests_repo

    row = whatsapp_requests_repo.get_or_create_pending_request(
        user_id,
        plan=plan_key,
        price_usd=price,
        currency=currency,
        language=language,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create the subscription request. Please try again.",
        )

    message = _MESSAGE_TEMPLATES[language].format(
        reference=row["reference"],
        plan=plan_name,
        price=f"{price:.2f}",
        currency=currency,
    )
    whatsapp_url = f"https://wa.me/{number}?text={quote(message)}"

    # Log the opaque reference only — never the user id in clear, never the
    # full URL (it embeds the message text).
    logger.info("whatsapp_subscription_request reference=%s status=%s", row["reference"], row["status"])

    return {
        "reference": row["reference"],
        "status": row["status"],
        "plan": plan_name,
        "price": f"{price:.2f}",
        "currency": currency,
        "whatsapp_url": whatsapp_url,
        # Honest expectation-setting — activation is NOT automatic.
        "note_en": "Activation occurs after payment verification.",
        "note_ar": "يتم تفعيل الاشتراك بعد التحقق من الدفع.",
    }

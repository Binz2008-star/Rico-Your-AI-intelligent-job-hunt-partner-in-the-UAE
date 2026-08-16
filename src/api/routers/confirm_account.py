"""Out-of-band account confirmation endpoint (launch-blocker closure).

A Jotform submission matching an existing registered account is held pending
until the ACCOUNT OWNER proves mailbox possession via a single-use, time-limited
link. This endpoint consumes the token and applies the server-built pending
payload. Every invalid/expired/reused/mismatched token fails closed.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.rate_limit import LIMIT_VERIFY_EMAIL, limiter

router = APIRouter(prefix="/api/v1/confirm-account", tags=["account-confirmation"])


@router.get("")
@limiter.limit(LIMIT_VERIFY_EMAIL)
def confirm_account_get(
    request: Request,
    token: str = Query(..., min_length=8, max_length=200),
    purpose: Optional[str] = Query(None, max_length=40),
) -> dict:
    """Consume a confirmation token (email link click) and apply the payload.

    Returns a plain result; a browser link gets a readable page.
    """
    from src.services.account_confirmation_service import confirm_account

    purpose = (purpose or "").strip()
    if purpose not in ("jotform_merge",):
        raise HTTPException(status_code=422, detail="Unsupported confirmation purpose")

    result = confirm_account(token, purpose)
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail="Confirmation is invalid, expired, or already used")
    return {"status": "ok", "message": "Account confirmed and updated."}

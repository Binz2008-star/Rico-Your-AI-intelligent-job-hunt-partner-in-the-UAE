"""Public, consented waitlist intake for pre-launch mode."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from src.api.rate_limit import LIMIT_WAITLIST, limiter
from src.repositories.waitlist_repo import WaitlistUnavailable, upsert_waitlist_entry
from src.schemas.waitlist import WaitlistRegisterRequest, WaitlistRegisterResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/waitlist", tags=["waitlist"])


@router.post("/register", response_model=WaitlistRegisterResponse)
@limiter.limit(LIMIT_WAITLIST)
def register_waitlist(
    request: Request,
    payload: WaitlistRegisterRequest,
) -> WaitlistRegisterResponse:
    try:
        upsert_waitlist_entry(
            email=payload.email,
            first_name=payload.first_name,
            target_role=payload.target_role,
            location=payload.location,
            consent=payload.consent,
            source=payload.source,
        )
    except WaitlistUnavailable as exc:
        logger.warning("waitlist_register_unavailable")
        raise HTTPException(
            status_code=503,
            detail="Early-access registration is temporarily unavailable. Please try again.",
        ) from exc

    # Same response for new and repeated submissions; do not expose whether an
    # email address was already present.
    return WaitlistRegisterResponse(
        message="Your early-access request has been recorded.",
    )

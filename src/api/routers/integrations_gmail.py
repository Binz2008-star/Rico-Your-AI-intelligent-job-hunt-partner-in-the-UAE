"""
src/api/routers/integrations_gmail.py
HTTP layer for the Gmail read-only connector (M0).

Security contract (docs/integrations/gmail-readonly-connector.md §5):
  * Identity comes ONLY from the JWT cookie (get_current_user_id) — request
    body/query user ids are never read.
  * Exception: GET /callback is reached by a Google browser redirect that
    carries no Rico JWT; its identity comes from the signed short-lived
    ``state`` minted for the authenticated user by GET /connect
    (HMAC(JWT_SECRET), 10-minute expiry — see src/services/gmail_oauth.py).
  * POST /sync-all is server-to-server only, guarded by X-Cron-Secret
    (require_cron_secret), like the other pipeline sweeps.
  * Everything except /status, listing reads, and /disconnect returns 503
    while RICO_ENABLE_GMAIL_SYNC is off (default). /disconnect stays available
    so a user can always revoke access, even if the feature is turned off
    while they are connected.
  * Scope is gmail.readonly only — this router exposes no path that could
    send, delete, label, or modify email.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.api.deps import get_current_user_id, require_cron_secret
from src.api.rate_limit import LIMIT_INTEGRATIONS, LIMIT_INTEGRATIONS_SYNC, limiter
from src.repositories import gmail_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations/gmail", tags=["integrations"])


class RecurringSyncConsentBody(BaseModel):
    """Body for POST /consent. `granted` is the only field — identity is never
    read from the body (JWT-only)."""

    granted: bool

_NOT_ENABLED_DETAIL = (
    "Gmail sync is not enabled on this deployment (RICO_ENABLE_GMAIL_SYNC=false)."
)


def _require_enabled() -> None:
    from src.services.gmail_sync_service import gmail_sync_enabled

    if not gmail_sync_enabled():
        raise HTTPException(status_code=503, detail=_NOT_ENABLED_DETAIL)


def _frontend_settings_url(result: str) -> str:
    base = (
        os.getenv("FRONTEND_URL", "").strip()
        or os.getenv("RESET_BASE_URL", "").strip()
        or "https://ricohunt.com"
    ).rstrip("/")
    return f"{base}/settings?gmail={result}"


# ── Status ────────────────────────────────────────────────────────────────────


@router.get("/status")
@limiter.limit(LIMIT_INTEGRATIONS)
def gmail_status(
    request: Request, user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Truthful connection state for the current JWT user.

    Privacy/revocation contract (docs §3): the connection state is reported
    INDEPENDENTLY of the sync feature flag. A user who is connected must always
    be able to see that and revoke it, even while RICO_ENABLE_GMAIL_SYNC is off
    (the flag gates *sync*, not *visibility*). ``sync_enabled`` carries the flag
    so the UI can render "connected, sync currently disabled — you can
    disconnect". The encrypted refresh token is never included in the payload.
    """
    from src.services.gmail_sync_service import gmail_sync_enabled

    sync_enabled = gmail_sync_enabled()
    # Always resolve the real connection — never hide it behind the flag.
    connection = gmail_repo.get_connection(user_id)
    if not connection:
        return {
            "sync_enabled": sync_enabled,
            # Back-compat alias for older clients that read `enabled`.
            "enabled": sync_enabled,
            "connected": False,
            "provider_email": None,
            "scopes": [],
            "needs_reauth": False,
            "recurring_sync_consent": False,
            "last_sync_at": None,
        }
    return {
        "sync_enabled": sync_enabled,
        "enabled": sync_enabled,
        "connected": connection.get("status") == "active",
        "provider_email": connection.get("provider_account_email"),
        "scopes": connection.get("scopes") or [],
        "needs_reauth": connection.get("status") == "needs_reauth",
        "recurring_sync_consent": connection.get("recurring_sync_consent_at")
        is not None,
        "last_sync_at": (
            connection["last_sync_at"].isoformat()
            if connection.get("last_sync_at")
            else None
        ),
    }


# ── OAuth connect / callback / disconnect ─────────────────────────────────────


@router.get("/connect")
@limiter.limit(LIMIT_INTEGRATIONS)
def gmail_connect(
    request: Request, user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Start the OAuth web flow: returns the Google authorization URL
    (gmail.readonly only) with a signed state bound to the current user."""
    _require_enabled()
    from src.services.gmail_oauth import GmailOAuthError, build_auth_url, oauth_configured
    from src.services.token_crypto import encryption_key_present

    if not oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    if not encryption_key_present():
        raise HTTPException(
            status_code=503, detail="Token encryption is not configured."
        )
    try:
        auth_url = build_auth_url(user_id)
    except GmailOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    gmail_repo.insert_audit_event(user_id, "oauth_connect_started", "ok")
    return {"auth_url": auth_url}


@router.get("/callback")
@limiter.limit(LIMIT_INTEGRATIONS)
def gmail_callback(request: Request) -> RedirectResponse:
    """Google OAuth redirect target. Identity is derived from the signed state
    (see module docstring) — never from a query/body user id. Always redirects
    back to /settings with a success or error flag; token material never
    appears in the redirect."""
    from src.services.gmail_sync_service import gmail_sync_enabled

    if not gmail_sync_enabled():
        raise HTTPException(status_code=503, detail=_NOT_ENABLED_DETAIL)

    from src.services.gmail_oauth import GmailOAuthError, exchange_code, verify_state

    state = request.query_params.get("state") or ""
    user_id = verify_state(state)
    if not user_id:
        logger.warning("gmail_callback_invalid_state")
        return RedirectResponse(url=_frontend_settings_url("error"), status_code=302)

    if request.query_params.get("error"):
        # User denied consent at Google — no code to exchange.
        gmail_repo.insert_audit_event(
            user_id, "oauth_callback", "error", metadata={"reason": "consent_denied"}
        )
        return RedirectResponse(url=_frontend_settings_url("denied"), status_code=302)

    code = request.query_params.get("code") or ""
    try:
        exchange_code(user_id, code)
    except GmailOAuthError:
        logger.warning("gmail_callback_exchange_failed user_id=%s", user_id)
        return RedirectResponse(url=_frontend_settings_url("error"), status_code=302)
    return RedirectResponse(url=_frontend_settings_url("connected"), status_code=302)


@router.post("/disconnect")
@limiter.limit(LIMIT_INTEGRATIONS)
def gmail_disconnect(
    request: Request, user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    """Revoke at Google (best-effort) and tombstone the local connection.
    Deliberately NOT gated by the feature flag: a user must always be able to
    revoke access. Imported application history is left intact."""
    from src.services.gmail_oauth import disconnect

    disconnected, revoked = disconnect(user_id)
    return {"disconnected": disconnected, "revoked_at_google": revoked}


# ── Recurring-sync consent ────────────────────────────────────────────────────


@router.post("/consent")
@limiter.limit(LIMIT_INTEGRATIONS)
def gmail_recurring_sync_consent(
    request: Request,
    body: RecurringSyncConsentBody,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Grant or revoke recurring (fleet) sync consent for the current JWT user.

    This is SEPARATE from the OAuth read grant (BLOCKER 2 / design §3): OAuth
    read consent does NOT authorize recurring background sync — only rows with
    this consent set are swept by /sync-all. Deliberately NOT gated by
    RICO_ENABLE_GMAIL_SYNC: revoking is a privacy-reducing action that must
    always be available, and granting merely records intent the fleet sweep
    honors once sync is enabled. Requires an existing connection; identity is
    JWT-only (the body carries the action, never a user id)."""
    connection = gmail_repo.get_connection(user_id)
    if not connection:
        raise HTTPException(status_code=409, detail="Gmail is not connected.")
    if not gmail_repo.set_recurring_sync_consent(user_id, body.granted):
        raise HTTPException(status_code=500, detail="Could not update sync consent.")
    gmail_repo.insert_audit_event(
        user_id,
        "recurring_sync_consent_granted"
        if body.granted
        else "recurring_sync_consent_revoked",
        "ok",
        connection_id=connection.get("id"),
    )
    return {"recurring_sync_consent": body.granted}


# ── Sync ──────────────────────────────────────────────────────────────────────


@router.post("/sync")
@limiter.limit(LIMIT_INTEGRATIONS_SYNC)
def gmail_sync(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Start a bounded manual sync for the current user in a background task
    (no Redis/queue — FastAPI BackgroundTasks). Poll /sync-runs for the result."""
    _require_enabled()
    from src.services.gmail_sync_service import run_user_sync

    connection = gmail_repo.get_connection(user_id)
    if not connection:
        raise HTTPException(status_code=409, detail="Gmail is not connected.")
    if connection.get("status") == "needs_reauth":
        raise HTTPException(
            status_code=409, detail="Gmail connection needs re-authentication."
        )

    background_tasks.add_task(run_user_sync, user_id, "manual")
    return {"status": "started", "detail": "Sync started — check /sync-runs for progress."}


@router.get("/sync-runs")
@limiter.limit(LIMIT_INTEGRATIONS)
def gmail_sync_runs(
    request: Request, user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    return {"runs": gmail_repo.list_sync_runs(user_id, limit=20)}


@router.post("/sync-all")
def gmail_sync_all(
    request: Request, _cron: None = Depends(require_cron_secret)
) -> Dict[str, Any]:
    """Fleet sweep over all active connections. Cron-only (X-Cron-Secret) — no
    JWT, no rate limit bucket needed (secret-gated, server-to-server). Bounded
    per user by message cap and time budget."""
    _require_enabled()
    from src.services.gmail_sync_service import run_fleet_sweep

    return run_fleet_sweep()


# ── Review items ──────────────────────────────────────────────────────────────


@router.get("/review-items")
@limiter.limit(LIMIT_INTEGRATIONS)
def gmail_review_items(
    request: Request, user_id: str = Depends(get_current_user_id)
) -> Dict[str, Any]:
    return {"items": gmail_repo.list_review_items(user_id, review_status="pending")}


@router.post("/review-items/{item_id}/approve")
@limiter.limit(LIMIT_INTEGRATIONS)
def approve_review_item(
    item_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Apply the proposed application status for a matched review item.

    Approval is ATOMIC (BLOCKER 3): rather than read → check pending → mutate in
    separate steps (which two concurrent approvals could both pass, double-
    applying the status), the item is claimed with a single conditional UPDATE
    that flips pending → approved and returns the row only if it was still
    pending. A concurrent second call loses the claim, gets nothing, and no-ops.
    The claimed status is then applied via applications_repo.update_status —
    which is itself idempotent (setting a status to a value is a no-op replay) —
    so the effective apply happens exactly once. If the apply fails, the claim
    is reverted to pending so it can be retried.

    The status is normalized to the SaaS vocabulary and applied for the JWT
    user only."""
    _require_enabled()
    from src.repositories import applications_repo
    from src.services.gmail_sync_service import normalize_status

    # Validate before spending the atomic claim (cheap 404/422 paths).
    item = gmail_repo.get_review_item(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found.")
    if item.get("review_status") != "pending":
        raise HTTPException(status_code=409, detail="Review item already resolved.")
    if not item.get("matched_job_id"):
        raise HTTPException(
            status_code=422,
            detail="This item is not matched to a tracked application — dismiss it instead.",
        )
    if normalize_status(item.get("proposed_status")) not in applications_repo._VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Proposed status '{normalize_status(item.get('proposed_status'))}' "
                "is not applicable."
            ),
        )

    # Atomic claim: pending → approved, returns the row only if we won the race.
    claimed = gmail_repo.claim_review_item_for_approval(user_id, item_id)
    if not claimed:
        # Another concurrent approval already claimed it — do not double-apply.
        raise HTTPException(status_code=409, detail="Review item already resolved.")

    matched_job_id = claimed.get("matched_job_id")
    status = normalize_status(claimed.get("proposed_status"))
    ok = applications_repo.update_status(
        {"job_id": matched_job_id},
        status,
        user_id=user_id,
        notes=f"Approved from Gmail review: {(claimed.get('subject_snippet') or '')[:80]}",
    )
    if not ok:
        # Compensating action: release the claim so the item can be retried.
        gmail_repo.set_review_item_status(user_id, item_id, "pending")
        raise HTTPException(status_code=500, detail="Could not update the application.")

    gmail_repo.insert_audit_event(
        user_id,
        "review_item_approved",
        "ok",
        metadata={"item_id": item_id, "applied_status": status},
    )
    return {"ok": True, "applied_status": status, "job_id": matched_job_id}


@router.post("/review-items/{item_id}/dismiss")
@limiter.limit(LIMIT_INTEGRATIONS)
def dismiss_review_item(
    item_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    _require_enabled()
    item = gmail_repo.get_review_item(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found.")
    if item.get("review_status") != "pending":
        raise HTTPException(status_code=409, detail="Review item already resolved.")
    gmail_repo.set_review_item_status(user_id, item_id, "dismissed")
    gmail_repo.insert_audit_event(
        user_id, "review_item_dismissed", "ok", metadata={"item_id": item_id}
    )
    return {"ok": True}

"""Owner-only subscriber administration surface.

Endpoints (both gated by :func:`src.api.deps.require_owner` — authenticated
non-owners get 403, unauthenticated get 401):

  GET /api/v1/admin/subscribers/summary  — dashboard totals + approximate MRR
  GET /api/v1/admin/subscribers          — filtered/searchable subscriber table

Privacy contract:
  * Neon is the operational read model; Paddle is the billing source of truth.
    This surface reads the locally webhook-updated billing state and NEVER
    calls Paddle during a page load.
  * No secrets, no full payment identifiers, no card data, no raw Paddle
    payloads ever reach the browser. Paddle references and the canonical user
    id are partially masked here before serialization; the owner's own id is
    masked too and is never returned as an authorization value.
  * Responses are explicitly marked no-store (the global cache-privacy
    middleware already does this; the endpoints set it again as defense in
    depth) so private admin data is never cached by a browser/proxy/CDN.
  * Owner access is recorded through the canonical audit mechanism
    (audit_repo.write_audit_log).

This is a read-only surface: it exposes no destructive subscription controls.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Response

from src.api.deps import require_owner
from src.repositories import admin_subscribers_repo as repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/subscribers", tags=["admin-subscribers"])

_NO_STORE = "no-store, no-cache, must-revalidate, private, max-age=0"

# Cap the page size so a single response can never dump the entire cohort.
_MAX_LIMIT = 200
_DEFAULT_LIMIT = 100


# ---------------------------------------------------------------------------
# Masking helpers (never expose full identifiers to the browser)
# ---------------------------------------------------------------------------

def _mask_canonical_id(user_id: Any) -> Optional[str]:
    """Partially mask the canonical numeric ``users.id`` (keep last 2 chars).

    Applied to every row including the owner's own id, so the id is never
    returned in a form usable as an authorization value.
    """
    if user_id is None:
        return None
    s = str(user_id)
    if len(s) <= 2:
        return "•" * len(s)
    return "•" * (len(s) - 2) + s[-2:]


def _mask_ref(ref: Any) -> Optional[str]:
    """Mask a Paddle customer/subscription reference (short prefix + last 4)."""
    if not ref:
        return None
    s = str(ref)
    if len(s) <= 4:
        return "•" * len(s)
    prefix = s[:6] if len(s) > 10 else s[:2]
    return f"{prefix}…{s[-4:]}"


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _allowance_entitlements(paying: bool):
    from src.subscription_plans import FREE_ENTITLEMENTS, RICO_MONTHLY_PLAN
    return RICO_MONTHLY_PLAN.entitlements if paying else FREE_ENTITLEMENTS


def _usage_pair(used: Optional[int], allowance: Optional[int]) -> Dict[str, Any]:
    return {"used": used, "allowance": allowance}


def _serialize_row(row: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    paying = repo.is_paying(row, now)
    ent = _allowance_entitlements(paying)
    usage = row.get("usage") or {}
    return {
        "name": row.get("name"),
        "email": row.get("email"),
        "user_id_masked": _mask_canonical_id(row.get("user_id")),
        "plan": "rico_monthly" if paying else "free",
        "status": repo.derive_status_label(row, now),
        "paddle_customer_ref": _mask_ref(row.get("paddle_customer_id")),
        "paddle_subscription_ref": _mask_ref(row.get("paddle_subscription_id")),
        "subscription_start": _iso(row.get("current_period_start")),
        "next_renewal": _iso(row.get("current_period_end")),
        "cancellation_effective": _iso(row.get("cancel_at")),
        "canceled_at": _iso(row.get("canceled_at")),
        "usage": {
            "ai_messages": _usage_pair(
                usage.get("ai_messages"), ent.monthly_ai_message_limit
            ),
            "saved_jobs": _usage_pair(usage.get("saved_jobs"), ent.saved_jobs_limit),
            "cv_documents": _usage_pair(usage.get("cv_documents"), ent.cv_storage_limit),
            "other_documents": _usage_pair(
                usage.get("other_documents"), ent.other_document_limit
            ),
        },
        "last_activity": _iso(row.get("last_login_at")),
        "last_billing_sync": _iso(row.get("last_billing_sync")),
        "reconciliation": (
            "needs_review" if repo.needs_reconciliation(row, now) else "ok"
        ),
    }


def _max_billing_sync(rows: List[Dict[str, Any]]) -> Optional[datetime]:
    stamps = [
        repo._as_aware(r.get("last_billing_sync"))
        for r in rows
        if r.get("last_billing_sync") is not None
    ]
    return max(stamps) if stamps else None


def _audit_access(owner: Dict[str, Any], endpoint: str, extra: Dict[str, Any]) -> None:
    """Best-effort audit of owner access (never blocks the response)."""
    try:
        from src.repositories import audit_repo
        audit_repo.write_audit_log(
            owner.get("email", ""),
            "admin_subscribers_access",
            {"endpoint": endpoint, **extra},
        )
    except Exception:
        logger.debug("admin_subscribers: audit write failed", exc_info=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary")
def subscribers_summary(
    response: Response,
    owner: Dict[str, Any] = Depends(require_owner),
) -> Dict[str, Any]:
    """Dashboard totals for the owner: user/plan breakdown + approximate MRR."""
    response.headers["Cache-Control"] = _NO_STORE
    now = datetime.now(timezone.utc)

    snapshot = repo.fetch_snapshot()
    rows = snapshot["rows"]
    summary = repo.summarize(rows, now)
    _audit_access(owner, "summary", {"total_users": summary["total_users"]})

    return {
        "summary": summary,
        "last_billing_sync": _iso(_max_billing_sync(rows)),
        "generated_at": _iso(snapshot["generated_at"]),
        "truncated": snapshot["truncated"],
        "usage_available": snapshot["usage_available"],
    }


@router.get("")
def list_subscribers(
    response: Response,
    owner: Dict[str, Any] = Depends(require_owner),
    filter: str = Query("all"),
    search: str = Query("", max_length=200),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Filtered, searchable subscriber table (paginated)."""
    response.headers["Cache-Control"] = _NO_STORE
    now = datetime.now(timezone.utc)

    snapshot = repo.fetch_snapshot()
    rows = snapshot["rows"]

    filtered = repo.filter_and_search(rows, status_filter=filter, search=search, now=now)
    page = filtered[offset : offset + limit]
    subscribers = [_serialize_row(r, now) for r in page]

    _audit_access(
        owner,
        "list",
        {"filter": (filter or "all"), "returned": len(subscribers)},
    )

    return {
        "subscribers": subscribers,
        "total": len(rows),
        "filtered_total": len(filtered),
        "limit": limit,
        "offset": offset,
        "filter": (filter or "all").strip().lower(),
        "last_billing_sync": _iso(_max_billing_sync(rows)),
        "generated_at": _iso(snapshot["generated_at"]),
        "truncated": snapshot["truncated"],
        "usage_available": snapshot["usage_available"],
    }

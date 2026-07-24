"""Read-only data access for the owner-only subscriber administration surface.

This module powers ``/api/v1/admin/subscribers`` and its ``/summary``. It is
strictly a *read model* over data Rico already persists:

  * ``users``               — canonical accounts (immutable ``id``, email, role,
                              timestamps). Owner authorization is keyed on
                              ``users.id`` elsewhere (see src/api/deps.py).
  * ``paddle_subscriptions``— webhook-updated billing state (the local read
                              model; Paddle remains the billing source of truth,
                              but this surface NEVER calls Paddle at read time).
  * ``rico_users``          — best-effort display name + the internal UUID that
                              keys the usage tables.
  * ``rico_job_recommendations`` / ``user_documents`` / ``rico_chat_history`` —
                              best-effort usage counters (keyed by the rico_users
                              UUID, hence the id-space bridge above).

Design notes:
  * One snapshot fetch (a handful of aggregate queries, independent of page
    size) returns every active account enriched with billing + usage. The
    dashboard summary and the filtered table are both computed in Python from
    that single in-memory snapshot, so the two can never disagree on counts.
  * Row classification (``derive_status_label`` / the bucket predicates) is the
    single source of truth shared by the summary and the table filters.
  * Masking of Paddle identifiers and the canonical id happens in the router,
    not here — this layer returns raw values so tests can assert on them.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# Hard cap on the snapshot. Rico's paying cohort is measured in the tens to low
# hundreds (founder cohort of 50-100). This cap keeps the owner view bounded and
# the 60s poll cheap; ``truncated`` is surfaced if it is ever hit.
SNAPSHOT_CAP = 2000

# AI-message usage is a best-effort 30-day count (the honest, cheap window that
# batches in one query; per-user daily/monthly windows would not).
_AI_USAGE_WINDOW_DAYS = 30

# Paddle statuses Rico understands (see src/services/paddle_webhook_service.py).
# Anything outside this set is a reconciliation signal.
KNOWN_STATUSES = frozenset(
    {"active", "trialing", "past_due", "paused", "canceled", "inactive"}
)


def _grace_days() -> int:
    """7-day payment-retry grace window, sourced from the canonical constant."""
    try:
        from src.subscription_plans import PAST_DUE_GRACE_PERIOD
        return max(0, int(PAST_DUE_GRACE_PERIOD.total_seconds() // 86400))
    except Exception:
        return 7


# ---------------------------------------------------------------------------
# Connection helper (RealDictCursor, mirrors src/repositories/paddle_repo.py)
# ---------------------------------------------------------------------------

def _get_conn(conn=None):
    if conn is not None:
        return conn, False
    from src.rico_db import RicoDB
    return RicoDB().connect(), True


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_UTC)
    return dt


# ---------------------------------------------------------------------------
# Snapshot fetch
# ---------------------------------------------------------------------------

def fetch_snapshot(conn=None, cap: int = SNAPSHOT_CAP) -> Dict[str, Any]:
    """Return every active account enriched with billing + best-effort usage.

    Shape::

        {
            "rows": [ {<enriched row>}, ... ],
            "truncated": bool,          # True if more accounts exist than `cap`
            "generated_at": datetime,   # snapshot time (UTC)
            "usage_available": bool,     # False if usage enrichment failed wholesale
        }

    Never raises for the best-effort enrichment (name/usage) — those degrade to
    None and set ``usage_available=False``. A hard failure fetching the core
    users/billing join propagates so the router can surface a failed state.
    """
    conn, should_close = _get_conn(conn)
    try:
        rows = _fetch_core_rows(conn, cap)
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]

        emails = [r["email"] for r in rows if r.get("email")]
        usage_available = True
        try:
            name_by_email, uuid_by_email = _fetch_rico_user_map(conn, emails)
        except Exception:
            logger.warning("admin_subscribers: rico_users map failed", exc_info=True)
            name_by_email, uuid_by_email = {}, {}
            usage_available = False

        uuids = [u for u in uuid_by_email.values() if u]
        saved_by_uuid: Dict[str, int] = {}
        docs_by_uuid: Dict[str, Dict[str, int]] = {}
        ai_by_uuid: Dict[str, int] = {}
        if uuids:
            try:
                saved_by_uuid = _fetch_saved_counts(conn, uuids)
                docs_by_uuid = _fetch_document_counts(conn, uuids)
                ai_by_uuid = _fetch_ai_counts(conn, uuids)
            except Exception:
                logger.warning("admin_subscribers: usage counts failed", exc_info=True)
                usage_available = False

        for r in rows:
            email = r.get("email")
            lower = email.lower() if email else ""
            r["name"] = name_by_email.get(lower)
            uuid = uuid_by_email.get(lower)
            if uuid:
                docs = docs_by_uuid.get(uuid, {})
                r["usage"] = {
                    "ai_messages": ai_by_uuid.get(uuid),
                    "saved_jobs": saved_by_uuid.get(uuid, 0),
                    "cv_documents": docs.get("cv", 0),
                    "other_documents": sum(
                        c for dt, c in docs.items() if dt != "cv"
                    ),
                }
            else:
                # No rico_users row — usage tables can't be keyed for this user.
                r["usage"] = {
                    "ai_messages": None,
                    "saved_jobs": None,
                    "cv_documents": None,
                    "other_documents": None,
                }

        return {
            "rows": rows,
            "truncated": truncated,
            "generated_at": datetime.now(_UTC),
            "usage_available": usage_available,
        }
    finally:
        if should_close:
            conn.close()


def _fetch_core_rows(conn, cap: int) -> List[Dict[str, Any]]:
    """The users ⟕ paddle_subscriptions join — the authoritative core rows."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id                     AS user_id,
                   u.email                  AS email,
                   u.role                   AS role,
                   u.created_at             AS user_created_at,
                   u.last_login_at          AS last_login_at,
                   s.plan                   AS plan,
                   s.status                 AS status,
                   s.billing_cycle          AS billing_cycle,
                   s.paddle_customer_id     AS paddle_customer_id,
                   s.paddle_subscription_id AS paddle_subscription_id,
                   s.current_period_start   AS current_period_start,
                   s.current_period_end     AS current_period_end,
                   s.cancel_at              AS cancel_at,
                   s.canceled_at            AS canceled_at,
                   s.past_due_since         AS past_due_since,
                   s.created_at             AS sub_created_at,
                   s.updated_at             AS last_billing_sync
            FROM users u
            LEFT JOIN paddle_subscriptions s ON s.user_id = u.email
            WHERE u.is_active = TRUE
            ORDER BY COALESCE(s.updated_at, u.created_at) DESC
            LIMIT %s
            """,
            (cap + 1,),  # +1 so we can detect truncation
        )
        return [dict(row) for row in cur.fetchall()]


def _fetch_rico_user_map(conn, emails: List[str]):
    """email(lower) -> display name, and email(lower) -> internal UUID.

    rico_users can carry more than one row per person (an email-keyed row and a
    UUID-keyed row); pick the most recently updated row that carries a name /
    the canonical UUID.
    """
    name_by_email: Dict[str, str] = {}
    uuid_by_email: Dict[str, str] = {}
    if not emails:
        return name_by_email, uuid_by_email
    lowered = [e.lower() for e in emails]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id,
                   LOWER(COALESCE(email, external_user_id)) AS key_email,
                   name,
                   updated_at
            FROM rico_users
            WHERE LOWER(COALESCE(email, external_user_id)) = ANY(%s)
            ORDER BY updated_at ASC NULLS FIRST
            """,
            (lowered,),
        )
        for row in cur.fetchall():
            key = row["key_email"]
            if not key:
                continue
            # Later rows (more recent updated_at) overwrite earlier ones.
            uuid_by_email[key] = str(row["id"])
            if row.get("name"):
                name_by_email[key] = row["name"]
    return name_by_email, uuid_by_email


def _fetch_saved_counts(conn, uuids: List[str]) -> Dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id::text AS uid, COUNT(*) AS cnt
            FROM rico_job_recommendations
            WHERE status = 'saved' AND user_id = ANY(%s::uuid[])
            GROUP BY user_id
            """,
            (uuids,),
        )
        return {row["uid"]: int(row["cnt"]) for row in cur.fetchall()}


def _fetch_document_counts(conn, uuids: List[str]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id::text AS uid, doc_type, COUNT(*) AS cnt
            FROM user_documents
            WHERE user_id = ANY(%s::uuid[])
            GROUP BY user_id, doc_type
            """,
            (uuids,),
        )
        for row in cur.fetchall():
            out.setdefault(row["uid"], {})[row["doc_type"] or "other"] = int(row["cnt"])
    return out


def _fetch_ai_counts(conn, uuids: List[str]) -> Dict[str, int]:
    since = datetime.now(_UTC) - timedelta(days=_AI_USAGE_WINDOW_DAYS)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id::text AS uid, COUNT(*) AS cnt
            FROM rico_chat_history
            WHERE role = 'user'
              AND user_id = ANY(%s::uuid[])
              AND created_at >= %s
            GROUP BY user_id
            """,
            (uuids, since),
        )
        return {row["uid"]: int(row["cnt"]) for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Row classification — the single source of truth for summary + filters
# ---------------------------------------------------------------------------

def _within_grace(row: Dict[str, Any], now: datetime) -> bool:
    if row.get("status") != "past_due":
        return False
    pds = _as_aware(row.get("past_due_since"))
    if pds is None:
        # Unknown stamp — lenient (matches subscription_plans grace semantics).
        return True
    return (now - pds) <= timedelta(days=_grace_days())


def is_paying(row: Dict[str, Any], now: datetime) -> bool:
    """Whether the account currently holds a live paid entitlement."""
    status = row.get("status")
    if status in ("active", "trialing"):
        # An active status whose period has lapsed is not really paying.
        end = _as_aware(row.get("current_period_end"))
        if status == "active" and end is not None and end < now:
            return False
        return True
    if status == "past_due":
        return _within_grace(row, now)
    return False


def derive_status_label(row: Dict[str, Any], now: datetime) -> str:
    """Canonical textual status for the table's status column."""
    status = row.get("status")
    if status is None:
        return "free"
    if status == "active":
        end = _as_aware(row.get("current_period_end"))
        if end is not None and end < now:
            return "needs_reconciliation"
        return "canceling" if row.get("cancel_at") else "active"
    if status == "trialing":
        return "trialing"
    if status == "past_due":
        return "past_due" if _within_grace(row, now) else "payment_failed"
    if status == "canceled":
        return "canceled"
    if status == "inactive":
        return "expired"
    if status == "paused":
        return "paused"
    return "needs_reconciliation"


def needs_reconciliation(row: Dict[str, Any], now: datetime) -> bool:
    status = row.get("status")
    if status is None:
        return False
    if status not in KNOWN_STATUSES:
        return True
    if status == "active":
        end = _as_aware(row.get("current_period_end"))
        if end is not None and end < now:
            return True
    return False


def _inactive_since(row: Dict[str, Any], now: datetime, days: int) -> bool:
    last = _as_aware(row.get("last_login_at"))
    if last is None:
        return True  # never logged in counts as inactive
    return (now - last) >= timedelta(days=days)


# Bucket predicates. Each is an independent boolean over a row (buckets overlap
# on purpose — e.g. a "canceling" row is also "active").
def _bucket_predicates(now: datetime):
    return {
        "all": lambda r: True,
        "free": lambda r: not is_paying(r, now),
        "active": lambda r: r.get("status") == "active"
        and not (
            _as_aware(r.get("current_period_end")) is not None
            and _as_aware(r.get("current_period_end")) < now
        ),
        "trialing": lambda r: r.get("status") == "trialing",
        "canceling": lambda r: r.get("status") == "active" and bool(r.get("cancel_at")),
        "past_due": lambda r: r.get("status") == "past_due" and _within_grace(r, now),
        "payment_failed": lambda r: r.get("status") == "past_due"
        and not _within_grace(r, now),
        "canceled": lambda r: r.get("status") == "canceled",
        "expired": lambda r: r.get("status") == "inactive",
        "needs_reconciliation": lambda r: needs_reconciliation(r, now),
        "inactive_7d": lambda r: _inactive_since(r, now, 7),
        "inactive_30d": lambda r: _inactive_since(r, now, 30),
    }


VALID_FILTERS = frozenset(
    {
        "all",
        "free",
        "active",
        "trialing",
        "canceling",
        "past_due",
        "payment_failed",
        "canceled",
        "expired",
        "needs_reconciliation",
        "inactive_7d",
        "inactive_30d",
    }
)


# ---------------------------------------------------------------------------
# Summary + filtering (pure functions over a snapshot's rows)
# ---------------------------------------------------------------------------

def _monthly_price_usd() -> float:
    try:
        from src.subscription_plans import RICO_MONTHLY_PLAN
        return float(RICO_MONTHLY_PLAN.price_monthly)
    except Exception:
        return 21.50


def summarize(rows: List[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Compute the dashboard summary from the in-memory snapshot rows."""
    now = now or datetime.now(_UTC)
    preds = _bucket_predicates(now)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def count(name: str) -> int:
        pred = preds[name]
        return sum(1 for r in rows if pred(r))

    active = count("active")
    new_this_month = sum(
        1
        for r in rows
        if _as_aware(r.get("sub_created_at")) is not None
        and _as_aware(r.get("sub_created_at")) >= month_start
    )
    cancellations_this_month = sum(
        1
        for r in rows
        if _as_aware(r.get("canceled_at")) is not None
        and _as_aware(r.get("canceled_at")) >= month_start
    )

    return {
        "total_users": len(rows),
        "free_users": count("free"),
        "active_subscribers": active,
        "trialing_subscribers": count("trialing"),
        "past_due_subscribers": count("past_due"),
        "canceling_subscribers": count("canceling"),
        "canceled_subscribers": count("canceled"),
        "expired_subscribers": count("expired"),
        "payment_failed_subscribers": count("payment_failed"),
        "needs_reconciliation": count("needs_reconciliation"),
        "new_subscriptions_this_month": new_this_month,
        "cancellations_this_month": cancellations_this_month,
        "approximate_mrr_usd": round(active * _monthly_price_usd(), 2),
        "currency": "USD",
        "mrr_is_approximate": True,
    }


def filter_and_search(
    rows: List[Dict[str, Any]],
    status_filter: str = "all",
    search: str = "",
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Apply a bucket filter and a name/email search (case-insensitive)."""
    now = now or datetime.now(_UTC)
    status_filter = (status_filter or "all").strip().lower()
    if status_filter not in VALID_FILTERS:
        status_filter = "all"
    pred = _bucket_predicates(now)[status_filter]
    out = [r for r in rows if pred(r)]

    needle = (search or "").strip().lower()
    if needle:
        def matches(r: Dict[str, Any]) -> bool:
            email = (r.get("email") or "").lower()
            name = (r.get("name") or "").lower()
            return needle in email or needle in name

        out = [r for r in out if matches(r)]
    return out

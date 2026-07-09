"""Weekly admin activation digest (issue #922).

Aggregates the previous full ISO week (Monday 00:00 UTC → Monday 00:00 UTC) of
signup/activation metrics and emails one summary to the admin recipient.

Idempotency: a row in admin_digest_log (migration 036) is claimed via
INSERT ... ON CONFLICT DO NOTHING BEFORE sending, keyed on
(digest_type, period_start). Because the period is anchored to the ISO week,
any rerun during the same week hits the same key and is skipped — the weekly
cron never double-sends. This mirrors the profile-nudge "stamp before
delivery" philosophy: never double-send beats never-miss.

Synthetic/internal accounts are excluded from metrics using the same guard the
profile nudge sweep uses. The digest body is aggregate-only — no emails or
other PII. Kill-switch: RICO_ENABLE_ADMIN_DIGEST=false (default enabled; the
endpoint is already cron-secret-guarded).
"""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict

from src.services.profile_nudge_service import _is_synthetic_email
from src.services.signup_notifications import _admin_recipient
from src.services.signup_source import SIGNUP_SOURCE_FALLBACK

logger = logging.getLogger(__name__)

DIGEST_TYPE = "weekly_activation"
PERIOD_DAYS = 7
TOP_SOURCES_LIMIT = 5


def _digest_enabled() -> bool:
    return os.getenv("RICO_ENABLE_ADMIN_DIGEST", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _pct(part: int, total: int) -> str:
    if total <= 0:
        return "n/a"
    return f"{int(part / total * 100)}%"


def _collect_metrics(conn, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
    """Aggregate activation metrics for signups inside [period_start, period_end)."""
    with conn.cursor() as cur:
        # Same users → rico_users → rico_profiles join chain as the nudge sweep.
        cur.execute(
            """
            SELECT
                u.id,
                u.email,
                COALESCE(u.email_verified, TRUE)   AS email_verified,
                u.signup_source,
                rp.profile->>'cv_filename'         AS cv_filename,
                rp.profile->'target_roles'         AS target_roles,
                rp.profile->'preferred_cities'     AS preferred_cities
            FROM users u
            LEFT JOIN rico_users ru
                ON ru.external_user_id = u.email
            LEFT JOIN rico_profiles rp
                ON rp.user_id = ru.id
            WHERE u.created_at >= %s AND u.created_at < %s
            """,
            (period_start, period_end),
        )
        rows = cur.fetchall()

    total = verified = cv = roles = cities = synthetic = 0
    sources: Counter[str] = Counter()
    for row in rows:
        email = row["email"] or ""
        if _is_synthetic_email(email):
            synthetic += 1
            continue
        total += 1
        if row["email_verified"]:
            verified += 1
        if row["cv_filename"]:
            cv += 1
        if row["target_roles"]:
            roles += 1
        if row["preferred_cities"]:
            cities += 1
        sources[row["signup_source"] or SIGNUP_SOURCE_FALLBACK] += 1

    # Nudge count is best-effort: the column ships with migration 029.
    nudges_sent = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM users
                WHERE profile_nudge_sent_at >= %s AND profile_nudge_sent_at < %s
                """,
                (period_start, period_end),
            )
            nudges_sent = cur.fetchone()["n"]
    except Exception:
        logger.warning("admin_digest_nudge_count_unavailable")

    return {
        "signups": total,
        "signups_synthetic_excluded": synthetic,
        "verified": verified,
        "cv_uploaded": cv,
        "target_roles_set": roles,
        "preferred_cities_set": cities,
        "nudges_sent": nudges_sent,
        "top_sources": sources.most_common(TOP_SOURCES_LIMIT),
    }


def _build_digest_body(period_start, period_end, metrics: Dict[str, Any]) -> str:
    total = metrics["signups"]
    lines = [
        "Rico weekly activation digest",
        f"Week: {period_start} → {period_end} (UTC)",
        "",
        f"Signups: {total}"
        + (
            f" ({metrics['signups_synthetic_excluded']} synthetic/internal excluded)"
            if metrics["signups_synthetic_excluded"]
            else ""
        ),
        f"Email verified: {metrics['verified']}/{total} ({_pct(metrics['verified'], total)})",
        f"CV uploaded: {metrics['cv_uploaded']}/{total} ({_pct(metrics['cv_uploaded'], total)})",
        f"Target roles set: {metrics['target_roles_set']}/{total} ({_pct(metrics['target_roles_set'], total)})",
        f"Preferred cities set: {metrics['preferred_cities_set']}/{total} ({_pct(metrics['preferred_cities_set'], total)})",
    ]
    if metrics["nudges_sent"] is not None:
        lines.append(f"Profile nudges sent this week: {metrics['nudges_sent']}")
    lines.append("")
    if metrics["top_sources"]:
        lines.append("Top signup sources:")
        for rank, (source, count) in enumerate(metrics["top_sources"], start=1):
            lines.append(f"  {rank}. {source} — {count}")
    else:
        lines.append("Top signup sources: no signups this week.")
    lines += [
        "",
        "— Rico weekly digest (admin-only). Configure recipient via "
        "ADMIN_SIGNUP_NOTIFICATION_EMAIL; disable via RICO_ENABLE_ADMIN_DIGEST=false.",
    ]
    return "\n".join(lines)


def run_weekly_admin_digest(dry_run: bool = False, now: datetime | None = None) -> Dict[str, Any]:
    """Compute last ISO week's metrics and send one admin email.

    Returns a summary dict; never raises. Safe to rerun: the second run in the
    same week returns status="already_sent" without emailing.
    """
    from src.rico_db import RicoDB
    from src.services.mailer import send_email

    if not _digest_enabled():
        return {"status": "disabled", "sent": False, "dry_run": dry_run}

    now = now or datetime.now(timezone.utc)
    today = now.date()
    week_monday = today - timedelta(days=today.weekday())
    period_start_date = week_monday - timedelta(days=PERIOD_DAYS)
    period_end_date = week_monday
    period_start = datetime.combine(period_start_date, time.min, tzinfo=timezone.utc)
    period_end = datetime.combine(period_end_date, time.min, tzinfo=timezone.utc)

    base = {
        "dry_run": dry_run,
        "period_start": str(period_start_date),
        "period_end": str(period_end_date),
    }

    db = RicoDB()
    if not getattr(db, "available", False):
        logger.warning("admin_digest: DB unavailable — skipping")
        return {"status": "unavailable", "sent": False, **base}
    try:
        conn = db.connect(ensure_schema=False)
    except Exception as exc:
        logger.warning("admin_digest: connect failed: %s", exc)
        return {"status": "unavailable", "sent": False, **base}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'admin_digest_log'
                """
            )
            if not cur.fetchone():
                logger.warning("admin_digest: migration 036 not applied — skipping")
                return {"status": "migration_pending", "sent": False, **base}

        metrics = _collect_metrics(conn, period_start, period_end)
        recipient = _admin_recipient()

        if dry_run:
            return {"status": "ok", "sent": False, "metrics": metrics, **base}

        # Claim the week BEFORE sending so reruns can never double-send.
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admin_digest_log (digest_type, period_start, period_end, recipient)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (digest_type, period_start) DO NOTHING
                RETURNING id
                """,
                (DIGEST_TYPE, period_start_date, period_end_date, recipient),
            )
            claimed = cur.fetchone()
        conn.commit()
        if not claimed:
            return {"status": "already_sent", "sent": False, **base}

        body = _build_digest_body(period_start_date, period_end_date, metrics)
        ok = send_email(
            to_email=recipient,
            subject=f"Rico weekly activation digest — week of {period_start_date}",
            body=body,
        )
        if not ok:
            logger.warning("admin_digest_email_not_sent period_start=%s", period_start_date)
            return {"status": "send_failed", "sent": False, "metrics": metrics, **base}
        return {"status": "ok", "sent": True, "metrics": metrics, **base}
    except Exception:
        logger.exception("admin_digest_failed")
        return {"status": "error", "sent": False, **base}
    finally:
        conn.close()

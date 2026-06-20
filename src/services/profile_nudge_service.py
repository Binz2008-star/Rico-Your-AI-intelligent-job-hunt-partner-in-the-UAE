"""Profile completion nudge sweep.

Sends a one-time follow-up email to users who:
  - Registered > 24 hours ago
  - Have never been sent a nudge (profile_nudge_sent_at IS NULL)
  - Still have an incomplete profile: CV missing OR target_roles empty OR preferred_cities empty

Invoked by the cron-guarded POST /api/v1/pipeline/profile-nudge endpoint.
Requires migration 029 (profile_nudge_sent_at column on users).
Idempotent: re-running never double-sends because sent_at is stamped before delivery.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

NUDGE_DELAY_HOURS = 24


def _build_nudge_body(name: str | None, email: str, missing: list[str]) -> str:
    display_name = name.strip() if name and name.strip() else email.split("@")[0]
    missing_lines = "\n".join(f"  - {item}" for item in missing)
    return "\n".join([
        f"Hi {display_name},",
        "",
        "You signed up for RicoHunt — great to have you!",
        "",
        "To start getting personalised UAE job matches, your profile needs a few more details:",
        "",
        missing_lines,
        "",
        "It takes less than 2 minutes. Head to:",
        "https://ricohunt.com/onboarding",
        "",
        "Rico is ready to find your next role the moment your profile is set.",
        "",
        "— The RicoHunt Team",
        "",
        "────────────────────────────────",
        "You're receiving this because you registered at ricohunt.com.",
        "If you no longer wish to receive emails from us, reply with 'unsubscribe'.",
    ])


def run_profile_nudge_sweep() -> Dict[str, Any]:
    """Find eligible users and send one nudge email each.

    Returns summary dict: {status, nudges_sent, nudges_failed, skipped}.
    Never raises — failures are logged and counted, not propagated.
    """
    from src.rico_db import RicoDB
    from src.services.mailer import send_email

    db = RicoDB()
    if not getattr(db, "available", False):
        logger.warning("profile_nudge_sweep: DB unavailable — skipping")
        return {"status": "unavailable", "nudges_sent": 0, "nudges_failed": 0, "skipped": 0}

    conn = getattr(db, "conn", None) or getattr(db, "_conn", None)
    if conn is None:
        # Try getting connection via db.get_conn or similar
        try:
            conn = db.get_connection()
        except Exception:
            conn = None
    if conn is None:
        logger.warning("profile_nudge_sweep: no DB connection available")
        return {"status": "unavailable", "nudges_sent": 0, "nudges_failed": 0, "skipped": 0}

    try:
        with conn.cursor() as cur:
            # Check the column exists (migration 029 guard)
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'profile_nudge_sent_at'
            """)
            if not cur.fetchone():
                logger.warning("profile_nudge_sweep: migration 029 not applied — skipping")
                return {"status": "migration_pending", "nudges_sent": 0, "nudges_failed": 0, "skipped": 0}

            # Fetch candidates
            cur.execute("""
                SELECT u.id, u.email, u.name,
                       rp.cv_filename,
                       rp.target_roles,
                       rp.preferred_cities
                FROM users u
                LEFT JOIN rico_profiles rp ON rp.user_id = u.id
                WHERE u.created_at < NOW() - INTERVAL '%s hours'
                  AND u.profile_nudge_sent_at IS NULL
                  AND u.email IS NOT NULL
                ORDER BY u.created_at ASC
                LIMIT 200
            """, (NUDGE_DELAY_HOURS,))
            rows = cur.fetchall()
    except Exception as exc:
        logger.warning("profile_nudge_sweep: query failed: %s", exc)
        return {"status": "error", "nudges_sent": 0, "nudges_failed": 0, "skipped": 0}

    sent = 0
    failed = 0
    skipped = 0

    for row in rows:
        user_id, email, name, cv_filename, target_roles, preferred_cities = row

        missing: list[str] = []
        if not cv_filename:
            missing.append("Upload your CV")
        if not target_roles:
            missing.append("Add your target roles (e.g. 'Marketing Manager', 'Data Analyst')")
        if not preferred_cities:
            missing.append("Add your preferred UAE cities (e.g. Dubai, Abu Dhabi)")

        if not missing:
            # Profile is already sufficiently filled — just stamp and skip
            skipped += 1
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET profile_nudge_sent_at = NOW() WHERE id = %s",
                        (user_id,),
                    )
                conn.commit()
            except Exception as exc:
                logger.warning("profile_nudge_sweep: stamp skip failed user_id=%s: %s", user_id, exc)
            continue

        try:
            # Stamp first so a mailer crash doesn't re-send on next sweep
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET profile_nudge_sent_at = NOW() WHERE id = %s",
                    (user_id,),
                )
            conn.commit()
        except Exception as exc:
            logger.warning("profile_nudge_sweep: stamp failed user_id=%s: %s", user_id, exc)
            failed += 1
            continue

        body = _build_nudge_body(name, email, missing)
        ok = send_email(
            to_email=email,
            subject="Complete your RicoHunt profile — your job matches are waiting",
            body=body,
        )
        if ok:
            sent += 1
            logger.info("profile_nudge_sweep: sent user_id=%s", user_id)
        else:
            failed += 1
            logger.warning("profile_nudge_sweep: email failed user_id=%s", user_id)

    return {
        "status": "ok",
        "nudges_sent": sent,
        "nudges_failed": failed,
        "skipped": skipped,
    }

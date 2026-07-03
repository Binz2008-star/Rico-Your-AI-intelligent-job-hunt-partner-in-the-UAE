"""Profile completion nudge sweep.

Sends a one-time follow-up email to users who:
  - Registered > 24 hours ago
  - Have never been sent a nudge (profile_nudge_sent_at IS NULL)
  - Still have an incomplete profile: CV missing OR target_roles empty OR preferred_cities empty
  - Are NOT synthetic/test/internal recipients (see _is_synthetic_email)

Invoked by the cron-guarded POST /api/v1/pipeline/profile-nudge endpoint.
Requires migration 029 (profile_nudge_sent_at column on users).
Idempotent: re-running never double-sends because sent_at is stamped before delivery.
Synthetic recipients are also stamped so the cron never retries them.

Schema facts:
  - users.email links to rico_users.external_user_id
  - rico_profiles.user_id references rico_users.id
  - profile fields live in rico_profiles.profile JSONB
  - users has no name column; name comes from rico_users.name
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)

NUDGE_DELAY_HOURS = 24

# ── Synthetic / internal recipient guard ──────────────────────────────────────

_INTERNAL_DOMAIN = "ricohunt.com"

# Matches local parts that are clearly test/dummy/seed/internal accounts.
# user_\d+ covers auto-generated seats like user_1469, user_9000, etc.
_SYNTHETIC_LOCAL_RE = re.compile(
    r"^(?:"
    r"(?:test(?:_user)?|dummy|demo|example|seed|fake)(?:[._+\-].*)?"
    r"|user_\d+"
    r")$",
    re.IGNORECASE,
)


def _is_synthetic_email(email: str) -> bool:
    """Return True for test/dummy/internal addresses that must never receive nudges."""
    try:
        local, domain = email.rsplit("@", 1)
    except ValueError:
        return True  # malformed — exclude
    if domain.lower() == _INTERNAL_DOMAIN:
        return True
    return bool(_SYNTHETIC_LOCAL_RE.match(local))


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
        "────────────────────────────────────────────────",
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

    try:
        # RicoDB.connect() uses RealDictCursor — rows are dicts.
        # ensure_schema=False: we don't need rico DDL here, just queries.
        conn = db.connect(ensure_schema=False)
    except Exception as exc:
        logger.warning("profile_nudge_sweep: connect failed: %s", exc)
        return {"status": "unavailable", "nudges_sent": 0, "nudges_failed": 0, "skipped": 0}

    try:
        with conn.cursor() as cur:
            # Guard: migration 029 adds profile_nudge_sent_at to users
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'profile_nudge_sent_at'
            """)
            if not cur.fetchone():
                logger.warning("profile_nudge_sweep: migration 029 not applied — skipping")
                conn.close()
                return {"status": "migration_pending", "nudges_sent": 0, "nudges_failed": 0, "skipped": 0}

            # Join chain: users → rico_users (via external_user_id) → rico_profiles
            # Profile fields are inside rico_profiles.profile JSONB.
            # timedelta parameter lets psycopg2 produce a safe INTERVAL literal.
            cur.execute("""
                SELECT
                    u.id                               AS user_id,
                    u.email,
                    ru.name,
                    rp.profile->>'cv_filename'         AS cv_filename,
                    rp.profile->'target_roles'         AS target_roles,
                    rp.profile->'preferred_cities'     AS preferred_cities
                FROM users u
                LEFT JOIN rico_users ru
                    ON ru.external_user_id = u.email
                LEFT JOIN rico_profiles rp
                    ON rp.user_id = ru.id
                WHERE u.created_at < NOW() - %s
                  AND u.profile_nudge_sent_at IS NULL
                  AND u.email IS NOT NULL
                ORDER BY u.created_at ASC
                LIMIT 200
            """, (timedelta(hours=NUDGE_DELAY_HOURS),))
            rows = cur.fetchall()
    except Exception as exc:
        logger.warning("profile_nudge_sweep: query failed: %s", exc)
        conn.close()
        return {"status": "error", "nudges_sent": 0, "nudges_failed": 0, "skipped": 0}

    sent = 0
    failed = 0
    skipped = 0
    skipped_synthetic = 0

    for row in rows:
        user_id = row["user_id"]
        email = row["email"]
        name = row["name"]
        # psycopg2 auto-decodes JSONB arrays to Python lists; text fields stay as str/None
        cv_filename: str | None = row["cv_filename"]
        target_roles: list | None = row["target_roles"]
        preferred_cities: list | None = row["preferred_cities"]

        # Synthetic/internal recipient guard — stamp and skip without sending.
        # Logging uses domain only to avoid exposing local parts in logs.
        if _is_synthetic_email(email):
            skipped_synthetic += 1
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET profile_nudge_sent_at = NOW() WHERE id = %s",
                        (user_id,),
                    )
                conn.commit()
                logger.info(
                    "profile_nudge_sweep: skipped synthetic user_id=%s domain=%s",
                    user_id, email.split("@")[-1],
                )
            except Exception as exc:
                logger.warning(
                    "profile_nudge_sweep: stamp-skip-synthetic failed user_id=%s: %s",
                    user_id, exc,
                )
                conn.rollback()
            continue

        missing: list[str] = []
        if not cv_filename:
            missing.append("Upload your CV")
        if not target_roles:
            missing.append("Add your target roles (e.g. 'Marketing Manager', 'Data Analyst')")
        if not preferred_cities:
            missing.append("Add your preferred UAE cities (e.g. Dubai, Abu Dhabi)")

        if not missing:
            # Profile already complete — stamp without sending email
            skipped += 1
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET profile_nudge_sent_at = NOW() WHERE id = %s",
                        (user_id,),
                    )
                conn.commit()
            except Exception as exc:
                logger.warning("profile_nudge_sweep: stamp-skip failed user_id=%s: %s", user_id, exc)
                conn.rollback()
            continue

        # Stamp first — prevents double-send if mailer crashes mid-sweep
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET profile_nudge_sent_at = NOW() WHERE id = %s",
                    (user_id,),
                )
            conn.commit()
        except Exception as exc:
            logger.warning("profile_nudge_sweep: stamp failed user_id=%s: %s", user_id, exc)
            conn.rollback()
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

    conn.close()
    return {
        "status": "ok",
        "nudges_sent": sent,
        "nudges_failed": failed,
        "skipped": skipped,
        "skipped_synthetic": skipped_synthetic,
    }

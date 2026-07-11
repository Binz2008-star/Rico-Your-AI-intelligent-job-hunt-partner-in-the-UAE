#!/usr/bin/env python3
"""
scripts/check_migration_drift.py

Read-only production migration-drift detector.

Numbered SQL migrations under migrations/ are applied manually (no deploy-time
runner), so production can silently fall behind `main` — this caused the 021
(#710) and 005/011 (#712) drift. This script checks that the canonical schema
object each migration introduces is present in the target database and exits
non-zero if any is missing, so a scheduled CI job can alert on drift.

It NEVER writes — only `SELECT` / catalog lookups. Reads DATABASE_URL from the
environment (the same secret the daily workflows use).

Usage:
    DATABASE_URL=postgres://... python scripts/check_migration_drift.py
"""
from __future__ import annotations

import os
import sys

# Each migration maps to one signature object that proves it ran.
# kind: "table" / "view" / "index" -> to_regclass; "column" -> (table, column);
#       "constraint" -> conname; "trigger" -> tgname.
# Migration 020 is a COMMENT-only migration with no detectable object -> omitted.
CHECKS: list[tuple[str, str, object]] = [
    ("005", "table", "pipeline_runs"),
    ("006", "table", "action_audit_log"),
    ("007", "table", "users"),
    ("008", "table", "rico_onboarding_states"),
    ("009", "table", "rico_saved_searches"),
    ("010", "table", "password_reset_tokens"),
    ("011", "index", "idx_rico_recommendations_user_job_unique"),
    ("012", "column", ("rico_saved_searches", "updated_at")),
    ("013", "table", "user_subscriptions"),
    ("014", "constraint", "uq_user_subscriptions_stripe_customer_id"),
    ("015", "column", ("subscription_events", "status")),
    ("016", "column", ("user_subscriptions", "cancel_at")),
    ("017", "column", ("users", "email_verified")),
    ("018", "table", "user_job_context"),
    ("019", "column", ("user_job_context", "last_action")),
    ("021", "column", ("user_job_context", "alt_url")),
    ("022", "column", ("user_job_context", "applied_at")),
    ("023", "column", ("rico_users", "telegram_notifications_enabled")),
    ("024", "column", ("settings", "blocked_companies")),
    ("025", "table", "learning_signals"),
    ("026", "column", ("user_documents", "skills_json")),
    ("027", "column", ("rico_job_recommendations", "follow_up_due_at")),
    ("028", "index", "idx_user_job_context_user_searched_at"),
    ("029", "column", ("users", "profile_nudge_sent_at")),
    ("030", "column", ("action_audit_log", "event_type")),
    ("030", "trigger", "trg_action_audit_log_append_only"),
    ("031", "table", "learning_signals_audit"),
    ("032", "table", "uploaded_document_context"),
    ("033", "table", "email_alert_log"),
    ("035", "constraint", "rico_job_recommendations_user_id_job_key_key"),
    ("036", "column", ("users", "signup_source")),
    ("036", "table", "admin_digest_log"),
    ("037", "column", ("user_documents", "content_hash")),
    ("037", "index", "uq_user_documents_user_type_hash"),
    ("037", "index", "uq_user_documents_one_primary_per_type"),
    ("038", "table", "cv_upload_artifacts"),
    ("039", "table", "waitlist_entries"),
]


def _present(cur, kind: str, ident: object) -> bool:
    if kind in ("table", "view", "index"):
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{ident}",))
    elif kind == "column":
        table, column = ident  # type: ignore[misc]
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s)",
            (table, column),
        )
    elif kind == "constraint":
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = %s)", (ident,))
    elif kind == "trigger":
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = %s)", (ident,))
    else:  # pragma: no cover - guarded by tests
        raise ValueError(f"unknown check kind: {kind}")
    return bool(cur.fetchone()[0])


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 2

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 is required (pip install psycopg2-binary)", file=sys.stderr)
        return 2

    conn = psycopg2.connect(db_url)
    try:
        conn.set_session(readonly=True, autocommit=True)
        missing: list[tuple[str, str, object]] = []
        with conn.cursor() as cur:
            for migration, kind, ident in CHECKS:
                ok = _present(cur, kind, ident)
                label = ident if not isinstance(ident, tuple) else ".".join(ident)
                status = "PRESENT" if ok else "*** MISSING ***"
                print(f"{migration:>4}  {kind:<10} {str(label):<48} {status}")
                if not ok:
                    missing.append((migration, kind, ident))
    finally:
        conn.close()

    print()
    if missing:
        nums = sorted({m for m, _, _ in missing})
        print(f"DRIFT DETECTED: {len(missing)} object(s) missing across migrations {', '.join(nums)}")
        print("Apply the missing migration(s) (verify-first) — see issue #712 for the runbook pattern.")
        return 1

    print(f"OK: all {len(CHECKS)} signature objects present — no migration drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

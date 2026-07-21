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
    ("040", "table", "paddle_customers"),
    ("040", "table", "paddle_subscriptions"),
    ("040", "table", "paddle_webhook_events"),
    ("040", "table", "paddle_checkout_sessions"),
    ("040", "column", ("paddle_subscriptions", "last_event_occurred_at")),
    ("041", "column", ("paddle_subscriptions", "past_due_since")),
    # Gmail read-only connector M0 (migration 043)
    ("043", "table", "gmail_connections"),
    ("043", "table", "gmail_sync_runs"),
    ("043", "table", "gmail_review_items"),
    ("043", "table", "gmail_audit_events"),
    ("043", "index", "uq_gmail_connections_active"),
    ("043", "constraint", "uq_gmail_review_items_user_message"),
    # Per-user recurring-sync consent (fleet-sweep opt-in) — amended into 043.
    ("043", "column", ("gmail_connections", "recurring_sync_consent_at")),
    # Guest merge single-owner claim (#1070)
    ("044", "table", "guest_identity_claims"),
    # Posting-history archive (Product Truth Sprint data-integrity foundation).
    # Expected to report drift after merge until the owner applies 046 — that
    # alert IS the reminder; the archive code no-ops until the table exists.
    ("046", "table", "job_observations"),
    ("046", "index", "idx_job_observations_fingerprint_observed"),
    # Detects a stale pre-review table shape (raw query_context / query_hash).
    ("046", "column", ("job_observations", "query_context_hmac")),
    # First-party analytics event store. Like 046: after merge the drift
    # alert IS the reminder until the owner applies 047; the event store
    # code no-ops (fail-closed) until the table exists.
    ("047", "table", "analytics_events"),
    ("047", "index", "uq_analytics_events_dedupe"),
    # Multi-session chat threads (#1193). Unlike 046/047 this one also lives
    # in the idempotent startup DDL (026 pattern), so it self-applies on the
    # first backend boot after deploy — drift here means the deploy never
    # started, not that a manual apply is pending.
    ("048", "column", ("rico_chat_history", "session_id")),
    # WhatsApp-assisted subscription pending requests (DEC-20260719-003).
    # Additive, entitlement-neutral: rows here never grant access — the code
    # fails closed (503 on the request endpoint) until 049 is applied.
    # 050: profile avatars (owner request 2026-07-21). Avatar endpoints fail
    # open on reads and 503 on writes until 050 is applied.
    ("050", "table", "user_avatars"),
    ("049", "table", "whatsapp_subscription_requests"),
    ("049", "index", "uq_whatsapp_sub_requests_user_pending"),
    ("048", "index", "idx_rico_chat_user_session_created"),
    # Atomic shared operation-ownership store (DEC-20260721-001 slice 1).
    # Renumbered 050→051 (2026-07-21) to resolve the duplicate-050 collision
    # with 050_user_avatars — user_avatars kept 050 (earlier in git history
    # AND created earlier in production per pg_class oid order). Additive and
    # deploy-order safe: until 051 is applied the code falls back to the
    # legacy in-process ownership; the Postgres store activates once the
    # table exists (verified present in production 2026-07-21, read-only).
    ("051", "table", "chat_operations"),
    ("051", "index", "idx_chat_operations_user_latest"),
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

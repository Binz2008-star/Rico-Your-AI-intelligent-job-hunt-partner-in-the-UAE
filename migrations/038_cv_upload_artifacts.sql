-- Migration 038: short-lived server-side CV upload artifact (#963)
--
-- Bridges /api/v1/rico/upload-cv (parse) and /api/v1/rico/confirm-cv-profile
-- (confirm) with a durable, server-derived record of what was actually
-- uploaded: the SHA-256 of the original bytes, byte count, and full parsed
-- text. The client is handed only the opaque `id` (upload_id) — the hash and
-- text are never re-sent by the client and never trusted from it.
--
-- One row per upload (not one row per user, unlike uploaded_document_context
-- from migration 032) so concurrent/multi-tab uploads never collide, and a
-- confirm always resolves the EXACT upload it was issued for. Rows are
-- resolved with `expires_at > now()` — short-lived by design; no confirm can
-- reuse an artifact past its TTL.
--
-- RETENTION / CLEANUP (this table holds the full parsed text of UNCONFIRMED
-- CV uploads, so it must not accumulate):
--   * `expires_at` (default 3h, set by the app) gates *readability*.
--   * Actual *deletion* is done by the application, opportunistically: every
--     create_cv_upload_artifact() call deletes a bounded batch of already-
--     expired rows in the same transaction (see
--     src/repositories/cv_upload_artifact_repo.py purge_expired_cv_upload_artifacts).
--     There is NO background worker on Render, so this amortized cleanup is
--     the deletion mechanism — each create adds one row and removes up to 200
--     expired rows, so the table converges to the live working set instead of
--     growing without bound. The exposed purge function can also back a
--     manual/cron sweep if one is added later.
--
-- ROLLOUT DECISION (explicit, not "same as 032"):
--   Decision: RUNTIME AUTO-APPLY (DDL executed at app startup via
--   src/api/app.py _apply_cv_upload_artifacts -> _apply_sql_migration).
--   Justification: this migration only CREATEs a brand-new, empty, additive
--   table + one secondary index, guarded by IF NOT EXISTS and idempotent per
--   statement. It performs NO ALTER of an existing table, NO backfill, and NO
--   unique index over pre-existing data — i.e. none of the risks that made
--   migration 037 a manual, owner-run, STEP-0-gated migration. So the safe,
--   zero-owner-burden path (matching 028/031/032) is justified here on its own
--   merits, not by analogy alone.
--   Risk & mitigation: _apply_sql_migration logs a warning and continues if the
--   DDL fails (it does not crash the app). A silently-missing table would
--   degrade onboarding CV persistence (confirm-cv-profile can then only 409
--   "please re-upload"), NOT corrupt data or crash. That failure mode is
--   covered by real-Postgres integration proof
--   (tests/integration/test_cv_upload_artifacts_postgres.py, run in the
--   qa-tests.yml postgres-integration job) which applies THIS migration and
--   exercises create/resolve/expiry/purge end-to-end, plus the startup
--   migration_ok/migration_failed log line.
--   Owner override: if the owner prefers manual pre-deploy application (as with
--   037), remove the _apply_cv_upload_artifacts() call from the lifespan and
--   apply this file with `psql "$DATABASE_URL" -f migrations/038_cv_upload_artifacts.sql`
--   before deploying. No code change beyond that call is required.
--
-- Rollback: DROP TABLE IF EXISTS cv_upload_artifacts; (no other table
-- references it; safe to drop any time — it never holds the source of truth,
-- only a transient bridge between two requests).

CREATE TABLE IF NOT EXISTS cv_upload_artifacts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       TEXT        NOT NULL,
    filename      TEXT        NOT NULL,
    doc_type      TEXT        NOT NULL DEFAULT 'cv',
    content_hash  TEXT        NOT NULL,
    file_size     INTEGER     NOT NULL DEFAULT 0,
    cv_text       TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL
);

-- Resolution lookup: id + user_id (server-derived identity) + freshness.
CREATE INDEX IF NOT EXISTS idx_cv_upload_artifacts_user_expires
    ON cv_upload_artifacts (user_id, expires_at DESC);

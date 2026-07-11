-- Migration 037: exact-duplicate protection + single-primary invariant for
-- user_documents (#960)
--
-- Adds a nullable content_hash (SHA-256 hex of the original file bytes) and a
-- PARTIAL unique index so an exact re-upload is caught atomically by the
-- database instead of racing at the application layer. Also adds a PARTIAL
-- unique index enforcing at most one is_primary=TRUE row per (user_id,
-- doc_type), closing the gap where a non-atomic clear-then-set could leave
-- two (or zero) primary rows.
--
-- ============================================================================
-- MIGRATION-BEFORE-DEPLOY SEQUENCE (required — read before merging the PR)
-- ============================================================================
-- This migration is deliberately NOT auto-applied by the application (not in
-- _USER_DOCUMENTS_DDL / _ensure_schema, not in the app.py startup lifespan).
-- Unlike migration 032, which auto-applies via the lifespan runner, 037 must
-- be applied manually — the same model as migrations 033-036 — because the
-- app code in this PR (find_user_document_by_hash, get_or_create_user_document)
-- queries/writes the content_hash column directly and will error with
-- "column content_hash does not exist" if it runs before this migration.
--
-- Required order:
--   1. Run STEP 0 (verification query below) against the target database and
--      confirm zero rows returned. If it returns rows, resolve those
--      duplicate primaries first (see STEP 0 comment) — the primary-invariant
--      index will fail to create otherwise.
--   2. Apply this migration file to the target database (owner-run, staging
--      then production Neon):
--        psql "$DATABASE_URL" -f migrations/037_user_documents_content_hash.sql
--   3. Only then deploy the application code from this PR (Render).
--   4. Do NOT start #963 (onboarding CV persistence) until this sequence has
--      completed and the drift check confirms both new objects are present.
--
-- Fresh/local/test databases (Docker Compose Postgres, a brand-new Neon
-- branch, etc.): apply migrations/*.sql in numeric order the same way — this
-- file is not special-cased by _ensure_schema/init() and must be run
-- explicitly like every other post-026 migration that isn't auto-applied.
--
-- Safety / idempotency:
--   * ADD COLUMN IF NOT EXISTS + CREATE UNIQUE INDEX IF NOT EXISTS — re-runnable.
--   * content_hash is NULLABLE and NOT backfilled here. The content-hash
--     unique index is PARTIAL (WHERE content_hash IS NOT NULL), so all
--     existing/historical rows (content_hash IS NULL) are excluded and cannot
--     collide — no backfill is required for migration safety, and multiple
--     legacy NULL rows stay valid.
--   * New uploads compute content_hash going forward; dedupe applies only to
--     rows that carry a hash.
--
-- STEP 0 — verify no existing (user_id, doc_type) pair already has more than
-- one is_primary=TRUE row before applying (the primary-invariant index below
-- will fail with a unique-violation at CREATE time otherwise, because a
-- partial unique index cannot be created over rows that already violate it):
--
--   SELECT user_id, doc_type, COUNT(*) AS primary_count
--     FROM user_documents
--    WHERE is_primary = TRUE
--    GROUP BY user_id, doc_type
--   HAVING COUNT(*) > 1;
--
-- If this returns any rows, do not apply the primary-invariant index blindly —
-- review and fix those rows first (e.g. keep the most recently updated row as
-- primary, clear the rest), then re-run STEP 0 until it returns zero rows.
--
-- Rollback:
--   DROP INDEX IF EXISTS uq_user_documents_one_primary_per_type;
--   DROP INDEX IF EXISTS uq_user_documents_user_type_hash;
--   ALTER TABLE user_documents DROP COLUMN IF EXISTS content_hash;
--   (Non-destructive to pre-existing document rows.)

ALTER TABLE user_documents ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_documents_user_type_hash
    ON user_documents (user_id, doc_type, content_hash)
    WHERE content_hash IS NOT NULL;

-- Single-primary-per-(user_id, doc_type) invariant. Run STEP 0 above first.
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_documents_one_primary_per_type
    ON user_documents (user_id, doc_type)
    WHERE is_primary = TRUE;

-- Migration 037: exact-duplicate protection for user_documents (#960)
--
-- Adds a nullable content_hash (SHA-256 hex of the original file bytes) and a
-- PARTIAL unique index so an exact re-upload is caught atomically by the
-- database instead of racing at the application layer.
--
-- Safety / idempotency:
--   * ADD COLUMN IF NOT EXISTS + CREATE UNIQUE INDEX IF NOT EXISTS — re-runnable.
--   * content_hash is NULLABLE and NOT backfilled here. The unique index is
--     PARTIAL (WHERE content_hash IS NOT NULL), so all existing/historical rows
--     (content_hash IS NULL) are excluded and cannot collide — no backfill is
--     required for migration safety, and multiple legacy NULL rows stay valid.
--   * New uploads compute content_hash going forward; dedupe applies only to
--     rows that carry a hash.
--
-- Rollback:
--   DROP INDEX IF EXISTS uq_user_documents_user_type_hash;
--   ALTER TABLE user_documents DROP COLUMN IF EXISTS content_hash;
--   (Non-destructive to pre-existing document rows.)
--
-- Apply (staging/local only — do NOT apply to production Neon in this PR):
--   psql "$DATABASE_URL" -f migrations/037_user_documents_content_hash.sql

ALTER TABLE user_documents ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_documents_user_type_hash
    ON user_documents (user_id, doc_type, content_hash)
    WHERE content_hash IS NOT NULL;

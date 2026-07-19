-- Migration 048: multi-session chat threads on rico_chat_history.
--
-- Adds a nullable session_id to rico_chat_history so one user can hold many
-- parallel conversations (the /command Sessions rail). Rows written before
-- this migration keep session_id NULL and are surfaced as the single
-- "default" thread — no backfill, no rewrite, fully backward compatible:
-- clients that never send a session_id keep writing NULL and reading the
-- unfiltered history exactly as before.
--
-- Neon safety: ADD COLUMN with no default is a metadata-only change (no table
-- rewrite, no lock beyond a brief ACCESS EXCLUSIVE); the index build is
-- incremental on a modest table. Mirrored in src/rico_db.py _RICO_SCHEMA_DDL
-- (idempotent startup ensure), following the 026_user_documents_skills_json
-- pattern.

ALTER TABLE rico_chat_history ADD COLUMN IF NOT EXISTS session_id UUID;

-- Session-scoped reads: history for one thread, newest first.
CREATE INDEX IF NOT EXISTS idx_rico_chat_user_session_created
    ON rico_chat_history (user_id, session_id, created_at DESC);

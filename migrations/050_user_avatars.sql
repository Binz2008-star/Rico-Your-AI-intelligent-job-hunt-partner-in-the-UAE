-- 050_user_avatars.sql
-- Profile avatars (owner request 2026-07-21): users can set a profile picture.
--
-- Design notes:
--   * The stack has NO blob storage (user_documents is metadata-only), so the
--     avatar is stored as a compact data URL (image/jpeg|png|webp, client-side
--     downscaled, server-capped at 500 KB) in a DEDICATED table keyed by the
--     user id. A dedicated table — never a profile JSONB key — keeps the
--     base64 payload out of profile fetches and out of the LLM chat context.
--   * Additive and reversible: no existing table is touched.
--
-- Apply explicitly BEFORE deploying the avatar endpoints (same sequence rule
-- as migration 037 — no implicit startup DDL). Rollback: DROP TABLE user_avatars;

CREATE TABLE IF NOT EXISTS user_avatars (
    user_id TEXT PRIMARY KEY,
    data_url TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'image/jpeg',
    byte_size INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
-- This is a brand-new, additive table — safe to auto-apply on every process's
-- first DB connect (see src/api/app.py _apply_cv_upload_artifacts), the same
-- pattern already used for migration 032. Unlike migration 037, this does not
-- touch an existing table with production data, so no manual pre-deploy
-- sequence is required.
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

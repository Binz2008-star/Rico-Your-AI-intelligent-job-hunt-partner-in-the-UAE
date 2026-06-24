-- migrations/032_uploaded_document_context.sql
-- Persist the transcript of the most recently uploaded image/document per user so
-- follow-up chat ("summarize this", "extract key information", "what do you think
-- of this job?") can always retrieve it.
--
-- The JSON memory store (RicoMemoryStore) is a no-op under
-- RICO_MEMORY_BACKEND=postgres and is wiped by Render restarts / multiple
-- instances, so the OCR transcript a user just uploaded would not survive to the
-- follow-up turn. This table keeps the latest transcript per user durably.
--
-- One row per user_id (the latest upload upserts). Keyed by the resolved user or
-- public-session id so both authenticated and public sessions are covered.

CREATE TABLE IF NOT EXISTS uploaded_document_context (
    user_id        TEXT        PRIMARY KEY,
    filename       TEXT,
    document_type  TEXT,
    display_label  TEXT,
    source         TEXT        NOT NULL DEFAULT 'image',
    extracted_text TEXT        NOT NULL,
    request_ref    TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Freshness lookups (latest transcript within a recency window).
CREATE INDEX IF NOT EXISTS idx_udc_user_updated
    ON uploaded_document_context (user_id, updated_at DESC);

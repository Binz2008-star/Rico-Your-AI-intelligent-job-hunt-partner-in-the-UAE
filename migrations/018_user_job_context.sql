-- migrations/018_user_job_context.sql
-- Persist Rico job-search results so apply/source links survive across turns,
-- Render restarts, and RICO_MEMORY_BACKEND=postgres mode.

CREATE TABLE IF NOT EXISTS user_job_context (
    id               SERIAL      PRIMARY KEY,
    user_id          TEXT        NOT NULL,
    title            TEXT        NOT NULL,
    company          TEXT        NOT NULL,
    location         TEXT,
    apply_url        TEXT        NOT NULL DEFAULT '',
    source_url       TEXT        NOT NULL DEFAULT '',
    verification_status TEXT     NOT NULL DEFAULT 'lead_needs_verification',
    searched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookups for the open_apply_link handler (recent matches per user).
CREATE INDEX IF NOT EXISTS idx_ujc_user_searched
    ON user_job_context (user_id, searched_at DESC);

-- Prevent exact duplicate rows for the same user+title+company within the same
-- search batch by upserting on this constraint.
CREATE UNIQUE INDEX IF NOT EXISTS idx_ujc_user_title_company
    ON user_job_context (user_id, lower(title), lower(company));

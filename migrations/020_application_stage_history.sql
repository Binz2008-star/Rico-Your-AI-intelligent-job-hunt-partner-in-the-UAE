-- migrations/020_application_stage_history.sql
-- Application Lifecycle: append-only stage transition log for tracked
-- applications (rico_job_recommendations). Additive, non-destructive.
--
-- The pipeline status lives on rico_job_recommendations.status (the live SaaS
-- table). This migration adds a per-stage timestamp and a transition audit
-- trail so Rico can answer "what's the status of my Halcyon application?" and
-- "when did it move to interview?".

-- 1. Per-stage entry timestamp for fast "since when" queries without a join.
--    Backfilled to updated_at/created_at for existing rows.
ALTER TABLE rico_job_recommendations
    ADD COLUMN IF NOT EXISTS stage_changed_at TIMESTAMPTZ;

UPDATE rico_job_recommendations
    SET stage_changed_at = COALESCE(updated_at, created_at, now())
    WHERE stage_changed_at IS NULL;

-- 2. Append-only transition history.
CREATE TABLE IF NOT EXISTS application_stage_history (
    id           BIGSERIAL   PRIMARY KEY,
    user_id      UUID        NOT NULL REFERENCES rico_users(id) ON DELETE CASCADE,
    job_key      TEXT        NOT NULL,
    from_stage   TEXT,                              -- NULL on first entry
    to_stage     TEXT        NOT NULL,
    note         TEXT,
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-application history, newest first.
CREATE INDEX IF NOT EXISTS idx_ash_user_job
    ON application_stage_history (user_id, job_key, changed_at DESC);

-- Aggregate queries ("how many moved to interview").
CREATE INDEX IF NOT EXISTS idx_ash_user_to_stage
    ON application_stage_history (user_id, to_stage);

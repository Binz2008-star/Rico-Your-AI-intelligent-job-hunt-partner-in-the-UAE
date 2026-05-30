-- migrations/022_user_job_context_lifecycle.sql
-- Application Lifecycle: per-stage timestamps on user_job_context so Rico can
-- track and answer questions about where each job sits in the funnel
-- (found → saved → opened_external → prepared → applied → interviewing → ...).
--
-- The coarse `status` column already exists (migration 019). This migration
-- adds the four explicit stage timestamps the product spec calls for, plus an
-- index for status-filtered lookups. Additive, non-destructive, idempotent.

ALTER TABLE user_job_context
    ADD COLUMN IF NOT EXISTS saved_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS opened_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS prepared_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS applied_at  TIMESTAMPTZ;

-- Fast "show saved / applied / opened-not-applied" queries per user.
CREATE INDEX IF NOT EXISTS idx_ujc_user_status
    ON user_job_context (user_id, status, searched_at DESC);

-- Migration 027: Follow-up reminders (Issue #355, Phase 1)
-- Adds lifecycle timestamps to rico_job_recommendations so a follow-up can be
-- scheduled a fixed interval after a job is marked applied, then surfaced on /flow.
--
-- APPLY THIS TO NEON BEFORE DEPLOYING THE #355 CODE.
-- The application code degrades safely if these columns are missing (timestamp
-- stamping no-ops, the reminders scan returns an error summary), but the feature
-- only works once this migration is applied.

ALTER TABLE rico_job_recommendations
    ADD COLUMN IF NOT EXISTS applied_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS follow_up_due_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_followup_at TIMESTAMPTZ;

-- Best-effort backfill: existing applied rows get applied_at from updated_at so
-- they enter the reminder window based on their last known transition time.
UPDATE rico_job_recommendations
SET applied_at = updated_at
WHERE status = 'applied' AND applied_at IS NULL;

-- Index for the reminder sweep (applied rows ordered by applied_at).
CREATE INDEX IF NOT EXISTS idx_rico_recommendations_status_applied_at
ON rico_job_recommendations (status, applied_at)
WHERE status = 'applied';

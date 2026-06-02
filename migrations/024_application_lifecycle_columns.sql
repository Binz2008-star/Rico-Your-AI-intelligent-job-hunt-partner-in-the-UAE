-- Migration 024: Application lifecycle timestamp columns + status normalisation
--
-- Adds saved_at/opened_at/prepared_at/applied_at to rico_job_recommendations so
-- the SaaS recommendation table has the same stage-timestamp granularity as
-- user_job_context (which already has these columns from migration 022).
--
-- Also corrects the historical "interviewing" → "interview" inconsistency that
-- exists between job_lifecycle.py and applications.py / rico_db stats queries.
--
-- The CHECK constraint is added only after normalising existing rows, so it
-- will never fail on production data that was written before this migration.

-- 1. Lifecycle timestamp columns (safe: all nullable, no default pressure)
ALTER TABLE rico_job_recommendations
    ADD COLUMN IF NOT EXISTS saved_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS opened_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS prepared_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS applied_at  TIMESTAMPTZ;

-- 2. Normalise "interviewing" → "interview" on any rows written before this
--    migration (handles data from job_lifecycle.py which used "interviewing").
UPDATE rico_job_recommendations
   SET status = 'interview'
 WHERE status = 'interviewing';

-- 3. Add CHECK constraint now that all rows are normalised.
--    Using a named constraint so it can be inspected or dropped by name.
--    Lists every status value the application code is permitted to write.
ALTER TABLE rico_job_recommendations
    DROP CONSTRAINT IF EXISTS chk_recommendation_status,
    ADD CONSTRAINT chk_recommendation_status CHECK (
        status IN (
            'found',
            'saved',
            'opened_external',
            'prepared',
            'applied',
            'interview',
            'offer',
            'rejected',
            'withdrawn',
            'expired',
            'archived',
            'on_hold',
            'needs_source_verification',
            'needs_review'
        )
    );

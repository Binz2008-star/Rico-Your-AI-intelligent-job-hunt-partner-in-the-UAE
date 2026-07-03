-- Migration 035: Codify the full UNIQUE (user_id, job_key) on rico_job_recommendations.
--
-- Production carries this constraint as rico_job_recommendations_user_id_job_key_key
-- (a full UNIQUE index on (user_id, job_key)). Migration 034 relies on it to cover the
-- two plain (user_id, job_key) indexes it drops. But nothing in the repo creates it:
-- src/rico_db.py's CREATE TABLE declares no (user_id, job_key) uniqueness, and only the
-- PARTIAL unique idx_rico_recommendations_user_job_unique (WHERE job_key IS NOT NULL) is
-- created, by migration 011. A database built fresh from code would therefore lack this
-- covering unique, and 034's drops would leave a (user_id, job_key) coverage gap.
--
-- This migration records the constraint so code and production agree. It is idempotent:
-- a no-op on every environment that already has it (all current ones). Adding it cannot
-- fail on duplicates -- the partial unique from 011 already forbids duplicate non-NULL
-- (user_id, job_key) pairs, and NULL job_key rows are treated as distinct.
--
-- The partial unique (011) STAYS. It is the named ON CONFLICT arbiter for
-- upsert_recommendation (ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL) and
-- must not be replaced by this full constraint.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'rico_job_recommendations_user_id_job_key_key'
    ) THEN
        ALTER TABLE rico_job_recommendations
            ADD CONSTRAINT rico_job_recommendations_user_id_job_key_key
            UNIQUE (user_id, job_key);
    END IF;
END$$;

-- Migration 029: Profile completion nudge tracking
-- Adds profile_nudge_sent_at to users so the cron sweep never double-sends.
--
-- APPLY THIS TO NEON BEFORE DEPLOYING THE PROFILE NUDGE CODE.
-- The service degrades safely if the column is missing (scan returns an error
-- summary instead of a 500), but nudges are only sent once the column exists.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS profile_nudge_sent_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_profile_nudge_sent_at
ON users (created_at)
WHERE profile_nudge_sent_at IS NULL;

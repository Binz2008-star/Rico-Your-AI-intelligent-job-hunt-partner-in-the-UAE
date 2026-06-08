-- migrations/024_blocked_companies.sql
-- Persist user-specific blocked companies in the settings table.
-- Run once: psql $DATABASE_URL -f migrations/024_blocked_companies.sql

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS blocked_companies TEXT[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN settings.blocked_companies IS 'Companies the user has blocked from appearing in their job feed';

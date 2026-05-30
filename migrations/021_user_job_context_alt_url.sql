-- migrations/021_user_job_context_alt_url.sql
-- Persist the JSearch alternate link (job_google_link) alongside apply_url and
-- source_url so the frontend apply-fallback chain can offer an alternate link
-- when the primary apply URL is rate-limited or unavailable. Additive, safe.

ALTER TABLE user_job_context
    ADD COLUMN IF NOT EXISTS alt_url TEXT NOT NULL DEFAULT '';

-- migrations/020_user_job_context_gap_filler.sql
-- This migration fills the sequence gap between 019 and 021.
-- Migration 020 was inadvertently omitted from the repository; this stub ensures
-- migration runners that require a contiguous sequence do not fail on DB reconstitution.
--
-- Safe to run against any DB state: the COMMENT statement is idempotent.
-- No schema changes — all required columns were added by migrations 018, 019, 021, and 022.

COMMENT ON TABLE user_job_context IS
    'Per-user job match context: interaction state, lifecycle timestamps, and URL variants. '
    'Schema built by migrations 018 (base), 019 (interaction), 021 (alt_url), 022 (lifecycle).';

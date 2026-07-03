-- Migration 034: Drop redundant duplicate indexes (write-amplification cleanup).
--
-- A read-optimization audit (2026-07-03, verified against live pg_indexes.indexdef)
-- found several byte-identical or unique-index-covered duplicate indexes on the
-- hottest per-user tables. They add nothing for reads but tax every INSERT/UPDATE
-- and waste storage. Each DROP below is confirmed redundant against an index that
-- REMAINS in place:
--
--   rico_job_recommendations — two NON-unique (user_id, job_key) indexes, both
--     already covered by:
--       * UNIQUE rico_job_recommendations_user_id_job_key_key (user_id, job_key)
--       * partial UNIQUE idx_rico_recommendations_user_job_unique
--           (user_id, job_key) WHERE job_key IS NOT NULL  ← powers the ON CONFLICT
--           upsert in rico_db.upsert_recommendation. DO NOT DROP.
--   rico_profiles — idx_rico_profiles_user_id duplicates UNIQUE rico_profiles_user_id_key.
--   users — idx_users_email duplicates UNIQUE users_email_key.
--   rico_saved_searches — rico_saved_searches_user_id_idx is an exact duplicate of
--     idx_rico_saved_searches_user_created (user_id, created_at DESC).
--   user_job_context — idx_ujc_user_searched is an exact duplicate of
--     idx_user_job_context_user_searched_at. Keep the latter: it is the
--     migration-028 signature object checked by scripts/check_migration_drift.py.
--
-- APPLY MANUALLY AT THE NEON CONSOLE (owner-gated — this touches production).
-- CONCURRENTLY avoids table locks; each statement must run on its own because
-- DROP INDEX CONCURRENTLY cannot run inside a transaction block. IF EXISTS makes
-- it safe to re-run. Rollback = recreate any dropped index (original defs are in
-- the PR description).

DROP INDEX CONCURRENTLY IF EXISTS idx_rico_job_recommendations_user_job_key;
DROP INDEX CONCURRENTLY IF EXISTS idx_rico_recommendations_user_job_key;
DROP INDEX CONCURRENTLY IF EXISTS idx_rico_profiles_user_id;
DROP INDEX CONCURRENTLY IF EXISTS rico_saved_searches_user_id_idx;
DROP INDEX CONCURRENTLY IF EXISTS idx_ujc_user_searched;
DROP INDEX CONCURRENTLY IF EXISTS idx_users_email;

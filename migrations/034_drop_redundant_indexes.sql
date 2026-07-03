-- Migration 034: Drop redundant duplicate indexes (write-side housekeeping).
--
-- OWNER-GATED, NON-DESTRUCTIVE. Apply manually at Neon; this is NOT auto-deployed.
-- No data is touched — only redundant index objects are removed. Every statement
-- is idempotent (IF EXISTS), so the migration is safe to re-run.
--
-- WHY: production carries 8 indexes whose leading-column coverage is already
-- provided by another index that MUST stay (a UNIQUE constraint, a superset
-- composite, or a byte-for-byte twin). Redundant indexes are dead weight on the
-- read side but tax every INSERT/UPDATE and waste storage/Neon compute. Verified
-- against live pg_indexes.indexdef on 2026-07-03.
--
-- LOCKING: a plain DROP INDEX takes a brief ACCESS EXCLUSIVE lock on the parent
-- table. These are per-user tables and the drops are near-instant metadata ops.
-- If any table has grown large, run the individual statements with
-- `DROP INDEX CONCURRENTLY IF EXISTS ...` OUTSIDE a transaction instead.
--
-- INVARIANTS PRESERVED (do NOT drop these — they are the reason each drop below
-- is safe, and two are load-bearing):
--   * idx_rico_recommendations_user_job_unique  — partial UNIQUE; the arbiter for
--     `ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL`
--     (src/rico_db.py upsert_recommendation, BUG-14). Dropping it => 42P10.
--   * idx_user_job_context_user_searched_at      — kept over its twin because it is
--     migration 028's drift-checker signature object.
--   * rico_job_recommendations_user_id_job_key_key, rico_profiles_user_id_key,
--     users_email_key                            — UNIQUE constraints; their implicit
--     btree serves the (user_id, job_key) / (user_id) / (email) lookups below.

-- rico_job_recommendations ---------------------------------------------------
-- (user_id, job_key) point lookups are served by the UNIQUE constraint
-- rico_job_recommendations_user_id_job_key_key. Both non-unique twins are dead.
DROP INDEX IF EXISTS idx_rico_job_recommendations_user_job_key;
DROP INDEX IF EXISTS idx_rico_recommendations_user_job_key;
-- (user_id, status) is a leading-column subset of
-- idx_rico_recommendations_user_status_updated (user_id, status, updated_at DESC).
DROP INDEX IF EXISTS idx_rico_recommendations_user_status;

-- rico_profiles --------------------------------------------------------------
-- (user_id) is served by the UNIQUE rico_profiles_user_id_key.
DROP INDEX IF EXISTS idx_rico_profiles_user_id;

-- rico_saved_searches --------------------------------------------------------
-- (user_id) is a leading-column subset of idx_rico_saved_searches_user_created
-- (user_id, created_at DESC); rico_saved_searches_user_id_idx is a byte-for-byte
-- twin of that same composite.
DROP INDEX IF EXISTS idx_rico_saved_searches_user_id;
DROP INDEX IF EXISTS rico_saved_searches_user_id_idx;

-- user_job_context -----------------------------------------------------------
-- idx_ujc_user_searched is a byte-for-byte twin of
-- idx_user_job_context_user_searched_at (kept — see invariants above).
DROP INDEX IF EXISTS idx_ujc_user_searched;

-- users ----------------------------------------------------------------------
-- (email) is served by the UNIQUE users_email_key. The case-insensitive
-- idx_users_email_lower (lower(email)) is a DIFFERENT index and stays.
DROP INDEX IF EXISTS idx_users_email;

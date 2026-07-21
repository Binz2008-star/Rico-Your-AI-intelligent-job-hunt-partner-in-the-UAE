-- Migration 050: chat_operations — atomic shared ownership store for chat
-- job-search operations (DEC-20260721-001, stabilization slice 1).
--
-- Why: duplicate-execution ownership currently lives in process memory with a
-- process-nonce liveness proof (src/services/operation_state.py). That model
-- is safe ONLY with exactly one Render instance and one uvicorn worker — a
-- concurrently-alive second process is indistinguishable from a dead one, so
-- it would release ownership and run a duplicate provider cascade (pinned by
-- tests/unit/test_operation_duplicate_guard.py). This table moves ownership
-- into Postgres where claims are serialized by a row lock and liveness is a
-- heartbeat lease (the executor renews heartbeat_at from a dedicated thread;
-- a dead process stops renewing, so lease expiry is proof of executor death —
-- strictly stronger than the nonce, and valid across any number of workers).
--
-- Deploy order safety: the application ships with a graceful fallback — until
-- this table exists, operation_state keeps the current in-process behavior
-- unchanged (single-worker invariant still applies). Apply this migration,
-- then the Postgres store activates on its own (DATABASE_URL present).
-- Scaling workers/instances stays BLOCKED until the multi-worker validation
-- slice (DEC-20260721-001 slice 4) passes on top of this store.
--
-- Privacy: role_query holds the same user-scoped search text the current
-- implementation already persists per-user in the RicoMemoryStore mirror; it
-- is operational per-user state (owner-readable by that user only through
-- status endpoints), never analytics. No third-party identifiers are stored.
--
-- Retention: rows are small and per-search-turn; a scheduled purge of old
-- terminal rows is a follow-up slice (monitoring slice 2) — this migration
-- deliberately adds no cron surface.
--
-- Idempotent: safe to re-run (IF NOT EXISTS everywhere).
-- Rollback: revert the application commit (fallback path resumes); the table
-- can then be dropped with: DROP TABLE IF EXISTS chat_operations;

CREATE TABLE IF NOT EXISTS chat_operations (
    operation_id   TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL,
    op_type        TEXT NOT NULL DEFAULT 'job_search',
    role_query     TEXT,
    status         TEXT NOT NULL,
    attempt        INTEGER NOT NULL DEFAULT 1,
    executor_nonce TEXT NOT NULL,
    heartbeat_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    result_count   INTEGER,
    error          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at   TIMESTAMPTZ
);

-- Latest-operation lookup per user (get_latest_job_search_operation).
CREATE INDEX IF NOT EXISTS idx_chat_operations_user_latest
    ON chat_operations (user_id, created_at DESC);

-- Migration 025: learning_signals table
-- Stores per-user behavioral signals used by LearningRepository.
-- The table is also auto-created at runtime by _db_write_signal() as a safety
-- net; this migration ensures it exists before the first write so the runtime
-- CREATE TABLE path is never exercised under production load.

CREATE TABLE IF NOT EXISTS learning_signals (
    id                  SERIAL PRIMARY KEY,
    canonical_user_id   VARCHAR(255) NOT NULL,
    signal_type         VARCHAR(100) NOT NULL,
    signal_value        TEXT         NOT NULL,
    signal_weight       FLOAT        NOT NULL,
    source              VARCHAR(50)  NOT NULL,
    timestamp           TIMESTAMP WITH TIME ZONE NOT NULL,
    metadata            JSONB,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_signals_user_timestamp
    ON learning_signals (canonical_user_id, timestamp DESC);

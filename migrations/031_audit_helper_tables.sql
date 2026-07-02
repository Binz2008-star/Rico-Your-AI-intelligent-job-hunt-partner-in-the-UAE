-- migrations/031_audit_helper_tables.sql
-- Bring the three audit helper tables that were previously created on-demand
-- by audit_repo.py under the migration system.
--
-- All statements use IF NOT EXISTS so this migration is safe to re-run and safe
-- to apply on databases where the tables were already created at runtime.
--
-- Apply before (or together with) any code deploy that removes the runtime DDL:
--   psql $DATABASE_URL -f migrations/031_audit_helper_tables.sql

CREATE TABLE IF NOT EXISTS learning_signals_audit (
    id                  SERIAL       PRIMARY KEY,
    canonical_user_id   VARCHAR(255) NOT NULL,
    signal_type         VARCHAR(100) NOT NULL,
    signal_value        TEXT         NOT NULL,
    signal_weight       FLOAT        NOT NULL,
    source              VARCHAR(50)  NOT NULL,
    metadata            JSONB,
    timestamp           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_signals_audit_user
    ON learning_signals_audit (canonical_user_id, timestamp DESC);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS profile_hydration_audit (
    id                  SERIAL       PRIMARY KEY,
    canonical_user_id   VARCHAR(255) NOT NULL,
    hydration_sources   TEXT[]       NOT NULL,
    completeness_before FLOAT        NOT NULL,
    completeness_after  FLOAT        NOT NULL,
    timestamp           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profile_hydration_audit_user
    ON profile_hydration_audit (canonical_user_id, timestamp DESC);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS permission_check_audit (
    id                    SERIAL       PRIMARY KEY,
    canonical_user_id     VARCHAR(255) NOT NULL,
    intent                VARCHAR(100) NOT NULL,
    permission_level      VARCHAR(50)  NOT NULL,
    allowed               BOOLEAN      NOT NULL,
    requires_confirmation BOOLEAN      NOT NULL,
    timestamp             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_permission_check_audit_user
    ON permission_check_audit (canonical_user_id, timestamp DESC);

-- Rollback (manual, only if explicitly approved):
-- DROP TABLE IF EXISTS permission_check_audit;
-- DROP TABLE IF EXISTS profile_hydration_audit;
-- DROP TABLE IF EXISTS learning_signals_audit;

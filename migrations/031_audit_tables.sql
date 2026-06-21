-- Migration 031: audit tables for learning signals, profile hydration, and permission checks.
--
-- These tables were previously auto-created by audit_repo.py at runtime via
-- inline DDL. This migration ensures they exist before the first write so the
-- runtime CREATE TABLE path is never exercised under production load (and so
-- the DB user does not need DDL privileges during request handling).

CREATE TABLE IF NOT EXISTS learning_signals_audit (
    id                  SERIAL PRIMARY KEY,
    canonical_user_id   VARCHAR(255) NOT NULL,
    signal_type         VARCHAR(100) NOT NULL,
    signal_value        TEXT         NOT NULL,
    signal_weight       FLOAT        NOT NULL,
    source              VARCHAR(50)  NOT NULL,
    metadata            JSONB,
    timestamp           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_signals_audit_user
    ON learning_signals_audit (canonical_user_id, timestamp);


CREATE TABLE IF NOT EXISTS profile_hydration_audit (
    id                   SERIAL PRIMARY KEY,
    canonical_user_id    VARCHAR(255) NOT NULL,
    hydration_sources    TEXT[]       NOT NULL,
    completeness_before  FLOAT        NOT NULL,
    completeness_after   FLOAT        NOT NULL,
    timestamp            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profile_hydration_audit_user
    ON profile_hydration_audit (canonical_user_id, timestamp);


CREATE TABLE IF NOT EXISTS permission_check_audit (
    id                      SERIAL PRIMARY KEY,
    canonical_user_id       VARCHAR(255) NOT NULL,
    intent                  VARCHAR(100) NOT NULL,
    permission_level        VARCHAR(50)  NOT NULL,
    allowed                 BOOLEAN      NOT NULL,
    requires_confirmation   BOOLEAN      NOT NULL,
    timestamp               TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_permission_check_audit_user
    ON permission_check_audit (canonical_user_id, timestamp);

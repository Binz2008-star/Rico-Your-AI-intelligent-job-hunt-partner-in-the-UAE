-- Migration 030: Harden the existing action_audit_log.
--
-- This migration owns the general-event columns that were previously added
-- by write_audit_log() during request handling. It also enforces the existing
-- append-only contract at the database layer.
--
-- Apply before deploying code that writes event_type/data without runtime DDL:
--   psql $DATABASE_URL -f migrations/030_action_audit_log_hardening.sql

ALTER TABLE action_audit_log
    ADD COLUMN IF NOT EXISTS event_type TEXT,
    ADD COLUMN IF NOT EXISTS data JSONB;

CREATE INDEX IF NOT EXISTS idx_action_audit_event_type_timestamp
    ON action_audit_log (event_type, timestamp DESC)
    WHERE event_type IS NOT NULL;

CREATE OR REPLACE FUNCTION reject_action_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'action_audit_log is append-only; % is not allowed',
        TG_OP
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_action_audit_log_append_only
    ON action_audit_log;

CREATE TRIGGER trg_action_audit_log_append_only
    BEFORE UPDATE OR DELETE OR TRUNCATE ON action_audit_log
    FOR EACH STATEMENT
    EXECUTE FUNCTION reject_action_audit_log_mutation();

-- Rollback (manual, only if explicitly approved):
-- DROP TRIGGER IF EXISTS trg_action_audit_log_append_only ON action_audit_log;
-- DROP FUNCTION IF EXISTS reject_action_audit_log_mutation();
-- DROP INDEX IF EXISTS idx_action_audit_event_type_timestamp;
-- ALTER TABLE action_audit_log DROP COLUMN IF EXISTS data;
-- ALTER TABLE action_audit_log DROP COLUMN IF EXISTS event_type;

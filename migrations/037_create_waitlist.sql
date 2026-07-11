-- 037_create_waitlist.sql
-- Owner-approved pre-launch waitlist intake.
-- Additive and idempotent. No destructive rollback is required.

BEGIN;

CREATE TABLE IF NOT EXISTS waitlist_entries (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    email_normalized TEXT NOT NULL UNIQUE,
    first_name TEXT,
    target_role TEXT,
    location TEXT,
    consent BOOLEAN NOT NULL,
    consent_version TEXT NOT NULL DEFAULT '2026-07-11',
    source JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved', 'invited', 'activated', 'unsubscribed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    invited_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_waitlist_entries_status
    ON waitlist_entries(status);

CREATE INDEX IF NOT EXISTS idx_waitlist_entries_created_at
    ON waitlist_entries(created_at DESC);

CREATE OR REPLACE FUNCTION set_waitlist_entries_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_waitlist_entries_updated_at ON waitlist_entries;
CREATE TRIGGER trg_waitlist_entries_updated_at
BEFORE UPDATE ON waitlist_entries
FOR EACH ROW
EXECUTE FUNCTION set_waitlist_entries_updated_at();

COMMIT;

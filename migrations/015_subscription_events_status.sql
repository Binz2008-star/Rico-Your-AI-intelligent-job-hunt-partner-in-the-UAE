-- migrations/015_subscription_events_status.sql
-- Add status tracking to subscription_events.
--
-- status values:
--   'pending'   -- claimed by a worker, handler in-flight
--   'processed' -- handler completed successfully (or event intentionally skipped)
--   'failed'    -- handler raised an exception; eligible for replay
--
-- record_subscription_event uses ON CONFLICT DO UPDATE WHERE status='failed'
-- so failed events are re-claimable on retry while processed ones are not.

ALTER TABLE subscription_events
    ADD COLUMN IF NOT EXISTS status       TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS error_detail TEXT,
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS payload_redacted_at TIMESTAMPTZ;

-- Migration 013 defined processed_at as NOT NULL DEFAULT NOW(), so the
-- ADD COLUMN IF NOT EXISTS above silently skipped it.  The column keeps its
-- original NOT NULL DEFAULT NOW() constraint, which stamps every INSERT with
-- the current time — making all events look processed before any handler runs.
-- Fix: drop the default and the NOT NULL so processed_at is only set when
-- update_subscription_event_status marks an event 'processed'.
--
-- Wrapped in a DO block for idempotency: ALTER COLUMN DROP NOT NULL errors
-- on PostgreSQL < 14 if the column is already nullable (e.g. migration runs
-- twice or 013 never added the NOT NULL constraint).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name  = 'subscription_events'
           AND column_name = 'processed_at'
           AND column_default IS NOT NULL
    ) THEN
        ALTER TABLE subscription_events
            ALTER COLUMN processed_at DROP DEFAULT;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name  = 'subscription_events'
           AND column_name = 'processed_at'
           AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE subscription_events
            ALTER COLUMN processed_at DROP NOT NULL;
    END IF;
END $$;

-- Treat all pre-migration events as successfully processed.
UPDATE subscription_events
   SET status = 'processed'
 WHERE status = 'pending';

-- For pre-migration rows now marked processed, preserve their original
-- processed_at (it was the INSERT time from 013, which is the best proxy
-- for when the event was handled).  Only NULL-out rows that remain pending.
UPDATE subscription_events SET processed_at = NULL WHERE status != 'processed';

-- Index to quickly locate failed events for replay queries.
CREATE INDEX IF NOT EXISTS idx_subscription_events_failed
    ON subscription_events (status)
 WHERE status = 'failed';

-- Index for archival cleanup (processed events older than retention window)
CREATE INDEX IF NOT EXISTS idx_subscription_events_archive_cleanup
    ON subscription_events (status, processed_at)
 WHERE archived_at IS NULL;

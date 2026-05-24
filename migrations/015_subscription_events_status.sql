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

-- Treat all pre-migration events as successfully processed.
UPDATE subscription_events
   SET status = 'processed'
 WHERE status = 'pending';

-- Index to quickly locate failed events for replay queries.
CREATE INDEX IF NOT EXISTS idx_subscription_events_failed
    ON subscription_events (status)
 WHERE status = 'failed';

-- Index for archival cleanup (processed events older than retention window)
CREATE INDEX IF NOT EXISTS idx_subscription_events_archive_cleanup
    ON subscription_events (status, created_at)
 WHERE archived_at IS NULL;

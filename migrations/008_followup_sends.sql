-- Follow-up sends table with idempotency
-- Prevents duplicate follow-up emails using database-level UNIQUE constraint
-- Uses insert-before-send pattern for safe deduplication

CREATE TABLE IF NOT EXISTS followup_sends (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    followup_day INT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    job_title TEXT NOT NULL,
    job_company TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'send_unknown', 'retryable_failed', 'unknown')),
    sent_at TIMESTAMPTZ,
    provider_message_id TEXT,
    error_message TEXT,
    send_attempts INT NOT NULL DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Database-level enforcement of identity & process idempotency
    CONSTRAINT uq_user_job_day UNIQUE (user_id, job_id, followup_day)
);

-- Index for faster lookups by user
CREATE INDEX IF NOT EXISTS idx_followup_sends_user_id ON followup_sends(user_id);

-- Composite index for user/job lookups (optimized for common queries)
CREATE INDEX IF NOT EXISTS idx_followup_sends_user_job ON followup_sends(user_id, job_id);

-- Index for faster lookups by job
CREATE INDEX IF NOT EXISTS idx_followup_sends_job_id ON followup_sends(job_id);

-- Index for pending follow-ups (for retry)
CREATE INDEX IF NOT EXISTS idx_followup_sends_status_pending ON followup_sends(status) WHERE status = 'pending';

-- Index for retryable failed follow-ups
CREATE INDEX IF NOT EXISTS idx_followup_sends_status_retryable ON followup_sends(status) WHERE status = 'retryable_failed';

-- Index for unknown status (for reconciliation)
CREATE INDEX IF NOT EXISTS idx_followup_sends_status_unknown ON followup_sends(status) WHERE status = 'unknown';

-- Index for created_at (for cleanup)
CREATE INDEX IF NOT EXISTS idx_followup_sends_created_at ON followup_sends(created_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_followup_sends_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS trigger_update_followup_sends_updated_at ON followup_sends;
CREATE TRIGGER trigger_update_followup_sends_updated_at
    BEFORE UPDATE ON followup_sends
    FOR EACH ROW
    EXECUTE FUNCTION update_followup_sends_updated_at();

-- Comment on table
COMMENT ON TABLE followup_sends IS 'Tracks follow-up email sends with idempotency to prevent duplicates';

-- Comment on idempotency_key
COMMENT ON COLUMN followup_sends.idempotency_key IS 'Unique key combining user_id, job_id, and followup_day to prevent duplicate sends';

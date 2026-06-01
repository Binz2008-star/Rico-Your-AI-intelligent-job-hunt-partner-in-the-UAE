-- migrations/023_telegram_notifications.sql
-- Telegram notifications: opt-in flag on rico_users + alert log for
-- duplicate prevention and per-user daily rate limiting.
-- Additive, non-destructive, idempotent.

ALTER TABLE rico_users
    ADD COLUMN IF NOT EXISTS telegram_notifications_enabled BOOLEAN DEFAULT TRUE;

-- telegram_alert_log records every job-alert sent so Rico never sends the
-- same job to the same user twice and can enforce a daily send cap.
CREATE TABLE IF NOT EXISTS telegram_alert_log (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    job_key     TEXT        NOT NULL,
    alert_type  TEXT        NOT NULL DEFAULT 'job_match',
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, job_key, alert_type)
);

CREATE INDEX IF NOT EXISTS idx_tal_user_sent
    ON telegram_alert_log (user_id, sent_at DESC);

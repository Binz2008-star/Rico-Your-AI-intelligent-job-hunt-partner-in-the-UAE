-- Migration 033: Personalized job-alert emails (PR-1 plumbing)
-- Adds the two tables the email alert feature needs. Additive, non-destructive,
-- idempotent. Opt-in state and frequency ride in rico_agent_settings.settings
-- (JSONB) and need NO schema change.
--
-- APPLY THIS TO NEON BEFORE DEPLOYING THE EMAIL-ALERT SENDING CODE (PR-2).
-- PR-1 only writes/reads email_unsubscribe_tokens (opt-in/unsubscribe plumbing);
-- email_alert_log is created now so PR-2 is pure application code. The service
-- layer degrades safely if these tables are missing (opt-in still records the
-- settings flag; token lookups simply miss).

-- email_alert_log records every job-alert emailed so Rico never emails the same
-- job to the same user twice and can enforce a per-user daily/weekly send cap.
-- Mirrors telegram_alert_log (migration 023). user_id is the TEXT
-- external_user_id (email for web users), consistent with telegram_alert_log.
CREATE TABLE IF NOT EXISTS email_alert_log (
    id          SERIAL      PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    job_key     TEXT        NOT NULL,
    alert_type  TEXT        NOT NULL DEFAULT 'job_match',
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, job_key, alert_type)
);

CREATE INDEX IF NOT EXISTS idx_eal_user_sent
    ON email_alert_log (user_id, sent_at DESC);

-- email_unsubscribe_tokens backs the one-click, login-free unsubscribe link.
-- One active token per user (PK on user_id); token is unique and rotatable.
CREATE TABLE IF NOT EXISTS email_unsubscribe_tokens (
    user_id     TEXT        PRIMARY KEY,
    token       TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eut_token
    ON email_unsubscribe_tokens (token);

COMMENT ON TABLE email_alert_log IS 'Sent job-alert emails: dedup + per-user send-rate cap';
COMMENT ON TABLE email_unsubscribe_tokens IS 'Login-free unsubscribe tokens for job-alert emails';

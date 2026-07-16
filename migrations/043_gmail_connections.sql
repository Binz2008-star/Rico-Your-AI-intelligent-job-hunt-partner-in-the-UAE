-- Migration 043: Gmail read-only connector foundation (M0)
-- Adds the four tables from docs/integrations/gmail-readonly-connector.md:
-- per-user Gmail connections (encrypted refresh token), immutable sync-run
-- records, user-scoped review items, and a secret-free audit trail.
-- Additive, non-destructive, idempotent.
--
-- APPLY THIS TO NEON BEFORE DEPLOYING THE GMAIL CONNECTOR CODE.
-- This migration is NOT auto-applied at startup (unlike 028/031/032/038).
-- The application code degrades safely if these tables are missing: the
-- feature is gated behind RICO_ENABLE_GMAIL_SYNC (default false), repo reads
-- return empty results, and repo writes log and no-op.
--
-- Privacy rules (see design doc §3):
--   * NO email bodies are stored anywhere — subject/sender/snippet-derived
--     fields only.
--   * Refresh tokens are stored Fernet-encrypted (GMAIL_TOKEN_ENCRYPTION_KEY).
--   * Audit events never contain tokens, auth codes, or message bodies.
--   * user_id is the TEXT external user id (email — the JWT sub), consistent
--     with email_alert_log / telegram_alert_log (migrations 023 and 033),
--     NOT the rico_users UUID.

-- One current Gmail account connection per Rico user.
CREATE TABLE IF NOT EXISTS gmail_connections (
    id                           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                      TEXT        NOT NULL,
    provider                     TEXT        NOT NULL DEFAULT 'gmail',
    provider_account_email       TEXT,
    scopes                       TEXT[]      NOT NULL DEFAULT '{}',
    encrypted_refresh_token      TEXT        NOT NULL,
    token_encryption_key_version TEXT,
    status                       TEXT        NOT NULL DEFAULT 'active',
    last_connected_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_refresh_at              TIMESTAMPTZ,
    last_sync_at                 TIMESTAMPTZ,
    last_error                   TEXT,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique ACTIVE connection per user+provider (revoked/tombstoned rows may
-- accumulate as history without blocking a reconnect).
CREATE UNIQUE INDEX IF NOT EXISTS uq_gmail_connections_active
    ON gmail_connections (user_id, provider)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_gmail_connections_status
    ON gmail_connections (status);

CREATE INDEX IF NOT EXISTS idx_gmail_connections_last_sync
    ON gmail_connections (last_sync_at);

-- Immutable record of manual and scheduled sync attempts.
CREATE TABLE IF NOT EXISTS gmail_sync_runs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             TEXT        NOT NULL,
    connection_id       UUID        NOT NULL,
    mode                TEXT        NOT NULL,
    status              TEXT        NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    lookback_days       INTEGER,
    messages_fetched    INTEGER     DEFAULT 0,
    messages_classified INTEGER     DEFAULT 0,
    messages_skipped    INTEGER     DEFAULT 0,
    updates_applied     INTEGER     DEFAULT 0,
    queued_for_review   INTEGER     DEFAULT 0,
    error_code          TEXT,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gmail_sync_runs_user_started
    ON gmail_sync_runs (user_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_gmail_sync_runs_connection_started
    ON gmail_sync_runs (connection_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_gmail_sync_runs_status
    ON gmail_sync_runs (status);

-- User-scoped replacement for data/gmail_review_queue.json.
-- Metadata only: subject snippet, sender, classification — never bodies.
CREATE TABLE IF NOT EXISTS gmail_review_items (
    id                        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                   TEXT        NOT NULL,
    sync_run_id               UUID,
    gmail_message_id          TEXT        NOT NULL,
    gmail_thread_id           TEXT,
    subject_snippet           TEXT,
    sender                    TEXT,
    received_at               TIMESTAMPTZ,
    classified_status         TEXT,
    classification_confidence NUMERIC,
    company_hint              TEXT,
    matched_job_id            TEXT,
    matched_company           TEXT,
    matched_title             TEXT,
    match_confidence          NUMERIC,
    match_reason              TEXT,
    proposed_status           TEXT,
    review_status             TEXT        NOT NULL DEFAULT 'pending',
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_gmail_review_items_user_message UNIQUE (user_id, gmail_message_id)
);

CREATE INDEX IF NOT EXISTS idx_gmail_review_items_user_status_created
    ON gmail_review_items (user_id, review_status, created_at DESC);

-- Connector-specific audit trail without secrets.
CREATE TABLE IF NOT EXISTS gmail_audit_events (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       TEXT        NOT NULL,
    connection_id UUID,
    sync_run_id   UUID,
    event_type    TEXT        NOT NULL,
    status        TEXT        NOT NULL,
    metadata      JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gmail_audit_events_user_created
    ON gmail_audit_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_gmail_audit_events_type_created
    ON gmail_audit_events (event_type, created_at DESC);

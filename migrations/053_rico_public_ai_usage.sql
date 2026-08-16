-- migrations/053_rico_public_ai_usage.sql
--
-- Phase: final production-hardening review.
--
-- Closes a confirmed billing gap: the registered-email "anti-dodge" on the
-- public chat endpoints checked the account's AI-message allowance but never
-- RECORDED the public turn against the account, so the cap never actually
-- enforced (a registered user could send unlimited AI messages via
-- /chat/public and /chat/stream/public).
--
-- This table is a content-free usage ledger keyed by the account identity
-- (the JWT sub / email) and the usage window, so public turns count toward the
-- same quota as authenticated turns WITHOUT writing message content into the
-- account's chat history. Rows are additive (ai_count +1 per turn); the
-- window rolls over via the window_start key.
--
-- Apply: python -m src.db_migrations apply

CREATE TABLE IF NOT EXISTS rico_public_ai_usage (
    identity_key TEXT        NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    ai_count     INTEGER     NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (identity_key, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rico_public_ai_usage_key
    ON rico_public_ai_usage (identity_key, window_start);

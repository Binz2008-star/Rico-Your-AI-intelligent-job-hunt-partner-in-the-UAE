-- migrations/017_email_verification_tokens.sql
-- Add email_verified column to users and create verification token table.
-- Existing users are marked verified so they are not locked out on deploy.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE;

-- All existing rows pick up TRUE from the DEFAULT above (safe for live deploy).
-- New accounts inserted by the application will use FALSE explicitly.

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id          SERIAL      PRIMARY KEY,
    user_email  TEXT        NOT NULL,
    token_hash  TEXT        NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evt_token_hash ON email_verification_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_evt_user_email  ON email_verification_tokens (user_email);

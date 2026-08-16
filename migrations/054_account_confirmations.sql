-- migrations/054_account_confirmations.sql
--
-- Launch-blocker closure (Jotform identity ownership + Telegram /start binding).
--
-- A public Jotform submission can currently auto-merge into an EXISTING
-- registered account based on unverified form input (email or Telegram handle),
-- overwriting profile/settings/CV. The same class of problem exists for
-- Telegram /start username binding (a freed handle can be re-bound to a
-- victim's account).
--
-- This table implements an out-of-band ownership proof shared by both channels:
-- a pending confirmation stores the account key, purpose, the hash of a random
-- single-use token, and the server-built payload to apply. The raw token goes
-- to the ACCOUNT OWNER (email), and only a valid, unexpired, unused, purpose-
-- and-account-matched token may apply the payload. Nothing is written to the
-- account before proof. All failures fail closed.
--
-- Apply: python -m src.db_migrations apply

CREATE TABLE IF NOT EXISTS account_confirmations (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    account_key TEXT        NOT NULL,            -- the registered account identity (email)
    purpose     TEXT        NOT NULL,            -- 'jotform_merge' | 'telegram_bind'
    token_hash  TEXT        NOT NULL,            -- sha256 of the raw single-use token
    payload     JSONB,                           -- server-built data to apply on proof
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_account_confirmations_token
    ON account_confirmations (token_hash);

CREATE INDEX IF NOT EXISTS idx_account_confirmations_account
    ON account_confirmations (account_key, purpose);

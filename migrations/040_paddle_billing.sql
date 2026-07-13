-- migrations/040_paddle_billing.sql
-- Paddle Billing: customers, subscriptions, and processed webhook events.
-- Run once: psql $DATABASE_URL -f migrations/040_paddle_billing.sql

-- ── paddle_customers: map Rico user_id → Paddle customer_id ───────────────

CREATE TABLE IF NOT EXISTS paddle_customers (
    id                  BIGSERIAL   PRIMARY KEY,
    user_id             TEXT        NOT NULL UNIQUE,
    paddle_customer_id  TEXT        NOT NULL UNIQUE,
    email               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paddle_customers_user_id
    ON paddle_customers (user_id);

CREATE INDEX IF NOT EXISTS idx_paddle_customers_paddle_id
    ON paddle_customers (paddle_customer_id);

-- ── paddle_subscriptions: one row per user, upserted on plan change ────────

CREATE TABLE IF NOT EXISTS paddle_subscriptions (
    id                      BIGSERIAL   PRIMARY KEY,
    user_id                 TEXT        NOT NULL UNIQUE,
    paddle_subscription_id  TEXT        NOT NULL UNIQUE,
    paddle_customer_id      TEXT        NOT NULL,
    plan                    TEXT        NOT NULL DEFAULT 'free',
    status                  TEXT        NOT NULL DEFAULT 'inactive',
    billing_cycle           TEXT        DEFAULT 'monthly',
    price_id                TEXT,
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    cancel_at               TIMESTAMPTZ,
    canceled_at             TIMESTAMPTZ,
    last_event_occurred_at  TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paddle_subscriptions_user_id
    ON paddle_subscriptions (user_id);

CREATE INDEX IF NOT EXISTS idx_paddle_subscriptions_paddle_sub_id
    ON paddle_subscriptions (paddle_subscription_id);

CREATE INDEX IF NOT EXISTS idx_paddle_subscriptions_paddle_customer_id
    ON paddle_subscriptions (paddle_customer_id);

-- ── paddle_webhook_events: idempotency + audit trail ──────────────────────

CREATE TABLE IF NOT EXISTS paddle_webhook_events (
    id              BIGSERIAL   PRIMARY KEY,
    paddle_event_id TEXT        NOT NULL UNIQUE,
    event_type      TEXT        NOT NULL,
    user_id         TEXT,
    status          TEXT        NOT NULL DEFAULT 'pending',
    payload         JSONB,
    error_detail    TEXT,
    processed_at    TIMESTAMPTZ,
    -- claimed_at: when this event was last claimed for processing. Lets the
    -- webhook claim atomically reprocess 'failed' or crashed-mid-flight (stale
    -- 'pending') events on a Paddle retry, without double-running an event that
    -- another worker just claimed. See record_paddle_webhook_event().
    claimed_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Defensive: if an earlier revision of this migration already created the table
-- without claimed_at, add it idempotently (040 uses IF NOT EXISTS throughout,
-- so re-running it is a no-op).
ALTER TABLE paddle_webhook_events
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_paddle_webhook_events_event_id
    ON paddle_webhook_events (paddle_event_id);

CREATE INDEX IF NOT EXISTS idx_paddle_webhook_events_user_id
    ON paddle_webhook_events (user_id)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_paddle_webhook_events_failed
    ON paddle_webhook_events (status)
    WHERE status = 'failed';

-- ── auto-update updated_at triggers ───────────────────────────────────────

CREATE OR REPLACE FUNCTION update_paddle_customers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_paddle_customers_updated_at ON paddle_customers;
CREATE TRIGGER trg_paddle_customers_updated_at
    BEFORE UPDATE ON paddle_customers
    FOR EACH ROW
    EXECUTE FUNCTION update_paddle_customers_updated_at();

CREATE OR REPLACE FUNCTION update_paddle_subscriptions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_paddle_subscriptions_updated_at ON paddle_subscriptions;
CREATE TRIGGER trg_paddle_subscriptions_updated_at
    BEFORE UPDATE ON paddle_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_paddle_subscriptions_updated_at();

-- ── paddle_checkout_sessions: server-owned checkout attribution ────────────
-- Created by the authenticated /billing/paddle/checkout-session endpoint.
-- The session_token is passed as custom_data.checkout_session_id in the
-- Paddle checkout; the webhook resolves the Rico user via this record.
-- custom_data.user_id is no longer used as authoritative identity.

CREATE TABLE IF NOT EXISTS paddle_checkout_sessions (
    id              BIGSERIAL   PRIMARY KEY,
    session_token   TEXT        NOT NULL UNIQUE,
    user_id         TEXT        NOT NULL,
    plan            TEXT        NOT NULL,
    billing_cycle   TEXT        NOT NULL DEFAULT 'monthly',
    used            BOOLEAN     NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '2 hours'),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paddle_checkout_sessions_token
    ON paddle_checkout_sessions (session_token);

CREATE INDEX IF NOT EXISTS idx_paddle_checkout_sessions_user_id
    ON paddle_checkout_sessions (user_id);

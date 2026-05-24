-- migrations/013_user_subscriptions.sql
-- Subscription persistence: user_subscriptions + subscription_events tables
-- Run once: psql $DATABASE_URL -f migrations/013_user_subscriptions.sql

-- ── user_subscriptions: one row per user, upserted on plan change ──────────

CREATE TABLE IF NOT EXISTS user_subscriptions (
    id                      BIGSERIAL   PRIMARY KEY,
    user_id                 TEXT        NOT NULL UNIQUE,
    plan                    TEXT        NOT NULL DEFAULT 'free',
    status                  TEXT        NOT NULL DEFAULT 'inactive',
    stripe_customer_id      TEXT,
    stripe_subscription_id  TEXT,
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id
    ON user_subscriptions (user_id);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_stripe_customer
    ON user_subscriptions (stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_stripe_sub
    ON user_subscriptions (stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

-- ── subscription_events: webhook idempotency + audit trail ─────────────────

CREATE TABLE IF NOT EXISTS subscription_events (
    id              BIGSERIAL   PRIMARY KEY,
    stripe_event_id TEXT        NOT NULL UNIQUE,
    event_type      TEXT        NOT NULL,
    user_id         TEXT,
    payload         JSONB,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscription_events_stripe_event_id
    ON subscription_events (stripe_event_id);

CREATE INDEX IF NOT EXISTS idx_subscription_events_user_id
    ON subscription_events (user_id)
    WHERE user_id IS NOT NULL;

-- ── auto-update updated_at on user_subscriptions ───────────────────────────

CREATE OR REPLACE FUNCTION update_user_subscriptions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_subscriptions_updated_at ON user_subscriptions;

CREATE TRIGGER trg_user_subscriptions_updated_at
    BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_user_subscriptions_updated_at();

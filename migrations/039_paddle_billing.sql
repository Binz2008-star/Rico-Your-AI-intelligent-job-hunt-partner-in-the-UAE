-- migrations/039_paddle_billing.sql
-- Paddle Billing replaces Stripe as the payment provider.
-- Additive only: adds paddle_* columns alongside the existing stripe_*
-- columns (left in place, unused, for historical/rollback safety).
-- Run once: psql $DATABASE_URL -f migrations/039_paddle_billing.sql

ALTER TABLE user_subscriptions
    ADD COLUMN IF NOT EXISTS paddle_customer_id     TEXT,
    ADD COLUMN IF NOT EXISTS paddle_subscription_id TEXT;

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_paddle_customer
    ON user_subscriptions (paddle_customer_id)
    WHERE paddle_customer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_paddle_sub
    ON user_subscriptions (paddle_subscription_id)
    WHERE paddle_subscription_id IS NOT NULL;

-- migrations/041_paddle_grace_period.sql
-- Tracks when a Paddle subscription first entered past_due, so entitlement
-- resolution can honor the promised 7-day payment-retry grace period
-- (see apps/web/app/refund-policy/RefundPolicyContent.tsx) before downgrading
-- to Free.
-- Run once: psql $DATABASE_URL -f migrations/041_paddle_grace_period.sql

ALTER TABLE paddle_subscriptions
    ADD COLUMN IF NOT EXISTS past_due_since TIMESTAMPTZ;

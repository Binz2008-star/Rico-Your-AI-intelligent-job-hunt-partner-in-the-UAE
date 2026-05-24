-- migrations/016_user_subscriptions_entitlements.sql
-- Add cancellation tracking and entitlement override columns to user_subscriptions.
--
-- These are needed for:
--   - cancel_at / canceled_at: Stripe cancellation timeline tracking
--   - entitlement columns: reserved for per-user overrides (not enforced by default;
--     resolve_effective_user_plan uses canonical plan definitions from subscription_plans.py)
--
-- Prerequisite: migration 015 (subscription_events status tracking) must be applied first.
-- Run once: psql $DATABASE_URL -f migrations/016_user_subscriptions_entitlements.sql

ALTER TABLE user_subscriptions
    ADD COLUMN IF NOT EXISTS cancel_at                          TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS canceled_at                        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS monthly_ai_message_limit           INTEGER,
    ADD COLUMN IF NOT EXISTS saved_jobs_limit                   INTEGER,
    ADD COLUMN IF NOT EXISTS profile_optimization_limit         INTEGER,
    ADD COLUMN IF NOT EXISTS premium_recommendations_enabled    BOOLEAN,
    ADD COLUMN IF NOT EXISTS application_automation_enabled     BOOLEAN;

-- Idempotent constraint removal: ALTER COLUMN DROP DEFAULT/DROP NOT NULL
-- errors on PostgreSQL < 14 when the constraint doesn't exist (e.g. columns
-- were just added as nullable with no default, or migration runs twice).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name  = 'user_subscriptions'
           AND column_name = 'premium_recommendations_enabled'
           AND column_default IS NOT NULL
    ) THEN
        ALTER TABLE user_subscriptions
            ALTER COLUMN premium_recommendations_enabled DROP DEFAULT;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name  = 'user_subscriptions'
           AND column_name = 'premium_recommendations_enabled'
           AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE user_subscriptions
            ALTER COLUMN premium_recommendations_enabled DROP NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name  = 'user_subscriptions'
           AND column_name = 'application_automation_enabled'
           AND column_default IS NOT NULL
    ) THEN
        ALTER TABLE user_subscriptions
            ALTER COLUMN application_automation_enabled DROP DEFAULT;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name  = 'user_subscriptions'
           AND column_name = 'application_automation_enabled'
           AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE user_subscriptions
            ALTER COLUMN application_automation_enabled DROP NOT NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_plan   ON user_subscriptions (plan);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions (status);

COMMENT ON COLUMN user_subscriptions.cancel_at                       IS 'Scheduled cancellation date from Stripe';
COMMENT ON COLUMN user_subscriptions.canceled_at                     IS 'Actual cancellation timestamp from Stripe';
COMMENT ON COLUMN user_subscriptions.monthly_ai_message_limit        IS 'Per-user override (NULL = use plan default)';
COMMENT ON COLUMN user_subscriptions.saved_jobs_limit                IS 'Per-user override (NULL = use plan default)';
COMMENT ON COLUMN user_subscriptions.profile_optimization_limit      IS 'Per-user override (NULL = use plan default)';
COMMENT ON COLUMN user_subscriptions.premium_recommendations_enabled IS 'Per-user override flag';
COMMENT ON COLUMN user_subscriptions.application_automation_enabled  IS 'Per-user override flag';

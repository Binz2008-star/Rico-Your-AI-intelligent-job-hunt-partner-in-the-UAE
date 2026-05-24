-- migrations/014_stripe_customer_unique.sql
-- Enforce Stripe customer ID uniqueness in user_subscriptions.
-- Replaces the non-unique partial index from migration 013 with a UNIQUE
-- constraint. PostgreSQL allows multiple NULLs under a UNIQUE constraint,
-- so users without a Stripe customer record are unaffected.
-- Run once: psql $DATABASE_URL -f migrations/014_stripe_customer_unique.sql

-- Drop the non-unique partial index added by migration 013
DROP INDEX IF EXISTS idx_user_subscriptions_stripe_customer;

-- The UNIQUE constraint creates its own implicit index and guarantees that
-- no two users can share the same Stripe customer ID.
ALTER TABLE user_subscriptions
    ADD CONSTRAINT uq_user_subscriptions_stripe_customer_id
    UNIQUE (stripe_customer_id);

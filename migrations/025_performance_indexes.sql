-- Migration 025: Performance indexes for hot query paths
--
-- Adds missing indexes identified during audit:
--   1. user_subscriptions(user_id) — missing index causes full table scan on every
--      subscription lookup (check_ai_message_allowed, get_subscription).
--   2. user_subscriptions(user_id, status) — composite for the common query pattern
--      "latest active subscription for user".
--   3. user_job_context(user_id, status) — application funnel queries filter by both.
--   4. action_audit_log(user_id, created_at) — audit trail lookups by user are frequent.
--
-- All indexes are CONCURRENTLY so they do not lock writes on production.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_user_id
    ON user_subscriptions (user_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_user_status
    ON user_subscriptions (user_id, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_created_at
    ON user_subscriptions (user_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_job_context_user_status
    ON user_job_context (user_id, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_action_audit_log_user_created
    ON action_audit_log (user_id, created_at DESC);

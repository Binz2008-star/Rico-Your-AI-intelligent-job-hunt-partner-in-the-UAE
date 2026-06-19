-- Migration 027: Add missing performance indexes on high-traffic FK and lookup columns.
--
-- These columns are queried on every chat session, job load, and application lookup
-- but had no dedicated indexes. The DDL in rico_db.py only created indexes on
-- rico_users itself; the child tables that JOIN against it were missing coverage.
--
-- All statements use IF NOT EXISTS so this migration is safe to re-run.

-- rico_profiles: every profile fetch JOINs on user_id
CREATE INDEX IF NOT EXISTS idx_rico_profiles_user_id
    ON rico_profiles(user_id);

-- rico_agent_settings: fetched on every chat session by user_id
CREATE INDEX IF NOT EXISTS idx_rico_agent_settings_user_id
    ON rico_agent_settings(user_id);

-- rico_chat_history: existing composite index covers (user_id, created_at DESC)
-- but an additional plain user_id index speeds up COUNT / EXISTS checks
CREATE INDEX IF NOT EXISTS idx_rico_chat_history_user_id
    ON rico_chat_history(user_id);

-- rico_learning_signals: aggregated by user_id on every recommendation refresh
CREATE INDEX IF NOT EXISTS idx_rico_learning_signals_user_id
    ON rico_learning_signals(user_id);

-- rico_job_recommendations: primary query is "all active recommendations for user"
-- Partial index skips discarded rows (typically 80%+ of the table after time).
CREATE INDEX IF NOT EXISTS idx_rico_job_recommendations_user_active
    ON rico_job_recommendations(user_id, updated_at DESC)
    WHERE status != 'discarded';

-- rico_job_recommendations: point-lookup by (user_id, job_key) for upsert idempotency
CREATE INDEX IF NOT EXISTS idx_rico_job_recommendations_user_job_key
    ON rico_job_recommendations(user_id, job_key);

-- rico_saved_searches: listed on every dashboard load per user
CREATE INDEX IF NOT EXISTS idx_rico_saved_searches_user_id
    ON rico_saved_searches(user_id);

-- rico_alerts: polled by the notification sender per user
CREATE INDEX IF NOT EXISTS idx_rico_alerts_user_status
    ON rico_alerts(user_id, status)
    WHERE status = 'pending';

-- telegram_alert_log: dedup guard runs (user_id, job_key, alert_type) lookups
-- The UNIQUE constraint already creates an implicit index; this confirms coverage.
CREATE INDEX IF NOT EXISTS idx_telegram_alert_log_user_sent
    ON telegram_alert_log(user_id, sent_at DESC);

-- user_documents: listed per user on file manager load
CREATE INDEX IF NOT EXISTS idx_user_documents_user_id
    ON user_documents(user_id);

-- application_drafts: listed per user for apply-queue view
CREATE INDEX IF NOT EXISTS idx_application_drafts_user_id
    ON application_drafts(user_id, status);

-- user_job_context: primary query filters by user_id and searched_at (recency window)
-- The table has no job_id column; the FK to action_audit_log is on a separate table.
CREATE INDEX IF NOT EXISTS idx_user_job_context_user_searched_at
    ON user_job_context(user_id, searched_at DESC);

-- migrations/052_settings_notifications_reconciliation.sql
--
-- Phase-3 forward reconciliation: the historical numbered migration 005
-- COMMENTs on settings.notifications and its CREATE TABLE defined that column,
-- but the runtime application DDL (src/db.py init_db) created `settings`
-- without it (and `CREATE TABLE IF NOT EXISTS` never retroactively adds it).
--
-- The column is dead in the application (settings_repo reads the
-- keyword/threshold columns) but must EXIST so that a replay of the numbered
-- migrations on a fresh database does not fail on migration 005's COMMENT.
-- Additive and idempotent — safe to run on any existing deployment.
--
-- Apply: python -m src.db_migrations apply

ALTER TABLE settings
    ADD COLUMN IF NOT EXISTS notifications JSONB NOT NULL DEFAULT '{}';

COMMENT ON COLUMN settings.notifications IS
    'Compatibility column defined by migration 005; reserved for per-channel notification settings.';

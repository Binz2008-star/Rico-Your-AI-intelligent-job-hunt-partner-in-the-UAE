-- migrations/019_user_job_context_interaction.sql
-- Extend user_job_context to persist per-job interaction state so Rico can
-- recall what a user did with a specific job across sessions / Render restarts:
-- what action they took, when, any note, and a coarse status.
--
-- Additive, non-destructive online migration: all new columns are nullable or
-- have safe defaults. upsert_matches() does NOT touch these columns, so a
-- repeated search never clobbers a meaningful last_action/status.

ALTER TABLE user_job_context
    ADD COLUMN IF NOT EXISTS last_action        TEXT,           -- apply|save|skip|block|draft|why|discussed
    ADD COLUMN IF NOT EXISTS last_action_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_discussed_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS user_note          TEXT,
    ADD COLUMN IF NOT EXISTS interaction_count  INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS status             TEXT NOT NULL DEFAULT 'seen';
    -- status domain: seen | discussed | saved | applied | skipped | blocked

-- Powers the "recently interacted" recall (greeting hook / recent_context intent).
CREATE INDEX IF NOT EXISTS idx_ujc_user_last_action
    ON user_job_context (user_id, last_action_at DESC NULLS LAST)
    WHERE last_action IS NOT NULL;

-- Powers cross-session "you looked at X last Tuesday" recall.
CREATE INDEX IF NOT EXISTS idx_ujc_user_last_discussed
    ON user_job_context (user_id, last_discussed_at DESC NULLS LAST)
    WHERE last_discussed_at IS NOT NULL;

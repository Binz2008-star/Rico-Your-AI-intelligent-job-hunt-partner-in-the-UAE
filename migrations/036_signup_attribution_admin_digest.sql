-- migrations/036_signup_attribution_admin_digest.sql
-- Issue #922: activation analytics.
--   1) Signup attribution: where each new account came from (UTM/referrer/landing path).
--   2) Admin digest log: idempotency guard so the weekly activation digest never double-sends.
-- Additive only — safe to run on the live database.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS signup_source TEXT,
    ADD COLUMN IF NOT EXISTS signup_attribution JSONB;

COMMENT ON COLUMN users.signup_source IS
    'Human-readable signup source summary (e.g. "google / cpc / brand-uae", "referrer: linkedin.com"). NULL for legacy rows — displayed as "direct / unknown".';
COMMENT ON COLUMN users.signup_attribution IS
    'Raw sanitized attribution fields captured at signup: utm_source/medium/campaign/content/term, referrer, landing_path.';

CREATE TABLE IF NOT EXISTS admin_digest_log (
    id           BIGSERIAL   PRIMARY KEY,
    digest_type  TEXT        NOT NULL DEFAULT 'weekly_activation',
    period_start DATE        NOT NULL,
    period_end   DATE        NOT NULL,
    recipient    TEXT        NOT NULL,
    sent_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (digest_type, period_start)
);

COMMENT ON TABLE admin_digest_log IS
    'One row per admin digest email. UNIQUE(digest_type, period_start) is claimed before sending, making the weekly cron idempotent.';

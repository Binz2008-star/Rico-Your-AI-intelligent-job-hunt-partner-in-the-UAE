-- Migration 047: analytics_events — first-party behavioral event store.
--
-- Product Truth Sprint track 1 ("eyes"): activation/retention measurement
-- lives in Rico's own Postgres, never a third-party analytics service.
--
-- Privacy contract (owner-approved pattern, mirrors 046):
--   * NO raw message text, email, CV text, search query text, or any other
--     PII — ever. Enforced in the application layer by a strict per-event
--     property allowlist that only admits booleans, bounded numbers, and
--     short enum-like tokens (^[a-z0-9_.:-]{1,64}$); free-form strings are
--     structurally impossible.
--   * The actor is stored ONLY as a keyed, non-reversible HMAC-SHA256
--     (`actor_hash`) under the dedicated RICO_ANALYTICS_HMAC_KEY — its own
--     secret (never JWT_SECRET, never RICO_ARCHIVE_HMAC_KEY, never stored
--     in the database). Absent key => event writes are skipped entirely
--     (fail-closed; product flows unaffected); no unkeyed-hash fallback.
--   * `schema_version` stamps every row so the property vocabulary can
--     evolve without corrupting history.
--
-- Idempotency: `dedupe_key` is unique — duplicate deliveries (retries,
-- double-clicks, replayed requests) collapse via ON CONFLICT DO NOTHING.
--
-- Retention: rows expire after 180 days (RETENTION_DAYS in
-- src/repositories/analytics_events_repo.py, purge_expired()); the purge is
-- executed by a scheduled job wired in a LATER change — this migration only
-- provides the supporting index (occurred_at).
--
-- Rollback: revert the application commit; the table can then be dropped —
-- nothing else references it.

CREATE TABLE IF NOT EXISTS analytics_events (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_version  SMALLINT NOT NULL DEFAULT 1,
    event_name      VARCHAR(64) NOT NULL,
    actor_hash      CHAR(64) NOT NULL DEFAULT '',
    audience        VARCHAR(16) NOT NULL DEFAULT 'user',
    surface         VARCHAR(32) NOT NULL DEFAULT '',
    language        VARCHAR(8) NOT NULL DEFAULT '',
    dedupe_key      CHAR(64) NOT NULL,
    properties      JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Idempotency: duplicate deliveries collapse on the dedupe key.
CREATE UNIQUE INDEX IF NOT EXISTS uq_analytics_events_dedupe
    ON analytics_events (dedupe_key);

-- Funnel/retention reads: "events of kind X over window Y".
CREATE INDEX IF NOT EXISTS idx_analytics_events_name_occurred
    ON analytics_events (event_name, occurred_at DESC);

-- Retention sweeps and time-window scans.
CREATE INDEX IF NOT EXISTS idx_analytics_events_occurred
    ON analytics_events (occurred_at);

-- 042_career_memory_engine.sql
-- ADR-001 (ACCEPTED 2026-07-14) — Career Memory Engine, milestone M1.
-- Additive only; every statement is IF NOT EXISTS-guarded and safe to re-run.
-- M1 scope: schema + shadow writes behind RICO_MEMORY_ENGINE_ENABLED (default
-- OFF). No reader exists yet; no legacy store is touched.
--
-- Identity keying (ADR-001 §3): account_key is namespaced TEXT —
--   'acct:<rico_users.id UUID>'  for authenticated accounts (immutable id,
--                                 never the mutable email), and
--   'session:<public:web-...>'   for public sessions, which stay separately
--                                 keyed until an explicit audited merge (M5).

CREATE TABLE IF NOT EXISTS career_memory_events (
    id BIGSERIAL PRIMARY KEY,
    account_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    -- ADR-001 §4 retention classes: core_fact | episode | bulk_text | derived | referenced
    retention_class TEXT NOT NULL DEFAULT 'episode',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- ADR-001 §6 mandatory provenance
    actor TEXT NOT NULL,
    source TEXT NOT NULL, -- user_stated | verified_event | cv_extracted | inferred
    source_record_id TEXT,
    source_uri TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    idempotency_key TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT career_memory_events_account_idem_key UNIQUE (account_key, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_cme_account_occurred
    ON career_memory_events (account_key, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_cme_account_type
    ON career_memory_events (account_key, event_type);

CREATE TABLE IF NOT EXISTS career_memory_facts (
    id BIGSERIAL PRIMARY KEY,
    account_key TEXT NOT NULL,
    fact_key TEXT NOT NULL,
    -- ADR-001 §7 per-fact conflict classes: replaceable | set_valued | time_bound | verified_only
    fact_class TEXT NOT NULL,
    value JSONB NOT NULL,
    source TEXT NOT NULL,
    source_record_id TEXT,
    source_uri TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    actor TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    effective_to TIMESTAMPTZ, -- NULL = current value; history rows carry a close date
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);

-- Exactly one open (current) row per fact for single-valued classes;
-- set_valued and time_bound facts may hold several open rows by design.
CREATE UNIQUE INDEX IF NOT EXISTS idx_cmf_current_single
    ON career_memory_facts (account_key, fact_key)
    WHERE effective_to IS NULL AND fact_class IN ('replaceable', 'verified_only');
CREATE INDEX IF NOT EXISTS idx_cmf_account_key_history
    ON career_memory_facts (account_key, fact_key, effective_from DESC);

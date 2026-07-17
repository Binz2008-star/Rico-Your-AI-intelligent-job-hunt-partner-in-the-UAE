-- migrations/042_career_memory_engine.sql
-- ADR-001 M1 — Career Memory Engine schema: episodic event log + curated fact
-- layer with history semantics. See AI_WORKSPACE/ADR/ADR-001-rico-career-memory-engine.md
-- and docs/career-memory-engine.md (operations, rollback, backfill).
--
-- ADDITIVE ONLY. No existing table, column, or index is touched. Safe to
-- re-run (IF NOT EXISTS everywhere).
--
-- Apply: psql $DATABASE_URL -f migrations/042_career_memory_engine.sql
--
-- account_id is the canonical immutable account ID (rico_users.id UUID).
-- It is a logical reference, not a foreign key, matching the repository's
-- existing convention (user_job_context, audit tables) and keeping this
-- migration applicable before the runtime has created rico_users on a fresh
-- database. Email is provenance data, never the storage key (ADR §3).

-- ─────────────────────────────────────────────────────────────────────────────
-- Episodes: append-only, immutable content (ADR §2, §4).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS career_memory_events (
    id               BIGSERIAL    PRIMARY KEY,
    account_id       UUID         NOT NULL,
    event_type       VARCHAR(64)  NOT NULL,   -- e.g. 'job_action.apply'
    version          INTEGER      NOT NULL DEFAULT 1,
    retention_class  VARCHAR(32)  NOT NULL DEFAULT 'episode'
        CHECK (retention_class IN ('core_fact', 'episode', 'bulk_text', 'derived', 'referenced')),
    idempotency_key  VARCHAR(160) NOT NULL,
    occurred_at      TIMESTAMPTZ  NOT NULL,   -- when it happened
    captured_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),  -- when memory learned it
    actor            VARCHAR(32)  NOT NULL
        CHECK (actor IN ('user', 'rico_agent', 'pipeline', 'webhook')),
    source           VARCHAR(32)  NOT NULL
        CHECK (source IN ('user_stated', 'verified_event', 'cv_extracted', 'inferred')),
    source_record_id TEXT,
    source_uri       TEXT,
    confidence       REAL         NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    payload          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    -- Mandatory provenance: at least one originating-record pointer (ADR §6).
    CONSTRAINT career_memory_events_provenance
        CHECK (source_record_id IS NOT NULL OR source_uri IS NOT NULL),
    -- Idempotency: same logical write never lands twice for the same account.
    CONSTRAINT uq_career_memory_events_idem UNIQUE (account_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_cm_events_account_time
    ON career_memory_events (account_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_cm_events_account_type
    ON career_memory_events (account_id, event_type, occurred_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Facts: current value + full change history (ADR §2, §7).
-- A fact row is current while effective_to IS NULL. Superseding never updates
-- the value in place: the old row is closed (effective_to set, superseded_by
-- pointing at the new row) and a new row is inserted.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS career_memory_facts (
    id               BIGSERIAL    PRIMARY KEY,
    account_id       UUID         NOT NULL,
    fact_key         VARCHAR(128) NOT NULL,   -- e.g. 'identity.notice_period'
    fact_class       VARCHAR(32)  NOT NULL
        CHECK (fact_class IN ('replaceable', 'set_valued', 'time_bound', 'verified_only')),
    version          INTEGER      NOT NULL DEFAULT 1,
    retention_class  VARCHAR(32)  NOT NULL DEFAULT 'core_fact'
        CHECK (retention_class IN ('core_fact', 'episode', 'bulk_text', 'derived', 'referenced')),
    value            JSONB        NOT NULL,
    source           VARCHAR(32)  NOT NULL
        CHECK (source IN ('user_stated', 'verified_event', 'cv_extracted', 'inferred')),
    source_record_id TEXT,
    source_uri       TEXT,
    confidence       REAL         NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    actor            VARCHAR(32)  NOT NULL
        CHECK (actor IN ('user', 'rico_agent', 'pipeline', 'webhook')),
    occurred_at      TIMESTAMPTZ  NOT NULL,
    captured_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    effective_from   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    effective_to     TIMESTAMPTZ,             -- NULL = current
    superseded_by    BIGINT       REFERENCES career_memory_facts (id),
    idempotency_key  VARCHAR(160) NOT NULL,
    CONSTRAINT career_memory_facts_provenance
        CHECK (source_record_id IS NOT NULL OR source_uri IS NOT NULL),
    CONSTRAINT uq_career_memory_facts_idem UNIQUE (account_id, idempotency_key)
);

-- Exactly one CURRENT row per (account, fact_key) for replaceable and
-- verified_only facts — real Postgres enforcement of the history invariant.
CREATE UNIQUE INDEX IF NOT EXISTS uq_cm_facts_current_single
    ON career_memory_facts (account_id, fact_key)
    WHERE effective_to IS NULL AND fact_class IN ('replaceable', 'verified_only');

-- set_valued facts: one current row per (account, fact_key, member value).
CREATE UNIQUE INDEX IF NOT EXISTS uq_cm_facts_current_set_member
    ON career_memory_facts (account_id, fact_key, md5(value::text))
    WHERE effective_to IS NULL AND fact_class = 'set_valued';

CREATE INDEX IF NOT EXISTS idx_cm_facts_account_key
    ON career_memory_facts (account_id, fact_key, effective_from DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Deletion state (#1088 gate): per-account deletion generation / tombstone.
-- purge_account bumps the generation and deletes the account's rows in ONE
-- transaction; every write records the generation it was admitted under and is
-- refused when its captured generation is older than the current one — a
-- pre-clear late write or backfill can never resurrect erased data.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS career_memory_deletion_state (
    account_id          UUID        PRIMARY KEY,
    deletion_generation BIGINT      NOT NULL DEFAULT 0,
    last_purged_at      TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE career_memory_events
    ADD COLUMN IF NOT EXISTS deletion_generation BIGINT NOT NULL DEFAULT 0;
ALTER TABLE career_memory_facts
    ADD COLUMN IF NOT EXISTS deletion_generation BIGINT NOT NULL DEFAULT 0;

-- Rollback (manual, only if explicitly approved — see docs/career-memory-engine.md):
-- The engine is shadow-write only behind RICO_MEMORY_ENGINE_ENABLED (default
-- false); the zero-risk rollback is to leave the flag off. Dropping data:
-- DROP TABLE IF EXISTS career_memory_deletion_state;
-- DROP TABLE IF EXISTS career_memory_facts;
-- DROP TABLE IF EXISTS career_memory_events;

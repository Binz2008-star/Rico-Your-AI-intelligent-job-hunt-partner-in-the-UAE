-- Migration 047: reasoning_traces — persistent Reasoning Graph nodes.
--
-- Every agent decision produces a structured ReasoningTrace
-- (src/agent/reasoning/trace.py): goal, evidence, assumptions,
-- contradictions, decision, confidence, next action, blocked state, and the
-- outcome recorded after execution. Persisting them gives Rico an auditable
-- record of WHY each decision was made and whether it proved correct —
-- instead of exposing model-internal chain-of-thought.
--
-- Contract:
--   * One row per trace, upserted on trace_id: a trace is written when the
--     decision is made and updated once when the outcome lands. Rows are
--     never deleted by application code.
--   * `trace` (JSONB) is the full serialized execution state
--     (ReasoningTrace.to_dict(), schema_version inside the payload).
--   * `user_id` matches the runtime's actor identity (email for API/chat,
--     chat id for Telegram) — the same identity class action_audit_log
--     already stores. Reads are always scoped by user_id.
--   * Privacy: evidence values are operational facts only (gate states,
--     action names, job title/company). Never raw chat/document text,
--     contact identifiers, or tokens (#1076).
--   * Writes are fire-and-forget (src/repositories/reasoning_repo.py never
--     raises); when this table is absent the repo disables itself for the
--     process, so applying this migration + restart enables recording.

CREATE TABLE IF NOT EXISTS reasoning_traces (
    id          BIGSERIAL PRIMARY KEY,
    trace_id    CHAR(32) NOT NULL UNIQUE,
    user_id     VARCHAR(255) NOT NULL DEFAULT '',
    goal        VARCHAR(512) NOT NULL DEFAULT '',
    status      VARCHAR(16) NOT NULL DEFAULT 'decided',
    decision    VARCHAR(128) NOT NULL DEFAULT '',
    confidence  REAL NOT NULL DEFAULT 0,
    source      VARCHAR(32) NOT NULL DEFAULT '',
    trace       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- "Why did Rico decide X?" — a user's recent decisions, newest first.
CREATE INDEX IF NOT EXISTS idx_reasoning_traces_user_created
    ON reasoning_traces (user_id, created_at DESC);

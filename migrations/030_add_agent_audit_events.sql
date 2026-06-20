-- migrations/030_add_agent_audit_events.sql
-- Agentic UX audit foundation: append-only event log + approval tokens.
-- Run once: psql $DATABASE_URL -f migrations/030_add_agent_audit_events.sql

-- ── Append-only agent audit event log ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_audit_events (
    id                BIGSERIAL       PRIMARY KEY,
    correlation_id    TEXT            NOT NULL,
    card_id           TEXT            NOT NULL DEFAULT '',
    idempotency_key   TEXT            NOT NULL,
    user_id           TEXT            NOT NULL,
    agent_name        TEXT            NOT NULL DEFAULT '',
    agent_version     TEXT            NOT NULL DEFAULT '',
    event_type        TEXT            NOT NULL,   -- action_created | policy_evaluated | approval_requested | ...
    action_type       TEXT            NOT NULL DEFAULT '',
    risk_class        TEXT            NOT NULL DEFAULT '',   -- low | medium | high | critical
    permission_level  TEXT            NOT NULL DEFAULT '',   -- read | write | external | irreversible
    policy_decision   TEXT            NOT NULL DEFAULT '',   -- allowed | denied | pending | expired
    reason            TEXT            NOT NULL DEFAULT '',
    before_state      JSONB,
    after_state       JSONB,
    target_resource   JSONB,
    expected_effect   TEXT            NOT NULL DEFAULT '',
    actual_effect     JSONB,
    provider          TEXT            NOT NULL DEFAULT '',
    external_systems  TEXT[]          NOT NULL DEFAULT '{}',
    reversible        BOOLEAN         NOT NULL DEFAULT TRUE,
    undo_window_sec   INTEGER         NOT NULL DEFAULT 0,
    latency_ms        INTEGER         NOT NULL DEFAULT 0,
    error_code        TEXT,
    error_message     TEXT,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Enforce: no UPDATE or DELETE on this table (append-only)
CREATE OR REPLACE FUNCTION agent_audit_events_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'agent_audit_events is append-only: UPDATE and DELETE are not allowed';
END;
$$;

DROP TRIGGER IF EXISTS trg_agent_audit_events_no_update ON agent_audit_events;
CREATE TRIGGER trg_agent_audit_events_no_update
    BEFORE UPDATE ON agent_audit_events
    FOR EACH ROW EXECUTE FUNCTION agent_audit_events_immutable();

DROP TRIGGER IF EXISTS trg_agent_audit_events_no_delete ON agent_audit_events;
CREATE TRIGGER trg_agent_audit_events_no_delete
    BEFORE DELETE ON agent_audit_events
    FOR EACH ROW EXECUTE FUNCTION agent_audit_events_immutable();

-- Indexes for operational memory queries
CREATE INDEX IF NOT EXISTS idx_aae_user_id         ON agent_audit_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aae_correlation_id  ON agent_audit_events (correlation_id);
CREATE INDEX IF NOT EXISTS idx_aae_idempotency_key ON agent_audit_events (idempotency_key);
CREATE INDEX IF NOT EXISTS idx_aae_card_id         ON agent_audit_events (card_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aae_event_type      ON agent_audit_events (event_type, created_at DESC);

-- ── Approval tokens ───────────────────────────────────────────────────────────
-- Tokens are stored separately; agent_audit_events references approval_token_id only.
-- Raw token values are NEVER stored — only the HMAC-SHA256 signature.

CREATE TABLE IF NOT EXISTS agent_approval_tokens (
    id                BIGSERIAL       PRIMARY KEY,
    approval_token_id TEXT            NOT NULL UNIQUE,   -- random UUID stored in approval card
    hmac_signature    TEXT            NOT NULL,           -- HMAC-SHA256(secret, token_payload)
    card_id           TEXT            NOT NULL,
    user_id           TEXT            NOT NULL,
    idempotency_key   TEXT            NOT NULL,
    risk_class        TEXT            NOT NULL DEFAULT '',
    permission_level  TEXT            NOT NULL DEFAULT '',
    expires_at        TIMESTAMPTZ     NOT NULL,
    used_at           TIMESTAMPTZ,
    invalidated       BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aat_approval_token_id ON agent_approval_tokens (approval_token_id);
CREATE INDEX IF NOT EXISTS idx_aat_user_card         ON agent_approval_tokens (user_id, card_id);
CREATE INDEX IF NOT EXISTS idx_aat_idempotency_key   ON agent_approval_tokens (idempotency_key);

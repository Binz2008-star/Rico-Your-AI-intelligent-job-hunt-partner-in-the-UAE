-- migration: 20260621_add_agent_audit_log
-- creates the append-only audit log for every agent policy decision
-- source of truth: docs/agentic-ux-contract.md (#683)
-- NEVER backfill or UPDATE rows in this table — append only

BEGIN;

CREATE TABLE IF NOT EXISTS agent_audit_log (
    id                  BIGSERIAL PRIMARY KEY,
    event_type          TEXT        NOT NULL,          -- e.g. 'policy_evaluated', 'execution_started'
    action_id           UUID        NOT NULL,          -- stable id for this action attempt
    card_id             TEXT        NOT NULL,          -- action card identifier
    user_id             UUID        NOT NULL,          -- human actor who initiated
    agent_id            TEXT        NOT NULL,          -- agent service identifier
    risk_class          TEXT        NOT NULL,          -- safe-read | draft-write | reversible-write | external-commit | destructive
    intent_summary      TEXT        NOT NULL,          -- human-readable, ≤ 512 chars
    policy_decision     TEXT        NOT NULL,          -- allowed | denied
    denial_reason       TEXT,                          -- populated only when policy_decision = 'denied'
    idempotency_key     TEXT        NOT NULL,          -- caller-supplied; used for duplicate protection
    approval_token_hash TEXT,                          -- SHA-256 of the approval token (never raw token)
    tool_name           TEXT,                          -- tool invoked, if execution proceeded
    target_resource     TEXT,                          -- resource identifier acted upon
    expected_effect     TEXT,                          -- what the agent declared it would do
    actual_effect       TEXT,                          -- populated post-execution
    undo_capability     BOOLEAN     NOT NULL DEFAULT FALSE,
    metadata            JSONB       NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- index: lookup by user for audit timeline UI
CREATE INDEX IF NOT EXISTS idx_agent_audit_log_user_id
    ON agent_audit_log (user_id, created_at DESC);

-- index: idempotency duplicate check
CREATE INDEX IF NOT EXISTS idx_agent_audit_log_idempotency
    ON agent_audit_log (idempotency_key);

-- index: action tracing (all events for one action_id)
CREATE INDEX IF NOT EXISTS idx_agent_audit_log_action_id
    ON agent_audit_log (action_id, created_at ASC);

-- prevent any UPDATE or DELETE via row-level security
-- (actual RLS policy must be applied per environment by the DBA)
-- this comment is the contract; enforcement is in the DB role config

COMMIT;

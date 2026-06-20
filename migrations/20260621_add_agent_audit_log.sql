-- Migration: agent_audit_log
-- Created: 2026-06-21
-- Purpose: Append-only audit trail for every policy gate decision.
-- Rules:
--   - Never DELETE or UPDATE rows in this table.
--   - idempotency_key is unique per (user_id, card_id) pair.
--   - All timestamps stored as UTC.

BEGIN;

CREATE TABLE IF NOT EXISTS agent_audit_log (
    id                BIGSERIAL       PRIMARY KEY,
    event_id          UUID            NOT NULL DEFAULT gen_random_uuid(),
    actor_user_id     TEXT            NOT NULL,
    agent_id          TEXT            NOT NULL,
    card_id           TEXT            NOT NULL,
    idempotency_key   TEXT            NOT NULL,
    intent_summary    TEXT            NOT NULL,
    risk_class        TEXT            NOT NULL,
    requested_scopes  JSONB           NOT NULL DEFAULT '[]',
    policy_decision   TEXT            NOT NULL CHECK (policy_decision IN ('ALLOWED', 'DENIED')),
    denial_reason     TEXT,                         -- NULL when ALLOWED
    approval_state    TEXT            NOT NULL CHECK (approval_state IN ('pending', 'approved', 'rejected')),
    token_issued_at   TIMESTAMPTZ     NOT NULL,
    token_expires_at  TIMESTAMPTZ     NOT NULL,
    evaluated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    effect_summary    JSONB,                        -- NULL until execution completes
    undo_capable      BOOLEAN         NOT NULL DEFAULT FALSE,
    raw_token_hash    TEXT            NOT NULL,     -- SHA-256 of token for traceability, never the token itself
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Idempotency index: one outcome per (user, card, key).
-- DENIED and ALLOWED are both recorded; duplicate ALLOWED is idempotent by key.
CREATE UNIQUE INDEX IF NOT EXISTS uidx_audit_idempotency
    ON agent_audit_log (actor_user_id, card_id, idempotency_key)
    WHERE policy_decision = 'ALLOWED';

-- Query index: look up all events for a given user.
CREATE INDEX IF NOT EXISTS idx_audit_actor_user
    ON agent_audit_log (actor_user_id, evaluated_at DESC);

-- Query index: look up all events for a given card.
CREATE INDEX IF NOT EXISTS idx_audit_card
    ON agent_audit_log (card_id, evaluated_at DESC);

COMMIT;

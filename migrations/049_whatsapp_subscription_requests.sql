-- Migration 049: whatsapp_subscription_requests — assisted-subscription
-- pending requests for the WhatsApp channel (DEC-20260719-003).
--
-- PRODUCT RULE: WhatsApp is an ASSISTED/MANUAL subscription channel, not a
-- payment processor. A row in this table NEVER grants entitlement. The only
-- entitlement write path stays paddle_repo.upsert_paddle_subscription —
-- reached either by the Paddle webhook or by the admin-only manual
-- activation endpoint (POST /api/v1/admin/subscriptions/activate). Approval
-- here is bookkeeping/audit of that admin action, not an entitlement source.
--
-- Identity: user_id is the authenticated account identifier (email), same
-- key as paddle_subscriptions.user_id. Plan/price/currency are a SERVER-side
-- snapshot taken from src/subscription_plans.py at request time — never
-- browser-supplied.
--
-- Idempotency: at most ONE pending request per user (partial unique index).
-- Repeated CTA clicks reuse the pending row instead of creating duplicates.
--
-- Rollback: DROP TABLE IF EXISTS whatsapp_subscription_requests;
-- (additive migration — no existing table or data is touched).

CREATE TABLE IF NOT EXISTS whatsapp_subscription_requests (
    id                  BIGSERIAL       PRIMARY KEY,
    reference           TEXT            NOT NULL UNIQUE,
    user_id             TEXT            NOT NULL,
    plan                TEXT            NOT NULL,
    price_usd           NUMERIC(10, 2)  NOT NULL,
    currency            TEXT            NOT NULL DEFAULT 'USD',
    -- pending | approved | rejected
    status              TEXT            NOT NULL DEFAULT 'pending',
    requested_language  TEXT            NOT NULL DEFAULT 'en',
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_sub_requests_user_id
    ON whatsapp_subscription_requests (user_id);

-- One pending request per user — the idempotency arbiter for repeated clicks.
CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_sub_requests_user_pending
    ON whatsapp_subscription_requests (user_id)
    WHERE status = 'pending';

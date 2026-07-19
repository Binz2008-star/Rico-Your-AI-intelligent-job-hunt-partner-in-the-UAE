# Handoff — WhatsApp-assisted subscription (secondary channel alongside Paddle)

Date: 2026-07-19
Decision: DEC-20260719-003 · Ledger: TASK-20260719-015
Branch: `feat/whatsapp-assisted-subscription` (one Draft PR, one objective)

Program mapping (Vision → Epic → Milestone → Phase → PR → Task):
Vision: trusted Career Operating System with sustainable revenue →
Epic: Billing & Subscriptions → Milestone: dual-channel subscription
(automated Paddle + assisted WhatsApp) → Phase: assisted-channel MVP
(pending-request + contact flow; approval via existing admin path) →
PR: this Draft PR → Task: TASK-20260719-015.

## 1. Evidence-first findings

**Current billing architecture (re-anchored on main `38bf14a`):**
Paddle is the only automated path (post-#1143): overlay checkout via
server-owned checkout sessions (`paddle_checkout_sessions`), signed webhook
→ `paddle_webhook_service` → `paddle_repo.upsert_paddle_subscription` (the
single entitlement writer, feeding `resolve_effective_user_plan`). Runtime
mode from public `GET /api/v1/billing/config`; UI fails closed when Paddle
can't be offered. Admin manual activation exists and is the authorized
manual approval mechanism: `POST /api/v1/admin/subscriptions/activate`
(admin-only, upserts entitlement with `admin_manual_*` sentinels, logs
`payment_reference`). `subscription_intents` records upgrade-intent
analytics (no status/reference — not usable as a request store).

**Previous WhatsApp implementation (recovered from git history):** client
side only — `buildWhatsAppUpgradeUrl`/`buildWhatsAppManageUrl` in
`apps/web/lib/billing.ts` + manual-mode CTA branches in the subscription
UI. Removed by **#1143** (`e903496`, owner directive 2026-07-17
"Paddle-only, fail-closed", handoff `2026-07-17-1143-paddle-only-reshape.md`),
pinned by banned-words tests. Unsafe/stale parts that do NOT return: the
user's email embedded in the message, AED price copy, client-built
plan/price, no server record, no idempotency. Reused safe parts: the
`wa.me/<number>?text=` deep-link shape and the established support number
`971585989080` (still present as the support-contact default).

**Smallest safe implementation (what this PR ships):** a server-owned
pending-request flow + secondary CTA; approval rides the EXISTING admin
mechanism (no new approval surface, no new privileges):

- `migrations/049_whatsapp_subscription_requests.sql` — additive table:
  opaque unique `reference` (`RICO-…`), authenticated `user_id`, server
  plan/price/currency snapshot, `status` pending→approved/rejected,
  timestamps, `approved_by/approved_at`; partial unique index = one pending
  request per user (idempotency arbiter). Rollback: `DROP TABLE`.
  Drift-check signatures registered ("049" table + partial index).
- `src/repositories/whatsapp_requests_repo.py` — get-or-create pending
  (race-safe), reference lookup, status transition. Never touches
  entitlement.
- `src/api/routers/billing_whatsapp.py` —
  `GET /api/v1/billing/whatsapp/config` (public `{whatsapp_active}` boolean
  only) and authenticated
  `POST /api/v1/billing/whatsapp-subscription-request`: fail-closed on
  config, ignores every client field except `language` ("en"|"ar"),
  resolves plan/price/currency from `src/subscription_plans.py`
  (Rico Monthly, USD 21.50), returns
  `{reference, status, plan, price, currency, whatsapp_url, note_en, note_ar}`
  — no JWTs, ids, or profile data. Message = reference/plan/price + request
  for payment instructions (EN/AR templates, spec copy).
- `src/api/routers/admin_subscriptions.py` — after successful manual
  activation, a `payment_reference` starting `RICO-` best-effort marks the
  matching request approved (audit bookkeeping; never blocks or undoes the
  activation).
- Frontend — `/subscription` gains a SECONDARY "Subscribe via WhatsApp" /
  "اشترك عبر واتساب" CTA under the primary Paddle CTA: fail-hidden unless
  the server reports `whatsapp_active`, request created BEFORE WhatsApp
  opens, repeated-click protected, honest errors, and the mandated copy
  "Activation occurs after payment verification." /
  "يتم تفعيل الاشتراك بعد التحقق من الدفع." (`/settings` intentionally
  stays Paddle-only management — out of the assisted-channel MVP.)

## 2. Entitlement security boundary

`paddle_repo.upsert_paddle_subscription` remains the ONLY entitlement
writer, reachable by exactly two callers: the Paddle webhook (signed) and
the admin-only manual activation endpoint. The WhatsApp flow can create
pending rows and open a chat — nothing else. Pinned by tests
(`test_request_creation_never_touches_entitlement`, cross-user identity,
forged plan/price rejection).

## 3. Operational approval procedure (owner/support)

1. User taps "Subscribe via WhatsApp" → pending request `RICO-…` created →
   WhatsApp opens with the prefilled message.
2. Support replies with verified payment instructions; user pays
   out-of-band; support verifies receipt of USD 21.50.
3. Owner/admin activates:
   `POST /api/v1/admin/subscriptions/activate`
   `{"email": <user email>, "plan": "pro", "duration_days": 30,
     "payment_reference": "RICO-…"}`
   → entitlement active; the matching request auto-marks approved
   (audit trail: `approved_by`, `approved_at`).
4. Rejection: reply in chat; optionally mark the row rejected via SQL/ops
   tooling (no user-facing effect — entitlement never existed).

Support ownership: the WhatsApp inbox behind `WHATSAPP_SUBSCRIPTION_NUMBER`
(owner today). SLA expectation set in-chat, not in the product UI.

## 4. Production environment variables (Render — NOT set by this PR)

```env
WHATSAPP_SUBSCRIPTIONS_ENABLED=true     # default false = channel off
WHATSAPP_SUBSCRIPTION_NUMBER=971585989080   # E.164; owner may designate a dedicated number
```

Missing/invalid values fail closed (CTA hidden, endpoint 503); Paddle is
unaffected in every configuration. Migration 049 must be applied (verify
via the Migration Drift Check workflow) BEFORE enabling the flag — the
endpoint 503s harmlessly until then.

## 5. Risks

- **Perceived-payment risk**: a user may believe messaging = subscribing.
  Mitigated by the mandated activation-note copy, the "info" toast, and no
  success claim on open.
- **Support load**: manual verification scales linearly with volume —
  acceptable at current scale; revisit if assisted volume grows.
- **Reference misuse**: references are opaque and grant nothing; approval
  requires the admin endpoint + the user's email.
- **Parallel-channel confusion**: Paddle stays visually primary; the CTA is
  labeled assisted.

## 6. Acceptance criteria

- [x] Paddle CTA/behavior byte-identical (no Paddle file touched).
- [x] WhatsApp CTA renders only when the server reports the channel active;
      fail-hidden otherwise (config missing/invalid/unreachable).
- [x] Request created before WhatsApp opens; repeated clicks reuse the
      single pending request; honest errors; no false success claim.
- [x] Entitlement unreachable from the assisted flow (pinned by tests).
- [x] Bilingual copy (EN/AR) incl. the mandated activation note.
- [x] Backend 23 + frontend 23 targeted tests green; full suites green;
      `next build` green.
- [ ] Owner: set the two Render env vars + apply migration 049, then a live
      assisted round-trip (request → chat → admin activate → entitlement
      once → duplicate activate idempotent).

## 7. Rollback

Set `WHATSAPP_SUBSCRIPTIONS_ENABLED=false` on Render: CTA disappears
(fail-hidden), request endpoint 503s, pending rows are preserved for audit,
Paddle continues unchanged, no entitlement change for anyone. Code rollback:
revert the PR's squash commit; migration 049 may stay (inert) or be dropped
per the file's documented rollback.

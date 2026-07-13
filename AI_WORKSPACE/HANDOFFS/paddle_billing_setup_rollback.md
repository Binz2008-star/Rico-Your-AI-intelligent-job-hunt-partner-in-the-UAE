# Paddle Billing — Setup & Rollback

Branch: `feat/paddle-billing`
Migrations: `migrations/040_paddle_billing.sql`, `migrations/041_paddle_grace_period.sql`
Scope: single plan — Rico Monthly, **USD 21.50/month** (authoritative displayed and charged price). AED 79 is shown alongside as an approximate reference for UAE users only. Paddle does not support AED as a billing currency.

---

## Setup

### 1. Paddle Sandbox account

1. Create account at <https://sandbox-vendors.paddle.com>
2. Go to **Catalog → Products** → create "Rico Monthly" with a single monthly
   USD 21.50/month price. Paddle operates in USD only. AED 79 is an approximate
   reference shown to UAE users — it is NOT the charged amount. Single-plan scope: no yearly cycle, no Premium tier.
3. Note the price ID (format: `pri_...`)

### 2. Webhook endpoint

1. In Paddle sandbox: **Notifications → New destination**
2. URL: `https://rico-job-automation-api.onrender.com/api/v1/billing/paddle/webhook`
3. Subscribe to events:
   - `subscription.created`
   - `subscription.updated`
   - `subscription.activated`
   - `subscription.past_due`
   - `subscription.paused`
   - `subscription.resumed`
   - `subscription.canceled`
   - `transaction.completed`
   - `transaction.payment_failed`
4. Copy the **signing secret** shown (format: `pdl_ntf_...`)

### 3. Backend environment variables — Sandbox (Render dashboard)

> **SANDBOX ONLY.** All values below come from sandbox-vendors.paddle.com.
> Do NOT mix Sandbox and Live tokens, API keys, webhook secrets, or Price IDs.

```sh
BILLING_MODE=paddle
PADDLE_SANDBOX=true
PADDLE_API_KEY=<sandbox API key — Paddle Sandbox → Developer Tools>
PADDLE_WEBHOOK_SECRET=<sandbox signing secret from step 2 — format: pdl_ntf_...>
PADDLE_PRO_MONTHLY_PRICE_ID=<sandbox pri_... — Paddle Sandbox → Catalog → Prices>
RICO_PRO_PRICE_USD=21.50
```

`RICO_PRO_PRICE_USD` is the **display/config amount** shown in the UI and API.
`PADDLE_PRO_MONTHLY_PRICE_ID` is the **Paddle catalog Price ID** — a separate opaque string.
These are different values and must not be confused.

Obsolete — remove from Render if present: `RICO_PRO_PRICE_AED`, `RICO_MONTHLY_PRICE_USD`.

### 4. Frontend environment variables — Sandbox (Vercel dashboard)

> **SANDBOX ONLY.** All values below come from sandbox-vendors.paddle.com.

```sh
NEXT_PUBLIC_BILLING_MODE=paddle
NEXT_PUBLIC_PADDLE_SANDBOX=true
NEXT_PUBLIC_PADDLE_CLIENT_TOKEN=<sandbox client token — Paddle Sandbox → Developer Tools → Authentication>
NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID=<sandbox pri_... — must match PADDLE_PRO_MONTHLY_PRICE_ID above>
```

**NEVER** set `NEXT_PUBLIC_PADDLE_API_KEY` — `PADDLE_API_KEY` is server-side only.

---

### Sandbox catalog IDs (created programmatically — safe to document, DO NOT use with PADDLE_SANDBOX=false)

| Item | ID |
|------|----|
| Product | `pro_01kxer83ae1mhafykkvgj7482z` |
| Price ID (`PADDLE_PRO_MONTHLY_PRICE_ID`) | `pri_01kxer8h278hvw37ec59yg73hg` |
| Webhook destination | `ntfset_01kxer96wk8jrgdyxjjdtyzc6x` |
| Webhook signing secret (`PADDLE_WEBHOOK_SECRET`) | `pdl_ntfset_01kxer96wk8jrgdyxjjdtyzc6x_LMwc5p61X4HPq/YYytBXSs0gNY9ROJDq` |

Price: USD 21.50/month, monthly, qty 1, no trial. All 9 events subscribed.
Endpoint: `https://rico-job-automation-api.onrender.com/api/v1/billing/paddle/webhook`

**Client token** (`NEXT_PUBLIC_PADDLE_CLIENT_TOKEN`): cannot be retrieved via API.
Get it from: sandbox-vendors.paddle.com → Developer Tools → Authentication → Client-side tokens.

**Complete Sandbox env block for Render:**

```sh
BILLING_MODE=paddle
PADDLE_SANDBOX=true
PADDLE_API_KEY=<sandbox API key — keep in Render only, never commit>
PADDLE_WEBHOOK_SECRET=pdl_ntfset_01kxer96wk8jrgdyxjjdtyzc6x_LMwc5p61X4HPq/YYytBXSs0gNY9ROJDq
PADDLE_PRO_MONTHLY_PRICE_ID=pri_01kxer8h278hvw37ec59yg73hg
RICO_PRO_PRICE_USD=21.50
```

**Complete Sandbox env block for Vercel:**

```sh
NEXT_PUBLIC_BILLING_MODE=paddle
NEXT_PUBLIC_PADDLE_SANDBOX=true
NEXT_PUBLIC_PADDLE_CLIENT_TOKEN=<get from sandbox-vendors.paddle.com → Developer Tools → Authentication>
NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID=pri_01kxer8h278hvw37ec59yg73hg
```

---

### Live catalog IDs (confirmed by owner — DO NOT use with PADDLE_SANDBOX=true)

| Item | ID | Source |
|------|----|--------|
| Rico Monthly — Live Price ID | `pri_01kxdmh4f28mfmz6sg0hxf20cj` | vendors.paddle.com/products-v2 |

This ID was created in the **Live** Paddle dashboard, not Sandbox.
It must only be used when `PADDLE_SANDBOX=false` and all other Live credentials are in place.
Do **not** commit it to `.env.example` or any file tracked in git as a default value.

### 5. Run DB migrations

```bash
psql $DATABASE_URL -f migrations/040_paddle_billing.sql
psql $DATABASE_URL -f migrations/041_paddle_grace_period.sql
```

Migration 040 creates `paddle_customers`, `paddle_subscriptions`,
`paddle_webhook_events`, `paddle_checkout_sessions`. Migration 041 adds
`paddle_subscriptions.past_due_since` for the 7-day payment-retry grace
period (see `src/subscription_plans.PAST_DUE_GRACE_PERIOD`).

### 6. Deploy

```bash
git push origin feat/paddle-billing
# Open draft PR → validate sandbox → merge to main
```

### 7. Sandbox smoke test

Two surfaces exercise the same checkout/status/portal flow: `/subscription`
(main pricing page) and `/settings` (Account tab → PaddleBillingSection).
Run through at least one of them end-to-end; both call the same backend.

1. Open `/subscription` (or `/settings`) with `NEXT_PUBLIC_BILLING_MODE=paddle`
2. Confirm the page shows exactly one plan: **Rico Monthly — USD 21.50/month** (with AED 79 shown as approximate reference)
3. Click **Upgrade** → confirm `POST /api/v1/billing/paddle/checkout-session`
   fires first (Network tab) and returns a `session_token`, *then* the
   Paddle.js overlay opens — checkout must never open without that call
   succeeding first (this is the identity-attribution fix; skipping it means
   the resulting subscription can't be linked to any Rico user)
4. Complete test checkout (Paddle test card: `4242 4242 4242 4242`)
5. Verify webhook received in Paddle dashboard (Notifications log)
6. Check `paddle_subscriptions` row created for your user, with
   `paddle_customer_id` populated in `paddle_customers` too
7. Verify `/api/v1/billing/status` returns `plan: "pro"`, `status: "active"`
8. Verify `/api/v1/subscription/me` (used by `/subscription`) also reflects
   the new Paddle-backed state — this is the same data source used by
   feature gating (chat limits, saved jobs, etc.), so also confirm a paid
   feature (e.g. saved-search limit) actually unlocks, not just the billing
   status display
9. Click **Manage subscription** → Paddle portal opens
10. Grace period: in Paddle sandbox, simulate a failed renewal (or manually
    set the subscription's DB row to `status='past_due'` with a
    `past_due_since` a few minutes in the past) and confirm entitlements
    stay active; then confirm they downgrade to Free once `past_due_since`
    is more than 7 days in the past

---

## Rollback

### Immediate (no DB change needed)

```bash
# Revert BILLING_MODE to manual in Render & Vercel
BILLING_MODE=manual
NEXT_PUBLIC_BILLING_MODE=manual
```

The Paddle billing UI is gated on `isPaddleBillingMode()` — setting mode back to
`manual` hides all Paddle checkout/portal UI instantly (WhatsApp-assisted activation
takes over), no redeploy required for env-var changes on Render/Vercel. Note: Stripe
has been fully removed from this codebase (no code path, no `stripe` dependency) —
`manual` is the only fallback mode.

### Full rollback (remove Paddle tables)

```sql
-- Only run if you want to fully remove Paddle data
DROP TABLE IF EXISTS paddle_webhook_events;
DROP TABLE IF EXISTS paddle_checkout_sessions;
DROP TABLE IF EXISTS paddle_subscriptions;
DROP TABLE IF EXISTS paddle_customers;
DROP FUNCTION IF EXISTS update_paddle_customers_updated_at();
DROP FUNCTION IF EXISTS update_paddle_subscriptions_updated_at();
```

(Migration 041's `past_due_since` column is dropped automatically with the
`paddle_subscriptions` table above — no separate statement needed.)

### Git rollback

```bash
git revert --no-commit <merge-commit-sha>
git commit -m "revert: paddle billing integration"
git push origin main
```

---

## Files changed (feat/paddle-billing)

| File | Change |
|------|--------|
| `migrations/040_paddle_billing.sql` | New: paddle_customers, paddle_subscriptions, paddle_webhook_events tables |
| `src/repositories/paddle_repo.py` | New: DB repository layer for all three tables |
| `src/services/paddle_webhook_service.py` | New: idempotent webhook event processor |
| `src/api/routers/paddle_billing.py` | New: webhook, status, portal endpoints |
| `src/api/app.py` | Modified: import + include paddle_billing_router |
| `src/billing_mode.py` | Modified: added is_paddle_billing_mode(), fixed is_manual_billing_mode() |
| `apps/web/lib/billing.ts` | Modified: added isPaddleBillingMode(), updated isManualBillingMode() |
| `apps/web/lib/paddle.ts` | New: Paddle.js init, openPaddleCheckout, getPaddlePriceId |
| `apps/web/lib/api.ts` | Modified: added PaddleBillingStatus type, getPaddleBillingStatus(), createPaddleCustomerPortalSession() |
| `apps/web/lib/translations.ts` | Modified: added 20+ Paddle billing keys in EN + AR |
| `apps/web/components/billing/PaddleBillingSection.tsx` | New: billing UI component with checkout + portal |
| `apps/web/components/settings/SettingsAtelier.tsx` | Modified: renders PaddleBillingSection in Account tab when paddle mode |
| `.env.example` | Modified: added Paddle backend variable placeholders |
| `apps/web/.env.local.example` | Modified: added Paddle frontend variable placeholders |
| `tests/test_paddle_billing.py` | New/Modified: backend tests (sig, idempotency, lifecycle, billing_mode) + DB-wiring regression test |
| `AI_WORKSPACE/HANDOFFS/paddle_billing_setup_rollback.md` | New: this file |

### Follow-up pass: PR #1008 vs #1011 reconciliation, single-plan pricing, grace period

The above table reflects PR #1008's original scope. A follow-up pass compared

# 1008 against a second, independent Paddle implementation (PR #1011), kept

# 1008's architecture (client-side Paddle.js overlay checkout, DB-backed

webhook idempotency) as the base, ported over #1011's server-owned checkout
identity-attribution pattern, and fixed several bugs that would have made

# 1008 non-functional in production. Additional changes in this pass

| File | Change |
|------|--------|
| `migrations/041_paddle_grace_period.sql` | New: adds `past_due_since` to `paddle_subscriptions` for the 7-day grace period |
| `src/repositories/paddle_repo.py` | Fixed: `_get_conn` called a nonexistent `db_module.get_connection()`; routed through `RicoDB().connect()` (RealDictCursor) instead. Added `past_due_since`/`clear_past_due` params to `upsert_paddle_subscription`, added `expire_stale_paddle_subscriptions()` |
| `src/services/paddle_webhook_service.py` | Added `_lookup_existing_status`/`_compute_past_due_transition` for grace-period bookkeeping (fail-open, never blocks the webhook); collapsed price map to the single Rico Monthly price ID |
| `src/subscription_plans.py` | Rewritten: single `RICO_MONTHLY_PLAN` (USD 21.50/month authoritative price; AED 79 shown as approximate reference for UAE users) replaces the Pro/Premium two-tier scheme; `resolve_effective_user_plan()` now reads from `paddle_subscriptions` (previously read from the deleted `user_subscriptions` table — entitlement gating was disconnected from what the webhook actually wrote); added `PAST_DUE_GRACE_PERIOD` (7 days) |
| `src/api/routers/subscription.py` | Rewritten: kept only `/intent`, `/plans`, `/me`; checkout/portal/webhook removed (superseded by `/api/v1/billing/paddle/*`) |
| `src/api/routers/admin_subscriptions.py` | Repointed manual activation from the deleted `subscription_repo` to `paddle_repo.upsert_paddle_subscription`; `plan` literal restricted to `"pro"` |
| `src/api/routers/paddle_billing.py` | `create_checkout_session` billing_cycle restricted to `"monthly"` only |
| `src/run_daily.py` | Swapped `subscription_repo.expire_stale_subscriptions` for `paddle_repo.expire_stale_paddle_subscriptions` |
| `src/billing_mode.py` | Removed `is_stripe_billing_mode`; `is_manual_billing_mode()` = `!= "paddle"` |
| `src/schemas/subscription.py` | Removed Stripe-era response/request models; `paddle_customer_id`/`paddle_subscription_id` naming |
| `src/rico_chat_api.py`, `src/rico_identity.py`, `src/services/chat_service.py` | Chat/AI-identity pricing copy updated to single-plan "Rico Monthly — USD 21.50/month (approximately AED 79)"; fixed a latent bug in `chat_service.py` where the free-plan branch referenced the deleted `PAID_PLANS[SubscriptionTier.PREMIUM]` |
| `src/rico/policy/capabilities.py` | Capability name `stripe_billing` → `paddle_billing` |
| `requirements.txt` | Removed `stripe` dependency entirely |
| `src/repositories/subscription_repo.py`, `src/services/subscription_webhook_service.py` | Deleted (Stripe-era, superseded) |
| `apps/web/lib/paddle.ts` | Fixed critical identity-attribution bug: checkout now sends `customData: { checkout_session_id }` (server-issued opaque token) instead of the browser-supplied `user_id`, which the webhook could not trust |
| `apps/web/lib/api.ts` | Added `createPaddleCheckoutSession()`; removed Stripe-era `createCheckoutSession`/`createCustomerPortalSession` |
| `apps/web/components/billing/PaddleBillingSection.tsx` | `handleCheckout()` now calls `createPaddleCheckoutSession` before `openPaddleCheckout`; removed yearly-billing button |
| `apps/web/app/subscription/page.tsx` | Rewritten for single-plan pricing; `handleUpgrade` uses the Paddle.js overlay flow; `handleManage` uses the customer portal |
| `apps/web/components/LandingPage.tsx`, `apps/web/components/LandingPageNocturne.tsx` | Collapsed the Pro/Premium marketing pricing cards into one "Rico Monthly — USD 21.50/month (approximately AED 79)" card |
| `apps/web/app/terms/TermsContent.tsx` | "Payments are processed through Stripe" → "Paddle" |
| `apps/web/lib/billing.ts` | `isManualBillingMode()` simplified to `!== "paddle"` |
| `.env.example`, `apps/web/.env.local.example` | Single-plan env vars only (`RICO_PRO_PRICE_USD=21.50`, `PADDLE_PRO_MONTHLY_PRICE_ID=` blank placeholder); all `STRIPE_*` and `RICO_PRO_PRICE_AED` vars removed |
| `scripts/check_migration_drift.py` | Added migration-041 drift-check entry |
| Various `tests/*.py` | Updated for the single-plan model, DB-wiring fix, and grace period; net test delta after this pass: 6922 passed / 22 pre-existing-and-unrelated failures (verified against the unmodified PR #1008 base) |

**Customer portal**: the active contract is
`POST /api/v1/billing/customer-portal`. It calls
`POST /customers/{customer_id}/portal-sessions` on the Paddle API server-side
for the authenticated user's stored `paddle_customer_id` + `paddle_subscription_id`,
and returns the `urls.general.overview` URL. The endpoint is **fully implemented**
(not 501 — returns 404 if no subscription, 503 if PADDLE_API_KEY not set, 502 on
Paddle API error). It remains **UNVERIFIED against live sandbox** until the
Sandbox smoke step 9 is run with a real `paddle_customer_id`.
The deleted legacy `POST /api/v1/subscription/portal` route is not the
Paddle contract. Manual/WhatsApp mode is unaffected.

**Sandbox smoke checklist**: see the "Sandbox smoke test" section above —
unchanged in shape, now exercises the single Rico Monthly plan only.

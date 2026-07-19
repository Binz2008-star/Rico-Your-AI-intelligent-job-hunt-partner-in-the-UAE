# Handoff — Live Paddle checkout failure on /subscription: diagnosis + repair

Date: 2026-07-19
Branch: `claude/paddle-checkout-subscription-fix-rsxety`
Scope: Paddle only (no Stripe, no pricing redesign). Plan unchanged:
**Rico Monthly — USD 21.50/month** (internal tier `pro`).

---

## 1. What the live failure is

Owner-provided production evidence (2026-07-19, ricohunt.com):

- **/subscription** — "Subscribe with Paddle" opens the Paddle overlay, which
  immediately shows Paddle's own **"Something went wrong"** error panel; the
  Rico toast reads only the generic "Paddle checkout error".
- **/settings** — the Subscription section's "Upgrade monthly" button shows
  **"Paddle checkout is not configured for this environment."**

Evidence tiers (owner-review framing, 2026-07-19):

**Verified (proven by the screenshots + code):**

1. The Paddle.js client token IS present in the Vercel bundle and Setup
   succeeded (the overlay opened at all).
2. `POST /api/v1/billing/paddle/checkout-session` succeeded and Render
   returned a `price_id` far enough for `Checkout.open` to run.
3. The /settings message comes from the old `getPaddlePriceId()` guard —
   **Vercel Production has no `NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID`**
   baked into the bundle. Vercel's Paddle vars were not (fully) updated in
   the live cutover.
4. Paddle's servers rejected the checkout after the overlay opened.
5. The exact Paddle error **code was discarded by our own code**: Paddle.js
   v2 delivers checkout errors in the top-level `event.error`
   (`{type, code, detail}`), but `openPaddleCheckout` only read
   `event.data.message` / `event.data.error` — hence the generic toast and no
   diagnosable code anywhere.

**Highly probable (strongest fit, but inferred — not proven until the
actual env values are inspected or the new error code appears post-deploy):**
a **client/server Paddle environment mismatch** — the full sandbox smoke
passed end-to-end on 2026-07-17 (TASK-20260717-007, config
`{"billing_mode":"paddle","paddle_active":true,"sandbox":true}`), and the
/settings evidence shows Vercel's Paddle vars lag the cutover, so Vercel
plausibly still carries the sandbox client token (`test_…`) and/or
`NEXT_PUBLIC_PADDLE_SANDBOX=true` while Render was switched to the live
price (`pri_01kxdmh4f28mfmz6sg0hxf20cj` per
`paddle_billing_setup_rollback.md`). A sandbox-mode Paddle.js asked to sell
a live price ID (or the reverse) fails exactly like this.

**Still possible (check if the env matrix below is fully live and
consistent):** the **live** Paddle account is not checkout-ready — default
payment link / approved website not configured, or account not approved for
live payments. That failure carries codes like
`transaction_default_checkout_url_not_set` and is now surfaced verbatim by
the fix (see §2.1). Either way, the next failure names itself.

This session could not probe production directly (the sandbox's network
policy blocks `ricohunt.com` / `onrender.com`), so §3 lists the exact
owner-run verification steps.

## 2. What changed in this branch (all global, user-agnostic)

### 2.1 Exact Paddle error/code is now captured (`apps/web/lib/paddle.ts`)

`checkout.error` handling reads the Paddle.js v2 top-level `error` object
first (`detail [code]` becomes the rejection message) and logs
`[paddle] checkout.error {type, code, detail}` to the browser console. The
next failure names itself — no more blind "Something went wrong". The Paddle
error object carries no customer PII.

### 2.2 The client token prefix now decides the Paddle.js environment

Paddle client tokens are `test_…` (sandbox) or `live_…` (production) and only
work in their own environment. `initPaddle()` derives sandbox/production from
the token prefix; `NEXT_PUBLIC_PADDLE_SANDBOX` is only a fallback for
unrecognized prefixes, and a contradiction logs a console error naming the
fix. This removes the "live token + forgotten sandbox flag" failure class
entirely.

### 2.3 Client/backend environment mismatch fails CLOSED (`apps/web/lib/billing.ts`)

`resolveBillingUiMode` now cross-checks the backend's `sandbox` flag (from
`GET /api/v1/billing/config`, reflecting Render's `PADDLE_SANDBOX` and hence
the environment of the price ID/API key/webhook secret) against the client
token's environment. Mismatch → `"unavailable"` → the standard disabled
"Payment is temporarily unavailable" button instead of a doomed checkout.
This is the guard that would have turned the current live failure into a
disabled button.

### 2.4 `paddle_active` requires the full server credential set (`src/api/routers/paddle_billing.py`)

`GET /api/v1/billing/config` now reports `paddle_active: true` only when
`BILLING_MODE=paddle` AND `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`, and
`PADDLE_PRO_MONTHLY_PRICE_ID` are all set. A checkout whose webhook could
never verify/activate entitlement (missing secret) is never offered.
`POST /billing/paddle/checkout-session` enforces the same gate (503 when
inactive), so a stale client bundle cannot start a checkout after a rollback.

### 2.5 /settings upgrade surface is no longer fail-open (`PaddleBillingSection.tsx`)

The Settings upgrade button now resolves the same runtime billing config as
/subscription (fail-closed disabled state), and uses the **server-resolved**
`price_id` from the checkout-session response instead of requiring the
build-time `NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID` (which production
doesn't have — the /settings screenshot error). The build-time var is now
only a legacy fallback on both surfaces.

### 2.6 Tests + docs

- Backend: fail-closed matrix for `/billing/config` and checkout-session
  (83 passing in the billing suites).
- Frontend: environment-derivation, error-code surfacing, and mismatch
  fail-closed matrix (full vitest suite 781 passing; `next build` green).
- `.env.local.example` documents the token-prefix contract;
  `paddle_billing_setup_rollback.md` rollback section corrected (the old
  `NEXT_PUBLIC_BILLING_MODE=manual` instruction was stale — the runtime
  backend config is the only mode switch).

## 3. Live cutover — env matrix that must hold (owner-run)

All six values must come from the SAME Paddle environment (live):

| Where | Var | Live requirement |
|---|---|---|
| Render | `BILLING_MODE` | `paddle` |
| Render | `PADDLE_SANDBOX` | `false` |
| Render | `PADDLE_API_KEY` | live key (vendors.paddle.com → Developer Tools) |
| Render | `PADDLE_WEBHOOK_SECRET` | live signing secret of the LIVE notification destination |
| Render | `PADDLE_PRO_MONTHLY_PRICE_ID` | `pri_01kxdmh4f28mfmz6sg0hxf20cj` (owner-confirmed live price) |
| Vercel (Production) | `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN` | live token — MUST start with `live_` |
| Vercel (Production) | `NEXT_PUBLIC_PADDLE_SANDBOX` | `false` (must agree with the token) |
| Vercel (Production) | `NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID` | optional fallback; if set, the live `pri_…` |

Plus, in the **live** Paddle dashboard (vendors.paddle.com):

- Rico Monthly product + price active (not archived), USD 21.50/month.
- Website `https://ricohunt.com` approved / default payment link configured
  (Checkout settings). Without this, live checkout fails with
  `transaction_default_checkout_url_not_set` — now visible in the console.
- Notification destination
  `https://rico-job-automation-api.onrender.com/api/v1/billing/paddle/webhook`
  with the 9 subscribed events (see `paddle_billing_setup_rollback.md`), and
  its signing secret is what Render carries.

A Vercel **redeploy is required** after changing `NEXT_PUBLIC_*` vars (they
are baked at build time). Render env changes restart the service
automatically.

## 4. The 10 go-live gates (fail-closed until ALL pass)

The button stays fail-closed automatically until gates 1–3 are truly done:
with this branch, any missing server credential, inactive mode, or
client/server environment mismatch renders the disabled "Payment is
temporarily unavailable" state — a working-looking checkout can no longer
appear half-configured.

1. **Live product/price active** — verify in vendors.paddle.com catalog;
   price `pri_01kxdmh4f28mfmz6sg0hxf20cj`, USD 21.50/month, not archived.
2. **Live client token in Vercel Production** — starts with `live_`;
   redeployed.
3. **Live backend credentials in Render** — §3 matrix;
   `GET /api/v1/billing/config` returns
   `{"billing_mode":"paddle","paddle_active":true,"sandbox":false}`.
4. **Checkout opens from ricohunt.com/subscription** — overlay renders the
   Rico Monthly line item at USD 21.50; no `checkout.error` in console.
5. **Real low-risk live transaction** — owner card, USD 21.50, completes.
6. **Webhook received + signature verified** — Paddle dashboard
   Notifications log shows 200 for `subscription.created`/`activated`;
   Render logs show `paddle_webhook_done … result=processed` (an invalid
   signature would be a 400 `paddle_webhook_invalid_signature`).
7. **Entitlement activated once** — `GET /api/v1/subscription/me` returns
   `is_active: true`, plan `pro`; `/subscription` shows Active + Manage.
   Exactly one row in `paddle_subscriptions` for the user.
8. **Cancellation/refund verified** — cancel via the customer portal
   (Manage subscription); `subscription.canceled` webhook lands; UI shows
   expiry date; refund the test charge from the Paddle dashboard.
9. **Duplicate webhook does not duplicate entitlement** — redeliver the
   `subscription.created` event from the Paddle dashboard; response is
   `{"status":"skipped","reason":"duplicate"}` (DB-backed idempotency on
   `paddle_webhook_events` + upsert semantics on `paddle_subscriptions`).
10. **Rollback documented** — `paddle_billing_setup_rollback.md` §Rollback
    (updated in this branch): set `BILLING_MODE=manual` on Render → config
    reports `paddle_active:false`, both surfaces fail closed, checkout-session
    returns 503; active subscriptions and webhooks unaffected.

## 5. If checkout still fails after the env matrix is aligned

Open the browser console on /subscription and click Subscribe: the exact
failure is now logged as `[paddle] checkout.error {type, code, detail}` and
shown in the Rico toast as `detail [code]`. Interpretation:

- `…default_checkout_url_not_set` / domain-approval codes → live Paddle
  checkout settings incomplete (gate 1 territory, Paddle dashboard).
- entity/price not-found codes → price ID belongs to the other environment
  (re-check §3).
- 403/authentication → token belongs to the other environment (should be
  impossible now — the token prefix drives the environment).

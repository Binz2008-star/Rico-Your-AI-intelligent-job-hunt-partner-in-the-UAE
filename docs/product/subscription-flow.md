# Subscription Flow

This document defines the correct routing and data flow for subscription plan
selection, checkout, and plan confirmation.

Provider: **Paddle** (Stripe is fully removed — see `DEC-20260713-005`). Single
plan scope: **Rico Monthly, USD 21.50/month**. AED 79 is shown alongside as an
approximate reference for UAE users only — Paddle bills in USD. There is no
Pro/Premium two-tier model and no `/api/v1/subscription/checkout` endpoint.

## Activation gate

Paddle checkout is **not activated in production by default**. `BILLING_MODE=manual`
(WhatsApp-assisted activation) is the safe default. Paddle overlay checkout goes
live only when the owner explicitly:

1. Sets `BILLING_MODE=paddle` on Render (and the matching `NEXT_PUBLIC_BILLING_MODE=paddle` on Vercel), and
2. Applies migrations `040_paddle_billing.sql` + `041_paddle_grace_period.sql` to Neon with approval, and
3. Completes the Paddle Sandbox smoke checklist.

See `AI_WORKSPACE/HANDOFFS/paddle_billing_setup_rollback.md` for the full setup and
rollback runbook. The frontend reads `GET /api/v1/billing/config` (`billing_mode`,
`paddle_active`, `sandbox`) to decide whether to show manual or Paddle checkout.

## Plan Selection → Checkout Routing

| Plan | Action on click | Expected route |
|---|---|---|
| Free | Auto-enrolled at registration | No explicit activation endpoint needed; users start on Free plan |
| Rico Monthly (`pro`) — manual mode | Record upgrade intent | `POST /api/v1/subscription/intent` → manual/WhatsApp-assisted activation path |
| Rico Monthly (`pro`) — Paddle mode | Create Paddle checkout session | `POST /api/v1/billing/paddle/checkout-session` → open Paddle.js overlay checkout with the returned transaction |

**Plan selection must never route the user directly to `/command` or Rico chat
without completing checkout (Paddle mode) or recording intent (manual mode).**

## Relevant endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/billing/config` | Public, no secrets: `billing_mode`, `paddle_active`, `sandbox` |
| `GET /api/v1/subscription/plans` | Plan catalog — single paid plan (Rico Monthly, USD) |
| `GET /api/v1/subscription/me` | Authenticated resolved plan/status (Paddle-backed) |
| `POST /api/v1/subscription/intent` | Fire-and-forget upgrade intent (manual mode) |
| `POST /api/v1/billing/paddle/checkout-session` | Server-owned Paddle checkout attribution (Paddle mode) |
| `POST /api/v1/billing/customer-portal` | Paddle customer portal URL (auth) |
| `POST /api/v1/billing/paddle/webhook` | Paddle webhook receiver (signed, no auth) |

## Full Subscription Flow Diagram (Paddle mode)

```
User on /subscription
    ↓
Selects Free
    → Redirect /command (plan badge: Free)
    (Free plan is auto-enrolled at registration; no activation endpoint needed)

User on /subscription
    ↓
Selects Rico Monthly
    ↓ POST /api/v1/billing/paddle/checkout-session  (issues opaque session_token)
    ↓ Frontend opens Paddle.js overlay checkout with the returned transaction
    ↓
Payment success
    ↓ Paddle sends subscription.* / transaction.completed to
      POST /api/v1/billing/paddle/webhook  (signature-verified)
    ↓ Webhook resolves the user via session_token and writes paddle_subscriptions
    ↓
Frontend
    ↓ GET /api/v1/subscription/me
    ↓ Confirm plan is now active
    → Display "You're on Rico Monthly"
    → CTA: "Start chatting with Rico" → /command
```

Paid status is the **backend's** decision: `resolve_effective_user_plan` reads the
`paddle_subscriptions` table (see `src/subscription_plans.py`). A `past_due`
subscription keeps paid entitlements for a 7-day grace period. The UI must never
claim the subscription is active until `/api/v1/subscription/me` confirms it.

## Rico Chat — Subscription Responses

If the user asks Rico about subscription mid-chat, Rico must not claim the
subscription is active until the backend confirms it via `/api/v1/subscription/me`.

If the user is on Free and asks about upgrading:

> You're on the Free plan. Want to upgrade to Rico Monthly (USD 21.50/month) for
> higher limits, advanced match scoring, and priority support? I'll take you to the
> upgrade page.

The upsell CTA must route to `/subscription`, not to generic chat.

## /subscription/success Page Requirements

- On mount, fetch active plan from backend via `/api/v1/subscription/me` (do not trust URL params alone).
- Display the plan name (Rico Monthly).
- If the backend still returns Free/inactive (e.g. webhook not yet processed), show a "Processing your payment — this may take a moment" state and retry after a short delay.
- CTA: "Start chatting with Rico" → navigates to `/command`.
- Do not show payment method details or Paddle transaction IDs to the user.

## /command Plan Badge

- Fetch plan on mount via `/api/v1/subscription/me`.
- Display badge next to the user avatar or in the header: `Free` or `Rico Monthly`.
- Do not hard-code the plan in frontend state from the plan selection click — always confirm from backend.

## Test Checklist

- [ ] `GET /api/v1/billing/config` reports the correct `billing_mode` and `sandbox` flag.
- [ ] In manual mode, selecting Rico Monthly records intent, not a Paddle checkout.
- [ ] In Paddle mode, selecting Rico Monthly calls `POST /api/v1/billing/paddle/checkout-session`, not `/command`.
- [ ] `/subscription/success` fetches and displays the confirmed active plan from the backend.
- [ ] `/command` shows the correct plan badge after activation.
- [ ] Free user upsell CTA routes to `/subscription`, not `/command` or chat.
- [ ] Rico does not say "subscription is active" until backend confirms it.
- [ ] No path calls a Stripe endpoint or references a Premium plan (both retired).

## Known Gaps / Next PRs

1. **Paddle activation (owner-gated)** — set `BILLING_MODE=paddle`, apply migrations 040 + 041, and complete the Sandbox smoke checklist before enabling paid checkout.
2. **`/subscription/success` page** — must fetch the confirmed plan from backend; show a processing state if the webhook has not yet been processed.
3. **Plan badge on `/command`** — must read from `/api/v1/subscription/me`, not from local state.

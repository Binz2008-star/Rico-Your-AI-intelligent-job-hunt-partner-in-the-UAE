# Subscription Flow

This document defines the correct routing and data flow for subscription package selection, checkout, and plan confirmation.

## Package Selection → Checkout Routing

| Package | Action on click | Expected route |
|---|---|---|
| Free | Activate free plan immediately | `POST /api/v1/subscriptions/activate-free` → redirect to `/command` |
| Pro | Create Stripe Checkout session | `POST /api/v1/subscriptions/checkout` with `plan=pro` → redirect to Stripe Checkout URL |
| Premium | Create Stripe Checkout session | `POST /api/v1/subscriptions/checkout` with `plan=premium` → redirect to Stripe Checkout URL |

**Package selection must never route the user directly to `/command` or Rico chat without completing checkout for paid plans.**

## Current Bug

`apps/web/app/command/page.tsx` currently handles package selection by routing all plans (including Pro and Premium) to `/command` without calling the checkout endpoint. This skips payment entirely and must be fixed.

Fix tracked in Known Gaps / Next PRs section below.

## Full Subscription Flow Diagram

```
User on /subscription
    ↓
Selects Free
    ↓ POST /api/v1/subscriptions/activate-free
    ↓ 200 OK — plan: free activated
    → redirect /command (plan badge: Free)

User on /subscription
    ↓
Selects Pro or Premium
    ↓ POST /api/v1/subscriptions/checkout { plan: "pro" | "premium" }
    ↓ Backend creates Stripe Checkout Session
    ↓ Returns { checkout_url: "https://checkout.stripe.com/..." }
    → frontend redirect to checkout_url

Stripe Checkout
    ↓
Payment success
    → Stripe redirect to /subscription/success?session_id=...

/subscription/success
    ↓ GET /api/v1/subscriptions/status (or /api/v1/me with plan field)
    ↓ Confirm plan is now active
    → Display "You're on Pro/Premium"
    → CTA: "Start chatting with Rico" → /command

/command
    ↓ Reads active plan from /api/v1/me or subscription endpoint
    → Displays confirmed plan badge (Free / Pro / Premium)
```

## Rico Chat — Subscription Responses

If the user asks Rico about subscription mid-chat:

> You selected Pro. I'll take you to secure checkout now. After payment, I'll activate your Pro workspace and bring you back here.

Rico must not claim the subscription is active until the backend confirms it via `/api/v1/me` or the subscription status endpoint.

If the user is on Free and asks about upgrading:

> You're on the Free plan. Want to upgrade to Pro for unlimited job tracking, inbox import, and priority matching? I'll take you to the upgrade page.

The upsell CTA must route to `/subscription`, not to generic chat.

## /subscription/success Page Requirements

- On mount, fetch active plan from backend (do not trust URL params alone).
- Display plan name.
- If backend returns plan still as free or inactive (e.g., webhook not yet processed), show a "Processing your payment — this may take a moment" state and retry after a short delay.
- CTA: "Start chatting with Rico" → navigates to `/command`.
- Do not show payment method details or Stripe session IDs to the user.

## /command Plan Badge

- Fetch plan on mount via `/api/v1/me` or dedicated subscription endpoint.
- Display badge next to user avatar or in header: `Free`, `Pro`, or `Premium`.
- Do not hard-code the plan in frontend state from the package selection click — always confirm from backend.

## Test Checklist

- [ ] Clicking Pro package calls checkout endpoint, not `/command`.
- [ ] Clicking Premium package calls checkout endpoint, not `/command`.
- [ ] Successful checkout Stripe redirect lands on `/subscription/success`.
- [ ] `/subscription/success` fetches and displays confirmed active plan.
- [ ] `/command` shows correct plan badge after successful checkout.
- [ ] Free user upsell CTA routes to `/subscription`, not `/command` or chat.
- [ ] Rico does not say "subscription is active" until backend confirms it.
- [ ] Clicking Free activates free plan and proceeds to `/command`.

## Known Gaps / Next PRs

1. **Subscription routing fix** — `apps/web/app/command/page.tsx` package selection must route Pro/Premium to Stripe Checkout, not `/command`.
2. **`/subscription/success` page** — must fetch confirmed plan from backend; show processing state if webhook not yet processed.
3. **Plan badge on `/command`** — must read from backend, not from local state.
4. **Free plan activation endpoint** — verify `POST /api/v1/subscriptions/activate-free` exists and is wired up.

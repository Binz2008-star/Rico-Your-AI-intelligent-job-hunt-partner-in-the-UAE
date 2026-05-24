# Subscription Flow

This document defines the correct routing and data flow for subscription package selection, checkout, and plan confirmation.

## Package Selection → Checkout Routing

| Package | Action on click | Expected route |
|---|---|---|
| Free | Auto-enrolled at registration | No explicit activation endpoint needed; users start on Free plan |
| Pro | Create Stripe Checkout session | `POST /api/v1/subscription/checkout` with `plan=pro` → redirect to Stripe Checkout URL |
| Premium | Create Stripe Checkout session | `POST /api/v1/subscription/checkout` with `plan=premium` → redirect to Stripe Checkout URL |

**Package selection must never route the user directly to `/command` or Rico chat without completing checkout for paid plans.**

## Current Bug (fixed in PR #207)

Two gaps existed in `apps/web/app/subscription/page.tsx`:

1. **Mock mode dead-end**: When Stripe is not yet configured, `createCheckoutSession` returns `provider: "mock"`. The frontend was showing a toast "Stripe Checkout is not configured" in production and hiding the inline notice behind a `NODE_ENV === "development"` check. Users had no path forward.

2. **Free plan row had no CTA**: `FreePlanRow` was purely informational — no button to continue to `/command` (logged-in users) or `/signup` (unauthenticated users).

Both fixed in PR #207:
- Mock notice is now shown in all environments with honest copy and a "Continue with Free plan →" link.
- `FreePlanRow` now shows "Open Rico →" (logged-in free users) or "Sign up free →" (unauthenticated).

## Full Subscription Flow Diagram

```
User on /subscription
    ↓
Selects Free
    → Redirect /command (plan badge: Free)
    (Free plan is auto-enrolled at registration; no activation endpoint needed)

User on /subscription
    ↓
Selects Pro or Premium
    ↓ POST /api/v1/subscription/checkout { plan: "pro" | "premium" }
    ↓ Backend creates Stripe Checkout Session
    ↓ Returns { checkout_url: "https://checkout.stripe.com/..." }
    → frontend redirect to checkout_url

Stripe Checkout
    ↓
Payment success
    → Stripe redirect to /subscription/success?session_id=...

/subscription/success
    ↓ GET /api/v1/subscription/me
    ↓ Confirm plan is now active
    → Display "You're on Pro/Premium"
    → CTA: "Start chatting with Rico" → /command

/command
    ↓ Reads active plan from /api/v1/subscription/me
    → Displays confirmed plan badge (Free / Pro / Premium)
```

## Rico Chat — Subscription Responses

If the user asks Rico about subscription mid-chat:

> You selected Pro. I'll take you to secure checkout now. After payment, I'll activate your Pro workspace and bring you back here.

Rico must not claim the subscription is active until the backend confirms it via `/api/v1/subscription/me`.

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

- Fetch plan on mount via `/api/v1/subscription/me`.
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
3. **Plan badge on `/command`** — must read from `/api/v1/subscription/me`, not from local state.

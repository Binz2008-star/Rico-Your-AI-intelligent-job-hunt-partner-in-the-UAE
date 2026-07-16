# Current System Status

**Overall status: Yellow — Operational with known product gaps**

The system is running. Backend is live on Render, frontend is live on Vercel. Public smoke passes. Authenticated smoke is still required after each backend deploy. Specific product flows have known defects documented below.

Last updated: 2026-07-16

---

## Live Systems

| System | URL | Status |
|---|---|---|
| Frontend | `https://ricohunt.com` | Live (Vercel) |
| Backend | `https://rico-job-automation-api.onrender.com` | Live (Render) |
| Database | Neon PostgreSQL | Live |
| Public chat (`/api/v1/rico/chat/public`) | Via Render | Live |
| Authentication (register, login, logout, `/me`) | Via Render | Live |
| Job search | Via Render | Live |
| Application tracking (basic) | Via Render | Partial |

---

## Public Smoke Status

Tier 1 public smoke (as of 2026-05-25):
- `/health` → ok
- `/version` → ok
- `ricohunt.com` home → 200
- Public chat → responding

---

## Authenticated Smoke Status

Tier 2 authenticated smoke: **pending verification after latest Render deploy.**

Known issue: `/me` 401 console noise on public routes (e.g., `/chat`, landing page). The frontend calls `/me` on unauthenticated pages, producing a 401 in the browser console. This is benign but noisy; it should be suppressed by guarding the call to auth-only pages. See Known Issues below.

---

## Known Issues

### 1. Paid billing not activated — intentional (Info)

**State:** Billing runs in `BILLING_MODE=manual` (WhatsApp-assisted activation). This is the intended safe default, not a bug.

**Provider:** Paddle is the paid-subscription source of truth. Stripe is fully removed (DEC-20260713-005) — the earlier "Stripe routing bug" is obsolete and no longer applies.

**Plan:** Single plan — Rico Monthly, USD 21.50/month (AED 79 is an approximate reference shown to UAE users; Paddle bills in USD). The retired two-tier Pro/Premium model no longer exists.

**Activation gate:** Paddle checkout goes live only when the owner explicitly sets `BILLING_MODE=paddle` on Render and applies migrations 040 + 041 with approval. See `AI_WORKSPACE/HANDOFFS/paddle_billing_setup_rollback.md` and `docs/product/subscription-flow.md`.

---

### 2. Job action context lost — "Prepare application" (High)

**Symptom:** Clicking "Prepare application — {title} at {company}" on a job card produces a generic or empty application flow response. Rico does not use the job card context.

**Impact:** Users cannot prepare a targeted application angle from a job card.

**Root cause:** Front end does not pass `job_context` (job key, title, company) in the chat payload when a job card action is triggered. Rico therefore has no job context to work with.

**Fix tracked in:** docs/product/chat-routing-contract.md — Known Gaps #1.

---

### 3. Application tracking semantics — no manual add, no inbox import (Medium)

**Symptom:** Rico tells users it cannot access email or job portals and has no path forward. Application Flow shows "no applications" with no add option.

**Impact:** Users with existing application history have no way to import or record it.

**Root cause:**
- Manual application entry is not implemented (no backend endpoint, no frontend form).
- Inbox/email import is not implemented (no OAuth flow, no scan service).

**Fix tracked in:** docs/product/application-tracking.md — Known Gaps #1, #2.

---

### 4. `/me` 401 console noise on public routes (Low)

**Symptom:** Browser console shows 401 errors on pages like `/chat` (public), landing page, and other unauthenticated routes.

**Impact:** No functional impact; confusing during debugging and smoke tests.

**Root cause:** Frontend calls `/me` on every page load without checking whether the current route requires authentication.

**Fix tracked in:** Known Gaps / Next PRs below.

---

## Known Gaps / Next PRs

| # | Description | Priority | Blocking |
|---|---|---|---|
| 1 | Paddle billing activation (owner-gated: `BILLING_MODE=paddle` + migrations 040/041 + Sandbox smoke) | Owner action | Paid plan revenue |
| 2 | Job action context fix ("Prepare application") | High | Application workflow UX |
| 3 | Manual application entry (backend endpoint + frontend form) | Medium | Application tracking completeness |
| 4 | Inbox import design and implementation (Gmail OAuth, scan, review screen) | Medium | Application tracking completeness |
| 5 | `/me` 401 console noise on public routes | Low | Nothing blocked |

---

## Deploy and Migration State

- Neon migrations 001–016 applied.
- Backend on Render: current as of PR #204.
- Vercel: current as of PR #204.

For the Render deploy checklist and migration order, see `docs/PRODUCTION_READINESS.md`.

---

## What "Yellow" Means

- Green: All tiers of smoke pass, no known high-priority bugs.
- Yellow: System is operational; at least one Tier 2 smoke is pending or at least one high-priority product bug is open.
- Red: Tier 1 smoke fails or backend is unreachable.

Current state is Yellow because:
- Tier 2 authenticated smoke is pending post-deploy verification.
- One high-priority product bug is open (job action context). Billing is intentionally in manual mode (Paddle activation is an owner-gated action, not a bug).

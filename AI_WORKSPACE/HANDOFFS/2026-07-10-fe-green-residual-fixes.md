# Handoff — FE green residual vitest fixes (`test(frontend): resolve green residual vitest failures`)

## Task

Resolve the clearly test-only residual frontend failures from TASK-20260710-008 (the "GREEN" subset,
PRs B1+B2 combined), without touching product code. Move the vitest baseline toward 321/321 so
`npm run test` can eventually become a required CI gate.

## Context

- Repository: `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE`
- Branch: `claude/career-terminology-audit-ojq1xl` (restarted from `main` at `2c685e7`, post-#942)
- Issue/PR: follow-up to #942; this PR title `test(frontend): resolve green residual vitest failures`
- Predecessor handoff: `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-test-health-ci-gate.md`

## Baseline

```
Before (post-#942, clean main):  Tests  12 failed | 309 passed (321)
After  (this PR):                Tests   4 failed | 317 passed (321)
Build:                           npm run build — passes cleanly, unchanged
```

**+8 tests fixed, all test-only. 0 product code touched. 0 new failures.** The remaining 4 are the
two YELLOW groups intentionally left for B3/B4 (owner decision required).

## Changes (all in `apps/web/__tests__/`, no product code)

1. **`signup-auth-edge-cases.test.tsx` (2 fixed)** — fixture bug. The 400/422 cases constructed
   `new ApiError("Bad request"/"Unprocessable", …)` with a non-empty message. `mapSignupError` uses
   `err.message || checkDetails`, so it rendered the message verbatim and never reached the generic
   fallback copy the test asserts. Fixed by passing an empty backend message (`new ApiError("", 400/422, {})`),
   which correctly exercises the fallback.

2. **`command-auth-state.test.tsx` (2 fixed)** — stale copy assertion. No component renders the literal
   text "Sign out"; the logout affordance is an accessible control labelled "Log out" (sidebar avatar
   button `aria-label`, plus the mobile drawer item). Updated the two authenticated assertions to
   `findAllByRole("button", { name: /log out/i })` / `getAllByRole(...)`, and the two negative
   (public/checking) assertions to `queryByRole("button", { name: /log out/i })`.

3. **`landing-page.test.tsx` (1 fixed)** — the entire hero + section copy block predated the landing
   rebuild (nearly every asserted string was gone). Rewrote the copy assertions in the first `it` to
   match current shipped strings (hero "Smarter UAE job hunting starts with your CV.", the
   problem/solution headline, the three value cards, pricing + final-CTA headlines, and trust copy).
   The second `it` (auth/onboarding links) already passed and was left unchanged.

4. **`chat-confirm-profile.test.tsx` (2 fixed)** — race condition. `handleCVUpload` in
   `app/command/page.tsx` silently returns while `chatAudience === "checking"`; the test uploaded a
   file immediately after `render()`, before the mocked `/me` resolved, so the CV-preview flow never
   started. Added `await screen.findByText("Sign up free")` (the guest-resolved marker) before each
   upload so the upload no longer races the auth check.

5. **`profile-name-edit.test.tsx` (1 fixed)** — three coupled test-fixture issues, diagnosed by
   instrumenting call stacks:
   - The inline edit field seeds its draft from the current profile name, so `userEvent.type`
     appended and produced a doubled name → added `await user.clear(input)` before typing.
   - `fetchProfile` has an extra caller beyond the page's own mount + save-refresh: the
     `useSidebarStatus` readiness hook (`hooks/useSidebarStatus.ts:75`) also calls it. That consumed
     the first positional `mockResolvedValueOnce`, mis-assigning the name values, and made the exact
     `toHaveBeenCalledTimes(2)` assertion wrong. Switched to a **state-based mock** (name is empty
     until `updateProfile` is called, then returns "Roben Nihad") and a **before/after-save delta**
     assertion (`> fetchCallsBeforeSave`) instead of a brittle global count.
   - The saved name renders in two surfaces (profile header + inline field), so the final assertion
     uses `findAllByText(...).length > 0`.

## Remaining 4 failures — NOT in this PR (YELLOW, owner decision)

- `chat-action-card.test.tsx` (3) → **B3** (needs a one-line product change in `ChatActionCard.tsx`
  + a test string update).
- `sidebar-nav-routing.test.ts` (1) → **B4** (needs a "was `/queue` nav removal intentional?" call).

Both are documented in TASK-20260710-008. Do not start them without owner sign-off.

## Verification

```bash
cd apps/web
# Targeted:
npx vitest run __tests__/signup-auth-edge-cases.test.tsx __tests__/command-auth-state.test.tsx \
  __tests__/landing-page.test.tsx __tests__/chat-confirm-profile.test.tsx __tests__/profile-name-edit.test.tsx
#   → 5 files, 16 tests passed
# Full suite:
npx vitest run          # → 317 passed | 4 failed (the two YELLOW groups)
npm run build           # → passes cleanly
```

## Rollback plan

Revert the commit. All changes are confined to five `__tests__/*` files; reverting returns the suite
to 309/12 with no product or CI-config impact.

## What was not touched

Product code, UI copy, backend/API, auth/session internals, billing, schema/migrations, dependencies,
provider/prompt routing, #920, `chat-action-card` product behavior, `sidebar /queue` nav behavior, and
the CI workflow (vitest stays informational until B3/B4/B5).

# Handoff — FE test-health + CI gate (`ci(frontend): gate build and frontend tests`)

## Task

Establish the current frontend (`apps/web`) test/build baseline on a clean `main`, fix the shared
`next/navigation`/App-Router test-crash class via test-config only, and add `npm run build` +
`npm run test` (vitest) to CI alongside the existing `pytest` and `playwright` jobs — without touching
product code and without creating a new required gate that fails today.

## Context

- Repository: `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE`
- Branch: `claude/career-terminology-audit-ojq1xl` (restarted from `main` after PR #941 merged; this is
  an unrelated follow-on task in the same session, not a continuation of the terminology audit)
- Base: `main` at `877b18b` (post-#941)
- Relevant files: `apps/web/vitest.setup.ts`, `apps/web/__tests__/*`, `.github/workflows/qa-tests.yml`

## Baseline (verified on clean `main`, before any change)

```
npm run test  →  Test Files  9 failed | 26 passed (35)
                 Tests       19 failed | 302 passed (321)
npm run build →  passes cleanly (no errors)
```

Full failing-test list and root causes captured in
`/tmp` session log at time of run (see "Root cause" table below for the durable record).

## Root cause fixed (test-config only, zero product code changed)

12 of the 19 failures shared one of two test-infrastructure gaps, not a product bug:

1. **No default `next/navigation` mock.** Several test files render components that call
   `useRouter()`/`usePathname()` without any Next App-Router test context, so Next throws
   `invariant expected app router to be mounted`. Other test files *did* mock `next/navigation`
   locally, but one (`chat-confirm-profile.test.tsx`) was missing the `usePathname` export used by
   `AppSidebar`, so vitest's strict-mock-shape check threw `No "usePathname" export is defined on the
   "next/navigation" mock`.
2. **Missing `LanguageProvider` wrapper.** Two test files rendered page components with the raw RTL
   `render()` instead of the repo's existing `renderWithProviders` helper (`__tests__/test-utils.tsx`),
   so `useLanguage()` threw `useLanguage must be used within a LanguageProvider`.

### Fix

- `apps/web/vitest.setup.ts` — added a default global `vi.mock("next/navigation", ...)` (covers
  `useRouter`, `usePathname`, `useSearchParams`, `useParams`, `redirect`, `notFound`). Test files that
  already declare their own `vi.mock("next/navigation", ...)` are unaffected — a local `vi.mock` in a
  test file overrides the global one for that file, so none of the 9 files with existing local mocks
  changed behavior.
- `apps/web/__tests__/chat-confirm-profile.test.tsx` — added the missing `usePathname` export to its
  existing local mock.
- `apps/web/__tests__/job-card.test.tsx`, `apps/web/__tests__/signals-interactions.test.tsx` — switched
  from raw `render` to the existing `renderWithProviders` helper (no new helper created; reused what
  already existed).

No product code (`app/`, `components/`, `lib/`, `contexts/`, `services/`) was touched.

## Result after fix

```
npm run test  →  Test Files  7 failed | 28 passed (35)
                 Tests       12 failed | 309 passed (321)
```

**+7 tests fixed, 0 new failures introduced, 0 product code changed.**

## Residual failures (12) — NOT fixed in this PR, grouped

Fixing the router-mount crash unmasked some of these — they were previously hidden because the test
crashed before reaching the real assertion. All 12 require a product-code or product-copy decision,
not a test-config change, so per the "stop if product code changes are required" instruction they are
left alone and only classified here:

**Group A — stale assertion vs. current product copy/behavior (needs owner decision, not a test-infra
bug):**
- `chat-action-card.test.tsx` (3) — test expects title text `"Coming soon"` / `"Not available yet"`;
  component now renders `"Not available"` / `"No endpoint configured for this action"`. Either the
  component copy changed intentionally and the test is stale, or the copy regressed.
- `landing-page.test.tsx` (1) — test expects a specific hero-heading regex; the landing page was
  rebuilt today (`feat(landing)` commits merged same day). Test predates the redesign.
- `sidebar-nav-routing.test.ts` (1) — test looks up a nav item with `href === "/queue"` (labelled
  "Applications") in `components/layout/app-nav.ts`; **no such nav item currently exists** in that
  file (confirmed by reading it — only Ask Rico/Pipeline/Profile/My Files/My Plan/Settings are
  defined). The `/queue` **page itself still exists** and builds fine, so this isn't a broken route —
  it's either an intentionally removed sidebar entry (test stale) or an accidentally dropped nav item
  (real regression). Needs an owner call, not a test fix.

**Group B — newly unmasked by the router-mount fix, cause not yet isolated (needs deeper
investigation, not test-config):**
- `chat-confirm-profile.test.tsx` (2) — now renders far enough to hit `"Use this profile"` / a
  `/chat/public` call assertion that isn't satisfied; this is deep into the command-page flow, not a
  render-crash.
- `command-auth-state.test.tsx` (2) — page renders an error/retry state (`"Couldn't load — tap to
  retry"`) instead of the authenticated `"Sign out"` state; could be `/me` mock timing or a real auth-
  state regression — unrelated to `next/navigation`, since this file already had a complete local mock
  before this PR.
- `profile-name-edit.test.tsx` (1) — router crash is fixed, but the test now fails on
  `expected "Roben Nihad", received "Roben Nihad  Roben Nihad"` (name appears duplicated with a double
  space) — a real behavior mismatch, not a test-setup gap.
- `signup-auth-edge-cases.test.tsx` (2 of original 6; 4 now pass) — `400`/`422` cases expect
  `/check your details/i` in the rendered error text; the component renders different copy for those
  status codes. `409`/generic/`500`/resend-verification cases all now pass cleanly.

## Why residuals are intentionally not fixed here

Every one of the 12 needs either a product-code change or an explicit call on which of test-vs-product
is "correct" (copy wording, nav-item presence, duplicated-name behavior, error-message text). The task
scope for this PR was test-infrastructure only; touching any of these would mean changing product
behavior or asserting a product decision without owner sign-off, which is explicitly out of bounds for
this PR.

## CI gate added

`.github/workflows/qa-tests.yml` — new `frontend` job:
- `npm run build` — **required/blocking** (passes cleanly today).
- `npm run test` (vitest) — **`continue-on-error: true`, informational only**, not yet a required
  gate, because 12 of 321 tests still fail for reasons above. Flipping this to required must wait until
  those 12 are resolved (owner-scoped follow-up), otherwise every future PR would be blocked by
  pre-existing, unrelated failures.

Existing `pytest` and `playwright` jobs are untouched.

## Changed files

- `apps/web/vitest.setup.ts`
- `apps/web/__tests__/chat-confirm-profile.test.tsx`
- `apps/web/__tests__/job-card.test.tsx`
- `apps/web/__tests__/signals-interactions.test.tsx`
- `.github/workflows/qa-tests.yml`
- `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-test-health-ci-gate.md` (this file)

## Rollback plan

Revert the commit. `vitest.setup.ts`'s global mock is additive and only affects test files with no
local override, so reverting drops the suite back to 302 passed/19 failed with no other side effects.
The CI change only adds a new job; reverting removes it and leaves `pytest`/`playwright` exactly as
before.

## Open questions for the owner

1. `chat-action-card.test.tsx`: is "Not available" / "No endpoint configured for this action" the
   intended current copy (update the test), or did the disabled-state copy regress (fix the
   component)?
2. `sidebar-nav-routing.test.ts`: was the "Applications" (`/queue`) sidebar nav item intentionally
   removed from `app-nav.ts`, or should it be restored?
3. `profile-name-edit.test.tsx`: is the doubled name (`"Roben Nihad  Roben Nihad"`) a real bug in the
   inline-edit save path, or a test-fixture issue?
4. Priority order for a follow-up PR to close out the remaining 12 residual failures, so `npm run test`
   can become a required CI gate.

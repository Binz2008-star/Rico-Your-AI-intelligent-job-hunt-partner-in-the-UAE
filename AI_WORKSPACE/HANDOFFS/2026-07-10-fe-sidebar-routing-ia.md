# Handoff — FE sidebar routing IA alignment (`test(frontend): align sidebar routing with current IA`)

## Task

Resolve the final `sidebar-nav-routing.test.ts` failure from TASK-20260710-008 (the "B4" YELLOW item).
Owner decision: the `/queue` ("Applications") sidebar nav removal is **intentional** — do not restore
it, keep the `/queue` page itself untouched.

## Context

- Repository: `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE`
- Branch: `claude/career-terminology-audit-ojq1xl` (restarted from `main` at `a844b71`, post-#944)
- Issue/PR: follow-up to #942/#943/#944; this PR title `test(frontend): align sidebar routing with current IA`
- Predecessor handoff: `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-chat-action-disabled-reasons.md`

## Changes

1. **`apps/web/__tests__/sidebar-nav-routing.test.ts`** (test) — removed the obsolete
   `const applications = …find(i => i.href === "/queue")!` lookup and its
   `"/queue (Applications) opens /queue from /flow"` test. There is no longer a `/queue` sidebar nav
   item, so there is no nav-item routing contract to assert for it. Left a short comment in its place.
   The `/queue` route is still used as a valid *origin* pathname in `otherRoutes` and the
   "/profile … from /queue" case, since the `/queue` **page still exists**.

2. **`apps/web/components/layout/AppSidebar.tsx`** (orphaned metadata only) — removed the
   `NAV_ITEM_KEYS["/queue"]: "applications"` entry. Verified dead: the only two readers,
   `NAV_ITEM_KEYS[item.href]` at the label span and the tooltip, both run inside the `.map` over
   `mainNavSections`, which no longer contains a `/queue` item, so the entry was never looked up. No
   sidebar UX or rendering behavior changed.

## What was intentionally NOT changed

- `components/layout/app-nav.ts` — `/queue` stays absent from the sidebar IA (owner decision).
- `app/queue/page.tsx` — untouched; the page still exists and builds (`/queue` 3.86 kB in the build
  output).
- The dead `item.href === "/queue" && status.queueCount > 0` badge branch in `AppSidebar.tsx`
  (~line 246) — this is rendering logic that references `status.queueCount`, outside the approved
  "orphaned metadata" scope, so it was left in place. Flagged here as a future cleanup, not acted on.

## Baseline

```
Before (post-#944):  Tests  1 failed | 320 passed (321)
After  (this PR):     Tests  0 failed | 320 passed (320)   ← total dropped by 1: the obsolete
                                                              /queue nav-item test was removed,
                                                              not converted to a passing test.
Build:                npm run build — passes cleanly; /queue route still builds (3.86 kB).
```

Note: the owner's "expected 321/0" assumed the failing test would be made to pass; the correct
resolution for an intentionally-removed nav item is to **delete** the obsolete test, yielding 320/0.

## Known pre-existing flake (does not block this PR; blocks B5)

`chat-confirm-profile.test.tsx` intermittently fails in the *full-suite* run (1 of 2 full runs here),
but passes deterministically in isolation (3/3, twice). Root cause: jsdom has no
`Element.prototype.scrollTo`, and `vitest.setup.ts` only mocks `scrollIntoView`; the command page's
`scrollMessagesPane` throws inside a `requestAnimationFrame` callback that leaks across test files.
Pre-existing (not introduced by B1–B4) and not touched here (out of allowed scope). Does not block PRs
today because CI runs vitest with `continue-on-error: true` and gates on `npm run build`. **Must be
fixed (mock `scrollTo` in `vitest.setup.ts`) before B5 promotes vitest to a required gate.**

## Verification

```bash
cd apps/web
npx vitest run __tests__/sidebar-nav-routing.test.ts   # → 15 passed
npx vitest run                                          # → 320 passed (deterministic; see flake note)
npm run build                                           # → passes; /queue route builds (3.86 kB)
ls app/queue/page.tsx                                   # → still exists
```

## Rollback plan

Revert the commit. Both changes are removals of obsolete/dead code (one test case + one unused
metadata entry); reverting reintroduces the failing `/queue` nav-item test and the orphaned key with
no other effect.

## What was not touched

`app-nav` `/queue` IA, the `/queue` page, sidebar UX/rendering (badge branch left as-is),
LandingPageV2, backend/API, auth/session, billing, schema/migrations, dependencies, provider/prompt
routing, #920, and the CI workflow (vitest stays informational pending the B5 flake fix).

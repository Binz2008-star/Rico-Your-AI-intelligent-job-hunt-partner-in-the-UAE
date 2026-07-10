# Handoff — FE vitest blocking gate (`ci(frontend): make vitest a blocking gate`)

## Task

Complete TASK-20260710-008 (the "B5" step): fix the pre-existing `scrollTo` jsdom flake in the shared
vitest setup, prove the frontend suite is stable, and promote `npm run test` (vitest) from
informational-only to a required/blocking CI gate.

## Context

- Repository: `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE`
- Branch: `claude/career-terminology-audit-ojq1xl` (restarted from `main` at `489b62e`, post-#945)
- Issue/PR: final step of TASK-20260710-008; this PR title `ci(frontend): make vitest a blocking gate`
- Predecessor handoff: `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-sidebar-routing-ia.md`

## Changes (test-infra / CI / docs only — no product code)

1. **`apps/web/vitest.setup.ts`** — added `HTMLElement.prototype.scrollTo` and `window.scrollTo`
   mocks (jsdom implements neither). The command page's `scrollMessagesPane` calls `pane.scrollTo(...)`
   inside a `requestAnimationFrame` callback; without the mock it threw `scrollTo is not a function`,
   and because the throw happened in an async animation-frame callback it leaked across test files and
   surfaced as an intermittent failure in `chat-confirm-profile.test.tsx` during the full-suite run.
   Mirrors the existing `scrollIntoView` mock pattern.

2. **`.github/workflows/qa-tests.yml`** — removed `continue-on-error: true` from the frontend `Vitest`
   step and renamed it `Vitest (required)`. It now blocks the `frontend` job alongside
   `npm run build`. The `pytest` and `playwright` jobs are unchanged.

## Stability evidence

The `scrollTo` flake was ~50% before this fix (1 of 2 full runs failed). After the fix:

```
npx vitest run  ×6 consecutive full-suite runs → 320 passed / 0 failed every time
                (no "scrollTo is not a function", no Uncaught exceptions)
npx vitest run __tests__/chat-confirm-profile.test.tsx → 3 passed (deterministic)
npm run build → passes cleanly
```

## Baseline / final state

```
Frontend vitest suite: 320 passed / 0 failed — stable across 6 consecutive runs.
CI frontend job:        npm run build (blocking) + npm run test / vitest (now blocking).
pytest / playwright:    unchanged, green.
```

This closes the full FE test-health arc:
`309/12 → 317/4 (B1+B2) → 320/1 (B3) → 320/0 (B4) → 320/0 stable + vitest blocking (B5)`.

## Verification

```bash
cd apps/web
npx vitest run __tests__/chat-confirm-profile.test.tsx   # → 3 passed
npx vitest run                                            # → 320 passed / 0 failed (ran 6×, all clean)
npm run build                                             # → passes
```

## Rollback plan

Revert the commit. The `vitest.setup.ts` change is additive (two prototype/window stubs) and the CI
change only re-adds `continue-on-error: true`; reverting returns vitest to informational-only and
re-exposes the (harmless-when-non-blocking) `scrollTo` flake, with no product impact.

## What was not touched

Product components, LandingPageV2, ChatActionCard, sidebar nav, the `/queue` page, backend/API,
auth/session, billing, schema/migrations, dependencies, provider/prompt routing, #920. The `pytest`
and `playwright` CI jobs are unchanged.

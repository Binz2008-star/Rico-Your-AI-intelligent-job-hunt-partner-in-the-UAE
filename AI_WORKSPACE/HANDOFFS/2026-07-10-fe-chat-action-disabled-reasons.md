# Handoff — FE chat action disabled reasons (`fix(frontend): align chat action disabled reasons`)

## Task

Resolve the 3 remaining `chat-action-card.test.tsx` failures from TASK-20260710-008 (the "B3" YELLOW
item), owner-approved for one scoped product-code touch. Move the vitest baseline 317/4 → 320/1.

## Context

- Repository: `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE`
- Branch: `claude/career-terminology-audit-ojq1xl` (restarted from `main` at `36f56fc`, post-#943)
- Issue/PR: follow-up to #942/#943; this PR title `fix(frontend): align chat action disabled reasons`
- Predecessor handoff: `AI_WORKSPACE/HANDOFFS/2026-07-10-fe-green-residual-fixes.md`

## Owner-approved decision (YELLOW, this scope only)

1. Add an explicit `open_drawer` disabled reason → `"Coming soon"`.
2. Keep the current `submit`-without-endpoint product message → `"No endpoint configured for this action"`.
3. Update the `submit`-no-endpoint **test** expectation to match that current (more useful) message.

## Changes

1. **`apps/web/components/ui/rico/ChatActionCard.tsx`** (product) — added one branch to
   `disabledReason()`: `if (action.kind === "open_drawer") return "Coming soon";`, placed after the
   approve/cancel, high-impact, and requires_confirmation gates (so those higher-priority reasons still
   win for a high-impact/confirmation open_drawer) and before the submit/navigate/default branches.
   Previously `open_drawer` fell through to the generic `"Not available"`. No other behavior changed.

2. **`apps/web/__tests__/chat-action-card.test.tsx`** (test) — the two `open_drawer` cases now pass via
   the product change; renamed and updated the `submit`-no-endpoint case from expecting
   `"Not available yet"` to the current `"No endpoint configured for this action"`.

## Baseline

```
Before (post-#943):  Tests  4 failed | 317 passed (321)
After  (this PR):     Tests  1 failed | 320 passed (321)
Build:                npm run build — passes cleanly
```

The only remaining failure is `sidebar-nav-routing.test.ts > /queue (Applications)` — the B4 YELLOW
item, still awaiting an owner decision (was `/queue` sidebar nav removal intentional?).

## Verification

```bash
cd apps/web
npx vitest run __tests__/chat-action-card.test.tsx   # → 28 passed
npx vitest run                                        # → 320 passed | 1 failed (sidebar-nav-routing /queue)
npm run build                                         # → passes cleanly
```

## Rollback plan

Revert the commit. The product change is a single additive branch in a pure string function
(`disabledReason`) with no side effects; reverting returns the suite to 317/4.

## What was not touched

Sidebar nav, `/queue`, `AppSidebar`, `app-nav`, backend/API, auth/session, billing,
schema/migrations, dependencies, provider/prompt routing, #920, and the CI workflow (vitest stays
informational until B4 lands and B5 flips it to blocking at 321/321).

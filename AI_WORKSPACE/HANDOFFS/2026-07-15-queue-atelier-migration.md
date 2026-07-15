# Queue Atelier Migration — 2026-07-15

## Scope

Full migration of `/queue` from the legacy authenticated `AppShell` surface to the approved Atelier workspace.

## Base

- Base branch: `main`
- Base SHA: `6dc535cb4823e00f248df51b8daf5c608d983bb0`
- Runtime PR: #1033
- Branch: `feat/atelier-queue`

## Changed runtime files

- `apps/web/app/queue/page.tsx`
- `apps/web/components/queue/QueueAtelier.tsx`
- `apps/web/components/queue/ApplicationDraftCard.tsx`
- `apps/web/__tests__/queue-atelier.test.tsx`

## Preserved contracts

- `getApplicationQueue`
- `getFollowUpReminders`
- `approveApplication`
- `rejectApplication`
- `ApplicationDraft` data shape
- session-cookie authentication and backend APIs

No backend, Neon, migration, Paddle, memory-engine, or `/command` behavior changed.

## Authentication result

- `/queue` now uses `useRequireAuth`.
- Resolving/guest users see `AuthGate`, not private workspace chrome.
- Guest return path is `/login?next=/queue` through the shared guard.
- Queue and reminder APIs mount only after authorization.

## Design result

- `WorkspaceShell` replaces `AppShell`.
- Existing workspace palette drives paper, ink, hairline, and sun-red styling.
- Loading, empty, populated, follow-up, error, retry, approve, and reject states are covered.
- Layout supports EN/AR direction and narrow mobile widths.

## Verification

PR head after the test stabilization fix: `c31bd23d4ee6e688e576069535e4ccdcc05dbfb2`.

GitHub Actions run `29425600847`:

- frontend build: PASS
- full frontend Vitest: PASS
- Playwright: PASS
- pytest: PASS
- real-Postgres integration: PASS
- Vercel preview: Ready

## Superseded work

PR #1016 is auth-guard-only and keeps legacy `AppShell`. It must be closed as superseded after #1033 merges.

## Control-plane note

`AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md` contains historical matrix entries that predate merged Command slices #1028/#1032 and the queue migration. This runtime PR deliberately does not broadly rewrite the program file. A separate evidence-based docs reconciliation should update the current route matrix while preserving closure/reopen history.

## Merge

- Final squash merge SHA: pending at handoff creation
- Production deployment verification: pending merge

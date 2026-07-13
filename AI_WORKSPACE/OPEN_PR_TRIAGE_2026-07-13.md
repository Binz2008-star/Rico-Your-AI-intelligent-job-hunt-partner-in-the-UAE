# Open PR Triage — 2026-07-13

This inventory is a control-plane snapshot, not permission to merge. Live GitHub state and current PR heads remain authoritative.

## Classification rules

- `ACTIVE`: the single currently approved implementation objective.
- `REVIEW`: potentially useful and awaiting focused review/CI/owner decision.
- `HOLD`: valid idea or work but not allowed to advance now.
- `STALE/CLOSE`: superseded, overlapping, or too far behind current `main`; do not resume.
- `REFERENCE`: historical/prototype evidence only; not for merge.

## Current open PR classification

| PR | Subject | Classification | Required action |
| ---: | --- | --- | --- |
| #1009 | Playwright cold-start diagnostics/timeout | REVIEW | Focused review; merge only if still needed against current main and CI evidence supports it. |
| #1008 | Paddle billing implementation (`feat/paddle-billing`; 17 files, ~2.9k additions) | HOLD / DEEP REVIEW | Do not merge or extend. Audit checkout, signed webhooks, user isolation, entitlement lifecycle, secrets/config, migrations, tests, and exact AED 79 contract. Split mixed scope if needed. |
| #1007 | favicon/icon system correction | REVIEW | Verify changed assets, build, metadata/PWA behavior, and visual approval. |
| #1002 | truthful “Discuss with Rico” settings affordances | REVIEW | Rebase/reconcile with merged #1000/#1001; confirm no false execution claim and no settings regression. |
| #997 | earlier `/settings` Atelier migration | STALE/CLOSE | Superseded by merged #1000/#1001; do not rebase or resume. |
| #996 | pitch/explainer/waitlist bundle | HOLD | Mixed scope; split any still-needed deliverable into separate tasks/PRs. |
| #989 | subscription-gating audit follow-ups | REVIEW | Deep review required before billing implementation; preserve per-account isolation and reconcile with #1008. |
| #988 | CI workflow to hide noisy bot comments | HOLD / NON-LAUNCH | One workflow file, unrelated to launch-critical product work. Review security/pinned-action permissions separately or close/defer; do not consume the active objective. |
| #987 | auth guards for `/flow` and `/queue` | REVIEW | Check current route state and conflicts; either finish as one narrow auth PR or supersede with a fresh route-specific task. |
| #985 | owner design decisions/docs | REVIEW | Confirm decisions are already reflected in current main/workspace; close if fully recorded elsewhere. |
| #968 | governance record for #965 | HOLD | Do not treat as permission for agentic implementation. |
| #967 | pre-launch gate/waitlist | HOLD | Rebase and migration-number reconciliation required if resumed; separate owner approval required. |
| #965 | journey-state/daily-plan seed | HOLD | No follow-on autonomous loop without owner decision. |
| #961 | autonomous AI loop | REFERENCE | Frozen reference only; not for merge. |
| #935 | old command proposal | REFERENCE | Historical proposal; current command work needs a fresh decision and current-code audit. |
| #873 | Rico Alive prototype | REFERENCE | Prototype/design evidence only. |
| #872 | Nocturne prototype | REFERENCE | Prototype/design evidence only. |

## Confirmed recent main changes that invalidate the old control snapshot

- Shared Atelier UI kit merged.
- Workspace Shell C and `/dashboard` migration merged.
- `/profile` Atelier migration merged.
- `/settings` Atelier migration and control-center refinement merged.
- Public teaser gate and launch film merged.
- Root-level explainer film path fix merged.
- Verification/legal routes made reachable through teaser middleware.

## Immediate cleanup order

1. Review and decide #1009.
2. Review and decide #1007.
3. Reconcile #1002 against current `/settings` main state.
4. Close #997 as superseded.
5. Perform a security and contract audit of #1008 together with #989 before any billing merge.
6. Defer or close #988 as non-launch CI housekeeping unless separately approved.
7. Keep #996, #967, #965, and #968 on hold.
8. Preserve #961, #935, #873, and #872 as reference only.
9. Re-audit #987 against the final route inventory.

## Safety rule

No agent may revive a `STALE/CLOSE`, `HOLD`, or `REFERENCE` PR merely because it is open. The active control panel and an explicit task claim are required first.

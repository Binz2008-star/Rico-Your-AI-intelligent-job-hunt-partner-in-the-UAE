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
| #1010 | control-plane reconciliation and launch execution | ACTIVE | Docs/control only. TASKS Continuity Block exists. Head `255e0c69` passed all CI checks (pytest \u2705 postgres-integration \u2705 playwright \u2705 frontend \u2705 Vercel \u2705). Remaining: final-head verification after this truth-only commit, independent approval, owner merge approval. |
| #1009 | Playwright cold-start diagnostics/timeout | MERGED | Merged to main (`fd49129b`). No further action required. |
| #1008 | Paddle billing implementation (`feat/paddle-billing`) | HOLD | CI green (pytest ✅ playwright ✅ frontend ✅ postgres-integration ✅ on `36536396`). Scope-audited and out-of-scope files reverted. #1011 closed without merge; its server-owned checkout-attribution pattern was ported into #1008. HOLD: do NOT merge or activate (`BILLING_MODE=paddle`) until Paddle Sandbox smoke, entitlement lifecycle, migration gates, and independent review are satisfied. Migrations 040+041 have NOT been applied to Neon production. |
| #1007 | favicon/icon system correction | MERGED | Merged to main (`67758854fa692e292ab7cce479805736222b749d`); Vercel production deploy confirmed. No further action required. |
| #1002 | truthful “Discuss with Rico” settings affordances | REVIEW | Rebase/reconcile with merged #1000/#1001; confirm no false execution claim and no settings regression. |
| #997 | earlier `/settings` Atelier migration | STALE/CLOSE | Superseded by merged #1000/#1001; do not rebase or resume. |
| #996 | pitch/explainer/waitlist bundle | HOLD | Mixed scope; split any still-needed deliverable into separate tasks/PRs. |
| #989 | subscription-gating audit follow-ups | REVIEW | Deep review required before billing implementation; preserve per-account isolation and reconcile with #1008. |
| #988 | workflow to hide noisy bot comments | HOLD | Non-launch CI housekeeping. Do not distract from the launch-critical sequence; review later as a narrow workflow/security task. |
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
- #1007 favicon/icon system merged (`67758854`) — Vercel production confirmed.
- #1009 Playwright webServer timeout fix merged (`fd49129b`).
- #1011 closed without merge; server-owned checkout-attribution pattern ported into #1008.
- Live main as of this update: `5a03035a` (includes two dashboard [skip ci] commits on top of `67758854`).

## Immediate cleanup order

1. Complete review and merge decision for #1010.
2. ~~Review and decide #1009.~~ Done — merged.
3. ~~Review and decide #1007.~~ Done — merged.
4. Reconcile #1002 against current `/settings` main state.
5. Close #997 as superseded.
6. Satisfy all remaining #1008 gates (Sandbox smoke, entitlement lifecycle verification, migration approval, independent review) before billing resumes.
7. #989 (subscription-gating audit) remains open REVIEW — assess independently before or alongside #1008 merge decision.
8. Keep #988 outside the launch-critical sequence.
9. Keep #996, #967, #965, and #968 on hold.
10. Preserve #961, #935, #873, and #872 as reference only.
11. Re-audit #987 against the final route inventory.

## Safety rule

No agent may revive a `STALE/CLOSE`, `HOLD`, or `REFERENCE` PR merely because it is open. The active control panel and an explicit task claim are required first.

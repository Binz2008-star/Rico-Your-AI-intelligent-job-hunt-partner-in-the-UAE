# 2026-07-15 — Control-plane refresh (docs-only)

Authority role: WRITER (docs-only, branch `claude/what-we-have-today-lkcq54`).
Activity pass: Planner.

## Why

`PROJECT_STATUS.md` (snapshot 2026-07-13), `START_HERE.md`'s execution lock, and
`CURRENT_STATE.md` (newest header 2026-07-11) all contradicted live `main` as of
2026-07-15. Per `OPERATING_RULES.md`, a control plane that conflicts with live
state blocks all runtime work, so this refresh is the unblocking move. No runtime
file changed.

## Evidence audited (live, 2026-07-15)

- `origin/main` HEAD `de8ce666` (four dashboard-only `[skip ci]` commits on
  `21ae19a7` = #1026).
- Full commit range `5a03035a..de8ce666` inspected; every non-`[skip ci]` commit
  is accounted for in the refreshed docs.
- Open PR list fetched live (12 open: #1028, #1027, #1025, #1024, #1022, #1016,
  #1002, #996, #989, #988, #967, #965).
- Changed-file lists fetched for #1027, #1024, #1028, #996 to establish file
  ownership before editing anything.
- Owner directives taken from the #1027 diff (program reopen, #1028 sole writer =
  Claude, Windsurf reviewer-only, #1029 reference-only) and the #1024 diff
  (ADR-001 ACCEPTED rev 2 at `ef66ebfa`; M1 stops before merge).

## What changed (this PR)

- `AI_WORKSPACE/PROJECT_STATUS.md` — full snapshot refresh to 2026-07-15:
  #1010/#1008 merged, teaser gate removed (site OPEN), USD 21.50/mo authoritative
  price, two active tracks, fresh 12-PR classification, reconciled launch path,
  next exact actions.
- `AI_WORKSPACE/START_HERE.md` — "Current execution lock" block replaced (was
  still "#1010 active / access gated").
- `AI_WORKSPACE/CURRENT_STATE.md` — new 2026-07-15 reconciliation header
  prepended; prior headers marked superseded by it.
- `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md` — superseded-pointer added; file
  retained as the historical snapshot.
- `AI_WORKSPACE/HANDOFFS/2026-07-15-control-plane-refresh.md` — this note.

## Deliberately NOT touched (open-PR file ownership)

- `AI_WORKSPACE/TASKS.md` — owned by open drafts #1027 (adds TASK-20260714-001)
  and #1028; editing it here would create merge conflicts with active writers.
  This handoff carries the continuity record instead.
- `AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md` — the reopen flip is #1027's
  single job; duplicating it would fork the record.
- `AI_WORKSPACE/DECISIONS.md` — touched by held PR #996; nothing here is a new
  decision (all facts trace to merged commits or owner directives already
  recorded in #1027/#1024).
- All runtime code, `LAUNCH_EXECUTION_PLAN.md`, and every `apps/web`/`src` file.

## Known open gates (unchanged by this PR, recorded for the next session)

1. #1028 EN/AR desktop+mobile visual gate, then owner merge approval.
2. #1022 real-browser Paddle Sandbox smoke; live Sandbox "Something went wrong"
   checkout error diagnosis.
3. Migration 040/041 application on Neon production not verified in this audit.
4. Owner merges pending for docs PRs #1027 and #1024.
5. Owner decision on #967 (pre-launch gate PR whose intent is obsolete now the
   site is open).

## Continuity

- Branch: `claude/what-we-have-today-lkcq54` (base = `main` @ `de8ce666`).
- Validation: docs-only — no build/test surface; file-ownership overlap check
  performed against #1027/#1024/#1028/#996 changed-file lists.
- Rollback: revert the single docs commit; no runtime impact possible.
- Next exact action: owner reviews/merges this docs PR; runtime work continues
  on #1028 and #1025 unaffected.
- Stop condition honored: no merge, no deploy, no production mutation performed.

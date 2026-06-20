# Current State

_Last updated: 2026-06-20 after PR #694 merge_

## Source-of-truth rule

This file is the session-start snapshot only. If this file conflicts with GitHub `main`, the latest merged PRs, or deployment workflow results, trust GitHub/deploy evidence first and update this file before starting new work.

## Repository / deployment baseline

- **Latest known `main` merge:** PR #694, merge commit `0eb064b06c398a62a4b94e5edb63450719c4f3e6`.
- **Previous trust/evidence merge:** PR #693, merge commit `ab964e0219f99a2178421e02dd2cc1d62fb205e3`.
- **Render backend deploy mechanism:** PR #686 added backend auto-deploy on push to `main` and `/version` commit-match verification.
- **Workspace deploy docs:** PR #690 corrected the old claim that Render auto-deployed before #686.
- **Frontend-only changes:** #693 and #694 touched frontend evidence/provenance surfaces only; no Render backend deploy is expected from those unless backend files change later.

## Recently completed / merged

| PR | Status | Purpose |
|---:|---|---|
| #680 | merged | P0 fix: stop fake job-search promises and route job-search confirmations toward real execution paths. |
| #686 | merged | Render backend auto-deploy on push to `main` with deployed-SHA verification. |
| #687 | merged | Profile warning banner + profile input validation. |
| #689 | merged | Cold-start banner, Link Opened demotion, CV role-mismatch warning. |
| #690 | merged | Workspace docs corrected for the real Render deploy mechanism after #686. |
| #693 | merged | Dashboard readiness breakdown + dashboard stats provenance labels. |
| #694 | merged | Profile/jobs/flow evidence trail: profile field breakdown, target-role provenance copy, job score fallback, flow date provenance. |

## Closed / superseded cleanup

| PR | Status | Reason |
|---:|---|---|
| #668 | closed, not merged | Stale workspace sync; carried an outdated Render auto-deploy claim. |
| #675 | closed, not merged | Old Career OS handoff superseded by #677/#683/#693/#694 and later workspace updates. |
| #682 | closed, not merged | Superseded by #672 and later Career OS merges. |

## Current open PRs to keep parked

| PR | Status | Decision |
|---:|---|---|
| #685 | draft | Security/DB-sensitive audit policy gate; do not merge before security + migration review. |
| #688 | draft | `/ask` agentic UX prototype with mock data; keep parked until product decision. |
| #691 | open | Small UX onboarding/floating-help PR; review later after the P1 pending-search bugfix. |

## Current system verdict

**AMBER.**

Healthy:

- Production foundation is stable enough for continued focused work.
- Render backend auto-deploy + `/version` verification exists after #686.
- Document-intelligence gate is on main and prevents non-CV/identity uploads from entering the CV parser.
- Trust/evidence surfaces improved via #693 and #694.

Still not GREEN:

- The latest full audit found `_store_pending_job_search()` exists but was not wired from production runtime paths at the time of audit.
- `_is_promise_only_reply()` existed as a guard but needed verification/wiring in runtime, not only tests.
- CI gating still needs cleanup: important root-level tests are not necessarily part of the enforced workflow selection.
- `CURRENT_STATE.md` and `TASKS.md` were previously stale and must not be trusted without GitHub verification.

## Immediate next task

### P1 — Wire pending job-search confirmation in runtime

Branch recommendation:

```text
fix/wire-pending-job-search
```

Goal:

- If Rico offers/promises to search but does not execute immediately, store pending job-search state.
- If the next user reply is `تمام`, `نعم`, `ok`, `yes`, or `go ahead`, execute `_classified_role_search()` from the stored state.
- Clear pending state after execution.
- Preserve normal acknowledgement behavior when no pending search exists.
- If role is missing, ask clarification instead of promising.

Constraints:

- No frontend changes.
- No DB migration.
- No scoring changes.
- No CV parser changes.
- No auth/billing changes.
- Do not touch #685 or #688.

Required proof:

- Add a full-turn regression test that does **not** pre-seed pending state.
- Report exact runtime call sites added for `_store_pending_job_search()`.
- Report whether `_is_promise_only_reply()` is now invoked in runtime.

## Next after P1

1. CI workflow cleanup so recent root-level regression tests are included in enforced checks.
2. Review #691 only if the board is otherwise clean.
3. Security/migration review for #685.
4. Product decision on #688 `/ask` prototype.

## Do not start now

- No drag-and-drop pipeline board.
- No new agentic autonomy.
- No `/ask` backend wiring.
- No approval-token execution.
- No additional UI backlog until the pending-search runtime bug is fixed.

# Tasks

_Last updated: 2026-06-20 after PR #694 merge_

Use this file as the shared task ledger. Each task must be small enough to review in one PR.

## Status values

- `proposed`
- `scoped`
- `in_progress`
- `blocked`
- `review`
- `verified`
- `done`

## Current priority order

1. TASK-20260620-033 — Wire pending job-search confirmation in runtime.
2. TASK-20260620-034 — CI gate cleanup for root-level regression tests.
3. Review #691 only after TASK-033 is merged and smoked.
4. Keep #685 and #688 parked until separate approval.

Avoid starting new UI backlog or autonomy work before TASK-033.

---

## Active tasks

### TASK-20260620-033 — Wire pending job-search confirmation in runtime

Status: scoped
Owner: unassigned
Branch: `fix/wire-pending-job-search`
Issue/PR: not opened yet

#### Objective

Make pending job-search confirmation work in real runtime, not only in pre-seeded tests.

#### Context

A read-only audit found that `_store_pending_job_search()` exists but was not called from production runtime paths at the time of audit. This means the recovery path where the user replies `تمام` after Rico offers/promises a search may not be armed in production.

#### Scope

- Find runtime paths where Rico asks/offers/promises to search but does not execute immediately.
- Store pending search state using `_store_pending_job_search()` with available role/location/context.
- On confirmation replies (`تمام`, `نعم`, `ok`, `yes`, `go ahead`), execute `_classified_role_search()` from the stored state.
- Clear pending state after successful execution.
- Preserve normal acknowledgement behavior when no pending search exists.
- If role is missing, ask clarification instead of promising.
- Check whether `_is_promise_only_reply()` should be invoked in runtime to avoid hollow search promises.

#### Constraints

- Keep the PR small and focused.
- Keep this limited to pending-search runtime behavior and related tests.
- No frontend, DB migration, scoring, CV parser, billing, or parked draft PR work in this task.

#### Acceptance criteria

- [ ] A full-turn test reproduces the runtime path without pre-seeding pending state.
- [ ] User receives or triggers a search offer/promise.
- [ ] User replies `تمام`.
- [ ] `_classified_role_search()` executes from stored state.
- [ ] Pending state clears after execution.
- [ ] No-pending `تمام` keeps existing acknowledgement behavior.
- [ ] Missing-role path asks clarification instead of promising.

#### Required verification

- [ ] Focused tests for pending job-search confirmation.
- [ ] Existing job-search action contract tests.
- [ ] Relevant conversation-state tests.
- [ ] Py compile for touched Python files.

#### Report requirements

- Changed files.
- Exact call sites where `_store_pending_job_search()` is now used.
- Whether `_is_promise_only_reply()` is now used in runtime.
- Test commands/results.
- Final recommendation: draft / ready.

---

### TASK-20260620-034 — CI gate cleanup for root-level regression tests

Status: proposed
Owner: unassigned
Branch: `ci/expand-regression-test-gate`
Issue/PR: not opened yet

#### Objective

Ensure CI gates the important root-level regression tests that are currently easy to miss.

#### Context

The latest audit reported that `qa-tests.yml` runs a limited subset and may skip important root-level test files such as job-search, public-chat, lifecycle, match-explanation, and application regression tests.

#### Scope

- Inspect `.github/workflows/qa-tests.yml`.
- Add missing root-level regression tests or run the full appropriate subset.
- Keep runtime/deploy behavior unchanged.

#### Constraints

- CI-only change.
- No app runtime code.
- No backend/frontend logic changes.
- No DB migration.
- Do not combine with TASK-033.

#### Acceptance criteria

- [ ] CI includes recent critical regression tests.
- [ ] Runtime files unchanged.
- [ ] Workflow remains reasonably fast.
- [ ] Existing checks still pass.

---

## Recently completed

| Task / PR | Status | Notes |
|---|---|---|
| #693 | done | Dashboard readiness breakdown + dashboard stats provenance. |
| #694 | done | Profile/jobs/flow evidence trail: profile field breakdown, target-role provenance copy, job score fallback, flow date provenance. |
| #690 | done | Workspace docs corrected for Render deploy mechanism after #686. |
| #686 | done | Render backend auto-deploy on push to `main` with `/version` commit-match verification. |
| #680 | done | P0 fake-search promise fix; remaining audit gap is runtime pending-state wiring, tracked as TASK-033. |

---

## Parked / separate review needed

| PR | Status | Decision |
|---:|---|---|
| #685 | draft | Security/DB-sensitive audit policy gate. Needs security + migration review. |
| #688 | draft | `/ask` mock/prototype. Product decision required before merge. |
| #691 | open | UX onboarding/floating help. Review only after TASK-033. |

---

## UI/UX audit backlog — remaining items

These are lower priority than TASK-033 and TASK-034.

- 2-B — Drag-and-drop between pipeline columns / larger stage pill.
- 2-C — Collapse zero-value pipeline stat boxes; lead with Applied/Interview/Offer.
- 3-C — Active CV indicator chip on the Profile page.
- 4-B — CV parse-confidence indicator + Review parsed data.
- 5-B — Fit-score slider guidance text.
- 6-C — Make Ask Rico the dominant sidebar action.
- 6-B / 6-D — First-use checklist + floating help icon are covered by #691 but not yet merged.

---

## Task template

```md
### TASK-YYYYMMDD-001 — <title>

Status: proposed
Owner: <human/model>
Branch: <branch-name>
Issue/PR: <link or number>

#### Objective
<one objective only>

#### Context
- Relevant files:
- Relevant docs:
- Existing behavior:

#### Constraints
- Files in scope:
- Files out of scope:
- Keep scope limited to:

#### Acceptance criteria
- [ ]
- [ ]
- [ ]

#### Required verification
- [ ] Unit tests:
- [ ] Integration tests:
- [ ] Frontend build:
- [ ] Local smoke:
- [ ] Production/deploy smoke if applicable:

#### Handoff notes
- Changed files:
- Commands run:
- Risks:
- Rollback plan:
```

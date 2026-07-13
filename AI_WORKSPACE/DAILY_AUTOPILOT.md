# Rico Daily Autopilot

## Purpose

Every agent session must determine the real project state, current ownership, and the highest-priority safe work. Agents must not open with a generic question such as "What would you like me to do?" when the repository already contains enough information to determine the next action.

## Canonical boot sequence

`AI_WORKSPACE/OPERATING_RULES.md` remains canonical for read order. Before planning, editing, testing, creating a branch, or opening a PR:

1. Read `AI_WORKSPACE/START_HERE.md`.
2. Read `CLAUDE.md`.
3. Read `AI_WORKSPACE/CURRENT_STATE.md`.
4. Read the active task and Continuity Block in `AI_WORKSPACE/TASKS.md`.
5. Read `AI_WORKSPACE/OPERATING_RULES.md`.
6. Read the latest relevant handoff referenced by `START_HERE.md`.
7. Fetch live `main` and record the exact SHA.
8. Inspect all open PRs relevant to the proposed work: owner, head, draft state, mergeability, CI, and changed-file overlap.
9. Reconcile live state against `PROJECT_STATUS.md` and the dated PR triage snapshot.
10. Build the session occupancy table.
11. Declare exactly one execution role: `WRITER`, `REVIEWER`, `RELEASE`, or `IDLE`.
12. Select and claim the highest-priority safe unowned task compatible with that role.

The Planner/Coder/Reviewer/Tester/Deploy-verifier pass types in `OPERATING_RULES.md` describe the activity being performed. The `WRITER`/`REVIEWER`/`RELEASE`/`IDLE` roles describe branch authority and concurrency. An agent must obey both without mixing responsibilities.

If live GitHub state and workspace documents disagree, the agent must stop implementation, report the conflict, and choose `REVIEWER` or `IDLE` until the control plane is reconciled.

## Required opening report

Every session must start with this compact report:

```text
RICO DAILY STATUS
Main: <exact SHA>
Active production objective: <one objective or none>
Open implementation PRs: <PR / owner / branch / status>
Other active agents: <known claims>
Stale or overlapping work: <PRs/branches that must not be resumed>
My authority role: WRITER | REVIEWER | RELEASE | IDLE
My activity pass: Planner | Coder | Reviewer | Tester | Deploy verifier
My task: <single task>
Branch: <existing or proposed branch>
Why this task is safe now: <one sentence>
Stop condition: <one sentence>
```

## Task selection rules

Select work in this order:

1. Production blocker already assigned to the session.
2. Broken CI or merge blocker on the single active objective.
3. Review of an active PR that is waiting for independent evidence.
4. Highest-priority `READY` task with no owner and no overlapping branch.
5. Control-plane reconciliation when repository state is stale.
6. `IDLE` with one concrete recommendation when no safe task exists.

An agent must not invent a new task merely to remain busy.

## Ownership and concurrency

- One writer per branch.
- One runtime objective at a time unless the owner explicitly opens parallel non-overlapping tracks.
- A UI writer may work in parallel with a backend/billing writer only when files, contracts, and migrations do not overlap and both claims are recorded.
- Review and release sessions never become silent co-writers.
- Local tools may run focused verification but must not edit another agent's branch.
- If an existing PR already implements the objective, use that PR or stop; do not create a competing implementation.

## Work claim format

A valid claim records:

```text
Task ID:
Objective:
Authority role:
Activity pass:
Owner/session:
Branch:
Base SHA:
Files allowed:
Files forbidden:
Acceptance criteria:
Required tests:
Known overlaps checked:
Stop condition:
```

The claim belongs in the task Continuity Block or the active handoff before code changes begin.

## No-work behavior

When no safe unowned task exists, the session must not ask a generic question. It must report:

```text
No safe unowned implementation task is available.
Recommended next owner decision: <specific decision>.
I am IDLE and will not create a branch or modify files.
```

## Cost and runtime rule

Do not start fan-out, broad repository scans, long integration suites, production smoke, billing mutations, or multi-agent reviews without explicit owner approval. Use the cheapest focused evidence that can change the decision.

## End-of-session requirement

Before stopping or approaching a context/tool/time limit:

- update the existing Continuity Block;
- record branch, head SHA, files changed, tests, CI/deploy state, blockers, rollback, and next exact action;
- add/update a dated handoff if the task is not verified;
- leave no undocumented work in progress.

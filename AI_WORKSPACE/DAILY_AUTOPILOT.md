# Rico Daily Autopilot

## Purpose

Every agent session must begin by determining the real project state, current ownership, and the highest-priority safe work. Agents must not open with a generic question such as "What would you like me to do?" when the repository already contains enough information to determine the next action.

## Mandatory boot sequence

Before planning, editing, testing, creating a branch, or opening a PR:

1. Fetch live `main` and record the exact SHA.
2. Read `AI_WORKSPACE/PROJECT_STATUS.md`.
3. Read `AI_WORKSPACE/START_HERE.md`.
4. Read the active task and continuity block in `AI_WORKSPACE/TASKS.md`.
5. Read the latest relevant handoff.
6. Inspect all open PRs, their branch heads, mergeability, draft state, CI state, and changed-file overlap.
7. Build the session occupancy table.
8. Declare exactly one role: `WRITER`, `REVIEWER`, `RELEASE`, or `IDLE`.
9. Select the highest-priority unowned task compatible with the declared role.
10. Claim it before making any write.

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
My role: WRITER | REVIEWER | RELEASE | IDLE
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
Role:
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

The claim belongs in the task continuity block or the active handoff before code changes begin.

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

- update the existing continuity block;
- record branch, head SHA, files changed, tests, CI/deploy state, blockers, rollback, and next exact action;
- add/update a dated handoff if the task is not verified;
- leave no undocumented work in progress.

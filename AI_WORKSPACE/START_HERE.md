# Start Here — Rico AI

This is the mandatory entrypoint for every new Rico session.

## One-line start command

```text
Rico mode. Run AI_WORKSPACE/DAILY_AUTOPILOT.md, verify live GitHub state, then obey AI_WORKSPACE/PROJECT_STATUS.md before doing anything.
```

## Mandatory bootstrap

Read and verify in this exact order:

1. Live GitHub `main`; record the exact SHA.
2. All open PRs relevant to the proposed work: head, owner, draft state, mergeability, CI, and file overlap.
3. `AI_WORKSPACE/PROJECT_STATUS.md` — execution lock.
4. `AI_WORKSPACE/DAILY_AUTOPILOT.md` — session discovery, role, and task-selection protocol.
5. `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md` — current PR classification snapshot.
6. The active task and continuity block in `AI_WORKSPACE/TASKS.md`.
7. Latest relevant handoff.
8. `AI_WORKSPACE/OPERATING_RULES.md` and `AI_WORKSPACE/AGENT_OPERATING_MODEL.md`.
9. Relevant code/tests only after all sources agree.

If any source disagrees, do not guess from conversation history. Declare `REVIEWER` or `IDLE`, report the conflict, and reconcile the control plane first.

## Current execution lock

```text
ACTIVE NOW
Control-plane reconciliation on:
chore/agent-control-plane-reconciliation

No runtime implementation writer is authorized by the workspace until this control
plane is reviewed/merged and the first launch task is explicitly claimed.

NEXT
Read-only route/design parity inventory, then one small launch-critical UI PR.
Billing (AED 79/month) and invitations are separate later tracks.

Production access stays gated until the launch smoke and owner approval.
```

## Required daily opening

Do not begin with a generic question when repository state already determines the work.

Every session must report:

```text
RICO DAILY STATUS
Main: <exact SHA>
Active production objective: <one objective or none>
Open implementation PRs: <PR / owner / branch / status>
Other active agents: <known claims>
Stale or overlapping work: <do-not-resume list>
My role: WRITER | REVIEWER | RELEASE | IDLE
My task: <one task>
Branch: <branch>
Why this task is safe now: <reason>
Stop condition: <condition>
```

## Role claim

Declare exactly one role before action:

- **WRITER** — only session allowed to push to its claimed branch.
- **REVIEWER** — read-only diff/tests/comments/evidence.
- **RELEASE** — CI/deploy/status/smoke verification only.
- **IDLE** — no safe task; report one concrete owner decision or next recommendation.

Rules:

- One writer per branch.
- Existing PR means no parallel implementation of the same objective.
- Parallel writers require explicitly recorded non-overlapping tracks.
- Windsurf/OneSurf may verify locally but must not edit a foreign branch.
- Codex reviews; it is not a second implementation owner.
- Lovable produces design/reference evidence unless explicitly assigned production scope.

## Current launch direction

Read `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md`.

```text
control-plane reconciliation
  -> open-PR cleanup
  -> route/design parity inventory
  -> launch-critical UI completion
  -> one AED 79/month billing plan
  -> branded secure invitations
  -> launch smoke + rollback readiness
  -> owner approval to open access
```

Do not mix UI, billing, auth, email, database, and deployment changes in one PR.

## Canonical source order

When sources conflict:

1. Live GitHub `main`, PR heads, CI, deployed `/version`, and verified production evidence.
2. `AI_WORKSPACE/PROJECT_STATUS.md`.
3. Active task continuity block in `AI_WORKSPACE/TASKS.md`.
4. Latest dated handoff.
5. Roadmaps/current-state documents.
6. Conversation summaries.

## Project map

- `AI_WORKSPACE/PROJECT_STATUS.md` — live execution lock.
- `AI_WORKSPACE/DAILY_AUTOPILOT.md` — mandatory session startup and safe task selection.
- `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md` — open PR classification.
- `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md` — UI, billing, invitation, and launch sequence.
- `AI_WORKSPACE/TASKS.md` — task ledger and continuity blocks.
- `AI_WORKSPACE/AGENT_OPERATING_MODEL.md` — per-agent roles.
- `AI_WORKSPACE/OPERATING_RULES.md` — merge/deploy/Neon/smoke gates.
- `AI_WORKSPACE/DECISIONS.md` — accepted decisions.

## Required workflow

```text
verify live state
  -> inspect occupancy and overlap
  -> declare role
  -> select/claim one safe task
  -> use existing branch or create one approved branch
  -> smallest safe change/review
  -> focused verification
  -> update continuity/handoff
  -> owner approval before merge/deploy/production mutation/opening access
```

## Task requirements

Every implementation task states:

- objective;
- owner/session and role;
- branch and base SHA;
- files allowed and forbidden;
- acceptance criteria;
- required tests and smoke checks;
- overlaps checked;
- risks and rollback;
- stop condition;
- next exact action.

## Continuity gate

Before a session ends, changes tools, or approaches a context/tool/time limit:

1. Update the existing task continuity block; never duplicate it.
2. Record exact branch/head, files, tests, blockers, rollback, and next action.
3. Add/update a dated handoff when work is not verified.
4. Leave no undocumented `in_progress` work.

## Standard cold-start prompt

```text
Rico mode.
Run AI_WORKSPACE/DAILY_AUTOPILOT.md.
Fetch exact live main and open PR state.
Read PROJECT_STATUS, OPEN_PR_TRIAGE, the active TASKS continuity block, and latest handoff.
Report RICO DAILY STATUS and declare WRITER, REVIEWER, RELEASE, or IDLE.
Select the highest-priority safe unowned task; do not ask a generic question.
Do not create a competing branch or touch a foreign-owned branch.
```

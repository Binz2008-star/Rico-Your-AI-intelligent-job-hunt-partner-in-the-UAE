# Start Here — Rico AI

This is the mandatory entrypoint for every new Rico session.

## One-line start command

```text
Rico mode. Start with AI_WORKSPACE/START_HERE.md, follow the canonical Session Boot Sequence in AI_WORKSPACE/OPERATING_RULES.md, then run AI_WORKSPACE/DAILY_AUTOPILOT.md before taking action.
```

## Mandatory bootstrap

This file is read first. Then follow the canonical order defined by `AI_WORKSPACE/OPERATING_RULES.md`:

1. `CLAUDE.md`.
2. `AI_WORKSPACE/CURRENT_STATE.md`.
3. The active task and Continuity Block in `AI_WORKSPACE/TASKS.md`.
4. `AI_WORKSPACE/OPERATING_RULES.md`.
5. The latest relevant handoff referenced by this file.
6. `AI_WORKSPACE/DAILY_AUTOPILOT.md`.
7. Live GitHub `main`; record the exact SHA.
8. Open PRs relevant to the proposed work: head, owner, draft state, mergeability, CI, and file overlap.
9. `AI_WORKSPACE/PROJECT_STATUS.md` and `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md` for reconciliation against live state.
10. Relevant code/tests only after all sources agree.

If any source disagrees, do not guess from conversation history. Declare `REVIEWER` or `IDLE`, report the conflict, and reconcile the control plane first.

## Current execution lock

```text
ACTIVE NOW
Control-plane reconciliation on:
chore/agent-control-plane-reconciliation
PR #1010

No runtime implementation writer is authorized by the workspace until this control
plane is independently reviewed/merged and the first launch task is explicitly claimed.

NEXT
Read-only route/design parity inventory, then one small launch-critical UI PR.
Billing (AED 79/month) and invitations are separate later tracks.

Production access stays gated until the launch smoke and owner approval.
```

## Required daily opening

Do not begin with a generic question when repository state already determines the work.

Every session reports:

```text
RICO DAILY STATUS
Main: <exact SHA>
Active production objective: <one objective or none>
Open implementation PRs: <PR / owner / branch / status>
Other active agents: <known claims>
Stale or overlapping work: <do-not-resume list>
My authority role: WRITER | REVIEWER | RELEASE | IDLE
My activity pass: Planner | Coder | Reviewer | Tester | Deploy verifier
My task: <one task>
Branch: <branch>
Why this task is safe now: <reason>
Stop condition: <condition>
```

## Authority role claim

Declare exactly one authority role before action:

- **WRITER** — only session allowed to push to its claimed branch.
- **REVIEWER** — read-only diff/tests/comments/evidence.
- **RELEASE** — CI/deploy/status/smoke verification only.
- **IDLE** — no safe task; report one concrete owner decision or next recommendation.

Also state the current activity pass from `OPERATING_RULES.md`: Planner, Coder, Reviewer, Tester, or Deploy verifier.

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

## Canonical source priority

When facts conflict, use this evidence priority while preserving the canonical boot read order above:

1. Live GitHub `main`, PR heads, CI, deployed `/version`, and verified production evidence.
2. `AI_WORKSPACE/PROJECT_STATUS.md`.
3. Active task Continuity Block in `AI_WORKSPACE/TASKS.md`.
4. Latest dated handoff.
5. Roadmaps/current-state documents.
6. Conversation summaries.

## Project map

- `AI_WORKSPACE/PROJECT_STATUS.md` — live execution lock.
- `AI_WORKSPACE/DAILY_AUTOPILOT.md` — mandatory session discovery and safe task selection.
- `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md` — open PR classification snapshot.
- `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md` — UI, billing, invitation, and launch sequence.
- `AI_WORKSPACE/TASKS.md` — task ledger and Continuity Blocks.
- `AI_WORKSPACE/AGENT_OPERATING_MODEL.md` — per-agent responsibilities.
- `AI_WORKSPACE/OPERATING_RULES.md` — canonical boot sequence and merge/deploy/Neon/smoke gates.
- `AI_WORKSPACE/DECISIONS.md` — accepted decisions.

## Required workflow

```text
canonical read order
  -> verify live state
  -> inspect occupancy and overlap
  -> declare authority role + activity pass
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
- owner/session, authority role, and activity pass;
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

1. Update the existing task Continuity Block; never duplicate it.
2. Record exact branch/head, files, tests, blockers, rollback, and next action.
3. Add/update a dated handoff when work is not verified.
4. Leave no undocumented `in_progress` work.

## Standard cold-start prompt

```text
Rico mode.
Read AI_WORKSPACE/START_HERE.md first and follow OPERATING_RULES.md's canonical boot sequence.
Run AI_WORKSPACE/DAILY_AUTOPILOT.md, fetch exact live main and relevant open PR state,
then reconcile PROJECT_STATUS, OPEN_PR_TRIAGE, the active TASKS Continuity Block, and latest handoff.
Report RICO DAILY STATUS with authority role and activity pass.
Select the highest-priority safe unowned task; do not ask a generic question.
Do not create a competing branch or touch a foreign-owned branch.
```

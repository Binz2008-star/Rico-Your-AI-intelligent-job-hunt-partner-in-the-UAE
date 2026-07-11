# Start Here — Rico AI

This is the mandatory entrypoint for every new Rico session.

## One-line start command

```text
Rico mode. Start from AI_WORKSPACE/START_HERE.md and obey AI_WORKSPACE/PROJECT_STATUS.md before doing anything.
```

## 60-second bootstrap

Read in this exact order:

1. `AI_WORKSPACE/PROJECT_STATUS.md` — live control panel and execution lock.
2. Live GitHub `main`, open PRs, and the exact active PR head.
3. The active task in `AI_WORKSPACE/TASKS.md`.
4. `AI_WORKSPACE/HANDOFFS/2026-07-11-agent-session-coordination.md`.
5. `AI_WORKSPACE/OPERATING_RULES.md`.
6. The relevant code/tests only after the steps above agree.

If any source disagrees, stop and report the conflict. Do not guess from chat history.

## Current execution lock

```text
No active runtime implementation. #963 / PR #975 is merged and
production-VERIFIED (owner-confirmed authenticated smoke, 2026-07-11);
onboarding is out of PARTIAL. `main` is at `feed8c4…` (#979 + #974 merged).

Next objective, not started: #962 (safe login return path). Start on a fresh
branch from updated `main` after its design/audit gate.

All other runtime/design/agentic work is paused unless the owner changes
AI_WORKSPACE/PROJECT_STATUS.md.
```

## Multi-session role claim

Several Claude sessions and Windsurf may be open simultaneously. Before writing, declare one role:

- **WRITER** — the only session allowed to push to the active branch.
- **REVIEWER** — read-only review, tests, comments, and evidence.
- **RELEASE** — CI/deploy/status verification only.
- **IDLE** — stop and wait.

Rules:

- One writer per branch.
- Existing PR means do not create a parallel implementation.
- Other Claude sessions default to REVIEWER or IDLE.
- Windsurf must not edit a Claude-owned branch unless ownership is explicitly handed over.
- Codex is a review signal, not a second implementation owner.
- Lovable/design agents remain prototype/reference-only unless specifically approved.

## Canonical source order

When sources conflict, use this order:

1. Live GitHub `main`, active PR head, CI, deployed `/version`.
2. `AI_WORKSPACE/PROJECT_STATUS.md`.
3. Active task continuity block in `AI_WORKSPACE/TASKS.md`.
4. Latest dated handoff.
5. `CURRENT_STATE.md`, roadmap, and historical handoffs.
6. Conversation summaries.

## Project map

- `AI_WORKSPACE/PROJECT_STATUS.md` — 30-second control panel.
- `AI_WORKSPACE/MASTER_INDEX.md` — workspace document index.
- `AI_WORKSPACE/ENGINEERING_ROADMAP.md` — vision through releases.
- `AI_WORKSPACE/AGENT_OPERATING_MODEL.md` — roles and coordination protocol.
- `AI_WORKSPACE/CURRENT_STATE.md` — deeper historical/current technical state.
- `AI_WORKSPACE/TASKS.md` — task ledger and continuity blocks.
- `AI_WORKSPACE/DECISIONS.md` — ADR log.
- `AI_WORKSPACE/OPERATING_RULES.md` — merge/deploy/Neon/smoke gates.

## Required workflow

```text
verify live state
  -> claim role
  -> read active task/PR
  -> use existing branch or stop
  -> smallest safe change/review
  -> focused verification
  -> update continuity block/handoff before stopping
  -> owner approval before merge/deploy/Neon mutation
```

## Task requirements

Every implementation task must state:

- objective;
- branch and owner;
- files in scope and out of scope;
- acceptance criteria;
- tests and smoke checks;
- risks;
- rollback;
- next exact action.

## Continuity gate

Before a session ends, loses context, changes tools, or approaches a token/time/tool limit:

1. Update the existing task continuity block; never duplicate the task.
2. Record exact branch, head SHA, changed files, tests, blockers, and next exact action.
3. Add/update a dated handoff when the work is not done/verified.
4. Do not leave `in_progress` work without a cold-start-resumable next action.

## Standard cold-start prompt

```text
Rico mode.
Read AI_WORKSPACE/PROJECT_STATUS.md first, then START_HERE.md, the live open PR board,
the active TASKS.md continuity block, and the latest handoff.
Declare WRITER, REVIEWER, RELEASE, or IDLE before taking action.
Do not create a parallel branch when an active PR already exists.
Use one writer per branch.
Report the exact main SHA, active PR/head, scope, tests, risks, rollback, and next exact action.
```

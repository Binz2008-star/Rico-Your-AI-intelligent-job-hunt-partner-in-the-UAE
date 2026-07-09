# Start Here — Rico AI

This is the entrypoint for new Rico AI work sessions.

## Short start command

```text
Rico mode. Start from AI_WORKSPACE/START_HERE.md.
```

## Latest handoff

Before starting new Rico work, read the latest rollout handoff:

1. `AI_WORKSPACE/HANDOFFS/2026-07-09-board-clean-governance-complete.md` (latest — #890 agent operating model merged at `ac0cd99`; #897 technical handoff merged at `bb9555e`; #898 Docker local-dev merged at `7fb41bc`; board clean with only #872/#873 held; no C3/C4/C8 started)
2. `AI_WORKSPACE/HANDOFFS/2026-07-08-technical-status.md` (#892 #764 trust guard merged, #894 Lovable quarantine merged, #895 C2 legal pages live, #896 duplicate closed, #898 Docker local-dev merged; #886/#867 closed as stale/superseded; #872/#873 held)
3. `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization-complete.md` (PRs #727/#724/#723/#728/#729/#730 merged + deployed; only PR C remains for Tests 1–9)
4. `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization.md` (earlier stabilization handoff — superseded by the complete handoff above)
5. `AI_WORKSPACE/HANDOFFS/2026-06-21-system-quality-audit.md` (codebase audit — bugs fixed, tech debt documented)
6. `AI_WORKSPACE/HANDOFFS/2026-06-21-career-os-roadmap-status.md` (which Career OS milestones are actually built)
7. `AI_WORKSPACE/HANDOFFS/2026-06-21-action-audit-rollout-complete.md`
8. Then continue with the read order below.

## Project map (read first)

Fastest orientation, in order:

- `AI_WORKSPACE/PROJECT_STATUS.md` — **30-second snapshot**: where Rico is, last
  merge, what works, what's next, risks, active PR. Read this first.
- `AI_WORKSPACE/MASTER_INDEX.md` — the living index of every workspace document
  (Active / Historical / Proposed) + the ADR index into `DECISIONS.md`.
- `AI_WORKSPACE/ENGINEERING_ROADMAP.md` — Vision → Architecture → Roadmap →
  Epics → Milestones → PRs → Releases, with the status of every phase (0–7).
- `AI_WORKSPACE/AGENT_OPERATING_MODEL.md` — agent roles, boundaries, and
  response logic for owner, architecture, Claude, Codex, Lovable, and release work.

## Read order

Start with the current repository state, then read:

1. `CLAUDE.md`
2. `AI_WORKSPACE/PROJECT_BRIEF.md`
3. `AI_WORKSPACE/ENGINEERING_ROADMAP.md`
4. `AI_WORKSPACE/AGENT_OPERATING_MODEL.md`
5. `AI_WORKSPACE/ARCHITECTURE.md`
6. `AI_WORKSPACE/CURRENT_STATE.md`
7. `AI_WORKSPACE/TASKS.md`
8. `AI_WORKSPACE/OPERATING_RULES.md`
9. `AI_WORKSPACE/DECISIONS.md`
10. `AI_WORKSPACE/PROMPT_CONTRACT.md`

Optional context bundle:

```bash
python scripts/sync_context.py
```

## Work flow

```text
Task entry
  -> handoff brief
  -> operating rules
  -> one branch
  -> pull request
  -> review and verification
  -> merge
  -> deploy verification when runtime changed
  -> workspace update if needed
```

## Task checklist

Each task should have:

- objective
- branch name
- files in scope
- files out of scope
- constraints
- acceptance criteria
- verification steps
- rollback plan

## Continuity Gate (read before writing anything)

Every agent starts by reading, in order: this file → `TASKS.md` (active
Continuity Blocks) → `CURRENT_STATE.md` → the latest `HANDOFFS/*` → the
active PR body → the linked GitHub issue. Every agent ends by writing/updating
the Continuity Block for the task it touched, and — if the task isn't
`done`/`verified` — a dated `HANDOFFS/<date>-<topic>.md` entry with the
Continuity Block copied in. A task with no Continuity Block, or one left
`in_progress` with no "next exact action," is not a valid stopping point.

## Branch ownership

Use one writer per branch. Other tools or reviewers can inspect and comment without editing the same branch.

## Standard handoff prompt

```text
Rico mode. Start from AI_WORKSPACE/START_HERE.md. Read the latest handoff, current state, current task in AI_WORKSPACE/TASKS.md, AI_WORKSPACE/OPERATING_RULES.md, and AI_WORKSPACE/PROMPT_CONTRACT.md. Use one branch and return summary, changed files, commands run, test results, CI/deploy status, risks, rollback plan, and open questions.
```

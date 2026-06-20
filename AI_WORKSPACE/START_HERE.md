# Start Here — Rico AI

This is the entrypoint for new Rico AI work sessions.

## Short start command

```text
Rico mode. Start from AI_WORKSPACE/START_HERE.md.
```

## Current session rule

Before starting work, verify GitHub `main` and the latest PR state. Do not assume older handoffs, `CURRENT_STATE.md`, or `TASKS.md` are current if they conflict with GitHub.

Current known baseline after the latest workspace refresh:

- Latest completed product trust work: PR #693 and PR #694.
- #685 and #688 are parked drafts.
- #691 is open but lower priority.
- Next active task: `TASK-20260620-033 — Wire pending job-search confirmation in runtime`.

## Latest handoff / state files

Read in this order:

1. `AI_WORKSPACE/CURRENT_STATE.md`
2. `AI_WORKSPACE/TASKS.md`
3. `AI_WORKSPACE/OPERATING_RULES.md`
4. Then continue with the standard read order below.

## Read order

Start with the current repository state, then read:

1. `CLAUDE.md`
2. `AI_WORKSPACE/PROJECT_BRIEF.md`
3. `AI_WORKSPACE/ARCHITECTURE.md`
4. `AI_WORKSPACE/CURRENT_STATE.md`
5. `AI_WORKSPACE/TASKS.md`
6. `AI_WORKSPACE/OPERATING_RULES.md`
7. `AI_WORKSPACE/DECISIONS.md`
8. `AI_WORKSPACE/PROMPT_CONTRACT.md`

Optional context bundle:

```bash
python scripts/sync_context.py
```

## Work flow

```text
Task entry
  -> verify GitHub main + open PRs
  -> current state + task ledger
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

## Branch ownership

Use one writer per branch. Other tools or reviewers can inspect and comment without editing the same branch.

## Standard handoff prompt

```text
Rico mode. Start from AI_WORKSPACE/START_HERE.md. Verify GitHub main and open PRs first. Then read AI_WORKSPACE/CURRENT_STATE.md, AI_WORKSPACE/TASKS.md, AI_WORKSPACE/OPERATING_RULES.md, and AI_WORKSPACE/PROMPT_CONTRACT.md. Use one branch and return summary, changed files, commands run, test results, CI/deploy status, risks, rollback plan, and open questions.
```

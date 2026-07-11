---
name: rico-memory-handoff
description: Create or update a Rico Hunt task continuity block and dated handoff so the next session can resume from the repo.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
  - write
  - edit
---

# rico-memory-handoff

## Purpose
Persist the exact state of an in-progress task into `AI_WORKSPACE` so the next session can cold-start without lost context. External notes (Claude memory, Obsidian, etc.) are advisory only; `AI_WORKSPACE` is the source of truth.

## When to use
- When the user says "pause", "stop", "handoff", "continuity", or "I need to continue later".
- When the session approaches a token, context, or time limit.
- At the end of any task that is not fully done.

## Inputs required
- Task ID / objective.
- Branch and base branch.
- Current head SHA.
- Files changed, files inspected, and files not touched.
- Tests run and results.
- Blockers and next exact action.

## Allowed actions
- Read `AI_WORKSPACE/TASKS.md` and `AI_WORKSPACE/HANDOFFS/`.
- Update the existing `TASKS.md` continuity block for the task.
- Create a dated `AI_WORKSPACE/HANDOFFS/<YYYY-MM-DD>-<topic>.md` if the task is not done.
- Record the current head SHA, status, and next action.
- Report the handoff summary.

## Forbidden actions
- Modify runtime code, tests, workflows, or `PROJECT_STATUS.md` (unless release role).
- Create or close GitHub issues.
- Merge or deploy.
- Record secrets, credentials, or user PII.
- Duplicate an existing task continuity block.

## Required output format
```markdown
### Memory handoff for <task>

- **Task ID:** ...
- **Branch:** ... (base: ...)
- **Head SHA:** ...
- **Status:** ...
- **Files changed:** ...
- **Files inspected:** ...
- **Files not touched:** ...
- **Tests run:** ...
- **Blockers:** ...
- **Next exact action:** ...
- **Stop condition:** ...
```

## Stop conditions
- The task is complete and verified.
- Live GitHub state conflicts with `PROJECT_STATUS.md`.
- No new state has been generated since the last handoff.
- The user asks to skip the handoff.

## Example prompt
"Rico memory handoff: record the current state for #963 before the session ends."

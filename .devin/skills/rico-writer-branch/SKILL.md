---
name: rico-writer-branch
description: Single-writer implementation path for Rico Hunt. Create a scoped branch, make the smallest safe change, run focused tests, update handoffs, and open a draft PR.
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

# rico-writer-branch

## Purpose
Own one implementation branch from first commit to draft PR. Enforces one branch, one PR, one objective, and keeps `AI_WORKSPACE` handoffs in sync. `AI_WORKSPACE` is the source of truth; Claude memory, Obsidian, and external notes are advisory only.

## When to use
- After the pre-implementation audit is complete.
- When the user asks to implement, fix, build, or change runtime code.

## Inputs required
- Exact objective (one sentence).
- Branch name and base branch.
- Files in scope / out of scope.
- Acceptance criteria and required tests.
- Whether to open a draft PR.

## Allowed actions
- Create or reuse the task branch.
- Edit only files in scope.
- Run focused tests and build/lint for the changed area.
- Update `AI_WORKSPACE/TASKS.md` and `AI_WORKSPACE/HANDOFFS/` continuity blocks.
- Open a draft PR when the user asks.
- Report status, changed files, tests, and risks.

## Forbidden actions
- Merge, deploy, or push without approval.
- Touch files outside scope or mix unrelated changes.
- Create a parallel branch when an active PR already exists.
- Mutate Neon, Stripe, or production services.
- Run production smoke without explicit owner approval.
- Skip the continuity block before the session ends.

## Required output format
```markdown
### Writer branch runbook for <objective>

- **Branch:** <branch> (base: <base>)
- **Scope:** ...
- **Files changed:** ...
- **Tests run:** ...
- **CI/build status:** ...
- **Blockers:** ...
- **Next exact action:** ...
- **PR:** draft/open/none
```

## Stop conditions
- Another session is already the WRITER on this branch.
- Scope expands beyond the audit.
- A new failing test appears in the changed area.
- CI/build fails and the cause is not trivial.
- The user asks to merge, deploy, or mutate production.

## Example prompt
"Rico writer branch for #963: implement canonical CV persistence in the onboarding confirmation flow, run focused onboarding tests, and open a draft PR."

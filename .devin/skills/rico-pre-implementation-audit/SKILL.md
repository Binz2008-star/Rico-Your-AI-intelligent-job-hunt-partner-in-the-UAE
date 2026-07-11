---
name: rico-pre-implementation-audit
description: Read-only pre-implementation audit for Rico Hunt. Verify PROJECT_STATUS, live GitHub state, scope, and the smallest safe change before any code is written.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# rico-pre-implementation-audit

## Purpose
Stop, read, and plan before writing Rico code. This skill is **read-only** and produces a concise audit that identifies the current state, the exact scope, the smallest safe change, and risks. `AI_WORKSPACE` is the source of truth; Claude memory, Obsidian, and external notes are advisory only.

## When to use
- A task touches multiple files, backend routing, auth, sessions, database, migrations, billing, AI routing, or webhooks.
- The user says "start", "implement", "fix", "build", "plan", or "audit" without a clear branch/scope.
- Before creating a branch or opening a PR.

## Inputs required
- Objective: one sentence.
- Issue/PR number or task ID.
- Known scope and forbidden files.
- Any owner-gated decisions.

## Allowed actions
- Read `AI_WORKSPACE/PROJECT_STATUS.md`, `START_HERE.md`, `TASKS.md`, `AGENT_OPERATING_MODEL.md`, `OPERATING_RULES.md`, `CLAUDE.md`, `AGENTS.md`, and the latest handoff.
- Verify live GitHub `main` state and open PRs.
- Read relevant code and tests.
- Produce a markdown audit with the required output format.
- Ask one clarifying question if the scope is genuinely ambiguous.

## Forbidden actions
- Modify runtime code, tests, workflows, or `PROJECT_STATUS.md`.
- Create a branch, open a PR, or push commits.
- Run migrations, production smoke, or external API calls.
- Make a code change without a completed audit.
- Treat assumptions as facts.

## Required output format
```markdown
### Pre-implementation audit for <objective>

- **Current state:** ...
- **Scope:** in-scope / out-of-scope
- **Files in scope:** ...
- **Files not to touch:** ...
- **Smallest safe change:** ...
- **Tests/smoke needed:** ...
- **Risks:** ...
- **Stop conditions:** ...
- **Next exact action:** ...
```

## Stop conditions
- `PROJECT_STATUS.md` conflicts with live GitHub state.
- An active PR already exists for this objective.
- The scope expands beyond the approved objective.
- The root cause is unclear.
- The user asks to skip the audit.

## Example prompt
"Rico pre-implementation audit for #963: confirm the canonical CV persistence path and list the exact files that must change."

# Current State

_Last updated: 2026-06-17_

## Repository baseline

- Rico AI is a UAE career companion.
- The system includes job discovery, filtering, scoring, alerts, application tracking, database storage, dashboard output, reminders, and feedback loops.
- Rico AI sits on top of the existing job automation system as the product layer.
- The backend foundation is FastAPI with Rico modules under `src/`.
- The database target is Neon/PostgreSQL.

## Current sync gap

Before this workspace package, the repository did not contain a single coordination folder for shared task context, decisions, handoffs, and verification evidence.

## Operating target

Use one repeatable workflow:

1. Scope one task.
2. Write or update the task in `TASKS.md`.
3. Generate one handoff brief.
4. Assign exactly one writer for the branch.
5. Require implementation notes and verification evidence.
6. Record final decisions and remaining risks.

## Quality gates

Use the applicable gates for each task:

- backend tests
- frontend build
- local smoke checks
- deployment verification when applicable
- no secrets changed
- no unrelated files changed
- rollback plan included

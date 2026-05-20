# Rico AI Coding Guardrails

This document defines safe operating rules for AI-assisted coding sessions.

Primary reference issue:
- GitHub Issue #147

## Goals

- Prevent architecture drift.
- Prevent accidental path or entrypoint changes.
- Keep Rico safety defaults intact.
- Keep GitHub and Asana aligned.
- Reduce random refactors from vibe-coding tools.

## Canonical FastAPI entrypoint

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Do not migrate production back to `src.rico_server:app`.

## Existing architecture must be reused

Before creating new files or services, check:

```text
src/api/app.py
src/api/routers/rico_chat.py
src/rico_agent.py
src/rico_openai_agent.py
src/rico_tool_registry.py
src/rico_safety.py
src/rico_db.py
src/cv_parser.py
```

## AI coding workflow

Before editing code:

1. Read GitHub Issue #147.
2. Read this document.
3. Read the target module fully.
4. Confirm whether functionality already exists.
5. Reuse existing routers/services when possible.
6. Avoid moving files or renaming modules.
7. Avoid silent architecture rewrites.
8. Keep PRs scoped to one engineering task.

## Required PR linkage

Every PR should:

- Reference Issue #147.
- Reference an Asana task.
- Explain public endpoint changes.
- Mention smoke tests executed.

## GitHub ↔ Asana sync

Workflow file:

```text
.github/workflows/rico-asana-sync.yml
```

Sync script:

```text
scripts/sync_asana_from_github.py
```

Behavior:

- Extracts Asana task IDs/URLs from PRs/issues/comments.
- Posts GitHub activity into linked Asana tasks.
- Skips safely when `ASANA_ACCESS_TOKEN` is not configured.

## Required GitHub secret

Add repository secret:

```text
ASANA_ACCESS_TOKEN
```

Recommended permissions:

- comment on tasks
- read workspace/project/task metadata

## Suggested PR body snippet

```text
Asana task:
https://app.asana.com/.../task/1234567890
```

or:

```text
asana_task: 1234567890
```

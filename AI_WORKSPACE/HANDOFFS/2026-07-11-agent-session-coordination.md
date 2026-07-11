# Handoff — Multi-session agent coordination

Date: 2026-07-11
Type: docs-only governance/continuity correction
Runtime impact: none

## Why this exists

The repository already had `START_HERE.md`, `PROJECT_STATUS.md`, `TASKS.md`, `AGENT_OPERATING_MODEL.md`, `AGENTS.md`, `CLAUDE.md`, and `.windsurfrules`, but the live project state had drifted across them. Multiple Claude sessions and Windsurf could therefore resume different historical tracks and create parallel work.

This handoff restores one cold-start path and one execution lock.

## Verified live state at the time of this handoff

- `main`: `9ceb87b1b6b4e112ffb5940b167408e8ef0cb16e`
- latest main commit: `docs(workspace): sync onboarding and auth-guard status (#964)`
- only active runtime PR: `#969`
- active branch: `feat/user-documents-dedup`
- active head: `4a0cf6cce3ef797a65f0b73a1259ccbefa12b1c6`
- active objective: issue `#960`, exact CV/document duplicate protection and atomic idempotency
- next objective after merge/migration/deploy verification: `#963`, onboarding CV persistence and profile hydration

## Binding execution order

```text
#969 review + CI
  -> owner merge approval
  -> migration 037 apply with Neon safety gate
  -> deploy/upload smoke
  -> #963 from updated main
  -> onboarding persistence + profile hydration
  -> authenticated owner smoke
  -> onboarding VERIFIED
  -> resume workspace/design work
```

## Work held

- `#967` pre-launch gate/waitlist: held; separate track and migration-number collision.
- `#965` journey-state seed: held draft; no follow-on without owner DEC.
- `#968` governance record for `#965`: held; does not authorize more agentic work.
- `#961` autonomous loop: frozen reference, not for merge.
- `#935`, `#872`, `#873`: historical/reference only.

## Migration collision

Both `#969` and `#967` currently claim migration number `037`.

- `#969`: `037_user_documents_content_hash.sql`
- `#967`: `037_create_waitlist.sql`

`#969` is first in the execution order. `#967` must later rebase and take the next free migration number before any review/merge resumes.

## Session roles

Every session must declare exactly one role:

- **WRITER** — one session only, one branch only.
- **REVIEWER** — read-only review and evidence.
- **RELEASE** — CI/deploy/status verification only.
- **IDLE** — no work.

Current safe allocation:

- the session already driving `feat/user-documents-dedup` is the only WRITER for `#969`;
- other Claude sessions are REVIEWER or IDLE;
- Windsurf is read-only/local verification or IDLE unless branch ownership is explicitly handed over;
- Codex is review-only;
- Lovable/design agents are prototype/reference-only.

## Files updated by this coordination PR

- `AI_WORKSPACE/PROJECT_STATUS.md`
- `AI_WORKSPACE/START_HERE.md`
- `AGENTS.md`
- `.windsurfrules`
- this handoff

No application code, migrations, tests, CI, environment configuration, or production data is changed.

## Cold-start instruction for any agent

```text
Rico mode.
Read AI_WORKSPACE/PROJECT_STATUS.md first, then START_HERE.md, live GitHub main/open PRs,
the active TASKS.md continuity block, and this handoff.
Declare WRITER, REVIEWER, RELEASE, or IDLE before acting.
Do not create parallel work when an active PR already exists.
```

## Next exact action

Independently review PR `#969` at exact head `4a0cf6cce3ef797a65f0b73a1259ccbefa12b1c6`.

Review only:

- changed-file scope;
- migration drift registration;
- unique-index and concurrent conflict behavior;
- dedupe-before-quota ordering;
- primary-CV invariants;
- focused and required CI;
- rollback.

Do not merge, apply migration, start `#963`, or open a new runtime branch.

## Rollback

Revert this docs-only PR. No runtime or data rollback is required.

# Handoff — Multi-session agent coordination

Date: 2026-07-11
Type: docs-only governance/continuity correction
Runtime impact: none

## Why this exists

The repository already had `START_HERE.md`, `PROJECT_STATUS.md`, `TASKS.md`, `AGENT_OPERATING_MODEL.md`, `AGENTS.md`, `CLAUDE.md`, and `.windsurfrules`, but the live project state had drifted across them. Multiple Claude sessions and Windsurf could therefore resume different historical tracks and create parallel work.

This handoff restores one cold-start path and one execution lock.

## Verified live state at the time of this handoff

- `main`: `50f73f04ecf078ae5993c2f805e5ea89351360d6`
- latest main commit: `docs(workspace): coordination handoff + agent rules update (#971)`
- only active runtime PR: `#969`
- active branch: `feat/user-documents-dedup`
- active head: `fdccbe5b2b39ea26d023b4efa228b91f21e8ed5e` (reviewed `960f2d4` merged with `origin/main`)
- active objective: issue `#960`, exact CV/document duplicate protection and atomic idempotency
- migration 037: applied to production Neon (2026-07-11 03:26:00–03:26:29 UTC); STEP 0 violations = 0; `user_documents` count remained 12
- next objective after merge/migration/deploy verification: `#963`, onboarding CV persistence and profile hydration

## Binding execution order

```text
#969 independently reviewed READY + migration 037 applied to Neon
  -> final required CI green
  -> owner merge approval
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

Run and verify required CI for PR `#969` at `fdccbe5b2b39ea26d023b4efa228b91f21e8ed5e` (pytest, frontend, playwright, postgres-integration, Vercel). Mark the PR ready for review once all checks are green.

Do not merge, deploy, start `#963`, or open a new runtime branch.

## Rollback

Revert this docs-only PR. Migration 037 has been applied to production Neon and is additive/unique-index only; no application rows were changed. A code rollback does not require a database rollback.

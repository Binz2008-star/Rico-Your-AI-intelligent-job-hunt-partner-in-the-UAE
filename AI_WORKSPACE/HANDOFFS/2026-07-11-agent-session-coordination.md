# Handoff — Multi-session agent coordination

Date: 2026-07-11 (updated after release smoke)
Type: docs-only governance/continuity correction
Runtime impact: none

## Why this exists

The repository already had `START_HERE.md`, `PROJECT_STATUS.md`, `TASKS.md`, `AGENT_OPERATING_MODEL.md`, `AGENTS.md`, `CLAUDE.md`, and `.windsurfrules`, but the live project state had drifted across them. Multiple Claude sessions and Windsurf could therefore resume different historical tracks and create parallel work.

This handoff restores one cold-start path and one execution lock and records the PR #969 production smoke verification results.

## Verified live state at the time of this handoff

- `main`: `e98fd59896bec492d770a09b0f6c2d03ad5e2f33`
- latest main commit: `feat(files): exact CV/document duplicate protection + atomic idempotency (#960) (#969)`
- only active runtime PR: `#969` (merged, deployed, and smoke-verified)
- active branch: `main`
- active head: `e98fd59896bec492d770a09b0f6c2d03ad5e2f33`
- active objective: issue `#963`, onboarding CV persistence and profile hydration
- migration 037: applied to production Neon (2026-07-11 03:26:00–03:26:29 UTC); STEP 0 violations = 0; `user_documents` count remained 12
- next objective after merge/migration/deploy verification: `#963`, onboarding CV persistence and profile hydration
- production smoke: exact-byte dedupe smoke passed with synthetic `other` PDF; counts and quota restored to baseline

## Binding execution order

```text
#969 independently reviewed READY + migration 037 applied to Neon
  -> final required CI green
  -> owner merge approval
  -> deploy/upload smoke [DONE]
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

PR #969 production verification PASS.

- merged SHA: e98fd59896bec492d770a09b0f6c2d03ad5e2f33
- deployed Render SHA: e98fd59896bec492d770a09b0f6c2d03ad5e2f33
- Render /health: HTTP 200 status=ok
- Vercel /proxy/health: HTTP 200 status=ok
- exact-byte dedupe smoke: first upload duplicate=false; second upload duplicate=true; same id (0cb0b1d1-0037-408e-823f-c7eccb337582) and filename (rico-969-smoke-20260711040844.pdf)
- document count: stored 4 -> 5 -> 5 -> 4 (baseline restored)
- quota: other_documents 0 -> 1 -> 1 -> 0 (baseline restored)
- primary CV invariant: 1 primary (profile-cv, legacy); synthetic not primary
- cleanup: synthetic document deleted; baseline restored
- next active track: #963 (do not start in this session)

## Rollback

Revert this docs-only PR. The smoke test created and deleted one synthetic `other` document; the account has returned to baseline. Migration 037 remains applied to production Neon and is additive/unique-index only. A code rollback does not require a database rollback.

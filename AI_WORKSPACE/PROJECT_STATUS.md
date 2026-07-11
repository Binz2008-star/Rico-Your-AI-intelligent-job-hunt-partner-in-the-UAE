# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, or other agent must read this file before planning or writing.**
>
> This file is intentionally short. It answers: what is active, who may write, what is blocked, and the next exact action. Live GitHub `main`, open PR state, CI, and deployed `/version` override stale prose anywhere else.

## Verified repository snapshot

| Field | Current value |
| --- | --- |
| **Current repository `main` head** | `241b85d4c5d74b6afd00f0d4e202e75c4f5a3f8b` (squash merge of PR `#975` / issue `#963`). |
| **Frontend deployment** | Vercel production deployment for `241b85d…` is `READY` and aliased to `ricohunt.com`. |
| **Backend deployment / authenticated smoke** | Not yet verified for `241b85d…`; do not claim the onboarding release is production-verified until Render version/migration 038 and the authenticated smoke pass are recorded. |
| **Coordination control plane** | PR `#970` merged; `PROJECT_STATUS.md` + `START_HERE.md` + root agent rules are now the mandatory cold-start path. |
| **Current execution phase** | Release verification for merged `#963`; no active implementation PR. |
| **Single active runtime objective** | Verify the merged onboarding CV persistence release before opening another runtime/design objective. |
| **Active PR branch/head** | None — `#975` merged as `241b85d…`. |
| **Next exact action** | Confirm Render serves `241b85d…`, migration 038 succeeds, then run authenticated onboarding CV → My Files → logout/login smoke. |
| **Owner gate after #963** | Record the authenticated production smoke; only then mark onboarding `VERIFIED` and release the design/workspace queue. |
| **Last updated** | 2026-07-11 (post-#975 merge; Vercel READY, backend smoke pending) |

## Execution lock

```text
ACTIVE NOW
Release verification for #963 / merged PR #975 (`241b85d…`).
No implementation writer is active.

NEXT, AFTER VERIFIED RELEASE
#962 — safe login return path; then the approved per-route design migration.

LATER
remaining auth-guard routes
workspace/dashboard migration
command i18n / command redesign

PAUSED / HOLD
#967 — pre-launch gate / waitlist
#965 — journey-state agentic seed
#968 — docs record for #965

REFERENCE ONLY / NOT FOR MERGE
#961 — autonomous AI loop
#935 — old command proposal
#872 — old Nocturne design-gallery prototype
#873 — old Rico Alive design-gallery prototype
```

`#969` is complete and production-smoke verified. `#963` is merged, CI-green, and Vercel-ready, but is not yet production-verified: Render migration/deploy and authenticated smoke remain the execution lock. Do not open a second runtime objective before that release gate is resolved.

## Mandatory multi-session coordination

There may be several Claude sessions plus Windsurf open at the same time. They do **not** each receive a separate implementation task automatically.

Before making any write:

1. Read this file, `START_HERE.md`, and the relevant task/PR.
2. Fetch live `main` and open PR state; do not trust chat summaries.
3. Check whether an active PR already exists for the objective.
4. Declare exactly one role:
   - **WRITER** — the only session allowed to push to the active branch.
   - **REVIEWER** — read-only diff/tests/comments; no branch writes.
   - **RELEASE** — CI/deploy/status verification only; no product code.
   - **IDLE** — stop and wait.
5. If another session is already the WRITER, do not create a competing branch or implementation.
6. One writer per branch. Never let Claude and Windsurf edit the same branch concurrently.

### Current safe allocation

| Agent/session | Allowed role now |
| --- | --- |
| Release session | **RELEASE only** for #963: verify Render version/migration and authenticated smoke; no product-code write |
| Other Claude sessions | **REVIEWER or IDLE** |
| Windsurf | Local/read-only verification or **IDLE**; no write to the `#963` branch unless explicitly handed ownership |
| Codex | Review signal only |
| Lovable/design agents | Prototype/reference only; no production implementation |

## Binding sequence

```text
#969 independently reviewed READY + migration 037 applied to Neon
  -> final required CI green
  -> owner approves merge
  -> deploy and smoke the canonical file-upload path [DONE]
  -> #963 merged as #975 (`241b85d…`); PR CI green and Vercel READY
  -> verify Render version + migration 038
  -> authenticated owner smoke
  -> onboarding PARTIAL becomes VERIFIED
  -> resume workspace/design migration
```

Do not reorder this sequence.

## Critical blocker: migration-number collision

Two open drafts currently claim migration number `037`:

- `#969`: `037_user_documents_content_hash.sql`
- `#967`: `037_create_waitlist.sql`

Therefore `#967` is blocked. When it resumes, it must rebase from current `main`, use the next free migration number, rerun drift checks, and remain inactive until separately approved. Do not merge or activate the pre-launch gate now.

## Current open PR classification

| PR | Track | Decision |
| ---: | --- | --- |
| `#969` | CV/file persistence foundation | **Completed, merged, deployed, and production-smoke verified**; migration 037 applied to production Neon |
| `#963` / merged `#975` | Onboarding CV persistence + profile hydration | **Merged, CI-green, Vercel READY**; backend deployment and authenticated smoke remain before `VERIFIED` |
| `#968` | Workspace governance for `#965` | Hold; docs-only, not permission for more agentic work |
| `#967` | Pre-launch gate/waitlist | Hold; blocked by separate scope and migration collision |
| `#965` | Read-only journey-state seed | Hold draft; no follow-on without owner DEC |
| `#961` | Autonomous loop | Frozen reference; not for merge |
| `#935` | Deferred command proposal | Stale/reference; no implementation |
| `#872` | Nocturne gallery prototype | Historical design reference |
| `#873` | Rico Alive gallery prototype | Historical design reference |

## What is already true

- `/onboarding` is restored as the real authenticated first-run route.
- `/settings` and `/profile` have the shared authenticated-page guard.
- Onboarding production smoke is **PARTIAL**: registration/verification, routing, steps, skip, and CV parsing/review passed.
- The merged #963 path uses server-side upload artifacts, hash-aware My Files persistence, required durable profile hydration, and retry-safe confirmation.
- The remaining onboarding gate is release verification, not known implementation work.
- The approved design package is sufficiently complete; design work resumes only after the release gate.

## #963 implementation status

- PR #975 was merged as `241b85d…` after final-head CI passed (`pytest`, frontend, Playwright, real-Postgres integration).
- Authenticated confirmation rejects missing/expired/foreign upload artifacts, writes My Files through the canonical hash-aware path, requires the Neon profile write, and never marks onboarding complete after either persistence failure.
- Retry is idempotent. The remaining proof is authenticated production smoke on the deployed backend.

## Stop conditions

Stop and ask the owner instead of continuing when:

- live GitHub state conflicts with this file;
- another writer already owns the branch/task;
- the requested work is not `#963` (or its direct design/audit gate) once that track is opened;
- a task requires Neon mutation, production smoke, merge, deploy, billing, auth, or infrastructure approval;
- the active PR expands beyond its stated objective;
- an agent approaches a context/token/tool limit without updating the task continuity block and handoff.

## Next exact action

```text
1. Confirm Render `/version` serves `241b85d…` and startup logs show migration 038 succeeded.
2. Run the authenticated onboarding flow: upload CV → confirm profile → verify My Files → logout/login → confirm persisted profile/onboarding state.
3. Record PASS/FAIL. On PASS, mark onboarding `VERIFIED` and select the next single objective.
```

PR #969 production verification: PASS (recorded for reference).

```text
- merged / deployed application SHA: e98fd59896bec492d770a09b0f6c2d03ad5e2f33
- Render /health: HTTP 200 status=ok
- Vercel /proxy/health: HTTP 200 status=ok
- exact-byte dedupe smoke: first upload duplicate=false; second upload duplicate=true; same id (0cb0b1d1-0037-408e-823f-c7eccb337582) and filename (rico-969-smoke-20260711040844.pdf)
- document count: stored 4 -> 5 -> 5 -> 4 (baseline restored)
- quota: other_documents 0 -> 1 -> 1 -> 0 (baseline restored)
- primary CV invariant: 1 primary (profile-cv, legacy); synthetic not primary
- cleanup: synthetic document deleted; baseline restored
- next implementation objective: #963
```

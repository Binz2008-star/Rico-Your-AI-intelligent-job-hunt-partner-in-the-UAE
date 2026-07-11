# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, or other agent must read this file before planning or writing.**
>
> This file is intentionally short. It answers: what is active, who may write, what is blocked, and the next exact action. Live GitHub `main`, open PR state, CI, and deployed `/version` override stale prose anywhere else.

## Verified repository snapshot

| Field | Current value |
| --- | --- |
| **Current repository `main` head** | `c51837ce81337ecf1caf766011eaba429d8e64cc` (`origin/main`). The two commits after the `#969` merge (`1454477…`, `c51837c…`) are generated `docs/index.html` dashboard build output only — no application runtime change. |
| **Last runtime / deployed application SHA** | `e98fd59896bec492d770a09b0f6c2d03ad5e2f33` (`#969`). This is the live application code SHA deployed to Render/Vercel; the later `main` commits are dashboard output and do not change deployed behavior. |
| **Coordination control plane** | PR `#970` merged; `PROJECT_STATUS.md` + `START_HERE.md` + root agent rules are now the mandatory cold-start path. |
| **Current execution phase** | `#969` completed, merged, deployed, and production-smoke verified. No active runtime PR currently exists. `#963` is the next implementation objective. |
| **Single active runtime objective** | None in flight. `#963` (onboarding CV persistence + profile hydration) is the next implementation objective, not yet started. |
| **Active PR branch/head** | None — `#969` is merged. `#963` starts on a fresh branch from updated `main`. |
| **Next runtime objective** | `#963` — persist confirmed onboarding CV and hydrate extracted profile fields |
| **Owner gate after #963** | Authenticated production smoke; only then mark onboarding `VERIFIED` |
| **Last updated** | 2026-07-11 (post-#969 release; docs merge PR #972) |

## Execution lock

```text
ACTIVE NOW
(none — #969 is complete, merged, deployed, and production-smoke verified;
no active runtime PR currently exists)

NEXT, NOT STARTED
#963 — onboarding CV persistence + profile hydration
(start in a fresh #963 branch from updated `main`)

LATER
#962 — safe login return path
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

`#969` is complete, merged, deployed, and production-smoke verified; no active runtime PR currently exists. `#963` is the next implementation objective and must start on a fresh branch from updated `main` after the `#963` design/audit gate. Do not open a second concurrent runtime objective without an owner change to this lock.

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
| Next writer session (when `#963` opens) | **WRITER for #963 only**, on a fresh branch from updated `main`, after the `#963` design/audit gate |
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
  -> start #963 on a fresh branch from updated main
  -> persist onboarding CV + hydrate profile
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
| `#963` | Onboarding CV persistence + profile hydration | **Next active implementation track**; start on a fresh branch from updated `main` after the `#963` design/audit gate |
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
- The remaining onboarding gap is persistence: the confirmed CV is not yet saved through the canonical My Files path and extracted profile fields are not fully hydrated.
- The approved design package is sufficiently complete; design work is not the current blocker.

## #963 completeness blocker (verified)

- `POST /api/v1/rico/confirm-cv-profile` currently calls the legacy `save_user_document(...)` path (`src/api/routers/rico_chat.py` → `src/rico_db.py`).
- That call does **not** participate in the canonical content-hash get-or-create path (`get_or_create_user_document`) shipped with `#969`.
- Onboarding must **not** be wired to that endpoint unchanged.
- `#963` must first make confirmation persistence **hash-aware and idempotent**, shared by onboarding and the existing command confirmation behavior, before any onboarding persistence work builds on it.

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
1. Merge PR #972 (docs-only: PROJECT_STATUS.md + coordination handoff) using Squash and merge.
2. Create a fresh #963 branch from updated `main` (feat/963-onboarding-cv-persistence).
3. Perform the #963 design/audit gate (read-only implementation audit) before writing any code.
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

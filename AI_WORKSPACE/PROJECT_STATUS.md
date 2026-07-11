# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, or other agent must read this file before planning or writing.**
>
> This file is intentionally short. It answers: what is active, who may write, what is blocked, and the next exact action. Live GitHub `main`, open PR state, CI, and deployed `/version` override stale prose anywhere else.

## Verified repository snapshot

| Field | Current value |
| --- | --- |
| **Main SHA** | `9ceb87b1b6b4e112ffb5940b167408e8ef0cb16e` — `docs(workspace): sync onboarding and auth-guard status (#964)` |
| **Current execution phase** | Onboarding persistence hardening before further workspace/design rollout |
| **Single active runtime objective** | Exact CV/document duplicate protection and atomic idempotency: issue `#960`, draft PR `#969` |
| **Active PR branch/head** | `feat/user-documents-dedup` @ `4a0cf6cce3ef797a65f0b73a1259ccbefa12b1c6` |
| **Next runtime objective** | `#963` — persist confirmed onboarding CV and hydrate extracted profile fields |
| **Owner gate after #963** | Authenticated production smoke; only then mark onboarding `VERIFIED` |
| **Last updated** | 2026-07-11 |

## Execution lock

```text
ACTIVE NOW
#969 / #960 — exact CV/document dedupe + atomic idempotency

NEXT, NOT STARTED
#963 — onboarding CV persistence + profile hydration

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

No agent may start a second runtime objective while `#969` is active unless the owner explicitly changes this lock.

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
| Session already driving `feat/user-documents-dedup` | **WRITER for #969 only** |
| Other Claude sessions | **REVIEWER or IDLE** |
| Windsurf | Local/read-only verification or **IDLE**; no write to `feat/user-documents-dedup` unless explicitly handed ownership |
| Codex | Review signal only |
| Lovable/design agents | Prototype/reference only; no production implementation |

## Binding sequence

```text
#969 reviewed + CI green
  -> owner approves merge
  -> apply migration 037 safely to Neon
  -> deploy and smoke the canonical file-upload path
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
| `#969` | CV/file persistence foundation | **Only active implementation PR**; keep draft until review and required CI are complete |
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

## Stop conditions

Stop and ask the owner instead of continuing when:

- live GitHub state conflicts with this file;
- another writer already owns the branch/task;
- the requested work is not `#969` or its direct review/verification;
- a task requires Neon mutation, production smoke, merge, deploy, billing, auth, or infrastructure approval;
- the active PR expands beyond its stated objective;
- an agent approaches a context/token/tool limit without updating the task continuity block and handoff.

## Next exact action

```text
Independently review PR #969 at exact head
4a0cf6cce3ef797a65f0b73a1259ccbefa12b1c6.

Verify scope, migration drift registration, atomic conflict behavior,
quota ordering, primary-CV invariants, changed files, required CI, and rollback.
Do not merge, apply migration, start #963, or open new runtime work.
```

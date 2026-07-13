# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, or other agent must read this file before planning or writing.**
>
> This file is intentionally short. It answers: what is active, who may write, what is blocked, and the next exact action. Live GitHub `main`, open PR state, CI, and deployed `/version` override stale prose anywhere else.

## Verified repository snapshot

| Field | Current value |
| --- | --- |
| **Current repository `main` head** | `60978aec00778d5b3aabd926ccfd2f9fc345eaab` (`#982` gating-invariant test). Runtime application state is `#962` / `c7aea42…`; `#982` after it is a backend test-only change with no runtime effect. |
| **Frontend deployment** | Vercel production for the latest `main` is `READY` and aliased to `ricohunt.com`. |
| **Backend deployment / authenticated smoke** | Render `/version` serves the `#963` release and `/health` is OK. Migration 038 and the authenticated onboarding smoke are **owner-confirmed PASS (2026-07-11)**; the onboarding release is production-verified. |
| **Coordination control plane** | PR `#970` merged; `PROJECT_STATUS.md` + `START_HERE.md` + root agent rules are the mandatory cold-start path. Docs reconciled after #963 via #979; CI render-audit fix via #974; #963 VERIFIED via #980; login return-path #962 via #981; gating-invariant test via #982. |
| **Current execution phase** | `#963` **VERIFIED** and `#962` merged. No active implementation PR. Next objective not yet selected (per-route design migration or remaining auth-guard routes). |
| **Single active runtime objective** | None in flight. Next candidate: the approved per-route design migration, or the remaining auth-guard routes — owner selects one. |
| **Active PR branch/head** | None — `#981` (#962) and `#982` (gating test) merged. |
| **Next exact action** | Owner selects the next single objective (per-route design migration or remaining auth-guard routes); start it on a fresh branch from updated `main` after its design/audit gate. |
| **Owner gate after #963** | Cleared — authenticated production smoke owner-confirmed PASS; the design/workspace queue is released. |
| **Last updated** | 2026-07-11 (post-#962 + #982 merge; `main` at `60978ae…`). |

## Owner-approved side track: Paddle billing migration (2026-07-13)

`billing` is a listed stop condition below — this track is opened on
explicit, direct owner approval given in-session (owner supplied Paddle API
keys and requested the integration; confirmed scope: full replace of Stripe,
not dual-provider; self-service portal explicitly deferred). It does **not**
change or supersede the queued objective above (per-route design migration /
auth-guard routes remain owner-selectable as before) — this is a separate,
explicitly authorized concurrent track, not a silent reinterpretation of the
lock.

- Branch: `claude/paddle-connector-issue-smjnbt` (WRITER: this session).
- Full detail: `AI_WORKSPACE/HANDOFFS/2026-07-13-paddle-billing-migration.md`.
- Status: implementation + tests complete on the branch; not yet PR'd/merged;
  not production-verified (no live Paddle account yet — `BILLING_MODE`
  defaults to `manual` so production behavior is unchanged until the owner
  configures real Paddle credentials on Render/Vercel).

## Execution lock

```text
ACTIVE NOW
(none — #963 VERIFIED and #962 merged. No implementation writer is active.)

NEXT, NOT STARTED
(owner selects one) the approved per-route design migration,
or the remaining auth-guard routes.
Start on a fresh branch from updated `main`, after its design/audit gate.

LATER
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

`#969` and `#963` are both complete and production-verified (owner-confirmed authenticated smoke, 2026-07-11). `#962` (safe login return path) is merged. No runtime objective is in flight. The next objective (per-route design migration or remaining auth-guard routes) is owner-selected and must start on a fresh branch from updated `main` after its design/audit gate. Do not open a second concurrent runtime objective without an owner change to this lock.

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
  -> Render `/version` confirmed `241b85d…`; verify migration 038 schema
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
| `#963` / merged `#975` | Onboarding CV persistence + profile hydration | **Merged, deployed, and production-verified** (owner-confirmed authenticated smoke, 2026-07-11); onboarding out of PARTIAL |
| `#962` / merged `#981` | Safe login return path (`next`) | **Merged** (`c7aea42…`); login honors a validated internal `next` via `resolveNextPath`; onboarding keeps priority; no open-redirect |
| `#982` | Subscription gating identity-key invariant | **Merged** (test-only); pins that plan gating keys on the account email |
| `#968` | Workspace governance for `#965` | Hold; docs-only, not permission for more agentic work |
| `#967` | Pre-launch gate/waitlist | Hold; blocked by separate scope and migration collision |
| `#965` | Read-only journey-state seed | Hold draft; no follow-on without owner DEC |
| `#961` | Autonomous loop | Frozen reference; not for merge |
| `#935` | Deferred command proposal | Stale/reference; no implementation |
| `#872` | Nocturne gallery prototype | Historical design reference |
| `#873` | Rico Alive gallery prototype | Historical design reference |

## What is already true

- `/onboarding` is restored as the real authenticated first-run route.
- `/settings` and `/profile` have the shared authenticated-page guard, and login now returns a guest to a validated `next` after authenticating (#962).
- Onboarding production smoke is **VERIFIED** (owner-confirmed, 2026-07-11): registration/verification, routing, steps, skip, CV parsing/review, and now confirmed-CV persistence + profile hydration all passed.
- The merged #963 path uses server-side upload artifacts, hash-aware My Files persistence, required durable profile hydration, and retry-safe confirmation.
- The onboarding release gate is cleared; the design/workspace queue is released.

## #963 implementation status

- PR #975 was merged as `241b85d…` after final-head CI passed (`pytest`, frontend, Playwright, real-Postgres integration).
- Authenticated confirmation rejects missing/expired/foreign upload artifacts, writes My Files through the canonical hash-aware path, requires the Neon profile write, and never marks onboarding complete after either persistence failure.
- Retry is idempotent. Authenticated production smoke is **owner-confirmed PASS (2026-07-11)**; the release is VERIFIED.

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
1. #963 VERIFIED (owner-confirmed smoke) and #962 (safe login return path)
   merged as #981. Gating identity-key invariant locked by test #982.
2. Owner selects the next single objective: the approved per-route design
   migration, or the remaining auth-guard routes. Start on a fresh branch
   from updated `main` after its design/audit gate.
3. Do not open a second concurrent runtime objective without an owner lock change.
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

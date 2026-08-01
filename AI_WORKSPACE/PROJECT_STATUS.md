# Project Status — Rico AI

> **Mandatory control panel.** Every agent must read this file before planning or writing.
>
> Live GitHub, exact PR heads, deployment/endpoint evidence, Neon state, and production-smoke evidence override prose. Reconcile this file before implementation when they disagree.

## Document contract

- **Why it exists:** one current, evidence-backed operating snapshot for Rico.
- **Update when:** production, active ownership, launch blockers, or priority order changes materially.
- **Source of truth:** this file for current control state; `DECISIONS.md` for binding decisions; `TASKS.md` for lane history; `ENGINEERING_ROADMAP.md` for forward sequence; `ARCHITECTURE.md` for structural rules.
- **Owner:** Rico owner, with the acting CTO/session responsible for evidence-backed reconciliation.
- **History:** prior snapshots remain in Git history; this file carries current truth.
- **SHA rule:** fetch `main` live. A SHA below is a verified snapshot, not a permanent future claim.

## Rule of authority

1. GitHub `main`, exact PR heads, and deployed `/version` evidence.
2. This file.
3. Lane continuity in `TASKS.md`.
4. The latest dated handoff.
5. Everything else.

A green deployment badge is not a product smoke. A merged runtime change is not proof that its changed path was exercised. An issue specification is not an implementation.

## Current reconciliation — 2026-08-01

Evidence cut: 2026-08-01T03:35:38Z (07:35 GST). GitHub, the public production endpoints, and the repository checkout were read during this pass. No database, secret, environment, merge, deployment, or authenticated-user mutation was performed.

### Verified repository and delivery state

| Item | Verified state |
| --- | --- |
| `main` | `9f5dccfa4d9a5eca6c7c4ecae7c28921da95059b`; fetched from `refs/heads/main` immediately before the L7 branch was created |
| Production backend | `/version` HTTP 200; `commit=9f5dccfa4d9a5eca6c7c4ecae7c28921da95059b`; `commit_verified=true`; `commit_source=RAILWAY_GIT_COMMIT_SHA`; `environment=production` |
| Backend health | `/health` HTTP 200 / `status=ok`; JSearch configured and non-degraded; DeepSeek configured; model precheck reachable with two available models; fallback exists and is available |
| Frontend proxy | `https://ricohunt.com/proxy/health` HTTP 200 / `status=ok` |
| Public frontend | `https://ricohunt.com/` reachable and serving the current Rico public experience |
| Commit deployment statuses | Vercel success and two Railway service statuses success on `main@9f5dccfa` |
| Open pull requests | Exactly one: `#1477`, Draft, unmerged |
| Closed stale docs PR | `#1475` closed without merge at head `baaaae90abbf55105c8258905b7bceb0cdd5bc67` |
| AI quality program | `#1479` open Epic; `#1480` open PR1 specification; no implementation PR exists for `#1480` |
| L7 reconciliation | Authorized branch `agent/control-plane-reconcile-20260801` from exact `main@9f5dccfa`; Draft PR only; merge and deployment forbidden by directive `RICO-20260801-L7-RECONCILE` |

### Production proof boundary

The endpoint reads prove that the backend is healthy and serves the exact current `main` commit. They do **not** prove the user-visible behavior of every change in that tree.

Proven in this pass:

- exact backend production commit identity;
- public backend and frontend-proxy health;
- public landing-page reachability;
- deployment status success attached to the exact `main` commit;
- DeepSeek configuration, model-list precheck reachability, and fallback availability.

Not proven in this pass:

- authenticated end-to-end product behavior;
- DeepSeek streaming or non-streaming response quality;
- a real primary failure invoking fallback exactly once;
- `PendingJobSearch` consume behavior in production;
- the Career Profile read contract in production;
- external-draft identity containment or provenance behavior;
- the new Settings warning presentation on real mobile, light/dark, and Arabic surfaces.

`/health.reasoning_provider.models_precheck.reachable=true` is a model-list precheck, not a completed chat smoke. `reachable=null` and empty last-attempt fields mean no current response-path success may be inferred from that health read.

## Current open PR — `#1477`

| Field | Verified state |
| --- | --- |
| Title | `fix(ai): prevent unconfirmed identity in external drafts` |
| Branch | `fix/external-draft-identity-guard` |
| Actual head | `4ac56805a0f5cb0ec2a3449db17ac7ee06fb3529` |
| Merge base | `3bcac4d5d418b3711b71976733b4baf3d6876570` |
| State | Open, Draft, unmerged, GitHub reports mergeable |
| Relation to current `main` | Diverged: the branch carries its own nine commits and is missing the one current-main commit `9f5dccfa` |
| Changed files | Five: shared AI identity contract, two focused test files, required QA enrollment, and its own handoff |
| Exact-head checks | QA Tests, Test Enumeration Guard, Workflow Security Guards, Log Privacy Ratchet, branch lifecycle workflow, and Vercel all succeeded on `4ac56805` |
| Review | Independent review recorded `PASS WITH LIMITS` at exact head `4ac56805`; no merge or deployment recommendation |
| Overlap with L7 | None: `#1477` does not change `PROJECT_STATUS.md`, `TASKS.md`, or this L7 handoff |

`#1477` is **not Ready**. Before any Ready or merge decision, its owner must:

1. synchronize it with `main@9f5dccfa` without expanding scope;
2. update the stale PR-body and handoff refs (`3bcac4d5` / `3a5a73b9` do not describe actual head `4ac56805`);
3. rerun exact-head CI after synchronization;
4. preserve the independent review boundary;
5. keep the PR Draft until an explicit owner merge authorization is issued.

The PR is prompt-contract containment. Its tests prove that the shared rule reaches the primary and Hugging Face paths; they do not prove model compliance or deterministic PII/provenance enforcement.

## Recent merged baseline now in production

| PR | Main commit | Delivered boundary | Production evidence boundary |
| ---: | --- | --- | --- |
| `#1464` | `41a95ad` | shared AI grounding and filename-evidence integrity | included in deployed tree; changed behavior not authenticated-smoked here |
| `#1468` | `a694dda` | retired Render workflows no longer block Railway delivery | workflow/configuration change; no product behavior claim |
| `#1469` | `07942d6` | never-apply company recorded as a safety constraint | included in deployed tree; behavior not authenticated-smoked here |
| `#1470` | `7056952` | platform-aware deployment commit identity | directly exercised by `/version.commit_verified=true` from `RAILWAY_GIT_COMMIT_SHA` |
| `#1472` | `1d00d46` | typed `PendingJobSearch` with atomic Postgres consume | included in deployed tree; consume interaction not production-smoked here |
| `#1474` | `afe272c` | RicoReply copy feedback and user-bubble wrapping hardening | Vercel status success; no manual browser smoke in this pass |
| `#1476` | `f5f5fd1` | typed read-only Career Profile foundation | included in deployed tree; read contract not production-smoked here |
| `#1478` | `3bcac4d` | explicit DeepSeek thinking-disabled request contract | included in deployed tree; chat/fallback behavior not production-smoked here |
| `#1471` | `9f5dccf` | palette-aware Settings guardrail warnings | exact current production tree; UI behavior not manually smoked here |

## Active program and next governed increments

### `#1479` — Rico AI Quality Flywheel

Open Epic. It owns the system-wide quality architecture: anonymized evaluations, deterministic provenance and PII metrics, retrieval/reranking measurement, safe prompt optimization, and privacy-bounded observability. It is not a model-swap authorization.

### `#1480` — evaluation foundation

Open specification, not an implementation PR. The first implementation must start from then-current `main` on a new non-overlapping branch and remain evaluation-only:

- anonymized Arabic/English golden cases;
- deterministic schema, routing, provenance, identity-egress, permission, language, and fallback metrics;
- machine-readable and human-readable reports;
- no required provider credentials for critical trust checks;
- no runtime prompt, provider, model, database, environment, or production dependency change;
- no reuse of the historical `claude/rico-hunt-evaluation-2ff5kf` branch.

DeepEval may be isolated and pinned only if repository-CI compatibility and supply-chain constraints are proven. DSPy, Presidio, retrieval models, and Langfuse remain later, separate decisions; none belongs in PR1 by default.

## Current work and ownership

| Work | Ownership and authorization |
| --- | --- |
| L7 control-plane reconciliation | `WRITER`, branch `agent/control-plane-reconcile-20260801`, base `9f5dccfa`, write `AUTHORIZED` by Roben under `RICO-20260801-L7-RECONCILE`; docs scope only |
| `#1477` containment | Existing foreign branch/PR; this L7 authorization grants no write, sync, Ready, merge, or deploy authority over it |
| `#1480` implementation | No branch, no PR, and no implementation write authorization in this L7 directive |
| Production/database work | No mutation authorization; Neon, secrets, environment, migrations, deployment, and authenticated production smoke are untouched |

GitHub cannot reveal unpushed work. The occupancy conclusion is therefore bounded: no overlapping open PR or remote target branch exists, and no active L7 lease was recorded before Roben issued this directive. It is not a claim that all other sessions are idle.

## Risks and unresolved gates

### High — external identity in content leaving Rico

`#1477` reduces risk through a shared prompt contract but is not a deterministic egress guard. The systemic follow-up must establish server-owned value, source, confirmation, conflict, and external-use state, followed by output validation.

### High — no unified evaluation gate yet

Prompt, provider, fallback, retrieval, and grounding changes still lack one Rico-owned regression baseline. `#1480` is the first safe treatment, not proof that the gap is already closed.

### Medium — production behavior evidence remains incomplete

Current deployment and health are proven. Authenticated behavior for the recent backend and AI changes is not. CI and health cannot substitute for a secret-safe product smoke.

### Medium — control documents decay quickly

This snapshot is intentionally current-state only. Every SHA and open-PR statement must be re-read live before reuse; replace stale current claims rather than stacking another snapshot under them.

### Medium — deployment instructions still name Render

Live `/version` and exact-main commit statuses prove that the current backend delivery is Railway, but root `CLAUDE.md` and the backend verification/rollback sections of `OPERATING_RULES.md` still instruct agents to verify and redeploy Render. `PROJECT_STATUS.md` outranks those stale platform-state claims, but the conflict remains an onboarding and release-safety risk. It is recorded here and must be corrected in a separate, explicitly scoped governance-doc PR; this L7 directive does not authorize expanding into those files.

### Medium — two historical task IDs remain duplicated

The base `TASKS.md` already contains two headings for `TASK-20260722-001` and two for `TASK-20260723-003`, in addition to the one deliberately frozen duplicate `TASK-20260721-005`. The current supervisor uniqueness gate does not exempt the first two and therefore cannot certify the unchanged base ledger. This PR introduces four new task headings and each is unique. Historical renumbering is withheld because it requires a separate reference audit rather than a blind in-place change.

## Governed execution order

1. Complete this L7 docs-only branch through focused validation, a Draft PR, exact-head CI, and independent review. No merge without a new explicit owner merge authorization.
2. On its separately owned branch, synchronize `#1477`, correct its refs, and rerun exact-head CI while keeping it Draft.
3. Start `#1480` only under a new attributed writer directive from then-current `main`; keep PR1 deterministic and evaluation-only.
4. Open a separate governance-doc correction for the stale Render instructions, grounded in Railway deployment evidence; do not mix it into runtime or evaluation work.
5. Audit references for the two pre-existing duplicate task IDs and repair them in a dedicated control-ledger PR before tightening the uniqueness gate.
6. After relevant merges and deployments, run the dedicated secret-safe authenticated smoke matrix and record behavior separately from deployment health.
7. Do not touch Neon, secrets, environment, provider selection, production data, or deployment from this reconciliation lane.

## Stop conditions

Stop and return to Roben if:

- `main` moves away from `9f5dccfa4d9a5eca6c7c4ecae7c28921da95059b` before this Draft PR is opened;
- another writer or overlapping branch appears for L7;
- the diff expands beyond `PROJECT_STATUS.md`, `TASKS.md`, and the single dated L7 verification handoff;
- any step would merge, deploy, mutate production/Neon, change an environment or secret, or edit runtime/test/workflow files;
- remote branch history differs from the expected head before a push.

## Next exact action

Validate the three-file L7 documentation diff, verify `main` and branch occupancy again, publish one controlled commit to `agent/control-plane-reconcile-20260801`, and open a Draft PR. Do not merge or deploy.

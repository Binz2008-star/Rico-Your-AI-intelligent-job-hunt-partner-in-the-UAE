# Project Status — Rico AI

> **Mandatory control panel.** Every agent must read this file before planning or writing.
>
> Live GitHub `main`, open PR heads, exact-head CI, deployed version evidence, and
> production smoke evidence override prose. When any conflict appears, stop and
> reconcile this file before starting new implementation work.

## Verified control snapshot

**Snapshot date:** 2026-07-25  
**Repository:** `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE`

| Field | Verified state |
| --- | --- |
| Live `main` | `97c5f6f62e863fb97ed0e08c9e88a7f57d167b67` |
| Latest merge | `#1372` — owner-only, read-only subscriber administration surface |
| Vercel production | `READY`, production deployment on `main` commit `97c5f6f` |
| GitHub deployment statuses on `main` | Vercel `success`; Railway service status `success` |
| Broader production smoke | **Not completed in this reconciliation.** Do not infer authenticated profile/chat/applications/billing/admin behavior from deployment status alone. |
| Governing strategy | `DEC-20260723-001`: trust and execution reliability before new feature expansion, unless a newer explicit owner decision supersedes it. No superseding decision was verified in this pass. |

## Current production truth

### Confirmed live

- The latest production frontend deployment is `READY` on `main` commit
  `97c5f6f`.
- The merged owner-only subscriber administration backend/UI from `#1372` is in
  `main`.
- `#1373` is merged: Applications board and `/queue` accessibility polish plus
  approval confirmation based on explicit persisted backend status.
- The provenance and trust track is materially advanced through merged PRs
  `#1364`, `#1365`, `#1366`, `#1367`, `#1368`, and `#1369`.

### Confirmed defect after `#1372`

The owner subscriber surface does not activate correctly in the browser:

```text
#1372 exposed is_owner on /api/v1/auth/me
The frontend reads the canonical /api/v1/me
Result: is_owner is absent, the Subscribers nav stays hidden,
and /admin/subscribers redirects to /dashboard
```

`#1375` is the focused fix. It adds the server-computed `is_owner` boolean to
`GET /api/v1/me` and does not change the owner authorization gate.

### Not verified in this reconciliation

- Authenticated end-to-end production smoke after `#1372`.
- Owner `/admin/subscribers` success, because `#1375` is not merged.
- Non-owner production rejection behavior after the eventual `#1375` deploy.
- Full CV upload, application lifecycle, Arabic/mobile, billing, or Gmail smoke.
- Current backend host/version response directly from production. GitHub reports
  a successful Railway deployment status, but this pass did not query the live
  backend `/version` endpoint.

## Open pull-request control

Seven PRs were verified open on 2026-07-25.

| PR | State | Current fact | Required action |
| ---: | --- | --- | --- |
| `#1376` | Draft, mergeable | Profile UX/accessibility polish; one focused frontend objective | Finish exact-head checks and owner review; no automatic merge |
| `#1375` | Draft, mergeable | Fixes the owner-surface activation defect on canonical `/api/v1/me`; focused tests and required GitHub workflows are green | **Highest priority:** review, merge only with authorization, deploy, then run owner/non-owner smoke |
| `#1374` | Draft, mergeable, docs-only | Competitive-differentiation gap-analysis proposal; no runtime code | Review as strategy documentation only; it does not authorize implementation |
| `#1371` | Draft, not mergeable | Mixed design references plus production polish; the production Applications/queue portion was extracted and merged through `#1373` | Do not merge as-is; split/retain reference-only material or close as superseded after review |
| `#1370` | Open, non-draft, mergeable | Public `/pricing` using current single-plan catalog; branch base predates current `main` | Rebase onto `97c5f6f`, rerun exact-head CI/smoke, then review |
| `#1362` | Draft, mergeable | Small `/command` starter-prompt category hints; branch base is old | Rebase and reassess priority under the trust-first gate |
| `#1359` | Open, non-draft, mergeable | Started as warning-contrast fix, later added workspace-wide theme persistence; mixed scope and old base | Split or record an explicit mixed-scope exception, rebase, then review |

An open PR is not permission to merge, deploy, or resume it without current owner
authorization and exact-head verification.

## Recent verified merges

| Commit | PR | Delivered capability |
| --- | ---: | --- |
| `97c5f6f` | `#1372` | Owner-only, read-only subscriber administration surface |
| `8ddc0f9` | `#1373` | Applications/queue accessibility polish and canonical approval proof |
| `8fd87e9` | `#1368` | OCR content cannot independently trigger discrimination-safety refusals |
| `b84d527` | `#1365` | Canonical latest-attachment context and type clarification |
| `335fc24` | `#1364` | Latest-attachment-wins continuation and redemption guard |
| `34f8cb1` | `#1369` | Chat Save/Prepare routed to canonical Applications storage |
| `c044053` | `#1367` | Job-result deduplication with source provenance |
| `7603c8e` | `#1366` | Explicit per-attempt search provenance |

## Current priority order

```text
1. Close the #1372 activation defect through #1375.
2. Deploy the exact merged #1375 commit and verify:
   - owner /api/v1/me.is_owner == true
   - Subscribers navigation appears
   - /admin/subscribers loads for the owner
   - non-owner remains false and blocked
3. Keep AI_WORKSPACE synchronized with live main and the PR board.
4. Triage #1371 overlap/supersession.
5. Rebase and review #1370, #1359, #1362, and #1376 individually.
6. Do not begin new product capability work until the active reliability and
   control-plane work above is resolved or explicitly re-prioritized by owner.
```

## Product and architecture guardrails

- Rico remains an **AI Career Operating System**.
- Production stack remains repository-defined; do not introduce architecture
  drift through opportunistic redesigns or copied prototypes.
- Canonical user-visible mutations must be confirmed from persisted state.
- Do not infer successful save, approval, application, subscription, or external
  action from intent or request completion alone.
- Design references are not production implementation sources unless explicitly
  mapped and rewritten against current `main` contracts.
- One objective per PR. Every runtime PR requires scope, risks, acceptance
  criteria, rollback, exact-head CI, and applicable smoke evidence.

## Current billing statement

Repository documentation and `#1370` describe one authoritative paid plan:
`Rico Monthly`, USD 21.50/month, with Paddle checkout behind authenticated
`/subscription`. Production billing activation and full payment/webhook/
entitlement behavior were **not independently re-verified in this pass**.
Do not advertise additional tiers or a different processor without an explicit
owner decision and synchronized backend/frontend configuration.

## Mandatory session behavior

1. Fetch current `main`; never trust the SHA above after this snapshot date.
2. List open PRs and inspect overlap before choosing work.
3. Read `DECISIONS.md`, this file, `CURRENT_STATE.md`, `TASKS.md`, and
   `ENGINEERING_ROADMAP.md`.
4. Prefer reliability/trust work over new features under `DEC-20260723-001`.
5. Claim one objective and use an isolated branch/worktree.
6. Stop if another writer owns the objective or the live state conflicts with
   the workspace.
7. Do not merge, deploy, mutate production data, or change secrets without
   explicit authorization.

## Stop conditions

Stop and report instead of guessing when:

- live `main`, deployed commit, CI, or the open PR board conflicts with this file;
- a proposed change overlaps an active PR;
- the task expands into auth, billing, database, deployment, email, or external
  actions outside the approved objective;
- production verification needs credentials or mutation that were not approved;
- a PR claims success without persisted-state or exact-head evidence.

## Next exact action

```text
Review #1375 against current main. If scope and exact-head gates remain clean,
obtain merge authorization, deploy it, and run the owner/non-owner production
smoke before starting any new feature work.
```

Historical snapshots remain available in Git history. This file intentionally
contains the current operational control state rather than stacking additional
superseded status narratives.

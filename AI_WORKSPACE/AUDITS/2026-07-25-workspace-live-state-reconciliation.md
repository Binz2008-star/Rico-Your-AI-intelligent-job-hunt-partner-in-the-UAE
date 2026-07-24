# AI_WORKSPACE Live-State Reconciliation — 2026-07-25

## Purpose

Record the evidence used to reconcile the mandatory control panel and engineering
roadmap with live repository and deployment state.

This is an **evidence record**, not a parallel source of truth.
`AI_WORKSPACE/PROJECT_STATUS.md` remains the mandatory current control panel.

## Ownership and update rule

- Owner: acting technical/release lead for this reconciliation.
- Update this record only to correct factual errors in this specific snapshot.
- Future state changes belong in `PROJECT_STATUS.md`, the relevant task entry,
  and a new dated evidence record when necessary.

## Scope

Docs only:

- `AI_WORKSPACE/PROJECT_STATUS.md`
- `AI_WORKSPACE/ENGINEERING_ROADMAP.md`
- this evidence record

`CURRENT_STATE.md` and `TASKS.md` were inspected and confirmed stale, but were
not rewritten in this PR because they contain large historical ledgers. A full
replacement would delete substantial traceability. They require a separate
structure-preserving reconciliation.

## Evidence gathered

### Live `main`

GitHub commit search returned:

```text
97c5f6f62e863fb97ed0e08c9e88a7f57d167b67
feat(admin): owner-only subscriber administration surface (#1372)
```

Recent preceding merges were also verified:

```text
8ddc0f9  #1373 Applications board + /queue a11y + canonical approval proof
8fd87e9  #1368 OCR discrimination-safety trigger correction
b84d527  #1365 attachment provenance slice 2
335fc24  #1364 attachment provenance slice 1
34f8cb1  #1369 canonical chat Save/Prepare persistence
c044053  #1367 job-result deduplication + provenance
7603c8e  #1366 per-attempt search provenance
```

### Production/deployment state

Vercel deployment listing showed the current production deployment:

```text
state: READY
target: production
branch: main
commit: 97c5f6f62e863fb97ed0e08c9e88a7f57d167b67
```

GitHub combined deployment status for `97c5f6f` showed:

```text
Vercel: success
Railway service: success
```

Limit of this evidence:

- No live backend `/version` or `/health` request was executed in this pass.
- No broad authenticated product smoke was executed.
- Deployment success was therefore recorded separately from product behavior.

### Open PR board

GitHub returned seven open PRs:

| PR | Draft | Mergeable | Verified role in current board |
| ---: | --- | --- | --- |
| `#1376` | yes | yes | Profile UX/accessibility polish |
| `#1375` | yes | yes | Canonical `/api/v1/me.is_owner` activation fix |
| `#1374` | yes | yes | Docs-only competitive-differentiation proposal |
| `#1371` | yes | no | Mixed design references plus production polish already extracted into `#1373` |
| `#1370` | no | yes | Public read-only `/pricing`; old base |
| `#1362` | yes | yes | Command category hints; old base |
| `#1359` | no | yes | Warning contrast plus theme persistence; mixed scope and old base |

### Confirmed `#1372` activation defect

The `#1375` PR evidence records:

```text
#1372 added is_owner to /api/v1/auth/me
The frontend owner gate reads /api/v1/me through fetchMe()
Live /api/v1/me omitted is_owner
The owner nav stayed hidden and /admin/subscribers redirected
```

The `#1375` diff is focused on:

- `src/api/routers/user.py`
- `tests/test_me_is_owner.py`

Focused tests cover:

- owner id match → true;
- non-owner → false;
- unset configuration → false;
- matching email with wrong canonical id → false.

GitHub Actions for the `#1375` head showed successful QA Tests and Workflow
Security Guards; its Vercel preview was `READY`. This does not replace the
required post-merge production smoke.

## Staleness findings

Before reconciliation:

- `PROJECT_STATUS.md` recorded `main` `45fa80c4` and zero open PRs.
- `CURRENT_STATE.md` recorded the same stale baseline and zero open PRs.
- `TASKS.md` ended its current operational story at the July 23 backlog sweep.
- `ENGINEERING_ROADMAP.md` carried a July 18 snapshot and superseded containment,
  PR, integration, and release states.

## Decisions applied

1. Update the mandatory control panel from live facts.
2. Replace the stale roadmap snapshot with the current trust-first sequence.
3. Preserve historical traceability rather than deleting thousands of task and
   current-state lines in a broad rewrite.
4. Mark `CURRENT_STATE.md` and `TASKS.md` as requiring a dedicated
   structure-preserving reconciliation.
5. Keep `#1375` as the immediate operational priority.
6. Do not treat `#1374` or design references as implementation authorization.
7. Do not merge `#1371` as-is because it is non-mergeable and its production
   Applications/queue portion already shipped via `#1373`.

## Required follow-up

```text
1. Review and merge this docs-only reconciliation after owner approval.
2. Review #1375 on exact head.
3. Merge/deploy #1375 only with explicit authorization.
4. Run owner and non-owner production smoke.
5. Reconcile CURRENT_STATE.md and TASKS.md without destructive history loss.
6. Triage and rebase the remaining PR board one PR at a time.
```

## Rollback

Revert this docs-only PR. No runtime, database, environment, billing, or
production-data rollback is required.

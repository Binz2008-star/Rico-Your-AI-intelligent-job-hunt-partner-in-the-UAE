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

A green deployment badge is not a product smoke. An open PR is not merge authorization. A rehearsal is not production-repair authorization.

## Current reconciliation — 2026-07-29

### Verified repository state

| Item | Verified state |
| --- | --- |
| `main` at the start of this pass | `0e68f11d834ae8e8f376f16f26f52091a0dc8cbb` |
| `#1432` | **MERGED** as `3fa214a2b6631d2f73d0980f7700983550dce717` |
| `#1434` | **MERGED** as `0e68f11d834ae8e8f376f16f26f52091a0dc8cbb`; previous batch reconciliation |
| `#1389` | **CLOSED WITHOUT MERGE**; branch history preserved, not validated for reuse |
| Other previously open PRs | closed or merged; no implementation PR is currently authorized |

## `#1432` production verification

Direct production reads through the deployed web proxy established:

- `/version` returned **HTTP 200** and served commit `3fa214a2b6631d2f73d0980f7700983550dce717` in the production environment;
- `/health` returned **HTTP 200 / status=ok**;
- Jooble, Adzuna, and JSearch were configured and non-degraded at the read;
- the reasoning provider was configured, its model precheck was reachable, and fallback was available;
- `ricohunt.com` was reachable.

### Verification boundary

The authenticated pending-search/gratitude interaction was **not executed by this controller session**. The available safe web connector could read production endpoints but could not perform an authenticated POST with the smoke account while preserving secret boundaries.

Therefore:

- deployment identity: **VERIFIED**;
- service health: **VERIFIED**;
- changed gratitude behavior in production: **NOT PRODUCT-SMOKE VERIFIED**;
- unit and exact-head CI evidence remain valid, but do not substitute for the missing authenticated interaction.

The remaining focused smoke must prove that standard Arabic gratitude `شكرًا` causes no second search/provider dispatch and leaves the pending offer available for a later explicit confirmation.

## Journey-1 D1 mapping and rehearsal

`TASK-20260728-003` became startable in this pass because the Neon connector was authenticated and the owner explicitly directed the controller to process the decision above `#1389`.

Every database call explicitly targeted the owner-created evidence branch `d1-ownership-evidence-2026-07-28`. The first read confirmed the connection resolved to that non-default branch. No production call or production mutation was made.

The public result is recorded in:

`AI_WORKSPACE/EVALS/2026-07-29-journey1-d1-row-mapping-rehearsal.md`

The task's current state is **completed**. Any older `blocked` label retained in its historical `TASKS.md` continuity block is superseded by this mandatory control panel and the final evaluation above; it carries no lease, write authorization, or permission to repeat the mapping.

### Evidence result

One unique ownership shape matched the historical conflict:

- five connected owner rows;
- three non-guest resolver candidates;
- two guest rows;
- one unique exact authenticated-principal row;
- two non-guest email-only candidates.

### Canonical rule

The unique exact authenticated-principal row is canonical. Recency, completeness, row order, or chat volume are not ownership proofs.

### Rehearsal result

A temporary private schema inside the evidence branch rehearsed the consolidation and then was dropped.

Validated post-state in the rehearsal copies:

- one owner row and one profile;
- all **1,463** chat messages preserved;
- all **24** learning-signal rows preserved;
- all **13** job-context rows preserved;
- one completed onboarding state;
- zero stale CV filename/status claims;
- zero orphaned chat or learning rows;
- one canonical owner for text-keyed learning and job context.

A final read after dropping the rehearsal schema confirmed the original evidence-branch tables remained unchanged at five owners/five profiles with all dependent counts intact.

### Data-repair boundary

The repair contract is now understood, but **production repair remains unauthorized**.

A production maintenance approval must separately confirm:

1. backup/PITR availability;
2. exact target re-identification at execution time;
3. exact SQL and rollback review;
4. fail-closed pre/post count assertions;
5. explicit acceptance that legacy `applications` has no usable ownership key;
6. post-repair authenticated smoke.

No bulk cleanup of other clusters is authorized.

## `#1389` ruling

The data blocker is characterized; the historical PR is still unsafe to merge.

Against current `main`, its branch was 28 commits ahead and 27 behind, changed 18 files, and combined backend, frontend, identity, artifact lifecycle, tests, and documentation.

**Ruling:** `#1389` was closed without merge. Its branch history remains available for selective salvage only.

After a separately authorized production consolidation completes, the pending-artifact activation objective must be recut from current `main` as one or more small PRs. No old CI result, review, SHA, or code hunk carries forward without independent re-verification.

## Current work state

| Measure | State |
| --- | --- |
| Open implementation PRs | 0 |
| Authorized implementation writers | 0 |
| Production database repair | not authorized |
| D1 evidence/rehearsal | completed; final report stored at the evaluation path above |
| `#1432` endpoint verification | complete |
| `#1432` authenticated behavior smoke | still required |

## Standing rulings

- Trust-first remains binding; no unrelated feature expansion.
- Production credentials must not be passed to agents or written into repository material.
- Shared email or contact data alone is not sufficient ownership proof.
- No production mutation, schema change, deletion, or reassignment is authorized by the D1 report or rehearsal.
- Closed PR branches are historical sources, not implementation branches.

## Stop conditions

Stop and report instead of guessing when:

- a writer already owns the same branch/objective;
- branch history contains unexplained commits;
- scope expands across unrelated objectives;
- production mutation, secret, migration, merge, or deployment action lacks explicit owner authorization;
- a data claim is not derived from a current authoritative read;
- an authenticated smoke would expose credentials or require an uncontrolled real-user mutation;
- a repair query cannot assert its exact target and expected cardinality before writing.

## Next exact action

```text
1. Close the remaining #1432 product-smoke gap with a dedicated authenticated
   smoke account and secret-safe POST path. Prove no second search dispatch on
   "شكرًا" and prove the pending offer survives for a later explicit YES.

2. Present the exact production consolidation plan, rollback queries, PITR proof,
   and post-repair smoke for explicit owner approval. Do not execute production
   SQL from the evidence/rehearsal authorization.

3. After the production data repair is separately approved and verified, recut
   Journey-1 D2 pending-artifact activation from current main. Do not reopen or
   rebase #1389.

No unrelated feature, bulk cleanup, or historical-branch merge is queued.
```

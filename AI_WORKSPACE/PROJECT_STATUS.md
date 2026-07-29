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

A green deployment badge is not a product smoke. A rehearsal is not production-repair authorization. A merged SQL package is not permission to execute it.

## Current reconciliation — 2026-07-29

### Verified repository state

| Item | Verified state |
| --- | --- |
| `main` | `cbcb4206b7b13a6de2fbbe84e42d610addc054e2` |
| `#1432` | **MERGED** as `3fa214a2b6631d2f73d0980f7700983550dce717`; authenticated gratitude smoke still pending |
| `#1435` | **MERGED** as `9f731f19f5c46d454525690fc44b2ec319a4f2d1`; records endpoint evidence and the `#1389` ruling |
| `#1436` | **MERGED** as `a292f99bf4a6a80745f4b5e29151684f37530cfc`; final D1 operating package, no production execution authorization |
| `#1437` | **MERGED** as `3e18737079d21da8db63f581b7d1d99c87cc1904`; synthetic persona/CV-fixture factory and required QA enrollment |
| `#1438` | **MERGED** as `7714b49643485f7c87a28c0f7d85ed61cc017375`; real-Postgres cross-user document-isolation coverage, tests only |
| `#1443` | **MERGED** as `cbcb4206b7b13a6de2fbbe84e42d610addc054e2` from head `542b66a6b7c65467b92385792ee0abe0201bf3d9`; read-only Delivery Smoke residual audit package |
| `#1389` | **CLOSED WITHOUT MERGE**; historical branch only, not an implementation branch |
| Open implementation PRs | **0** |

## Production verification boundary

The last direct production verification for `#1432` established:

- `/version` returned HTTP 200 and served `3fa214a2b6631d2f73d0980f7700983550dce717`;
- `/health` returned HTTP 200 / `status=ok`;
- configured providers were non-degraded at the read;
- `ricohunt.com` was reachable.

The authenticated pending-search/gratitude interaction remains **not product-smoke verified**. A dedicated secret-safe smoke must prove that `شكرًا` causes no second search dispatch and leaves the pending offer available for a later explicit confirmation.

`#1436` is documentation/operator SQL only. `#1437` and `#1438` are tests/workflow enrollment only. Their merge SHAs do not constitute new runtime behavior evidence and do not close the `#1432` smoke gap.

## Journey-1 D1 evidence

The single mapped ownership cluster is established:

- five owner rows;
- one unique exact authenticated-principal row;
- two non-guest email-only rows;
- two guest rows;
- five profiles;
- 1,463 chat messages;
- 24 text-keyed learning signals;
- 13 job-context rows;
- five completed onboarding rows;
- one canonical agent-settings row;
- no authoritative stored document or pending CV artifact.

The canonical rule is the unique exact authenticated-principal row. Shared email, recency, completeness, row order, and chat volume are not ownership proofs.

## D1 production consolidation package

The reviewed package is merged at `a292f99bf4a6a80745f4b5e29151684f37530cfc` and stored at:

`AI_WORKSPACE/RUNBOOKS/2026-07-29-d1-production-consolidation.md`

Adjacent SQL files provide:

- read-only preflight;
- private backup export from a fresh pre-repair Neon branch;
- serializable fail-closed apply script;
- aggregate postcheck;
- targeted rollback from the private export.

### Rehearsal evidence

Non-production rehearsal passed for:

- positive preflight;
- fail-closed rejection of invalid onboarding lifecycle shapes;
- dry-run with no state change;
- committed apply preserving all expected dependent rows;
- postcheck;
- targeted rollback restoring the original fingerprint.

The rehearsal branches are test evidence only and are not the mandatory production backup.

### PITR and backup gate

The verified Neon history-retention window was 24 hours at the time of package preparation. A fresh pre-repair branch plus private encrypted row export is a hard execution gate. Both must be retained for seven days after successful smoke.

### Authorization state

| Action | State |
| --- | --- |
| Package preparation, review, merge, and non-production rehearsal | **COMPLETE** |
| Production read-only preflight | **NOT AUTHORIZED** |
| Production `commit=false` rehearsal | **NOT AUTHORIZED** |
| Production committed transaction | **NOT AUTHORIZED** |
| Targeted production rollback | authorized only by a defined rollback condition after final execution approval |
| Any other cluster or bulk cleanup | **NOT AUTHORIZED** |

A future production approval must explicitly name the merged package commit, the maintenance window, the exact target re-identification, the backup/export gate, the preflight, the `commit=false` rehearsal, the committed transaction, postcheck, authenticated smoke, and rollback conditions.

## `#1389` ruling

`#1389` is closed without merge. Its branch is substantially diverged and mixes backend, frontend, identity, artifact lifecycle, tests, and documentation.

Do not reopen, rebase, mark Ready, merge, or treat it as resumable. After the production data repair is separately approved and verified, pending-artifact activation must be recut from then-current `main` as one or more small PRs. No old CI result, review, SHA, or code hunk carries forward without re-verification.

## Current work state

| Measure | State |
| --- | --- |
| Active implementation writers | **0** |
| Active documentation writers | **1 — this reconciliation branch only; lease ends on merge/close** |
| Open implementation PRs | **0** |
| Multi-user reliability PR 1 / PR 2 | **merged through #1437 / #1438** |
| D1 mapping/rehearsal | **complete** |
| D1 final operating package | **merged** |
| Production database repair | **not authorized** |
| `#1432` endpoint verification | **complete** |
| `#1432` authenticated behavior smoke | **pending** |
| `#1443` Delivery Smoke residual audit | **complete** |
| `#1443` cleanup package preparation | **in progress; production deletion not authorized** |
| CV smoke overall | **FAIL** |
| `#355` | **deferred** |
| `#1389` | **closed without merge; historical only** |

## Delivery Smoke residual audit (`#1443`)

A separate read-only audit was dispatched against production data at workflow run `30475312924` (checked out `main` `cbcb4206b7b13a6de2fbbe84e42d610addc054e2`, success):

- **Total synthetic rows observed:** 84
- **Tables audited:** 11
- **Tables marked INCONCLUSIVE:** 0
- **Residual tables:** `rico_users` (8), `rico_onboarding_states` (8), `rico_chat_history` (48), `rico_profiles` (4), `learning_signals` (3), `chat_operations` (3), `user_job_context` (5), `rico_job_recommendations` (5)
- **No PII, credentials, or raw payload reached the log output.**

This audit covered the full historical Delivery Smoke synthetic namespace (`smoke-delivery-*@synthetic-rico.test`) and is explicitly not attributed to a single workflow run.

### Authorization state for cleanup

| Action | State |
| --- | --- |
| Cleanup package preparation and non-production rehearsal | **AUTHORIZED** |
| Production `commit=false` rehearsal | **NOT AUTHORIZED** |
| Production committed cleanup transaction | **NOT AUTHORIZED** |
| Production deletion of any kind | **NOT AUTHORIZED** |

A fresh pre-cleanup Neon branch (or equivalent approved private backup) is a hard gate before any committed production execution.

## Documentation drift boundary

This control panel supersedes stale current-state wording still present in lower-authority historical snapshots, including references that describe `#1389` as open or `TASK-20260728-003` as blocked on Neon access. Those statements must not be used to authorize work. Historical entries are not deleted merely to make the current snapshot shorter.

## Standing rulings

- Trust-first remains binding; no unrelated feature expansion.
- Production credentials and target identifiers must not enter repository material.
- No production SQL may run from the package-preparation or merge authorization.
- Shared email or contact data alone is not ownership proof.
- Closed PR branches are historical sources, not implementation branches.
- Do not re-upload a real CV merely to test this repair.
- Any push changes the exact head and invalidates prior exact-head CI/review evidence.

## Stop conditions

Stop and report instead of guessing when:

- another writer already owns the same branch or objective;
- branch history contains an unexpected commit;
- scope expands beyond control-plane reconciliation;
- the live D1 fingerprint differs from the approved `5/5/1463/24/13/5/1` contract;
- the fresh pre-repair branch or encrypted export is missing;
- the affected account is active during the maintenance window;
- a production mutation, secret, migration, merge, deployment, or authenticated real-user smoke lacks explicit authorization;
- a repair query cannot assert its exact target and expected cardinality before writing.

## Next exact action

```text
1. Complete this one-file control-panel reconciliation through exact-head CI and
   independent review. Do not merge without explicit owner merge approval.
2. Close the separate #1432 authenticated gratitude smoke gap with a dedicated
   smoke account and secret-safe path. Do not combine it with the D1 repaired account.
3. Present the merged D1 package commit and maintenance plan for a new, explicit
   production-execution approval. No production SQL, preflight, dry run, branch,
   export, or real-user mutation is authorized before that approval.
4. Only after successful D1 repair and smoke may pending-artifact activation be
   recut from current main. Do not reopen or reuse #1389.
```

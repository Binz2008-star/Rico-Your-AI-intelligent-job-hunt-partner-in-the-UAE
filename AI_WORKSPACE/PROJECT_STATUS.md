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

A green deployment badge is not a product smoke. A rehearsal is not production-repair authorization. A prepared SQL package is not permission to execute it.

## Current reconciliation — 2026-07-29

### Verified repository state

| Item | Verified state |
| --- | --- |
| `main` at package cut | `9f731f19f5c46d454525690fc44b2ec319a4f2d1` |
| `#1432` | **MERGED** as `3fa214a2b6631d2f73d0980f7700983550dce717` |
| `#1435` | **MERGED** as `9f731f19f5c46d454525690fc44b2ec319a4f2d1`; records production endpoint evidence and the `#1389` ruling |
| `#1389` | **CLOSED WITHOUT MERGE**; branch history is not an implementation branch |
| Open implementation PRs | **0** |

## `#1432` production verification

Verified directly:

- `/version` returned HTTP 200 and served `3fa214a2b6631d2f73d0980f7700983550dce717`;
- `/health` returned HTTP 200 / `status=ok`;
- configured providers were non-degraded at the read;
- `ricohunt.com` was reachable.

The authenticated pending-search/gratitude interaction remains **not product-smoke verified**. A dedicated secret-safe smoke must still prove that `شكرًا` causes no second search dispatch and leaves the pending offer available for an explicit later confirmation.

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

Owner authorization covers **preparation only**. The package is stored at:

`AI_WORKSPACE/RUNBOOKS/2026-07-29-d1-production-consolidation.md`

Adjacent SQL files provide:

- read-only preflight;
- private backup export from a fresh pre-repair Neon branch;
- serializable fail-closed apply script;
- aggregate postcheck;
- targeted rollback from the private export.

### Rehearsal evidence

Two disposable branches created from the current production parent were used.

Apply rehearsal passed:

- one owner and one profile;
- all 1,463 chat messages preserved;
- all 24 learning signals preserved;
- all 13 job-context rows preserved;
- one completed onboarding row;
- zero stale CV claims.

Targeted rollback rehearsal passed:

- five owners restored;
- five profiles restored;
- five onboarding rows restored;
- one agent-settings row restored;
- zero chat ownership differences;
- zero learning ownership differences;
- zero job-context ownership differences.

These branches are test evidence only and are not the required production backup.

### PITR and backup finding

The Neon connector currently reports a 24-hour history-retention window. A fresh pre-repair branch plus private encrypted row export is therefore a hard execution gate. The branch and export must be retained for seven days after successful smoke.

### Authorization state

| Action | State |
| --- | --- |
| Package preparation and non-production rehearsal | **AUTHORIZED AND COMPLETE** |
| Docs PR review/merge | permitted after exact-head gates |
| Production read-only preflight | **NOT YET AUTHORIZED** |
| Production `commit=false` rehearsal | **NOT YET AUTHORIZED** |
| Production committed transaction | **NOT AUTHORIZED** |
| Targeted production rollback | authorized only by a rollback condition after the final execution approval |
| Any other cluster or bulk cleanup | **NOT AUTHORIZED** |

## `#1389` ruling

`#1389` remains closed without merge. Its branch was substantially diverged and mixed backend, frontend, identity, artifact lifecycle, tests, and documentation.

After the production data repair is separately approved and verified, pending-artifact activation must be recut from current `main` as one or more small PRs. No old CI result, review, SHA, or code hunk carries forward without re-verification.

## Current work state

| Measure | State |
| --- | --- |
| Active implementation writers | 0 |
| Active documentation writers | 1 — D1 package branch only; lease ends on merge/close |
| Production database repair | not authorized |
| D1 mapping/rehearsal | complete |
| D1 final operating package | prepared; awaiting exact-head review gates and explicit execution approval |
| `#1432` endpoint verification | complete |
| `#1432` authenticated behavior smoke | still required |

## Standing rulings

- Trust-first remains binding; no unrelated feature expansion.
- Production credentials and target identifiers must not enter repository material.
- No production SQL may run from the preparation authorization.
- Shared email or contact data alone is not ownership proof.
- Closed PR branches are historical sources, not implementation branches.
- Do not re-upload a real CV merely to test this repair.

## Stop conditions

Stop and report instead of guessing when:

- a writer already owns the same branch/objective;
- the package head changes after review or CI;
- the live fingerprint differs from the approved 5/5/1463/24/13/5/1 contract;
- the pre-repair branch or encrypted export is missing;
- the account is active during the maintenance window;
- a production mutation, secret, migration, merge, or deployment action lacks explicit authorization;
- a repair query cannot assert its exact target and expected cardinality before writing.

## Next exact action

```text
1. Open the docs-only D1 package PR from the current package branch.
2. Require exact-head CI and an independent review of the SQL, rollback, PITR,
   privacy boundary, and smoke plan.
3. Present the final head and review result to the owner. Do not run production SQL.
4. Only after a new explicit owner approval naming that final head:
   - create and verify the fresh pre-repair Neon branch;
   - export and validate the private backup;
   - run production preflight;
   - run one commit=false rehearsal;
   - commit only if every gate passes;
   - execute postcheck and authenticated smoke;
   - run targeted rollback only on a defined rollback condition.
5. Close the separate #1432 authenticated gratitude smoke gap with a dedicated
   smoke account; do not combine it with the repaired account.
```

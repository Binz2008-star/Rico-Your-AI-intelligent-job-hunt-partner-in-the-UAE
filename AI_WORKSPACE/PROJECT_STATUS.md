# Project Status — Rico AI

> **Mandatory control panel.** Every agent must read this file before planning or writing.
>
> Live GitHub `main`, exact PR heads, CI, Vercel/Render deployment evidence, Neon state, and production smoke evidence override prose. When this file conflicts with live evidence, stop implementation and reconcile this file first.

## Document contract

- **Why it exists:** one current, evidence-backed operating snapshot for Rico.
- **Update when:** production, active ownership, launch blockers, or priority order changes materially.
- **Source of truth:** this file for current control state; `AI_WORKSPACE/DECISIONS.md` for binding decisions; `AI_WORKSPACE/TASKS.md` for lane-level continuity.
- **Owner:** Rico owner, with the acting CTO/session responsible for evidence-backed reconciliation.
- **History:** prior snapshots remain preserved in Git history. This file intentionally keeps current truth ahead of historical narrative.
- **SHA rule:** never make this document self-stale by claiming its own commit is the permanent current `main`. Fetch `main` live. Record the application/runtime baseline separately from docs-only control commits.

## Rule of authority

Ranked, and not negotiable when they disagree:

1. GitHub `main`, PR heads, and the deployed `/version`.
2. This file.
3. The lane continuity blocks in `AI_WORKSPACE/TASKS.md`.
4. The latest dated handoff.
5. Everything else.

**Every SHA in this file is verified from the API before it is written.** A SHA copied from a message, a summary, or a previous session is not evidence. If live state and this file disagree, reconcile this file before starting anything else.

## Reconciliation — 2026-07-26

### Verified control snapshot

| Field | Value | How it was established |
| --- | --- | --- |
| `main` | `fc2e107d` | Fetched live at the moment this section was written |
| Deployed backend `/version` | **Not verified this pass** | The production host is unreachable from the reconciling container (outbound blocked). Recorded as unknown rather than assumed |
| Application/runtime baseline | **Expected to move to `fc2e107d`** | `#1399` changes five runtime paths under `src/`, so a Render deploy is expected. Confirmation is owner-side |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired | Unchanged |

**`main` and the deployed `/version` are not asserted to be equal here.** Before this cycle they agreed at `e433c7d`. `#1400` cannot have moved the deployment because it touches no runtime path. `#1399` can and should have, because it touches five. Whether that deploy has landed is not verifiable from this container, so it is left open rather than guessed in either direction.

### Merged this cycle

| PR | Merge commit | Runtime paths touched | Deploy | Why that is correct |
| --- | --- | --- | --- | --- |
| `#1400` privileged-trigger containment | `03450277` | **0** | **No deploy expected** | CI/workflow mechanism only. A deploy would be noise, not safety |
| `#1399` documents inventory contract (Milestone A) | `fc2e107d` | **5** (`src/api/routers/files.py`, `src/domain/documents/*`) | **Deploy expected** | It changes runtime behaviour, so it must reach production and be confirmed there |

For merges that touch no runtime path, `main` moving ahead of the deployed `/version` is **expected divergence, not deployment drift**. Do not chase parity, and do not fire a deploy to manufacture it.

### Closed without merge this cycle

| PR | Head | Disposition |
| --- | --- | --- |
| `#1401` design-reference extraction | `d4bd5469` | Closed without merge by the owner as reference-only, outside the Architecture V2 production sequence. **Branch preserved deliberately** — do not delete it, do not reopen the PR. Its exact-head CI was green at closure |
| `#1371` command visual polish | `4e7b82f6` | Closed without merge. It was superseded by `#1401`, which has itself now been closed without merge — so the design-reference work is parked in branch form only, and nothing from either PR is in `main` |

### Production smoke on `e433c7d` (prior baseline)

Three of three classes passed: an ownership-qualified account question answered from the database with reconciled counts; a CV file-list question answered deterministically from the file store; and a general documents question answered by the model **without listing any personal file**.

**Evidence class: verified by the owner through the proxy in a browser session. There is no automated artifact.** That is stated plainly because it decides how much the result can carry: it is real evidence of live behaviour and it is not a regression gate. Nothing may cite this smoke as a substitute for a test. **This smoke predates `#1399` and does not cover it.**

## Active PRs — heads fetched live at this pass

| Lane | PR | Branch | Head | State |
| --- | --- | --- | --- | --- |
| L1 identity ownership | `#1398` | `fix/identity-ownership-resolution` | `c708bbb3` | Draft — next integrity merge |
| L2 CV and documents | `#1389` | `claude/cv-pending-artifact-confirm` | `878c5944` | Draft — resumes after `#1398` |
| L7 control plane | `#1402` | `claude/workspace-control-reconcile` | this PR | Draft — docs-only |

Deferred under the trust-first freeze, heads fetched live: `#1374` (`bed81b15`), `#1370` (`b90dd910`), `#1362` (`a14faffd`), `#1359` (`83d07785`). An open PR is not permission to merge.

**Enabling branch protection will block these four until they rebase. That is intended protective behaviour, not breakage.**

### CI evidence rule

**A passing job on a different commit is not exact-head evidence and may never be cited as one.** Transience is established by the failed run's own annotation, and settled only by a re-run recorded against the same head. A re-run that goes green with no content change is the clean form of that proof: it isolates infrastructure from the diff.

Recorded because it was violated here: a green from a later, different commit was cited as if it settled a `postgres-integration` failure on `#1401`'s head. The failure was a container-registry pull failure with no test executed, and it was properly settled by a re-run on that same SHA.

## Concurrency state

Caps are rules and are fixed. **Counts are read at the reconciliation pass that writes this section**, by applying the counting rules in `OPERATING_RULES.md` to the lane blocks in `TASKS.md` as they read at that moment. They are not carried forward from any earlier report.

| Measure | Cap | At this pass |
| --- | --- | --- |
| Active agents (`WRITING` or `REVIEWING`) | 4 | 2 — L1 writing, L7 writing this reconciliation |
| Simultaneous code writers (`WRITING` + `AUTHORIZED` + executable scope) | 2 | 1 — L1 only; L7 is docs-only and does not count |
| Writers per branch | 1 | 1 on every branch holding a lease |

Lease holders appear against branches throughout this file. **That is ownership, not activity** — see `OPERATING_RULES.md` → "Ownership is not activity". Reading those assignments as concurrent work in progress is the specific misreading the four-field lease model exists to prevent.

## Standing owner rulings

- **Render billing notice — deferred, non-blocking.** Render is operational. The payment reminder is acknowledged by the owner and will be handled by the owner. It is **not** a blocker for work, reviews, merges, or the roadmap. **Do not restate or escalate it.** Raise Render again only on verified service degradation, suspension, failed deployment, health-check failure, or production impact.

## Merge order

1. **L1 `#1398`** — identity ownership; the next integrity merge. Nothing behavioural merges ahead of it.
2. **L7 `#1402`** — this docs-only reconciliation; runs in parallel and must not block coding on other lanes.
3. **L2 `#1389`** — after `#1398` lands, rebased onto the new `main`.

Branch protection is enabled by the owner, with `trusted-ratchet` as the only Required status check.

## Stop conditions

Stop and report instead of guessing when:

- another writer holds the lease on the same branch or objective;
- a branch contains commits not explained by its continuity record;
- a PR scope expands across unrelated objectives;
- a schema diff appears where no migration was approved;
- a check is green only because the relevant test is outside CI;
- production mutation, billing, access-control, secret, migration, merge, or deployment action lacks explicit owner authorization;
- a UI claim is not derived from a current server read;
- a user-data workflow would require another real upload merely to test an unverified fix;
- an instruction arrives without full attribution — see `OPERATING_RULES.md` → "Directive Authority".

## Next exact action

```text
Per lane, read the continuity block in AI_WORKSPACE/TASKS.md, confirm the lease is
yours, check write authorization, fetch the remote, and compare the remote head
against the expected head recorded there before any push.

L1 completes its identity-ownership batch.
L2 rebases onto the new main after #1398 lands.

No merge, no deploy, no database mutation, no real-CV upload, and no bulk Neon
branch deletion is authorized by this document.
```

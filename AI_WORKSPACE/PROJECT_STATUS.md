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

## Reconciliation — 2026-07-26 (late)

> **Evidence-class rule, and the point of this section.** Every line below carries
> its own evidence class: **verified this pass** (with the method named),
> **not verified this pass**, or **owner ruling / owner-reported**. **No line
> inherits certainty from the line above it.** A block of facts is not made true
> by sitting under a heading that says "verified".

### Control snapshot

| Field | Value | Evidence class and method |
| --- | --- | --- |
| `main` | `97af6ded2f2741c10031417c7ac8bda7e7432580` | **Verified this pass** — `git ls-remote origin refs/heads/main`, then confirmed against the fetched tracking ref |
| `main` subject | `fix(identity): never overwrite a stored rico_users.email on a generic upsert (#1404)` | **Verified this pass** — `git log -1 origin/main` |
| `main` commit time | `2026-07-26T14:11:15Z` | **Verified this pass** — same command (`+04:00` local = `14:11:15Z`) |
| Deployed backend `/version.commit` | Owner reports `97af6ded`, i.e. parity with `main` | **NOT verified this pass.** `rico-job-automation-api.onrender.com:443` is refused by this session's egress policy (proxy answered `403` to `CONNECT`; recorded in the proxy's own failure log). Policy denials must be reported, not routed around. **Recorded as owner-reported, not as an independent reading** |
| Application/runtime baseline | Expected at `97af6ded` | **Derived, not observed** — follows from the owner report above, not from a reading taken here |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired | **Owner ruling** — restated as a ruling, not re-derived as an observation |

**On the parity line specifically.** The owner reports `main` and production agree at `97af6ded`. This reconciliation could not confirm that, so it is written as the owner's report rather than as a verified fact. Anyone needing deployment parity as a *gate* must take their own reading — this document does not supply one. That distinction is the whole reason this section exists: a previous pass asserted parity it had not observed, and the correction is recorded in `#1402`.

### Merged 2026-07-26, in order

**Evidence class: verified this pass** — `git log origin/main`, reading merge commits directly off the branch.

| PR | Merge commit | Subject |
| --- | --- | --- |
| `#1382` | `e433c7df` | routing: ownership-qualified account questions reach their handler |
| `#1400` | `03450277` | ci: privileged-trigger containment properties made executable |
| `#1399` | `fc2e107d` | documents inventory contract (Milestone A, first slice) |
| `#1402` | `805dd4d6` | docs: control-plane reconciliation + lane authority rules |
| `#1398` | `70c2af7c` | identity: fail closed on ambiguous account ownership |
| `#1404` | `97af6ded` | identity: never overwrite a stored email on a generic upsert |

For merges that touch no runtime path, `main` moving ahead of the deployed `/version` is **expected divergence, not deployment drift**. Do not chase parity, and do not fire a deploy to manufacture it.

### Closed without merge this cycle

| PR | Head | Disposition |
| --- | --- | --- |
| `#1401` design-reference extraction | `d4bd5469` | Closed without merge by the owner as reference-only, outside the Architecture V2 production sequence. **Branch preserved deliberately** — do not delete it, do not reopen the PR. Its exact-head CI was green at closure |
| `#1371` command visual polish | `4e7b82f6` | Closed without merge. It was superseded by `#1401`, which has itself now been closed without merge — so the design-reference work is parked in branch form only, and nothing from either PR is in `main` |

### Production smoke on `e433c7d` (prior baseline)

Three of three classes passed: an ownership-qualified account question answered from the database with reconciled counts; a CV file-list question answered deterministically from the file store; and a general documents question answered by the model **without listing any personal file**.

**Evidence class: owner-verified through the proxy in a browser session. There is no automated artifact.** That is stated plainly because it decides how much the result can carry: it is real evidence of live behaviour and it is not a regression gate. Nothing may cite this smoke as a substitute for a test.

**It predates `#1399`, `#1402`, `#1398` and `#1404`, and covers none of them.** Five merges have landed since. Treat it as a historical baseline only — it is not evidence about the current deployment.

## Open PRs — exactly seven, all Draft

**Evidence class: verified this pass** — enumerated from the GitHub API; count, draft state, head and base SHAs all read from that response rather than carried from any report.

| PR | Head | Base | Base state | Objective |
| --- | --- | --- | --- | --- |
| `#1406` | `251654cf` | `97af6ded` | current | Runs the identity-ownership boundary tests in the pytest job |
| `#1405` | `99a3aca0` | `97af6ded` | current | Maps ambiguous account ownership to `409` on onboarding |
| `#1389` | `4f2abe60` | `70c2af7c` | **stale — one commit behind** | CV confirm path reachable |
| `#1374` | `bed81b15` | `97c5f6f6` | **stale** | Competitive-differentiation gap analysis (docs) |
| `#1370` | `b90dd910` | `8fd87e90` | **stale** | Public `/pricing` page |
| `#1362` | `a14faffd` | `34f8cb1a` | **stale** | Command starter-prompt category hints |
| `#1359` | `83d07785` | `8fd87e90` | **stale** | `GuardrailWarnings` palette awareness |

An open PR is not permission to merge. The five stale-base PRs must rebase before they can take exact-head gates; branch protection blocking them is **intended protective behaviour, not breakage**.

### `#1389` — written hold reason has cleared

The recorded hold was "behind the five-row identity consolidation". **That hold no longer applies**, for a reason worth stating precisely: the production repair was executed as **separation, not consolidation** — all five rows still exist, nothing was deleted, each row's email now equals its own `external_user_id`, and each account kept its own data. *(Evidence class: **owner-reported**. This reconciliation performed no database read and is forbidden from doing so.)*

Two mechanical facts about the PR were checked here directly:

- **No merge conflict against `main@97af6ded`** — *verified this pass*, `git merge-tree --write-tree` returned a clean tree with no conflict markers.
- **Zero file overlap with `#1404`** — *verified this pass*. `#1404` touched `src/repositories/profile_repo.py`, `src/rico_db.py`, `src/rico_jotform_webhook.py` and one test; `#1389` touches none of them.

**Its base is nonetheless stale** (`70c2af7c`, one commit behind `main`) and must be refreshed by its own lane. **Do not modify `#1389`** — not its body, not its branch. This is a record of state, not an action on it.

## Open production-integrity item — identity clusters not healed by `#1404`

**Evidence class: owner-reported. Not verified this pass** — no Neon read was taken, and none is authorized. Recorded here because no other control document currently states it, and a session that reads only the merge list would wrongly conclude the identity work is finished.

- **Cluster `55502f40…`** — three rows, two wrongly stamped, and **no login accounts among them**, which makes it Telegram/Jotform-sourced identity rather than password-auth identity.
- **`#1404` does not heal it.** That fix fills a `NULL` email only on byte-exact equality with the row's own `external_user_id`; these rows do not meet that condition, so the rule passes over them.
- **Any user in `55502f40…` still sees `409`/`503`.**
- **Three further mismatched rows are not yet colliding.** They will begin refusing the moment a second row joins their email — a latent fault, not a dormant one.

Identifiers appear as truncated hashes only. **This is an open item, not a closed one, and no production data repair is authorized by this document.**

## CI gap — OPEN

**Evidence class: verified this pass** by reading `.github/workflows/qa-tests.yml` at `97af6ded` and the `#1406` diff.

The `pytest` job **enumerates explicit test paths** rather than running `tests/`. `tests/test_identity_ownership_boundaries.py` exists on `main` but appears nowhere in that list, so **it has never been executed in CI — its green was blind.** A passing `pytest` job therefore did not mean those boundaries held.

`#1406` adds exactly that one path (a single-line, single-file diff) and is **the fix, in review**. **This gap stays OPEN until `#1406` merges.** It is a live instance of the standing stop condition "a check is green only because the relevant test is outside CI".

### CI evidence rule

**A passing job on a different commit is not exact-head evidence and may never be cited as one.** Transience is established by the failed run's own annotation, and settled only by a re-run recorded against the same head. A re-run that goes green with no content change is the clean form of that proof: it isolates infrastructure from the diff.

Recorded because it was violated here: a green from a later, different commit was cited as if it settled a `postgres-integration` failure on `#1401`'s head. The failure was a container-registry pull failure with no test executed, and it was properly settled by a re-run on that same SHA.

## Concurrency state

Caps are rules and are fixed. **Counts are read at the reconciliation pass that writes this section**, by applying the counting rules in `OPERATING_RULES.md` to the lane blocks in `TASKS.md` as they read at that moment. They are not carried forward from any earlier report.

| Measure | Cap | At this pass |
| --- | --- | --- |
| Active agents (`WRITING` or `REVIEWING`) | 4 | **Not derivable from GitHub** — read the lane blocks in `TASKS.md`. This pass observed only L7 (this docs-only reconciliation) |
| Simultaneous code writers (`WRITING` + `AUTHORIZED` + executable scope) | 2 | 0 observed — L7 is docs-only and does not count. Other lanes may hold unpushed work that is invisible here |
| Writers per branch | 1 | 1 on every branch holding a lease |

**Why these are not filled in with confident numbers.** Activity and write authorization are *not* observable from GitHub: a lane can hold a `WRITING` lease with local commits that have never been pushed, so a quiet branch is not an idle lane. Counting open PRs is not counting active writers. Any pass that needs these numbers must read them from the lane blocks, not infer them from this table.

Lease holders appear against branches throughout this file. **That is ownership, not activity** — see `OPERATING_RULES.md` → "Ownership is not activity". Reading those assignments as concurrent work in progress is the specific misreading the four-field lease model exists to prevent.

## Standing owner rulings

**These are rulings, not observations.** They hold until the owner changes them, and they are not re-derived, re-litigated, or "checked" by a reconciliation pass.

- **`DEC-20260723-001` — no new feature expansion** until trust and execution reliability are repaired.
- **Render billing notice — deferred, non-blocking.** Render is operational per the owner's ruling; the owner is handling payment. It is **not** a blocker for work, reviews, merges, or the roadmap. **Do not restate or escalate it.** Raise Render again only on verified service degradation, suspension, failed deployment, health-check failure, or production impact.
- **Do not redesign the UI while operational state is unstable.** Visual work stays parked regardless of how ready a design branch looks.

## Merge order

1. **`#1406`** — the CI gap fix. It is one line and it closes a blind spot that makes every other identity green untrustworthy, so it goes first.
2. **`#1405`** — ambiguous account ownership → `409` on onboarding; it lands on a `pytest` job that actually runs the boundary tests once `#1406` is in.
3. **`#1389`** — rebase off the stale `70c2af7c` first. Its written hold has cleared and it conflicts with nothing, but the rebase is its own lane's work.
4. **The four deferred PRs** (`#1374`, `#1370`, `#1362`, `#1359`) remain parked under the trust-first freeze and the UI ruling above.

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
Base for all lanes: main@97af6ded. Fetch it and confirm before any push.

1. Review and merge #1406. Until it lands, every identity-boundary green in CI
   is blind, so it precedes the other identity work rather than following it.

2. Review #1405 (ambiguous ownership -> 409 on onboarding) against a pytest job
   that actually executes the boundary tests -- that is, after #1406.

3. #1389's lane rebases it off the stale base 70c2af7c. Its hold has cleared and
   merge-tree is clean; the rebase is still its own lane's work, not this
   document's, and no other lane may touch that branch.

4. Owner decision, and nothing here substitutes for it: the 55502f40 cluster and
   the three not-yet-colliding rows are unhealed by #1404. They need a decided
   repair path. No repair is authorized by this document.

5. Whoever needs deployment parity as a gate takes their own /version reading.
   This document records the owner's report of parity at 97af6ded; it does not
   supply an independent one, because egress policy blocked the host at this pass.

No merge, no deploy, no database mutation, no real-CV upload, no production data
repair, and no bulk Neon branch deletion is authorized by this document.
```

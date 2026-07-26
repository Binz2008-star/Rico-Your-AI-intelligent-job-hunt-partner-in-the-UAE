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

## Reconciliation — 2026-07-26 (post-`#1414`)

### Verified control snapshot

| Field | Value | How it was established |
| --- | --- | --- |
| `main` | `ca266366` | Fetched live at the moment this section was written |
| Deployed backend `/version` | **`ca266366` — verified** | Central Controller read `/version.commit` = `ca266366` in a browser. Not reproducible from the reconciling container, whose egress to the Render host is blocked |
| `/health` | **ok** | Same read: `jooble`, `adzuna` and `jsearch` configured and **not** degraded; DeepSeek precheck reachable |
| Application/runtime baseline | `ca266366` — **equal to `main`** | `#1414` touches `src/repositories/profile_repo.py`, so the `src/**` deploy filter matched and the deploy fired on merge |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired | Unchanged |

**`main` and the deployed `/version` are asserted equal at this pass, on a browser read by the Controller.** That is a real observation with a named observer, not an automated artifact, and it is not a regression gate.

### Merged since the previous reconciliation

Listed in merge order. The previous snapshot of this section described `#1398` and `#1402` as open Drafts; **both are merged** and that description was stale.

| PR | Merge commit | Runtime paths touched | Deploy |
| --- | --- | --- | --- |
| `#1402` control-plane reconciliation | `805dd4d6` | **0** — docs-only | No deploy expected |
| `#1398` fail closed on ambiguous account ownership | `70c2af7c` | 11 under `src/` | Deploy expected and fired |
| `#1404` never overwrite a stored `rico_users.email` | `97af6ded` | 3 under `src/` | Deploy expected and fired |
| `#1406` identity-ownership tests into the pytest gate | `42c3b976` | **0** — CI-only | No deploy expected |
| `#1408` roadmap truth restored | `1c13147f` | **0** — docs-only | No deploy expected |
| `#1412` a phone number is not proof of who someone is | `701939fa` | 3 under `src/` | Deploy expected and fired |
| `#1411` fail when a test file is run by no pytest invocation | `a610b696` | **0** — CI-only | No deploy expected |
| `#1414` a guest row is not a candidate on the email or Telegram path | `ca266366` | 1 under `src/` | Deploy expected and fired; `/version` confirms |

For merges that touch no runtime path, `main` moving ahead of the deployed `/version` is **expected divergence, not deployment drift**. Do not chase parity, and do not fire a deploy to manufacture it.

### Reviewer availability — recorded because it affected three merges

`#1398`, `#1412` and `#1414` each merged with **no independent review**: the Codex reviewer returned "You have reached your Codex usage limits for code reviews" on all three. `#1414` was marked Ready specifically so review would gate merging, and that gate did not function. This is recorded as a standing condition of the review pipeline, not as a defect in any one PR.

### Closed without merge

| PR | Head | Disposition |
| --- | --- | --- |
| `#1407` | — | Closed as **stale, not merged** |
| `#1401` design-reference extraction | `d4bd5469` | Closed without merge by the owner as reference-only, outside the Architecture V2 production sequence. **Branch preserved deliberately** — do not delete it, do not reopen the PR. Its exact-head CI was green at closure |
| `#1371` command visual polish | `4e7b82f6` | Closed without merge. It was superseded by `#1401`, which has itself now been closed without merge — so the design-reference work is parked in branch form only, and nothing from either PR is in `main` |

### Production smoke on `e433c7d` (prior baseline)

Three of three classes passed: an ownership-qualified account question answered from the database with reconciled counts; a CV file-list question answered deterministically from the file store; and a general documents question answered by the model **without listing any personal file**.

**Evidence class: verified by the owner through the proxy in a browser session. There is no automated artifact.** That is stated plainly because it decides how much the result can carry: it is real evidence of live behaviour and it is not a regression gate. Nothing may cite this smoke as a substitute for a test. **This smoke predates `#1399` and does not cover it.**

## Active PRs — heads fetched live at this pass

| Lane | PR | Branch | State |
| --- | --- | --- | --- |
| L1 identity ownership | `#1398` | `fix/identity-ownership-resolution` | **CLOSED — merged as `70c2af7c`.** The lane's later slices merged as `#1412` (`701939fa`) and `#1414` (`ca266366`) |
| L2 CV and documents | `#1389` | `claude/cv-pending-artifact-confirm` | Open. Was held behind the identity track; that blocker has cleared, and its base is now stale against `ca266366` |
| L7 control plane | `#1402` | `claude/workspace-control-reconcile` | **CLOSED — merged as `805dd4d6`.** This reconciliation is a separate, later docs-only PR |

Other open PRs at this pass, read live: `#1413`, `#1410`, `#1409`, `#1405`, `#1374`, `#1370`, `#1362`, `#1359`. `#1409`, `#1410` and `#1405` continue the identity-ownership track on the chat and onboarding paths. **An open PR is not permission to merge**, and per-PR heads are deliberately not restated here — they move, and a head copied into this file is stale the moment a lane pushes. Fetch them live.

**Enabling branch protection will block these four until they rebase. That is intended protective behaviour, not breakage.**

### CI evidence rule

**A passing job on a different commit is not exact-head evidence and may never be cited as one.** Transience is established by the failed run's own annotation, and settled only by a re-run recorded against the same head. A re-run that goes green with no content change is the clean form of that proof: it isolates infrastructure from the diff.

Recorded because it was violated here: a green from a later, different commit was cited as if it settled a `postgres-integration` failure on `#1401`'s head. The failure was a container-registry pull failure with no test executed, and it was properly settled by a re-run on that same SHA.

## Concurrency state

Caps are rules and are fixed. **Counts are read at the reconciliation pass that writes this section**, by applying the counting rules in `OPERATING_RULES.md` to the lane blocks in `TASKS.md` as they read at that moment. They are not carried forward from any earlier report.

| Measure | Cap | At this pass |
| --- | --- | --- |
| Active agents (`WRITING` or `REVIEWING`) | 4 | 1 — this docs-only reconciliation. L1's batch is merged and its lease released |
| Simultaneous code writers (`WRITING` + `AUTHORIZED` + executable scope) | 2 | 0 — this pass is docs-only and does not count against the cap |
| Writers per branch | 1 | 1 on every branch holding a lease |

Lease holders appear against branches throughout this file. **That is ownership, not activity** — see `OPERATING_RULES.md` → "Ownership is not activity". Reading those assignments as concurrent work in progress is the specific misreading the four-field lease model exists to prevent.

## Standing owner rulings

- **Render billing notice — deferred, non-blocking.** Render is operational *per the owner's standing ruling* — that is the owner's statement, not a reading taken by this reconciliation, which could not reach the host. The payment reminder is acknowledged by the owner and will be handled by the owner. It is **not** a blocker for work, reviews, merges, or the roadmap. **Do not restate or escalate it.** Raise Render again only on verified service degradation, suspension, failed deployment, health-check failure, or production impact.

## Merge order

The previous order (L1 `#1398` → L7 `#1402` → L2 `#1389`) is **spent**: its first two entries are merged.

1. **The identity-ownership track continues** on the chat and onboarding paths — `#1409`, `#1410`, `#1405`. They work in the same area and are sequenced by the Controller, not by this file.
2. **L2 `#1389`** — its blocker has cleared. It needs a rebase onto `ca266366` before anything else; every SHA in its body predates four merges.
3. Everything else stays deferred under `DEC-20260723-001`.

The forward engineering sequence (PR1 → PR5, beginning with the Chat Job Provenance Contract) lives in `ENGINEERING_ROADMAP.md` under Phase 2 — Hardening. It is **not** duplicated here: this file carries current control state, not forward plans.

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

L1's identity-ownership batch is complete and merged (70c2af7c, 701939fa,
ca266366). The track continues on the chat and onboarding paths in #1409,
#1410 and #1405.

L2 (#1389) is unblocked and must rebase onto ca266366 before anything else.

No merge, no deploy, no database mutation, no real-CV upload, and no bulk Neon
branch deletion is authorized by this document.
```

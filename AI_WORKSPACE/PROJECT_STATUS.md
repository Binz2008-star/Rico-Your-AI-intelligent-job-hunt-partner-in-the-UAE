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

## Reconciliation — 2026-07-25 (evening)

### Verified control snapshot

| Field | Value | How it was established |
| --- | --- | --- |
| `main` | `e433c7d` | Verified from the API this session |
| Deployed backend `/version` | `e433c7d` — matches `main` | Owner-reported |
| Backend `/health` | OK; all three job providers healthy; reasoning provider non-degraded | Owner-reported |
| Application/runtime baseline | `e433c7d` — the deployed tree and the repository head agree | Verified from the API |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired | Unchanged |

### Merged this cycle

| PR | Merge commit | Deploy | Why that is correct |
| --- | --- | --- | --- |
| `#1388` log-privacy ratchet | `592cb46` | **No deploy fired** | It touches no runtime path — CI mechanism only. A deploy would have been noise, not safety |
| `#1382` account-data routing | `e433c7d` | **Deploy fired and verified** | It changes request handling, so it must reach production and be confirmed there |

### Production smoke on `e433c7d`

Three of three classes passed:

1. An ownership-qualified account question was answered from the database, with reconciled counts.
2. A CV file-list question was answered deterministically from the file store.
3. A general documents question was answered by the model **without listing any personal file**.

**Evidence class: verified by the owner through the proxy in a browser session. There is no automated artifact.** That is stated plainly because it decides how much the result can carry: it is real evidence of live behaviour and it is not a regression gate. Nothing may cite this smoke as a substitute for a test.

## Active PRs — heads verified from the API this session

| Lane | PR | Branch | Head | Base | State |
| --- | --- | --- | --- | --- | --- |
| L1 identity ownership | `#1398` | `fix/identity-ownership-resolution` | `63749d3d` | `e433c7d` | Draft — **blocked by the owner** |
| L2 CV and documents | `#1389` | `claude/cv-pending-artifact-confirm` | `878c5944` | `e433c7d` | Draft — sole writer |
| L4 workflow-trigger checker | `#1400` | `claude/workflow-guard-pr-target` | `0548e424` | `e433c7d` | Draft |
| L5 documents domain contract | `#1399` | `claude/arch-v2-phase1-contract-6mqzlv` | `3705d1eb` | `e433c7d` | Draft — approved direction |
| L7 docs-only design extraction | `#1401` | `claude/design-handoffs-incoming-extract` | `d4bd5469` | `e433c7d` | Draft |
| superseded | `#1371` | `claude/command-visual-polish-51dq2z` | `4e7b82f6` | stale | Superseded by `#1401`; **the owner closes it** |

Older Draft PRs (`#1374`, `#1370`, `#1362`, `#1359`) remain deferred under the trust-first freeze. An open PR is not permission to merge.

**Exact-head CI, `#1401` at `d4bd5469`: settled green.** `postgres-integration` failed once on that head from a container-registry pull failure (`Docker pull failed with exit code 1`, retried with backoff), with no test executed, and **passed on re-run attempt #2 at the same SHA** (check-run `89728253310`, 22:19:56 → 22:21:09). All eleven checks are now green at `d4bd5469` **with no content change** — both ratchet jobs included. The transient-registry explanation is therefore proven on the head itself, not inferred from another commit.

### CI evidence rule

**A passing job on a different commit is not exact-head evidence and may never be cited as one.** Transience is established by the failed run's own annotation — here, a Docker pull failure retried with backoff, which is registry infrastructure and not the change — and it is settled only by a re-run recorded against the same head. A re-run that goes green with no content change is the clean form of that proof: it isolates infrastructure from the diff.

This rule is written down because this lane's reporting made exactly that mistake — citing a green from a later, different commit as if it settled a failure on `d4bd5469` — and the owner caught it.

### Drift found and corrected during this reconciliation

Recorded because a control plane that hides its own corrections cannot be trusted:

- **L5 branch name.** Carried as `claude/arch-v2-phase1-contract`; the live branch is `claude/arch-v2-phase1-contract-6mqzlv`. The live name is authoritative.
- **L5 head.** Carried as `c2a4dbf`; the live head is `3705d1eb`. The live head is authoritative, and any lane check against `c2a4dbf` would have compared against a commit that is not the tip.
- **L4 PR number.** Not previously carried; it is `#1400`.
- **L2 head.** Carried as "`7e707c8` or newer"; live is `878c5944`, which satisfies it.

## Merge order

1. **L1 `#1398`** — blocked until all five owner conditions hold. Nothing merges ahead of identity ownership.
2. **L2 `#1389`** — after L1, because it is the largest behavioural surface in flight.
3. **L5 `#1399`** — contract work; direction approved, traceability must map to a roadmap that exists in `AI_WORKSPACE/`.
4. **L4 `#1400`** — must report which existing PR heads a stricter checker would break **before** it is pushed further.
5. **L7 `#1401`** — docs-only, no runtime effect, mergeable independently whenever the owner chooses.

## Stop conditions

Stop and report instead of guessing when:

- another writer holds the lease on the same branch or objective;
- a branch contains commits not explained by its continuity record;
- a PR scope expands across unrelated objectives;
- a schema diff appears where no migration was approved;
- a check is green only because the relevant test is outside CI;
- production mutation, billing, access-control, secret, migration, merge, or deployment action lacks explicit owner authorization;
- a UI claim is not derived from a current server read;
- a user-data workflow would require another real upload merely to test an unverified fix.

## Next exact action

```text
Per lane, read the continuity block in AI_WORKSPACE/TASKS.md, confirm the lease is
yours, fetch the remote, and compare the remote head against the expected head
recorded there before any push.

L1 stays blocked until the owner's five conditions hold.
L4 reports its breakage list before pushing further.

No merge, no deploy, no database mutation, no real-CV upload, and no bulk Neon
branch deletion is authorized by this document.
```

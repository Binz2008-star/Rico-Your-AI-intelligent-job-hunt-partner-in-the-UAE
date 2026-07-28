# Project Status — Rico AI

> **Mandatory control panel.** Every agent must read this file before planning or writing.
>
> Live GitHub `main`, exact PR heads, CI/deployment evidence, Neon state, and production smoke evidence override prose. When this file conflicts with live evidence, stop implementation and reconcile this file first.

## Document contract

- **Why it exists:** one current, evidence-backed operating snapshot for Rico.
- **Update when:** production, active ownership, launch blockers, or priority order changes materially.
- **Source of truth:** this file for current control state; `AI_WORKSPACE/DECISIONS.md` for binding decisions; `AI_WORKSPACE/TASKS.md` for lane history and continuity; `AI_WORKSPACE/ENGINEERING_ROADMAP.md` for the forward sequence; `AI_WORKSPACE/ARCHITECTURE.md` for structural rules.
- **Owner:** Rico owner, with the acting CTO/session responsible for evidence-backed reconciliation.
- **History:** prior snapshots remain preserved in Git history. This file carries current truth rather than duplicating historical narratives.
- **SHA rule:** fetch `main` live. A SHA recorded here is a verified snapshot, not a permanent claim about future `main`.

## Rule of authority

1. GitHub `main`, exact PR heads, and deployed `/version` evidence.
2. This file.
3. Lane continuity in `AI_WORKSPACE/TASKS.md`.
4. The latest dated handoff.
5. Everything else.

A passing check from another commit is not exact-head evidence. A deployment status is not a product smoke. An open PR is not merge authorization.

## Current reconciliation — 2026-07-29, post-`#1432` batch

### Verified repository state

| Item | Verified state |
| --- | --- |
| `main` at this pass | `3fa214a2b6631d2f73d0980f7700983550dce717` |
| `#1433` | **MERGED** as `24ee04d362be561bb761f7951d1f43bb90fbd051`; docs-only control-plane reconciliation |
| `#1432` | **MERGED** as `3fa214a2b6631d2f73d0980f7700983550dce717`; Arabic-normalized gratitude guard |
| `#1431` | **CLOSED WITHOUT MERGE**; explicit-city widening and provider-budget questions require a fresh, smaller redesign from current `main` |
| `#1413`, `#1374`, `#1362`, `#1359` | **CLOSED WITHOUT MERGE** as stale, deferred, superseded, or mixed-scope work |
| `#1389` | The only open PR; **Draft and on owner HOLD**, head `4f2abe60c5ec03fd3ed399bbc5dab5ee7a081bbe` |

The closed branch histories remain available. Closing a PR did not authorize or validate its code.

### Delivered in this batch

#### `#1433` — control-plane reconciliation

- Records `#1430` as merged and `TASK-20260728-002` as completed.
- Opens `TASK-20260728-003` as evidence/rehearsal only.
- Marks evidence-branch existence, name, parentage, creation time, and extension as **owner-attested, not connector-verified**.
- Keeps credential handling behind the neutral Owner P0 reference.
- Preserves the separate owner-go-ahead blocker: connecting access does not itself authorize the first row-level read.
- Changed only four `AI_WORKSPACE/**` files; no runtime or database action.

#### `#1432` — gratitude must not redeem a pending search

- `_acknowledgement_key` now routes Arabic through the existing shared normalizer.
- `شكرا`, `شكراً`, `شكرًا`, and `شُكرًا` resolve to one gratitude decision.
- Pure gratitude does not dispatch another search and does not consume the pending offer.
- Genuine confirmations such as `yes`, `ok`, `تمام`, and `ماشي` still redeem.
- Instruction-bearing courtesy messages are not swallowed.
- The focused suite contains 47 hermetic cases; exact-head QA, frontend, Playwright, Postgres integration, enumeration, privacy, workflow-security, Vercel, and PR-branch checks passed before merge.

### Deployment and production verification

GitHub commit-status evidence for `3fa214a2` reported:

- Vercel — **success**.
- Railway service `thorough-energy - rico-api` — **success**.

This session did **not** independently read a production `/version` body or `/health` body and did not execute the authenticated pending-search/gratitude interaction. Therefore:

- deployment status is verified;
- the deployed commit identity is not independently endpoint-verified here;
- the changed production behavior is **not product-smoke verified**.

Do not use a green deployment badge as proof that the gratitude path executed.

### Neon boundaries

The ordinary PR-scoped Neon branches created automatically for `#1433` and `#1432` were deleted successfully by their PR-close workflows.

Those disposable PR branches are unrelated to the separately discussed D1 evidence branch.

For the D1 evidence branch, the following remain **owner-attested, not connector-verified**: existence, branch name, point-in-time parentage, creation timestamp, and extended expiry. Re-check in the Neon Console before relying on them.

`TASK-20260728-003` must not use production credentials. No production mutation, schema change, deletion, reassignment, or repair PR is authorized.

## Active work and leases

| Measure | Current state |
| --- | --- |
| Active implementation writers | 0 |
| Active documentation writers | 1 — this reconciliation branch only; lease ends on merge/close |
| Open implementation PRs authorized to proceed | 0 |
| Held PRs | `#1389` only |

The historical `TASK-20260728-004` and `TASK-20260728-005` continuity blocks describe closed/merged lanes. They carry no current lease or write authorization.

## Standing owner rulings

- **Trust-first remains binding.** No new feature expansion until reliability and truthful execution are repaired.
- **`#1389` remains HOLD.** Do not rebase, edit, mark Ready, merge, deploy, or use it as an implementation branch until the ownership-data decision is made.
- **No production row repair is authorized.** Assessment, mapping, and rehearsal findings do not authorize mutation.
- **Owner P0 credential rotation remains open and owner-controlled.** Agents must not receive or use production credentials for evidence work.

## Closed work that may be recut later

- **Thin-market zero recovery (`#1431`):** recut only after separating inherited/default location from an explicitly requested city. Automatic UAE widening is acceptable only for inherited/default location; explicit city scope requires truthful zero plus user permission to widen. Re-evaluate the extra provider call and remove undocumented directive language.
- **Design proposals (`#1362`, `#1359`):** recut as one objective per PR from current `main`, with current Atelier, EN/AR, accessibility, persistence, and screenshot evidence.
- **Infrastructure standby (`#1413`):** reopen only against a verified continuity requirement and the approved architecture.
- **Strategy proposal (`#1374`):** future strategy belongs in the current roadmap, not a parallel proposal document.

## Known residuals — recorded, not authorized

1. Journey-1 D1 ownership/data consolidation remains assessed but unrepaired; it is upstream of the `#1389` HOLD.
2. Journey-1 D2 pending-artifact activation remains held in `#1389`.
3. Journey-1 D4 mission/dashboard truth remains open.
4. Journey-1 D5 first-useful-result activation remains open.
5. Stored-CV state remains distributed across multiple gates in `src/rico_chat_api.py`.
6. The raw acknowledgement fast path may choose a generic reply for some normalized Arabic spellings; the merged spend-prevention contract is unaffected. Treat this as a copy-path nit unless new evidence shows behavioral impact.
7. Historical `TASKS.md` contains a non-operational markdown typo: `# 1349` instead of `#1349`. Accepted housekeeping debt; it does not alter current control state.

## Stop conditions

Stop and report instead of guessing when:

- another writer owns the same branch or objective;
- branch history contains unexplained commits;
- scope expands across unrelated objectives;
- a schema diff appears without an approved migration;
- a relevant test is outside CI while a check is claimed green;
- production mutation, billing, access-control, secret, migration, merge, or deployment action lacks explicit owner authorization;
- a UI or data claim is not derived from a current authoritative read;
- a user-data test would require another real upload merely to verify an unproven fix.

## Next exact action

```text
1. Run Tier-1 production verification for the current main:
   - read /version and confirm the served commit;
   - read /health and require status=ok;
   - confirm ricohunt.com is reachable.

2. Run one focused authenticated product smoke for #1432 without exposing tokens:
   - establish a pending search offer in a dedicated smoke account;
   - send standard Arabic gratitude "شكرًا";
   - prove no second search/provider dispatch occurs;
   - prove the pending offer remains available for a later explicit confirmation.

3. Record the production evidence. If either endpoint or the behavior fails,
   stop and open one narrowly scoped repair lane.

4. After the #1432 smoke is closed, return to the owner decision above #1389:
   secure evidence access and mapping/rehearsal first; no production repair.

No other merge, feature expansion, Neon mutation, or #1389 work is queued.
```

# Project Status — Rico AI

> **Mandatory control panel.** Every agent must read this file before planning or writing.
>
> Live GitHub `main`, exact PR heads, CI, Vercel/Render deployment evidence, Neon state, and production smoke evidence override prose. When this file conflicts with live evidence, stop implementation and reconcile this file first.

## Document contract

- **Why it exists:** one current, evidence-backed operating snapshot for Rico.
- **Update when:** production, active ownership, launch blockers, or priority order changes materially.
- **Source of truth:** this file for current control state; `AI_WORKSPACE/DECISIONS.md` for binding decisions; `AI_WORKSPACE/TASKS.md` for task-level continuity.
- **Owner:** Rico owner, with the acting CTO/session responsible for evidence-backed reconciliation.
- **History:** prior snapshots remain preserved in Git history. This file intentionally keeps current truth ahead of historical narrative.
- **SHA rule:** never make this document self-stale by claiming its own commit is the permanent current `main`. Fetch `main` live. Record the application/runtime baseline separately from docs-only control commits.

## Reconciliation — 2026-07-25

The previous snapshot said `main=45fa80c4` and zero open PRs. Both claims were stale. This reconciliation is based on direct GitHub, Vercel, Neon, CI, production screenshots, and owner-provided backend logs.

### Verified control snapshot

| Field | Current verified value |
| --- | --- |
| Repository | `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE` |
| GitHub control head | Fetch live at session start. `#1390` merged the control-plane reconciliation as docs-only commit `745e9714`; it does not change application runtime |
| Application/runtime baseline | `e26548bb` is the latest application tree on `main` before the docs-only control reconciliation |
| Latest application merges | `#1385` rate-limit configuration (`da5339c`), `#1387` first log-privacy sweep (`989f774`), `#1386` test-environment isolation (`e26548b`) |
| Vercel production | READY on application tree `e26548b`; no 5xx or warning/error runtime logs found in the inspected six-hour window |
| Render backend | Owner-verified at `989f774`; `#1386` is test-only, so a different backend runtime SHA is expected rather than deployment drift |
| Neon production | Project ready. CV preview branch exists and has **zero schema diff** from production; the current CV work requires no migration |
| Governing strategy | `DEC-20260723-001`: no new feature expansion until trust and execution reliability are repaired |
| Current product P0 | Issue `#1391`: one canonical CV upload/review/confirm/save journey across `/upload`, `/profile`, and `/command` |
| Current CI/security P0/P1 | Make privacy ratchet sound, remove unintended external network from tests, then move toward a trustworthy full-suite gate |
| Owner-only operations | Hosting account continuity/billing and database protection posture require owner review; sensitive configuration details are intentionally not recorded in this public repository |

## Production evidence that changes the plan

### CV upload is parsed but the product journey is split

Production evidence proves the backend parser can read the uploaded PDF and produce a good preview. The failure is the product state machine:

1. `/upload` can create a pending preview but historically retained only client state and discarded the authoritative handoff.
2. `/profile` reports upload success before confirmation and reloads an empty document inventory.
3. `/command` can render the preview while the generic chat path answers from different context and asks the user to upload again.
4. The same real file was uploaded repeatedly because the first pending operation was not recovered consistently across surfaces.

A read-only aggregate production audit also found material amplification of duplicate short-lived artifact rows for identical uploads, with many artifacts already corresponding to a saved document. Exact operational counts are intentionally not published. This makes a retention increase unsafe until duplicate amplification and periodic purge are resolved.

**Decision:** do not patch each surface independently. One server-authoritative pending-artifact contract must drive all three entry points. Explicit confirmation-before-save remains binding.

### CV work currently in flight

- Tracker: `#1391`
- Branch: `claude/cv-pending-artifact-confirm`
- Observed head: `c3effbae02a0e2f8ae885b6a32a408b0bf817164`
- Vercel preview: READY
- Neon preview branch: READY; schema diff from production is empty
- No implementation PR opened yet
- Current branch comparison: broader than the reported four-commit summary; it must be audited before PR creation
- Known blocker: the branch changes Command/Vault/backend state handling but does not yet prove the `/profile` upload entry uses the same orchestration
- Functional preview smoke is still unverified; static route HTTP 200 is not acceptance evidence
- TTL increase is blocked until duplicate-artifact amplification and scheduled purge are explicitly handled

**Required acceptance before merge:**

- one upload from each entry point produces the same server-backed pending contract;
- no `user_documents` row before confirmation;
- pending state survives navigation and refresh;
- chat never contradicts a visible preview or asks for a duplicate upload;
- `pending`, `already_saved`, `expired`, `absent`, and `unavailable` remain distinct;
- confirmation creates exactly one canonical document and is idempotent;
- repeated identical uploads cannot amplify retained full CV text without a bounded contract;
- My Files and Profile refresh from server read-back;
- no identity/security tests are weakened;
- authenticated preview smoke uses non-personal test data before production deployment;
- the owner's real CV is uploaded only once after merge, deploy, and `/version` verification.

## Open PR occupancy — verified 2026-07-25

| PR | State | Ownership / decision |
| --- | --- | --- |
| `#1388` differential log-privacy ratchet | Draft, CI green | **Blocked.** CTO review comment records three correctness/governance findings; keep Draft until resolved |
| `#1382` account-data routing | Draft | Stale base and overlaps trust-routing work; rebase and re-audit after current P0 |
| `#1374` differentiation proposal | Draft, docs-only | Defer; strategy already governed by trust-first decision |
| `#1371` design + production polish | Draft, currently non-mergeable | Mixed concerns and stale; split or close after P0 |
| `#1370` public pricing | Ready | Defer under feature freeze and unresolved billing activation/operations |
| `#1362` Command prompt hints | Draft | Cosmetic; defer until trust P0 closes |
| `#1359` warnings palette + theme persistence | Ready | Mixed objectives; split/rebase/review later |

An open PR is not permission to merge. Exact-head review, CI, overlap, production impact, rollback, and documentation must be re-verified before every merge.

## #1388 — merge blockers

The current head is green, but green CI does not prove the ratchet is sound.

1. **Rule weakening:** HEAD rules are used to scan both base and head. Weakening the rule vocabulary can blind both scans. Required design: base-rule comparison to prevent weakening plus head-rule comparison to activate new protections.
2. **Zero-debt end state:** a base scan with zero findings must be valid, not `CANNOT RUN`, provided source discovery and strict parse/decode checks succeeded.
3. **Truthful governance:** major action tags are not immutable SHA pins; documentation must not claim pinned refs unless exact SHAs are used. Detection and Required-check merge enforcement must be stated separately.

No call-site remediation belongs in this mechanism PR.

## Newly verified infrastructure and test risks

### Neon

- CV preview schema matches production exactly; no migration is justified for the current CV fix.
- Read-only aggregate checks found no primary-CV uniqueness violation and no expired artifact backlog at inspection time.
- Duplicate live artifacts exist and must be handled before longer retention is approved.
- Preview-branch accumulation exists across old branches. Do not mass-delete blindly. First produce a dry-run inventory mapped to open PRs/deployments, TTL, and branch ownership, then remove only proven-orphaned branches.
- Production branch protection and connection controls require an owner-only settings review. Exact posture is not published here.
- No application query-performance blocker was found in the inspected query statistics; observed application queries were below the requested slow-query threshold.

### Vercel

- Current production and the CV/ratchet previews are READY.
- No inspected production 5xx/error/warning events were found in the scoped runtime-log query.
- One isolated 404 was for `/design-preview`; no production 5xx pattern was found.
- Static page success is not a functional smoke test for authenticated CV APIs.
- CV preview build has one framework warning about edge runtime disabling static generation for a page; it is not currently a build failure but should be attributed before merge if the changed route caused it.

### Test network isolation

Measured full-suite evidence found unintended outbound calls to job providers and integration APIs. Some tests remain green even when those calls fail, so they generate traffic without test signal. A third-party Indeed adapter also disables TLS verification on a reachable path.

Required sequence:

1. block external TCP/HTTP by default while temporarily allowing DNS needed by SSRF tests;
2. mock JobSpy/Bayt/Telegram/Hugging Face at service boundaries;
3. make link-verifier DNS deterministic with an injected resolver;
4. then block external DNS too;
5. isolate any deliberate live integration into a scheduled/manual non-blocking workflow;
6. resolve the known Arabic test flake independently — network evidence shows it performs no external calls;
7. run the complete suite as a shadow gate before making it Required.

## Current execution order

1. **Owner:** resolve hosting account continuity/billing warning.
2. **CV P0 / #1391:** finish one canonical CV orchestration; audit branch commit history, add the missing Profile entry-point behavior, and control duplicate artifact retention before opening a Draft PR.
3. **Privacy gate:** fix the three `#1388` blockers; keep Draft and rerun exact-head checks.
4. **Test trust:** create the external-network isolation PR, then deterministic DNS PR, then flake investigation.
5. **Log privacy:** after the ratchet is sound and Required, continue remediation in functional batches plus a separate runtime egress sanitizer.
6. **Database operations:** review protection settings privately and create a non-destructive preview-branch cleanup inventory.
7. **Backlog:** rebase, split, close, or defer older PRs; do not merge cosmetic/new-feature work ahead of trust P0.
8. **Production acceptance:** full authenticated EN/AR/mobile smoke only after exact deployment SHAs are known.

## Stop conditions

Stop and report instead of guessing when:

- another writer owns the same objective or files;
- a branch contains commits not explained by its continuity record;
- a PR scope expands across unrelated objectives;
- a schema diff appears where no migration was approved;
- a check is green only because the relevant test is outside CI;
- production mutation, billing, access-control, secret, migration, merge, or deployment action lacks explicit owner authorization;
- a UI claim is not derived from a current server read;
- a user-data workflow would require another real upload merely to test an unverified fix.

## Next exact action

```text
CV owner: work from #1391. Audit the branch range against current main, explain
every commit, wire `/profile` into the same server-authoritative pending contract,
control duplicate full-text artifact amplification, run backend baselines, and
open a Draft PR only when all three entry points share one state machine.

Privacy owner: address the three blocking findings recorded on #1388 and keep the
PR Draft.

No production deploy, database mutation, real-CV upload, or bulk Neon branch
deletion is authorized by this status document.
```

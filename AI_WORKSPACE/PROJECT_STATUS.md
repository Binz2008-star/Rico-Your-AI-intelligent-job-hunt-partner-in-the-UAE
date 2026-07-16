# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, ChatGPT, or other agent must read this file before planning or writing.**
>
> Live GitHub `main`, open PR heads, CI, deployed `/version`, and production smoke evidence override stale prose. If this file conflicts with live state, implementation stops until the control plane is reconciled.

## Verified control snapshot

| Field | Current value |
| --- | --- |
| Repository | `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE` |
| Snapshot date | 2026-07-16 |
| Live-main baseline audited | `27df7ba6` (#1022 squash-merge); agents must fetch and report the exact current SHA at session start |
| Control-plane PR #1010 | **MERGED** `b753885` (2026-07-13) — the reconciliation freeze it imposed is over |
| Active objectives | Two owner-directed, non-overlapping tracks: (1) Atelier full-site migration **REOPENED by owner 2026-07-14** — Step 2 slice 4a via PR #1028; (2) Rico Intelligence Phase 1 — ADR-001 **ACCEPTED** on #1024; M1 shadow-write PR #1025 (stops before merge) |
| Runtime writers | UI track: **Claude is writer on #1028** (owner directive; Windsurf reviewer-only). Memory track: #1025 draft only, no merge authority |
| Production access state | **Teaser/access gate REMOVED** (`96b7efd`) — the full site is open; waitlist retired; landing plays one of 3 launch films at random (#1019) |
| Billing | **Paddle merged** (#1008 `1b1748c` + follow-up fixes `d05ca08`/`30ebb7d`/`c11575d`, Sandbox mode). One plan "Rico Monthly" — **USD 21.50/mo is the authoritative price** (`403c28b`); AED 79 is a reference display note only. **#1022 MERGED** (`27df7ba6`) — Setup-level eventCallback fix production-verified (open/close/reopen smoke PASS). Paddle billing NOT activated in production (`NEXT_PUBLIC_BILLING_MODE=""`). Sandbox checkout URL configured in Paddle dashboard. Architecture debt: hardcoded fallbacks still present (separate PR planned) |
| Invitation target | Branded secure email invitations; not started, not production-verified |

## Current execution lock

```text
ACTIVE NOW (owner-directed, two non-overlapping tracks)
1. Atelier full-site migration — REOPENED by owner 2026-07-14
   (supersedes the #1023 closure record; docs flip is PR #1027, in review).
   Step 1 (preview-route hygiene, F-4) DONE via #1026 (merged 21ae19a7).
   Step 2 slice 4a (Atelier CommandComposer): PR #1028 — the SOLE active
   UI implementation PR. Claude is writer; Windsurf is reviewer-only.
   #1029 is CLOSED without merge — technical reference only.
2. Rico Intelligence Phase 1 — ADR-001 (Career Memory Engine) ACCEPTED
   by owner on #1024 (rev 2, head ef66ebfa). M1 = PR #1025 (additive
   schema + shadow MemoryWriter, flag RICO_MEMORY_ENGINE_ENABLED default
   OFF). Owner scope: M1 ships as a draft and STOPS BEFORE MERGE.

GATES
- #1028 needs its EN/AR desktop+mobile visual gate before leaving draft,
  then owner merge approval.
- #1022 (Paddle split B — Setup-level eventCallback) **MERGED** `27df7ba6`
  after Sandbox open/close/reopen smoke PASS. Full payment/webhook/entitlement
  testing deferred to isolated staging track (separate Render + Neon branch).
- Migrations 040/041 (Paddle) application state on Neon production is NOT
  verified in this snapshot; verify drift check before relying on them.

HOLD
- #996 mixed-scope pitch/explainer/waitlist bundle
- #988 CI bot-comment housekeeping
- #967 pre-launch gate/waitlist (obsolete in intent — the site is now open;
  requires an owner decision to close or repurpose)
- #965 journey-state seed (owner ruling: becomes a Memory Engine projection)

REVIEW QUEUE
- #1027 docs reopen (merge to make main's program doc match owner direction)
- #1024 ADR-001 decision artifact (accepted; merge records it)
- #989 subscription-audit follow-ups (reconcile against merged #1008)
- #1002 settings "Discuss with Rico" honesty labels
- #1016 /queue auth guard (guard-only; coordinate merge-then-migrate vs
  supersede with a full /queue Atelier PR per program Step 3)

REFERENCE ONLY / DO NOT RESUME
- #1029 (closed composer attempt), #961, #935, #872, #873
- #997/#987/#985/#968 are no longer open — do not resurrect
```

## Recent main reality (de8ce666 → 27df7ba6, 2026-07-14 → 07-16)

Merged/landed since the previous 2026-07-13 snapshot — agents must not plan from it:

- **#1010** control-plane reconciliation (`b753885`).
- **#1008 Paddle Billing end-to-end** (`1b1748c`): checkout attribution server-owned, stale-event guard, single Rico Monthly plan, grace period, migration 040 drift checks, `GET /api/v1/billing/config` health endpoint, webhook reprocessing. Follow-up direct fixes on main: default public web checkout to Paddle, Sandbox checkout defaults, force Paddle on public web.
- **Price contract**: USD 21.50/mo authoritative; AED 79 note is display reference.
- **Teaser gate removed — full site open** (`96b7efd`).
- **Atelier merges**: #1012 `/applications`, #1013 `/profile`, #1015 `/upload`, #1017 foundation (route matrix, canonical nav, `/dashboard` unblocked, orphaned teaser-gate test removed — F-1/F-2), #1020 authenticated `/command` → WorkspaceShell rail (shell only), #1021 `/subscription` Atelier UI (split A of closed #1018).
- **#1019** landing opening films + waitlist retirement.
- **#1023** program-closure docs (now superseded by the owner's 2026-07-14 reopen — see #1027).
- **#1026** internal preview routes (`/design-preview`, `/rico-preview`, `/sandbox/*`) 404 in production (F-4).

## Open PR control

Fresh snapshot 2026-07-15 (12 open PRs) — `OPEN_PR_TRIAGE_2026-07-13.md` is retained as the historical 07-13 snapshot:

| PR | Subject | Classification |
| ---: | --- | --- |
| #1028 | Atelier CommandComposer (Step 2 slice 4a) | **ACTIVE** — sole UI implementation PR; visual gate before leaving draft |
| #1027 | docs: reopen full-site Atelier migration, refreshed gap matrix | REVIEW |
| #1025 | Memory Engine M1 — additive schema + shadow MemoryWriter | ACTIVE-DRAFT — owner scope: stops before merge |
| #1024 | ADR-001 Career Memory Engine + Phase 1 program file | REVIEW — ADR accepted at `ef66ebfa` |
| #1022 | Paddle Setup-level eventCallback (split B of #1018) | **MERGED** `27df7ba6` — production-verified |
| #1016 | /queue auth guard | REVIEW — coordinate with program Step 3 |
| #1002 | settings honesty labels | REVIEW |
| #989 | subscription-audit follow-ups | REVIEW — reconcile with merged #1008 |
| #996 | pitch/explainer/waitlist bundle | HOLD — mixed scope |
| #988 | hide noisy bot comments workflow | HOLD — non-launch housekeeping |
| #967 | pre-launch gate/waitlist | HOLD — intent obsolete (site is open); owner decision to close |
| #965 | journey-state seed | HOLD — superseded in direction by ADR-001 |

An open PR is not permission to resume it.

## Mandatory session behavior

Every session follows `AI_WORKSPACE/DAILY_AUTOPILOT.md` after the canonical `OPERATING_RULES.md` boot sequence.

It must:

1. complete the canonical document read order;
2. fetch exact live `main`;
3. inspect open PR ownership and overlap;
4. build an occupancy table;
5. declare authority role and activity pass;
6. choose the highest-priority safe unowned task;
7. claim the task before writing;
8. avoid generic “what would you like me to do?” openings when repository state provides the answer.

## Launch path

`AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md` predates the owner's decision to open the site; access is **already open** (teaser gate removed, waitlist retired). What remains from that plan, reconciled to reality:

```text
[done] control plane        — #1010 merged
[done] open access          — teaser gate removed 96b7efd
[done] billing fix         — #1022 merged; eventCallback smoke PASS
[open] billing verification — full payment/webhook/entitlement test on
                              isolated staging track (separate Render + Neon);
                              then owner decision on live activation
[open] architecture debt    — remove hardcoded Paddle fallbacks, fail-closed on
                              missing env vars, separate PR (not #1022)
[open] invitations          — not started
[open] launch smoke         — full production smoke after billing verification
```

Do not reorder or combine billing/auth/email/database/design work into one PR.

## Safe agent allocation

| Session | Allowed default role |
| --- | --- |
| UI implementation account | WRITER only via #1028 (or the next claimed program slice after it merges) |
| Backend/billing implementation account | WRITER for one claimed backend/billing/invitation PR only |
| Independent account | REVIEWER or RELEASE |
| Windsurf/OneSurf/local tooling | focused verifier; **reviewer-only on #1028**; no foreign-branch edits |
| Codex | review signal only |
| Lovable | design/reference only unless explicitly assigned a production UI PR |

Parallel writers are allowed only for explicitly recorded non-overlapping tracks with separate files/contracts and no shared migration or auth surface. The two active tracks (#1028 UI, #1025 memory) satisfy this: no shared files, no shared migrations.

## Stop conditions

Stop and report instead of guessing when:

- live state conflicts with this file;
- another writer owns the objective or branch;
- an unclassified PR overlaps the proposed files;
- work expands into billing, auth, email, database, deployment, or production smoke outside the approved task;
- a migration number or contract conflicts;
- production mutation, merge, deploy, or opening access is required without owner approval;
- the session approaches a context/tool/time limit without updating continuity.

## Next exact action

```text
1. Owner: merge the #1027 docs reopen so main's program doc matches direction;
   merge #1024 to record the accepted ADR-001.
2. UI track: run the #1028 EN/AR desktop+mobile visual gate; on pass, owner
   merge approval; then cut slice 4b from latest main.
3. Billing track: #1022 MERGED and production-verified. Next: rotate exposed
   Paddle Sandbox webhook secret (security PR); then isolated staging track
   for full payment/webhook/entitlement testing. Architecture debt (remove
   hardcoded fallbacks) as a separate PR after security work.
4. Memory track: finish #1025 to its stop-before-merge boundary; owner review.
5. Housekeeping: owner decision on #967 (obsolete intent) and the REVIEW queue
   (#989, #1002, #1016).
```

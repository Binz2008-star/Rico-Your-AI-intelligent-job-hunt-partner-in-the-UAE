# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, ChatGPT, or other agent must read this file before planning or writing.**
>
> Live GitHub `main`, open PR heads, CI, deployed `/version`, and production smoke evidence override stale prose. If this file conflicts with live state, implementation stops until the control plane is reconciled.

## Reconciliation note (2026-07-23)

This file was last verified 2026-07-18 and had gone stale — it still described
a "containment" freeze and listed 6 open PRs, none of which were actually
open anymore (3 merged, 3 closed; verified individually via `gh pr view`
below). Reconciled against live `main`, live open PRs, and live Render
`/version` on 2026-07-23. **The old containment posture (2026-07-16) is
superseded** — see `DEC-20260723-001` below, the current binding priority
order.

## Verified control snapshot

| Field | Current value |
| --- | --- |
| Repository | `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE` |
| Snapshot date | 2026-07-23 |
| Live-main baseline | **`d5b020e0`** (fetched from `origin/main` 2026-07-23; agents must re-fetch and confirm the exact current SHA at session start — do not trust this number after today) |
| Deployed (Render) | Confirmed matching — `GET /version` returned `commit=d5b020e0`, `started_at=2026-07-23T18:24:25Z` (fresh boot, same session). Backend and `main` are in sync. |
| Governing strategy | **`DEC-20260723-001`** (`AI_WORKSPACE/DECISIONS.md`) — CEO verdict, trust-first commercial strategy: **no new features until trust/execution reliability is fixed.** #1336 (CV/search-integrity) is explicitly named as a Days 0–30 priority, not just an engineering preference. Full text: `docs/strategy/2026-07-23-ceo-verdict-strategy-positioning.md`. |
| Merged 2026-07-23 (10 commits since the 2026-07-18 `96464b8e` baseline — see table below) | `#1343` #1336 PR1 (fail-closed city write-boundary), `#1345` Arabic CV-status-text city rejection, `#1340` #1075 atomic draft decisions, `#1341` #1096 billing quota fail-open→fail-closed, `#1342` #1074 atomic checkout attribution, `#1338` #1097 canonical safe job URLs, `#1339` #1095 scanner-safe email verification, `#1138` #1072 per-user `auth_version` JWT invalidation, `#1230` image-attachment CV-quota exemption, `#1344` DEC-20260723-001 doc. |
| Open PRs (verified via `gh pr list --state open`, 2026-07-23) | Only **3**: `#1347` (#1314 ack-loop recurrence fix), `#1348` (#1336 PR2, CV/search-continuity), `#1346` (draft — Claude Code skills tooling, unrelated to the product). **None of the 6 PRs previously listed as open are still open** — verified individually: `#1062` MERGED, `#1055` MERGED, `#965` MERGED, `#1025` CLOSED (not merged), `#1002` CLOSED, `#988` CLOSED. |
| #1336 status | **PR1 merged+deployed** (`956130d1`→`#1343`). **PR2 open, not merged** (`#1348`) — CV/search-continuity defects from a new authenticated production transcript (role↔location bleed, unrecognized Arabic execute/broaden commands, CV-status-question routing). A related but separate fix landed same-day: `#1345` (Arabic CV-status text added to the city-rejection token bank in `city_validation.py` — complementary to, not a duplicate of, `#1348`'s role-noun rejection). |
| #1314 status | Two of four recurrences of the typed-YES pending-confirmation loop were already fixed on `main` (`_resolve_pending_intent`, `answer_conversationally`). Two more recurrences (acknowledgement-replies fast path, `follow_up_confirmation` legacy-intent dispatch) fixed in open, unmerged `#1347`. |
| Billing (Paddle) | Merged (#1008 + follow-ups), **still NOT activated in production** (`NEXT_PUBLIC_BILLING_MODE=""`). Single plan "Rico Monthly," USD 21.50/mo authoritative. `#1341`/`#1342` (2026-07-23) hardened quota fail-closed behavior and checkout-attribution atomicity — architecture debt (hardcoded fallbacks) not yet addressed in a dedicated PR. |
| Design system | Atelier V3 remains the sole production system (`DEC-20260716-001`). `#1062` (MATCH job cards) is now **merged** — no longer held. |
| Gmail M0 (`#1055`) | **Merged** (previously listed as draft/held under containment). Flag/activation state (`RICO_ENABLE_GMAIL_SYNC`) **not independently re-verified in this pass** — do not assume live-active without checking Render env directly. |
| Memory Engine M1 (`#1025`) | **Closed, not merged.** Superseded in direction (as the old snapshot itself anticipated) — do not resume from the closed branch without owner direction. |
| Journey state (`#965`) | **Merged** (previously listed as a stale "close candidate" draft). |

## Current priority (DEC-20260723-001 — supersedes the 2026-07-16 containment plan below)

```text
GOVERNING RULE: no new features until trust + execution reliability is fixed.
Trust engine is the moat: no invented jobs, no false execution claims, one
canonical active CV, consistent profile state, explicit approval before
external actions.

Days 0–30 (current window, 2026-07-23 start): close #1336 slices (PR1 done,
PR2 open #1348), canonical CV inventory, eliminate ungrounded generation,
fail-closed billing/quota (in progress: #1341/#1342 merged), atomic checkout
attribution (#1342 merged), analytics, smoke tests, AI_WORKSPACE sync
(this reconciliation).

Days 31–60: founder cohort of 50-100 users proves payment.
Days 61–90: repeatable acquisition — only after retention is proven.

Full text and scale/margin gates: docs/strategy/2026-07-23-ceo-verdict-strategy-positioning.md
Decision record: AI_WORKSPACE/DECISIONS.md → DEC-20260723-001
```

### Follow-ups DEC-20260723-001 itself flagged, not yet done

- `AI_WORKSPACE/CURRENT_STATE.md` narrative is also stale (last header
  2026-07-18) — this reconciliation only covers `PROJECT_STATUS.md`
  (this file). A separate pass is still needed for `CURRENT_STATE.md`,
  `ROADMAP`, and `TASKS.md` to fully agree.
- Concrete Free/Pro/Premium pricing points — owner decision still pending;
  implemented billing remains single-plan Rico Monthly USD 21.50.

## Superseded — 2026-07-16 containment plan (historical, do not resume from this)

Everything below this line was the active plan as of 2026-07-16 evening. All
of its numbered steps completed or were overtaken by events; it is kept only
as history. **Do not treat any of it as current instruction** — see
`DEC-20260723-001` above instead.

```text
ACTIVE NOW (owner containment plan, 2026-07-16 evening — sequence, do not skip)
1. SECURITY CONTAINMENT (owner action): rotate ALL credentials in the local
   `rico-job-automation-api.env` — status not re-verified in this pass.
2. SOURCE-OF-TRUTH UNIFICATION — superseded by this 2026-07-23 reconciliation.
3. FREEZE new-integration activation — LIFTED. #1062, #1055, #965 all merged
   since; #1025 closed. DEC-20260723-001 is the current governing rule.
```

## Open PR control (live, 2026-07-23)

| PR | Subject | Classification |
| ---: | --- | --- |
| #1348 | #1336 PR2 — CV/search-continuity defects from production transcript | Open, self-reviewed, tested, **not merged** — awaiting owner review |
| #1347 | Two more #1314 typed-YES ack-loop recurrences | Open, self-reviewed, tested, **not merged** — awaiting owner review |
| #1346 | Claude Code skills tooling install (draft) | Unrelated to the product codebase — not a Rico feature/fix |

An open PR is not permission to merge or resume it without the owner.

## Launch path (carried forward from the 2026-07-18 snapshot — NOT re-verified in this pass)

The previous snapshot tracked these as still-open. This reconciliation did
**not** independently verify their current state — do not assume any of them
are done without checking live evidence first (Paddle dashboard, `gh`,
production smoke):

```text
[unverified] billing verification — full payment/webhook/entitlement test on
                                     isolated staging track; then owner
                                     decision on live activation
[unverified] architecture debt      — remove hardcoded Paddle fallbacks,
                                     fail-closed on missing env vars
                                     (#1341/#1342 2026-07-23 improved
                                     fail-closed behavior for quota/checkout
                                     specifically — may partially cover this)
[unverified] invitations            — branded secure email invitations
[unverified] launch smoke           — full production smoke after billing
                                     verification
```

## Mandatory session behavior

Every session follows `AI_WORKSPACE/DAILY_AUTOPILOT.md` after the canonical `OPERATING_RULES.md` boot sequence.

It must:

1. complete the canonical document read order;
2. fetch exact live `main` (do not trust the SHA in this file beyond today);
3. inspect open PR ownership and overlap — verify each listed PR's actual state via `gh pr view`, not just this table;
4. build an occupancy table;
5. declare authority role and activity pass;
6. choose the highest-priority safe unowned task, weighted by `DEC-20260723-001` (reliability/trust work over new features);
7. claim the task before writing;
8. avoid generic "what would you like me to do?" openings when repository state provides the answer.

## Stop conditions

Stop and report instead of guessing when:

- live state conflicts with this file;
- another writer owns the objective or branch (this repo has repeatedly shown concurrent agents committing to the same branch in the same session — check `git reflog` / `git log` for commits you didn't make before assuming a clean state);
- an unclassified PR overlaps the proposed files;
- work expands into billing, auth, email, database, deployment, or production smoke outside the approved task;
- a migration number or contract conflicts;
- production mutation, merge, deploy, or opening access is required without owner approval;
- the session approaches a context/tool/time limit without updating continuity.

## Next exact action

```text
Per DEC-20260723-001, Days 0-30 reliability sequence:
1. #1348 (#1336 PR2) and #1347 (#1314 recurrences) — open, owner review pending.
   Do not merge without explicit owner approval.
2. Canonical CV inventory work (named in DEC-20260723-001, not yet started as
   a tracked PR as of this snapshot).
3. Eliminate ungrounded generation elsewhere in the router (same defect class
   as #1336; #1348 fixed the transcript-specific instances, not necessarily
   all instances repo-wide).
4. CURRENT_STATE.md / ROADMAP / TASKS.md reconciliation (flagged by
   DEC-20260723-001 as a separate follow-up, not done in this pass).
5. Full production smoke gate (CV, login persistence, attachments,
   applications, billing sandbox, AR + mobile) — still not started per the
   last verified snapshot; re-verify before assuming it remains outstanding.
```

# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, ChatGPT, or other agent must read this file before planning or writing.**
>
> Live GitHub `main`, open PR heads, CI, deployed `/version`, and production smoke evidence override stale prose. If this file conflicts with live state, implementation stops until the control plane is reconciled.

## Verified control snapshot

| Field | Current value |
| --- | --- |
| Repository | `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE` |
| Snapshot date | 2026-07-13 |
| Live-main baseline audited | main included `b66eb46fe16f826bdbb9ef5466d2d0d60472c2a9` (`#1005`) before this control-plane branch; agents must fetch and report the exact current SHA at session start |
| Active control-plane PR | `#1010` on `chore/agent-control-plane-reconciliation` |
| Active objective | Reconcile coordination, classify open PRs, and establish the launch execution sequence before more runtime work |
| Runtime writer | None authorized until #1010 is independently reviewed/merged and the first launch task is claimed |
| Production access state | Teaser/access gate remains in place; opening access requires the launch gate and owner approval |
| Billing target | One plan: Rico Monthly — AED 79/month; implementation not yet production-verified |
| Invitation target | Branded secure email invitations; implementation not yet production-verified |

## Current execution lock

```text
ACTIVE NOW
Control-plane reconciliation only:
- live/open-PR inventory
- daily agent autopilot
- launch execution plan
- updated cold-start instructions
- continuity/review evidence

NEXT — AFTER #1010 IS REVIEWED/MERGED
1. Route/design parity inventory against current production + approved reference.
2. Launch-critical UI completion through small route-group PRs.
3. Independent AED 79/month billing track.
4. Independent user-invitation email track.
5. Full launch smoke, rollback readiness, and owner approval to open access.

HOLD
- Paddle PR #1008 until deep billing/security/contract review against #989
- mixed-scope pitch/explainer/waitlist work (#996)
- pre-launch gate/waitlist implementation (#967) until explicitly resumed and migration state reconciled
- journey-state follow-on (#965/#968)
- any broad autonomous-agent implementation

STALE / DO NOT RESUME
- #997 (superseded `/settings` migration)

REFERENCE ONLY / NOT FOR MERGE
- #961 autonomous loop
- #935 old command proposal
- #872 Nocturne prototype
- #873 Rico Alive prototype
```

## Review status for #1010

The initial self-review found and corrected a real governance conflict:

- `OPERATING_RULES.md` is canonical for the Session Boot Sequence.
- Earlier #1010 drafts incorrectly placed live GitHub checks before the canonical read order.
- `START_HERE.md` and `DAILY_AUTOPILOT.md` now preserve the canonical read order and perform live-state verification before action.
- Branch-authority roles (`WRITER`/`REVIEWER`/`RELEASE`/`IDLE`) are now distinguished from activity-pass roles (`Planner`/`Coder`/`Reviewer`/`Tester`/`Deploy verifier`).

Remaining merge blocker:

- `AI_WORKSPACE/TASKS.md` still needs the canonical `TASK-20260713-001` Continuity Block. The dated handoff exists, but it does not replace the task-ledger requirement.

## Recent main reality

The previous workspace snapshot was stale. Current `main` has already advanced through major product changes, including:

- shared Atelier UI kit;
- Workspace Shell C and `/dashboard` migration;
- `/profile` Atelier migration;
- `/settings` Atelier migration and Rico control-center refinement;
- teaser/access gate and launch film;
- explainer path fix;
- verification and legal-route middleware fix.

Agents must not plan from the older `60978ae…` snapshot.

## Open PR control

Read `AI_WORKSPACE/OPEN_PR_TRIAGE_2026-07-13.md` before touching any open PR.

Key rules:

- #1009, #1007, #1002, #989, and possibly #987 require focused current-main review.
- #1008 is a large Paddle implementation and remains HOLD pending deep review.
- #988 is non-launch CI housekeeping and remains HOLD.
- #997 is superseded and must not be resumed.
- #996 is mixed scope and stays on hold.
- #967/#965/#968 stay on hold.
- #961/#935/#872/#873 remain reference only.

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

The binding launch plan is `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md`.

```text
control plane
  -> PR cleanup
  -> route parity matrix
  -> launch-critical UI
  -> AED 79 billing
  -> invitations
  -> launch smoke
  -> owner opens access
```

Do not reorder or combine billing/auth/email/database/design work into one PR.

## Safe agent allocation

| Session | Allowed default role |
| --- | --- |
| UI implementation account | WRITER for one claimed route-group PR only |
| Backend/billing implementation account | WRITER for one claimed backend/billing/invitation PR only |
| Independent account | REVIEWER or RELEASE |
| Windsurf/OneSurf/local tooling | focused verifier; no foreign-branch edits |
| Codex | review signal only |
| Lovable | design/reference only unless explicitly assigned a production UI PR |

Parallel writers are allowed only for explicitly recorded non-overlapping tracks with separate files/contracts and no shared migration or auth surface.

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
1. Add TASK-20260713-001 with the complete Continuity Block to AI_WORKSPACE/TASKS.md.
2. Re-run final-head diff/CI review for #1010.
3. Obtain independent review and explicit owner merge approval.
4. After merge, run the read-only route/design parity inventory and record one small
   launch-critical UI task as the first ACTIVE runtime objective.
```

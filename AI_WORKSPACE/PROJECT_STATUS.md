# Project Status — Rico AI

> **Mandatory control panel. Every Claude, Windsurf, Codex, Devin, Lovable, ChatGPT, or other agent must read this file before planning or writing.**
>
> Live GitHub `main`, open PR heads, CI, deployed `/version`, and production smoke evidence override stale prose. If this file conflicts with live state, implementation stops until the control plane is reconciled.

## Verified control snapshot

| Field | Current value |
| --- | --- |
| Repository | `Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE` |
| Snapshot date | 2026-07-18 |
| Live-main baseline audited | `ae656787` (2026-07-18 night; agents must fetch and report the exact current SHA at session start) |
| Profile Workspace Hardening track (2026-07-18, owner-authorized autonomous run) | **COMPLETE** — `21293c9d` #1163 (docs reconciliation) · `63e976d0` #1164 (**Phase 4A** severity contract) · `ab707594` #1165 (**Phase 4B** actionable warnings) · `0da1c3e2` #1166 (numeric-field clearing, no migration) · `ae656787` #1167 (route-exit dirty-state protection). Deploys: #1164/#1165/#1166 "Deploy to Production" **success**; #1167 run initiated on merge. Ledger: `TASKS.md` TASK-20260718-016…019; narrative: `CURRENT_STATE.md` (2026-07-18 night header). **Owner live authenticated `/profile` + AR RTL smoke pending for the track.** Deferred: `chat-confirm-profile.test.tsx` CI flake (test-stability follow-up); `/settings` passive warning list; Review-later persistence beyond session (product decision). |
| Job-Seeker-Workspace merges since #1145 (2026-07-18) | `14b2b2e` #1153, `cee1d63` #1152, `25f1944` #1156, `6b62a11` #1155, `965dd64` #1151, `4ce678b` #1157 — all merged + "Deploy to Production" green; **owner production visual smoke pending** for #1155/#1151/#1157. Per-PR detail: `TASKS.md` TASK-20260718-001…006; narrative: `CURRENT_STATE.md` (2026-07-18 header). **Still open (do not mark complete):** actionable warning workflow, full cross-route audit, Command Workspace, Applications/Documents/Cover-letter, Dashboard #14, `Sessions → Conversations`. |
| Merged since #1157 (2026-07-18 evening) | `197d946` #1159 (Gmail consent/readiness **UI only** — connector stays production-disabled, flag OFF), `18fb5631` #1160 (**docs-only** Neon architecture audit + **proposed** plan `DEC-20260718-001`; **no DDL/DML/DB change executed**), `f10498cd` #1162 (deployment-policy CI change), `76e52984` #1161 (**Profile true section navigation**, frontend-only, deployed — **"Deploy to Production" success**; **Profile Phase 3 complete**). Profile Phase 4A/4B **not started**. Residual: browser Back route-exit dirty-state is a separate **P1** shared-shell task. Detail: `CURRENT_STATE.md` (2026-07-18 evening header), `TASKS.md` TASK-20260718-015. |
| Control-plane PR #1010 | **MERGED** `b753885` (2026-07-13) — the reconciliation freeze it imposed is over |
| Operating posture (owner 2026-07-16) | **CONTAINMENT FIRST.** (1) Rotate/quarantine the local `rico-job-automation-api.env` secrets (owner action; never deploy from it — stale + Stripe). (2) Unify source of truth (this reconciliation). (3) **Freeze new-integration activation** — allow only security + docs fixes until unified; Atelier design completion (#1062 job cards ready but held) and Gmail/Memory activation resume after. See `CURRENT_STATE.md` (evening header) for the full merge log. |
| Design system | **Atelier V3 is the sole production-wide system** (`DEC-20260716-001`, merged #1059). `/command` re-skinned to Atelier (paper + "Atelier at Night", sun-red) — re-skin + editorial serif replies merged (#1060) + composer gradient (#1061); MATCH job cards **ready, held** (#1062). "Command Obsidian" acid-lime retired to reference. C5/C6 collapse to a verification pass. |
| Integrations (frozen, flag-OFF drafts) | **Gmail M0** `TASK-20260716-001` / #1055 (draft — first-party OAuth, migration 043, Fernet tokens, `RICO_ENABLE_GMAIL_SYNC=false`). **Memory M1** `TASK-20260716-002` / #1025 (draft — additive migration 042, shadow writer, `RICO_MEMORY_ENGINE_ENABLED=false`). Neither activates until owner-reviewed. |
| New infra merged 2026-07-16 | Hermetic CI decision-regression harness (#1056, `tests/decision_regression/`); security hardening (#1058 — XFF rate-limit, `/chat/public` email-impersonation, DOCX bomb, weak session id); attachment-OCR/SSE/transcript fixes (#1046/#1050/#1051/#1052). `.gitignore` broadened to `*.env` catch-all. |
| Production access state | **Teaser/access gate REMOVED** (`96b7efd`) — the full site is open; waitlist retired; landing plays one of 3 launch films at random (#1019) |
| Billing | **Paddle merged** (#1008 `1b1748c` + follow-up fixes `d05ca08`/`30ebb7d`/`c11575d`, Sandbox mode). One plan "Rico Monthly" — **USD 21.50/mo is the authoritative price** (`403c28b`); AED 79 is a reference display note only. **#1022 MERGED** (`27df7ba6`) — Setup-level eventCallback fix production-verified (open/close/reopen smoke PASS). Paddle billing NOT activated in production (`NEXT_PUBLIC_BILLING_MODE=""`). Sandbox checkout URL configured in Paddle dashboard. Architecture debt: hardcoded fallbacks still present (separate PR planned) |
| Invitation target | Branded secure email invitations; not started, not production-verified |

## Current execution lock

```text
ACTIVE NOW (owner containment plan, 2026-07-16 evening — sequence, do not skip)
1. SECURITY CONTAINMENT (owner action): rotate ALL credentials in the local
   `rico-job-automation-api.env` (treat as exposed — plaintext export, ~23 live
   fields), never deploy from it (stale + Stripe, not Paddle). Build a fresh
   production env from `.env.example`. `.gitignore` now blocks any `*.env`.
2. SOURCE-OF-TRUTH UNIFICATION (this reconciliation PR): AI_WORKSPACE caught up
   to main; duplicate `TASK-20260715-001` fixed (4b → -002); Gmail + Memory
   registered (`TASK-20260716-001/-002`); `DEC-20260716-001` merged (#1059).
3. FREEZE new-integration activation; allow only security + docs fixes until (1)+(2)
   are done. Atelier design completion (#1062 job cards — ready, HELD) and Gmail /
   Memory activation resume only after.

DONE (Atelier /command, in main)
- Re-skin to Atelier (paper + Atelier at Night, sun-red) + editorial serif reply
  rendering (#1060); composer gradient fade (#1061). Obsidian acid-lime retired.
- Decision harness (#1056), security hardening (#1058), attachment/SSE/transcript
  fixes (#1046/#1050/#1051/#1052) all merged. Billing unchanged: Paddle merged,
  NOT activated; env/config Stripe-vs-Paddle mismatch = owner cleanup item.

HELD / FROZEN (ready or paused, do NOT merge/activate without owner review)
- #1062 Atelier MATCH job cards — CI-green, held until containment done (design).
- #1055 Gmail M0 (`TASK-20260716-001`) — draft, flag OFF; needs independent
  security/privacy review + isolated migration-043 + limited real-account OAuth test.
- #1025 Memory M1 (`TASK-20260716-002`) — draft, flag OFF; keep as draft pending
  shadow evidence; no MemoryReader.

CLOSED 2026-07-16 (board cleanup, owner plan step 4)
- #967 pre-launch gate (superseded — site open) · #996 mixed pitch/explainer/waitlist
  (split-or-close) · #989 subscription fallback (stale vs Paddle) · issues #960/#963
  (completed — CV dedup migration 037 / onboarding CV persistence migration 038).

REFERENCE ONLY / DO NOT RESUME
- #1029 (closed composer attempt), #961, #935, #872, #873
- Uploaded design packages (rico-design-reference*.zip, lovable-source) = visual
  reference ARCHIVE only — never port their pricing (AED tiers), auth, or mock logic.
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

Fresh snapshot 2026-07-16 evening (6 open PRs). The pre-Atelier-pivot 07-15 table
is superseded; only these are open:

| PR | Subject | Classification |
| ---: | --- | --- |
| #1062 | Atelier MATCH job cards | **HELD** — CI-green; design frozen under containment; owner logged colour/AR/test gaps |
| #1055 | Gmail M0 read-only connector | **DRAFT** — flag OFF; 3 P1 review blockers + separate merge/activation gates (`TASK-20260716-001`) |
| #1025 | Memory Engine M1 (shadow) | **DRAFT** — flag OFF; paused pending shadow evidence (`TASK-20260716-002`) |
| #1002 | settings honesty labels | draft — small; review after containment |
| #988 | hide noisy bot comments workflow | housekeeping |
| #965 | journey-state seed | draft — superseded in direction by Memory Engine; close candidate |

**Merged since the 07-15 table:** #1048/#1060/#1061 (Atelier `/command`), #1056/#1058
(decision harness + security hardening), #1046/#1050/#1051/#1052/#1053, #1059
(`DEC-20260716-001`), #1063 (this reconciliation). #1028 (slice-4a composer) merged
long ago, then the whole `/command` re-skinned to Atelier — superseded.
**Closed (board cleanup):** #967, #996, #989 + issues #960/#963.

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

Under the containment posture (2026-07-16) the only writer work allowed is
**security + docs/reconciliation**. Feature/design/integration writing is frozen.

| Session | Allowed default role (containment) |
| --- | --- |
| Claude | WRITER for the containment reconciliation (#1068) + security fixes only |
| Windsurf / Codex / local tooling | REVIEWER — e.g. the #1055 Gmail review; no foreign-branch feature edits |
| Any implementation account | no new feature/design/integration writing until containment closes |
| Lovable | design/reference only |

No parallel feature writers during containment. When containment closes and feature
work resumes, record each non-overlapping track (separate files/contracts, no shared
migration or auth surface) before starting.

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
Containment sequence (owner priority 2026-07-16 — do not skip):
1. #1068 — finish the source-of-truth reconciliation (this PR): make CURRENT_STATE,
   PROJECT_STATUS, ROADMAP, and TASKS agree on active/held/next; Gmail Draft + gates;
   *.env ignore coverage. Docs/security only.
2. Owner: rotate ALL credentials in the local rico-job-automation-api.env (treat as
   exposed); build a fresh Paddle production env from .env.example. Never deploy from
   the stale Stripe file.
3. #1066 (retire old Stripe tooling + stale Render env file) and #1067 (align paid-plan
   promises with implemented limits) — after secret rotation.
4. Still FROZEN until the above close: #1062 (Atelier job cards — fix the logged
   colour/AR/test gaps first), #1055 Gmail (fix 3 P1 blockers + gates), #1025 Memory.
5. Then resume Atelier completion + integrations as small provable PRs, and the full
   production gate (CV, logout/login persistence, attachments, applications, billing
   sandbox, AR + mobile).
```

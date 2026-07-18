# Engineering Roadmap

The single map of the whole project: where Rico is, where it is going, what is
blocked, what is completed, and what comes next. Any agent or contributor should
be able to read this file and orient in under a minute.

This is the **top-level spine**. It sits above the other workspace docs:

```text
Vision          AI_WORKSPACE/PROJECT_BRIEF.md · CAREER_OS_VISION.md
   ↓
Architecture    AI_WORKSPACE/ARCHITECTURE.md  (how the system is / will be built)
   ↓
Roadmap         THIS FILE                     (phases 0–7, status, what's next)
   ↓
Epics           long-lived product themes (below)
   ↓
Milestones      shippable capability blocks
   ↓
PRs             one reviewable change each (GitHub)
   ↓
Releases        what actually reached production
```

Decisions that shape the roadmap live in `AI_WORKSPACE/DECISIONS.md`. The task
ledger lives in `AI_WORKSPACE/TASKS.md`. The near-term execution gate is
`AI_WORKSPACE/AUDITS/2026-07-08-production-hardening-audit.md` — read it before
starting any feature, redesign, worker, notification, or infrastructure work.

---

## Where Rico is right now (2026-07-18)

> This snapshot is authoritative alongside `PROJECT_STATUS.md` (the control panel);
> if they ever disagree, `PROJECT_STATUS.md` + live `main` win. Snapshots dated
> 2026-07-16 and earlier are **historical** (superseded).
>
> **`main` `4ce678b`.** Job-Seeker-Workspace batch merged + deployed since #1145
> (Phase 5 surfaces): #1153 English CV-vs-search routing (`14b2b2e`), #1152 `/profile`
> editorial rebuild + **visual** section rail (`cee1d63`), #1156 profile-warning
> **contrast** (`25f1944`), #1155 **Arabic** search routing (`6b62a11`, Render #389
> verified), #1151 structured `/command` replies + motion (`965dd64`), #1157
> plain-language terminology EN+AR (`4ce678b`). Per-PR detail: `TASKS.md`
> TASK-20260718-001…006. **Owner production visual smoke pending** for #1155/#1151/#1157.
> **Profile *true* section navigation is COMPLETE** — #1161 (`76e52984`, Profile
> Phase 3). **Profile *actionable* warning workflow is COMPLETE** — #1164 Phase 4A
> severity contract (`63e976d0`) + #1165 Phase 4B actionable UI (`ab707594`); plus
> #1166 numeric-field clearing (`0da1c3e2`) and #1167 route-exit dirty-state
> protection (`ae656787`) close the Profile Hardening track (2026-07-18).
> **Still open — do NOT read as complete:**
> the *full* cross-route authenticated audit (only the English routing defect fixed),
> Command Workspace, Applications/Documents/Cover-letter workspaces, Dashboard #14,
> `Sessions → Conversations`. Claude Design's UX prototype is design-only, not
> repository/runtime-verified.

| Question | Answer |
| --- | --- |
| **Where is Rico?** | `main` `4194736f`+. `/command` is the full **Atelier** surface (paper + Atelier at Night, editorial serif replies) — `DEC-20260716-001` merged. #963 CV-persistence + Paddle #1008 shipped long ago (Paddle merged, NOT activated). |
| **Posture (owner 2026-07-16)?** | **CONTAINMENT.** Security-first → source-of-truth unification (#1068) → then resume. Only security + docs writing allowed now. |
| **What is blocked / frozen?** | New-integration activation is frozen. #1062 (Atelier job cards — HELD, has logged colour/AR/test gaps), #1055 Gmail M0 (Draft, flag OFF, 3 P1 blockers), #1025 Memory M1 (Draft, flag OFF). Owner P0: rotate the exposed local `rico-job-automation-api.env` secrets. |
| **What is completed (recent)?** | Atelier `/command` (#1048/#1060/#1061), decision-regression harness (#1056), security hardening (#1058), attachment/SSE/transcript fixes, `DEC-20260716-001` (#1059), operational reconciliation (#1063). |
| **What comes next?** | #1068 (this reconciliation) → owner secret rotation → #1066 (retire Stripe tooling / stale Render env) + #1067 (paid-plan promises vs limits) → then unfreeze Atelier completion + integrations as small provable PRs. |

Production is stable: Render backend healthy (`/health` ok, providers configured),
Vercel frontend up. The batch-row-isolation hardening fix (#887) is live.

---

## The hierarchy (how work is organized)

Rico work nests so every PR traces up to a product reason:

```text
EPIC        Career Operating System
  └ Milestone   Operational Memory
      └ Phase       Lifecycle
          └ PR          #885 — follow-up endpoint
              └ Task        list applied jobs ready for follow-up
```

- **Epic** — a long-lived product theme (months). Rarely changes.
- **Milestone** — a shippable capability block within an epic.
- **Phase** — an ordered stage of hardening/build within a milestone (maps to the 0–7 phases below).
- **PR** — one reviewable change on GitHub. Small, single-objective.
- **Task** — the concrete unit inside a PR, tracked in `TASKS.md`.

Naming/branch/PR governance: see `AI_WORKSPACE/OPERATING_RULES.md` and
`AI_WORKSPACE/PR_QUALITY_GATE_RULES.md`.

---

## Phases 0–7

Status legend: ✅ completed · 🔵 in progress · ⬜ planned (not started)

### Phase 0 — Architecture & Governance ✅

The workspace, roadmap, audit gate, operational-memory strategy, branch/PR
governance, and naming standards that let multiple agents work without drift.

- Delivered: AI Workspace, `ARCHITECTURE.md`, DEC-20260707-001, the 2026-07-08
  production hardening audit gate, this roadmap.
- PRs: #881 (roadmap + audit reconciliation, merged).

### Phase 1 — Operational Memory Foundation ✅

Rico must never forget what it found, opened, applied to, or needs to follow up.

- Delivered: `user_job_context` persistence (migrations 018–022), operational
  memory readiness helper, follow-up readiness selection, read-only lifecycle
  follow-ups endpoint, Audit Phase 2 verification (persistence proven sound).
- PRs: #883 (readiness helper, merged), #885 (follow-ups endpoint, merged).

### Phase 2 — Hardening 🔵 (current)

Not features, not UI. Robustness, resilience, regression protection, operational
safety. Each finding becomes a small, scoped hardening PR — verify-first, and
fix only proven gaps (synthetic data only).

- Delivered: #887 — batch-row-isolation in `upsert_matches` (one malformed row
  no longer drops the whole apply-link batch); proven against real Postgres.
- Delivered, awaiting release verification: #969/#960 exact document dedupe and #975/#963
  onboarding confirmation persistence with real-Postgres coverage.
- Next candidates: any gap surfaced by continued Audit Phase 2–9 verification.

### Phase 3 — Chat Integration 🔵 (current)

Wire chat to what is already persisted — almost no new logic, just connection.

- Delivered: #891 — "what should I follow up?" / "which jobs are due for
  follow-up?" (EN + AR) → reuses the merged readiness logic
  (`get_by_status("applied")` → `select_revisit_candidates`).
- Already in chat before this phase: "show my applications", "show saved jobs",
  "what did I open but not apply to?", follow-up timing advice.
- Next candidates: a combined job-search status digest; any other lifecycle view
  not yet reachable from chat.
- Constraint: reuse existing lifecycle reads; verify-first; synthetic data only.

### Phase 4 — Lifecycle Intelligence 🔵 (Gmail M0 in build)

Rico stops being only a keeper and starts following up with the user, e.g.
"You applied 6 days ago — prepare a follow-up email?" / "You opened this job
three times — want to apply?"

- In build: **#1055** — Gmail read-only connector M0 (first-party OAuth,
  `gmail.readonly` scope, Fernet-encrypted refresh tokens, bounded inbox sync,
  propose-only review items, `RICO_ENABLE_GMAIL_SYNC=false`).
  Design doc: `docs/integrations/gmail-readonly-connector.md`.
  Milestone: Email Integration. M1 = AI-drafted follow-ups (no `gmail.compose`).
  M2 = Outlook via Microsoft Graph.

```text
EPIC        Career Operating System
  └ Milestone   Email Integration
      └ Phase       Lifecycle Intelligence (Phase 4)
          └ PR          #1055 — Gmail read-only connector M0
              └ Task        Gmail-M0-connector
```

### Phase 5 — UX Facelift ⬜

Only after the system is stable. Atelier, Rico Alive, Nocturne, and the new
design language. (Corresponds to DEC-20260707-001 "UI redesign / PR G".)
The approved target is `/design-preview` per DEC-20260710-002; migration remains
per-route and owner-gated, and resumes after the #963 release gate.

### Phase 6 — Notifications ⬜

After lifecycle exists: email, WhatsApp, reminders, weekly reports. Must honor
the Telegram audience rules (admin/dev vs user channels).

### Phase 7 — Infrastructure Evolution ⬜ (last)

Not now. Railway, worker split, queue, Redis, background processing. Render
stays the production backend until a Railway target passes full production
smoke. (Corresponds to DEC-20260707-001 PRs D/E.)

---

## How this maps to the other roadmaps

This product-level roadmap (phases 0–7) and the architecture-level roadmap in
`DECISIONS.md` → DEC-20260707-001 (PRs A–G) are two lenses on the same work,
not competing plans:

| Engineering phase | Architecture-level (DEC-20260707-001) |
| --- | --- |
| 1 Operational Memory Foundation | PR A (persist job context + apply links) |
| 2 Hardening | robustness layer over PR A/B (verify-first) |
| 3 Chat Integration | consumes persisted lifecycle (no infra change) |
| 4 Lifecycle Intelligence | builds on PR B (application lifecycle) |
| 5 UX Facelift | PR G (UI redesign) |
| 6 Notifications | notifications-only layer |
| 7 Infrastructure Evolution | PRs D/E (worker separation, Render→Railway) |

The 2026-07-08 production hardening audit remains the **near-term execution
gate**: it controls immediate stabilization (Phases 1–2) and must be read
before feature/redesign/worker/notification/infra work.

---

## Releases (what reached production)

| Date | Commit | What went live |
| --- | --- | --- |
| 2026-07-18 | `4ce678b` | #1157 — plain-language terminology in user-facing copy (EN+AR). Deploy-to-Production #997 green; **owner visual smoke pending** |
| 2026-07-18 | `965dd64` | #1151 — structured safe-markdown `/command` replies + motion. Deploy-to-Production #996 green; **owner visual smoke pending** |
| 2026-07-18 | `6b62a11` | #1155 — explicit Arabic job search reaches the search router. Render backend deploy #389 verified serving `6b62a11`; **owner AR smoke pending** |
| 2026-07-18 | `25f1944` | #1156 — profile guardrail-warnings contrast/legibility (editorial `/profile`) |
| 2026-07-18 | `cee1d63` | #1152 — `/profile` editorial rebuild + real-data wiring (visual section rail only) |
| 2026-07-18 | `14b2b2e` | #1153 — English "find jobs that match my CV" routed to job search (not job-doc scoring) |
| 2026-07-08 | `7d167dd` | #887 — batch-row-isolation hardening (apply-link batch resilience) |

_Merged to `main` (`80e246b`), deploy verification pending: #885 (follow-ups
endpoint) and #891 (chat follow-up readiness). Promote each to a release row once
`/version.commit` on Render reads `80e246b…` and `/health` is ok._

_Add a row when a runtime change is deployed and verified (`/version.commit`
matches `main`, `/health` ok). Docs-only merges are not releases._

---

## How to update this file

- Move a phase to ✅ only when its milestone's PRs are merged **and** any runtime
  change is deployed + verified.
- When a phase becomes current, mark it 🔵 and list delivered PRs + next candidates.
- Record each production deploy in the Releases table.
- Keep phase names stable; this file is the map contributors trust.

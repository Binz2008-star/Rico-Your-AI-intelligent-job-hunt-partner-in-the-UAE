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

## Where Rico is right now (2026-07-11)

| Question | Answer |
| --- | --- |
| **Where is Rico?** | Release verification for #963: the onboarding CV persistence implementation is merged as `241b85d…`, CI-green, and Vercel-ready. |
| **Where is it going?** | Verify the deployed backend/authenticated flow, then resume the approved per-route Atelier migration and separately scoped hardening. |
| **What is blocked?** | No new runtime/design objective may start until the #963 release gate (migration 038 schema proof + authenticated smoke) passes. Render version already matches `241b85d…`. **#1008 (Paddle billing)** is draft — blocked on migrations 040+041, `PADDLE_*` env vars, and owner approval to set `BILLING_MODE=paddle`. |
| **What is completed?** | Phases 0–1, #969 document idempotency foundation, and #963 implementation. Production verification of #963 is pending. |
| **What comes next?** | Complete release verification; then select one objective only: #962 or the next owner-approved design route. |

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

### Phase 4 — Lifecycle Intelligence ⬜

Rico stops being only a keeper and starts following up with the user, e.g.
"You applied 6 days ago — prepare a follow-up email?" / "You opened this job
three times — want to apply?"

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

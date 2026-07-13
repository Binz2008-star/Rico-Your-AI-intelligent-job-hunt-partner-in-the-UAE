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

## Where Rico is right now (2026-07-13) — Launch Program

| Question | Answer |
| --- | --- |
| **Where is Rico?** | Production is in **pre-launch teaser mode**. `ricohunt.com` serves the launch film to the public and gates the unfinished app. The P0 email-verification break is fixed and live. |
| **Where is it going?** | Open to real users behind a proper **waitlist gate** (#967), then enable **billing** (#1008). Each is blocked on a Neon migration + env the owner must approve. |
| **What is blocked?** | **#967** (waitlist) — needs migration 039 + waitlist/backend smoke before merge. **#1008** (Paddle billing) — needs migration 040 + `PADDLE_*` env + `BILLING_MODE`. **#989** — scope unverified (doc gap). |
| **What is completed?** | Teaser gate live (#1003/#1004), **P0 verify-email allowlist fix live (#1005)**, icon unification (#1007), Playwright CI stability (#1005 env + #1009), control-plane docs (#1010). |
| **What comes next?** | Owner-run production smoke: **Signup → Resend → Verify → Login**. Then per-PR launch decisions (#967, then #1008). Product hardening (Phases 2–4 below) resumes after launch stabilizes. |

Live gate: `apps/web/middleware.ts` (`NEXT_PUBLIC_SITE_LIVE`). Launch film:
`apps/web/public/explainer/` (option-2/3/3b, random cut per visit). Detail:
handoffs `2026-07-12-rico-launch-film-3d.md`, `2026-07-13-p0-verify-email-hotfix.md`;
`DECISIONS.md` DEC-20260712-001. Render backend + Neon DB unchanged.

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

## Launch Program — Vision → Epic → Milestone → Phase → PR (current focus)

Status: ✅ done · 🔵 in progress · ⛔ blocked · ⬜ planned. Owners:
**C**=Claude · **L**=Lovable · **X**=Codex · **D**=Devin · **O**=Owner (Roben — approvals/merges/prod env).

**Vision** (`PROJECT_BRIEF.md` · `CAREER_OS_VISION.md`): a UAE-focused AI career
companion that models the user and runs their job search — launched safely, users
onboarded behind a controlled gate, then monetized.

| Epic | Milestone | Phase / PR | Status | Owner |
| --- | --- | --- | --- | --- |
| **Launch & Access** | Public teaser | Ship teaser gate + launch film — #1003, #1004 | ✅ live | C · O |
| | | P0: unblock email verification — **#1005** (`b66eb46f`) | ✅ live | C · O |
| | Waitlist onboarding | Atelier bilingual waitlist + film-in-page + gate — **#967** | ⛔ migration 039 + waitlist/backend smoke | C · L · O |
| | Full-site open | Flip `NEXT_PUBLIC_SITE_LIVE`/`RICO_LAUNCH_MODE` after validation (env, no PR) | ⬜ owner-gated | O |
| **Monetization** | Paddle billing | Stripe→Paddle: checkout, webhooks, entitlements — **#1008** | ⛔ migration 040 + `PADDLE_*` env + `BILLING_MODE` | C · O |
| **Brand & UI** | Consistent brand | Unify app icons / brand mark — #1007 | ✅ live | C |
| | Launch film | 3D "Dimensional" cuts + remix, bilingual, random rotation | ✅ built (in #967 / `explainer/*`) | C |
| **Eng. Quality** | CI reliability | Playwright full-site mode + headroom — #1005 env, #1009 | ✅ merged | C · O |
| | Control plane | Roadmap/status/decisions reconciliation — #1010 | ✅ merged | C · O |

PR triage + decisions are the source of truth, not this table:
`AI_WORKSPACE/OPEN_PR_TRIAGE.md`, `DECISIONS.md`, `TASKS.md`, and the per-PR
handoffs under `AI_WORKSPACE/HANDOFFS/`. This table only maps them.

The product-engineering spine (Phases 0–7 below) is the longer-horizon plan;
launch work above takes precedence until production is open and stable.

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

| Date | Commit / PR | What went live |
| --- | --- | --- |
| 2026-07-08 | `7d167dd` · #887 | batch-row-isolation hardening (apply-link batch resilience) |
| 2026-07-12 | #1003 / #1004 | teaser gate + launch film on `ricohunt.com` |
| 2026-07-12 | `67758854` · #1007 | unified gold brand icons |
| 2026-07-12 | `b66eb46f` · **#1005** | teaser allowlist fix — `/verify-email`, `/privacy`, `/terms` reachable (P0) |
| 2026-07-12 | `fd49129b` · #1009 | Playwright CI headroom (CI-only) |
| 2026-07-13 | `b7538858` · #1010 | control-plane docs — current production deploy `dpl_HyctVSpC…` (READY) |

_P0 (#1005) production route-smoke verified: `/verify-email?token=fake` → 200 (not
the teaser). **Not yet closed** — pending owner-run fresh Signup → Resend → Verify →
Login on production._

_Add a row when a runtime change is deployed and verified (`/version.commit`
matches `main`, `/health` ok). Docs-only merges are not releases._

---

## How to update this file

- Move a phase to ✅ only when its milestone's PRs are merged **and** any runtime
  change is deployed + verified.
- When a phase becomes current, mark it 🔵 and list delivered PRs + next candidates.
- Record each production deploy in the Releases table.
- Keep phase names stable; this file is the map contributors trust.

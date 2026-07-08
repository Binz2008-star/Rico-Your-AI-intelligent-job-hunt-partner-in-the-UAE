# Project Status — Rico AI

> **Control panel. Read this first (30 seconds), then `START_HERE.md`.** A pointer,
> not a log — deep detail lives in `ENGINEERING_ROADMAP.md`, `CURRENT_STATE.md`,
> and the latest handoff. If this page disagrees with live GitHub `main` /
> deployed `/version`, those win (`OPERATING_RULES.md`).

## Dashboard

| Field | Value |
| --- | --- |
| **Current Version** | Pre-1.0 (production, unversioned; `/version.commit` tracks deploys) |
| **Current Main SHA** | `49d14c1` (`origin/main`); PR #900 is ahead by 2 docs commits |
| **Current Phase** | Phases 0–1 complete · **2 Hardening + 3 Chat Integration active** · 4–7 planned |
| **Production Status** | 🟢 Render backend healthy · Vercel up · Neon = source of truth |
| **Open Critical Risks** | `005 pipeline_runs` migration drift (#712); `#885`/`#891` deploy verification unconfirmed from agent sessions |
| **Active PR** | **#900** — documentation audit + single-source-of-truth hardening (draft) |
| **Next Milestone** | Continue Phase 3 chat slices; **C3** Atelier `/about` `/contact` `/faq` (approved, owner-gated, not started) |
| **Last Updated** | 2026-07-08 |

_Refresh the dashboard row(s) in the same PR as any merge that moves `main` HEAD,
changes production status, or resolves/opens a critical risk._

---

## What works (live in production)

- Auth: JWT-cookie signup / login / logout / `/me`, user isolation.
- Chat: public + authenticated; intent routing, provider fallback, P0 trust guard.
- CV: upload → classify → parse; non-CV documents routed safely.
- Jobs: search with provider cascade (cache → internal → Jooble → Adzuna → JSearch
  → degraded CTA), fit-score, apply-link trust gate.
- Applications: save / open / prepare / mark-applied; `/flow` pipeline board.
- Operational memory: `user_job_context` persistence; "what should I follow up?"
  answered from persisted lifecycle (EN + AR).
- Trust: `MutationConfirmationGuard` — no false success on save/update/delete.
- Notifications: Telegram, split by audience (user vs admin/dev channels).
- Marketing surfaces: `/terms`, `/privacy`, `/refund-policy` on Atelier V2.

## What does not work yet / is gated

- **Email job alerts** — shipped but **gated/inert** (`RICO_ENABLE_EMAIL_ALERTS`
  off); activation is owner-gated (TASK-20260702-033).
- **Open bugs:** BUG-8 (no description — owner must supply), BUG-13 (profile/role
  drift across multiple CVs), BUG-14 (pipeline save idempotency — partial; draft
  PR #784), BUG-18 (`?q=` navigation mutates chat thread).
- **Chat QA open items:** TC-1 (UAE-national badge), TC-9 (per-message language),
  TC-10 (session cache/dedup), TC-11 (profile flashes search first), TC-12
  (cold-start "what can you do?"). See the `TASK-20260703-*` entries in `TASKS.md`.
- **Migration drift:** `005 pipeline_runs` (#712) still unverified in production.

## Next (ordered)

1. Continue **Phase 3 Chat Integration** slices (verify-first, synthetic data only).
2. **C3** — Atelier migration of `/about`, `/contact`, `/faq` (owner-gated, not started).
3. **Phase 2 Hardening** — fix gaps only as the audit proves them.

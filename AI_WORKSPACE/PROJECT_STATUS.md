# Project Status — Rico AI

> **Read this first (30 seconds), then `START_HERE.md`.** One-page snapshot of
> where Rico is right now. It is a pointer, not a log — deep detail lives in
> `ENGINEERING_ROADMAP.md`, `CURRENT_STATE.md`, and the latest handoff. If this
> page disagrees with live GitHub `main` / deployed `/version`, those win
> (`OPERATING_RULES.md`).
>
> **Last reviewed:** 2026-07-08 · **Maintainer:** whoever merges the latest PR
> must refresh this page in the same PR.

---

## Where is the project?

Rico is a **stable production** UAE-focused AI career companion (Career Operating
System). Backend FastAPI on Render (healthy), frontend Next.js on Vercel (up),
Neon PostgreSQL as the source of truth.

Roadmap position (see `ENGINEERING_ROADMAP.md`): **Phases 0–1 complete**
(Architecture & Governance, Operational Memory Foundation); **Phases 2–3 active**
(Hardening, Chat Integration); **Phases 4–7 planned** (Lifecycle Intelligence,
UX Facelift, Notifications, Infra). Stage: **foundation solid, building lifecycle
intelligence on top.**

## What is the last merge?

- **`main` HEAD:** `aeb7ff3` — docs audit / single-source-of-truth hardening (PR #900).
- **Last verified production release:** `#887` (`7d167dd`) — batch-row-isolation
  persistence hardening (live).
- **Merged, deploy verification pending:** `#885` + `#891` (`80e246b`) — lifecycle
  follow-ups endpoint + chat follow-up readiness (Render egress is blocked from
  agent sessions; promote to a release once `/version.commit` matches on Render).

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

## What is next?

1. Continue **Phase 3 Chat Integration** slices (wire remaining persisted
   lifecycle into chat; verify-first, synthetic data only).
2. **C3** — Atelier migration of `/about`, `/contact`, `/faq` (approved,
   owner-gated, **not started**; style/layout only, preserve EN/AR verbatim).
3. **Phase 2 Hardening** — fix gaps only as the audit proves them.

## Top risks

- `005` migration drift (#712) open — do not mix with feature work.
- Render ephemeral disk — mitigated by Neon persistence; Railway move deferred
  (Phase 7), Render stays production until Railway passes full smoke.
- `#885`/`#891` deploy verification unconfirmed from agent sessions (egress blocked).

## Active PR

- **#900** — documentation audit + single-source-of-truth hardening (draft).
  Board otherwise clean: only design prototypes **#872 / #873** held. No C3/C4/C8
  started.

---

_Update rule: refresh this page in the same PR as any merge that changes `main`
HEAD, the release status, what works, or the active-PR line. Keep it to one page._

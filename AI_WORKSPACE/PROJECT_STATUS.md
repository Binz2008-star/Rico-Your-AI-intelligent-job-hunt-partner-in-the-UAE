# Project Status — Rico AI

> **Control panel. Read this first (30 seconds), then `START_HERE.md`.** A pointer,
> not a log — deep detail lives in `ENGINEERING_ROADMAP.md`, `CURRENT_STATE.md`,
> and the latest handoff. If this page disagrees with live GitHub `main` /
> deployed `/version`, those win (`OPERATING_RULES.md`).

## Dashboard

| Field | Value |
| --- | --- |
| **Current Version** | Pre-1.0 (production, unversioned; `/version.commit` tracks deploys) |
| **Current Main SHA** | `b9563a7` (`origin/main`) — #900, #902, #903, #904 merged and live. Supersedes the earlier `d2bd860`/`f6996b4`/`e5dd9091` rows further below in history — those references are now stale. |
| **Current Phase** | Phases 0–1 complete · **2 Hardening + 3 Chat Integration active** · 4–7 planned |
| **Production Status** | 🟢 Render backend healthy · Vercel up (production deploy confirmed READY for `b9563a7`, alias `ricohunt.com`) · Neon = source of truth |
| **Open Critical Risks** | `005 pipeline_runs` migration drift (#712); `profile_repo.py` DB connection leak on 5 call sites — Medium severity, confirmed still unfixed (2026-07-09 deep dive). **#446 Stage 1 (16 `public:web-*` rows) executed and validated 2026-07-09** — `email` nulled on the 16-row manifest, primary row untouched, 0 orphaned `rico_chat_history`; **Stage 2 (5 non-public rows, incl. the primary) is deferred, not started — #446 stays open until Stage 2 is decided.** #263 still flagged needs-deep-dive (deferred). `#885`/`#891` deploy verification unconfirmed from agent sessions. No live SQL-injection, credential-leak, or public-identity security issue found (#127/#198); see `HANDOFFS/2026-07-09-security-data-risk-deep-dive.md`. |
| **Active PR** | none — #900, #902, #903, #904 all merged; see `HANDOFFS/2026-07-09-446-stage1-cleanup.md` for current board state |
| **Next Milestone** | Document #446 Stage 1 (this PR) → review #446 Stage 2 (5 non-public rows) separately, no mutation without a fresh decision → fix `profile_repo.py` connection leak → #758 → #812; Continue Phase 3 chat slices; **C3** Atelier `/about` `/contact` `/faq` (approved, owner-gated, not started) |
| **Last Updated** | 2026-07-09 |

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

1. **Document #446 Stage 1** — this PR: exact before/after counts, 16-row rollback manifest,
   Stage 2 deferral, recorded in `HANDOFFS/2026-07-09-446-stage1-cleanup.md`.
2. **#446 Stage 2** — separately review the 5 non-public rows (incl. the primary) before any
   further mutation; no cleanup SQL until a fresh decision is made on that set.
3. **Fix `profile_repo.py` connection leak** — `with db.connect() as conn:` at lines 541, 583,
   615, 651, 742 never closes the connection; confirmed still present by the 2026-07-09 deep dive.
4. **#758** — unify job-key scheme (duplicate DB rows from save-path key mismatch).
5. **#812** — fix compound-title role splitting.
6. Continue **Phase 3 Chat Integration** slices (verify-first, synthetic data only).
7. **C3** — Atelier migration of `/about`, `/contact`, `/faq` (owner-gated, not started).
8. **Phase 2 Hardening** — fix gaps only as the audit proves them.

See `HANDOFFS/2026-07-09-security-data-risk-deep-dive.md` for the #127/#198 verdict and
`HANDOFFS/2026-07-09-446-stage1-cleanup.md` for the #446 Stage 1 cleanup record.

# Project Status — Rico AI

> **Control panel. Read this first (30 seconds), then `START_HERE.md`.** A pointer,
> not a log — deep detail lives in `ENGINEERING_ROADMAP.md`, `CURRENT_STATE.md`,
> and the latest handoff. If this page disagrees with live GitHub `main` /
> deployed `/version`, those win (`OPERATING_RULES.md`).

## Dashboard

| Field | Value |
| --- | --- |
| **Current Version** | Pre-1.0 (production, unversioned; `/version.commit` tracks deploys) |
| **Current Main SHA** | `f6996b4` (`origin/main`) — #900 (docs audit + SSOT hardening) and #902 (Rico Continuity Gate) merged and live. Supersedes the earlier `e5dd9091` / "PR #900 active" row further below in history — that reference is now stale. |
| **Current Phase** | Phases 0–1 complete · **2 Hardening + 3 Chat Integration active** · 4–7 planned |
| **Production Status** | 🟢 Render backend healthy · Vercel up (production deploy `dpl_6uiUB8yuF1FAf4uyBsNN4G8BToZQ` READY on `f6996b4`, alias `ricohunt.com`) · Neon = source of truth |
| **Open Critical Risks** | `005 pipeline_runs` migration drift (#712); **#127/#198/#263 flagged in the 2026-07-09 board-health scan as "needs full deep dive" — unverified claims of SQL injection (#127), DB connection leaks + public-chat identity gap (#198), and product-trust contradictions (#263). Verify before further product fixes.**; #446 data-integrity cleanup (root cause fixed, cleanup owner-gated); `#885`/`#891` deploy verification unconfirmed from agent sessions |
| **Active PR** | none — #900 and #902 both merged; see `HANDOFFS/2026-07-09-board-health-scan.md` for current board state |
| **Next Milestone** | Security/data-risk deep dive on #127 and #198 (then #263 if time remains) before touching #758/#812/#446; Continue Phase 3 chat slices; **C3** Atelier `/about` `/contact` `/faq` (approved, owner-gated, not started) |
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

1. **Security/data-risk deep dive** on #127 (claimed SQL injection + hardcoded credentials) and
   #198 (DB connection leaks, public-chat identity gap, billing webhook races); #263 if time
   remains. See `HANDOFFS/2026-07-09-board-health-scan.md`. If live issues are confirmed, fix
   those first; if stale/fixed, proceed to #446 (owner-gated cleanup), then #758, then #812.
2. Continue **Phase 3 Chat Integration** slices (verify-first, synthetic data only).
3. **C3** — Atelier migration of `/about`, `/contact`, `/faq` (owner-gated, not started).
4. **Phase 2 Hardening** — fix gaps only as the audit proves them.

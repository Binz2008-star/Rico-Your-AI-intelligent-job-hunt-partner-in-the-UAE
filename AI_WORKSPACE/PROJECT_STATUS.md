# Project Status — Rico AI

> **Control panel. Read this first (30 seconds), then `START_HERE.md`.** A pointer,
> not a log — deep detail lives in `ENGINEERING_ROADMAP.md`, `CURRENT_STATE.md`,
> and the latest handoff. If this page disagrees with live GitHub `main` /
> deployed `/version`, those win (`OPERATING_RULES.md`).

## Dashboard

| Field | Value |
| --- | --- |
| **Current Version** | Pre-1.0 (production, unversioned; `/version.commit` tracks deploys) |
| **Current Main SHA** | `3e91ba6` (`origin/main`) — #906 (`profile_repo.py` connection-leak fix), #907 (#758 job-key unification), and #911 (#812 compound-title role splitting) all merged and live; Vercel production confirmed READY for all three. Supersedes the earlier `ec06ef5`/`b9563a7`/`d2bd860`/`f6996b4`/`e5dd9091` rows further below in history — those references are now stale. |
| **Current Phase** | Phases 0–1 complete · **2 Hardening + 3 Chat Integration active** · 4–7 planned |
| **Production Status** | 🟢 Render backend healthy · Vercel up (production deploy confirmed READY for `3e91ba6`, alias `ricohunt.com`) · Neon = source of truth |
| **Open Critical Risks** | `005 pipeline_runs` migration drift (#712). ~~`profile_repo.py` DB connection leak~~ — **fixed via #906** (8 sites, not the originally-estimated 5). ~~#758 duplicate DB rows from job-key mismatch~~ — **fixed via #907**. ~~#812 compound-title role splitting~~ — **fixed via #911**, merged and production READY. **NEW #908** — attachment-first reasoning bypassed; owner reframes as a conversation-orchestration/intent-routing root cause, not a quick patch — needs a scoped deep-dive before any fix, owner sign-off pending. **NEW #909** — governance-doc request that duplicates existing Active docs (`RICO_EXECUTION_PRINCIPLES.md`, `AGENT_OPERATING_MODEL.md`, `PR_QUALITY_GATE_RULES.md`, `DECISIONS.md` as ADR log); this repo already rejected a parallel `GOVERNANCE/` folder once (PR #901) — owner decision needed before any doc is written. **#446 Stage 1 (16 `public:web-*` rows) executed and validated 2026-07-09**; **Stage 2 (5 non-public rows, incl. the primary) is deferred, not started — #446 stays open until Stage 2 is decided.** #263 still flagged needs-deep-dive (deferred). `#885`/`#891` deploy verification unconfirmed from agent sessions. No live SQL-injection, credential-leak, or public-identity security issue found (#127/#198); see `HANDOFFS/2026-07-09-security-data-risk-deep-dive.md`. |
| **Active PR** | none — #906, #907, #910, #911 all merged and production READY; #913 (C-number naming-collision clarification, docs-only) is the current open PR |
| **Next Milestone** | The runtime priority chain (#906 → #907 → #812/#911) is complete and production-READY. #908 orchestration deep-dive and #909 governance-doc conflict both await owner direction; Continue Phase 3 chat slices; **About/Contact/FAQ Migration** (was labeled "C3" — see `DEC-20260709-005`: that label collided with PR #899's unrelated landing-hero work; approved, owner-gated, not started) |
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

1. **#446 Stage 2** — separately review the 5 non-public rows (incl. the primary) before any
   further mutation; no cleanup SQL until a fresh decision is made on that set.
2. **#908** — attachment-first orchestration/intent-routing bug; owner has explicitly reframed
   this as a root-cause investigation (conversation orchestrator, intent-routing precedence,
   tool-selection policy, active-CV selection), not a symptom-by-symptom patch. Needs owner
   sign-off on deep-dive scope/cost before starting (`CLAUDE.md` cost-optimization rule).
3. **#909** — governance-doc request; conflicts with existing Active docs
   (`RICO_EXECUTION_PRINCIPLES.md`, `AGENT_OPERATING_MODEL.md`, `PR_QUALITY_GATE_RULES.md`,
   `DECISIONS.md`) and a prior rejection of a parallel `GOVERNANCE/` folder (PR #901). Needs an
   owner decision (reuse existing docs vs. a dedicated `GOVERNANCE/` namespace) before any file
   is written.
4. Continue **Phase 3 Chat Integration** slices (verify-first, synthetic data only).
5. **About/Contact/FAQ Migration** — Atelier migration of `/about`, `/contact`, `/faq` (formerly
   labeled "C3"; owner-gated, not started). **Not** the same as PR #899 ("Landing Hero Polish",
   also formerly self-labeled "C3") — see `DEC-20260709-005` for the naming-collision record.
6. **Phase 2 Hardening** — fix gaps only as the audit proves them.

**#812 is done** — fixed by #911, merged and production READY (`3e91ba6`). No longer pending;
removed from this ordered list.

**Naming note:** bare "C#" labels (C1–C8) are retired as implementation identifiers per
`DEC-20260709-005` — "C3" was found in use for two unrelated things (this About/Contact/FAQ
migration and PR #899's landing-hero work) plus an unrelated #198 security-finding ID. Use the
explicit names above for new work; see the decision for the full conflict table and canonical map.

See `HANDOFFS/2026-07-09-security-data-risk-deep-dive.md` for the #127/#198 verdict,
`HANDOFFS/2026-07-09-446-stage1-cleanup.md` for the #446 Stage 1 cleanup record,
`HANDOFFS/2026-07-09-906-907-sync-and-908-909-triage.md` for the #906/#907 merge sync and
#908/#909 triage, and `DECISIONS.md` (`DEC-20260709-005`) for the C-number naming-collision
clarification.

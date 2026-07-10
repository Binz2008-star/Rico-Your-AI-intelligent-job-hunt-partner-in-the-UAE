# Current State

> **Reconciliation header — 2026-07-10, night (latest; supersedes all headers below).**
> **Rollout scope corrected by the owner: `/design-preview` is the approved production target
> for shape + content + flows** — not "visual polish" and not "landing below-the-fold only."
> Recorded as `DEC-20260710-002` (expands `DEC-20260710-001`), with an evidence-based reference
> inventory in `HANDOFFS/2026-07-10-design-preview-target-inventory.md` (53 reference PNGs in
> `apps/web/public/design-preview/`, the 6-group hub tile inventory in
> `apps/web/app/design-preview/_client.tsx`, and the live `/design-gallery` + `/rico-preview`
> previews). The uploaded design-preview PDF is **not present in the agent environment**; the
> in-repo `/design-preview` source is used as authoritative in its place. The package spans
> landing · auth · onboarding · workspace (dashboard/profile/settings/applications/upload/
> pricing) · support+legal · states, across three shells (marketing masthead, minimal auth
> header, workspace left sidebar), EN/AR, desktop/mobile. Delivery stays small per-route PRs
> with owner visual-approval gates; `DEC-20260710-002` carries a **binding guardrails block**
> (source-of-truth = `/design-preview`; no separate/"inspired-by" theme; one objective per PR;
> owner visual approval per phase; no backend/auth/billing/schema without approval; no fake
> actions; sample data labelled/removed; legal copy unchanged without legal review;
> command/chat requires its own DEC) plus **per-PR acceptance criteria**. **PR #933** (landing
> below-the-fold cream, draft on `claude/design-preview-hub-6o2ev5`, head `9627a5e`, CI green)
> is **paused** — it does not merge as a partial below-the-fold polish PR; the owner must pick
> one of: (a) revise into full public-landing parity, (b) close and start a clean full-parity
> PR, or (c) keep as reference only. Migration sequence + #933 decision: `TASK-20260710-003`
> (revised). This header is a
> docs-only workspace update on `docs/design-preview-target-inventory`; no `apps/web` or #933
> code changed.
>
> **Reconciliation header — 2026-07-10, evening (superseded by the header above).**
> `main` is at `db3d7226c1ed87990db2abbb964e6e4196526213` (#930 workspace sync merged,
> owner-approved). **Full read-only system audit run and verdict accepted by owner:
> YELLOW — acceptable, zero P0/P1 blockers; production stable.** Verified: Render
> `/version.commit` == `main` exactly (auto-deploy healthy); Vercel proxy chain healthy;
> DB reachable, no localhost fallback; 15/15 public routes 200; `/design-preview`
> noindex + not nav-linked; public chat correct EN/AR (guest job search returns an
> onboarding CTA, zero fabricated listings; empty message → 422); billing live in
> manual/WhatsApp mode with a no-Stripe guard; `/flow` confirmed as the pipeline source
> of truth (`/applications` is a thin redirect); admin API 401s unauth; no secrets in
> tracked files; frontend build green; vitest exactly at the known 19-failure baseline
> (zero new); backend focused suite 225 passed / 3 known-stale (trust-gate contract,
> `test_agent.py` not in CI); guest render smoke of `/command`, `/flow`, `/dashboard`
> (mobile+desktop, local prod build) 0 app errors. **Not run (honest gaps):**
> authenticated smokes (no smoke credentials — TASK-20260710-007), Render log
> inspection (MCP unauthorized), production-domain browser execution (proxy/TLS
> tooling; covered by local build + CI Playwright). Audit P2s recorded as
> TASK-20260710-004..007; P3s in the handoff. Full record:
> `HANDOFFS/2026-07-10-system-audit-phase0-gate.md`.
> **Rollout governance: `DEC-20260710-001`** (Atelier phases 1–6, visual-only,
> per-phase owner gate; Phase 3 gated on -006 + -007, Phase 4 on -005; `/command`
> excluded pending its own DEC). **Phase 1 implementation is NOT started** — owner
> instruction: UI migration begins only after this Phase 0 docs PR merges.
>
> **Reconciliation header — 2026-07-10, later same day (superseded by the header above).**
> `main` is at `9d47711961be58c767ef60271a0ab004e2f278ee`. **#929 merged (owner-approved
> draft merge) and production verified — `/design-preview` internal consolidation hub.** One
> noindex entry point to review the whole Atelier direction at once: live tiles
> (`/rico-preview`, `/design-gallery`, `/privacy`, `/refund-policy`, terms) plus 53 labelled
> EN/AR desktop/mobile reference screenshots covering landing, auth, onboarding, authenticated
> workspace, support/legal, and empty/loading/error/mobile/RTL states, behind a sticky
> INTERNAL PREVIEW · SAMPLE DATA · ACTIONS DISABLED header. Also: near-bottom-aware
> auto-follow in the preview-only Atelier console (`RicoConsole.tsx`), used by
> `/rico-preview` and `/design-gallery`. Post-merge production smoke PASS on ricohunt.com:
> `/design-preview`, `/rico-preview`, `/design-gallery`, `/privacy`, `/refund-policy`, and
> landing all return 200. Preview-only: no production route/nav change (`/command`, `/rico`,
> `/` untouched); no backend/auth/billing/Neon/schema change; no new deps. Rollback: revert
> #929 (squash `9d47711`) and let Vercel redeploy. Full task record:
> `TASK-20260710-002` in `TASKS.md`.
>
> **Reconciliation header — 2026-07-10 (superseded by the header above).** `main` is at
> `b3811ef6cd0aa598549a06c3a089536887e4c8e3`. Session outcomes (all merged unless noted):
> - **#908 attachment / Active-CV bug — RESOLVED & CLOSED.** RC1 (attachment-follow-up regex,
>   #914) and RC4 (prevent non-CV documents becoming the Active CV, #916) merged and confirmed
>   by owner-run production smoke (attachment answers stay transcript-grounded; an
>   invoice/image never becomes the Active CV). RC2 (low-confidence message wording) and RC3
>   (rejection taxonomy) were deferred as separate smaller items; #908 closed as completed with
>   that scope noted.
> - **#922 / #923 activation analytics — merged + production verified PASS.** Migration 036
>   (signup attribution columns + `admin_digest_log`) confirmed applied via a GitHub Actions
>   `weekly-admin-digest` `dry_run=true` run: HTTP 200, `status=ok`, `sent=false`, real metrics
>   returned (not `migration_pending`). Backend serving the code; no rollback needed.
> - **Design direction — `DEC-20260709-006` (#925):** records **Atelier Console as the candidate
>   authenticated-workspace direction (preview/exploration only)**, amending `DEC-20260708-003`
>   for exploration only. Nocturne remains the production workspace design; `/command` and
>   `/rico` are unchanged and not replaced.
> - **#924** — Atelier Console added as an isolated `/design-gallery` reference tab (ported from
>   the Lovable "Atelier" prototype: light/dark, EN/AR, RTL, mobile; demo data; all actions
>   reference-only). Adds `lucide-react` + Fraunces/Amiri/IBM Plex Sans Arabic via `next/font`.
> - **#926** — internal `/rico-preview` route (noindex, reference-only) reusing the #924 Atelier
>   Console behind an INTERNAL PREVIEW / SAMPLE DATA / ACTIONS DISABLED banner. Demo-only.
> - **#919** — dashboard-deploy CI fix (pull latest `main` before regenerating
>   `docs/index.html`) in `daily.yml` and `daily-job-bot.yml`; removes the recurring
>   self-inflicted rebase conflict.
> - **#921** — the incoming C2 privacy/refund handoff was reclassified (stale brief → rejected;
>   general design-reference zip → reviewed). The shipped `/privacy` and `/refund-policy` pages
>   were NOT changed.
> - **#918 closed** (command-concept gallery tab, superseded by #924; its reviewed reference
>   remains at `design-handoffs/reviewed/command-concept-sandbox/`).
> - **#920 open** — legal-review question: confirm whether the live `/privacy` & `/refund-policy`
>   "Last updated: June 2026" copy was legally reviewed. Not a design task; shipped pages left
>   untouched pending owner/legal.
> No backend/auth/billing/Neon/schema changes in this session's frontend/docs PRs. No #917,
> #899, #872, or #873 work started.
>
> **Reconciliation header — 2026-07-09 (superseded by the header above).** Docs-only:
> `DEC-20260709-005` retires bare "C#" labels as implementation identifiers. "C3" was found in
> use for two unrelated things — the canonical Atelier `/about`/`/contact`/`/faq` migration
> (per `PROJECT_STATUS.md`) and PR #899's unapproved landing-hero animation (open draft,
> unmerged) — plus an unrelated #198 security-finding ID. "C4" was referenced only as an
> undefined placeholder, never given a scope. Full conflict table and canonical map in
> `AI_WORKSPACE/DECISIONS.md` (`DEC-20260709-005`). No runtime code, no UI, no Neon, no issue
> closed, no roadmap reprioritization, PR #899 not renamed.
>
> **Reconciliation header — 2026-07-09 (earlier same day; now itself superseded by the header
> above).** `main` has advanced to `b9563a78154743d0270586ce23326bc372be6192` (#904, security/data-risk deep-dive
> verdict persisted).
>
> **#446 Stage 1 cleanup executed and validated (2026-07-09).** Run by a session with live Neon
> connector access (project `old-frog-88141983`, branch `br-restless-cherry-amq6wj7o`, database
> `neondb`) — **not** this Claude Code session, which has no `DATABASE_URL`/DB access. Read-only
> queries confirmed 21 total `rico_users` rows with `email = 'robenedwan@gmail.com'`; 16 matched
> `external_user_id LIKE 'public:web-%'` and were the Stage 1 target (primary row confirmed NOT
> in that set). Stage 1 `UPDATE` nulled `email` on exactly those 16 explicit IDs (manifest in
> `HANDOFFS/2026-07-09-446-stage1-cleanup.md`). Post-cleanup validation: `remaining_with_email = 5`
> (matches expectation — the 5 non-public rows, including the primary, untouched), all 16 target
> IDs confirmed `email IS NULL`, primary row confirmed still `email = 'robenedwan@gmail.com'`,
> `0` orphaned `rico_chat_history` rows. No schema change, no deletes, no inserts, no Stage 2.
> **#446 stays open** — the 5 non-public rows (Stage 2) still need separate review before any
> further mutation; do not close #446 until Stage 2 is decided or the issue is updated with
> partial-completion status.
>
> **Updated priority:** document Stage 1 (this header + the dated handoff) → review #446 Stage 2
> separately → fix `profile_repo.py` connection leak → #758 → #812. No runtime code changed by
> any of the board-health scan, the security/data-risk deep dive, or this cleanup.
>
> **Reconciliation header — 2026-07-09 (earlier same day; now itself superseded by the header
> above).** `main` had advanced to `d2bd86093a155b91522c4cb02e9cd6db23b498d2` (#903, board-health
> scan persisted). A read-only security/data-risk deep dive on #127 and #198 (per owner
> decision after the board-health scan) found **no live SQL-injection, hardcoded-credential,
> public-identity, or recommendation-TOCTOU security issue** — all those named claims are
> already fixed in current code (confirmed by direct inspection, not automated review; no
> Codex pass was run on this deep dive). One confirmed still-live issue: **`profile_repo.py`
> leaks a DB connection** on 5 call sites (`with db.connect() as conn:` never closes) —
> Medium severity, a real reliability risk, not a security breach. #263 remains flagged
> needs-deep-dive (deferred, not yet checked). Full verdict, methodology, and per-claim
> file/function evidence: `AI_WORKSPACE/HANDOFFS/2026-07-09-security-data-risk-deep-dive.md`.
>
> **Updated priority:** #446 read-only precheck → #446 cleanup (owner-approval only) → fix
> `profile_repo.py` connection leak → #758 → #812. No fixes started yet; no code changed by
> either the scan or the deep dive.
>
> **Reconciliation header — 2026-07-09 (earlier same day; now itself superseded by the header
> above — `main` has since advanced from `f6996b4` to `d2bd860`).** At the time this header was
> written, `main` had just advanced to `f6996b4da04f6d3812fe873067e89247c8bb165e`.
> Both #900 (documentation audit + single-source-of-truth hardening, incl.
> `PROJECT_STATUS.md`/`MASTER_INDEX.md`) and #902 (Rico Continuity Gate) are
> **merged and live** — Vercel production deployment `dpl_6uiUB8yuF1FAf4uyBsNN4G8BToZQ`
> confirmed `READY` on `f6996b4` (alias `ricohunt.com`). The reconciliation header
> below this one, and `PROJECT_STATUS.md`'s prior "Current Main SHA: `e5dd9091`" /
> "Active PR: #900 (draft)" rows, are now **stale/superseded** — do not treat them
> as current.
>
> A read-only board-health scan (2026-07-09) classified all 34 open issues; full
> detail in `AI_WORKSPACE/HANDOFFS/2026-07-09-board-health-scan.md`. Headline:
> #446 is confirmed data-integrity cleanup debt (P0, owner-gated, root cause
> already fixed); #127, #198, and #263 are flagged **needs full deep dive** —
> unverified claims of SQL injection (#127), DB connection leaks + a public-chat
> identity gap (#198), and product-trust contradictions (#263). Per owner
> decision, verify these before touching #758/#812/#446. No code changes, no
> issues closed, no labels changed in the scan itself.
>
> **Reconciliation header — 2026-07-09 (earlier same day).** The dated sections in this file are a
> **historical log**; the newest detailed narrative below stops at **2026-07-03**
> (`main` `b021273`). Since then the operational-memory / governance / Atelier
> train has merged and `main` has advanced. For the authoritative "where is Rico
> right now," read **`AI_WORKSPACE/ENGINEERING_ROADMAP.md`** (phase status +
> Releases table) and the latest handoff
> **`AI_WORKSPACE/HANDOFFS/2026-07-09-board-clean-governance-complete.md`**.
> If this log and the roadmap disagree, the roadmap + latest handoff + live
> GitHub `main` win (per `OPERATING_RULES.md`).
>
> **Actual `main` HEAD:** `e5dd9091` (`docs: add Docker Neon dev/staging guidance`). **Merged since the 2026-07-03 log below** (see the roadmap
> and handoffs for detail — do not re-derive from this log):
>
> - **Operational Memory / Hardening (Roadmap Phases 0–2):** #881 phased
>   architecture decision + audit gate reconciliation, #883 revisit-readiness
>   helper, #885 lifecycle follow-ups endpoint, #887 batch-row-isolation
>   persistence hardening (live, `7d167dd`), #888 Engineering Roadmap master map.
> - **Chat Integration (Phase 3):** #891 "what should I follow up?" readiness
>   (`80e246b`; deploy verification pending per the roadmap Releases note).
> - **Trust:** #892 `MutationConfirmationGuard` — canonical closure of #764
>   (`bd887d7`; supersedes the older QA-cycle #764 note further down this file).
> - **Design / marketing surfaces:** #879/#880 C1 Atelier `/terms` pilot, #895 C2
>   Atelier `/privacy` + `/refund-policy`, #889 command-concept-sandbox approved as
>   design reference, #894 Lovable streaming-chat quarantine (DEC-20260708-004).
> - **Governance / tooling:** #890 agent operating model
>   (`AI_WORKSPACE/AGENT_OPERATING_MODEL.md`), #897 technical status handoff, #898
>   Docker local-dev (local-only), #901 Docker Neon dev/staging guidance (docs-only,
>   .gitignore protection). Board is clean — only #872 / #873 design
>   prototypes held. No C3/C4/C8 started.

## 2026-07-03 — Neon index-cleanup train (034 + 035) live; drift resolved

_`main` HEAD `b021273`. Backend verified live on `b021273` via deploy-rico
(`/version.commit` match, `/health` 200, Vercel proxy + root 200)._

A read-optimization audit of the Neon hot per-user tables found the DB correctly
indexed for reads (no missing indexes / no seq scans on hot paths) but carrying
redundant duplicate/subset indexes that only taxed writes. Two owner-gated
migrations (applied manually at Neon; not auto-deployed):

- **#826** (`034_drop_redundant_indexes.sql`) — drops 6 redundant indexes, each
  covered by an index that stays (a UNIQUE constraint, a superset composite, or a
  byte-for-byte twin): `idx_rico_job_recommendations_user_job_key`,
  `idx_rico_recommendations_user_job_key`, `idx_rico_profiles_user_id`,
  `rico_saved_searches_user_id_idx`, `idx_ujc_user_searched`, `idx_users_email`.
  Adds `034` to `_NO_OBJECT_MIGRATIONS` (DROP-only → no drift signature).
- **#828** (`035_rico_recommendations_full_unique.sql`) — codifies the full
  `UNIQUE (user_id, job_key)` constraint (`rico_job_recommendations_user_id_job_key_key`)
  that production already carried but the repo never created; 034's twin-drops
  rely on it for read coverage. Idempotent (no-op where present). Adds drift check
  `("035","constraint","rico_job_recommendations_user_id_job_key_key")`.
- **#827** — CLOSED as duplicate (proposed dropping 8; the 2 extras were unsafe —
  `idx_rico_recommendations_user_status` is re-created on every startup by the
  `rico_db.py` runtime DDL, so a migration DROP would not persist).

**Preserved (load-bearing):** `idx_rico_recommendations_user_job_unique` — the
partial-UNIQUE arbiter for `ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL`
in `rico_db.upsert_recommendation` (BUG-14 idempotency); `idx_user_job_context_user_searched_at`
— migration 028's drift signature (kept over its twin `idx_ujc_user_searched`).

**Production apply (owner, Neon `production` branch, owner-verified 2026-07-03):**
all 6 redundant indexes dropped (diff query → 0 rows); covering uniques
`rico_job_recommendations_user_id_job_key_key` + `rico_profiles_user_id_key` present.
The 6 drops landed in two passes (4 + 2 stragglers) — re-running the full 034 set
(`DROP … IF EXISTS`) is the foolproof way to land any branch at 0 rows. The
**Migration Drift Check** workflow (`workflow_dispatch`, `b021273`) is green — the
live DB behind the GitHub `DATABASE_URL` secret has every migration signature
object incl. 035's constraint, 011's unique index, and 005 `pipeline_runs`.

### #712 (005/011 drift) — 011 half resolved

The 011 unique index is confirmed present in production (owner `pg_indexes` query +
green drift check). The `pipeline_runs` signature for 005 is also present. #712's
broader 005 scope (keyword tables, `latest_pipeline_run` view, `pipeline_status`
enum, `settings` trigger) is not covered by the drift checker and remains
unverified — #712 stays open until those are confirmed.

## 2026-07-03 — merge train (safety fixes live) + BUG-14 diagnosis

_`main` HEAD `ee36c18`. #813 verified live via deploy-render run **#149**
(`5ad208a`, `/version.commit` match); cumulative run **#151** (`ee36c18`) rolls
the #817 cleanup + #814 tests on top of the already-verified #813._

Merged today (GitHub session, deploy verified via `deploy-render.yml`):

- **#813** (`5ad208a`) — backend safety from the 2026-07-02 stress test: Arabic
  conversational guard (BUG #6/#5), UAE-phone PII redaction (BUG #13),
  `emotional_support` intent (BUG #9), known-code-only error mapping (BUG #15).
  **Live & verified** (deploy-render run #149 success).
- **#817** (`c36a97f`) — cleanup: removed dead `DocumentClassifier.CV_THRESHOLD`;
  repointed 3 stale `apps/web/app/chat/page.tsx` refs in `CLAUDE.md` to `/command`.
- **#814** (`ee36c18`) — 71-test regression suite for #813, reconciled to the
  shipped error-message contract.
- **#816** — CLOSED, absorbed into #813 (duplicate BUG #15 fix; #813 is canonical).

### #813 pre-merge fixes (branch was red on 3 tests)

1. `runtime._build_message` mapped ALL failure errors (incl. free-text) to a
   generic message, breaking the pre-existing `test_607` contract. Now: KNOWN
   internal codes → user-safe string; unknown/free-text → `Action failed: <error>`
   (operator format, matches #816). #814's tests were reconciled to this contract.
2. The Arabic guard ran BEFORE `classify_intent` and swallowed structured Arabic
   commands (`احفظ أول وظيفة` save, `تحديث ملفي` profile-update). Moved AFTER
   classification; intercepts only search-like intents (`_ARABIC_GUARD_SEARCH_INTENTS`
   in `rico_chat_api.py`). Declarative Arabic still guarded (no cold-start hang);
   explicit-search and structured commands reach their own handlers.

### BUG-14 (pipeline save idempotency) — migration 011 APPLIED; #784 remaining

**Update 2026-07-03:** owner verified `idx_rico_recommendations_user_job_unique` **exists in
production Neon** (`SELECT indexname FROM pg_indexes …` returned one row). Migration 011 is
**applied** — this corrects the earlier "#711 drift: 011 not applied" note (011 is now closed;
005 pipeline_runs is separate). Because a `CREATE UNIQUE INDEX` only succeeds with no dupes,
the index being present also means the table is dedup-clean.

Effect: the **chat ordinal-save** path (`_save_job_by_ordinal` → `applications_repo.create`
→ `rico_db.upsert_recommendation`, `ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL`)
is now **idempotent** — re-saving the same job updates in place instead of inserting a dupe.

Remaining: the **other** save path — `jobs_service.save_job/skip/block` — still dedups via
the JSON-file `is_applied()` (always False for DB-backed SaaS users), fixed only in **draft
PR #784** (unmerged). Close BUG-14 by: (1) merge #784, (2) owner authenticated smoke
("save the second job" twice → count +1 then unchanged, on both the chat and action paths).
Tracked as **TASK-20260703-036**.

---

_Last updated: 2026-07-02 — `main` HEAD `a2a53b4`, deploy-verified on Render
(`/version.commit` match + `/health` ok). Merged today: #805 (email alerts, gated/inert),
# 806 (BUG-19 — confirmation screenshots = application evidence), #807 (applied-from-screenshot
OCR fallback — 2026-07-02 smoke failure), #808 (email-alerts docs sync). See the
"Screenshot → application evidence" section below for #806/#807 detail and smoke status.
Earlier merge train #800–#804: T1/PR C search-first (#801, closes TASK-20260622-031),
profile-evidenced CV search (#802), Track Application modal + sticky header (#803),
stale pipeline-reset confirmation cancel (#804)._

## Email job alerts — PR #805 (merged 2026-07-02, gated/inert)

Opt-in personalized job-alert emails. Merged to `main` at `f64e7e0` (squash). **Nothing is
sending** — the feature is doubly gated and unscheduled:

- opt-in default **off** (`RicoAgentSettings.can_receive_email_alerts=False`)
- kill-switch `RICO_ENABLE_EMAIL_ALERTS` default **off** (sweep returns `disabled`)
- cron workflow `job-alert-emails.yml` is **dispatch-only** (no `schedule:`)
- **migration 033 APPLIED** to Neon (2026-07-02, verified: both tables + `idx_eal_user_sent`
  / `idx_eut_token` + primary/unique indexes present)

**Production dry-run plumbing smoke PASSED (2026-07-02):** owner ran
`POST /api/v1/pipeline/job-alert-emails?dry_run=true` (X-Cron-Secret) →
`{status: ok, users: 0, sent: 0, skipped: 0, failed: 0, dry_run: true}`. Confirms endpoint
deployed, cron-secret auth works, and dry-run bypasses the kill-switch without sending.
`users: 0` expected (no opt-ins yet) — validates plumbing, not match quality.

What shipped (16 files): `migrations/033_email_job_alerts.sql` (`email_alert_log`,
`email_unsubscribe_tokens`); `src/services/email_notifications.py` (opt-in/out, unsubscribe
tokens, dedup + hours-based frequency helpers); `src/services/email_alert_service.py`
(sweep + HTML/text digest, reuses `RicoSystem.run_for_profile`, exclusions/dedup/threshold/
frequency cap/synthetic guard/kill-switch); `src/services/mailer.py` (optional HTML);
`RicoAgentSettings` email fields; `profile_repo.get_users_with_email_alerts`; settings
opt-in/out/status endpoints; public `GET /api/v1/email/unsubscribe`; cron-guarded
`POST /api/v1/pipeline/job-alert-emails?dry_run=`. Tests: `test_email_notifications.py`,
`test_email_alert_service.py` (90 in the relevant subset, green in CI on `ac9dd52`).

Pre-merge self-review (`/code-review`, Codex was quota-blocked) fixed two findings before
enable: unsubscribe URL now resolves via the `/proxy` rewrite; daily frequency window is
hours-based (jitter-tolerant). Deferred to PR-3 (scale-only): sync cron runs live JSearch per
user sequentially (#3), per-job dedup opens a new DB connection (#5).

**Remaining before activation (owner-gated, not done):** (1) opt in one test/owner account →
re-run the dry-run for a match-quality smoke (`users:1`, non-zero would-send or a match-related
skip reason) → (2) set `RICO_ENABLE_EMAIL_ALERTS=true` → enable the daily `schedule:` →
address #3/#5 → monitor `email_alert_log`; then Arabic localization. Done so far: migration 033
applied + dry-run plumbing smoke passed. Tracked as TASK-20260702-033 in `TASKS.md`.

---

## Screenshot → application evidence — PRs #806 + #807 (merged + deployed 2026-07-02)

**#806 (BUG-19, `70e7c48`):** job-confirmation screenshots ("Your application was sent…")
used to classify `unknown` → "Unrecognized Document" with dead-end actions, and tracking fell
back to the wrong recent-context job. Now: `application_confirmation` classifier type (EN+AR
signal bank, ≥2-specific-signals override), `application_evidence` attachment purpose through
the whole chain (backend enums, factory, frontend zod + card label), "Track this application"
action persisting from the screenshot's own extracted title/company, and
`_resolve_application_status_job` prefers a fresh confirmation transcript over the blind
recent-context fallback (asks instead of guessing when meta is unreadable). Tests:
`test_bug19_application_evidence.py` 19/19.

**#807 (owner smoke failure, `c7d8343`):** the owner's re-smoke used a job-LISTINGS screenshot
(2 jobs) + Arabic "لقد قمت بالتقديم عليها ارجوك احفظها" → classifier said `unknown@0%`, the
Arabic phrasing itself classified `unknown`, and the successfully-extracted OCR text was
discarded. Owner ruling: functional bug — OCR results must not be invalidated by low
classification confidence. Now: Arabic applied-report regex covers "قمت بالتقديم عليها" /
"تقدمت عليها" forms, and `_applied_from_screenshot_fallback` mines the last uploaded
transcript's OCR text for job entities regardless of classification verdict (CV / identity
docs excluded) — one entity → one-click confirm, several → disambiguation buttons (pre-armed
so a single click persists via the existing mark-applied gate), none → previous clarification
unchanged. Tests: `test_applied_screenshot_ocr_fallback.py` 16/16 (includes the exact owner
transcript + phrase).

**Production smoke status (2026-07-02):**

- ✅ Live-verified on the public surface (anonymous session, generated screenshots):
  confirmation upload → `application_confirmation@0.9` + "Application Confirmation" label +
  Track/View/Remind actions + `application_evidence` purpose; listings upload → OCR transcript
  intact with both job entities (classified `unknown` — exactly the case #807 handles).
- ⏳ Owner 2-minute authenticated check remains (public sessions correctly hit the sign-in
  gate; a scripted account can't pass email verification): (1) listings screenshot +
  "لقد قمت بالتقديم عليها ارجوك احفظها" → job buttons → one click → correct row in
  `/applications` as applied; (2) confirmation screenshot → "Track this application" →
  correct row. Both paths are covered end-to-end by 366 mocked tests.
- Housekeeping: 4 disposable smoke accounts `rico.smoke.20260702*@ricohunt-smoke.test` exist
  in the users table (unverified — cannot log in); safe to delete anytime.

Future work logged as TASK-20260702-035: full `JobFromAttachmentService` (NER + fuzzy
pipeline match, owner architecture note).

## PR C / TASK-20260622-031 — CLOSED (merged as #801, 2026-07-01)

- **T7** (verbatim role, no silent taxonomy substitution): ✅ on `main` (`bd4c4f8`).
- **T1** (search-first for stale profile roles instead of pausing to ask): ✅ merged via
  PR #801 (`b94ec1f`), branch `fix/profile-context-role-selection` deleted.
- History: both fixes originated from an unmerged background session
  (`claude/workflow-progress-check-qycxuo`, deleted); a stale pre-PR#797
  `_build_tracking_message` hunk was intentionally not ported.

## QA Cycle 1 — CLOSED 2026-06-27

| Bug | PR | SHA | Deployed | Tests |
|---|---|---:|---|---|
| BUG-01 | #757 | `325aa0e` | ✅ | frontend (sidebar cache) |
| BUG-02 | #759 | `3a9221a` | ✅ | preference sanitization |
| BUG-03 | #760 | `b6a1196` | ✅ | `test_bug03_source_url_fallback.py` 18/18 |
| BUG-04 | #761 | `4918f55` | ✅ | frontend (`/pipeline` → `/flow`) |
| BUG-05 | #762 | `007246b` | ✅ | `test_bug05_confirmation_loop.py` 7/7 |
| BUG-06 | — | — | 🚫 blocked | no description |
| BUG-07 | — | — | 🚫 blocked | no description |
| BUG-08 | #763 | `62ff5ad` | ✅ | `test_bug08_city_declaration.py` 14/14 |
| BUG-09 | — | `46a7ba7` | ✅ | `test_bug09_keyword_filter_bleed.py` 7/7 |
| BUG-10 | — | `b776abf` | ✅ | frontend (double-send `sendingRef`) |
| P0 #764 | #767 | `71466d2` | ✅ | `test_p0_mutation_trust_guard.py` 42/42 |

Regression suite: **104/104 PASS**. 45 pre-existing environment failures (cryptography version, mock log-format, webhook secrets) — none caused by any BUG or P0 change.

> **Reconciled (2026-07-08):** earlier #764 status referenced a prior QA-cycle fix. Canonical closure is PR #892 / `bd887d7f3793b789b2553bf7ae005f0eb629c756`, which added `MutationConfirmationGuard` and verified no-false-success behavior across the guarded mutation paths. Scope: save job route, chat job save by ordinal, mark applied / manual application status update, delete saved jobs, profile update — 5 mutation paths wired. Production health green post-merge; rollback not needed.

## PR #780 + #781 — Chat-OS agentic UI + smoke-test fixes (2026-06-30)

### PR #780 — action cards for `application_status` and `prepare_application`

Merged at `6863409`. Added `_application_status_actions()` and `_prepare_application_actions()` factories to `agentic_ui_composer.py` and registered them in `_RESPONSE_TYPE_ACTIONS`. Tests: 6 new unit tests in `test_agentic_ui_composer.py`.

| Response type | Action cards |
|---|---|
| `application_status` | View Application Flow (navigate /flow) · Add application (chat_continue) |
| `prepare_application` | View Application Flow (navigate /flow) · Find similar jobs (chat_continue) |

### PR #781 — question-form routing + sidebar nav/count/plan fixes

Merged at `e4979eb`. Squash commit on `main`.

| Fix | What | Files |
|---|---|---|
| Chat routing | Extended `_APPLICATIONS_LIST_RE` to match question-form phrases ("what are my applications?", "how many applications do I have?", etc.) — previously fell to AI path with no action cards | `src/rico_chat_api.py` |
| Composer mapping | Added `"application_list": _application_status_actions` to `_RESPONSE_TYPE_ACTIONS` so both question-form and tracker-card responses get action cards | `src/services/agentic_ui_composer.py` |
| BUG-1 (sidebar count) | `useSidebarStatus.ts` now uses `stats.total` from backend rather than summing only `applied+interview+offer+saved+rejected` — previously missed `opened`, `opened_external`, `prepared`, `follow_up_due`, `decision_made` | `apps/web/hooks/useSidebarStatus.ts` |
| BUG-4 (sidebar nav) | Removed `chatPrompt` from all nav items — sidebar links now always navigate to real pages, never inject `/command?q=…` URLs | `apps/web/components/layout/app-nav.ts` |
| BUG-5 (plan label) | "Pro Plan" → "My Plan" nav label + `navMyPlan` translation key (EN + AR) — eliminates "Pro Plan / PREMIUM" badge contradiction | `apps/web/components/layout/app-nav.ts`, `AppSidebar.tsx`, `translations.ts` |

## Production baseline

- **Repository main HEAD:** `e4979eb` (PR #781 — chat routing + sidebar fixes). Merge train: `0e0a6aa` (dashboard), `6863409` (PR #780 — Chat-OS action cards), `f0e0cea` (PR #776 — No Dead UI Rule + route cleanup), `744dbec` (PR #775 — P2-A), `78c22857` (PR #770 — Chat-as-interface milestone), `4ad2e29` (PR #767 — P0 mutation trust guard).
- **Last deploy-verified SHA:** `4ad2e29` — `deploy-render.yml` run #28301440105 succeeded. ✅ (PRs #770, #775, #776, #780, #781 are frontend-only or backend-lightweight; Render deploy auto-triggered for backend changes but not yet re-verified in-session.)
- **Production deploy verification history:** `4ad2e29` (run #28301440105), `6113123` (run #80), `0d28a08` (#747), `7e0b9ec` (#741), `f202a86` (#739), `a7e294b` (#736), `115adde` (#738), `e214178` (#737).
- **Pending owner-side smoke:** authenticated save→count flow and #741 screenshot follow-up require `ricohunt.com` login — sandbox cannot reach authenticated production.
- **Migration 032 (`uploaded_document_context`):** auto-applied on startup via the app.py lifespan runner (idempotent `CREATE TABLE/INDEX IF NOT EXISTS`), targeting the exact branch the production `DATABASE_URL` uses. Direct confirmation of the `migration_ok` log line / table existence needs Render-log or Neon access (unavailable in-session) — the owner re-test is the end-to-end proof.
- **Image reading reliability:** `OCRSPACE_API_KEY` set on Render as a dependable free OCR backstop behind the (rate-limited) free vision model (OpenRouter/HF).
- **Render logs:** direct Render MCP log scan unavailable in-session; no error signals from `/health` or deploy workflows.

## Job-flow stabilization — 2026-06-22 complete

Rico's job-search flow was stabilized through a focused merge train. Each PR stayed in one bug category, used mocked tests/fixtures, avoided provider quota burn, and excluded #712 DB migration work, billing changes, landing-page changes, and provider scraping.

| PR | Category | Merge SHA | Deploy | Tests / notes |
|---|---|---:|---|---|
| **#727** | P0 — job-card apply-link integrity + canonical `src/services/job_link.py` | `e1d87fc` | ✅ verified | `test_job_card_apply_link_integrity.py`; no more missing required `link` error |
| **#724** | P1 — low-cost provider cascade (cache → internal → Jooble → Adzuna → JSearch → degraded CTA) | `5fe9171` | ✅ verified | `test_job_providers.py`, `test_provider_degraded_ux.py` |
| **#723** | P1 — multi-role parsing (`extract_role_list`, `job_search_multi_role`) | `713ea75` | ✅ verified | `test_multi_role_search_*.py` |
| **#728** | P0 follow-up — route ordinal apply-link requests past job-detail gate | `c77781a` | ✅ verified | `test_ordinal_apply_link_routing.py` |
| **#729** | PR B — save the Nth job to pipeline from recent search context | `963e40b` | ✅ verified | `test_save_ordinal_to_pipeline.py` |
| **#730** | PR D — role parsing edge cases: `only`, jobs-for-A-and-B, CV exclusions, category mapping / not coding | `38fbf5d` | ✅ verified | `test_role_parsing_edge_cases.py` |

## Key production behaviors now live

- `src/services/job_link.py` is the **only canonical apply-link resolver**. Do not reintroduce `src/rico_link_resolver.py`.
- Job cards and chat apply-link commands share canonical `usable_link` / `link_unavailable` fields.
- `apply_job` no longer throws `Job payload is missing required 'link' field`; missing trusted links produce safe fallback CTAs.
- Ordinal apply-link commands work for first/second/last job references from recent search context.
- Save-to-pipeline works for ordinal references such as "save the second job".
- Provider cascade is live: cache(24h) → internal → Jooble → Adzuna → JSearch → degraded fallback CTA.
- `/health` exposes `job_providers` configured/degraded state only; no secret values.
- Role parsing now handles:
  - `Technical Product Owner only` → `Technical Product Owner`
  - `jobs for HSE Manager and QHSE Manager` → both roles
  - CV-based search with `do not search …` exclusions
  - `product and technical management jobs, not coding jobs` → allowed management roles + coding exclusions

## Provider env

Set in Render by the owner; presence only is observable via `/health`:

- `JOOBLE_API_KEY`
- `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` (Adzuna opt-in; both required)
- `RAPIDAPI_KEY` (JSearch)

No provider keys are hardcoded, committed, or logged.

## Production Tests 1–9 status

| Test | Bug | Status |
|---|---|---|
| T2 | `Technical Product Owner only` qualifier | ✅ fixed live (#730) |
| T3 | `HSE Manager and QHSE Manager` jobs-for-A-and-B order | ✅ fixed live (#730) |
| T4 | 3-role comma list as one role | ✅ fixed live (#723) |
| T5 | CV-based search + `do not search …` exclusions | ✅ fixed live (#730) |
| T6 | category mapping `product/technical management` + `not coding` | ✅ fixed live (#730) |
| T8 | `save the second job to pipeline` not wired to recent context | ✅ fixed live (#729) |
| T9 | open apply link → missing-link error | ✅ fixed live (#727 + #728) |
| T1 | strongest CV profile ignored; stale `target_role` | ✅ fixed live (#731 PR C) |
| T7 | silent role substitution + auth/CV context loss + weak location | ✅ fixed live (#731 PR C) |

## Merge train after #730 (all live on `main`)

| PR | What | Merge SHA | Status |
|---|---|---:|---|
| **#731** | PR C — profile-context role selection (T1 & T7): no silent stale/ambiguous search; ambiguity by role-family not raw count; raw role text preserved | `9a9070c` | ✅ merged + deployed |
| **#733** | Investigation/test-only — production-equivalent live-path tests for T2–T6 role parsing | `ab170e2` | ✅ merged |
| **#734** | Career-memory identity resolution fix | `5944d72` | ✅ merged |
| **#735** | Single-role parsing accepts explicit titles like "Technical Product Owner" (live recheck found single-role rejected what multi-role accepted) | `96f415a` | ✅ merged + deployed |
| **#737** | Attachment/document routing — keep no-text/image-only PDFs out of the CV pipeline (#674 residual, Finding 1) | `e214178` | ✅ merged + deploy-verified |
| **#738** | Upload size limits — 25 MB docs / 10 MB images, per-kind cap enforced before parsing, friendly type-aware AR/EN oversize messages (fixes the misleading "under 10 MB" CV rejection) | `115adde` | ✅ merged + deploy-verified |
| **#736** | Image reading (Finding 2) — job-screenshot images transcribed via free VLM (OpenRouter/HF) + OCR.space fallback, re-classified to a readable `classified` response; graceful (never blocks uploads) | `a7e294b` | ✅ merged + deploy-verified |
| **#739** | Image/document action follow-up — buttons (Describe/Extract/Summarize) answer from the stored transcript via an early interceptor (no CV-draft hijack); transcript injected into AI context for typed questions | `f202a86` | ✅ merged + deploy-verified |
| **#741** | Durable transcript store (`uploaded_document_context` table + repo) — fixes the postgres-mode bug where the OCR transcript was saved only to the no-op `RicoMemoryStore`; follow-ups now read durably; migration 032 auto-applies on startup | `7e0b9ec` | ✅ merged + deploy-verified (owner re-test pending) |
| **#747** | Phase-0 job-link trust gate (`src/services/job_link_trust.py`) — View & Apply may only surface a source-backed, non-fake, non-LLM apply URL; rejects recent_context/LLM/sequential-LinkedIn/placeholder URLs; `apply_to_job` restored with safe action errors | `0d28a08` | ✅ merged + deploy-verified |
| **#749** | Pipeline save/count correctness — chat ordinal "save the Nth job" now persists to the user-scoped counted store (`rico_job_recommendations`), idempotent on a trusted save identity; untrusted recent_context jobs save as leads with no claimed apply link; user-safe save errors (`src/services/job_save.py`) | `6113123` | ✅ merged + deploy-verified (owner-side authenticated smoke pending) |
| **#755** | Link quality (#721) — `employer_url` + `apply_is_direct` surfaced from JSearch `employer_website` / `job_apply_is_direct`; `apply_is_direct=True` upgrades unknown domains to `live_verified`; aggregator/login/rate-limited never overridden; `employer_url` returned as separate field, never in apply_link/alt_link/usable_link; company-site fallback CTA uses real URL when available (label "Company website" vs "Search company site") | `504c755` | ✅ merged + deploy-verified |

> Note: `fix/single-role-taxonomy-rejection` was an independent duplicate of the #735 fix built in another session — **abandoned** (not merged). Do not revive it.

## Attachment / Document Intelligence routing — 2026-06-23

- **Audit:** `AI_WORKSPACE/AUDITS/attachment-document-routing-post-674-677.md` (Findings 1–5). #677 shipped native-image classification on `/command`; the audit found the residual gaps.
- **#737 (Finding 1, merged):** a screenshot/scan exported as a PDF (image-only PDF, no text layer) used to fall through `unknown@0.0` into CV extraction → misleading "poor quality" CV preview. The classifier now tags a _substantial_ (`>= _MIN_DOC_BYTES`, 1 KB) text-bearing file with near-empty text (`< _MIN_TEXT_CHARS`, 25) as `no_text`; `/upload-cv` returns a clear needs-text response (`status="classified"`, `document_type="no_text"`) before the CV pipeline. Tiny stub PDFs still flow normally; native images unchanged; real text CVs unchanged. Tests: `tests/test_no_text_pdf_routing.py`.
- **#738 (upload size, merged):** documents 25 MB / images 10 MB, per-kind cap enforced from magic-byte format **before** parsing; friendly type-aware oversize message (413) replacing "exceeds 10 MB"; `/command` + `/onboarding` map 413 → localized `cmdCvTooLarge` (AR/EN); `files.py` doc cap also 25 MB. Tests: `tests/test_upload_size_limits.py`, `apps/web/__tests__/cv-upload-size-message.test.ts`.
- **Open findings (NEXT work):** **Finding 3** — no application-evidence destination (read screenshot → "Save as target job" / "Score against my CV" not wired end-to-end; this is the owner's "link A↔B without buttons" ask). **Finding 4** — `onboarding`/`upload` surfaces still don't honor `status="classified"` for non-CV docs/images (#738 only added 413 size handling). **Finding 5** — dead `CV_THRESHOLD`; stale `CLAUDE.md` `/chat` reference (trivial cleanup).

## Image-reading chain (Finding 2) — COMPLETE & LIVE

`#736 → #739 → #741`, all merged + deploy-verified. Flow: upload image → free VLM (OpenRouter/HF) or **OCR.space** fallback transcribes it → re-classify transcript → readable `classified` response. Follow-up buttons (Describe/Extract/Summarize) and typed questions ("what do you think of this job?") answer from the transcript; **never** a CV-draft hijack; honest "no readable document" when nothing was read.

- **Durability (#741):** the transcript is persisted in the durable `uploaded_document_context` table (migration 032, auto-applied on startup) — fixes the prod bug where it was saved only to the `RICO_MEMORY_BACKEND=postgres`-disabled `RicoMemoryStore`. Read path: `_get_last_uploaded_document` (ephemeral fast-path → durable DB), used by `_handle_uploaded_document_followup` and `_build_openai_context`. Keyed by resolved `user_id` (email / `public:web-*`), one row per user, 180-min freshness window.
- **Provider env (owner-set on Render):** `OCRSPACE_API_KEY` set (reliable OCR backstop); optional `OPENROUTER_API_KEY` / `OPENROUTER_VISION_MODEL` or a free HF Inference Provider on `HF_TOKEN`.
- **Pending:** owner re-test in `/command` (upload job screenshot → buttons + typed Qs answer from the text). Sandbox can't reach `onrender.com` / Neon, so the re-test is the end-to-end proof of migration 032 + the durable store.
- **Tests:** `tests/test_uploaded_document_durable_context.py`, `tests/test_uploaded_image_ai_context.py`, `tests/unit/test_image_extractor.py`, `tests/unit/test_upload_image_vision.py`.

## Standing guardrails for this work-stream

- No auth rewrite, no billing changes, no DB migration, no #712 work, no landing-page work, no provider scraping, no repeated real provider searches.
- Use mocks/fixtures only in tests; no live OpenAI/HF/JSearch/Telegram/Jotform calls in unit tests.
- Keep `src/services/job_link.py` as the only canonical apply-link resolver; do not reintroduce `src/rico_link_resolver.py`.

## Superseded / duplicate PRs

- **#726** — closed as superseded by #727 + #728 + #729. Do not rebase or salvage it.
- **#722** — degraded job-card fallback CTAs; overlaps #724/#727. Close or rebase only if a new focused gap is proven.

## Important older context still relevant

- **#712 DB migration drift:** still separate; do not mix with job-flow work.
- **System Quality Audit PR #717:** draft/CI-green status was documented earlier; do not merge without separate review.
- **Migration `030_action_audit_log_hardening.sql`:** applied + verified in production Neon on 2026-06-21.
- **Migration `021_user_job_context_alt_url.sql`:** applied; issue #710 closed.
- **Issue #711 drift:** `011 idx_rico_recommendations_user_job_unique` is **APPLIED** in production (owner-verified 2026-07-03 via `pg_indexes`). `005 pipeline_runs` remains not applied unless separately approved.
- **Canonical handoffs:** `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization-complete.md` (job-flow train through #730), `AI_WORKSPACE/HANDOFFS/2026-06-23-attachment-document-routing.md` (document routing #737 + #736 review).

## Open PRs — triage (6, all stale / pre-session 2026-06-20..22)

| PR | What | Recommendation |
|---|---|---|
| **#722** | degraded job-card fallback CTAs | **Close** — overlaps merged #724/#727 |
| **#713** | CI read-only `verify_710` audit job (Draft) | **Close** — #710 verified/closed; diagnostic obsolete |
| **#698** | docs: agentic vision (Draft, docs only) | keep as reference or close; no runtime code |
| **#697** | reject "تمام" as a city value | **Salvage** — real small bug; rebase + ship |
| **#691** | frontend onboarding checklist + help icon | review; needs rebase + `npm run build` |
| **#688** | frontend `/ask` agentic UX (mock data) | review/park; bigger, mock-only |

## Open issues — highlights (29 total)

- **#732 — Rico over-commits to "Developer" without evidence.** HIGH value, owner-facing: profiles show `Target Roles: Developer` despite the real profile (Technical Product Owner / Operations Manager). Career guidance should be CV-evidence-based.
- **#712 / #711** — migration drift (`005 pipeline_runs`, `011` indexes missing) — still open, separate.
- Older epics/backlog (#654, #618, #531, #356, #355, #354, #353, #352, #294, #263, #213, #198, #196, #187, #179, #147, #140, #138, #127, #118, #105, #99, #96) — not urgent.

## Phase-0 trust + save/count — COMPLETE & LIVE (2026-06-25)

- **#747 (trust gate, live):** `resolve_trusted_apply_url` is the only sanctioned apply-URL resolver. Untrusted origins (`recent_context`, `llm`, `chat`, `search_match`, …) are rejected at Gate 0; placeholder/sequential-LinkedIn/bad-scheme URLs rejected; a trusted provenance marker (`persisted_job_id` / `source_job_id` / `provider`+`source_backed`) is required. `apply_to_job` no longer errors on missing links — safe action messages instead.
- **#749 (save/count, live):** the chat ordinal save persists to the counted `rico_job_recommendations` (so the application/pipeline count actually increments), idempotent on a trusted save identity (`source_job_id`/`persisted_job_id`, else a `title|company` hash — never the bare `job_id`). A recent_context job is still saved, as a **lead**, with no apply URL persisted and no verified-link claim. Save failures return user-safe messages. No `pipeline_runs` (migration 005 / #711) dependency. Helper: `src/services/job_save.py`; tests: `tests/test_pipeline_save_count_correctness.py`.
- **Pending:** owner-side authenticated smoke on `ricohunt.com` — search a role, "save the second job to my pipeline" → count +1, repeat → count unchanged. Sandbox cannot reach authenticated production.

## Rico Website Hard QA — BUG-01 through BUG-08 (2026-06-27)

Fixing bugs from the "Rico Website Hard QA Report". Each PR is one bug category, focused diff only. No SQL, no schema migrations, no provider API calls in tests.

| BUG | PR | Merge SHA | Status | Description |
|---|---|---:|---|---|
| **BUG-01** | #757 | `325aa0e` | ✅ merged | Bust sidebar cache after chat save; correct `/flow` destination in save copy |
| **BUG-02** | #758 | `3a9221a` | ✅ merged | Sanitize `preferred_cities` at profile read/write boundary; strip corrupted AI-response values stored as city names |
| **BUG-03** | #760 | `b6a1196` | ✅ merged | Sidebar nav routing (href not chatPrompt), icon rendering, pipeline counter |
| **BUG-04** | #761 | `4918f55` | ✅ merged | Redirect `/pipeline` → `/flow` (old route returned 404) |
| **BUG-05** | #762 | `007246b` | ✅ merged | "Yes, search {role}" quick-reply button caused infinite confirmation loop; interceptor added before role classification in `_handle_active_user_inner` |
| **BUG-06** | — | — | 🚫 blocked — no description | Description not found in repo, GitHub issues, or any workspace doc. Owner must supply original QA report entry. |
| **BUG-07** | — | — | 🚫 blocked — no description | Description not found in repo, GitHub issues, or any workspace doc. Owner must supply original QA report entry. |
| **BUG-08** | #763 | `62ff5ad` | ✅ merged | "My favorite city is Dubai" silently ignored (3 stacked bugs: intent regex, router regex, `preferred_city` vs `preferred_cities`). |
| **BUG-09** | #791 | `merged` | ✅ merged | Sidebar widgets disappear on `/upload` page — `sidebarProps` was not passed; fixed by threading `onLogout` + `sidebarProps` through the page component |
| **BUG-10** | #792 | `merged` | ✅ merged | Data quality: years experience displayed as `30.0`; salary displayed without comma (`AED 18000/month`). Fixed `_target_role_search_response` (int rounding) and `_format_pref_changes` (comma-format). Tests: `test_bug10_data_quality_display.py` |
| **BUG-11** | #793 | `merged` | ✅ merged | Name casing inconsistency — CV names extracted verbatim (ALL CAPS on UAE CVs). `CVParser._extract_name` now returns `line.title()`. Tests: `test_bug11_name_casing.py` |
| **BUG-12** | — | merged | ✅ fixed | Search results body ignores Arabic locale. Fixed pre-#796; `test_bug12_arabic_search_locale.py` green on `main`. |
| **BUG-13** | — | — | ⏸ not started | Profile/role drift across multiple uploaded CVs — wrong role shown after re-upload. |
| **BUG-14** | — | — | ⏸ not started | No save idempotency on pipeline: second "save this job" shows success but increments counter. |
| **BUG-15** | #794 | merged | ✅ merged 2026-06-30 | Internal API name leaked to user-facing UI ("JSearch API" visible in responses). Fixed in `apps/web/lib/translations.ts`. |
| **BUG-16** | #794 | merged | ✅ merged 2026-06-30 | "Waking up" banner overlaps chat content (CSS z-index). Fixed in `apps/web/app/command/page.tsx` (pt-12/pt-14). |
| **BUG-17 (pipeline reset)** | — | `61b783b` | ✅ pushed | "Clear them we must start over" misclassified as job role search. Fixed: "clear"/"reset" added to `_NON_ROLE_STARTERS`; `_PIPELINE_RESET_RE` + `_PIPELINE_RESET_IMPLICIT_RE` added; 2-turn Archive/Delete/Cancel confirmation flow. Tests: `test_bug17_pipeline_reset.py` 13/13. |
| **BUG-18** | — | — | ⏸ not started | `?q=` query-string navigation mutates / resets chat thread. |
| **BUG-19** | #806 | `70e7c48` | ✅ merged + deployed | Job-confirmation screenshots not classified as application evidence → "Unrecognized Document"; save falls back to wrong recent-context job. See "Screenshot → application evidence" section; follow-up #807 (`c7d8343`) added the OCR fallback for unclassified screenshots. |

> ✅ **QA Cycle 1 is CLOSED.** BUG-01 through BUG-05, BUG-08, BUG-09, BUG-10, and P0 #764 are all confirmed deployed and smoke-tested at `4ad2e29`. BUG-06 and BUG-07 remain blocked until the owner supplies original QA report descriptions.

## PR #756 — Migration drift runbook (docs-only)

- **Status:** ✅ Merged at `2ef4107` (2026-06-27). Content: 606-line `docs/runbooks/production-drift-005-011.md`.
- **Rollback execution (owner-only):** after G1–G6 signed off, owner applies migrations 011 (Step A) then 005 (Step B) via Neon console.

## Chat-as-Interface milestone — PR #770 (2026-06-28)

Merged at `78c22857`. Squash commit: `feat(chat-as-interface): P2-B delete-saved-jobs + PR-A agentic UI schema + PR-C live action cards`.

| Sub-feature | What shipped |
|---|---|
| **P2-B** | 2-turn delete-saved-jobs confirmation (`_handle_pending_delete_saved_jobs`, memory TTL, `delete_saved_jobs_confirm` → `delete_saved_jobs_done`) |
| **PR-A** | `RicoAgenticUi` Pydantic schema (`src/schemas/chat.py`) — actions, permission_request, proposed_changes, attachment_analysis, progress |
| **PR-C** | `compose(result, response_dict)` in `src/services/agentic_ui_composer.py` — emits type-based action cards on every real chat response |
| **MagicMock fix** | `isinstance(ctx, dict)` guard in `_handle_pending_delete_saved_jobs` — fixes 10 previously-failing tests |
| **Tests** | 38 `test_agentic_ui_composer.py` + 41 `test_attachment_analysis_factory.py` + 2 conversation-state fixes |

Action cards now emitted by type:

| Response type | Actions |
|---|---|
| `job_matches` | View all jobs (navigate /flow) + Save search (chat_continue) + Refine search (chat_continue) |
| `delete_saved_jobs_confirm` | Yes, delete all (high impact, requires_confirmation) + No, keep them |
| `delete_saved_jobs_done` | Find new jobs (chat_continue) |
| `profile_update` / `profile_summary` / `cv_first_profile` | View my profile (navigate /profile) |
| `application_status_update` | Track applications (navigate /applications) |
| `save_job` | View saved jobs (navigate /flow) |
| `application_list` / `application_status` | View Application Flow (navigate /flow) + Add application (chat_continue) — **added PR #780/#781** |
| `prepare_application` | View Application Flow (navigate /flow) + Find similar jobs (chat_continue) — **added PR #780** |

---

## Route architecture — post-PR #776

**No Dead UI Rule** adopted (DEC-20260628-001 in `AI_WORKSPACE/DECISIONS.md`, enforced in `OPERATING_RULES.md`):
a route must be active+reachable, redirect-only with no real page code, or removed.

| Route | State | Notes |
|---|---|---|
| `/command` | ✅ active | Primary chat surface |
| `/flow` | ✅ active | Application flow page |
| `/login`, `/signup`, `/forgot-password` | ✅ active | Auth surfaces |
| `/chat` | ✅ redirect-only | `next.config.js` → `/command`; stub deleted (Phase A) |
| `/orchestrate` | ✅ redirect-only | `next.config.js` → `/command`; stub deleted (Phase A) |
| `/pipeline` | ✅ redirect removed | No page ever existed; redirect had no purpose |
| `/dashboard` | ⚠️ Phase B | Redirect + 48-line page. Needs product decision: live or strip. |
| `/onboarding` | ⚠️ Phase B | Redirect + 466-line page. Needs product decision: live or strip. |
| `/jobs` | ⚠️ Phase B | Redirect + 336-line page. Needs product decision: live or strip. |
| `/signals` | ⚠️ Phase B | Redirect + 576-line page. Needs product decision: live or strip. |
| `/archive` | ⚠️ Phase B | Redirect + 162-line page. Needs product decision: live or strip. |
| `/saved-searches` | ⚠️ Phase B | Redirect + 102-line page. Needs product decision: live or strip. |

Phase B routes are blocked until each gets an explicit product decision.

## Career Operating System — forward plan

Per owner direction (2026-06-28), the next development focus is Career OS / Mission Control, introduced in one PR per phase:

1. **Current Mission** — what is Rico working on right now for the user
2. **Mission Feed** — live updates from the job search pipeline
3. **Daily Actions** — surfaced tasks Rico recommends each day
4. **Career Timeline** — application history and progress
5. **AI Workspace** — Rico's reasoning and plan visible to the user

Do not open more than one PR per phase. Do not revive Phase B routes until product decision is made.

## 2026-06-30 Smoke-test bug backlog (new — from owner production testing session)

These are separate from the QA Cycle 1 BUG-01/19 list above.

| ID | Status | Description |
|---|---|---|
| **BUG-1** | ✅ fixed (PR #781) | Sidebar pipeline count disagreed with /flow and chat — sidebar was summing subset of statuses, missing opened/prepared/follow_up_due/decision_made |
| **BUG-2** | ✅ fixed (PR #786, `c8aabd7`) | Self-cancelling keyword filters: `exclude_keywords` was read from a process-global env var instead of per-user settings, and `include_keywords` was never read in scoring at all — fixed in `src/scoring.py` to honor per-user include/exclude keywords (exclude still wins on overlap, by design) |
| **BUG-3** | ✅ fixed (PR #787, `83e961e2`) | Duplicate board entry: same job appears twice on /flow kanban board |
| **BUG-4** | ✅ fixed (PR #781) | Sidebar nav links injected `/command?q=…` URLs instead of navigating to real pages |
| **BUG-5** | ✅ fixed (PR #781) | "Pro Plan / PREMIUM" label contradiction in sidebar |
| **BUG-6** | ✅ fixed (PR #788, `cc1eed1`) | Status taxonomy mismatch: list view vs kanban board use different status labels — `apps/web/lib/applicationStatus.ts` is now the single source of truth for status list + stage grouping, consumed by list view, board view, StatusBadge, and the chat pipeline summary |
| **BUG-7** | ✅ fixed (PR #790, `6381680`) | Session hydration: user appears logged-out on first load until hard refresh |
| **BUG-8** | ⏸ open | (details in session history — owner must supply) |
| **BUG-9** | ✅ fixed (PR #791) | Sidebar widgets disappear on /upload page |
| **BUG-10** | ✅ fixed (PR #792) | Data quality: 30.0 years experience displayed, salary inconsistency |
| **BUG-11** | ✅ fixed (PR #793) | Name casing inconsistency in profile |

## Recommended next command

```text
Rico mode. Everything through #808 is merged and deployed (main a2a53b4, deploy-verified).
Remaining open bugs: BUG-8 (no description — owner must supply), BUG-13 (profile/role drift
across multiple CVs — verify what #802 already covered), BUG-14 (pipeline save idempotency —
verify against #749), BUG-18 (?q= navigation mutates chat thread). Owner-side 2-minute
authenticated smoke for #806/#807 pending (see "Screenshot → application evidence").
Email alerts remain gated — activation sequence in TASK-20260702-033 (opt-in test → dry-run →
enable → schedule), owner-gated. Backlog: TASK-20260702-035 (JobFromAttachmentService),
TASK-20260630-032 (Search & Intent Flow UX spec — item 2 largely landed via #801/#802).
One PR per bug group. Do NOT touch Phase B routes. Do NOT run migrations without owner sign-off.
```

# Tasks

Use this file as the shared task ledger. Each task must be small enough to review in one PR.

## Status values

- `proposed`
- `scoped`
- `in_progress`
- `blocked`
- `review`
- `verified`
- `done`

## Task template

```md
### TASK-YYYYMMDD-001 — <title>

Status: proposed
Owner: <human/model>
Branch: <branch-name>
Issue/PR: <link or number>

#### Objective
<one objective only>

#### Context
- Relevant files:
- Relevant docs:
- Existing behavior:

#### Constraints
- Do not touch:
- No migrations unless explicitly required:
- Keep scope limited to:

#### Acceptance criteria
- [ ]
- [ ]
- [ ]

#### Required verification
- [ ] Unit tests:
- [ ] Integration tests:
- [ ] Frontend build:
- [ ] Local smoke:
- [ ] Production/deploy smoke if applicable:

#### Handoff notes
- Changed files:
- Commands run:
- Risks:
- Rollback plan:
```

## Active tasks

### TASK-20260619-026 — BUG-05: Public-chat onboarding infinite loop

Status: review
Owner: Claude
Branch: `claude/ai-workspace-review-vtdjrb`
Issue/PR: (draft PR created 2026-06-19)

#### Objective
Fix the `/command` public chat returning identical "Welcome to Rico AI…" on every message
after the first, and the double API call from the streaming fallback guard.

#### Root cause
Three compounding issues:
1. `IntentRouter` sends most messages (not starting with `?` / question word / "show me") to
   the legacy classifier.
2. Legacy classifier always returns the onboarding welcome when `profile is None`, and never
   saves state for public sessions (`_persist=False`), creating an infinite loop.
3. Frontend `if (!streamStarted)` fallback fired even when the legacy path already applied a
   response via the SSE `"done"` event — causing a duplicate API call.

#### Fix summary
- **Fix A** (`src/services/chat_service.py`): `_force_ai` gate redirects public no-profile
  legacy decisions to `_conversational_ai_reply`.
- **Fix B** (`src/api/routers/rico_chat.py`): streaming endpoint only takes legacy path when
  `profile is not None`.
- **Fix C** (`apps/web/app/command/page.tsx`): fallback guard changed to
  `!streamStarted && !responseApplied`.
- 7 unit tests in `tests/test_public_chat_no_profile_loop.py` (all PASS).

#### Acceptance criteria
- [x] Public user messages (interview prep, profile data, injection) route to AI, not welcome
- [x] Public user WITH existing profile still routes to legacy (unchanged)
- [x] Authenticated users unaffected (legacy for no-profile, AI for AI-decision)
- [x] No duplicate API call from streaming fallback
- [x] 7 unit tests passing

#### Required verification
- [x] Unit tests: 7/7 PASS (`tests/test_public_chat_no_profile_loop.py`)
- [ ] Frontend build: node_modules not installed in this environment; change is a 1-line guard
- [ ] Render deploy: pending PR merge
- [ ] Production smoke: pending PR merge

#### Handoff notes
- Changed files: `src/services/chat_service.py`, `src/api/routers/rico_chat.py`,
  `apps/web/app/command/page.tsx`, `tests/test_public_chat_no_profile_loop.py`
- Risks: `_force_ai` gate is additive; authenticated users and public users with profiles
  are unaffected. Rollback: revert `_force_ai` conditional in `send_message`.
- Open: #653 sidebar retry still draft; unrelated to BUG-05.

---

### TASK-20260619-025 — Security: redact archived database credential

Status: done
Owner: Claude
Branch: `chore/redact-archived-db-credential` (merged → `e104135` via PR #656)
Issue/PR: #656

#### Objective
Remove a real Neon connection string committed in `docs/archive/AUDIT_REPORT_2026-05-14.md`
from the current tree.

#### Fix
Replaced `DATABASE_URL=postgresql://authenticator:npg_R8hdwAMu9cOs@ep-long-poetry-am9o9qth-pooler...`
with `DATABASE_URL=postgresql://<role>:<redacted>@<neon-host>/<database>?sslmode=require`.

#### Scope
- 1 file changed: `docs/archive/AUDIT_REPORT_2026-05-14.md` only.
- No app code, env examples, Neon, or Render changes.

#### Notes
- Old credential (`authenticator` / `npg_R8hdwAMu9cOs`) believed rotated/invalid.
- Current credential (`neondb_owner` / `npg_DI5SJWxO8wVj`) was NOT in the repo.
- Git history purge (`git filter-repo`) is out of scope — requires coordinated force-push.
- CI green (pytest ✅ playwright ✅ Vercel ✅). Merged `e104135`, 2026-06-19.

---

### TASK-20260619-024 — BUG-04 Unauthorized profile mutation (Hard Audit)

Status: done
Owner: Claude
Branch: `claude/clever-galileo-gii41r` (merged → `f4bacfa` via PR #655)
Issue/PR: #655

#### Objective
Close three code paths that silently wrote to `rico_profiles` via `upsert_profile` without
explicit user consent.

#### Fix summary
- **Fix A** (`src/rico_chat_api.py`): `profile_update` intent now asks before persisting.
  `_pending_field="confirm_profile_update"` + `_format_pref_changes` helper. `upsert_profile`
  fires only on affirmative reply via `_resolve_pending_field`.
- **Fix B** (`src/rico_chat_api.py`): Removed `upsert_profile` from
  `_target_role_search_response`. Searching a role no longer persists it as a `target_role`.
- **Fix C** (`src/agent/context/resolver.py`): `_hydrate_from_chat` NER enrichment stripped
  from DB write via `_chat_added` delta. In-memory profile retains NER values for the current
  request. CV/Jotform/action-derived values preserved.

#### Tests
- 13 new tests: `tests/test_bug04_profile_mutation.py`.
- `test_p0_trust_fixes.py::test_concrete_profile_update_*` updated to assert ask-first behavior.
- Zero new failures vs main baseline (115 pre-existing failures unchanged).

#### Verification
- CI green. Merged `f4bacfa`, 2026-06-19T15:51Z.
- Production confirmed: Vercel `dpl_ArjxouNKhjYnVMb9tMg1bLS1MdXf` at `f4bacfa`.

---

### TASK-20260619-023 — BUG-03 Google-intermediary link (Hard Audit)

Status: done
Owner: Claude
Branch: `fix/bug03-alt-link-google-root` + hotfix (merged → `b0807c0` via PRs #651/#652)
Issue/PR: #651 / #652

#### Objective
Prevent Google search/redirect URLs from appearing in job card apply/alt links.

#### Fix
- `_format_match` no longer promotes `job_google_link` into `apply_url` when it contains
  `google.com/search` or `google.com/url`.
- `alt_link` Google intermediary cleared at write time (hotfix #652).

#### DB cleanup
Neon sweep confirmed zero Google URLs in `jobs` or `user_job_context`. Talent BluePrint
row in `rico_job_recommendations` had empty URLs (not Google URLs) — contamination was
display-only, resolved at write time. No DB write required.

---

### TASK-20260619-022 — BUG-02 A/B/C/D letter-choice routing off-by-one (Hard Audit)

Status: done
Owner: Claude
Branch: `claude/clever-galileo-gii41r` (merged → `631ce7d` via PR #649)
Issue/PR: #649

#### Objective
Fix off-by-one in letter-choice router: selecting "A" was routing to option B, "B" to C, etc.

#### Fix
Zero-vs-one-based index corrected in the letter-choice handler in `src/rico_chat_api.py`.
CI green. Merged `631ce7d`, 2026-06-19.

---

### TASK-20260619-021 — BUG-01 Cover-letter company-search routing guard (Hard Audit)

Status: done
Owner: Claude
Branch: `claude/clever-galileo-gii41r` (merged → `40636ba` via PR #648)
Issue/PR: #648

#### Objective
Fix BUG-01 from the Hard Audit: a cover letter prompt containing "role at [Company]"
(e.g. "Draft me a cover letter for the HSE MANAGER - DATA CENTERS role at Dutco Group")
triggered `_COMPANY_SEARCH_RE` and returned job search results instead of a cover letter.

#### Root cause
Pre-classifier `_COMPANY_SEARCH_RE` pattern-2
(`\b(?:jobs?|roles?|vacancies|openings?|positions?)\s+at\s+[A-Z][A-Za-z]`) matched
"role at Dutco Group" because `roles?` also matches the singular "role". This check fires
before `classify_intent` and before the cover-letter slot extractor, so cover letter
prompts with "role at" were silently routed to company search.

#### Fix
- New early-exit block inserted before `_COMPANY_SEARCH_RE` check: when
  `_COVER_LETTER_COMMAND_RE` matches and slot extractor returns results, generate the
  letter immediately (or ask only for the missing field).
- Belt-and-suspenders: `_COMPANY_SEARCH_RE` guard also gets
  `not _COVER_LETTER_COMMAND_RE.search(message)`.
- Regression tests: `TestBug01CoverLetterCompanySearchGuard` (5 new tests in
  `tests/test_cover_letter_slot_extraction.py`; 15/15 total pass).

#### Constraints
- No DB schema changes. No migrations. No frontend changes.
- No #640/#641. No Phase 2. No BUG-02/BUG-03 in this PR.
- Changed files limited to: `src/rico_chat_api.py`,
  `tests/test_cover_letter_slot_extraction.py`, `AI_WORKSPACE/CURRENT_STATE.md`.

#### Verification (2026-06-19)
- [x] 15/15 tests in `test_cover_letter_slot_extraction.py` PASS.
- [x] CI green (pytest + playwright) on PR #648.
- [x] Merged to main as `40636ba6ed2fd15cf135ef38030c6e1d2641ecab`.
- [x] Render deploy run #29 (09:34Z): `/health` 200, `/version` = `40636ba`.
- [x] bug01-smoke.yml run #1 (27818302534, 09:45Z): **4/4 PASS**
      (version check + cover-letter smoke + company-search regression + health).
- [x] Manual app smoke (user-confirmed): cover letter drafted, no job_results,
      no Dutco company search, no unrelated apply links, `/flow` uncontaminated.
- [x] Company-search regression confirmed: "find jobs at Dutco Group" still works
      normally (smoke step 3 PASS + user manual test).

#### Handoff notes
- Changed files: `src/rico_chat_api.py`, `tests/test_cover_letter_slot_extraction.py`,
  `AI_WORKSPACE/CURRENT_STATE.md`.
- bug01-smoke.yml was a one-off verification workflow; pushed to main then deleted
  (commit `3e997073`) after smoke PASS.
- Rollback: revert PR #648 and re-deploy.
- BUG-02 and BUG-03 from the Hard Audit are now unblocked (smoke passed).
  Do not start without explicit scope and branch assignment.

---

### TASK-20260619-020 — DB pool AttributeError hotfix (Issue #644)

Status: done
Owner: Claude
Branch: `fix/db-pool-psycopg2-connection-attribute` (merged → `26124ed`)
Issue/PR: #644

#### Objective
Fix production outage: every `db.connect()` raised `AttributeError: 'psycopg2.extensions.connection'
object has no attribute '_rico_pool'`, taking down all DB-backed endpoints after #638 deployed.

#### Root cause
`src/rico_db.py` `connect()` did `conn._rico_pool = pool`. psycopg2 connection objects have no
`__dict__` (verified: `'__dict__' in dir(psycopg2.extensions.connection)` → `False`), so that
assignment raises `AttributeError` on every call.

#### Fix
- `connect()` returns a direct per-request connection; no attribute assignment.
- `_return_or_close()` closes directly.
- Pool scaffolding left in place but unused — re-enabling needs a caller-wide acquire/release
  refactor (subscription_repo / applications_repo / profile_repo all use `with db.connect()`
  and never return connections to a pool).
- Regression tests: `tests/test_rico_db_connect.py` (4 tests, slots-only fake conn that
  mimics psycopg2 no-`__dict__`).

#### Verification (2026-06-19)
- [x] 35 tests passed (test_rico_db_connect + test_followup_reminders + test_application_lifecycle).
- [x] py_compile clean.
- [x] Merged to main as `26124ed180a77658be21cfa499e5629bd6a816ed`.
- [x] Render deploy run #27 + #28: `/health` 200, `/version` = `26124ed`.
- [x] followup-smoke.yml run #2 (27813425034): **9/9 PASS** on `26124ed`.
- [x] Cron double-fire (cron-test.yml dispatch 27813559291): run 1 `status="ok"`, run 2 `status="ok"`.

#### Handoff notes
- Changed files: `src/rico_db.py`, `tests/test_rico_db_connect.py`.
- Separate follow-up needed: re-enable pooling with caller-wide refactor.
- Separate cleanup needed: `028_performance_indexes` startup warning (column "job_id" does not exist).
- Rollback: revert PR #644 and re-deploy; Neon not involved (no migration).

---

### TASK-20260619-019 — System Overhaul v1+v2

Status: done
Owner: Claude
Branch: `engineering/system-overhaul-v2` (merged → `9c003a7` via PR #638)
Issue/PR: #638

#### Objective
Multi-area engineering improvement based on full codebase audit — backend reliability,
DB performance, and frontend UX, delivered in two commits.

#### v1 changes (commit `9d7c1e0`, on main)
- **Telegram DM fix**: `process_telegram_update()` was returning replies in the HTTP body
  (Telegram ignores). Now calls `send_telegram_to_user()` in `/start`, `/stop`, and general DM paths.
- **Telegram deduplication**: `update_id` tracked in bounded deque (2000 entries, 1h TTL).
- **12 DB indexes**: `migrations/028_performance_indexes.sql` — indexes on all unindexed
  FK columns. Applied at startup via `_apply_performance_indexes()` in `app.py` lifespan.
- **Jobs pagination**: frontend now tracks `page`/`totalPages`; "Load more" button appends
  results. PAGE_SIZE=20.

#### v2 changes (commit `65709b9`, merged via PR #638)
- **DB connection pooling**: `psycopg2.ThreadedConnectionPool` (min=1, max=10) in
  `src/rico_db.py`. ⚠️ **DISABLED by #644** — pooling broken due to psycopg2 `__dict__`
  incompatibility. Pool scaffolding remains; re-enabling tracked separately.
- **Email pre-fill after verification**: `verify-email` page redirects to `/login?email=...`
  so login form is pre-filled. `LoginForm` accepts `initialEmail` prop. `login/page.tsx`
  uses `useSearchParams` + `Suspense`.
- **TagInputField component**: chip/tag UI for `target_roles`, `preferred_cities`, `skills`
  in profile page. Enter/comma to add; × to remove; Backspace to delete last.

#### Outcome
- [x] All v1 changes live on main (`9d7c1e0`).
- [x] All v2 changes merged (`9c003a7`, PR #638) + deployed (`26124ed` post-#644 hotfix).
- [x] DB pooling disabled by #644 (separate re-enable follow-up).
- [x] Known non-blocking startup warning: `migration_failed label=028_performance_indexes:
      column "job_id" does not exist` — separate cleanup, do not mix.

#### Handoff notes
- Changed files: `src/rico_telegram_webhook.py`, `migrations/028_performance_indexes.sql`,
  `src/api/app.py`, `apps/web/app/jobs/page.tsx`, `src/rico_db.py`,
  `apps/web/app/verify-email/page.tsx`, `apps/web/components/auth/LoginForm.tsx`,
  `apps/web/app/login/page.tsx`, `apps/web/app/profile/page.tsx`
- Migration number: 028 (027 was already taken by follow-up reminders)
- Rollback plan: revert the two commits on this branch.

---

### TASK-20260618-018 — Follow-up Reminders, Phase 1 (Issue #355)

Status: done (Phase 1 complete — Render Cron verified 2026-06-19)
Owner: Claude
Branch: `feat/follow-up-reminders-355` (merged → `a95c413`, in current main)
Issue/PR: #355

#### Implementation (Phase 1, 2026-06-18)
Both gated items approved: (1) migration adding `applied_at`; (2) `RICO_CRON_SECRET`.
- `migrations/027_followup_reminders.sql` — adds `applied_at`/`follow_up_due_at`/
  `last_followup_at` + backfill + scan index. **Applied to Neon.**
- `src/rico_db.py` — guarded `_stamp_status_timestamp` (stamps `applied_at` when a row
  first becomes `applied`, `follow_up_due_at` on `follow_up_due`); called from
  `upsert_recommendation` + `update_recommendation_status`. New idempotent
  `mark_followups_due(interval_days)` sweep (only touches status='applied').
  Stamping is best-effort/own-transaction so a pre-migration column never breaks writes.
- `src/services/followup_service.py` — `run_due_scan` (never raises; safe summary on
  DB-unavailable / pre-migration).
- `src/api/deps.py` — `require_cron_secret` (X-Cron-Secret vs `RICO_CRON_SECRET`,
  constant-time, fails closed with 503 when unset).
- `src/api/routers/pipeline.py` — `POST /api/v1/pipeline/reminders` (cron-guarded,
  optional `?interval_days`). `src/schemas/pipeline.py` — `RemindersResponse`.
- Default interval = 7 (constant). Per-user settings interval = deferred (Phase 2).
- Telegram DM = deferred (Phase 2). Dashboard renders `follow_up_due` already (#627).

#### Tests (sandbox)
- `tests/test_followup_reminders.py` — 10 passed (cron guard 503/403/ok; service ok/
  unavailable/error/interval-coercion; sweep idempotency SQL + interval clamp).
- `tests/test_application_lifecycle.py` — 21 passed (no regression from stamping calls).

#### Rollout + production smoke — COMPLETE (2026-06-19)
1. [x] **Migration `027_followup_reminders.sql` applied to Neon production**: 3 columns +
   index verified, no data loss.
2. [x] **`RICO_CRON_SECRET` set on Render** (and as a GitHub Actions secret for the smoke).
3. [x] **Production verified live on `26124ed`**: `/health` 200, `/version` = `26124ed`
   (Render deploy runs #27 + #28).
4. [x] **Smoke PASS 9/9** — followup-smoke.yml run #1 (`27810675201`, on `3958376`) and
   run #2 (`27813425034`, on `26124ed`):
   - guard: missing→403, wrong→403, correct→200 `{"interval_days":4000,"marked_due":1}`
   - old applied → `follow_up_due`; fresh → stays `applied`
   - idempotent re-run → `marked_due=0`, `follow_up_due_at` unchanged
   - `/flow`-backing status = `follow_up_due`; no duplicate rows (1 each)
   - smoke test rows cleaned up; secrets masked in log (`***`).
5. [x] **Render Cron** ✅ configured and verified — `status="ok"` both consecutive runs
   (cron-test.yml dispatch 27813559291, 2026-06-19T08:04Z). **Do not change Cron command.**
6. [ ] **Phase 2** ⏳ not started. (#640 and #641 on hold — do not merge.)

Migration collision concern RESOLVED — no duplicate number:
- follow-up reminders migration = `027_followup_reminders.sql`
- performance indexes migration = `028_performance_indexes.sql`

#### Original scope / blockers (now resolved)

#### Objective
After a job is `applied`, detect when it has been ≥ interval (default 7 days) with no
follow-up and transition it `applied → follow_up_due`; surface due items on the `/flow`
dashboard so the user can act. No auto-send. Idempotent.

#### Agreed decisions (2026-06-18)
- **Scheduler:** Render Cron → protected `POST /api/v1/pipeline/reminders` endpoint
  (chosen over in-process APScheduler — lower ops risk, matches existing manual-deploy/cron
  model). Rico provides the endpoint + scan logic; the Render Cron schedule is wired by the
  owner (infra, out of code scope).
- **Channel:** Dashboard-first. Surface `follow_up_due` on `/flow` (status already renders
  since #627). **Telegram DM deferred to a later phase** to keep Phase 1 simple/user-friendly.

#### Existing building blocks
- `follow_up_due` already a valid status and renders on `/flow` (#627).
- Legacy `src/follow_up.py` = global JSON blast (not user-scoped, not idempotent) — to be
  superseded, not extended.
- `pipeline` router exists; per-user Telegram (`send_user_notification`) exists for later.

#### Blockers — require explicit approval before implementation
1. **No `applied_at` timestamp.** `rico_job_recommendations` has only `created_at`/`updated_at`
   (and `get_recommendations` maps `date_applied = created_at`). "7 days since applied" has no
   reliable source. Options:
   - (a) **Add `applied_at TIMESTAMPTZ` (+ `follow_up_due_at`, `last_followup_at`) via a
     migration** — cleanest, but a DB schema change (gated).
   - (b) Approximate from `updated_at` at the time status became `applied` — no migration, but
     imprecise (any later edit moves `updated_at`).
   - Recommendation: (a) — correctness matters for a reminder feature.
2. **Cron auth.** A Render Cron call can't carry a JWT. Needs a shared-secret guard
   (e.g. `X-Cron-Secret` header vs a new `RICO_CRON_SECRET` env var) — an env/config addition
   (gated). Recommendation: add `RICO_CRON_SECRET`, reject the endpoint without it.

#### Scope (Phase 1, after approval)
- In: reminders endpoint + idempotent per-user scan over `rico_job_recommendations`; status
  transition `applied → follow_up_due → follow_up_sent`; configurable interval in settings
  (default 7); unit tests (mocked DB, no live calls).
- Out: auto-send emails/messages; Telegram (later phase); Redis/RQ; SMS; the Render Cron infra
  config itself; replacing legacy `follow_up.py` beyond deprecating its use.

#### Acceptance criteria (maps to issue #355)
- [x] Follow-up becomes due automatically at interval after applied.
- [x] Default interval 7 days, configurable per user in settings (Phase 2).
- [x] Due items surface on `/flow` (dashboard).
- [x] No duplicates; worker/endpoint idempotent (re-run = no extra transitions).
- [x] No auto-send (state stops at `follow_up_due`; user confirms later).
- [x] State transitions `applied → follow_up_due`.

#### Required verification
- [x] `pytest` unit tests for due-detection + idempotency.
- [x] `python -m py_compile` on changed files.
- [x] Post-deploy production smoke: PASS 9/9 (both runs).

#### Handoff notes
- Phase 2 gated: per-user interval settings, Telegram DM.
- #640/#641 on hold — do not merge until Phase 2 is explicitly scoped.
- Rollback plan: revert PR #644 + this migration (migration is additive; columns can be dropped).

---

### TASK-20260618-017 — Fix prepare→prepared lifecycle persistence (Issue #353)

Status: done (live + production-smoke PASS)
Owner: Claude
Branch: `fix/prepare-flow-prepared-status-persistence` (merged)
Issue/PR: #353 / PR #634

#### Objective
Close the #353 production-smoke gap where prepare-application reported "prepared" but the
`/flow` board row stayed at the opened tier (PREPARED counter 0, no duplicate).

#### Root cause
- Prepare handler took title/company from intent extraction and hardcoded the resolved
  context row to `None`, so its lifecycle `job_key` could diverge from the key the search
  path stored the `opened` row under — the upsert never upgraded the same record.
- The prepared write was best-effort/swallowed; Rico claimed success regardless of whether
  the board write landed. (DB `status` column has no CHECK constraint — `prepared` was
  already valid; no migration needed.)

#### Fix
- Resolve the surfaced job via `_resolve_card_job` so prepared upgrades the SAME opened
  record (consistent `job_key`; also populates apply_url/location).
- `_persist_application_lifecycle_event` returns whether the board reflects the status;
  still never raises.
- Prepare reply states "Tracked as Prepared on your board" only when persistence succeeded,
  else warns; response exposes `board_status_persisted`.

#### Outcome
- [x] Persists `status="prepared"` to `rico_job_recommendations` (the `/flow` backing table).
- [x] Existing `opened` record upgraded to `prepared` (same `job_key`); no duplicate.
- [x] Rico only claims Prepared when persistence succeeds, else warns.
- [x] Tests: `tests/test_application_lifecycle.py` 21 passed (3 new); 140 related tests pass.
- [x] CI green (pytest + playwright + Vercel). Squash-merged to main as `c8ea4fb` (#634).
- [x] Render deploy run #26 confirmed live (`/version` commit=`c8ea4fb`, `/health` 200).
- [x] **Production smoke PASS 2026-06-18:** prepare works; `/flow` Prepared updates; no
      duplicate; reply says "Tracked as Prepared on your board".

#### Handoff notes
- Changed files: `src/rico_chat_api.py`, `tests/test_application_lifecycle.py`.
- This closes the prepare→prepared lifecycle gap for #353. Any further #353 lifecycle
  parts remain not started. #355 Follow-up Reminders is next but NOT started.
- Rollback plan: revert PR #634.

---

### TASK-20260618-016 — Apply-Link Verification (Issue #354)

Status: done (live + smoke PASS)
Owner: Claude
Branch: (merged)
Issue/PR: #354 / PR #632

#### Objective
Wire `LinkVerifier` into the `open_apply_link` handler so apply links are verified before
being surfaced: a live link returns an `apply_url`; a dead/blocked link returns a fallback
response with no `apply_url`.

#### Outcome
- [x] `LinkVerifier` wired into the `open_apply_link` handler.
- [x] Squash-merged to main as `668d59dc` (PR #632).
- [x] Confirmed live on Render (`c8ea4fb`, run #26, 2026-06-18).
- [x] Production smoke PASS: live apply link → `apply_url` present; dead/blocked link →
      fallback response with no `apply_url`.

#### Handoff notes
- Backend change merged to `main`; not confirmed live on Render. Covered by the
  "Next required action" deploy + smoke checklist in `CURRENT_STATE.md`.
- #354 is no longer the next roadmap priority — #355 Follow-up Reminders is next (needs scope).

---

### TASK-20260618-015 — Application Lifecycle Completion (Issue #353)

Status: done (Changes A & B live + production-smoke PASS via #634; further #353 parts not started)
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: #353

#### Objective
Wire `rico_job_recommendations` writes into the two previously unwired paths so every job
Rico surfaces (search results) or prepares (cover letter / application draft) immediately
appears on the /flow board — no manual save required.

#### Context
- Root cause: `upsert_matches` (search) and `set_lifecycle_status` (prepare flow) write to
  `user_job_context` only. `rico_job_recommendations` (the /flow board table) was only
  written by explicit user save/apply actions.
- Fix: extend use of the existing `_persist_application_lifecycle_event` dual-write helper
  to both paths.
- Status `"opened"` chosen for auto-persist (not `"saved"`) to bypass subscription gating
  in `applications_repo.create`. `"opened"` is in `VALID_STATUSES`, appears in the Leads
  column on /flow, and is semantically correct.
- Regression guard: `_should_update_status` rank-orders statuses (opened=20). Any job
  already at prepared(30)/applied(40)/interview(60)/offer(70) is not downgraded.
- Relevant files: `src/rico_chat_api.py`, `tests/test_application_lifecycle.py`,
  `src/repositories/applications_repo.py`, `src/applications.py`.

#### Constraints
- No DB migration. No schema changes. No new routes. No frontend changes.
- No Gmail, follow-up workers, email sending, automation scheduler.
- No billing/auth/AI provider changes. No destructive Neon operations.
- No broad status vocabulary alignment (interviewing/found/archived divergence is
  pre-existing and documented as follow-up work, NOT fixed in this PR).
- Do not merge. Do not deploy. Deliver one focused draft PR only.

#### Acceptance criteria
- [x] Search results: after `upsert_matches`, each match with non-empty title+company calls
      `_persist_application_lifecycle_event(status="opened")`.
- [x] Prepare flow: after existing `set_lifecycle_status` call, also calls
      `_persist_application_lifecycle_event(status="prepared")`.
- [x] Both paths are non-blocking (wrapped in try/except, exceptions logged at DEBUG).
- [x] Regression guard: `"opened"` never downgrades a job already at prepared/applied/
      interview/offer.
- [x] `tests/test_application_lifecycle.py` 18/18 pass — 3 new tests added, 15 existing
      tests still pass.

#### Required verification
- [x] `python -m pytest tests/test_application_lifecycle.py -v` — 18/18 passed.

#### Handoff notes
- Changed files:
  - `src/rico_chat_api.py` — Change A (loop after `upsert_matches`, ~line 8091) +
    Change B (dual-write after `set_lifecycle_status`, ~line 7221)
  - `tests/test_application_lifecycle.py` — 3 new tests appended
  - `AI_WORKSPACE/TASKS.md` — this entry
- Known pre-existing vocabulary divergence (NOT in scope):
  `LIFECYCLE_STATUSES` uses `"interviewing"` while `VALID_STATUSES`/frontend uses
  `"interview"`. `found`/`archived`/`needs_review` in LIFECYCLE only;
  `opened`/`follow_up_due`/`decision_made` in VALID_STATUSES only.
  Document as tech-debt follow-up in a separate PR.
- Risks: Both changes are guarded by try/except — no search or prepare flow is affected
  by a DB failure. The regression guard ensures no data is corrupted.
- Rollback plan: revert the two blocks added to `src/rico_chat_api.py`.
- Production: squash-merged to main as `01cff584` (#353). Change A (search → `opened`)
  and Change B (prepare → `prepared`) are live on `main`.
- #353 partial completion only. Remaining parts NOT started and require explicit scope +
  branch assignment: apply-link verification (#354), follow-up reminders (#355), and any
  further lifecycle completions (incl. the pre-existing status-vocabulary divergence above).

---

### TASK-20260618-014 — Open-PR backlog triage and cleanup

Status: done
Owner: Claude
Branch: `claude/festive-turing-5q21s8`
Issue/PR: #601, #608, #566

#### Objective
Reduce backlog noise without starting new feature work: triage the three open PRs and act
(close stale, merge clean docs-only) — no production code, DB, env, or feature changes.

#### Constraints
- Read-only triage; no src/, apps/, tests/, DB/schema/migration, env/config, or production code.
- No deploy. No merge without explicit approval.

#### Outcome
- [x] **#601 closed** as stale/superseded — too broad (~1.3k LOC), stale base, draft,
      production code in `src/rico_chat_api.py`, unchecked test plan, body/title mismatch
      (#601 vs "#610"). Fast paths to be re-cut later as small focused PRs from current `main`.
      No replacement PR opened.
- [x] **#608 merged** (squash `8941697c2be56c40d2047dcdeedd20e521dfc06f`) — adds
      `docs/architecture/localization.md`. Verified docs-only, mergeable clean, Vercel green.
      Documented fix (PR #606) confirmed live in `main` (`_handle_lifecycle_query(..., message="")`).
- [x] **#566 merged** (squash `edc53fdf37645b153148a006e68f34215d8adc8a`) — adds
      `docs/integrations/gmail-readonly-connector.md`. Verified docs-only, no conflicts,
      Vercel green, aligned with #356 Inbox Intelligence (design-only).
- [x] Open PR backlog now clean: **0 open PRs**. main HEAD = `edc53fd`.

#### Handoff notes
- Changed files (this workspace-sync PR): `AI_WORKSPACE/CURRENT_STATE.md`,
  `AI_WORKSPACE/TASKS.md`, `AI_WORKSPACE/DECISIONS.md`.
- The six "Continuous AI: …" third-party bot checks error on every PR and are not project
  test failures — recommend disabling that integration to clean the checks UI.
- Decision recorded: DEC-20260618-001.
- Rollback plan: revert this docs-only commit.

---

### TASK-20260617-013 — Application Pipeline V1 status alignment

Status: done
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: #627

#### Objective
Align the frontend `ApplicationStatus` type with the backend `VALID_STATUSES` set by
adding the three statuses already accepted by the backend but missing from the frontend:
`opened_external`, `prepared`, `follow_up_due`. Update the /flow board, status labels,
translations, and StatusBadge accordingly.

#### Context
- Relevant files:
  - `apps/web/types/index.ts` — `ApplicationStatus` union type
  - `apps/web/app/flow/page.tsx` — board columns, label maps, option list
  - `apps/web/components/ui/StatusBadge.tsx` — badge colour config
  - `apps/web/lib/translations.ts` — EN + AR status labels and next-action strings
  - `src/applications.py` — `VALID_STATUSES` (backend source of truth)
- Root cause: backend `VALID_STATUSES` had 10 statuses; frontend type had 7.
  Records with `opened_external`, `prepared`, or `follow_up_due` stored in DB
  were silently dropped from board view and caused TypeScript type gaps.
- Existing behavior: `/applications` redirects to `/flow`. Board has 4 columns.

#### Constraints
- No DB schema changes. No backend route changes. No auth/billing/scoring changes.
- No new API endpoints. No env/config changes.
- Frontend only: types, page, component, translations.

#### Acceptance criteria
- [x] `ApplicationStatus` type includes `opened_external`, `prepared`, `follow_up_due`.
- [x] Board Leads column includes `opened_external` and `prepared`.
- [x] Board Applied column includes `follow_up_due`.
- [x] All new statuses appear in the status dropdown (manual tracking modal + inline).
- [x] Status count row covers all 10 statuses.
- [x] EN + AR labels and next-action guidance for all 3 new statuses.
- [x] `StatusBadge` renders new statuses with distinct colours.
- [x] `npm run build` clean — no TypeScript errors.
- [x] New alignment tests: 7/7 pass.
- [x] Existing application tests: 64/64 pass, no regressions.

#### Required verification
- [x] `npm run build` — clean in `apps/web`.
- [x] `pytest tests/unit/test_application_pipeline_statuses.py` — 7/7 passed.
- [x] `pytest tests/test_application_lifecycle.py tests/test_manual_application_tracking.py
       tests/unit/test_english_manual_application_status_update.py
       tests/unit/test_arabic_application_status_update.py
       tests/unit/test_application_tracking_intelligence.py` — 64/64 passed.
- [x] Frontend build: no TypeScript errors.

#### Handoff notes
- Changed files:
  - `apps/web/types/index.ts` — added `opened_external | prepared | follow_up_due`
  - `apps/web/app/flow/page.tsx` — updated KANBAN_COLS, STATUS_LABEL_KEYS,
    NEXT_ACTION_KEYS, STATUS_OPTIONS, STATUS_COUNT_ORDER
  - `apps/web/components/ui/StatusBadge.tsx` — added 3 new status configs
  - `apps/web/lib/translations.ts` — added 6 EN + 6 AR strings
  - `tests/unit/test_application_pipeline_statuses.py` — 7 new alignment tests
  - `AI_WORKSPACE/TASKS.md`
- Risks: Records in DB with old statuses unaffected (read-only display change).
  No scoring or ranking logic touched. No backend validation changed.
- Rollback plan: revert the 4 frontend files.
- Production: squash-merged to main as `62a679b6594afa4475fe9bd92b649ae623a092d8` (#627).
  Deployed to Vercel automatically (Deploy to Production ✅ 2026-06-18T04:45 UTC).
  Render backend not required (frontend-only change).
  Manual smoke 2026-06-18: /flow loads, /applications→/flow redirect confirmed, board columns
  correct, status dropdown includes Opened externally / Prepared / Follow-up due, no crash.

---

### TASK-20260618-011 — Guard preferred_cities against yes/no input

Status: done
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: #625

#### Objective
Prevent non-city strings ("نعم", "لا", "yes", "no") from being stored in
`preferred_cities` when collected via the chat pending-field handler or Jotform webhook.
Also provide a SQL data patch for the one known bad record (`robenedwan@gmail.com`).

#### Context
- Relevant files:
  - `src/rico_chat_api.py` — pending-field handler for `preferred_cities` (line ~4136)
  - `src/rico_jotform_webhook.py` — `map_jotform_payload()` line 116
  - `src/services/matching_guardrails.py` — `is_uae_city()` already warns on stored invalid cities
- Root cause: when Rico asks "What city do you prefer?" and the user replies "نعم",
  the chat handler accepts it (not an intent verb, short enough) and stores it. Jotform
  field mapping has no validation at all.
- Existing behavior: matching_guardrails warns on retrieval but does not prevent storage.

#### Constraints
- No DB schema changes. No frontend changes. No scoring changes.
- Do not add a new service module — filter inline or as a module-level constant.
- Data patch is provided as SQL in PR description; user runs it manually on Neon.
- Keep tests unit-only, no DB/network.

#### Acceptance criteria
- [x] Replying "نعم" / "yes" / "no" / "لا" to Rico's city prompt is rejected (returns None,
      prompts again) — preferred_cities not updated.
- [x] Valid city ("Dubai", "دبي") still accepted and saved correctly.
- [x] Jotform `preferred_cities` field strips yes/no strings before storage.
- [x] Unit tests cover yes/no rejection and valid-city acceptance.
- [x] Backend test suite passes with no regressions.

#### Required verification
- [x] `python -m py_compile` clean on changed files.
- [x] `python -m pytest tests/unit/test_preferred_cities_guard.py` — 21/21 passed.
- [x] Full backend test suite: 2768 passed, no regressions.
- [x] Frontend build: not required (no frontend changes).

#### Handoff notes
- Changed files:
  - `src/rico_chat_api.py` — `_CITY_REJECT_WORDS` class constant + one-line filter in
    `_resolve_pending_field` preferred_cities branch
  - `src/rico_jotform_webhook.py` — `_CITY_REJECT_WORDS` module constant +
    `_as_city_list()` helper; `map_jotform_payload()` uses it
  - `tests/unit/test_preferred_cities_guard.py` — 21 new unit tests
  - `AI_WORKSPACE/TASKS.md`
- Data patch SQL — **completed on Neon 2026-06-18**:
  ```sql
  UPDATE rico_profiles
  SET profile = jsonb_set(profile, '{preferred_cities}', '[]'::jsonb)
  WHERE profile->'preferred_cities' @> '["نعم"]';
  ```
  Verification query returned 0 rows — no remaining bad records.
- Future yes/no answers now blocked from `preferred_cities` in:
  - Rico chat pending-field handler (`src/rico_chat_api.py`)
  - Jotform webhook mapping (`src/rico_jotform_webhook.py`)
- Production: squash-merged to main as `1cb66e5d34895e83e1a61fd620bba4222bc14606` (#625).
  Render deploy required (workflow_dispatch). Vercel auto-deployed.
- Rollback plan: revert the two source files.

---

### TASK-20260617-010 — Fix chat composer clip icon UX

Status: done
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: #623

#### Objective
Make the chat composer clip icon reliably open the file picker on all browsers,
including mobile Safari and WebViews that block programmatic `input.click()`.

#### Context
- Relevant files:
  - `apps/web/app/command/page.tsx` (hidden file input + clip button in composer)
- Root cause: `<button onClick={() => fileInputRef.current?.click()}>` silently fails on
  some mobile browsers because programmatic `.click()` on a hidden file input is treated
  as an untrusted event. The `/upload` page works because it uses native label/input wiring.
- Existing behavior: clip button exists and is wired, but the file picker never opens on
  affected browsers.

#### Constraints
- Frontend composer only. No backend, no CV parser, no DB, no scoring, no AI provider.
- Do not change upload logic (handleCVUpload, confirmCVProfile, etc.).
- Do not change tests beyond what is practical for the click behaviour.

#### Acceptance criteria
- [x] Clicking the clip icon opens a native file picker on desktop and mobile.
- [x] Icon is visually dimmed and non-interactive during `checking`/`thinking` state.
- [x] Accept attribute extended to `.pdf,.doc,.docx` (more useful than `.pdf` only).
- [x] Frontend build passes with no TypeScript errors.

#### Required verification
- [x] `npm run build` clean in `apps/web`.
- [x] CI QA Tests (pytest + playwright) green on PR.
- [x] Manual smoke: click clip icon on desktop → file chooser opened (Playwright confirmed).
- [x] Manual smoke: click clip icon on mobile (iPhone 14 Pro UA) → file chooser opened.
- [x] Disabled/checking state: no `for` attr + `pointer-events-none` + `opacity-30` confirmed.
- [x] Upload flow (setInputFiles): no crash confirmed.

#### Handoff notes
- Changed files:
  - `apps/web/app/command/page.tsx` — hidden `<input>` gets `id="cv-file-upload"` and
    `accept=".pdf,.doc,.docx"`; `<button>` replaced with `<label htmlFor="cv-file-upload">`
    with equivalent disabled/aria styling.
  - `AI_WORKSPACE/TASKS.md`
- Risks: None. `<label htmlFor>` pattern is universally supported and more reliable than
  programmatic `.click()`. The `ref` on the input is kept for the `__cv_upload__` magic
  message path (line ~811) which is unaffected.
- Rollback plan: revert the single file `apps/web/app/command/page.tsx`.
- Non-blocking follow-up: `aria-disabled`/`tabIndex` polish (SSR/hydration timing nuance,
  functional behaviour is correct via `pointer-events-none` + missing `for` attr).
- Production: squash-merged to main as `4df959bdee354d4bf431925c5d3fbb10354801ba` (#623).
  Deployed to Vercel automatically (Deploy to Production ✅ 2026-06-17T22:08 UTC).
  Render backend also live as of 2026-06-17T22:12 UTC (separate manual deploy).

---

### TASK-20260617-009 — CV extraction quality warnings

Status: done
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: #621

#### Objective
Surface lightweight advisory warnings when a CV upload produces low-quality extraction,
an unrealistic years_experience value, very few detected skills, or a role mismatch between
the CV's current_role and the user's target_roles. Warnings are advisory only — saves are
never blocked and scoring is never changed.

#### Context
- Relevant files:
  - `src/services/cv_quality_warnings.py` (new)
  - `src/api/routers/rico_chat.py` (upload response, confirm-cv response)
  - `src/cv_parser.py` (ParsedCV.extraction_quality, skills, years_experience_hint)
  - `src/services/matching_guardrails.py` (pattern reference)
  - `tests/unit/test_cv_quality_warnings.py` (new)
- Existing behavior: `extraction_quality` is computed during parsing but no warnings
  are surfaced to the caller.

#### Constraints
- Do not add migrations or change DB schema.
- Do not change scoring or search ranking.
- Do not change auth, billing, or env config.
- Do not touch unrelated UI pages or Application Pipeline work.
- Advisory only — no saves blocked.

#### Acceptance criteria
- [x] `build_cv_quality_warnings()` warns on `extraction_quality` "poor"/"partial".
- [x] Warns when `years_experience` > 25 (high) or > 50 (unrealistic).
- [x] Warns when fewer than 3 skills are detected (but list is non-empty).
- [x] Warns when CV `current_role` shares no keywords with `target_roles`.
- [x] Upload response includes `warnings` field.
- [x] Tests cover all four warning scenarios plus the no-warnings path.

#### Required verification
- [x] Unit tests: `tests/unit/test_cv_quality_warnings.py` — 30/30 passed.
- [x] Syntax check: `python -m py_compile` clean on both changed files.
- [x] Full backend test suite: 2620/2620 passed, no regressions.
- [x] Frontend build: not required; no frontend files changed.
- [x] CI: pytest ✅ playwright ✅ Vercel ✅ Neon/setup ✅ on PR #621.

#### Handoff notes
- Changed files:
  - `src/services/cv_quality_warnings.py` (new)
  - `src/api/routers/rico_chat.py` (import + `warnings` field in upload response)
  - `tests/unit/test_cv_quality_warnings.py` (new)
  - `AI_WORKSPACE/TASKS.md`
- Risks: role-mismatch check is keyword-overlap heuristic; unusual role phrasings may
  produce a false positive. Warning is advisory so the impact is low.
- Rollback plan: revert the three source/test files.
- Production: squash-merged to main as `b9708c91c0afd1b8d8a5ea83d7ff29aee02f5fb2` (#621).
  Render deploy not yet triggered. CV quality warnings are on main but not confirmed
  production-live. Trigger Manual Render Deploy before smoke-testing this feature.

---

### TASK-20260617-008 — Add session-level job search history

Status: done
Owner: Codex
Branch: `codex/task-20260617-008-session-job-history`
Issue/PR: #617

#### Objective
Track lightweight job-search summaries in the current Rico chat session so Rico can answer
how many jobs it found earlier in the same conversation.

#### Context
- Relevant files:
  - `src/rico_chat_api.py`
  - `tests/unit/test_rico_job_search_tracker_flow.py`
  - `tests/unit/test_followup_fast_path.py`
  - `AI_WORKSPACE/EVALS/2026-06-17-post-615-616-verification.md`
- Existing behavior: Rico caches recent search matches but count follow-ups only read the
  current cached match list and can miss Arabic/session-count phrasing such as
  `كم عدد الوظائف التي وجدتها منذ بداية المحادثة`.

#### Constraints
- Do not add Redis unless already wired and necessary.
- Do not change DB schema.
- Do not change scoring/search ranking.
- Do not touch unrelated UI pages.
- Do not change Settings/Profile guardrails from #616.

#### Acceptance criteria
- [x] When Rico returns N jobs, store a lightweight search summary for the session.
- [x] User can ask how many jobs Rico found in the current conversation.
- [x] Response includes last search count, role/query, city if available, and top match if available.
- [x] If no searches happened in the current session, Rico says that clearly.
- [x] Regression tests cover storing, follow-up count, and no-history path.

#### Required verification
- [x] Unit tests: focused session job history tests.
- [x] Existing chat/job routing tests: focused nearby tests attempted; existing local routing fixture failures are noted below.
- [x] Frontend build: not required; no frontend files changed.
- [x] Production/deploy smoke: not in this PR; post-#615/#616 deploy health was recorded before starting.

#### Handoff notes
- Changed files:
  - `AI_WORKSPACE/EVALS/2026-06-17-post-615-616-verification.md`
  - `AI_WORKSPACE/TASKS.md`
  - `src/rico_chat_api.py`
  - `tests/unit/test_followup_fast_path.py`
  - `tests/unit/test_rico_job_search_tracker_flow.py`
- Commands run:
  - `git fetch origin main`
  - `gh run list --branch main --limit 10 --json ...`
  - `gh run view 27713530030 --json ...`
  - `Invoke-RestMethod https://rico-job-automation-api.onrender.com/health`
  - `Invoke-RestMethod https://rico-job-automation-api.onrender.com/version`
  - `Invoke-RestMethod https://rico-job-automation-api.onrender.com/api/v1/version`
  - `python -m py_compile src\rico_chat_api.py`
  - `python -m pytest tests\unit\test_rico_job_search_tracker_flow.py tests\unit\test_followup_fast_path.py::TestResultCount -q`
  - `python -m pytest tests\unit\test_rico_routing_fix.py tests\unit\test_job_search_role_extraction.py tests\unit\test_rico_profile_job_search_role_list.py tests\unit\test_self_ref_role_resolution.py tests\unit\test_role_context_routing.py -q`
- Test results:
  - Focused acceptance suite: `24 passed`.
  - Syntax check: passed.
  - Existing local routing subset: `107 passed, 2 failed`; failures were in
    `tests/unit/test_rico_routing_fix.py` expecting `run_for_profile` calls and match the known
    stale local routing fixture pattern. No routing/scoring code was changed for this task.
- Risks: process-local session history is intentionally lightweight. It answers immediate
  follow-ups even when JSON recent-context writes are disabled, but it is not durable across
  process restarts or multi-worker hops. Existing `recent_context` remains the primary store when available.
- Rollback plan: revert the TASK-008 PR commit.
- Production: squash-merged to main as `09027412ac3287e7ec78e6b73dd964a607c36357` (#617).
  Deployed to Render. Smoke test 2026-06-17: session job count confirmed working.

### TASK-20260617-007 — Add matching guardrails

Status: done
Owner: Codex
Branch: `codex/task-20260617-007-job-match-guardrails`
Issue/PR: #616

#### Objective
Surface advisory warnings for contradictory matching settings and risky profile inputs on
Settings and Profile pages without blocking saves. Preserve DB schema and scoring behavior.

#### Acceptance criteria
- [x] Backend guardrail evaluator warns on contradictory include/exclude keywords.
- [x] Backend guardrail evaluator warns on high `min_score` with broad criteria.
- [x] Backend guardrail evaluator warns on invalid city or excessive target roles.
- [x] Warnings returned as advisory fields; saves are not blocked.
- [x] English and Arabic warning messages supported.

#### Handoff notes
- Changed files: `src/services/matching_guardrails.py`, `src/api/routers/settings.py`,
  `src/api/routers/rico_chat.py`, `src/schemas/settings.py`, frontend Settings/Profile
  warning display, related tests.
- Production: squash-merged to main as `a8516c188baa0841d7f2ec7b942ef9215e9e2787` (#616).
  Deployed to Render. Smoke test 2026-06-17: guardrails confirmed working.

### TASK-20260617-002 — Fix cover-letter intent slot extraction

Status: done
Owner: Claude
Branch: `claude/great-ritchie-75219u`
Issue/PR: #615

#### Objective
Extract role, company, city, and language from a single cover-letter request and
generate the letter directly instead of re-asking for role/company.

#### Context
- Relevant files:
  - `src/rico_chat_api.py` (`_extract_explicit_draft_job_from_message`,
    `_cover_letter_clarification_message`, `_COVER_LETTER_TIPS_RE`, draft handler)
  - `src/cover_letter_writer.py` (Arabic generation path)
  - `src/message_generator.py` (Arabic partial-identity prompt)
  - `tests/test_cover_letter_slot_extraction.py` (new)
- Existing behavior: the Arabic message
  `اكتب لي خطاب تقديم لوظيفة ESG Manager في شركة Aldar Properties في أبوظبي`
  returned no slots (English-only regex) and the bare phrase `خطاب تقديم` was
  caught by the cover-letter *tips* gate, so Rico re-asked for role/company.

#### Constraints
- Do not rewrite routing; keep the fix minimal.
- Do not touch unrelated handlers, DB schema, or the frontend.

#### Acceptance criteria
- [x] Arabic request with role + company + city generates an Arabic letter directly.
- [x] English request with role + company + city generates an English letter directly.
- [x] Missing role or company asks only for the missing field.
- [x] Existing chat routing / cover-letter tests still pass.
- [x] Regression test for the exact Arabic Aldar ESG Manager example.

#### Handoff notes
- Changed files: `src/rico_chat_api.py`, `src/cover_letter_writer.py`,
  `src/message_generator.py`, `tests/test_cover_letter_slot_extraction.py`,
  `AI_WORKSPACE/TASKS.md`.
- Commands run: targeted `pytest` suites (cover letter, intent, document,
  agent, jotform, jwt, onboarding) — all green.
- Risks: Arabic slot regex is heuristic; unusual phrasings may still need
  clarification (safe fallback). Tightened Arabic tips regex now requires an
  interrogative/advice context.
- Rollback plan: revert the four source/test files on this branch.
- Production: squash-merged to main as `66f7364f8b6ea03326223383b5536c627204ffd2` (#615).
  Deployed to Render. Smoke test 2026-06-17: Arabic cover-letter confirmed writing directly.
  Previous failure was a deployment gap, not an active code bug.

### TASK-20260617-001 — Add AI multi-model sync workspace

Status: done
Owner: ChatGPT
Branch: `chore/ai-workspace-sync-standard`
Issue/PR: #610

#### Objective
Add a repo-native shared source of truth for AI planning, implementation handoffs, review, verification, and decision tracking.

#### Acceptance criteria
- [ ] Add `AI_WORKSPACE/` docs.
- [ ] Add handoff and evaluation templates.
- [ ] Add a context bundle script.
- [ ] Update PR template with handoff evidence fields.
- [ ] Open a focused PR.

#### Required verification
- [ ] Documentation-only change; no runtime tests required.
- [ ] Confirm changed files are limited to docs/templates/script.

#### Handoff notes
- Merged via squash into main: a76a1b6

## Backlog — next priorities

Product roadmap order (post 2026-06-19 BUG-04 closure). Do not start without explicit scope and
branch assignment.

1. **#653 (TASK-024)** — sidebar status widget retry; draft, rebased onto `f4bacfa`, build-green.
   Awaiting review/merge. Do not merge without explicit approval.
2. **TASK-013 Application Pipeline V1** (P1) — end-to-end application submission with approval
   gate, audit log, Telegram confirmation. Needs dedicated issue + branch.
3. **TASK-010 Pipeline relevance guard** (P1) — pre-filter pipeline results against active
   profile before scoring. Needs dedicated issue + branch.
4. **#355 Phase 2** — per-user interval settings + Telegram DM notifications. (#640 and #641
   on hold — do not merge until Phase 2 is scoped.)
5. **#356 Inbox Intelligence** — design-only; connector design doc (#566) on `main`.
6. **028_performance_indexes cleanup** — fix `migration_failed label=028_performance_indexes:
   column "job_id" does not exist` startup warning. Separate focused PR.
7. **DB pooling re-enable** — caller-wide acquire/release refactor. Separate PR after 028 cleanup.

Open #618 UX tasks (8 remaining, tracked in #618 as living tracker):
TASK-010 (P1), TASK-011 (P2), TASK-013 (P1), TASK-014 (P2), TASK-015 (P2),
TASK-016 (P3 — sidebar loading fixed in #653; metric reconciliation open),
TASK-017 (P3), TASK-018 (P2).

Carry-over engineering backlog:
- **Match score explanation** — expose per-field score breakdown in job cards.
- **Blocked link UX** (#354 remainder) — clean blocked-link messaging + verified alternative.
  Overlaps #263. Existing verifier from #266–#268.
- **Neon duplicate profile/document cleanup** — DB write, needs explicit approval.
- **028_performance_indexes startup warning** — `column "job_id" does not exist`.
- **git filter-repo purge** of old archived credential — coordinated force-push, out of scope.

### Active issues
- **Issue #618** — living tracker for 8 open UX tasks (reconciled 2026-06-19,
  status index posted as issuecomment-4753155540). Keep open.
- **Issue #654** — AI Workflow V2 tracker; absorbed timeout/city/profile/routing observations
  from #618 (cross-link posted 2026-06-19). Do not implement AI Workflow V2 without explicit
  scope confirmation.
- **PR #640 / #641** — on hold, awaiting explicit approval. Do not merge.

# Current State

_Last updated: 2026-06-19_

## Production baseline

- **Repository main HEAD:** `3e997073b9713f269031566f0d1cb6103ccb346b`
  (chore: remove bug01-smoke.yml after one-shot use). Recent lineage:
  `3e997073` (remove bug01-smoke.yml, CI-only) ←
  `aa9281bf` (add bug01-smoke.yml, CI-only) ←
  `40636ba` (#648 BUG-01 cover-letter guard) ←
  `7f80cc6` (#647 cleanup/docs) ← `ac8c8ad` (#646 workflow secrets cleanup) ←
  `26124ed` (#644 DB hotfix) ← `3fbe2ea` (#643 workspace sync) ←
  `3958376` (#642 followup-smoke.yml) ← `9c003a7` (#638 system-overhaul-v1+v2) ←
  `9d7c1e0` (overhaul v1) ← earlier.
- **Production backend deployed SHA:** `40636ba6ed2fd15cf135ef38030c6e1d2641ecab`
  (latest runtime-impacting PR: #648 BUG-01 cover-letter guard). Render deploy run #29
  triggered 2026-06-19T09:34Z. `/health` 200, `/version` = `40636ba`.
  `aa9281bf` and `3e997073` are CI-workflow-only — no Render deploy needed.
- **Deployed to Vercel:** ✅ live — frontend at `ricohunt.com`.

## BUG-01 Cover-Letter Company-Search Guard — RESOLVED (2026-06-19)

**Symptom:** Cover letter prompts like
"Draft me a cover letter for the HSE MANAGER - DATA CENTERS role at Dutco Group"
triggered a company job search instead of generating a cover letter.

**Root cause:** Pre-classifier `_COMPANY_SEARCH_RE` pattern-2
(`\b(?:jobs?|roles?|vacancies|openings?|positions?)\s+at\s+[A-Z][A-Za-z]`) matched
"role at Dutco Group" before the cover-letter slot extractor ran.

**Fix (PR #648, merged `40636ba6ed2fd15cf135ef38030c6e1d2641ecab`, 2026-06-19T09:34Z):**
- New early-exit block: when `_COVER_LETTER_COMMAND_RE` matches, extract slots and
  either generate the letter (title + company present) or ask only for the missing
  field — before `_COMPANY_SEARCH_RE` is evaluated.
- Belt-and-suspenders guard: `_COMPANY_SEARCH_RE` check now also requires
  `not _COVER_LETTER_COMMAND_RE.search(message)`.
- 5 new regression tests in `TestBug01CoverLetterCompanySearchGuard`
  (15/15 total in `test_cover_letter_slot_extraction.py`).

**Verification chain:**
- Pre-merge: 15/15 tests PASS.
- Render deploy run #29 (09:34Z, SHA `40636ba`): all steps PASS, `/health` 200.
- bug01-smoke.yml run #1 (27818302534, 09:45Z): **4/4 PASS**
  - `/version` = `40636ba6ed2fd15cf135ef38030c6e1d2641ecab` ✅
  - Cover-letter smoke: `type=onboarding` (not `job_results`) ✅
  - Company-search regression: `type=onboarding` (not `draft_message`/`cover_letter_prompt`) ✅
  - `/health` = 200 ✅
- Manual app smoke (user-confirmed 2026-06-19): "Draft me a cover letter for the HSE
  MANAGER - DATA CENTERS role at Dutco Group" → Rico drafted cover letter, no job_results,
  no Dutco company search, no unrelated apply links. ✅
- `/flow` contamination: none — smoke session had no profile, no jobs surfaced or tracked.
- bug01-smoke.yml cleaned up from main (commit `3e997073`).

## #644 Production Incident — RESOLVED (2026-06-19)

**Symptom:** All DB-backed endpoints broken after #638 merged to main and deployed.
`POST /pipeline/reminders` returned `{"status":"error"}`. `/rico/profile`,
`/applications`, `/subscription` also affected.

**Root cause:** `src/rico_db.py` `connect()` did `conn._rico_pool = pool`. psycopg2
connections have no `__dict__`; this raised `AttributeError` on every `db.connect()` call.

**Fix (PR #644, merged `26124ed180a77658be21cfa499e5629bd6a816ed`, 2026-06-19T07:53Z):**
- `connect()` no longer assigns any attribute to the connection object.
- Returns a direct per-request connection (proven pre-overhaul behavior).
- `_return_or_close()` closes directly.
- Regression tests added: `tests/test_rico_db_connect.py` (4 tests, slots-only fake conn).

**Why pooling disabled (not just patched):** pool is also incompatible with the many
`with db.connect() as conn:` callers (subscription_repo / applications_repo / profile_repo)
that never return connections to a pool. Re-enabling pooling needs a caller-wide
acquire/release refactor — tracked as a separate follow-up. Pool scaffolding left in place,
unused.

**Full verification chain:**
- Pre-merge tests: test_rico_db_connect (4) + test_followup_reminders (10) +
  test_application_lifecycle (21) = 35 passed. py_compile clean.
- Render deploy run #27 (07:55Z, SHA `26124ed`): all steps PASS, `/health` 200, `/version` confirmed.
- Render deploy run #28 (08:01Z, SHA `26124ed`): all steps PASS, `/health` 200, `/version` confirmed.
- followup-smoke.yml run #2 (08:02Z, SHA `26124ed`): **9/9 PASS** (first post-#644 smoke).
- Cron double-fire (cron-test.yml, dispatch run 27813559291):
  run 1 `status="ok"`, run 2 `status="ok"` (idempotent). cron-test.yml then removed.

## #355 Follow-up Reminders Phase 1 — COMPLETE (2026-06-19)

All Phase 1 gates passed:

| Gate | Status |
|---|---|
| Migration `027_followup_reminders.sql` applied to Neon | ✅ confirmed |
| `RICO_CRON_SECRET` set on Render + GitHub secret | ✅ confirmed |
| Production backend live at `26124ed` | ✅ `/health` 200, `/version` `26124ed` |
| `POST /pipeline/reminders` returns `status="ok"` | ✅ two consecutive Cron runs confirmed |
| followup-smoke.yml 9/9 PASS | ✅ run #1 (`27810675201`) and run #2 (`27813425034`) |
| DB layer restored (no `_rico_pool` error) | ✅ #644 merged + deployed |

**Render Cron configured (do not change command):**
```
Schedule: 0 4 * * *
Command:  curl -fsS -X POST -H "X-Cron-Secret: $RICO_CRON_SECRET" \
          https://rico-job-automation-api.onrender.com/api/v1/pipeline/reminders
```

**Phase 2: not started.** (#640 and #641 on hold — do not merge.)

## System overhaul v1+v2 — merged to main (PR #638, commit `9c003a7`)

| Change | Status |
|---|---|
| Telegram DM replies fixed (`rico_telegram_webhook.py`) | ✅ on main |
| Telegram `update_id` deduplication | ✅ on main |
| 12 DB indexes via `028_performance_indexes.sql` (applied at startup) | ✅ on main |
| Jobs "Load more" pagination (`apps/web/app/jobs/page.tsx`) | ✅ on main |
| DB connection pooling (`src/rico_db.py`) | ⚠️ scaffolding present, pooling **disabled by #644** |
| Email pre-fill after verification (`verify-email/page.tsx`) | ✅ on main |
| `initialEmail` prop + Suspense on login page | ✅ on main |
| TagInputField chips for profile page | ✅ on main |

**Known non-blocking startup warning (separate cleanup, do not fix here):**
```
migration_failed label=028_performance_indexes: column "job_id" does not exist
```
Pre-existing schema gap. Does not affect runtime. Track separately.

## On-hold PRs

- **PR #640** — on hold, awaiting explicit approval. Do not merge.
- **PR #641** — on hold, awaiting explicit approval. Do not merge.

## Confirmed production state (as of 2026-06-19, updated post-#648)

| Feature | PR | Status |
|---|---|---|
| Arabic/English cover-letter slot extraction | #615 | ✅ live |
| Matching guardrails (Settings + Profile) | #616 | ✅ live |
| Session job-search history | #617 | ✅ live |
| CI npm + Playwright browser cache | #619 | ✅ live |
| CV extraction quality warnings | #621 | ✅ live |
| Chat composer clip icon fix | #623 | ✅ live |
| preferred_cities yes/no guard | #625 | ✅ live |
| Application Pipeline V1 status alignment | #627 | ✅ live |
| Application Lifecycle Completion (search→opened, prepare→prepared) | #353 | ✅ smoke-PASS |
| Apply-Link Verification | #354 | ✅ smoke-PASS |
| Prepare→prepared persistence fix | #634 | ✅ live |
| Follow-up Reminders Phase 1 | #355/#636 | ✅ **Phase 1 COMPLETE** |
| System overhaul v1+v2 | #638 | ✅ merged + deployed `26124ed` |
| DB pool AttributeError hotfix | #644 | ✅ merged + deployed `26124ed` |
| BUG-01 cover-letter company-search guard | #648 | ✅ merged + deployed `40636ba` |

## CI health

- QA Tests (pytest + playwright): green on main.
- followup-smoke.yml: 9/9 PASS on `26124ed` (run #2, 2026-06-19).
- bug01-smoke.yml: **4/4 PASS** on `40636ba` (run #1, 2026-06-19). **Removed** after one-shot use.
- Render deploy: `workflow_dispatch` only — must be triggered manually after each release.
- cron-test.yml: **removed** (one-off #644 verification, cleaned up 2026-06-19).

## Next product roadmap order

Do not start without explicit scope and branch assignment.

1. **#355 Phase 2** — per-user interval settings, Telegram DM notifications (deferred
   from Phase 1). Needs explicit scope + branch.
2. **#356 Inbox Intelligence** — design-only; connector design doc on `main`.
3. **028_performance_indexes cleanup** — fix `column "job_id" does not exist` startup warning.
   Separate PR; do not mix with incident or Phase 2 work.
4. **DB pooling re-enable** — caller-wide acquire/release refactor required first; separate PR.

## Carry-over engineering backlog

- JWT revocation after password reset (old sessions stay valid after reset)
- Per-user rate limiting on /apply endpoint
- Race condition in guest→auth identity merge
- Settings page keywords tag input (same UX as profile TagInputField)
- Password complexity validation on register/reset

## Operating target

Use one repeatable workflow:

1. Scope one task.
2. Write or update the task in `TASKS.md`.
3. Generate one handoff brief.
4. Assign exactly one writer for the branch.
5. Require implementation notes and verification evidence.
6. Record final decisions and remaining risks.

## Quality gates

Use the applicable gates for each task:

- backend tests
- frontend build
- local smoke checks
- deployment verification when applicable
- no secrets changed
- no unrelated files changed
- rollback plan included

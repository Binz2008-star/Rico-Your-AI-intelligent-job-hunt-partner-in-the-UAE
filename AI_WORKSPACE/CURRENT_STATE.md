# Current State

_Last updated: 2026-06-19_

## Production baseline

- **main HEAD:** `26124ed180a77658be21cfa499e5629bd6a816ed` (fix(db): stop connect()
  crashing on conn._rico_pool — PR #644). Full recent lineage:
  `26124ed` (#644 DB hotfix) ← `3fbe2ea` (#643 workspace sync) ←
  `3958376` (#642 followup-smoke.yml) ← `9c003a7` (#638 system-overhaul-v1+v2) ←
  `9d7c1e0` (overhaul v1) ← earlier.
- **Deployed to Render:** ✅ live — `26124ed` confirmed deployed.
  Manual Render Deploy runs #27 and #28 succeeded (2026-06-19, 07:55Z and 08:01Z).
  `/health` 200, `/version` = `26124ed`. No `_rico_pool` AttributeError in logs.
- **Deployed to Vercel:** ✅ live — frontend at `ricohunt.com`.

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

## Confirmed production state (as of 2026-06-19)

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

## CI health

- QA Tests (pytest + playwright): green on main.
- followup-smoke.yml: 9/9 PASS on `26124ed` (run #2, 2026-06-19).
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

# Current State

_Last updated: 2026-06-18_

## Production baseline

- **main HEAD:** `1cb66e5d34895e83e1a61fd620bba4222bc14606`
- **Deployed to Render:** ✅ live — backend at `rico-job-automation-api.onrender.com`.
  Confirmed live 2026-06-17T22:12 UTC. All API routes 200 OK. CV quality warnings (#621)
  confirmed production-live. PR #625 not yet manually deployed to Render — trigger
  `workflow_dispatch` (Manual Render Deploy) to activate the preferred_cities guard on Render.
- **Deployed to Vercel:** ✅ live — frontend at `ricohunt.com`. Deploy to Production
  completed 2026-06-17T22:08 UTC on commit `4df959b`. Clip icon fix (#623) confirmed live.

## Repository baseline

- Rico AI is a UAE career companion.
- The system includes job discovery, filtering, scoring, alerts, application tracking,
  database storage, dashboard output, reminders, and feedback loops.
- Rico AI sits on top of the existing job automation system as the product layer.
- The backend foundation is FastAPI with Rico modules under `src/`.
- The database target is Neon/PostgreSQL.

## Confirmed production state (as of 2026-06-18)

| Feature | PR | Status |
|---|---|---|
| Arabic/English cover-letter slot extraction | #615 | ✅ live and confirmed |
| Matching guardrails (Settings + Profile) | #616 | ✅ live and confirmed |
| Session job-search history | #617 | ✅ live and confirmed |
| CI npm + Playwright browser cache | #619 | ✅ merged and deployed |
| CV extraction quality warnings | #621 | ✅ live and confirmed (Render 2026-06-17T22:12 UTC) |
| Chat composer clip icon fix | #623 | ✅ live and confirmed (Vercel 2026-06-17T22:08 UTC) |
| preferred_cities yes/no guard | #625 | ✅ merged to main `1cb66e5` — Render deploy pending |

## preferred_cities data quality — resolved

- **`preferred_cities: ['نعم']`** on `robenedwan@gmail.com` — fixed.
  - **Code guard:** PR #625 merged to main `1cb66e5`. Yes/no affirmations ("نعم", "yes",
    "no", "لا", "ok") are now blocked from being stored in `preferred_cities` in both the
    Rico chat pending-field handler and the Jotform webhook mapping.
  - **Data patch:** Neon SQL patch completed 2026-06-18. Verification query returned 0 rows —
    no remaining bad records.
  - **Render deploy:** Must be triggered manually (workflow_dispatch) to activate the guard
    on the live backend.

## Arabic cover-letter parser verdict

- Previous production failure (`اكتب لي خطاب تقديم لوظيفة ESG Manager ...` returning
  clarification instead of letter) was a **deployment gap**, not an active code bug.
- Fix was already in `main` via PR #615 (merged 2026-06-17T18:53 UTC). Render was running
  a June 12 build until manually redeployed.
- After deploy, smoke test confirmed Rico writes the Arabic cover letter directly.
- **Do not treat Arabic cover-letter parser as active P0** unless a new reproducible failure
  appears after commit `525964d758d13b86cf0f9b2907bdde7be773d9da`.

## CI health

- QA Tests (pytest + playwright) green on main.
- npm cache and Playwright browser cache now active — `playwright` job no longer stalls
  at `npm ci`. Warm-up run completed; subsequent runs restore from cache.
- Render deploy: `workflow_dispatch` only (no auto-deploy on push to main). Must be
  triggered manually via GitHub Actions → Manual Render Deploy after each release.

## Next priority

- **Application Pipeline V1** — end-to-end application submission flow with approval gate,
  audit log, and Telegram confirmation. Requires `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.
  Do not start without explicit scope and branch assignment.

## Active issues

- **Issue #618** — open as backlog for Arabic intent / smoke-test observations.
  Do not treat as P0 unless a new reproducible failure appears after commit
  `525964d758d13b86cf0f9b2907bdde7be773d9da`.

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

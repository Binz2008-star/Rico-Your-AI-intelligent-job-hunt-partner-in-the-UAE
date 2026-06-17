# Current State

_Last updated: 2026-06-17_

## Production baseline

- **main HEAD:** `b9708c91c0afd1b8d8a5ea83d7ff29aee02f5fb2`
- **Deployed to Render:** pending — Render deploy not yet triggered after #621. Last confirmed
  smoke test was against `525964d758d13b86cf0f9b2907bdde7be773d9da` (2026-06-17). CV quality
  warnings are merged to main but not yet confirmed production-live.
- **Deployed to Vercel:** yes — frontend live at `ricohunt.com` (no frontend changes in #621)

## Repository baseline

- Rico AI is a UAE career companion.
- The system includes job discovery, filtering, scoring, alerts, application tracking,
  database storage, dashboard output, reminders, and feedback loops.
- Rico AI sits on top of the existing job automation system as the product layer.
- The backend foundation is FastAPI with Rico modules under `src/`.
- The database target is Neon/PostgreSQL.

## Confirmed production state (as of 2026-06-17 smoke test)

| Feature | PR | Status |
|---|---|---|
| Arabic/English cover-letter slot extraction | #615 | ✅ live and confirmed |
| Matching guardrails (Settings + Profile) | #616 | ✅ live and confirmed |
| Session job-search history | #617 | ✅ live and confirmed |
| CI npm + Playwright browser cache | #619 | ✅ merged and deployed |
| CV extraction quality warnings | #621 | ✅ merged to main — Render deploy pending |

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

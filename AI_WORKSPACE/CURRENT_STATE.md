# Current State

_Last updated: 2026-06-19_

## Production baseline

- **main HEAD:** `9d7c1e0` (system overhaul v1). Lineage:
  `9d7c1e0` (overhaul v1) ← `a95c413` (#636 follow-up reminders Phase 1) ←
  `c8ea4fb` (#634 prepare→prepared persistence fix) ← `668d59dc` (#632/#354) ←
  `60d9d92` (#631 docs sync) ← `01cff584` (#630/#353 lifecycle board-write wiring).
- **Deployed to Render:** ✅ live — backend at `rico-job-automation-api.onrender.com`.
  Last confirmed live on `c8ea4fb` (run #26, 2026-06-18). System overhaul v1+v2 are
  on `engineering/system-overhaul-v2` branch (PR #638, draft) — **not yet merged to main**.
  Render deploy: `workflow_dispatch` only (no auto-deploy on push to main).
- **Deployed to Vercel:** ✅ live — frontend at `ricohunt.com`. System overhaul v2
  preview deployed on Vercel for PR #638 branch.

## Repository baseline

- Rico AI is a UAE career companion.
- The system includes job discovery, filtering, scoring, alerts, application tracking,
  database storage, dashboard output, reminders, and feedback loops.
- Rico AI sits on top of the existing job automation system as the product layer.
- The backend foundation is FastAPI with Rico modules under `src/`.
- The database target is Neon/PostgreSQL.

## Active branch: engineering/system-overhaul-v2 (PR #638, draft)

### v1 — Commit `9d7c1e0` (on main)

| Change | File(s) | Status |
|---|---|---|
| Telegram DM replies fixed — bot now calls `sendMessage` in all reply paths | `src/rico_telegram_webhook.py` | ✅ on main |
| Telegram `update_id` deduplication (bounded deque, 2000 entries, 1h TTL) | `src/rico_telegram_webhook.py` | ✅ on main |
| 12 missing DB indexes via `028_performance_indexes.sql`; applied at startup | `migrations/028_performance_indexes.sql`, `src/api/app.py` | ✅ on main |
| Jobs pagination — "Load more" button with page tracking | `apps/web/app/jobs/page.tsx` | ✅ on main |

### v2 — Commit `65709b9` (on engineering/system-overhaul-v2, PR #638)

| Change | File(s) | Status |
|---|---|---|
| DB connection pooling — ThreadedConnectionPool (min=1, max=10) | `src/rico_db.py` | PR #638 |
| Email pre-fill after verification — `/login?email=...` redirect | `apps/web/app/verify-email/page.tsx` | PR #638 |
| `initialEmail` prop + `useSearchParams` + `Suspense` on login page | `apps/web/components/auth/LoginForm.tsx`, `apps/web/app/login/page.tsx` | PR #638 |
| TagInputField component for target_roles, preferred_cities, skills | `apps/web/app/profile/page.tsx` | PR #638 |

## Confirmed production state (as of 2026-06-19)

| Feature | PR | Status |
|---|---|---|
| Arabic/English cover-letter slot extraction | #615 | ✅ live and confirmed |
| Matching guardrails (Settings + Profile) | #616 | ✅ live and confirmed |
| Session job-search history | #617 | ✅ live and confirmed |
| CI npm + Playwright browser cache | #619 | ✅ merged and deployed |
| CV extraction quality warnings | #621 | ✅ live and confirmed |
| Chat composer clip icon fix | #623 | ✅ live and confirmed |
| preferred_cities yes/no guard | #625 | ✅ merged to main — Render deploy pending |
| Application Pipeline V1 status alignment | #627 | ✅ live and confirmed (Vercel 2026-06-18) |
| Application Lifecycle Completion (partial) | #353 | ✅ search→opened + prepare→prepared smoke-PASS 2026-06-18 |
| Apply-Link Verification | #354 | ✅ live and smoke-PASS (PR #632) |
| Prepare→prepared persistence fix | #634 | ✅ live on `c8ea4fb` — smoke-PASS 2026-06-18 |
| Follow-up Reminders Phase 1 | #636 | ✅ live on `9d7c1e0` — **production smoke PASS 9/9** (2026-06-19); Render Cron not yet wired |
| System overhaul v1 (Telegram, indexes, pagination) | on main `9d7c1e0` | ✅ merged — Render deploy pending |
| System overhaul v2 (pooling, email pre-fill, tag UX) | PR #638 | 🔄 draft PR — CI pending |

## #355 Follow-up Reminders Phase 1 — production smoke PASS (2026-06-19)

- Migration `027_followup_reminders.sql` applied to Neon production (3 columns + index, no data loss).
- `RICO_CRON_SECRET` set on Render (and as a GitHub Actions secret for the smoke run).
- Production verified live on `9d7c1e0`: `/health` 200, `/version` commit `9d7c1e0`
  (via `ricohunt.com/proxy/*` Vercel MCP fetch; `x-render-origin-server: uvicorn`).
- **Smoke PASS 9/9** via dispatch-only CI workflow `followup-smoke.yml` (#642), run
  `27810675201`, test-safe isolated data (5000-day row, `interval_days=4000`):
  guard 403/403/200, old→`follow_up_due`, fresh stays `applied`, idempotent `marked_due=0`,
  no duplicate rows, `/flow`-backing status correct. Smoke test rows cleaned up.
- **Render Cron: not configured** (gated on approval). **Phase 2: not started.**
- Migration-collision concern RESOLVED — no duplicate number: follow-up reminders =
  `027_followup_reminders.sql`; performance indexes = `028_performance_indexes.sql`.

## CI health

- QA Tests (pytest + playwright) green on main.
- npm cache and Playwright browser cache active.
- Render deploy: `workflow_dispatch` only. Must be triggered manually after each release.

## PR #638 status (2026-06-19)

- Draft PR open on `engineering/system-overhaul-v2`.
- Vercel preview: ✅ deployed.
- pytest: queued at last check.
- playwright: in_progress at last check.
- No review comments.

## Next product roadmap order

Do not start without explicit scope and branch assignment.

1. **PR #638** — merge system overhaul v1+v2 once CI green.
2. **#355 Follow-up Reminders** — Phase 1 merged (`a95c413`); owner must apply
   migration + set `RICO_CRON_SECRET` + wire Render Cron.
3. **#356 Inbox Intelligence** (design-only; connector design doc on `main`).

## Carry-over engineering backlog

- JWT revocation after password reset (old sessions stay valid after reset)
- Per-user rate limiting on /apply endpoint
- Race condition in guest→auth identity merge
- Settings page keywords tag input (same UX fix as profile TagInputField)
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

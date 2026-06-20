# Current State

_Last updated: 2026-06-20_

## Production baseline

- **main HEAD:** `0ecef2b` (feat(auth): password complexity validation, #640). Lineage:
  `0ecef2b` (#640 password complexity) ← `6747b6d` (#666 workspace docs) ←
  `58ab189` (#667 render-audit fixes) ← `8200811` (#665 profile nudge synthetic guard) ←
  `9d7c1e0` (system overhaul v1) ← `a95c413` (#636 follow-up reminders Phase 1) ←
  `c8ea4fb` (#634 prepare→prepared persistence fix) ← `668d59dc` (#632/#354) ←
  `60d9d92` (#631 docs sync) ← `01cff584` (#630/#353 lifecycle board-write wiring).
- **Deployed to Render:** ✅ live — backend at `rico-job-automation-api.onrender.com`.
  Service ID: `srv-d7vjljrbc2fs73ctkp8g`. Auto-deploys from `main` via GitHub integration
  (Render auto-deploy is ON — `deploy-render.yml` is only needed for forced manual redeployment).
  Last confirmed: health 200, `/version` commit `0ecef2b`.
- **Deployed to Vercel:** ✅ live — frontend at `ricohunt.com`. Auto-deploys from `main`.
  Last confirmed: frontend reachable, proxy pass-through working.

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

### v2 — (on engineering/system-overhaul-v2, PR #638 — not yet merged)

| Change | File(s) | Status |
|---|---|---|
| DB connection pooling — ThreadedConnectionPool (min=1, max=10) | `src/rico_db.py` | PR #638 |
| Email pre-fill after verification — `/login?email=...` redirect | `apps/web/app/verify-email/page.tsx` | PR #638 |
| `initialEmail` prop + `useSearchParams` + `Suspense` on login page | `apps/web/components/auth/LoginForm.tsx`, `apps/web/app/login/page.tsx` | PR #638 |
| TagInputField component for target_roles, preferred_cities, skills | `apps/web/app/profile/page.tsx` | PR #638 |

## Confirmed production state (as of 2026-06-20)

| Feature | PR | Status |
|---|---|---|
| Arabic/English cover-letter slot extraction | #615 | ✅ live and confirmed |
| Matching guardrails (Settings + Profile) | #616 | ✅ live and confirmed |
| Session job-search history | #617 | ✅ live and confirmed |
| CI npm + Playwright browser cache | #619 | ✅ merged and deployed |
| CV extraction quality warnings | #621 | ✅ live and confirmed |
| Chat composer clip icon fix | #623 | ✅ live and confirmed |
| preferred_cities yes/no guard | #625 | ✅ live and confirmed |
| Application Pipeline V1 status alignment | #627 | ✅ live and confirmed (Vercel 2026-06-18) |
| Application Lifecycle Completion (partial) | #353 | ✅ search→opened + prepare→prepared smoke-PASS 2026-06-18 |
| Apply-Link Verification | #354 | ✅ live and smoke-PASS (PR #632) |
| Prepare→prepared persistence fix | #634 | ✅ live on `c8ea4fb` — smoke-PASS 2026-06-18 |
| Follow-up Reminders Phase 1 | #636 | ✅ merged to main `a95c413` — owner deploy steps pending |
| System overhaul v1 (Telegram, indexes, pagination) | on main `9d7c1e0` | ✅ merged — Render auto-deploys |
| Profile nudge synthetic guard | #665 | ✅ merged to main `8200811` — live |
| render-audit.yml bug fixes | #667 | ✅ merged to main `58ab189` — live |
| AI workspace docs update | #666 | ✅ merged to main `6747b6d` |
| Password complexity validation (register + reset) | #640 | ✅ merged to main `0ecef2b` — production smoke PASS 2026-06-20 |
| System overhaul v2 (pooling, email pre-fill, tag UX) | PR #638 | 🔄 draft PR — not yet merged |

## CI health

- QA Tests (pytest + playwright) green on main.
- npm cache and Playwright browser cache active.
- Render deploy: auto-deploys from main. `deploy-render.yml` (`workflow_dispatch`) available for forced manual redeployment.

## Cron jobs (Render) — 2 active

| Job | ID | Schedule | Status |
|---|---|---|---|
| `rico-profile-nudge-daily` | `crn-d8r53q6rnols73eujtbg` | `0 5 * * *` (09:00 UAE) | ✅ active — synthetic guard live (#665) |
| `rico-followup-reminders` | `crn-d8qet9rtqb8s73bk08e0` | `0 4 * * *` (08:00 UAE) | ✅ active — owner deploy steps for migration + secret pending (#636) |

## Next product roadmap order

Do not start without explicit scope and branch assignment.

1. **PR #638** — merge system overhaul v2 once CI green (v1 already on main).
2. **#355 Follow-up Reminders** — Phase 1 merged (`a95c413`); owner must apply
   migration + set `RICO_CRON_SECRET` + wire Render Cron.
3. **#356 Inbox Intelligence** (design-only; connector design doc on `main`).

## Carry-over engineering backlog

- JWT revocation after password reset (old sessions stay valid after reset)
- Per-user rate limiting on /apply endpoint
- Race condition in guest→auth identity merge
- Settings page keywords tag input (same UX fix as profile TagInputField — blocked on PR #638 merge)

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

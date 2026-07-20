# Handoff — #1249 Phase B: frontend controls + in-app results (rollout step 3)

**Issue:** #1249. **Previous:** Phase A (backend, inert) merged as #1251
(`9a55439d`). **This phase:** the Saved Search / Job Alert card + controls.
**Still inert in production** — `RICO_ENABLE_SCHEDULED_SEARCHES` stays false;
nothing here arms any schedule.

## What ships

- `apps/web/components/ScheduledSearchCard.tsx` (new): bilingual (EN/AR via
  the app-wide `rico-language` flag; RTL inherited from the root layout)
  card showing criteria (city / min AED salary / cadence), enabled state,
  last run, next expected run (~24h when enabled), and the latest in-app
  results (real source link, score, reason; **unknown salary labeled, never
  invented**). One-click pause/resume; delete is destructive → inline
  two-step confirm. Edit routes through chat by design (schedule identity is
  canonical per (city, salary, cadence)).
- `apps/web/app/saved-searches/page.tsx`: schedule cards render above the
  plain saved-search list; schedule rows are filtered out of the plain list
  (the generic endpoint returns them too — no double render). Scheduled
  fetch failure degrades to the plain list, never blanks the page.
- `apps/web/lib/api.ts` + `lib/schemas/index.ts`: `fetchScheduledSearches()`
  (zod-validated), `setScheduledSearchEnabled()`; delete reuses the existing
  saved-search DELETE.
- Backend (small, required for the controls):
  `PATCH /api/v1/rico/scheduled-searches/{id}` — JWT identity only; the id
  resolves strictly within the caller's own schedules (foreign/unknown id →
  plain 404, no cross-user probing); service
  `set_schedule_enabled_by_id` toggles exactly one schedule.

## Evidence

- Backend `tests/test_1249_scheduled_search.py`: **44 passed** (Phase A's 39
  + toggle endpoint auth/isolation/404 + per-id service toggle).
- Frontend `__tests__/scheduled-search-card.test.tsx`: **9 passed**
  (criteria/state, honest salary labels, real links, pause/resume PATCH
  calls, two-step delete confirm incl. cancel-no-call, AR copy, empty state).
- Full frontend suite: **854 passed (83 files)**; `npm run build` ✓;
  lint scoped to changed files: clean (repo baseline carries pre-existing
  errors untouched by this diff).

## Remaining rollout (owner-gated)

Step 4 production dry-run (`POST /api/v1/pipeline/scheduled-searches?dry_run=true`
with `X-Cron-Secret`), step 5 enable schedule + `RICO_ENABLE_SCHEDULED_SEARCHES=true`,
step 6 email for opted-in users. A Playwright journey spec lands with step 4/5
when the full flow can run against a real schedule.

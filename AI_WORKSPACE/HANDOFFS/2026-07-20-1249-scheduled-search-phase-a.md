# Handoff — #1249 Phase A: scheduled saved searches (backend, inert)

**Issue:** #1249 (owner spec). **Phase:** rollout step 2 — "Backend/chat
persistence and tests, inert by default." **No frontend. No schedule enabled.
No email behavior change. No DDL/migration.**

## What ships

- `src/services/scheduled_search_service.py` (new): AR/EN parsing (daily
  cadence + jobs word + explicit search verb; city lexicon; honest AED salary
  extraction incl. Arabic-Indic digits), canonical query identity, CRUD on the
  existing `rico_saved_searches` row (schedule lives in `filters.schedule`
  JSONB — additive, UNIQUE(user_id, query) upserts kill duplicates),
  constrained matching on the real engine, cross-run dedup
  (`delivered_keys`, cap 500), and the cron sweep.
- `src/repositories/profile_repo.py`: `list_enabled_scheduled_searches()`
  roster (JOIN rico_users for external identity).
- `src/agent/intelligence/intent_classifier.py`: deterministic
  `scheduled_search_{create,pause,resume,delete,status}` routing before the
  one-shot search branches; detection delegates to the service parsers.
- `src/rico_chat_api.py`: Step-2 dispatch branch → service handler
  (bilingual structured replies; public/guest identities get a sign-in
  prompt and never persist).
- `POST /api/v1/pipeline/scheduled-searches` (X-Cron-Secret, `?dry_run=true`)
  + `ScheduledSearchSweepResponse` schema; authenticated read-only
  `GET /api/v1/rico/scheduled-searches` (JWT identity only).
- Env: `RICO_ENABLE_SCHEDULED_SEARCHES` (default **false**, fail-closed) in
  CLAUDE.md + rico_env expectations.

## Safety invariants

- Kill switch off → sweep is a `{"status": "disabled"}` no-op; `dry_run=true`
  evaluates without persisting anything (mirrors the email sweep smoke).
- Salary honesty: stated-below-minimum excluded; unknown salary carried as
  `salary_known=false`, never inferred; no job surfaced without a real link.
- Lifecycle exclusions: applied/saved/skipped/blocked/hidden never re-delivered.
- In-app only: this path sends **no** email; `RICO_ENABLE_EMAIL_ALERTS` and
  per-user opt-in are untouched.
- No auto-apply anywhere in scope (per issue constraint).

## Evidence

- `tests/test_1249_scheduled_search.py`: **39 passed** (parsing AR/EN,
  canonicalization + history-preserving update, intent routing incl.
  not-swallowing plain searches, salary honesty, city/lifecycle/dedup/link
  filters, sweep kill-switch/dry-run/persistence/no-match behavior, chat
  guardrails, cron 503/403/200 auth, JWT-only status endpoint).
- Regression: intent/chat/routes/apply batches — 273 + 387 passed. 3
  pre-existing failures in `test_agent.py::TestApplyServiceIndeedMethod`
  reproduce identically on the clean tree (order-dependent env leakage; same
  family as the `test_apply_subscription_gate` finding logged on #1250).

## Deliberately NOT in this phase (later rollout steps)

Frontend card/controls (step 3), production dry-run smoke (step 4), enabling
the daily schedule/workflow (step 5), email delivery for opted-in users
(step 6), salary-slot editing of role set via chat, batching/caching provider
calls across users.

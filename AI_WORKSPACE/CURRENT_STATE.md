# Current State

_Last updated: 2026-06-20 (sidebar retry verified + UI/UX audit backlog logged)_

## Production baseline

- **Repository main HEAD:** `2bc48981fea8368c337931cc00323cb66feba703`
  (#661 duplicate upsert fix). Recent lineage:
  `2bc489` (#661 duplicate upsert_matches CI fix) ←
  `518a1a8` (#660 P0 context-loss bugs — 4 fixes) ←
  `a4f038a` (#658 workspace sync) ←
  `712be79` (#658 sidebar status retry) ←
  `f89c555` (#657 BUG-05 public-chat loop).
- **Production backend deployed SHA:** `f89c555aa969f75f99ee8b7d0296bb7582c272cd`
  (BUG-05 — last confirmed Render deploy 2026-06-19T~19:15Z).
  `518a1a8` / `2bc489` backend changes need a Manual Render Deploy to go live.
- **Deployed to Vercel:** ✅ auto-deploying `2bc489` from main.

## P0 Context-Loss Bugs — RESOLVED (2026-06-19, PR #660 + #661)

Four adversarial QA failures fixed and merged to main. Root cause: `RICO_MEMORY_BACKEND=postgres`
sets `_JSON_WRITE_ENABLED=False`, silently neutering all in-process context storage in production.

| Bug | Symptom | Fix |
|---|---|---|
| BUG-A | Ordinal follow-up ("Open the second one") → "No recent job search" | DB fallback in `_handle_job_detail`; `get_recent_matches()` added to `user_job_context_repo` |
| BUG-B | Bare company name ("Majid Al Futtaim") → "not a job role" | Company-name check against recent context + DB before emitting unknown-role error |
| BUG-C | "Give me the URL" misrouted to search | Extended `_OPEN_APPLY_LINK_RE` to match natural language URL requests |
| BUG-D | Apply link silently absent in job detail | `source_url` fallback + explicit "No apply link available" notice |

Also: `_store_search_matches_context` now calls `upsert_matches` on every search so results
persist to Neon across workers and process restarts (#660). Duplicate call removed in #661.

**Live QA validation (2026-06-19):** BUG-A and BUG-B confirmed working against production
Render endpoint. BUG-C and BUG-D code-confirmed (egress throttle prevented full E2E).
23 unit tests in `tests/test_p0_context_bugs.py` — all passing in CI.

## BUG-04 Unauthorized Profile Mutation — RESOLVED (2026-06-19)

**Symptom:** Three code paths silently wrote to Neon via `upsert_profile` without explicit
user consent: (A) `profile_update` intent persisted before confirming; (B)
`_target_role_search_response` appended searched role to `target_roles` on every search;
(C) `resolver._hydrate_from_chat` NER-inferred fields (cities/skills/roles/industries) were
persisted to DB from chat context.

**Fix (PR #655, merged `f4bacfa`, 2026-06-19T15:51Z):**
- **Fix A:** `profile_update` intent now stashes prefs as `_pending_field="confirm_profile_update"`,
  shows a before-save prompt, and calls `upsert_profile` only on affirmative reply. New
  `_format_pref_changes` helper. `_resolve_pending_field` handles confirm/cancel/pass-through.
- **Fix B:** Removed `upsert_profile` call from `_target_role_search_response`. Searching a
  role no longer promotes it to a standing `target_role`.
- **Fix C:** `resolver.py` snapshots 4 chat-inferable fields pre-NER, computes `_chat_added`
  delta, strips only that delta from the DB write. In-memory profile for the current request
  retains NER enrichment. CV/Jotform/action-derived values unaffected.
- 13 new tests in `tests/test_bug04_profile_mutation.py`.
- `test_p0_trust_fixes.py::test_concrete_profile_update_*` updated to assert ask-first behavior
  (old test was asserting the bug).

**Verification:** CI green (pytest ✅ playwright ✅ Vercel ✅). Zero new failures vs main
baseline (115 pre-existing failures unchanged). Production confirmed at `f4bacfa` via Vercel.

---

## BUG-03 Google-Intermediary Link — RESOLVED (2026-06-19)

**Symptom:** Job cards showed `google.com/search?...` as the apply/alt link because
`_format_match` was promoting `job_google_link` into `apply_url`/`source_url` without
stripping the Google intermediary.

**Fix (PR #651 `8685458` + hotfix PR #652 `b0807c0`, 2026-06-19):**
- `source_url` fallback no longer accepts Google search/URL links.
- `alt_link` Google intermediary cleared at write time.

**DB cleanup:** Read-only Neon sweep confirmed zero Google URLs in `jobs` or
`user_job_context`. One `rico_job_recommendations` row (Senior HSE Manager — Events /
Talent BluePrint, `job_key=6b1e9b6fdca6ad6b`) had empty `apply_url`/`source_url` —
contamination was display-only, already fixed at write time by #651/#652. No DB write needed.

---

## BUG-02 A/B/C/D Letter-Choice Routing — RESOLVED (2026-06-19)

**Symptom:** When Rico presented lettered options (A/B/C/D), user selecting "A" was routed
to option B, "B" to C, etc. — off-by-one in the index lookup.

**Fix (PR #649, merged `631ce7d`, 2026-06-19):** Zero-vs-one-based index corrected in the
letter-choice router. CI green on merge.

---

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

**Phase 2: not started.** (#640 on hold — do not merge. #641 merged 2026-06-20, see below.)

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

**028_performance_indexes startup warning — FIXED in PR #662:**
`job_id` → `searched_at DESC` in the `user_job_context` index.
`user_job_context` never had a `job_id` column; the correct column is `searched_at`.

## On-hold PRs

- **PR #640** — on hold, awaiting explicit approval. Do not merge.
- ~~**PR #641** — on hold~~ → ✅ **MERGED** `6fac4c0` (2026-06-20T07:59Z): v4 navy/indigo
  design tokens, live + smoke-PASS. Addresses audit item 6-A (see TASK-028).

## Security — credential redaction (2026-06-19)

An old Neon connection string (`authenticator:npg_R8hdwAMu9cOs`) was found committed in
`docs/archive/AUDIT_REPORT_2026-05-14.md`. Redacted via PR #656 (merged `e104135`,
2026-06-19). The credential is believed rotated/invalid (different user, different password
from current). Current chat-exposed credential (`npg_DI5SJWxO8wVj`, `neondb_owner`) was
**not** in the repo. Rotation of the current password is left to the owner (Neon console →
Reset password → update Render `DATABASE_URL` → redeploy).

**Note:** `git filter-repo` purge of the old credential from history is out of scope —
requires a coordinated force-push. Track separately if needed.

---

## #618 Reconciliation — complete (2026-06-19)

Status index posted as GitHub comment (issuecomment-4753155540). #654 absorbed-observations
note posted (issuecomment-4753155919). #618 remains open as the living tracker for 8 open
UX tasks. Workflow-class items moved to #654. Resolved items checked off.

**8 open tasks remaining in #618:**
TASK-010 Pipeline relevance guard (P1) · TASK-011 Match-score explanation (P2) ·
TASK-013 Application Pipeline V1 status alignment (P1) · TASK-014 Queue Arabic empty state (P2) ·
TASK-015 Pipeline notes/activity log (P2) · TASK-016 Profile completeness vs readiness (P3,
sidebar widget loading fixed in #658; metric reconciliation still open) ·
TASK-017 Daily application-limit explanation (P3) · TASK-018 Telegram Chat-ID validation (P2).

---

## Sidebar status-widget retry (TASK-027 / PR #658) — DONE + smoke-PASS (2026-06-20)

Sidebar READINESS/PIPELINE widgets no longer cache failed cold-start loads (the "blank grey
boxes on navigate-back" bug). Merged `712be79` via **PR #658**, which replaced #653 — that
branch had 46 stale commits already on main and was **closed/superseded**. Production smoke
PASS 2026-06-20 (full table on PR #658, issuecomment-4756899519). Tracked as
**TASK-20260619-027**.

> Earlier chat shorthand called this "TASK-024" — that is incorrect; TASK-024 is BUG-04. The
> sidebar fix had no ledger ID until TASK-027 was added.

---

## UI/UX live-audit backlog (2026-06-19) — logged as TASK-028

The 2026-06-19 live production UI/UX audit (`docs/audits/ui-ux-live-audit-2026-06-19.md`,
shipped via #658) produced 20 prioritized recommendations across `/command`, `/flow`,
`/profile`, `/upload`, `/settings`, `/subscription`, and the sidebar. They are now tracked as a
backlog in **TASK-20260619-028**. Item 1-D (sidebar widgets) is already DONE (TASK-027); each
remaining item spins into its own scoped TASK-NNN when picked up. Top pick per the audit:
**1-A** (clickable option buttons — biggest UX win for least effort).

---

## Neon production audit — complete (2026-06-19)

| Item | Finding |
|---|---|
| Production branch | `br-restless-cherry-amq6wj7o` (primary, default) |
| Active compute | `ep-long-poetry-am9o9qth` (PostgreSQL 17, aws-us-east-1) |
| Core Rico tables | All present (rico_users, rico_profiles, rico_chat_history, rico_saved_searches, rico_job_recommendations, rico_webhook_events, applications, application_drafts, user_job_context, user_documents, user_subscriptions, subscription_events, search_context, jobs) |
| Migration ledger | Inline idempotent (`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) — no Alembic; current as of `f4bacfa` |
| Google URLs in DB | Zero — `jobs` and `user_job_context` clean |
| Stale Neon branches >7 days | None — all closed PRs within 7 days |
| Live preview branches | 3 expected: pr-640, pr-641, pr-653 |

---

## Confirmed production state (as of 2026-06-19, updated post-BUG-04)

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
| BUG-02 A/B/C/D letter-choice routing | #649 | ✅ merged `631ce7d` |
| BUG-03 Google-intermediary link | #651/#652 | ✅ merged `b0807c0` |
| BUG-04 unauthorized profile mutation | #655 | ✅ merged + prod confirmed `f4bacfa` |
| Archived credential redaction | #656 | ✅ merged `e104135` (docs-only) |
| BUG-05 public-chat onboarding loop | #657 | ✅ merged `f89c555`, live on Render |
| P0 context-loss bugs (BUG-A/B/C/D) | #660 + #661 | ✅ merged `518a1a8` + `2bc489`; needs Render deploy |
| Sidebar status-widget retry (cold-start) | #658 | ✅ merged `712be79`, smoke-PASS 2026-06-20 (TASK-027) |
| Navy/indigo v4 design tokens | #641 | ✅ merged `6fac4c0`, smoke-PASS 2026-06-20 (audit 6-A / TASK-028) |

## BUG-05 Public-Chat Onboarding Loop — RESOLVED (2026-06-19)

**Symptom:** Every message sent from the `/command` (Ask Rico) public chat after the first
returned the identical "Welcome to Rico AI. Upload your CV or tell me your target role…"
string. Chat never progressed, ignored conversation history, and never routed to real AI.

**Root cause (three-part):**
1. `IntentRouter` routes "Give me 3 interview questions", fully-specified profile strings,
   and prompt-injection attempts to the legacy classifier (`should_use_ai=False`), not AI.
2. The legacy classifier's `process_message` checks `profile is None` → skips `upsert_profile`
   + `set_onboarding_status` when `_persist=False` (all public sessions) → always falls back
   to the onboarding welcome string. Since nothing is ever persisted for public users, every
   turn repeats the welcome.
3. When the streaming endpoint returns a `"done"` event without any SSE tokens (legacy path),
   `streamStarted=false` but `responseApplied=true`; the `if (!streamStarted)` guard in the
   frontend fired a redundant second `sendChatPublic` call.

**Fix (PR on branch `claude/ai-workspace-review-vtdjrb`, 2026-06-19):**
- **Fix A** (`src/services/chat_service.py`): Added `_force_ai` gate — when legacy path is
  chosen AND `profile is None` AND `ctx.can_persist_profile is False`, redirect to
  `_conversational_ai_reply` so public users get real responses instead of the welcome loop.
- **Fix B** (`src/api/routers/rico_chat.py`): `rico_chat_stream_public` only takes the
  non-streaming legacy path when `profile is not None`. No-profile public users fall through
  to AI streaming.
- **Fix C** (`apps/web/app/command/page.tsx`): Streaming fallback changed from
  `if (!streamStarted)` to `if (!streamStarted && !responseApplied)` to prevent double API
  call when the legacy path already applied the response via the `"done"` event.
- 7 unit tests in `tests/test_public_chat_no_profile_loop.py` covering the full routing
  matrix (public/no-profile/legacy → AI; public/no-profile/AI → AI; public/with-profile →
  legacy; auth/no-profile → legacy; auth/AI → AI).

**Routing matrix after fix:**

| Session | Profile | Router decision | Route taken |
|---|---|---|---|
| Public | None | Legacy | **AI** (new _force_ai gate) |
| Public | None | AI | AI (unchanged) |
| Public | present | Legacy | Legacy (unchanged) |
| Public | present | AI | AI (unchanged) |
| Auth | None | Legacy | Legacy (can persist state) |
| Auth | None | AI | AI |

---

## CI health

- QA Tests (pytest + playwright): green on main (`e104135`).
- followup-smoke.yml: 9/9 PASS on `26124ed` (run #2, 2026-06-19).
- bug01-smoke.yml: **4/4 PASS** on `40636ba` (run #1, 2026-06-19). **Removed** after one-shot use.
- Render deploy: `workflow_dispatch` only — must be triggered manually after each runtime release.
  Note: `/health` returns 403 from external networks (Render network-level policy) — verify via
  Render dashboard or GitHub Actions workflow (not WebFetch).
- cron-test.yml: **removed** (one-off #644 verification, cleaned up 2026-06-19).

## Next product roadmap order

Do not start without explicit scope and branch assignment.

1. ~~**#653 (TASK-024)** — sidebar status widget retry~~ — DONE: merged via #658 (`712be79`),
   production smoke-PASS 2026-06-20. Tracked as TASK-20260619-027.
2. **TASK-013 Application Pipeline V1** (P1) — end-to-end application submission with approval
   gate, audit log, Telegram confirmation. Needs dedicated issue + branch.
3. **TASK-010 Pipeline relevance guard** (P1) — pre-filter pipeline results against active
   profile before scoring. Needs dedicated issue + branch.
4. **#355 Phase 2** — per-user interval settings + Telegram DM notifications.
5. **#356 Inbox Intelligence** — design-only; connector design doc (#566) on `main`.
6. ~~**028_performance_indexes cleanup**~~ — fixed in #662 (2026-06-19).
7. **DB pooling re-enable** — caller-wide acquire/release refactor; separate PR after 028 fix.

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

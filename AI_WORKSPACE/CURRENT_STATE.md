# Current State

_Last updated: 2026-06-18_

## Production baseline

- **main HEAD:** `c8ea4fb` (#634 prepare→prepared persistence fix). Lineage:
  `c8ea4fb` (#634) ← `668d59dc` (#632/#354) ← `60d9d92` (#631 docs sync) ←
  `01cff584` (#630/#353 lifecycle board-write wiring) ← `edc53fd` (docs) ←
  `62a679b` (production code baseline).
- **✅ Production backend confirmed live on `c8ea4fb`.** Manual Render Deploy
  (`workflow_dispatch`) run #26 verified `/version` `commit=c8ea4fb` and `/health` 200
  on 2026-06-18. This includes #353 (Changes A & B), #354 (LinkVerifier), and #634
  (prepare→prepared fix). Render remains `workflow_dispatch` only — no auto-deploy on push.
- **Deployed to Render:** ✅ live — backend at `rico-job-automation-api.onrender.com`.
  Confirmed live 2026-06-17T22:12 UTC. All API routes 200 OK. CV quality warnings (#621)
  confirmed production-live. PR #625 (preferred_cities guard) not yet manually deployed to
  Render — trigger `workflow_dispatch` (Manual Render Deploy) to activate it on the live backend.
- **Deployed to Vercel:** ✅ live — frontend at `ricohunt.com`. Deploy to Production
  completed 2026-06-18T04:45 UTC on commit `62a679b`. Application Pipeline V1 status
  alignment (#627) confirmed live. Manual smoke passed 2026-06-18.

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
| Application Pipeline V1 status alignment | #627 | ✅ live and confirmed (Vercel 2026-06-18T04:45 UTC) |
| Application Lifecycle Completion (partial) | #353 | 🟢 search→`opened` (Change A, #630) and prepare→`prepared` (Change B, #630 + fix #634) confirmed live and **production-smoke PASS** 2026-06-18. Remaining #353 lifecycle parts (beyond this item) not started. |
| Apply-Link Verification | #354 | ✅ live on `668d59dc`/`c8ea4fb` (PR #632) — `LinkVerifier` wired into `open_apply_link`. Smoke PASS. |
| Prepare→prepared persistence fix | #634 | ✅ live on `c8ea4fb` — upgrades the same `opened` record (no duplicate); reply only claims "Prepared" when the board write succeeds. Production-smoke PASS 2026-06-18. |

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

## PR backlog triage (2026-06-18)

Read-only triage of the three open PRs, then cleanup. Open PR backlog is now **clean: 0 open PRs**.

| PR | Title | Decision | Result |
|---|---|---|---|
| #601 | feat: job hopping / first day / upskilling + prior batch | Close as stale/superseded | Closed — too broad, stale base, draft, production code in `src/rico_chat_api.py`, test plan unchecked, body/title mismatch. Fast paths to be re-cut later as small focused PRs from current `main` if still needed. |
| #608 | docs: detect-but-ignore localization pattern | Merge after final check | Squash-merged `8941697c2be56c40d2047dcdeedd20e521dfc06f` — adds `docs/architecture/localization.md`, docs-only. |
| #566 | docs: Gmail read-only connector design | Merge after final check | Squash-merged `edc53fdf37645b153148a006e68f34215d8adc8a` — adds `docs/integrations/gmail-readonly-connector.md`, docs-only; aligned with #356 Inbox Intelligence (design-only). |

Note: the six "Continuous AI: …" third-party bot checks error generically on every PR and are
not project test failures. Real gate (Vercel) was green on all three.

## Next product roadmap order

Do not start without explicit scope and branch assignment.

1. **#353 Application Lifecycle Completion** — 🟢 search→opened + prepare→prepared live and smoke-PASS (this lifecycle gap closed via #630 + #634); any further #353 lifecycle parts not started
2. **#354 Apply-Link Verification** — ✅ live and smoke-PASS
3. **#355 Follow-up Reminders** ⬅ next priority (NOT started — needs explicit scope + branch)
4. **#356 Inbox Intelligence** (design-only; #566 connector design doc now on `main`)

## Deploy + smoke — completed 2026-06-18

The #353/#354/#634 backend changes are live on Render (`c8ea4fb`, run #26) and the
production smoke passed:

1. ✅ search jobs → `/flow` shows them as `opened` (#353 Change A)
2. ✅ prepare an application → `/flow` Prepared counter/status updates (#353 Change B + #634)
3. ✅ live apply link → `apply_url` present (#354)
4. ✅ dead/blocked apply link → fallback response, no `apply_url` (#354)
5. ✅ no duplicate record on prepare; Rico only claims "Prepared" when board persistence succeeds (#634)

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

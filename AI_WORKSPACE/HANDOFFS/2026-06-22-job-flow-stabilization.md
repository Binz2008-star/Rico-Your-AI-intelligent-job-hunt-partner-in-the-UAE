# Handoff — Job-Flow Stabilization (PRs #727, #724, #723)

_Date: 2026-06-22 · Author: Claude Code (Opus) · Session: job-flow stabilization train_

## Objective

Move Rico from "many job-flow failures" (production Tests 1–9) to a stable, production-ready
job-search flow. Triage the failures into focused PRs, merge one at a time, and verify the
Render deploy after each merge before proceeding.

## Outcome — 3 PRs merged + deployed (priority order)

| PR | Category | Merge SHA | Deploy verified |
|---|---|---|---|
| **#727** | P0 — job-card apply-link integrity + "open the Nth job" chat action | `e1d87fc` | ✅ `/version`==SHA, `/health` 200 |
| **#724** | P1 — provider cascade (Jooble/Adzuna) + quota fallback + degraded UX | `5fe9171` | ✅ `/version`==SHA, `/health` 200 |
| **#723** | P1 — multi-role job-search parsing | `713ea75` | ✅ `/version`==SHA, `/health` 200 (run 27960400407) |

Production main HEAD is now **`713ea7528b0ff6f6ccd9e2c3adf3ee51be7d8479`**.

## How deploy was verified (egress-restricted sandbox)

The session sandbox cannot reach `rico-job-automation-api.onrender.com` (egress allowlist). The
existing **`Deploy Render Backend`** GitHub Actions workflow (`.github/workflows/deploy-render.yml`)
fires on every push to `main`, triggers the Render deploy hook (`RENDER_DEPLOY_HOOK_URL` secret),
**polls `/version` until `.commit` == the merge SHA**, then asserts `/health` == 200. A green run
is therefore proof of a live, correct deploy. Verified each merge via the Actions API
(`actions_list` / `get_job_logs`) rather than direct curl. **This is the canonical way to confirm
backend deploys from a restricted environment.**

## What shipped (now live)

- **`src/services/job_link.py`** — canonical `resolve_job_link()` returning a single `usable_link`
  plus `link_unavailable`/`reason`, shared by `_format_match` (cards) and the open-apply chat
  action; `build_link_fallback_cta()` (company-site/Google/LinkedIn/copy/save — plain search URLs).
  `apply_job` tool no longer raises "missing required 'link' field".
- **`src/job_providers.py`** — cascade `cache(24h) → internal → Jooble → Adzuna → JSearch →
  degraded CTA`; provider-health/quota cooldowns (403→quota no-retry); `/health` `job_providers`
  indicator (configured/degraded only — never secrets).
- **`extract_role_list()` + `job_search_multi_role` intent** — comma/`and`-separated role lists
  and trailing `do not search …` exclusions parsed instead of "I do not recognize …".

## Provider configuration (owner-managed)

Keys live in Render env only (never hardcoded/committed/logged): `JOOBLE_API_KEY`,
`ADZUNA_APP_ID`+`ADZUNA_APP_KEY` (Adzuna opt-in, both required), `RAPIDAPI_KEY`. Confirm presence
via `GET /health → job_providers[].configured` (booleans only).

## Production Tests 1–9 — status

- ✅ Fixed & live: **T9** (apply-link, #727), **T4** (3-role list, #723).
- 🔴 Still open → next PRs:
  - **PR B / P1** — T8: save the Nth job to pipeline from recent context.
  - **PR C / P1** — T1, T7: strongest-CV/profile selection + auth/CV context retention + no silent
    role substitution. (T7 weak-location partly addressed by #727.)
  - **PR D / P1** — T2, T3, T5, T6: role-parsing edge cases (`only`, `jobs for A and B`, CV-based
    exclusions, category mapping, `not coding`). Builds on #723.

## Open items / watch-outs

- **Duplicate PRs from other sessions** (flagged, untouched): **#726** (`rico_link_resolver.py` —
  superseded by #727) and **#722** (`lib/job-fallback.ts` — overlaps #724/#727). Recommend
  closing or rebasing to avoid a competing apply-link resolver.
- Each next PR must stay one-bug-category, start from clean `origin/main`, open Draft, mark ready
  only when CI green, merge only when scope clean — per OPERATING_RULES.
- Do **not** touch #712 DB migration, scraping, billing, or auth rewrites.

## Constraints honored

One PR per bug category · CI-green + scope-clean before each merge · Render deploy confirmed
before next merge · 0 external provider quota burned (all tests mocked) · no secrets exposed ·
no LinkedIn/Indeed scraping.

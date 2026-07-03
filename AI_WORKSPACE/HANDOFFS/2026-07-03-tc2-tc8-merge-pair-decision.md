# TC-2 / TC-8 Merge Pair Decision — 2026-07-03

## Summary

PR #834 and PR #835 must be merged as a pair.

#834 alone is **not** sufficient for the user-visible TC-2 / TC-8 fixes.

## Current PR status

- **#834**: ready for review, clean, mergeable, base `main`
- **#835**: ready for review, clean, mergeable, stacked on #834 branch
  (`claude/tc2-tc8-wiring-followup` → base `claude/tc2-tc8-live-path-fix`)
- **#833**: evidence-only, independent, keep draft / merge later
- **#824**: blocked / not mergeable, do not merge

## Decision

Merge order:

1. Merge **#834** first.
2. Let **#835** retarget / recompute against `main`.
3. If #835 remains clean and CI stays green, merge **#835** immediately.
4. Wait for backend deploy (Render).
5. Run live `/command` smoke.

**Do not deploy production with only #834 and call TC-2/TC-8 fixed.**

## Why #834 alone is incomplete

#834 adds the groundwork:

- `target_roles` plural classification (`update my target roles to X and Y`)
- canonical `target_roles` persistence (singular `target_role` key was dropped by
  the `upsert_profile` field whitelist)
- grounded interview-prep handler (role + company + tracked-application lookup)
- duplicate / dead interview-prep handler cleanup

But #834 does **not** include the final dispatch wiring required for the live,
user-visible behavior.

Empirical smoke (real dispatch, `_handle_active_user_inner`, seeded ESG/Compliance
profile) showed:

- **TC-8 on #834 alone:**
  `prepare me for an interview for the Retail Operations Manager role at Richemont`
  is still intercepted by the company-openings path (`_COMPANY_SEARCH_RE` matches
  "role at Richemont") **before** it reaches the grounded interview handler —
  returns company/openings, not prep.

- **TC-2 on #834 alone:**
  after confirming `ESG Manager` + `Compliance Manager`, `search for jobs now`
  still resolves `search_query = "Operations Manager"` because the dispatch prefers
  a stale `recent_search_role` cache over the freshly-confirmed `target_roles`.

## What #835 adds

#835 contains the wiring that makes #834's contracts actually fire:

- `_INTERVIEW_REQUEST_RE` guard
- company-search guard so interview-prep phrases are not hijacked into the
  company-openings path
- target-role confirmation clears the
  `recent_search_role` / `recent_role` / `recent_job` cache
- control case remains valid: `find jobs at ADNOC` still routes to company search

## Required production smoke after both merge

**TC-2:**

1. `update my target roles to ESG Manager and Compliance Manager`
2. confirm
3. `search for jobs now`

Expected:

- Search uses ESG Manager / Compliance Manager
- No stale `Operations Manager` query
- No long irrelevant target-role blob

**TC-8:**

1. `prepare me for an interview for the Retail Operations Manager role at Richemont`

Expected:

- Routes to `interview_prep`
- Response is grounded to Retail Operations Manager + Richemont
- Does **not** return Richemont openings / company-search results

**Control:**

1. `find jobs at ADNOC`

Expected:

- Company-search still works

## Current instruction

Proceed only with the **#834 → #835 merge train** and post-deploy smoke.

- Do not start new work.
- Do not touch #824, #815, #688, #691.
- Do not treat GitHub Pages deployment failures as Rico production failures.
- GitHub Pages should be disabled separately from repo settings if needed; do
  **not** repoint `ricohunt.com` / `www` to GitHub Pages.

## Environment caveat for future agents

The live TC-2/TC-8 contracts were proven here by running the backend dispatch
directly (real `RicoChatAPI._handle_active_user_inner` with a seeded profile),
**not** against live Neon / JSearch / DeepSeek — this build environment cannot
reach them. Provider results and final AI text still require the production
`/command` smoke above after deploy.

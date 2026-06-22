# Handoff — Job-flow stabilization complete

_Date: 2026-06-22_

## Current production baseline

- **Repository main HEAD / production backend SHA:** `38fbf5da19975df6f7d3d21168b137741d502e6d`
- **PR #730 deploy verification:** `/version` matched `38fbf5da19975df6f7d3d21168b137741d502e6d`; `/health` returned 200; GitHub deploy workflows were successful.
- **Vercel:** production/root/proxy healthy by deploy verification report.
- **Render logs:** direct Render MCP log scan was unavailable/unauthorized in the session; no error signals were observed from deploy workflows or health checks.

## PRs merged and deployed in the job-flow stabilization train

| PR | Scope | Merge SHA | Status |
|---|---|---:|---|
| #727 | P0 apply-link integrity, canonical `src/services/job_link.py`, card/chat shared usable link | `e1d87fc` | ✅ merged + deployed |
| #724 | provider cascade/quota fallback: cache → internal → Jooble → Adzuna → JSearch → degraded CTA | `5fe9171` | ✅ merged + deployed |
| #723 | multi-role parsing and `job_search_multi_role` | `713ea75` | ✅ merged + deployed |
| #728 | P0 ordinal apply-link routing past job-detail gate | `c77781a` | ✅ merged + deployed |
| #729 | PR B: save the Nth job to pipeline from recent search context | `963e40b` | ✅ merged + deployed |
| #730 | PR D: role-parsing edge cases (`only`, jobs-for-A-and-B, CV exclusions, category mapping) | `38fbf5d` | ✅ merged + deployed |

## Superseded/closed PRs

- **#726** was closed as superseded by #727 + #728 + #729.
- Do **not** rebase or salvage #726.
- Do **not** reintroduce `src/rico_link_resolver.py`.
- Keep `src/services/job_link.py` as the single canonical apply-link resolver.

## Production Tests 1–9 status

| Test | Status | Fixed by / next step |
|---|---|---|
| T2 — Technical Product Owner only | ✅ fixed live | #730 |
| T3 — HSE Manager and QHSE Manager | ✅ fixed live | #730 |
| T4 — comma-separated multi-role list | ✅ fixed live | #723 |
| T5 — CV search with exclusions | ✅ fixed live | #730 |
| T6 — product/technical management, not coding | ✅ fixed live | #730 |
| T8 — save second job to pipeline | ✅ fixed live | #729 |
| T9 — open apply link / missing link | ✅ fixed live | #727 + #728 |
| T1 — strongest CV/profile selection | 🔴 open | PR C |
| T7 — Environmental Manager substitution + auth/CV context retention + location quality | 🔴 open | PR C |

## Remaining work: PR C only

PR C is now the only remaining job-flow QA item from Tests 1–9.

### PR C scope

- T1: `Find UAE jobs that match my strongest CV profile.`
  - Do not blindly use stale `target_role` such as Software Engineer.
  - Use the strongest confirmed active CV/profile signal.
  - Ask the user to choose if multiple profile tracks are ambiguous.

- T7: `Search UAE jobs for Environmental Manager.`
  - Do not silently substitute Environmental Manager with Environmental Officer.
  - Ask permission before broadening if exact role is unavailable.
  - Preserve authenticated user/CV/session context.
  - Do not ask a logged-in Pro user with uploaded CV to sign up or upload again.
  - Keep location UAE-focused with safe preference for UAE/Ajman/Dubai/Sharjah/Abu Dhabi.

### PR C hard guardrails

- No auth rewrite.
- No billing changes.
- No DB migration.
- No #712 work.
- No landing-page work.
- No provider scraping.
- No repeated real provider searches.
- Use mocks/fixtures only in tests.
- Keep `src/services/job_link.py` as the only canonical resolver.
- Do not reintroduce `src/rico_link_resolver.py`.

## Recommended next command

```text
Rico mode. Start PR C only from clean current origin/main. First do read-only mapping of current CV/profile selection, target_role loading, auth/CV context loss, and role substitution. Report the smallest safe implementation plan before large edits. Branch: fix/profile-context-role-selection.
```

# Post-merge verification — PR #615 and PR #616

Date: 2026-06-17
Owner: Codex

## Scope

- PR #615: Arabic/English cover-letter slot extraction.
- PR #616: TASK-20260617-007 Settings/Profile matching guardrails.

## Repository verification

- Latest `origin/main` includes #616 squash merge:
  `a8516c188baa0841d7f2ec7b942ef9215e9e2787`.
- Previous commit on main includes #615:
  `66f7364f8b6ea03326223383b5536c627204ffd2`.
- #616 changed files stayed limited to Settings/Profile guardrails, frontend warning display,
  related API/types/schemas, and matching guardrail tests.

## Production/deploy verification

- GitHub `Deploy to Production` workflow completed successfully for
  `a8516c188baa0841d7f2ec7b942ef9215e9e2787`.
- Workflow job `Deploy & Verify Production` passed backend health, frontend reachability,
  and proxy pass-through checks.
- Live Render `/health` returned `status=ok`.
- Live `/version` and `/api/v1/version` are reachable but still report an older static commit
  (`01c092b58a30011b4f8b46435f36e7de20152e9e`). Treat this as version metadata drift unless
  another live smoke check fails.

## Smoke verification plan

- `/health`: call `https://rico-job-automation-api.onrender.com/health` and require `status=ok`.
- Basic Rico chat: send a harmless public chat message and require a non-error Rico response.
- Settings guardrail warnings: set conflicting include/exclude keywords and high `min_score`,
  then verify advisory warnings are returned/displayed without blocking save.
- Profile guardrail warnings: set invalid city (`نعم`) and more than 3 target roles,
  then verify advisory warnings are returned/displayed without blocking save.
- Arabic cover-letter request: send
  `اكتب لي خطاب تقديم لوظيفة ESG Manager في شركة Aldar Properties في أبوظبي`
  and verify Rico drafts directly instead of asking again for role/company/city.

## Outcome

Post-merge health is acceptable for starting TASK-20260617-008. No production break was observed.

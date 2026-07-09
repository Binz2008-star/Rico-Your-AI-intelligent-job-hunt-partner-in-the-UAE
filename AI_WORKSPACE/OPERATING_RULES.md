# Rico Operating Rules

These rules define how AI coding agents should work in this repository. They are operational guardrails for GitHub, Render, Vercel, Neon, testing, and production verification.

Treat every change as production work. Prefer small scoped pull requests, explicit verification, and honest status reporting over broad rewrites.

## Session Boot Sequence

Every new Rico work session must read, in order:

1. `AI_WORKSPACE/START_HERE.md`
2. `CLAUDE.md`
3. `AI_WORKSPACE/CURRENT_STATE.md`
4. `AI_WORKSPACE/TASKS.md`
5. `AI_WORKSPACE/OPERATING_RULES.md`
6. The latest file under `AI_WORKSPACE/HANDOFFS/`, when referenced by `START_HERE.md`

If these files disagree, do not guess. Report the conflict and use GitHub `main`, deployed `/version`, and the relevant PR/commit as the source of truth.

## Agent Roles

Use one role per pass. Do not mix planning, coding, reviewing, and deployment verification in one unstructured response.

| Role | Responsibility | Output |
|---|---|---|
| Planner | Read workspace state, confirm scope, identify risks | Plan, files in scope/out of scope, verification plan |
| Coder | Make the smallest safe change | Patch plus tests/docs needed for that patch |
| Reviewer | Audit the diff for regressions, security, scope creep | Findings, blockers, approval or changes requested |
| Tester | Run relevant checks or inspect CI | Commands/checks, results, failures, next action |
| Deploy verifier | Confirm production state after merge | Deployed SHA, health/version, smoke result, rollback note |

## Branch and Scope Rules

- Use one branch per task.
- Use one writer per branch.
- Keep PRs small enough to review safely.
- Do not mix docs-only workspace syncs with runtime code changes.
- Do not include unrelated formatting, renames, refactors, or generated churn.
- If a branch contains unrelated files, stop and report the scope issue before merging.

## Product Generalization Rule

Rico is a global SaaS product for all users. Smoke-test findings are evidence of product behavior; they are not product logic.

Every fix must be:

- global
- user-agnostic
- data-driven
- tested with synthetic users where possible

Do not special-case:

- one live user account
- one owner/test account
- one profile state
- one target-role list
- one saved search
- one session state
- one language path
- one provider result set
- one smoke-test dataset

For every investigation or fix, identify the affected scope:

1. one user only
2. one profile state
3. one language or locale
4. one provider or integration
5. all users

Fix the underlying product/system behavior, not one account.

If a bug is discovered through a smoke-test account, the report must state:

> The smoke-test account exposed the bug, but the fix is global.

If a proposed fix only improves one live account or one sampled dataset, stop and mark it invalid.

Use synthetic users and synthetic profile data unless the owner explicitly approves production smoke testing.

Where relevant, cover:

- complete-profile user
- no-profile / no-CV user
- guest/public session
- Arabic input
- English input
- multiple unrelated target roles, not only the role that exposed the bug

## Pull Request Audit Checklist

Before recommending merge, verify:

1. PR is not draft, unless the owner explicitly approved merging that draft.
2. Base branch is `main`, unless a different base is intentional and documented.
3. Head branch is current enough for the risk level.
4. Changed files match the stated scope.
5. CI status is green or failures are proven unrelated/pre-existing.
6. Security-sensitive changes have tests or a clear manual verification path.
7. DB migrations have an explicit application/rollback plan.
8. Backend changes include Render deploy expectations.
9. Frontend changes include Vercel/build/browser expectations.
10. The PR body and workspace state do not contain stale claims.
11. The linked TASKS.md entry has a complete Continuity Block (scope, risk,
    validation run/required, rollback) — no PR merges on a task with an
    empty or stale Continuity Block.

Do not merge if any blocker remains unresolved.

## Merge Policy

Never recommend or perform a merge when:

- The PR is draft without explicit approval.
- CI is failing and the failure is not explained.
- The PR includes unrelated files.
- A production deployment requirement is unclear.
- A migration may be destructive and the owner has not approved it.
- The change bypasses `src/rico_safety.py`, user confirmation, auth identity, or approval mode.
- The deployed state cannot be verified but the report claims it is live.

Docs-only PRs may skip runtime tests only when changed files are limited to documentation/workspace files and no generated/runtime config changed.

## Backend / Render Verification

For backend changes, do not claim production is live until verified:

1. Record merged commit SHA.
2. Confirm Render deployment references the same commit SHA.
3. Check `GET /health`.
4. Check `GET /version`.
5. Confirm `/version.commit` matches the expected SHA or explicitly report the mismatch.
6. Run feature-specific smoke checks when routes or behavior changed.

Render **auto-deploys on every push to `main`** via `deploy-render.yml` (PR #686): it triggers the
deploy hook and blocks until `/version.commit` matches the pushed SHA, so the deploy run itself performs
steps 2–5 above. Check that run's status to confirm a backend release. A manual `workflow_dispatch` run
is still available for on-demand redeploys.

If `main` is ahead of Render, report: `backend not live yet` and identify the deployed SHA and expected SHA.

## Frontend / Vercel Verification

For frontend changes:

1. Confirm Vercel build/check is successful for the target commit.
2. Confirm production or preview URL points to the expected commit where available.
3. For UI/UX changes, require browser or device smoke testing.
4. Build success alone is not sufficient for navigation, responsive layout, auth, or interaction changes.

Minimum UI smoke for affected flows:

- Landing page loads.
- Signup/login path loads.
- Authenticated dashboard loads.
- Chat/command surface loads.
- Mobile navigation works when layout/navigation changed.
- Arabic and English text are not broken when copy/i18n changed.

## Neon / Migration Safety

For DB changes:

- Never assume a migration applied.
- Verify migration filename and sequence number.
- Prefer idempotent SQL (`IF NOT EXISTS`, safe backfills, nullable-first columns).
- Avoid destructive changes unless explicitly approved.
- Provide rollback or mitigation notes.
- Unit tests must not write to live Neon.
- If startup-applied migrations fail, inspect the first failing migration; later migrations may not have applied.

## Production Smoke Matrix

Use this matrix after relevant merges/deploys.

| Area | Smoke |
|---|---|
| Backend core | `GET /health`, `GET /version` |
| Public chat | `POST /api/v1/rico/chat/public` with a harmless prompt |
| Auth | signup/login/logout and `GET /api/v1/me` when auth changed |
| CV/upload | upload route and parse result when CV code changed |
| Jobs | search/list/details/apply-link route when job pipeline changed |
| Applications | save/apply/draft/reminder action when lifecycle changed |
| Cron | endpoint returns `status="ok"`; confirm idempotency for repeat runs |
| Frontend | affected page loads, no blocking console/network errors, mobile if relevant |

## Safety and User Trust

- High-impact actions require explicit user confirmation.
- Apply/send/mutate-preferences paths must respect `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.
- Do not derive protected user identity from request body fields.
- Do not log secrets or expose tokens in docs, tests, comments, or PR bodies.
- If credentials appear in history, report whether redaction and rotation are both needed.
- Do not call live third-party APIs from unit tests.

## No Dead UI Rule

A route must be exactly one of:

1. **Active and reachable** — no redirect; the page is the live production UI.
2. **Redirect-only** — `next.config.js` redirect is the mechanism AND the `page.tsx` either does not
   exist or contains only a thin passthrough with no meaningful logic.
3. **Removed** — route, redirect, and page file all deleted.

Hybrid state (redirect + real page.tsx code) is prohibited. It silently escapes CI, TypeScript, and
code review while accumulating unreachable dead code. See DEC-20260628-001.

Before opening a PR that adds or keeps a redirect: confirm `page.tsx` either does not exist or
contains only `redirect()`. If it contains real logic, either make the route live or strip the page.

## Status Reporting Format

Use fact-only status reports:

```text
Status: PASS / BLOCKED / PARTIAL / UNKNOWN
Scope checked: <files/features>
Current main: <sha>
PR/head: <sha>
CI: <result>
Deploy: <Render/Vercel sha and status>
Smoke: <what passed/failed/not run>
Affected scope: <one user / one profile state / one language / one provider / all users>
Product generalization: <confirm fix is global and user-agnostic>
Synthetic users used: <yes / no / n-a>
No owner-account special-casing: <confirmed>
Risks: <remaining risk>
Recommendation: <merge / do not merge / deploy / investigate>
```

If a check was not run, write `not run` and explain why. Do not imply verification from assumptions.

## Rollback Rules

Every production-impacting PR should have a rollback note:

- Runtime code: revert commit or PR.
- Frontend UI: revert PR and let Vercel redeploy.
- Backend: revert PR and redeploy Render.
- Migration: state whether rollback SQL is needed or whether code can tolerate the schema.
- Cron: disable or restore the previous command/schedule.

## Default Decision Bias

When uncertain, prefer:

1. Stop and report uncertainty.
2. Inspect current repo/deploy state.
3. Create a small docs or test-only PR.
4. Avoid production mutation until the owner explicitly approves it.

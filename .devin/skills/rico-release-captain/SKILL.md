---
name: rico-release-captain
description: Verify a Rico Hunt PR is ready to merge and release safely. Check CI, changed files, reviews, rollback, and production impact.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
  - mcp1
---

# rico-release-captain

## Purpose
Coordinate the final verification before a Rico PR is handed to the owner for merge. Reports merge readiness, changed files, rollback plan, and production impact. No merge or deploy is done by this skill.

## When to use
- When a PR is ready for merge.
- After CI and review are complete.
- When the user asks "can we merge this" or "is it released".

## Inputs required
- PR number and branch.
- Base branch.
- Required reviews and owner approval status.
- Migration numbers, if any.

## Allowed actions
- Read PR diff, CI status, changed files, and review comments.
- Verify `origin/main` and PR branch commit status.
- Check Render/Vercel `/version` and `/health` endpoints.
- Confirm migration numbers do not collide.
- Document rollback and production impact.
- Report the next action and stop conditions.

## Forbidden actions
- Merge, push, deploy, or close issues.
- Mutate Neon, env vars, or production services.
- Approve a PR without explicit owner approval.
- Proceed when CI is not green or review is unresolved.
- Ignore migration-number collisions.

## Required output format
```markdown
### Release captain report for <PR>

- **PR / branch:** ...
- **Base branch:** ...
- **Changed files:** ...
- **CI status:** ...
- **Review status:** ...
- **Migrations:** ...
- **Rollback plan:** ...
- **Production impact:** ...
- **Status:** ready / not-ready / owner-approval-required
- **Next action:** ...
```

## Stop conditions
- CI is not green.
- A required review is missing or unresolved.
- Diff includes runtime, auth, billing, or migration changes without explicit owner approval.
- `origin/main` has moved ahead of the PR branch.
- Migration number collision.
- Production health check fails.

## Example prompt
"Rico release captain, check PR #973 for merge readiness and report the rollback plan."

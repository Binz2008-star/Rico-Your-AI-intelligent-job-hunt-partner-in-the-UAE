---
name: rico-local-qa
description: Run focused local QA for Rico Hunt. Validate frontend build, backend tests, and lint without touching production or live APIs.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# rico-local-qa

## Purpose
Run the cheapest, safest verification for the changed area. Catch TypeScript, import, and focused test failures before a PR is opened. Never touches live production or external APIs.

## When to use
- After code changes in a writer branch.
- Before asking for code review.
- When the user asks "is this working" or "run the tests".

## Inputs required
- Changed files or scope.
- Known pre-existing failures.
- Environment constraints (local or container without browser / live DB).

## Allowed actions
- `cd apps/web && npm run build`
- `cd apps/web && npm run lint` (if explicitly asked)
- `cd apps/web && npm run test` (focused unit tests)
- `python -m pytest <changed-area> -q` and the focused core tests
- `bash .claude/skills/run-rico/smoke.sh` (local smoke, when available)
- Report results and pre-existing failures.

## Forbidden actions
- Call live OpenAI, DeepSeek, HuggingFace, JSearch, JotForm, Telegram, Stripe, or Gmail.
- Write to live Neon or production DB.
- Run production smoke without explicit owner approval.
- Run the full test suite without explicit approval.
- Hide or silence pre-existing failures.

## Required output format
```markdown
### Local QA for <branch>

- **Commands run:** ...
- **Results:** pass/fail per command
- **New failures in changed area:** ...
- **Pre-existing failures:** ...
- **Recommendation:** proceed / fix / cannot-verify
- **Next action:** ...
```

## Stop conditions
- `npm run build` fails.
- A new failing test in the changed area appears.
- A command requires an external API and no key is set.
- A command attempts to write to production DB.

## Example prompt
"Rico local QA for this branch: run the frontend build and the focused onboarding tests."

# AGENTS.md

## Rico Agent Rules

This repository is Rico Hunt / Rico AI, a production UAE-focused AI career companion and job-search automation platform.

Follow `CLAUDE.md` for the full project architecture, routes, auth rules, safety rules, testing strategy, deployment context, and AI provider routing.

## Core Rules

1. Treat Rico as production code.
2. Prefer small, safe patches that preserve live production behavior.
3. Do not add pseudo-code, placeholder implementations, or unrelated rewrites.
4. One task = one clean session = one branch = one PR.
5. Do not mix bug fixes, features, refactors, docs, deploys, or billing changes in one PR.
6. Do not touch unrelated files.
7. Do not merge without explicit approval.
8. Do not deploy without explicit approval.
9. Do not mutate Neon or any production database without explicit approval.
10. Never expose secrets, cookies, tokens, passwords, or private environment values.

## Cost and Token Governance

Optimize for the owner's cost, time, and review control. Use the cheapest safe path that produces enough evidence to make a decision.

Do not launch any of the following unless the owner explicitly approves it first:

- multi-agent or fan-out reviews
- broad background investigations
- repeated verifier agents reading the same files
- long-running integration suites beyond the focused scope
- open-ended searches or exploratory refactors
- any workflow expected to use unusually high tokens, tool calls, or runtime

Before requesting approval for expensive work, state:

1. expected token or cost range
2. expected runtime
3. why the work is needed
4. cheaper alternative
5. concrete output expected

No approval means do not run it.

For PRs around 150 changed lines or less, use the lightweight path:

1. run focused tests first
2. do one focused review using an explicit checklist
3. fix confirmed low-risk issues only
4. report concise results
5. stop when enough evidence exists

Do not use multi-agent fan-out for small PRs.

Scale review cost to both diff size and blast radius, not to tool availability or mode flags. Deeper review may be appropriate for authentication, payments, billing, database migrations, public API contracts, cross-service deployment changes, or security-sensitive user data flows, but it still requires explicit owner approval first.

Stop and ask the owner before continuing when:

- the task becomes broader than approved
- tests exceed the expected runtime
- token or tool usage is becoming high
- findings are speculative rather than confirmed
- the same files are being re-read repeatedly by multiple agents

## Product Generalization Rule

Rico is a global SaaS product for all users. Smoke-test findings are evidence of product behavior; they are not product logic.

Every fix must be:

- global
- user-agnostic
- data-driven
- tested with synthetic users where possible

Agents must not special-case:

- one live user account
- one owner/test account
- one profile state
- one target-role list
- one saved search
- one session state
- one language path
- one provider result set
- one smoke-test dataset

For every investigation or fix, agents must identify the affected scope:

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

## Plan Mode Required

Use Plan Mode before any task involving:

- multiple files
- backend behavior
- frontend routing/layout behavior
- auth, cookies, JWT, sessions, or user isolation
- Neon/database queries, migrations, or cleanup
- Stripe/billing/subscriptions
- Render or Vercel deployment behavior
- AI routing, intent classification, LLM provider logic, or scoring
- Telegram/JotForm webhooks
- production smoke testing
- deletion of files
- broad refactors

Before coding risky work, report:

1. Current bug or goal
2. Exact files/functions involved
3. Smallest safe fix
4. Tests and smoke checks needed
5. Risks and rollback path

Wait for approval before coding if the change is risky.

## Direct Execution Allowed

Direct execution is allowed only for small, low-risk work such as:

- typo fixes
- small copy changes
- static asset additions
- README/rules documentation updates
- narrow single-file test additions
- one-line safe refactors with clear behavior preservation

## Testing Rules

- Run focused tests for the changed area.
- Do not call live OpenAI, DeepSeek, HuggingFace, Telegram, JotForm, Stripe, Gmail, or JSearch from unit tests.
- Do not write to live Neon from tests.
- For frontend changes, run `npm run build` from `apps/web`.
- For backend changes, run relevant `pytest` tests.
- For deployment-related work, verify `/version`, `/health`, and proxy health before smoke tests.

## Reporting Format

When work is done, report only:

- PR number and branch
- changed files
- exact behavior before and after
- tests run and results
- CI status
- known risks
- recommended next action

Every PR report must also include:

- affected scope (one user / one profile state / one language / one provider / all users)
- product-generalization confirmation (the fix is global and user-agnostic)
- whether synthetic users were used
- confirmation of no owner-account special-casing

## Production Safety

- Protected routes must derive identity from JWT, not request body `user_id`.
- Signup must always create normal users, never admin accounts.
- High-impact actions must respect approval mode.
- Auto-apply must not bypass `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.
- Do not reintroduce old parallel implementations that conflict with current `main`.

## Prohibited Without Explicit Owner Approval

- auto-merge
- production deploy
- rotating credentials
- changing payment or funding details
- exposing personal data
- adding bank details or secrets to the public repository

## Failure Rule

If the agent fails twice on the same task:

1. Stop.
2. Do not keep patching blindly.
3. Clear context or start a new clean session.
4. Rewrite the task prompt.
5. Restart from a clean branch/worktree.

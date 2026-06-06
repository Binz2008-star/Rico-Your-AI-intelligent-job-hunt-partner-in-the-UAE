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

## Production Safety

- Protected routes must derive identity from JWT, not request body `user_id`.
- Signup must always create normal users, never admin accounts.
- High-impact actions must respect approval mode.
- Auto-apply must not bypass `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.
- Do not reintroduce old parallel implementations that conflict with current `main`.

## Failure Rule

If the agent fails twice on the same task:

1. Stop.
2. Do not keep patching blindly.
3. Clear context or start a new clean session.
4. Rewrite the task prompt.
5. Restart from a clean branch/worktree.

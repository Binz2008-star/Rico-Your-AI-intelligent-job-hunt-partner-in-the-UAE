# AGENTS.md

## Mandatory Cross-Session Coordination Gate

Before planning, editing, testing, creating a branch, or opening a PR:

1. Read `AI_WORKSPACE/PROJECT_STATUS.md`.
2. Read `AI_WORKSPACE/START_HERE.md`.
3. Verify live GitHub `main`, open PRs, and the exact active PR head.
4. Read the active `AI_WORKSPACE/TASKS.md` entry and latest handoff.
5. Declare exactly one role: **WRITER**, **REVIEWER**, **RELEASE**, or **IDLE**.
6. For the full read order and per-agent-name responsibilities this gate summarizes, see `AI_WORKSPACE/OPERATING_RULES.md` ("Session Boot Sequence") and `AI_WORKSPACE/AGENT_OPERATING_MODEL.md` (per-agent role and scope boundaries, including Devin and Lovable). If those documents and this gate ever disagree on read order, `OPERATING_RULES.md` is canonical — report the drift instead of silently picking one.

Rules:

- `PROJECT_STATUS.md` contains the current execution lock.
- One writer per branch.
- If an active PR already exists for the objective, do not create a competing branch or implementation.
- Other Claude sessions default to REVIEWER or IDLE.
- Windsurf must not edit a Claude-owned branch unless ownership is explicitly handed over.
- Codex reviews; it does not become a second implementation owner.
- Devin and Lovable follow the role and scope boundaries in `AI_WORKSPACE/AGENT_OPERATING_MODEL.md`. Production-scoped work requires explicit owner assignment and an approved branch.
- If live state conflicts with workspace docs, stop and report the conflict instead of guessing.
- Old handoffs and chat summaries are historical context, not current permission to resume work.

## Continuity and Handoff Gate

Mandatory for every agent, every session, regardless of tool. If you notice you may hit a token, context, tool-call, usage, or time limit before the current task is done, stop expanding scope immediately and record state before doing anything else — documenting the handoff outranks continuing implementation once this triggers.

- The handoff format is the existing Continuity Block in `AI_WORKSPACE/TASKS.md` — do not invent a parallel format or document type.
- Update the task's existing Continuity Block in place; never duplicate the task entry.
- If the task is not `done`/`verified`, also add or update a dated `AI_WORKSPACE/HANDOFFS/<date>-<topic>.md` carrying the same block.
- Record: objective, branch, PR number, head SHA, files inspected/changed, tests run and results, exact status, what remains unfinished, risks/blockers, the exact next recommended step, what must not be touched, whether there are uncommitted changes, and any deploy/CI/Neon/Vercel state still to check.
- A handoff must be understandable from repository files alone — never write one that only makes sense with this conversation's hidden context.
- This does not replace `START_HERE.md`'s end-of-task Continuity Gate; it adds an explicit "stop and record now" trigger for approaching a limit mid-task. Full detail: `AI_WORKSPACE/AGENT_OPERATING_MODEL.md` → "Session continuity / limit-approach handoff".

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

This expands CLAUDE.md's Cost Optimization Rules with agent-coordination specifics below. CLAUDE.md mirrors and summarizes the canonical `AI_WORKSPACE` rules; if they conflict, `AI_WORKSPACE` is authoritative and the drift must be reported.

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

This mirrors `CLAUDE.md`'s Product Generalization Rule and `AI_WORKSPACE/OPERATING_RULES.md`'s copy. CLAUDE.md mirrors and summarizes the canonical `AI_WORKSPACE` rules; if they conflict, `AI_WORKSPACE/OPERATING_RULES.md` is authoritative and the drift must be reported.

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

This applies whenever you hold the WRITER role. REVIEWER, RELEASE, and IDLE sessions do not write code, so this gate does not trigger for them.

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

Every PR must also carry the `AI_WORKSPACE/PR_CHECKLIST.md` checklist filled in. For changes touching Rico's behavior, intent routing, tools, attachments, or job search, fill in its "Rico product gate" section too (see `AI_WORKSPACE/PR_QUALITY_GATE_RULES.md` → "Rico Product Behavior Gate" and `AI_WORKSPACE/RICO_EXECUTION_PRINCIPLES.md`).

## Production Safety

- Protected routes must derive identity from JWT, not request body `user_id`.
- Signup must always create normal users, never admin accounts.
- High-impact actions must respect approval mode.
- Auto-apply must not bypass `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.
- Do not reintroduce old parallel implementations that conflict with current `main`.

## Landing Page Production Freeze

### Incident

PR #866 changed `apps/web/app/page.tsx` to render `LandingPageV3` as the production homepage. The new design did not pass the owner's live review, so PR #870 reverted the change to restore `LandingPageV2`.

### Rule

Until the owner explicitly lifts this freeze, **no agent may change `apps/web/app/page.tsx` to swap the production landing component** (`LandingPageV2`, `LandingPageV3`, or any successor) without explicit owner approval.

Any new landing design or homepage variant must follow this path:

1. Land in `design-handoffs/` as a prototype package.
2. Move to `/design-gallery` as a reviewable draft if approved.
3. Run browser smoke tests against the gallery variant.
4. Receive explicit owner approval.
5. Only then create a separate, minimal production PR that swaps the landing component.

This rule applies to all direct or indirect changes that replace the component rendered on `/`. It does not apply to copy-only or bug-fix changes inside the current production component.

## Prohibited Without Explicit Owner Approval

- auto-merge
- production deploy
- rotating credentials
- changing payment or funding details
- exposing personal data
- adding bank details or secrets to the public repository
- swapping the production landing page component (`apps/web/app/page.tsx`)

## Failure Rule

If the agent fails twice on the same task:

1. Stop.
2. Do not keep patching blindly.
3. Clear context or start a new clean session.
4. Rewrite the task prompt.
5. Restart from a clean branch/worktree.

Before restarting, follow the Continuity and Handoff Gate above and record what was tried and why it failed — a clean restart without a handoff is how the next session repeats the same failed attempt.

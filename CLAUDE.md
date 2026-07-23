# CLAUDE.md

## Project Context

This repository is Rico Hunt / Rico AI: a UAE-focused AI career companion and job-search automation platform.

Treat this as production code. Do not add pseudo-code, placeholder implementations, or unrelated rewrites. Prefer small, safe patches that preserve the live production behavior.

## Cost Optimization Rules (base directive — always in force)

Powerful model or not, optimize for the owner's cost.

Do NOT launch multi-agent workflows, broad background reviews, or repeated
verifier agents unless the owner explicitly approves the estimated cost first.

For every task, use the cheapest safe path:

- focused tests first
- one focused review pass
- concise report
- stop when enough evidence exists

If a deep review seems needed, ask first and give:

1. expected token range
2. expected dollar cost
3. reason
4. cheaper alternative

No approval = do not run it.

## AI Workspace Entry Point

For new Rico work sessions, start from `AI_WORKSPACE/START_HERE.md`.

Use the AI workspace as the shared source of truth for tasks, decisions, handoffs, evaluations, and prompt contracts. Do not rely on chat memory when the repository already contains current workspace files.

Multiple AI agents (Claude, Windsurf, Codex, Devin, Lovable) work in this repository. `AGENTS.md` defines the mandatory cross-session coordination gate: read `AI_WORKSPACE/PROJECT_STATUS.md` (the current execution lock) before planning or editing, one writer per branch, and never create a competing branch when an active PR already exists for the objective.

## Rico Operating Rules

Before planning, coding, reviewing, merging, or verifying production, read `AI_WORKSPACE/OPERATING_RULES.md`.

That file is the canonical operational checklist for:

- GitHub PR audit and merge policy
- Render backend deployment verification
- Vercel frontend verification
- Neon migration safety
- production smoke testing
- AI agent roles and status reporting

If `CLAUDE.md`, `CURRENT_STATE.md`, `TASKS.md`, and live GitHub/deploy state disagree, stop and report the conflict instead of guessing.

## Product Generalization Rule

Rico is a global SaaS product for all users. Smoke-test findings are evidence of product behavior; they are not product logic.

Every fix must be global, user-agnostic, and data-driven.

Do not special-case:

- one live user account
- one owner/test account
- one profile state
- one saved target-role list
- one saved search
- one session state
- one language path
- one provider result set
- one smoke-test dataset

For every investigation or fix, identify whether the issue affects:

1. one user only
2. one profile state
3. one language or locale
4. one provider or integration
5. all users

Fix the underlying product/system behavior, not one account.

If a bug is discovered through a smoke-test account, state:

> The smoke-test account exposed the bug, but the fix is global.

If a proposed fix only improves one live account or one smoke-test dataset, stop and report it as invalid.

Tests must use synthetic users and synthetic profile data unless the owner explicitly approves a production smoke check.

Where relevant, cover:

- user with a complete profile
- user without a profile or CV
- guest/public session
- Arabic input
- English input
- multiple unrelated target roles, not only the role that exposed the bug

## Current Live Stack

- Frontend: Next.js 14 / TypeScript / Tailwind in `apps/web`
- Backend: Python / FastAPI in `src/api`
- Database: Neon PostgreSQL
- Backend deployment: Render
- Frontend deployment: Vercel
- Job search API: JSearch / RapidAPI
- Notifications: Telegram
- Intake fallback: Jotform
- AI providers: OpenAI (gpt-4.1-mini) → DeepSeek (deepseek-v4-flash) → HuggingFace → Keyword Fallback

## Production Source of Truth

The live stack is already deployed:

- `ricohunt.com` frontend on Vercel
- Render backend at `rico-job-automation-api.onrender.com`
- Neon DB connected
- `/chat` public page live
- `/signup` self-registration live
- CORS, cookie secure mode, reset URL, and JSearch key are configured in production

Do not reintroduce older parallel implementations that conflict with current `main`.

## Architecture Overview

The repo combines three layers:

1. Legacy job automation pipeline
   - job fetching
   - filtering
   - scoring
   - application tracking
   - Telegram notifications
   - dashboard/report generation
   - follow-up reminders

2. Rico AI backend
   - FastAPI app
   - chat routes
   - public chat
   - CV upload and parsing
   - onboarding
   - auth
   - user isolation
   - Jotform and Telegram webhooks
   - OpenAI/DeepSeek/HF/Keyword fallback behavior

3. SaaS frontend
   - public landing page
   - `/chat`
   - `/signup`
   - `/login`
   - `/forgot-password`
   - `/dashboard`
   - `/jobs`
   - `/applications`
   - `/profile`
   - `/settings`
   - `/onboarding`

## Key Backend Files

- `src/api/app.py` — main FastAPI app used by Render
- `src/api/auth.py` — login, logout, register, forgot/reset password, `/me`
- `src/api/deps.py` — JWT/current-user dependencies
- `src/api/rate_limit.py` — SlowAPI limits
- `src/api/routers/rico_chat.py` — Rico chat, public chat, CV upload, webhooks
- `src/api/routers/onboarding.py` — structured onboarding submit
- `src/api/routers/actions.py` — idempotent job actions (apply/save/skip/block/draft/why)
- `src/api/routers/agent.py` — natural-language chat with Rico agent
- `src/api/routers/pipeline.py` — pipeline status/trigger
- `src/rico_db.py` — Rico DB helper
- `src/rico_chat_api.py` — primary conversational layer (intent classification, role intelligence pipeline, structured response types)
- `src/rico_safety.py` — guardrails; blocks forged docs, unapproved applies, spam
- `src/agent/runtime.py` — central action dispatcher; idempotency, audit logging, dry-run
- `src/agent/registry/tool_registry.py` — declarative tool system
- More backend files (remaining routers, repository layer, webhook processors): `src/CLAUDE.md`.

## Key Frontend Files

- `apps/web/app/command/page.tsx` — public chat UI (primary chat surface; `/chat` redirects here)
- `apps/web/lib/api.ts` — canonical frontend API helper for auth/chat/CV/profile/onboarding
- More frontend files (auth pages, onboarding, service wrappers): `apps/web/CLAUDE.md`.

## Auth Rules

- Auth uses JWT in an `httpOnly` cookie.
- Public signup uses `POST /api/v1/auth/register`.
- Signup must force `role="user"` always.
- Signup creates an **unverified** normal user. It does **not** set an authenticated JWT
  cookie; instead it **clears any stale auth cookie** (`register()` calls `delete_cookie`) and
  returns `email_verification_required=true`.
- **Email verification is required before login** — `POST /api/v1/auth/login` rejects an
  unverified email; only a successful login sets the HTTP-only JWT cookie.
- Admin accounts must not be creatable by public request body fields.
- Protected routes must derive identity from JWT, not from request body `user_id`.

## Important API Routes

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/rico/chat`
- `GET /api/v1/rico/chat/sessions`
- `POST /api/v1/rico/chat/public`
- `POST /api/v1/rico/upload-cv`
- `GET /api/v1/rico/profile`
- `POST /api/v1/onboarding/submit`
- `POST /api/v1/rico/webhooks/jotform`
- `POST /api/v1/rico/webhooks/telegram`
- `POST /api/v1/rico/webhooks/github`
- `POST /api/v1/agent/chat`
- `POST /api/v1/actions/run`
- `GET /api/v1/pipeline/status`
- `POST /api/v1/pipeline/trigger`
- `GET /health`
- `GET /version`

## CV Upload

The live CV upload path is:

```text
apps/web/app/command/page.tsx or apps/web/app/onboarding/page.tsx
→ apps/web/lib/api.ts
→ /proxy/api/v1/rico/upload-cv
→ src/api/routers/rico_chat.py
```

## Public Chat Flow

```text
apps/web/app/command/page.tsx
→ sendChatPublic() in apps/web/lib/api.ts
→ /proxy/api/v1/rico/chat/public
→ src/api/routers/rico_chat.py
→ src/services/chat_service.py
```

The public chat endpoint is intentionally unauthenticated and session-based. It must stay rate-limited and must prefix anonymous users as public sessions so they cannot collide with real JWT-authenticated users.

## Commands

```bash
# Backend API
python -m uvicorn src.api.app:app --reload --port 8000

# Legacy/Rico daily pipeline
python -m src.run_daily

# Backend tests (pytest.ini sets testpaths=tests, asyncio_mode=strict)
python -m pytest tests/ -v --tb=short
python -m pytest tests/test_agent.py tests/test_agent_runtime.py tests/test_jotform_webhook.py tests/test_jwt_user_isolation.py tests/test_onboarding_state.py -q

# Single backend test
python -m pytest tests/test_agent.py::test_name -v

# Frontend
cd apps/web
npm run dev
npm run build
npm run lint

# Frontend unit tests (Vitest, jsdom; tests live in apps/web/__tests__/)
cd apps/web
npm run test                                  # full suite (CI-required gate)
npx vitest run __tests__/auth-guard.test.tsx  # single file

# Frontend E2E (Playwright specs in apps/web/e2e/; excluded from Vitest)
cd apps/web
npx playwright test
```

## Required Env Vars

Full list with rationale/incident history: `docs/env-vars.md`. Summary (backend/Render unless noted):

- `DATABASE_URL`, `JWT_SECRET`, `JWT_TTL_HOURS`, `COOKIE_SECURE`, `RESET_BASE_URL`, `CORS_ORIGINS` — core auth/DB/CORS config
- `OPENAI_API_KEY`, `OPEN_AI_API`, `RICO_OPENAI_MODEL`, `RICO_AI_PROVIDER`, `DEEPSEEK_API_KEY`, `HF_TOKEN` — AI provider routing (see below)
- `JSEARCH_API_KEY`, `RAPIDAPI_KEY` — job search API
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — user-facing job/career notifications
- `TELEGRAM_ADMIN_CHAT_ID`, `TELEGRAM_DEV_CHAT_ID`, `TELEGRAM_ADMIN_BOT_TOKEN` — admin/dev technical alerts only (never falls back to user chat)
- `JOTFORM_API_KEY`, `JOTFORM_FORM_ID`, `JOTFORM_WEBHOOK_SECRET` — Jotform intake
- `WHATSAPP_SUBSCRIPTIONS_ENABLED`, `WHATSAPP_SUBSCRIPTION_NUMBER` — assisted subscription channel; never grants entitlement by itself, fail-closed default off
- `RICO_ENABLE_AUTO_APPLY`, `RICO_INTERACTIVE_APPLY`, `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`, `RICO_TELEGRAM_PUBLIC_ALERTS` — apply/approval safety switches
- `RICO_ENABLE_USER_TELEGRAM_ALERTS`, `RICO_ENABLE_SCHEDULED_SEARCHES`, `RICO_ENABLE_ANALYTICS_PURGE` — scheduled-job kill switches, all fail-closed (default `false`)
- `RICO_CRON_SECRET` — shared secret guarding cron-only pipeline endpoints
- `GUEST_CAPABILITY_SECRET` — dedicated guest-session signing key; required in production, fails closed if missing; never share with `JWT_SECRET`
- `RICO_REDIS_URL`, `REDIS_URL` — rate limiting backend
- `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_TO` — outbound email

Frontend/Vercel: `NEXT_PUBLIC_RICO_API=https://rico-job-automation-api.onrender.com`

Do not invent new env var names unless the code is being intentionally migrated.

## Database Migrations

- Schema migrations are numbered SQL files in `migrations/` (e.g. `034_drop_redundant_indexes.sql`). New migrations continue the numeric sequence.
- Migration drift is checked by `scripts/check_migration_drift.py` (workflow `migration-drift-check.yml`) and applied through `scripts/apply_migration_drift.py` (workflow `apply-migration-drift.yml`) — not by hand.
- Never mutate the live Neon database directly. Neon migration safety rules are in `AI_WORKSPACE/OPERATING_RULES.md`.

## Testing Strategy

- Backend tests use `pytest`.
- Route tests should use FastAPI `TestClient` or `httpx` only where the existing tests already do.
- Auth tests should generate/mock JWTs through project helpers; do not hardcode real credentials.
- Unit tests must not write to the live Neon database.
- Prefer mocks/fixtures for repositories and external services.
- Do not call live OpenAI, Hugging Face, Telegram, Jotform, Gmail, or JSearch APIs in unit tests.
- For frontend changes, run `npm run build` AND `npm run test` in `apps/web` — both are required CI gates in `qa-tests.yml`.
- Frontend unit tests are Vitest + Testing Library in `apps/web/__tests__/`; Playwright E2E specs live in `apps/web/e2e/` and are excluded from the Vitest run.
- CI (`qa-tests.yml`) runs backend pytest with fake env values and `REDIS_URL` unset (SlowAPI falls back to `memory://` — with a real `REDIS_URL` absent, rate-limited routes would 500). Match that setup when reproducing CI failures locally.
- For Daily Job Bot changes, run `python -m py_compile src/run_daily.py` before running the workflow.

## AI Provider Routing

- Active provider is controlled by `RICO_AI_PROVIDER` env var (Render).
- Current production provider: `deepseek` (`DEEPSEEK_API_KEY` set on Render).
- Runtime fallback chain when `RICO_AI_PROVIDER=deepseek`:
  `DeepSeek -> HuggingFace (if hf_available=true) -> keyword/templated fallback`
- OpenAI is NOT currently the primary provider despite `OPENAI_API_KEY` being present.
  Switch to OpenAI by setting `RICO_AI_PROVIDER=openai` on Render.
- Health semantics (as of `6645d05`):
  - `*_key_present` = env var exists, independent of active provider
  - `ready_for_*` = that provider is selected AND key is present
  - `hf_available` = HF token present (legacy field, same as `hf_key_present`)
- Do not add a provider without updating: routing logic in `src/rico_openai_agent.py`,
  health report in `src/rico_env.py`, `RicoEnvReport` dataclass, and this section.
- Do not set `openai_available`, `hf_available`, `provider`, `ready_for_hf`,
  or `response_source` as static Render env vars. These are runtime-computed fields.

## Landing Page Production Freeze

Do not change `apps/web/app/page.tsx` to swap the production landing component without explicit owner approval (copy-only/bug-fix changes inside the current component are fine). Canonical rule + incident history: `AGENTS.md` → "Landing Page Production Freeze". Working-context copy: `apps/web/CLAUDE.md`.

## Safety Layer Rules

- `src/rico_safety.py` guardrails are non-negotiable. Do not add routes or tool calls that bypass safety checks.
- High-impact actions (apply, send message, mutate preferences) require explicit user confirmation when approval mode is enabled.
- `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is the default; any code path that bypasses it for apply actions is a safety violation. Implementation detail (idempotency key scheme, singleton dispatcher): `src/CLAUDE.md` → "Agent Runtime Rules".
- Telegram notification audience separation (user-facing vs. admin/dev channels) is non-negotiable — `admin_*` alerts must never reach a user chat. Full rules: `src/CLAUDE.md` → "Telegram Notification Audience Rules".

## Full Architecture Reference

See `docs/architecture.md` for system diagrams, data flow, scoring algorithm, and scalability roadmap. Do not duplicate that content here — keep CLAUDE.md focused on operational rules and file locations.

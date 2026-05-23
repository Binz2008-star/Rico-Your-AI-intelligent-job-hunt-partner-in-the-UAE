# CLAUDE.md

## Project Context

This repository is Rico Hunt / Rico AI: a UAE-focused AI career companion and job-search automation platform.

Treat this as production code. Do not add pseudo-code, placeholder implementations, or unrelated rewrites. Prefer small, safe patches that preserve the live production behavior.

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
- `src/api/routers/jobs.py` — jobs API
- `src/api/routers/applications.py` — applications API
- `src/api/routers/settings.py` — settings API
- `src/api/routers/stats.py` — stats/dashboard API
- `src/api/routers/user.py` — profile retrieval/update
- `src/api/routers/actions.py` — idempotent job actions (apply/save/skip/block/draft/why)
- `src/api/routers/agent.py` — natural-language chat with Rico agent
- `src/api/routers/pipeline.py` — pipeline status/trigger
- `src/rico_jotform_webhook.py` — Jotform processing and idempotency
- `src/rico_telegram_webhook.py` — Telegram webhook processing
- `src/rico_db.py` — Rico DB helper
- `src/rico_chat_api.py` — primary conversational layer (intent classification, role intelligence pipeline, structured response types)
- `src/rico_safety.py` — guardrails; blocks forged docs, unapproved applies, spam
- `src/rico_repo_adapter.py` — bridge between agent layer and legacy pipeline
- `src/agent/runtime.py` — central action dispatcher; idempotency, audit logging, dry-run
- `src/agent/registry/tool_registry.py` — declarative tool system
- `src/services/chat_service.py` — chat business logic
- `src/db.py` — DB connection layer
- `src/repositories/*` — repository layer
- `src/run_daily.py` — Daily Job Bot / intelligence pipeline

## Key Frontend Files

- `apps/web/app/chat/page.tsx` — public chat UI
- `apps/web/app/signup/page.tsx` — self-signup UI
- `apps/web/app/login/page.tsx` — login UI
- `apps/web/app/onboarding/page.tsx` — guided onboarding / CV-first flow
- `apps/web/lib/api.ts` — canonical frontend API helper for auth/chat/CV/profile/onboarding
- `apps/web/services/*` — older service wrappers (dashboard stats, jobs, applications, settings, health)

## Auth Rules

- Auth uses JWT in an `httpOnly` cookie.
- Public signup uses `POST /api/v1/auth/register`.
- Signup must force `role="user"` always.
- Signup auto-logs in by setting the JWT cookie.
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
- `POST /api/v1/rico/chat/public`
- `POST /api/v1/rico/upload-cv`
- `GET /api/v1/rico/profile`
- `POST /api/v1/onboarding/submit`
- `POST /api/v1/rico/webhooks/jotform`
- `POST /api/v1/rico/webhooks/telegram`
- `POST /api/v1/rico/webhooks/github`
- `POST /api/v1/agent/chat`
- `POST /api/v1/actions/{action}`
- `GET /api/v1/pipeline/status`
- `POST /api/v1/pipeline/trigger`
- `GET /api/v1/user/profile`
- `GET /health`
- `GET /version`

## Jotform Idempotency

Current `main` already has stronger DB-backed Jotform idempotency:

- `db.register_webhook_event(...)` before processing
- `db.mark_webhook_event_processed(...)` after processing

Do not add a parallel `webhook_events_repo` idempotency layer unless intentionally refactoring the current DB-backed implementation.

## CV Upload

The live CV upload path is:

```text
apps/web/app/chat/page.tsx or apps/web/app/onboarding/page.tsx
→ apps/web/lib/api.ts
→ /proxy/api/v1/rico/upload-cv
→ src/api/routers/rico_chat.py
```

## Public Chat Flow

```text
apps/web/app/chat/page.tsx
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

# Backend tests
python -m pytest tests/ -v --tb=short
python -m pytest tests/test_agent.py tests/test_agent_runtime.py tests/test_jotform_webhook.py tests/test_jwt_user_isolation.py tests/test_onboarding_state.py -q

# Frontend
cd apps/web
npm run dev
npm run build
npm run lint
```

## Required Env Vars

### Backend / Render

```env
DATABASE_URL=
JWT_SECRET=
JWT_TTL_HOURS=
COOKIE_SECURE=true
RESET_BASE_URL=https://ricohunt.com

CORS_ORIGINS=*

OPENAI_API_KEY=
OPEN_AI_API=
RICO_OPENAI_MODEL=
RICO_AI_PROVIDER=
DEEPSEEK_API_KEY=
HF_TOKEN=

JSEARCH_API_KEY=
RAPIDAPI_KEY=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

JOTFORM_API_KEY=
JOTFORM_FORM_ID=
JOTFORM_WEBHOOK_SECRET=

RICO_ENABLE_AUTO_APPLY=false
RICO_INTERACTIVE_APPLY=false
RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true
RICO_TELEGRAM_PUBLIC_ALERTS=true

RICO_REDIS_URL=
REDIS_URL=

EMAIL_USER=
EMAIL_PASS=
EMAIL_TO=
```

### Frontend / Vercel

```env
NEXT_PUBLIC_RICO_API=https://rico-job-automation-api.onrender.com
```

Do not invent new env var names unless the code is being intentionally migrated.

## Async I/O Patterns

- `src/cv_parser.py` is synchronous by design (CPU/IO-bound parsing operations).
- When calling CV parser from FastAPI routers, wrap in `run_in_executor` to avoid blocking the event loop:

  ```python
  import asyncio
  loop = asyncio.get_event_loop()
  parsed = await loop.run_in_executor(None, parser.parse_bytes, raw_bytes, filename)
  ```

- Do not make CVParser itself async — the router is the async boundary.

## Testing Strategy

- Backend tests use `pytest`.
- Route tests should use FastAPI `TestClient` or `httpx` only where the existing tests already do.
- Auth tests should generate/mock JWTs through project helpers; do not hardcode real credentials.
- Unit tests must not write to the live Neon database.
- Prefer mocks/fixtures for repositories and external services.
- Do not call live OpenAI, Hugging Face, Telegram, Jotform, Gmail, or JSearch APIs in unit tests.
- For frontend changes, run `npm run build` in `apps/web`.
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

## Migration Status: `lib/client.ts` → `lib/api.ts`

Migration is complete. `apps/web/lib/client.ts` has been deleted. All API calls now go through `apps/web/lib/api.ts`. Do not reintroduce `lib/client.ts`.

## Agent Runtime Rules

- `agent_runtime` in `src/agent/runtime.py` is a module-level singleton. Do not reinstantiate it.
- All job actions (apply/save/skip/block/draft/why/remind) MUST go through `agent_runtime.handle_action()` — never call repo layer directly from routers for actions.
- Idempotency key: MD5 of `user_id:action:job_key`. Do not change this scheme without updating the audit log schema.
- `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is the default. Any code path that bypasses this for apply actions is a safety violation.

## Safety Layer Rules

- `src/rico_safety.py` guardrails are non-negotiable. Do not add routes or tool calls that bypass safety checks.
- High-impact actions (apply, send message, mutate preferences) require explicit user confirmation when approval mode is enabled.

## Full Architecture Reference

See `docs/architecture.md` for system diagrams, data flow, scoring algorithm, and scalability roadmap. Do not duplicate that content here — keep CLAUDE.md focused on operational rules and file locations.

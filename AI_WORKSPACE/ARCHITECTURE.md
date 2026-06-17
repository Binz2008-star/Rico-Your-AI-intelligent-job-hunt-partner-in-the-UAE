# Architecture

## Current live stack

- Frontend: Next.js 14 / TypeScript / Tailwind in `apps/web`
- Backend: Python / FastAPI in `src/api`
- Database: Neon PostgreSQL
- Backend deployment: Render
- Frontend deployment: Vercel
- Job search API: JSearch / RapidAPI
- Notifications: Telegram
- Intake fallback: Jotform
- AI providers: OpenAI -> DeepSeek -> HuggingFace -> Keyword Fallback

## Current high-level flow

```text
apps/web frontend
        ↓
FastAPI app in src/api
        ↓
API routers + services
        ↓
Rico chat / jobs / applications / profile / settings / actions
        ↓
Rico conversational layer + agent runtime + legacy job pipeline
        ↓
Neon PostgreSQL + Telegram + dashboard/report output
```

## Repository layers

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
   - provider fallback behavior

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

## Key backend files

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
- `src/api/routers/actions.py` — idempotent job actions
- `src/api/routers/agent.py` — natural-language chat with Rico agent
- `src/api/routers/pipeline.py` — pipeline status/trigger
- `src/rico_jotform_webhook.py` — Jotform processing and idempotency
- `src/rico_telegram_webhook.py` — Telegram webhook processing
- `src/rico_db.py` — Rico DB helper
- `src/rico_chat_api.py` — primary conversational layer
- `src/rico_safety.py` — guardrails
- `src/rico_repo_adapter.py` — bridge between agent layer and legacy pipeline
- `src/agent/runtime.py` — central action dispatcher
- `src/agent/registry/tool_registry.py` — declarative tool system
- `src/services/chat_service.py` — chat business logic
- `src/db.py` — DB connection layer
- `src/repositories/*` — repository layer
- `src/run_daily.py` — daily job bot / intelligence pipeline

## Key frontend files

- `apps/web/app/chat/page.tsx` — public chat UI
- `apps/web/app/signup/page.tsx` — self-signup UI
- `apps/web/app/login/page.tsx` — login UI
- `apps/web/app/onboarding/page.tsx` — guided onboarding / CV-first flow
- `apps/web/lib/api.ts` — canonical frontend API helper
- `apps/web/services/*` — older service wrappers

## Architecture rules

- Preserve the existing Rico architecture unless the task explicitly approves changing it.
- Do not add parallel implementations that conflict with current `main`.
- Keep protected routes based on JWT-derived identity, not request-body `user_id`.
- Keep user-impacting actions permission-based.
- Do not claim production readiness without tests, deployment verification, and smoke evidence.

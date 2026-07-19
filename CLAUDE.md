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

- `apps/web/app/command/page.tsx` — public chat UI (primary chat surface; `/chat` redirects here)
- `apps/web/app/signup/page.tsx` — self-signup UI
- `apps/web/app/login/page.tsx` — login UI
- `apps/web/app/onboarding/page.tsx` — guided onboarding / CV-first flow
- `apps/web/lib/api.ts` — canonical frontend API helper for auth/chat/CV/profile/onboarding
- `apps/web/services/*` — older service wrappers (dashboard stats, jobs, applications, settings, health)

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

## Jotform Idempotency

Current `main` already has stronger DB-backed Jotform idempotency:

- `db.register_webhook_event(...)` before processing
- `db.mark_webhook_event_processed(...)` after processing

Do not add a parallel `webhook_events_repo` idempotency layer unless intentionally refactoring the current DB-backed implementation.

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

# User-facing bot/chat — job & career notifications only
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Admin/dev channel — technical notifications only (CI, deploy, errors,
# provider quota). admin_* alerts route here and never fall back to the user
# chat; if unset, admin alerts are logged and dropped. See
# src/services/notification_router.py.
TELEGRAM_ADMIN_CHAT_ID=
TELEGRAM_DEV_CHAT_ID=
TELEGRAM_ADMIN_BOT_TOKEN=

JOTFORM_API_KEY=
JOTFORM_FORM_ID=
JOTFORM_WEBHOOK_SECRET=

# WhatsApp-assisted subscription channel (DEC-20260719-003). ASSISTED, not a
# payment processor: creating a request/opening WhatsApp NEVER grants
# entitlement — activation only via POST /api/v1/admin/subscriptions/activate
# after owner payment verification. Fail-closed: flag default false; number
# must be valid E.164 or the channel stays off. Paddle is unaffected.
WHATSAPP_SUBSCRIPTIONS_ENABLED=false
WHATSAPP_SUBSCRIPTION_NUMBER=

RICO_ENABLE_AUTO_APPLY=false
RICO_INTERACTIVE_APPLY=false
RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true
RICO_TELEGRAM_PUBLIC_ALERTS=true

# Global kill switch for scheduled PER-USER Telegram job alerts (#1082).
# Default OFF (fail-closed) while consent enforcement is remediated; distinct
# from RICO_TELEGRAM_PUBLIC_ALERTS (admin/public bot). Set true to re-enable
# the daily per-user roster sender.
RICO_ENABLE_USER_TELEGRAM_ALERTS=false

# Shared secret for the cron-only follow-up reminders sweep
# (POST /api/v1/pipeline/reminders, X-Cron-Secret header). Issue #355.
RICO_CRON_SECRET=

# Kill switch for the scheduled analytics_events retention purge
# (POST /api/v1/pipeline/analytics-purge; workflow analytics-purge.yml).
# Default OFF (fail-closed) — disabled runs are a 200 no-op. The 180-day
# window is the RETENTION_DAYS code constant in
# src/repositories/analytics_events_repo.py — never an env var, never an
# API input. See DEC-20260719-001.
RICO_ENABLE_ANALYTICS_PURGE=false

# Guest-session capability signing key (#1070). DEDICATED secret — never
# derived from or shared with JWT_SECRET. Signs the versioned guest capability
# token (rico_guest_proof cookie) that carries the server-minted guest SID.
# REQUIRED in production: missing value fails closed (guest surfaces return
# 503; nothing is minted or validated). Rotation: replacing the value
# invalidates every outstanding guest capability — active guests transparently
# restart as fresh anonymous sessions on their next request. Generate with:
# python3 -c "import secrets; print(secrets.token_hex(32))"
GUEST_CAPABILITY_SECRET=

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

## Telegram Notification Audience Rules

Telegram notifications are split by audience in `src/services/notification_router.py`.

- User-facing chat (`TELEGRAM_CHAT_ID` / per-user `telegram_chat_id`) is for
  job/career notifications ONLY: `user_job`, `user_account`.
- Admin/dev chat (`TELEGRAM_ADMIN_CHAT_ID` → `TELEGRAM_DEV_CHAT_ID`) is for
  technical alerts ONLY: `admin_ci`, `admin_deploy`, `admin_error`, `admin_provider`
  (CI/test status, deploy status, errors/logs, AI-provider quota/health).
- `admin_*` notifications MUST NEVER be delivered to a user chat. If no
  admin/dev channel is configured, admin alerts are logged and dropped — never
  redirected to the user chat. Use `send_admin_notification()` /
  `send_notification(..., notification_type=...)`; do not send technical alerts
  through `send_telegram_message()`/`send_telegram_to_user()` directly.
- GitHub Actions admin alerts (`error-notifications.yml`, runner/session and
  apply-ops alerts in `daily.yml` / `manual-naukrigulf-apply.yml`) target the
  admin/dev secret and are skipped when it is unset.

## Full Architecture Reference

See `docs/architecture.md` for system diagrams, data flow, scoring algorithm, and scalability roadmap. Do not duplicate that content here — keep CLAUDE.md focused on operational rules and file locations.

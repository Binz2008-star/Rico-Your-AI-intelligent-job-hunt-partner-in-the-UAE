# src/ — Backend Implementation Detail

Scoped to the Python/FastAPI backend (`src/`, including `src/api/`). Loaded on demand when working in this directory. Root `CLAUDE.md` covers the cross-tool contract (auth rules, safety rules, AI provider routing, testing strategy) that every agent tool must see; this file covers backend-internal detail that only matters when you're actually editing backend code.

## Additional Key Backend Files

Beyond the singletons/dispatch points listed in root `CLAUDE.md`:

- `src/api/routers/jobs.py`, `applications.py`, `settings.py`, `stats.py`, `user.py` — CRUD-style routers for their respective domains
- `src/api/routers/subscription.py`, `paddle_billing.py`, `billing_whatsapp.py`, `admin_subscriptions.py` — billing/entitlements (Paddle + WhatsApp-assisted channel; activation is admin-only)
- `src/api/routers/apply_queue.py` — apply queue management
- `src/api/routers/link_verification.py` — job apply-link verification (#354)
- (the full router set lives in `src/api/routers/` — more routers exist than are listed here)
- `src/rico_jotform_webhook.py` — Jotform processing and idempotency
- `src/rico_telegram_webhook.py` — Telegram webhook processing
- `src/rico_repo_adapter.py` — bridge between agent layer and legacy pipeline
- `src/services/chat_service.py` — chat business logic
- `src/db.py` — DB connection layer
- `src/repositories/*` — repository layer
- `src/run_daily.py` — Daily Job Bot / intelligence pipeline

## Jotform Idempotency

Current `main` already has stronger DB-backed Jotform idempotency:

- `db.register_webhook_event(...)` before processing
- `db.mark_webhook_event_processed(...)` after processing

Do not add a parallel `webhook_events_repo` idempotency layer unless intentionally refactoring the current DB-backed implementation.

## Async I/O Patterns

- `src/cv_parser.py` is synchronous by design (CPU/IO-bound parsing operations).
- When calling CV parser from FastAPI routers, wrap in `run_in_executor` to avoid blocking the event loop:

  ```python
  import asyncio
  loop = asyncio.get_event_loop()
  parsed = await loop.run_in_executor(None, parser.parse_bytes, raw_bytes, filename)
  ```

- Do not make CVParser itself async — the router is the async boundary.

## Agent Runtime Rules

- `agent_runtime` in `src/agent/runtime.py` is a module-level singleton. Do not reinstantiate it.
- All job actions (apply/save/skip/block/draft/why/remind) MUST go through `agent_runtime.handle_action()` — never call repo layer directly from routers for actions.
- Idempotency key: MD5 of `user_id:action:job_key`. Do not change this scheme without updating the audit log schema.
- `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is the default; this is also stated as a hard safety rule in root `CLAUDE.md` and `AGENTS.md` — any code path that bypasses it for apply actions is a safety violation, not just an implementation detail.

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

---
name: check-rico-webhooks
description: Read-only audit of Rico Hunt Jotform and Telegram webhooks. Verify idempotency, signature checks, and command isolation without sending live messages.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-webhooks

Read-only audit of Rico Hunt webhooks. This skill **never sends live Telegram messages or calls JotForm APIs**. It only inspects code and configuration.

## What it verifies

1. Jotform webhook uses `db.register_webhook_event()` before processing and `db.mark_webhook_event_processed()` after.
2. Jotform signature verification uses `JOTFORM_WEBHOOK_SECRET`.
3. Telegram webhook does not expose admin commands to users and routes admin alerts to the admin channel only.
4. Public Telegram commands are limited to safe, user-facing actions.
5. Webhook routes are unauthenticated where required and rate-limited.

## Quick checks

```bash
# Idempotency
grep -n "register_webhook_event\|mark_webhook_event_processed" src/rico_jotform_webhook.py

# Signature verification
grep -n "JOTFORM_WEBHOOK_SECRET\|signature\|hmac" src/rico_jotform_webhook.py

# Telegram admin vs user separation
grep -n "admin\|send_admin_notification\|TELEGRAM_ADMIN_CHAT_ID\|TELEGRAM_CHAT_ID" src/rico_telegram_webhook.py src/services/notification_router.py

# Webhook routes in FastAPI
grep -n "jotform\|telegram" src/api/routers/rico_chat.py src/api/app.py
```

## Files to read

- `src/rico_jotform_webhook.py` — Jotform processing and idempotency
- `src/rico_telegram_webhook.py` — Telegram command processing
- `src/services/notification_router.py` — audience routing rules
- `src/api/routers/rico_chat.py` — webhook route registration

## Safety constraints

- Do not send test messages to Telegram user or admin chats.
- Do not call JotForm APIs or submit test forms.
- Do not disable signature verification or idempotency checks.

# Environment Variables Reference

Full rationale and incident history for Rico's environment variables. `CLAUDE.md` keeps a short name + one-line purpose for each; this doc carries the "why" so CLAUDE.md stays lean. Do not invent new env var names here without also updating `CLAUDE.md`'s summary list.

## Backend / Render

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

# Kill switch for the scheduled saved-search sweep (#1249)
# (POST /api/v1/pipeline/scheduled-searches, X-Cron-Secret guarded).
# Default OFF (fail-closed): disabled runs are a no-op; ?dry_run=true
# evaluates matching without persisting anything. In-app delivery only —
# email job alerts stay behind RICO_ENABLE_EMAIL_ALERTS + per-user opt-in.
RICO_ENABLE_SCHEDULED_SEARCHES=false

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

# Owner account for the owner-only subscriber admin surface
# (/admin/subscribers UI, GET /api/v1/admin/subscribers[/summary]).
# Value is the immutable canonical users.id (BIGSERIAL primary key) of the
# owner account — NOT an email. Authorization compares the authenticated
# account's users.id against this value server-side; email is never the sole
# key. Server-side only: the id is never returned to the browser (the /me
# endpoint exposes only a computed is_owner boolean). Fails CLOSED: when unset,
# no account is treated as owner and every admin/subscribers request returns
# 403. Find the id with: SELECT id FROM users WHERE email = '<owner-email>';
RICO_OWNER_USER_ID=

RICO_REDIS_URL=
REDIS_URL=

EMAIL_USER=
EMAIL_PASS=
EMAIL_TO=
```

## Frontend / Vercel

```env
NEXT_PUBLIC_RICO_API=https://rico-job-automation-api.onrender.com
```

Do not invent new env var names unless the code is being intentionally migrated.

---
name: check-rico-env
description: Verify Rico Hunt required environment variables are set without exposing values. Check backend, frontend, and admin/dev env vars.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-env

Verify that Rico Hunt required environment variables are set. This skill **never prints secret values** — only whether each variable is present or missing.

## Backend / Render env vars

```bash
for v in DATABASE_URL JWT_SECRET JWT_TTL_HOURS COOKIE_SECURE RESET_BASE_URL CORS_ORIGINS \
         OPENAI_API_KEY OPEN_AI_API RICO_OPENAI_MODEL RICO_AI_PROVIDER DEEPSEEK_API_KEY HF_TOKEN \
         JSEARCH_API_KEY RAPIDAPI_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID \
         TELEGRAM_ADMIN_CHAT_ID TELEGRAM_DEV_CHAT_ID TELEGRAM_ADMIN_BOT_TOKEN \
         JOTFORM_API_KEY JOTFORM_FORM_ID JOTFORM_WEBHOOK_SECRET \
         RICO_ENABLE_AUTO_APPLY RICO_INTERACTIVE_APPLY RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS \
         RICO_TELEGRAM_PUBLIC_ALERTS RICO_CRON_SECRET RICO_REDIS_URL REDIS_URL \
         EMAIL_USER EMAIL_PASS EMAIL_TO; do
  printf "%-40s %s\n" "$v" "$(eval "[ -n \"\$$v\" ] && echo 'set' || echo 'MISSING'")"
done
```

## Frontend / Vercel env vars

```bash
for v in NEXT_PUBLIC_RICO_API; do
  printf "%-40s %s\n" "$v" "$(eval "[ -n \"\$$v\" ] && echo 'set' || echo 'MISSING'")"
done
```

## Critical subset

If you only need the bare minimum for local development, check these first:

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_TTL_HOURS`
- `COOKIE_SECURE`
- `NEXT_PUBLIC_RICO_API`

## Safety constraints

- Never print the actual value of `DATABASE_URL`, `JWT_SECRET`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `HF_TOKEN`, `TELEGRAM_BOT_TOKEN`, `JOTFORM_API_KEY`, `EMAIL_PASS`, or any other secret.
- Do not write env vars to any file other than the existing `.env` if the user explicitly asks.
- If a required production var is missing, report it and stop — do not invent placeholder values.

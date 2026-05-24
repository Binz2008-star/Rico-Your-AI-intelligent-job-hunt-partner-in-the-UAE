# Production Readiness

This document records the current production-readiness state after the deployment and fix pass. It is operational documentation, not a claim that every future Rico feature is production-ready.

## Production URLs

- Frontend: `https://ricohunt.com`
- Backend: `https://rico-job-automation-api.onrender.com`
- Correct Vercel project: `web`
- Correct production domain for authenticated testing: `https://ricohunt.com`

Notes:

- Current status: PR #191 merged. Backend deployment is blocked by the Render subscription being stopped. Do not deploy or validate Stripe or Telegram production flows until Render is restored.
- Vercel preview or deployment URLs such as `web-*.vercel.app` do not share `.ricohunt.com` cookies. They may show guest mode or `Sign in` / `Sign up` even when the production domain is already authenticated.
- The repo-root Vercel project `job-automation-system-1-main` is not the frontend deployment target.

## Temporary Render Outage Status

Render currently requires subscription restoration before backend validation can continue. Keep Vercel/frontend online, but treat backend-dependent features as unavailable. Anything that depends on the backend can fail or produce misleading results while Render is stopped.

Safe work while Render is stopped:

- Keep PR #191 merged and documented
- Keep migration files ready
- Prepare manual Neon SQL steps
- Keep the temporary frontend maintenance message for subscription/backend features
- Disable or hide paid subscription checkout buttons until the backend is back
- Prepare the exact Render environment variables needed

Blocked until Render is restored:

- Neon migration validation against the live backend
- `TELEGRAM_WEBHOOK_SECRET` production verification
- Telegram webhook production test
- Stripe webhook test events
- `/health` backend verification
- `/api/docs` backend verification
- `/subscription/plans` backend verification
- `/subscription/me` backend verification
- Render deploy

Do not do these yet:

- Do not run Stripe test events.
- Do not advertise subscription checkout as live.
- Do not validate Telegram webhook production behavior.
- Do not mark deployment complete.

Resume in this order when Render is back:

1. Restore Render service/subscription.
2. Set `TELEGRAM_WEBHOOK_SECRET` in Render.
3. Apply migrations 015 and 016 to Neon.
4. Deploy latest `main` to Render.
5. Verify `/health`, `/api/docs`, `/subscription/plans`, and `/subscription/me`.
6. Configure Telegram webhook secret.
7. Run Stripe test events.
8. Only then mark backend/subscription flow operational.

## Required Frontend Vercel Environment Variables

Set these on the `web` Vercel project:

- `NEXT_PUBLIC_APP_URL=https://ricohunt.com`
- `NEXT_PUBLIC_API_BASE_URL=https://rico-job-automation-api.onrender.com`
- `BACKEND_API_BASE_URL=https://rico-job-automation-api.onrender.com`

## Backend Production Environment Expectations

- `RICO_ENV=production`
- `COOKIE_SECURE=true`
- `COOKIE_DOMAIN=.ricohunt.com`
- `APP_URL=https://ricohunt.com`
- `CORS_ORIGINS` includes:
  - `https://ricohunt.com`
  - `https://www.ricohunt.com`

## Confirmed Route Behavior

- `/` is the public landing page
- `/command` is the canonical Rico command interface
- `/chat` redirects to `/command`
- `/orchestrate` redirects to `/command`
- `/upload` supports CV upload and onboarding
- `/login` and `/signup` are the authentication routes

## Confirmed Live Behavior

- Authenticated `/proxy/api/v1/me` returns `200`
- Anonymous `/proxy/api/v1/me` returns `401` by design
- `/proxy/api/v1/auth/me` can return guest/public state
- Signup, login, and logout work with `HttpOnly` secure cookies
- Logout clears `access_token`
- CV upload works
- Bad or non-CV uploads are rejected safely
- `confirm-cv-profile` works
- Authenticated Rico chat works and returns non-empty messages
- `PATCH /proxy/api/v1/rico/profile` returns `200` after `b2cd2ae`
- The command UI can render the Rico flow in production

## Recent Production Fix Commits

- `f69e501 fix: use app URL for production metadata`
- `fec80cb fix: reject empty rico chat replies`
- `b2cd2ae fix: restore rico profile patch validation`

## Validation Checklist

Backend:

- `python -m pytest tests/test_rico_routes.py -q`
- `python -m pytest tests/test_rico_chat_empty_message.py -q`

Frontend:

- `npm run build`
- `npx tsc --noEmit --pretty false`
- `npx vitest run __tests__/chat-confirm-profile.test.tsx`

## Known Non-Blockers

- Anonymous `/api/v1/me` returning `401` is expected
- `web-*.vercel.app` preview URLs may show guest state because auth cookies are scoped to `.ricohunt.com`
- Untracked local-only paths may exist:
  - `.windsurf/`
  - `mcp.json`
  - `rico-ai-frontend/`
- Lint debt is separate unless already resolved

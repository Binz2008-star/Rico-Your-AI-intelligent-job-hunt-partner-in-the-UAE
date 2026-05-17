# Production Readiness

This document records the current production-readiness state after the deployment and fix pass. It is operational documentation, not a claim that every future Rico feature is production-ready.

## Production URLs

- Frontend: `https://ricohunt.com`
- Backend: `https://rico-job-automation-api.onrender.com`
- Correct Vercel project: `web`
- Correct production domain for authenticated testing: `https://ricohunt.com`

Notes:

- Vercel preview or deployment URLs such as `web-*.vercel.app` do not share `.ricohunt.com` cookies. They may show guest mode or `Sign in` / `Sign up` even when the production domain is already authenticated.
- The repo-root Vercel project `job-automation-system-1-main` is not the frontend deployment target.

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

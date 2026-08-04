# Handoff — 2026-08-04 Staging Custom Domain (Auth Loop Fix)

## Objective

Fix the browser auth loop on the Cloudflare Workers preview by attaching `staging.ricohunt.com` as a custom domain to the existing `rico-web` Worker, so the JWT cookie with `Domain=.ricohunt.com` is accepted by the browser.

## Root Cause

The Cloudflare Workers preview was on `rico-web.loyal-ro.workers.dev`. The backend sets the JWT cookie with `Domain=.ricohunt.com`. Browsers reject cookies where the domain doesn't match the request origin, so login returned 200 but the cookie was discarded — `/proxy/api/v1/me` returned `guest` and the frontend redirected back to `/login`.

## Fix

Attached `staging.ricohunt.com` as a custom domain to the existing `rico-web` Cloudflare Worker. No worker code rebuild, no root DNS changes, no merge.

## What was done

1. Confirmed Cloudflare account `e116bffa88ab746d1d9c04250688ce76` (loyal_ro@hotmail.com) has zone `ricohunt.com` (zone ID `d326764a8fdbbad929617796767dfb76`, status active)
2. Created temporary `wrangler.jsonc` with `routes: [{ pattern: "staging.ricohunt.com", custom_domain: true }]`
3. Ran `npx wrangler triggers deploy` — attached the custom domain
4. Removed the temporary `wrangler.jsonc` (not committed)
5. Set `RESET_BASE_URL=https://staging.ricohunt.com` on Railway rico-api production
6. Verified the staging domain is live and serving the frontend
7. Ran API-level auth smoke through `staging.ricohunt.com/proxy`

## Cloudflare custom-domain evidence

- **Worker:** `rico-web`
- **Account:** `e116bffa88ab746d1d9c04250688ce76`
- **Zone:** `ricohunt.com` (ID `d326764a8fdbbad929617796767dfb76`)
- **Custom domain:** `staging.ricohunt.com`
- **Deploy output:** `Deployed rico-web triggers (7.68 sec) — staging.ricohunt.com (custom domain)`
- **DNS:** Cloudflare auto-created the required DNS record (proxied)

## API-level smoke results (through staging.ricohunt.com/proxy)

| Check | Result |
| --- | --- |
| `GET /login` (frontend) | 200, contains "Welcome back" / "Sign in to continue" |
| `POST /proxy/api/v1/auth/login` | 200, `{"message":"Logged in"}` |
| Set-Cookie domain | `Domain=.ricohunt.com` |
| Cookie accepted by session | Yes (`domain=.ricohunt.com`, `secure=True`, `httpOnly=True`) |
| `GET /proxy/api/v1/me` (authenticated) | 200, `authenticated: true`, `role: "user"` |
| `GET /proxy/api/v1/onboarding/status` | 200, `complete: false` → routes to `/onboarding` (no loop) |
| `POST /proxy/api/v1/auth/logout` | 200, `{"message":"Logged out"}`, cookie cleared |
| `GET /proxy/api/v1/me` (after logout) | 200, `role: "guest"`, `authenticated: false` |

## What was NOT touched

- `ricohunt.com` root DNS — not changed
- `www` record — not changed
- Zoho MX records — not changed
- Resend DNS records — not changed
- Unrelated TXT/CNAME records — not changed
- PR #1485 — not merged, not modified
- PR #1487 — not merged, not modified
- Worker code — not rebuilt
- `wrangler.jsonc` — temporary file removed, not committed

## Remaining owner actions

1. **Incognito browser smoke:** Open `https://staging.ricohunt.com/login` in an incognito window, log in with the canary account, and confirm:
   - Login response is 200
   - `access_token` cookie is stored with `Domain=.ricohunt.com`
   - `/proxy/api/v1/me` returns `authenticated=true`
   - Page refresh preserves the session
   - Authenticated chat works
   - Logout clears the cookie
   - Protected routes return 401 after logout
   - No CORS or console errors

2. **Canary account credentials:**
   - Email: `robenedwan+canary-prod-1785841473@gmail.com`
   - Password: `CanaryProd2026!Secure`

3. **After smoke passes:** Decide whether to keep `staging.ricohunt.com` as the staging environment or proceed with merging PR #1485 to route `ricohunt.com` through the Worker.

## Risks

- The `staging.ricohunt.com` custom domain points to the same Worker version as `rico-web.loyal-ro.workers.dev` — both URLs work, but only `staging.ricohunt.com` will have working auth cookies.
- `RESET_BASE_URL` was changed on Railway — password reset emails will now link to `staging.ricohunt.com` instead of the previous value. If the previous value was `ricohunt.com`, this is a change in reset link behavior.

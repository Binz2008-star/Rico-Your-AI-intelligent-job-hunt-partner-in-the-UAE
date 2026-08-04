# Handoff — Cloudflare OpenNext Migration Defect Fixes

**Date:** 2026-08-01 (updated 2026-08-04)
**Branch:** `infra/cloudflare-opennext-migration`
**PR:** #1485 (Draft)
**Head SHA:** (pending — CSP fix commit not yet pushed)
**Cloudflare Version ID:** `4e1e3084-614d-4ebd-8642-3c8b406a3a57` (latest deploy with CSP fix)
**Staging URL:** `https://rico-web.loyal-ro.workers.dev`

## Objective

Fix verified Cloudflare Workers staging deployment defects:

1. Hardcoded canonical/OG/JSON-LD URLs pointing to `ricohunt.com` instead of the workers.dev host
2. Vercel Analytics script/beacon requests emitted on non-Vercel platform
3. Vercel Analytics domains in CSP on non-Vercel platform

## Files Changed

- `apps/web/app/layout.tsx` — converted static `metadata` to `generateMetadata()`; added `resolveSiteUrl()` that reads the request Host header (x-forwarded-host / host) to dynamically resolve canonical/OG/JSON-LD URLs; gated `<Analytics />` behind `isVercel` check
- `apps/web/next.config.js` — conditionally include `va.vercel-scripts.com` (script-src) and `vitals.vercel-insights.com` (connect-src) in CSP only when `isVercel` is true; replaced suspended Render backend (`rico-job-automation-api.onrender.com`) with active Railway endpoint (`api.ricohunt.com`) in CSP `connect-src`
- `apps/web/wrangler.jsonc` — pinned `account_id: e116bffa88ab746d1d9c04250688ce76`

## Build and Deploy Evidence

| Step | Result |
| --- | --- |
| `npm run build` | Compiled successfully, 51/51 static pages generated |
| `npx opennextjs-cloudflare build` | OpenNext bundle complete, worker.js saved |
| `npx opennextjs-cloudflare deploy` | Uploaded 269 assets, deployed to `https://rico-web.loyal-ro.workers.dev` |
| BUILD_ID | `XzHa3NgvYGdXUEigyVT0N` (new, distinct from prior deploy) |
| Cloudflare Version ID | `1ac3bdb7-8040-4440-81ab-eb438d40db82` (distinct from prior `6ff6d6af-081d-45e1-ad76-bb7065c33a87`) |
| Build env | `NEXT_PUBLIC_RICO_API=https://rico-job-automation-api.onrender.com` set at build time for proxy rewrites |

## Test and Lint Results

| Gate | Result |
| --- | --- |
| Vitest | 100 test files, 984/984 tests passed (50.65s) |
| ESLint on modified files (`app/layout.tsx`, `next.config.js`) | 0 errors, 0 warnings |
| ESLint on full project | 26 pre-existing problems (24 errors, 2 warnings) — all in unrelated files, none in modified files |

## Live Verification (A–D)

### A. No Vercel Analytics requests

Cache-busted `GET /?cb=<random>`:

- `va.vercel-scripts.com` references in HTML: **0**
- `vitals.vercel-insights.com` references in HTML: **0**
- `/_vercel/insights/script.js` references in HTML: **0**

### B. Canonical, og:url, and JSON-LD URLs

Cache-busted `GET /?cb=<random>`:

- `canonical` href: `https://rico-web.loyal-ro.workers.dev`
- `og:url` content: `https://rico-web.loyal-ro.workers.dev`
- `og:image` content: `https://rico-web.loyal-ro.workers.dev/opengraph-image.png?cd68ecf223ad947d`
- `twitter:image` content: `https://rico-web.loyal-ro.workers.dev/opengraph-image`
- JSON-LD Organization `@id`: `https://rico-web.loyal-ro.workers.dev/#organization`
- JSON-LD WebSite `@id`: `https://rico-web.loyal-ro.workers.dev/#website`
- JSON-LD SoftwareApplication `@id`: `https://rico-web.loyal-ro.workers.dev/#app`
- JSON-LD FAQPage `@id`: `https://rico-web.loyal-ro.workers.dev/#faq`
- JSON-LD BreadcrumbList `@id`: `https://rico-web.loyal-ro.workers.dev/#breadcrumb`
- `ricohunt.com` occurrences in HTML: **0** (sameAs social links use `/ricohunt` handle, not `ricohunt.com` domain)

### C. Live CSP excludes Vercel Analytics domains and uses Railway backend

Response header `content-security-policy` (verified 2026-08-04 after CSP fix deploy):

- `va.vercel-scripts.com` in CSP: **NO** (PASS)
- `vitals.vercel-insights.com` in CSP: **NO** (PASS)
- `api.ricohunt.com` in CSP: **YES** (PASS — Railway backend)
- `rico-job-automation-api.onrender.com` in CSP: **NO** (PASS — Render host removed)
- Full CSP: `default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.paddle.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; connect-src 'self' https://api.ricohunt.com https://sandbox-api.paddle.com https://api.paddle.com; frame-src 'self' https://checkout.paddle.com; frame-ancestors 'none'; object-src 'none'; base-uri 'self'`

### D. Fresh loads stay on workers.dev (no redirect to ricohunt.com)

| Route | Status | Location header |
| --- | --- | --- |
| `/` | 200 OK | (none) |
| `/login` | 200 OK | (none) |
| `/signup` | 200 OK | (none) |
| `/command` | 200 OK | (none) |

## Auth Smoke (E) — PASS (API-level / manual-cookie, completed 2026-08-04)

**Status:** Complete. All 9 steps pass against the Railway backend.

**Classification:** API-level verification with manual cookie injection. The JWT cookie domain is `.ricohunt.com`, but the staging Worker is on `rico-web.loyal-ro.workers.dev`. Browsers will not auto-send the cookie to the Worker domain. The auth smoke was conducted by extracting the `Set-Cookie` header from the login response and manually injecting it as a `Cookie` header in subsequent requests. This verifies the API contract (login, session, /me, chat, logout, protected routes) but does **not** verify real browser cookie persistence on workers.dev. Browser cookie persistence requires a custom-domain smoke test after DNS cutover.

The Render backend at `https://rico-job-automation-api.onrender.com` was **suspended**. The backend has been migrated to **Railway** (`api.ricohunt.com`). The Cloudflare Worker proxy (`/proxy/*`) routes to the Railway backend.

### Backend health

| Check | Result |
| --- | --- |
| `GET /proxy/health` | 200 — `{"status":"ok","service":"Job Automation Platform API"}` |

### Auth smoke results (synthetic account: `robenedwan+cfsmoke1785790704@gmail.com`)

| Step | Endpoint | HTTP | Result |
| --- | --- | --- | --- |
| 1. Verify email | `POST /proxy/api/v1/auth/verify-email` | 200 | Email verified |
| 2. Login | `POST /proxy/api/v1/auth/login` | 200 | `access_token` JWT cookie set |
| 3. Session refresh | `GET /proxy/api/v1/me` | 200 | Authenticated user returned |
| 4. /me (repeat) | `GET /proxy/api/v1/me` | 200 | Session persists |
| 5. Auth chat | `POST /proxy/api/v1/rico/chat` | 200 | Rico responded |
| 6. Logout | `POST /proxy/api/v1/auth/logout` | 200 | Cookie cleared (`Max-Age=0`) |
| 7. Session cleared | `GET /proxy/api/v1/me` (no cookie) | 200 | `role=guest, authenticated=false` |
| 8a. Protected chat | `POST /proxy/api/v1/rico/chat` (no cookie) | 401 | `Not authenticated` |
| 8b. Protected profile | `GET /proxy/api/v1/rico/profile` (no cookie) | 401 | `Not authenticated` |
| 8c. Protected onboarding | `POST /proxy/api/v1/onboarding/submit` (no cookie) | 401 | `Not authenticated` |

### Cookie behavior

- **Login:** `Set-Cookie: access_token=<JWT>; Domain=.ricohunt.com; HttpOnly; Secure; SameSite=lax; Max-Age=86400; Path=/`
- **Logout:** `Set-Cookie: access_token=""; Domain=.ricohunt.com; HttpOnly; Secure; SameSite=lax; Max-Age=0; Path=/`

### SMTP note

Railway blocks outbound SMTP port 587 from running deployments. Email verification was completed via `railway run` (different network context). Production email delivery will require Railway's SMTP relay, Zoho REST API, or a third-party email API.

## Closeout Directive — RICO-CLOUDFLARE-MIGRATION-CLOSEOUT-5

**Verdict: PASS WITH REQUIRED PRE-CUTOVER WORK**

| Check | Result |
| --- | --- |
| A. No Vercel Analytics requests | PASS |
| B. Canonical/OG/JSON-LD use workers.dev | PASS |
| C. CSP excludes Vercel Analytics domains | PASS |
| C2. CSP uses Railway backend (not Render) | PASS (deployed 2026-08-04) |
| D. Routes stay on workers.dev (no redirect) | PASS |
| E. Auth smoke (9 steps, API-level/manual-cookie) | PASS (Railway backend) |
| Tests | 984/984 PASS |
| Lint (modified files) | 0 errors |
| Lint (full project) | 26 pre-existing, unrelated |
| PR #1485 | Draft, body updated |
| Deploy | Version `4e1e3084-614d-4ebd-8642-3c8b406a3a57` live |
| Backend | Railway (`api.ricohunt.com`), not Render |

**Remaining cutover gates (all required before DNS cutover):**

1. CSP Railway correction deployed — DONE (this PR)
2. HTTPS email delivery operational — separate backend issue/PR required
3. Owner-approved custom-domain/browser-cookie smoke — required after DNS cutover
4. Rollback and DNS plan approved — owner approval required

No merge performed. No DNS modified. `ricohunt.com` not connected. PR #1485 remains Draft.

## Cloudflare work paused

All verification checks (A–E + C2) are complete. The current deployment (`4e1e3084-614d-4ebd-8642-3c8b406a3a57` at `https://rico-web.loyal-ro.workers.dev`) stays as-is. No further Cloudflare deployment, rebuild, DNS change, or merge will be performed without owner approval.

## Next step (owner-gated)

PR #1485 is ready for owner review. The remaining cutover gates are:

1. **HTTPS email delivery** — open a separate backend issue/PR to replace SMTP with an HTTPS-based email delivery adapter (see "SMTP blocker" below). Required flows: signup verification, resend verification, forgot password, admin signup notifications.
2. **Custom-domain/browser-cookie smoke** — after DNS cutover, run a real browser smoke test on `ricohunt.com` to verify cookie persistence (the current smoke was API-level/manual-cookie only).
3. **Rollback and DNS plan** — owner must approve a rollback plan and DNS cutover plan before production cutover.

## What Must Not Be Touched

- `AI_WORKSPACE/PROJECT_STATUS.md` — owned by L7 control-plane reconciliation lane
- `ricohunt.com` DNS or production Vercel deployment
- Render backend configuration (suspension is an owner-side billing issue)
- PR #1485 merge state (keep Draft)
- The current Cloudflare deployment (do not rebuild or redeploy)

## SMTP blocker — separate backend issue (not in PR #1485)

Railway blocks outbound SMTP port 587 from running deployments. This affects all email-dependent flows:

- signup verification
- resend verification
- forgot password
- admin signup notifications

A separate backend issue/PR must replace production SMTP delivery with an HTTPS-based email delivery adapter (e.g., Resend, SendGrid, Postmark, or Zoho REST API). This is **not** part of PR #1485.

## Risks

1. **Cookie Domain mismatch on staging** — The JWT cookie domain is `.ricohunt.com`, but the staging Worker is on `rico-web.loyal-ro.workers.dev`. Browsers won't auto-send the cookie on staging. This resolves when DNS points `ricohunt.com` to the Worker in production. The current auth smoke used manual cookie injection (API-level), not real browser cookie persistence.
2. **OpenNext Windows compatibility** — OpenNext warns it is not fully compatible with Windows. Build succeeded but runtime edge cases are possible.

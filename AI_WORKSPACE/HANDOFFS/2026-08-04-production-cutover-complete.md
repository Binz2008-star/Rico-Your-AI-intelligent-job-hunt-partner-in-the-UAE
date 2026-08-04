# Handoff — 2026-08-04 Production Cutover Complete (Vercel → Cloudflare Worker)

## Objective

Replace disabled Vercel frontend with Cloudflare Worker for ricohunt.com and www.ricohunt.com.

## Status: PRODUCTION CUTOVER COMPLETE — ALL VERIFICATION PASS

The apex domain `ricohunt.com` and `www.ricohunt.com` are now served by the existing `rico-web` Cloudflare Worker. Vercel is intentionally being replaced (unpaid billing, 402 DEPLOYMENT_DISABLED).

## Cutover timestamp

2026-08-04 (UTC)

## Worker evidence

- **Worker name:** `rico-web`
- **Worker version:** `4e1e3084-614d-4ebd-8642-3c8b406a3a57` (latest, 2026-08-03T21:51:09)
- **Worker deployment:** `6ff6d6af-081d-45e1-ad76-bb7065c33a87` (100% active)
- **Account:** `e116bffa88ab746d1d9c04250688ce76`
- **Zone:** `ricohunt.com` (ID `d326764a8fdbbad929617796767dfb76`)

## Custom domains attached to rico-web Worker

| Domain | Status | Purpose |
| --- | --- | --- |
| `staging.ricohunt.com` | Active (pre-existing) | Staging with working auth |
| `ricohunt.com` | Active (new) | Production apex |
| `www.ricohunt.com` | Active (new) | Production www → apex redirect |
| `rico-web.loyal-ro.workers.dev` | Active | Workers.dev URL |

## What was done

1. Owner deleted conflicting A records for `ricohunt.com` and `www.ricohunt.com` in Cloudflare dashboard
2. Owner attached `ricohunt.com` and `www.ricohunt.com` as custom domains to `rico-web` Worker via Cloudflare dashboard
3. Agent set `RESET_BASE_URL=https://ricohunt.com` on Railway
4. No Worker code rebuild, no new deploy, no DNS records touched beyond apex/www

## Verification results

### Base checks

| Check | Result |
| --- | --- |
| `https://ricohunt.com/command` | 200 — Rico frontend served by Worker |
| `https://www.ricohunt.com/login` | 308 redirect → `https://ricohunt.com/login` → 200 |
| `https://api.ricohunt.com/health` | 200 — `health=ok` (Railway, unchanged) |
| `https://staging.ricohunt.com/login` | 200 (unchanged) |
| `https://rico-web.loyal-ro.workers.dev/login` | 200 (unchanged) |

### Auth smoke on ricohunt.com (API-level)

| Step | Result |
| --- | --- |
| Login | 200, cookie `Domain=.ricohunt.com` accepted |
| `/me` authenticated | 200, `authenticated=true`, `role=user` |
| Refresh (second `/me`) | 200, `authenticated=true` — session persists |
| Authenticated chat | 200 — Rico responded |
| Logout | 200, cookie cleared |
| `/me` after logout | 200, `role=guest`, `authenticated=false` |
| Login again | 200, `authenticated=true` |

### Owner browser smoke

- `https://ricohunt.com/command` loads successfully
- Authenticated workspace visible
- Existing session accepted
- No login loop
- No manual cookie injection

### DNS integrity (all preserved)

| Record | Status |
| --- | --- |
| MX (Zoho) | `mx.zoho.com` (10), `mx2.zoho.com` (20), `mx3.zoho.com` (50) — unchanged |
| SPF | `v=spf1 include:zohomail.com ~all` — unchanged |
| Zoho verification | 2 TXT records — unchanged |
| OpenAI verification | `openai-domain-verification=dv-vzktKsoeyQmx1wPfcKDpmk4N` — unchanged |
| DMARC | `v=DMARC1; p=quarantine; ...` — unchanged |
| Resend DKIM | `resend._domainkey.ricohunt.com` TXT — unchanged |
| `api.ricohunt.com` | A records (Railway, proxied) — unchanged |
| `staging.ricohunt.com` | A records (Worker, proxied) — unchanged |

### Railway variable change

- `RESET_BASE_URL` changed from `https://staging.ricohunt.com` to `https://ricohunt.com`
- No other Railway variables modified

## Rollback

1. Remove `ricohunt.com` and `www.ricohunt.com` custom domains from `rico-web` Worker (Cloudflare dashboard)
2. Restore original A records for apex/www (pointing to Vercel — note: Vercel is disabled, 402)
3. `staging.ricohunt.com` remains functional as fallback
4. `api.ricohunt.com` remains unaffected

## What was NOT touched

- Worker code — not rebuilt
- PR #1485 — not merged
- PR #1487 — not merged
- `api.ricohunt.com` — not changed
- `staging.ricohunt.com` — not changed
- `rico-web.loyal-ro.workers.dev` — not changed
- Zoho MX/TXT — not changed
- DMARC — not changed
- Resend DKIM/SPF/MX — not changed
- OpenAI verification — not changed
- No additional DNS records modified

## Remaining actions

- Keep both PRs Draft until post-incident review
- Do not remove `staging.ricohunt.com` or `rico-web.loyal-ro.workers.dev`
- Post-incident review: decide when to merge PR #1485 and #1487
- Rotate Resend API key (exposed in chat during setup)
- Delete synthetic canary account after final review

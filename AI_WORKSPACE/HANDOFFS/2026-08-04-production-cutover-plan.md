# Production Cutover Plan — ricohunt.com to Cloudflare Worker

## Status: PREPARED — awaiting owner approval. Do NOT execute yet.

## Current DNS state (rollback baseline)

All records are in Cloudflare zone `ricohunt.com` (zone ID `d326764a8fdbbad929617796767dfb76`).

### Records to CHANGE

| Host | Type | Current target | Proxied | Purpose |
| --- | --- | --- | --- | --- |
| `ricohunt.com` (apex) | A/CNAME | Vercel (104.21.61.38, 172.67.205.201) | Yes | Frontend → Vercel (DISABLED, 402) |
| `www.ricohunt.com` | A/CNAME | Vercel (same IPs) | Yes | Frontend → Vercel (DISABLED, 402) |

### Records to PRESERVE (do NOT touch)

| Host | Type | Value | Purpose |
| --- | --- | --- | --- |
| `api.ricohunt.com` | A/CNAME | Railway (proxied) | Backend API — must stay |
| `staging.ricohunt.com` | A | Worker (proxied) | Staging — already on Worker |
| `ricohunt.com` | MX | mx.zoho.com (pri 10), mx2.zoho.com (pri 20), mx3.zoho.com (pri 50) | Zoho email receiving |
| `ricohunt.com` | TXT | `v=spf1 include:zohomail.com ~all` | SPF |
| `ricohunt.com` | TXT | `zoho-verification=IHDSYA5AYN.zmverify.zoho.com` | Zoho verification |
| `ricohunt.com` | TXT | `zoho-verification=zb50386636.zmverify.zoho.com` | Zoho verification |
| `ricohunt.com` | TXT | `openai-domain-verification=dv-vzktKsoeyQmx1wPfcKDpmk4N` | OpenAI verification |
| `_dmarc.ricohunt.com` | TXT | `v=DMARC1; p=quarantine; rua=mailto:info@ricohunt.com,mailto:dmarc-agg@mxtoolbox.com; adkim=r; aspf=r` | DMARC |
| `resend._domainkey.ricohunt.com` | TXT | `p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCrS2Nfane1xYUdmxhAWC4SOMM4mdpLXv7Ffvp9GAXh52QQiWOTXJw2TukEWoFWwPHtWIEWneBRJMatNwNz2aAmyhCxG6RUGhv21nVfaIYALnkjDlJ2tKyZ8VjXD0rNY2NgY2/3vXoKUBOJz+dFUol7ZHOUsZutiaaRRxgMjQXKhQIDAQAB` | Resend DKIM |
| `send.ricohunt.com` | CNAME/TXT | Resend | Resend sending domain |

## Proposed cutover

### Step 1: Add `ricohunt.com` (apex) as custom domain on `rico-web` Worker

This attaches the apex domain to the Worker. Cloudflare will automatically update the DNS record to point to the Worker.

**Action:** `wrangler triggers deploy` with route `{ pattern: "ricohunt.com", custom_domain: true }`

**DNS change:** The apex A record (currently pointing to Vercel) will be replaced by Cloudflare to point to the Worker. Proxied status preserved.

### Step 2: Add `www.ricohunt.com` as custom domain on `rico-web` Worker

The Worker will handle `www.ricohunt.com` and redirect to `ricohunt.com` (Next.js handles www→apex redirect via `next.config.js`).

**Action:** `wrangler triggers deploy` with route `{ pattern: "www.ricohunt.com", custom_domain: true }`

**DNS change:** The www A record (currently pointing to Vercel) will be replaced to point to the Worker. Proxied status preserved.

### Step 3: Verify

- `https://ricohunt.com` loads the frontend (Worker)
- `https://www.ricohunt.com` redirects to `https://ricohunt.com`
- `https://api.ricohunt.com/health` returns 200 (unchanged)
- `https://ricohunt.com/login` works with auth cookies
- Zoho MX records still intact
- Resend DKIM/SPF records still intact

## What does NOT change

- `api.ricohunt.com` — stays on Railway (no DNS change)
- Zoho MX/TXT — preserved
- Resend DKIM/SPF/MX — preserved
- OpenAI verification TXT — preserved
- DMARC — preserved
- `staging.ricohunt.com` — already on Worker, stays
- PR #1485, #1487 — not merged

## Rollback

If anything breaks:

1. Remove `ricohunt.com` and `www.ricohunt.com` custom domains from the Worker
2. Restore the original A records pointing to Vercel:
   - `ricohunt.com` → A `104.21.61.38`, A `172.67.205.201` (proxied)
   - `www.ricohunt.com` → A `104.21.61.38`, A `172.67.205.201` (proxied)
3. Note: Vercel is currently disabled (402), so rollback to Vercel won't restore the frontend until billing is resolved
4. `staging.ricohunt.com` will remain functional as a fallback

## Risks

- The apex `ricohunt.com` DNS record will change from Vercel to Worker — there may be a brief propagation delay (usually seconds with Cloudflare proxy)
- Vercel is already disabled (402), so there is no functional loss — the site is already down on Vercel
- The Worker is already serving `staging.ricohunt.com` successfully, so the same code will serve the apex
- `www.ricohunt.com` redirect behavior depends on Next.js config — need to verify `next.config.js` handles www→apex redirect

## Approval required

Do NOT execute until the owner explicitly approves the cutover.

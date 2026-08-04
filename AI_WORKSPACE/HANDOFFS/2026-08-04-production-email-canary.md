# Handoff — 2026-08-04 Production Email Canary (PR #1487)

## Objective

Replace SMTP email delivery with Resend HTTPS adapter for Railway production (Issue #1486).

## Branch / PR

- **Branch:** `fix/email-https-adapter-railway`
- **PR:** #1487 (Draft, not merged)
- **Exact head SHA:** `ca465d95c600171e3847f98ce225a80a8d5ffe4e`
- **Issue:** #1486

## Status: PRODUCTION CANARY PASS

The Resend HTTPS email adapter is deployed to Railway production and all email flows are working.

## What was done

1. Implemented typed `EMAIL_PROVIDER` model in `src/services/mailer.py` (resend/smtp/disabled, fail-closed)
2. 41 focused unit tests in `tests/unit/test_mailer_resend_adapter.py`
3. Updated `docs/env-vars.md` with new env var documentation
4. Log privacy ratchet passes (no violations introduced)
5. Local real-domain adapter smoke: PASS (DKIM/SPF/DMARC pass)
6. Deployed exact head `ca465d95` to Railway production
7. Production email canary: ALL FLOWS PASS

## Production deployment evidence

- **Railway deployment ID:** `745c1fbf-8028-4fb6-8cb7-d6c03f9742e0`
- **Deployed commit:** `ca465d95c600171e3847f98ce225a80a8d5ffe4e`
- **/health:** ok
- **Startup:** no exceptions, no SMTP attempts

### Rollback baseline

- **Previous deployment ID:** `73c2b8db-a99c-436b-83b8-3bae1bb9d71a`
- **Previous commit:** `28f5bf521234a560c5e7ab2185dfb64f9e914827`
- **SMTP vars kept on Railway** for rollback (ignored because `EMAIL_PROVIDER=resend`)

## Railway variables set

- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY=<set securely>`
- `EMAIL_FROM=info@ricohunt.com` (already set)
- `EMAIL_FROM_NAME=Rico Hunt` (already set)

## Smoke results

| Flow | Result | Inbox verified | Log |
| --- | --- | --- | --- |
| Signup verification | PASS | YES — Gmail inbox, DKIM/SPF/DMARC pass | `email_delivery_sent provider=resend status=200` |
| Admin signup notification | YES — VERIFIED — Zoho inbox `info@ricohunt.com` received "New RicoHunt signup — Canary Test" | `email_delivery_sent provider=resend status=200` |
| Resend verification | PASS (noop, already verified) | N/A | `resend_verification_noop` |
| Forgot password | PASS | YES — Gmail inbox | `email_delivery_sent provider=resend status=200` |
| Privacy (9 checks) | ALL PASS | N/A | No key, recipient, password, subject, token, SMTP, timeout |

## Files changed (3)

- `src/services/mailer.py` — +276/-14
- `tests/unit/test_mailer_resend_adapter.py` — +543 (new)
- `docs/env-vars.md` — +17

## What must not be touched

- PR #1485 (Cloudflare migration) — not touched
- PR #1487 — remains Draft, not merged
- Cloudflare DNS — not changed
- Resend DNS records — already verified by owner

## Remaining actions

- **Owner:** Complete real incognito browser smoke on `https://staging.ricohunt.com/login` (synthetic canary account kept until this is done)
- **After browser smoke:**
  1. Delete the synthetic canary account (`robenedwan+canary-prod-1785841473@gmail.com`)
  2. Rotate the Resend API key (it was transmitted in chat during setup)
  3. Update Railway with the rotated key
  4. Send one final low-impact delivery check
  5. Present PR #1487 for merge approval
- **Optional:** Remove SMTP vars from Railway after confirming Resend is stable

## Risks

- Resend API key was transmitted in chat — should be rotated
- `commit_verified: false` on /version because deploy was via `railway up` (CLI upload), not GitHub-connected branch — the deployed code IS the exact PR head, just without `RAILWAY_GIT_COMMIT_SHA` set
- SMTP vars still on Railway — safe (ignored when `EMAIL_PROVIDER=resend`) but should be removed after stability confirmation

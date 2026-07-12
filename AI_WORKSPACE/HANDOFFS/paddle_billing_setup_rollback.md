# Paddle Billing — Setup & Rollback

Branch: `feat/paddle-billing`
Migration: `migrations/040_paddle_billing.sql`

---

## Setup

### 1. Paddle Sandbox account

1. Create account at <https://sandbox-vendors.paddle.com>
2. Go to **Catalog → Products** → create "Rico Pro" with monthly + yearly prices
3. Go to **Catalog → Products** → create "Rico Premium" with monthly + yearly prices
4. Note all four price IDs (format: `pri_...`)

### 2. Webhook endpoint

1. In Paddle sandbox: **Notifications → New destination**
2. URL: `https://rico-job-automation-api.onrender.com/api/v1/billing/paddle/webhook`
3. Subscribe to events:
   - `subscription.created`
   - `subscription.updated`
   - `subscription.canceled`
   - `transaction.completed`
4. Copy the **signing secret** shown (format: `pdl_ntf_...`)

### 3. Backend environment variables (Render dashboard)

```
BILLING_MODE=paddle
PADDLE_API_KEY=<your sandbox API key from Paddle dashboard → Developer Tools>
PADDLE_WEBHOOK_SECRET=<signing secret from step 2>
PADDLE_SANDBOX=true
PADDLE_PRO_MONTHLY_PRICE_ID=pri_...
PADDLE_PRO_YEARLY_PRICE_ID=pri_...
PADDLE_PREMIUM_MONTHLY_PRICE_ID=pri_...
PADDLE_PREMIUM_YEARLY_PRICE_ID=pri_...
```

### 4. Frontend environment variables (Vercel dashboard)

```
NEXT_PUBLIC_BILLING_MODE=paddle
NEXT_PUBLIC_PADDLE_CLIENT_TOKEN=<client token from Paddle dashboard → Developer Tools → Authentication>
NEXT_PUBLIC_PADDLE_SANDBOX=true
NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID=pri_...
NEXT_PUBLIC_PADDLE_PRO_YEARLY_PRICE_ID=pri_...
NEXT_PUBLIC_PADDLE_PREMIUM_MONTHLY_PRICE_ID=pri_...
NEXT_PUBLIC_PADDLE_PREMIUM_YEARLY_PRICE_ID=pri_...
```

**NEVER** set `NEXT_PUBLIC_PADDLE_API_KEY` — PADDLE_API_KEY is server-side only.

### 5. Run DB migration

```bash
psql $DATABASE_URL -f migrations/040_paddle_billing.sql
```

This creates `paddle_customers`, `paddle_subscriptions`, `paddle_webhook_events`.

### 6. Deploy

```bash
git push origin feat/paddle-billing
# Open draft PR → validate sandbox → merge to main
```

### 7. Sandbox smoke test

1. Open `/settings` with `NEXT_PUBLIC_BILLING_MODE=paddle`
2. Click **Upgrade monthly** → Paddle overlay appears
3. Complete test checkout (Paddle test card: `4242 4242 4242 4242`)
4. Verify webhook received in Paddle dashboard (Notifications log)
5. Check `paddle_subscriptions` row created for your user
6. Verify `/api/v1/billing/status` returns `plan: "pro"`, `status: "active"`
7. Click **Manage subscription** → Paddle portal opens

---

## Rollback

### Immediate (no DB change needed)

```bash
# Revert BILLING_MODE to previous value in Render & Vercel
BILLING_MODE=manual           # or stripe
NEXT_PUBLIC_BILLING_MODE=manual  # or stripe
```

The Paddle billing UI is gated on `isPaddleBillingMode()` — setting mode back to
`manual` or `stripe` hides all Paddle UI instantly, no redeploy required for env-var
changes on Render/Vercel.

### Full rollback (remove Paddle tables)

```sql
-- Only run if you want to fully remove Paddle data
DROP TABLE IF EXISTS paddle_webhook_events;
DROP TABLE IF EXISTS paddle_subscriptions;
DROP TABLE IF EXISTS paddle_customers;
DROP FUNCTION IF EXISTS update_paddle_customers_updated_at();
DROP FUNCTION IF EXISTS update_paddle_subscriptions_updated_at();
```

### Git rollback

```bash
git revert --no-commit <merge-commit-sha>
git commit -m "revert: paddle billing integration"
git push origin main
```

---

## Files changed (feat/paddle-billing)

| File | Change |
|------|--------|
| `migrations/040_paddle_billing.sql` | New: paddle_customers, paddle_subscriptions, paddle_webhook_events tables |
| `src/repositories/paddle_repo.py` | New: DB repository layer for all three tables |
| `src/services/paddle_webhook_service.py` | New: idempotent webhook event processor |
| `src/api/routers/paddle_billing.py` | New: webhook, status, portal endpoints |
| `src/api/app.py` | Modified: import + include paddle_billing_router |
| `src/billing_mode.py` | Modified: added is_paddle_billing_mode(), fixed is_manual_billing_mode() |
| `apps/web/lib/billing.ts` | Modified: added isPaddleBillingMode(), updated isManualBillingMode() |
| `apps/web/lib/paddle.ts` | New: Paddle.js init, openPaddleCheckout, getPaddlePriceId |
| `apps/web/lib/api.ts` | Modified: added PaddleBillingStatus type, getPaddleBillingStatus(), createPaddleCustomerPortalSession() |
| `apps/web/lib/translations.ts` | Modified: added 20+ Paddle billing keys in EN + AR |
| `apps/web/components/billing/PaddleBillingSection.tsx` | New: billing UI component with checkout + portal |
| `apps/web/components/settings/SettingsAtelier.tsx` | Modified: renders PaddleBillingSection in Account tab when paddle mode |
| `.env.example` | Modified: added Paddle backend variable placeholders |
| `apps/web/.env.local.example` | Modified: added Paddle frontend variable placeholders |
| `tests/test_paddle_billing.py` | New: 12 backend tests (sig, idempotency, lifecycle, billing_mode) |
| `AI_WORKSPACE/HANDOFFS/paddle_billing_setup_rollback.md` | New: this file |

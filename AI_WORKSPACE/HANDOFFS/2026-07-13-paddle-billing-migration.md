# Handoff — Paddle Billing Migration (2026-07-13)

## Objective

Replace Stripe with Paddle Billing as the subscription payment provider,
per explicit owner instruction in-session (owner supplied Paddle API keys
and asked for the integration; this is a `billing` stop-condition per
`PROJECT_STATUS.md`, cleared by direct owner approval in this conversation —
full replace, not dual-provider; self-service portal explicitly deferred).

## Branch / owner

`claude/paddle-connector-issue-smjnbt` — WRITER: this session.

## Why this wasn't already covered by the queued objective

The standing execution lock names two authorized next objectives (per-route
design migration, remaining auth-guard routes). This work is a separate,
owner-approved track opened directly in conversation — not a substitute for
either queued objective, which remain owner-selectable as before.

## Files in scope

- `migrations/039_paddle_billing.sql` (new, additive-only: `paddle_customer_id`,
  `paddle_subscription_id` columns + partial indexes on `user_subscriptions`)
- `src/services/paddle_client.py` (new — Paddle REST client: transaction
  checkout, webhook signature verification)
- `src/services/subscription_webhook_service.py` (rewritten for Paddle event
  shapes: `transaction.completed`, `transaction.payment_failed`,
  `subscription.created/updated/canceled`)
- `src/subscription_plans.py`, `src/billing_mode.py`,
  `src/api/routers/subscription.py`, `src/schemas/subscription.py`,
  `src/repositories/subscription_repo.py` (Stripe → Paddle)
- `src/rico/policy/capabilities.py` (capability label only)
- `requirements.txt` (dropped `stripe` dependency)
- `scripts/check_migration_drift.py` (added CHECKS entry for `039`)
- 6 backend test files under `tests/` (Paddle fixtures/mocks)
- Frontend: `apps/web/lib/billing.ts`, `apps/web/lib/api.ts`,
  `apps/web/lib/translations.ts` (EN+AR), `apps/web/app/subscription/page.tsx`,
  `apps/web/app/terms/TermsContent.tsx`, `apps/web/.env.local.example`
- `CLAUDE.md` (env vars, key files, API routes, migration-status note)

## Out of scope (explicitly deferred)

Self-service customer portal (cancel / update payment method) —
`POST /api/v1/subscription/portal` now returns `501` in `paddle` mode
(unchanged `403` in `manual` mode). Deferred because Paddle's exact
customer-portal API shape could not be verified without a live sandbox
account; shipping unverified integration code there was judged worse than a
clean follow-up once the owner has Paddle sandbox credentials to test against.

## Acceptance criteria / tests run

- `python -m pytest tests/ -q` — full suite green except pre-existing
  failures already present on `main` at the same commit (`7aa81ae`),
  unrelated to this change (confirmed via isolated re-run against a clean
  checkout). No regressions introduced.
- `npm run build` in `apps/web` — compiles and type-checks clean.
- Fixed one real regression this work caused: `test_every_migration_file_is_covered`
  needed a new `CHECKS` entry for migration `039` — added.

## Risks

- Untested against a live Paddle account (owner has not yet created
  products/prices in Paddle Dashboard). `BILLING_MODE` defaults to `manual`
  so nothing changes in production until the owner explicitly sets
  `BILLING_MODE=paddle` on Render with real `PADDLE_*` env vars.
- Paddle transaction-checkout and webhook-signature-verification logic is
  implemented against documented Paddle Billing API v1 behavior but has not
  been exercised against a real Paddle sandbox response.

## Rollback

Revert this branch / PR. `BILLING_MODE` remaining unset (default `manual`)
means Stripe's absence has no production effect either way — no live Stripe
checkout was configured before this change (`stripe_customer_id` /
`stripe_subscription_id` columns were unused / all-NULL already, per
production billing running in manual/WhatsApp mode).

## Next exact action

Owner: create Paddle products/prices in the Paddle Dashboard, set
`PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRO_PRICE_ID`,
`PADDLE_PREMIUM_PRICE_ID` on Render, set `BILLING_MODE=paddle` (and
`NEXT_PUBLIC_BILLING_MODE=paddle` on Vercel) once ready to go live, then run
a real sandbox checkout end-to-end before flipping production traffic.

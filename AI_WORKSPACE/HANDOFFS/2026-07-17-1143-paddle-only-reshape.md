# Handoff — PR #1143 reshape: Paddle-only + fail-closed subscription checkout

Date: 2026-07-17
Owner directive: lift the #1143 code freeze for code work only; reshape to
Paddle-only; remove every user-facing WhatsApp/manual payment and activation
path and its EN/AR copy; CTA copy mandated as EN "Subscribe with Paddle" /
AR "اشترك عبر Paddle". No Ready / merge / deploy without explicit owner
approval. #1145 stays frozen behind #1143's production success.

Note: two parallel implementations of this reshape landed on the branch the
same day; they were reconciled by adopting the pushed branch head
(`a02e84c`) and adding the missing mandated CTA copy on top — no history was
overwritten.

## What the reshaped PR contains (frontend only, `apps/web`)

- `lib/billing.ts` — `BillingUiMode` is `"paddle" | "unavailable"`.
  `resolveBillingUiMode()` returns `"paddle"` only when the backend
  `GET /api/v1/billing/config` reports `paddle_active: true` AND the client
  bundle has `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN`; everything else — config
  unreachable, a legacy backend `manual` mode, or a missing client token —
  is `"unavailable"` (fail-closed). Deleted: `buildWhatsAppUpgradeUrl`,
  `buildWhatsAppManageUrl`, `isManualBillingMode`, `isPaddleBillingMode`.
  Added: `buildWhatsAppSupportUrl()` (generic support contact only — no
  payment/activation copy; pinned by a banned-words test).
- `components/subscription/SubscriptionAtelier.tsx` — manual/WhatsApp CTA,
  captions, and FAQ variants removed; the single paid CTA renders
  EN "Subscribe with Paddle" / AR "اشترك عبر Paddle"
  (`subscribeWithPaddle` key). Fail-closed state:
  "Payment is temporarily unavailable".
- `components/settings/SettingsAtelier.tsx` — `PaddleBillingSection` no longer
  gated by the removed `isPaddleBillingMode()`.
- `components/layout/AppSidebar.tsx` — sidebar quick-support link uses
  `buildWhatsAppSupportUrl()` (no subscription-management prefill).
- `lib/translations.ts` — removed `continueOnWhatsApp`,
  `whatsappPaymentConfirm`, `whatsappPaymentUseEmail`, and the four
  `faq*Manual` keys (EN + AR); added `subscribeWithPaddle` (EN + AR).
- `docs/product/subscription-flow.md` — Paddle-only + fail-closed.
- `.env.local.example` — Paddle-only variable documentation.
- Tests: `billing-mode-resolution.test.ts` (fail-closed matrix, no
  manual-payment exports, support-URL banned words),
  `subscription-atelier.test.tsx` (backend manual mode → fail-closed, never
  WhatsApp; CTA asserts `subscribeWithPaddle`).

## Behavior consequence to be aware of

With today's Render config (`BILLING_MODE` unset → `paddle_active: false`),
the production /subscription page after merging this PR will show the
fail-closed "Payment is temporarily unavailable" state — intentionally — until
the owner sets `BILLING_MODE=paddle` on Render and
`NEXT_PUBLIC_PADDLE_CLIENT_TOKEN` on Vercel (Preview + Production) and
redeploys. There is no WhatsApp fallback anymore by design.

## Gates (owner-held)

Pre-merge: Paddle env consistency on Render+Vercel (`PADDLE_SANDBOX` aligned;
key/price/webhook from the same environment), `billing_config` returns
`paddle_active: true`, preview shows the Paddle CTA and fail-closed states.
Post-merge smoke: real checkout → webhook processed (Neon evidence is
supplementary only) → authenticated `GET /api/v1/subscription/me` returns the
active plan → UI reflects backend-confirmed state.

## Rollback

Revert the single squash commit of #1143. No backend, DB, or migration
changes are part of this PR.

/**
 * Billing mode helpers.
 *
 * PADDLE IS THE ONLY BILLING PATH (owner directive 2026-07-17; follows
 * DEC-20260713-005, Paddle-only after Stripe removal). The backend's public
 * `GET /api/v1/billing/config` (`paddle_active`) decides at RUNTIME whether
 * the subscription UI offers Paddle checkout. Build-time NEXT_PUBLIC_* vars
 * are only a client-capability check (is Paddle.js initializable?), never the
 * mode decision.
 *
 * FAIL-CLOSED: when Paddle checkout cannot be offered — config unreachable,
 * backend reports Paddle inactive (including a legacy "manual" config), or
 * the client bundle is missing NEXT_PUBLIC_PADDLE_CLIENT_TOKEN — the UI shows
 * "payment temporarily unavailable". There is no manual/WhatsApp payment
 * fallback of any kind.
 *
 * SECURITY: PADDLE_API_KEY must NEVER appear in NEXT_PUBLIC_* variables or
 * any client-side code. All Paddle server-side API calls go through the
 * backend proxy. The only public Paddle key is NEXT_PUBLIC_PADDLE_CLIENT_TOKEN
 * (a read-only Paddle.js token used solely to initialize the checkout widget).
 */

import type { BillingConfig } from "@/lib/api";

/** How the subscription UI should offer the upgrade action. */
export type BillingUiMode = "paddle" | "unavailable";

/**
 * True when the client bundle carries what Paddle.js needs to initialize.
 * The price ID is intentionally NOT required here: the server-owned checkout
 * session response includes `price_id` (resolved from Render env), and
 * NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID is only a fallback.
 */
export function hasPaddleClientConfig(): boolean {
    return !!process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim();
}

/**
 * Resolve the runtime UI mode from the backend billing config.
 *
 *  - backend says Paddle active + client can run Paddle.js → "paddle"
 *  - anything else                                         → "unavailable"
 *
 * "unavailable" is the fail-closed state: no checkout is offered. A backend
 * config reporting Paddle inactive (e.g. a stale `billing_mode: "manual"`)
 * also fails closed — Paddle is the only billing path.
 */
export function resolveBillingUiMode(
    config: Pick<BillingConfig, "billing_mode" | "paddle_active"> | null,
): BillingUiMode {
    if (config?.paddle_active && hasPaddleClientConfig()) return "paddle";
    return "unavailable";
}

/**
 * Build the WhatsApp deep-link for the sidebar's quick-support entry.
 * Support contact only — carries no payment or subscription-activation copy.
 */
export function buildWhatsAppSupportUrl(): string {
    const raw = process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const number = raw.replace(/\D/g, "");
    const text = "Hi Rico support, I need help with my account.";
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

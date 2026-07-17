/**
 * Billing mode helpers and WhatsApp upgrade URL builder.
 *
 * SOURCE OF TRUTH: the backend's public `GET /api/v1/billing/config`
 * (`billing_mode`, `paddle_active`, `sandbox`) decides at RUNTIME whether the
 * subscription UI offers Paddle checkout or the manual (WhatsApp-assisted)
 * flow — see docs/product/subscription-flow.md. Build-time NEXT_PUBLIC_* vars
 * are only a client-capability check (is Paddle.js initializable?), never the
 * mode decision.
 *
 * FAIL-CLOSED: when the backend says Paddle is active but the client cannot
 * run Paddle.js (missing NEXT_PUBLIC_PADDLE_CLIENT_TOKEN), or when the config
 * cannot be fetched at all, the UI must show "payment temporarily unavailable"
 * — it must NEVER silently fall back to WhatsApp because of a missing
 * credential. Manual mode is only ever an explicit backend decision.
 *
 * SECURITY: PADDLE_API_KEY must NEVER appear in NEXT_PUBLIC_* variables or
 * any client-side code. All Paddle server-side API calls go through the
 * backend proxy. The only public Paddle key is NEXT_PUBLIC_PADDLE_CLIENT_TOKEN
 * (a read-only Paddle.js token used solely to initialize the checkout widget).
 */

import type { BillingConfig } from "@/lib/api";

/** How the subscription UI should offer the upgrade action. */
export type BillingUiMode = "paddle" | "manual" | "unavailable";

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
 *  - backend explicitly says manual (and Paddle inactive)  → "manual"
 *  - config unreachable, or Paddle active but the client is
 *    missing its Paddle.js token, or unknown mode           → "unavailable"
 *
 * "unavailable" is the fail-closed state: no checkout is offered and no
 * WhatsApp fallback is shown, because neither mode was actually decided.
 */
export function resolveBillingUiMode(
    config: Pick<BillingConfig, "billing_mode" | "paddle_active"> | null,
): BillingUiMode {
    if (!config) return "unavailable";
    if (config.paddle_active) {
        return hasPaddleClientConfig() ? "paddle" : "unavailable";
    }
    return config.billing_mode === "manual" ? "manual" : "unavailable";
}

/**
 * Build-time hint only (e.g. Settings' Paddle billing section). Reflects the
 * explicit NEXT_PUBLIC_BILLING_MODE value and nothing else — missing Paddle
 * credentials must NOT flip this to manual (that silent fallback is exactly
 * the bug that put WhatsApp in front of paying users). The subscription
 * checkout CTA must use resolveBillingUiMode() with the runtime config, not
 * this helper.
 */
export function isManualBillingMode(): boolean {
    return process.env.NEXT_PUBLIC_BILLING_MODE?.trim() === "manual";
}

export function isPaddleBillingMode(): boolean {
    return !isManualBillingMode();
}

/**
 * Build the WhatsApp deep-link for the upgrade flow. Used ONLY when the
 * backend config explicitly reports manual billing mode.
 */
export function buildWhatsAppUpgradeUrl(
    plan?: string,
    email?: string | null,
    priceMonthly?: number | null,
    currency: string = "USD",
): string {
    const raw = process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const number = raw.replace(/\D/g, "");
    const planLabel = plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : "Pro";
    const priceStr = priceMonthly ? ` (${currency} ${priceMonthly.toFixed(2)}/month)` : "";
    const emailStr = email ? ` ${email}` : "";
    const text = `I want to upgrade to Rico ${planLabel}${priceStr}. My account email is:${emailStr}`;
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

/**
 * Build the WhatsApp deep-link for support requests.
 */
export function buildWhatsAppManageUrl(): string {
    const raw = process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const number = raw.replace(/\D/g, "");
    const text = "I want to manage my Rico subscription. My account email is:";
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

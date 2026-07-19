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
import { getPaddleTokenEnvironment } from "@/lib/paddle";

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
 *  - backend says Paddle active + client can run Paddle.js
 *    + client/backend Paddle environments agree                → "paddle"
 *  - anything else                                             → "unavailable"
 *
 * "unavailable" is the fail-closed state: no checkout is offered. A backend
 * config reporting Paddle inactive (e.g. a stale `billing_mode: "manual"`)
 * also fails closed — Paddle is the only billing path.
 *
 * Environment cross-check: the backend's `sandbox` flag reflects the
 * environment of the server-side credentials (price ID, API key, webhook
 * secret); the client token's `test_`/`live_` prefix reflects the Paddle.js
 * environment. A mismatched pair can only fail at purchase time with
 * Paddle's opaque "Something went wrong" overlay, so it is refused up
 * front. The check is skipped when the backend omits `sandbox` (older
 * backend) or the token prefix is unrecognized.
 */
export function resolveBillingUiMode(
    config:
        | (Pick<BillingConfig, "billing_mode" | "paddle_active"> &
              Partial<Pick<BillingConfig, "sandbox">>)
        | null,
): BillingUiMode {
    if (!config?.paddle_active || !hasPaddleClientConfig()) return "unavailable";
    const tokenEnv = getPaddleTokenEnvironment();
    if (typeof config.sandbox === "boolean" && tokenEnv !== null) {
        const backendEnv = config.sandbox ? "sandbox" : "production";
        if (tokenEnv !== backendEnv) {
            console.error(
                `[billing] Paddle environment mismatch: backend credentials are ` +
                `${backendEnv} (PADDLE_SANDBOX) but the client token is ${tokenEnv} — ` +
                `failing closed. Align Render and Vercel Paddle env vars.`,
            );
            return "unavailable";
        }
    }
    return "paddle";
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

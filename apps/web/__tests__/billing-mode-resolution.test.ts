/**
 * billing-mode-resolution.test.ts
 *
 * Pins the runtime billing-mode contract in lib/billing.ts:
 *   - the backend GET /api/v1/billing/config decides the mode;
 *   - manual (WhatsApp) is ONLY an explicit backend decision;
 *   - missing Paddle client credentials fail CLOSED ("unavailable"),
 *     they never silently flip the UI to WhatsApp;
 *   - build-time isManualBillingMode() reflects only the explicit
 *     NEXT_PUBLIC_BILLING_MODE value, never missing credentials.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
    buildWhatsAppUpgradeUrl,
    hasPaddleClientConfig,
    isManualBillingMode,
    isPaddleBillingMode,
    resolveBillingUiMode,
} from "@/lib/billing";

afterEach(() => {
    vi.unstubAllEnvs();
});

describe("resolveBillingUiMode — runtime backend config is the source of truth", () => {
    it("paddle_active + client token present → paddle", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token");
        expect(resolveBillingUiMode({ billing_mode: "paddle", paddle_active: true })).toBe("paddle");
    });

    it("paddle_active but client token missing → unavailable (fail closed, never manual)", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "");
        expect(resolveBillingUiMode({ billing_mode: "paddle", paddle_active: true })).toBe("unavailable");
    });

    it("explicit backend manual mode → manual", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "");
        expect(resolveBillingUiMode({ billing_mode: "manual", paddle_active: false })).toBe("manual");
    });

    it("config unreachable (null) → unavailable, not manual", () => {
        expect(resolveBillingUiMode(null)).toBe("unavailable");
    });

    it("unknown mode with Paddle inactive → unavailable, not manual", () => {
        expect(resolveBillingUiMode({ billing_mode: "stripe", paddle_active: false })).toBe("unavailable");
    });
});

describe("hasPaddleClientConfig — client capability only", () => {
    it("true when NEXT_PUBLIC_PADDLE_CLIENT_TOKEN is set", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "tok");
        expect(hasPaddleClientConfig()).toBe(true);
    });

    it("false when the token is missing or blank", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "  ");
        expect(hasPaddleClientConfig()).toBe(false);
    });
});

describe("isManualBillingMode — explicit env only, no credential fallback", () => {
    it("manual only when NEXT_PUBLIC_BILLING_MODE=manual", () => {
        vi.stubEnv("NEXT_PUBLIC_BILLING_MODE", "manual");
        expect(isManualBillingMode()).toBe(true);
        expect(isPaddleBillingMode()).toBe(false);
    });

    it("missing Paddle credentials do NOT flip the build-time mode to manual", () => {
        vi.stubEnv("NEXT_PUBLIC_BILLING_MODE", "paddle");
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "");
        vi.stubEnv("NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID", "");
        expect(isManualBillingMode()).toBe(false);
        expect(isPaddleBillingMode()).toBe(true);
    });
});

describe("buildWhatsAppUpgradeUrl — currency matches the plan", () => {
    it("labels the price with the plan currency (USD), two decimals", () => {
        const url = buildWhatsAppUpgradeUrl("pro", "u@rico.ai", 21.5, "USD");
        const text = decodeURIComponent(url.split("text=")[1]);
        expect(text).toContain("(USD 21.50/month)");
        expect(text).not.toContain("AED");
    });
});

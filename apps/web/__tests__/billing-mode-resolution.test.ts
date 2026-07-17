/**
 * billing-mode-resolution.test.ts
 *
 * Pins the runtime billing-mode contract in lib/billing.ts:
 *   - Paddle is the ONLY billing path (owner directive 2026-07-17);
 *   - the backend GET /api/v1/billing/config decides whether Paddle
 *     checkout is offered;
 *   - every non-Paddle state fails CLOSED ("unavailable") — a legacy
 *     "manual" backend config, an unreachable config, or missing Paddle
 *     client credentials must never surface a WhatsApp/manual payment path;
 *   - the support deep-link carries no payment or activation copy.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
    buildWhatsAppSupportUrl,
    hasPaddleClientConfig,
    resolveBillingUiMode,
} from "@/lib/billing";

afterEach(() => {
    vi.unstubAllEnvs();
});

describe("resolveBillingUiMode — Paddle-only, everything else fails closed", () => {
    it("paddle_active + client token present → paddle", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token");
        expect(resolveBillingUiMode({ billing_mode: "paddle", paddle_active: true })).toBe("paddle");
    });

    it("paddle_active but client token missing → unavailable (fail closed)", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "");
        expect(resolveBillingUiMode({ billing_mode: "paddle", paddle_active: true })).toBe("unavailable");
    });

    it("legacy explicit backend manual mode → unavailable, never a WhatsApp flow", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token");
        expect(resolveBillingUiMode({ billing_mode: "manual", paddle_active: false })).toBe("unavailable");
    });

    it("config unreachable (null) → unavailable", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token");
        expect(resolveBillingUiMode(null)).toBe("unavailable");
    });

    it("unknown mode with Paddle inactive → unavailable", () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token");
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

describe("no manual-payment exports remain in lib/billing", () => {
    it("the module exposes no upgrade/manage WhatsApp builders or manual-mode helpers", async () => {
        const billing = await import("@/lib/billing");
        expect(billing).not.toHaveProperty("buildWhatsAppUpgradeUrl");
        expect(billing).not.toHaveProperty("buildWhatsAppManageUrl");
        expect(billing).not.toHaveProperty("isManualBillingMode");
        expect(billing).not.toHaveProperty("isPaddleBillingMode");
    });
});

describe("buildWhatsAppSupportUrl — support contact only", () => {
    it("prefills a generic support message with no payment or activation copy", () => {
        const url = buildWhatsAppSupportUrl();
        expect(url).toMatch(/^https:\/\/wa\.me\/\d+\?text=/);
        const text = decodeURIComponent(url.split("text=")[1]).toLowerCase();
        for (const banned of ["pay", "upgrade", "subscription", "activate", "receipt", "bank", "transfer", "plan", "usd", "aed"]) {
            expect(text).not.toContain(banned);
        }
    });
});

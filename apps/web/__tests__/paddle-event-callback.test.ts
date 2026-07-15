/**
 * Paddle.js v2 event-callback contract — regression for the #1018 review finding.
 *
 * Paddle.js v2 only honors `eventCallback` at Setup/Initialize time; passing it
 * to `Checkout.open()` is silently ignored, which left the openPaddleCheckout
 * Promise unsettled forever (upgrade button stuck on its spinner).
 *
 * This suite pins the corrected contract:
 *   1. Setup receives the event dispatcher; Checkout.open() gets NO eventCallback.
 *   2. checkout.error  → the checkout Promise rejects with Paddle's error detail.
 *   3. checkout.completed → resolves.
 *   4. checkout.closed    → resolves quietly (user dismissal is not an error).
 *   5. A synchronous Checkout.open throw rejects (no hang).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
    _resetInitPromise,
    openPaddleCheckout,
    type PaddleCheckoutOptions,
    type PaddleEventDetail,
    type PaddleInstance,
} from "@/lib/paddle";

type EventCallback = (event: PaddleEventDetail) => void;

let setupOpts: { token: string; eventCallback?: EventCallback } | undefined;
let checkoutOpts: (PaddleCheckoutOptions & { eventCallback?: unknown }) | undefined;
const checkoutOpen = vi.fn((opts: PaddleCheckoutOptions) => {
    checkoutOpts = opts as PaddleCheckoutOptions & { eventCallback?: unknown };
});

function stubPaddle(): void {
    const paddle: PaddleInstance = {
        Setup: (opts) => {
            setupOpts = opts;
        },
        Checkout: { open: checkoutOpen },
        Environment: { set: vi.fn() },
    };
    (window as unknown as { Paddle?: PaddleInstance }).Paddle = paddle;
}

/** Fire a synthetic Paddle event through the Setup-registered dispatcher. */
function firePaddleEvent(event: PaddleEventDetail): void {
    expect(setupOpts?.eventCallback, "Setup must register the event dispatcher").toBeTypeOf("function");
    setupOpts!.eventCallback!(event);
}

beforeEach(() => {
    vi.spyOn(console, "debug").mockImplementation(() => undefined);
    vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token");
    setupOpts = undefined;
    checkoutOpts = undefined;
    checkoutOpen.mockClear();
    _resetInitPromise();
    stubPaddle();
});

afterEach(() => {
    delete (window as unknown as { Paddle?: PaddleInstance }).Paddle;
    _resetInitPromise();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
});

describe("openPaddleCheckout — Paddle.js v2 event contract", () => {
    it("registers eventCallback at Setup and passes none to Checkout.open()", async () => {
        const pending = openPaddleCheckout("pri_test", "sess_token_123", "u@rico.ai", "en");

        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));
        expect(setupOpts?.eventCallback).toBeTypeOf("function");
        expect(checkoutOpts && "eventCallback" in checkoutOpts && checkoutOpts.eventCallback).toBeFalsy();
        // The server-owned session token still travels via customData.
        expect(checkoutOpts?.customData).toEqual({ checkout_session_id: "sess_token_123" });

        firePaddleEvent({ name: "checkout.closed" });
        await expect(pending).resolves.toBeUndefined();
    });

    it("rejects with Paddle's own detail on checkout.error", async () => {
        const pending = openPaddleCheckout("pri_test", "sess_token_123", null, "ar");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        firePaddleEvent({ name: "checkout.error", data: { message: "price not active" } });
        await expect(pending).rejects.toThrow("price not active");
    });

    it("resolves on checkout.completed", async () => {
        const pending = openPaddleCheckout("pri_test", "sess_token_123", "u@rico.ai", "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        firePaddleEvent({ name: "checkout.completed" });
        await expect(pending).resolves.toBeUndefined();
    });

    it("does not log sensitive data (token prefix, session prefix, email, raw events)", async () => {
        const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => undefined);

        const pending = openPaddleCheckout("pri_test", "sess_token_123", "u@rico.ai", "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        firePaddleEvent({ name: "checkout.completed" });
        await expect(pending).resolves.toBeUndefined();

        expect(debugSpy).not.toHaveBeenCalled();
    });

    it("rejects instead of hanging when Checkout.open throws synchronously", async () => {
        checkoutOpen.mockImplementationOnce(() => {
            throw new Error("paddle exploded");
        });
        await expect(openPaddleCheckout("pri_test", "sess_token_123", null, "en")).rejects.toThrow(
            "paddle exploded",
        );
    });

    it("rejects when NEXT_PUBLIC_PADDLE_CLIENT_TOKEN is not set (fail-closed)", async () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "");
        _resetInitPromise();

        await expect(openPaddleCheckout("pri_test", "sess_token_123", null, "en")).rejects.toThrow(
            "NEXT_PUBLIC_PADDLE_CLIENT_TOKEN is not set",
        );
    });
});

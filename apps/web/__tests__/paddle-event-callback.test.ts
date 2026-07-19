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
 *   3. checkout.completed → resolves "completed".
 *   4. checkout.closed    → resolves "closed" quietly (dismissal is not an error).
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
        await expect(pending).resolves.toBe("closed");
    });

    it("rejects with Paddle's own detail on checkout.error", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        const pending = openPaddleCheckout("pri_test", "sess_token_123", null, "ar");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        firePaddleEvent({ name: "checkout.error", data: { message: "price not active" } });
        await expect(pending).rejects.toThrow("price not active");
        errSpy.mockRestore();
    });

    it("surfaces the exact Paddle error code from the v2 top-level error object", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        const pending = openPaddleCheckout("pri_test", "sess_token_123", null, "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        // Paddle.js v2 checkout.error shape: detail lives in event.error, not event.data.
        firePaddleEvent({
            name: "checkout.error",
            error: {
                type: "request_error",
                code: "transaction_default_checkout_url_not_set",
                detail: "checkout URL not approved for this domain",
            },
        });
        await expect(pending).rejects.toThrow(
            "checkout URL not approved for this domain [transaction_default_checkout_url_not_set]",
        );
        // The exact code must be logged for production diagnosis.
        expect(errSpy).toHaveBeenCalledWith(
            "[paddle] checkout.error",
            expect.objectContaining({ code: "transaction_default_checkout_url_not_set" }),
        );
        // Privacy pin: the logged payload carries ONLY {type, code, detail} —
        // never the raw event, customer email, or customData.
        const loggedPayload = errSpy.mock.calls.find(
            (c) => c[0] === "[paddle] checkout.error",
        )?.[1] as Record<string, unknown>;
        expect(Object.keys(loggedPayload).sort()).toEqual(["code", "detail", "type"]);
        errSpy.mockRestore();
    });

    it("never logs customer data on checkout.error (payload with customer fields)", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        const pending = openPaddleCheckout("pri_test", "sess_secret_tok", "user@rico.ai", "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        // Even if Paddle's event data carries customer fields, they must not
        // reach the console — only the error triple is logged.
        firePaddleEvent({
            name: "checkout.error",
            data: {
                customer: { email: "user@rico.ai" },
                custom_data: { checkout_session_id: "sess_secret_tok" },
            },
            error: { type: "request_error", code: "payment_declined", detail: "card declined" },
        });
        await expect(pending).rejects.toThrow("card declined [payment_declined]");

        const allLogged = JSON.stringify(errSpy.mock.calls);
        expect(allLogged).not.toContain("user@rico.ai");
        expect(allLogged).not.toContain("sess_secret_tok");
        errSpy.mockRestore();
    });

    it("redacts email + session token embedded in error.detail itself, keeping exact type/code", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        const pending = openPaddleCheckout("pri_test", "sess_leaky_tok_42", "cust@rico.ai", "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        // Worst case: Paddle's free-text detail echoes customer input.
        firePaddleEvent({
            name: "checkout.error",
            error: {
                type: "request_error",
                code: "checkout_customer_invalid",
                detail: "customer cust@rico.ai with session sess_leaky_tok_42 was rejected",
            },
        });

        // The rejection (toast source) keeps the exact code but neither secret.
        const err = await pending.catch((e: Error) => e);
        expect(err).toBeInstanceOf(Error);
        expect((err as Error).message).toContain("[checkout_customer_invalid]");
        expect((err as Error).message).toContain("[redacted-email]");
        expect((err as Error).message).toContain("[redacted-session]");
        expect((err as Error).message).not.toContain("cust@rico.ai");
        expect((err as Error).message).not.toContain("sess_leaky_tok_42");

        // The console log preserves exact type/code and redacts both secrets.
        const logged = errSpy.mock.calls.find((c) => c[0] === "[paddle] checkout.error")?.[1] as {
            type?: string; code?: string; detail?: string;
        };
        expect(logged.type).toBe("request_error");
        expect(logged.code).toBe("checkout_customer_invalid");
        const allLogged = JSON.stringify(errSpy.mock.calls);
        expect(allLogged).not.toContain("cust@rico.ai");
        expect(allLogged).not.toContain("sess_leaky_tok_42");
        errSpy.mockRestore();
    });

    it("resolves with \"completed\" on checkout.completed", async () => {
        const pending = openPaddleCheckout("pri_test", "sess_token_123", "u@rico.ai", "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        firePaddleEvent({ name: "checkout.completed" });
        await expect(pending).resolves.toBe("completed");
    });

    it("does not log sensitive data (token prefix, session prefix, email, raw events)", async () => {
        const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => undefined);

        const pending = openPaddleCheckout("pri_test", "sess_token_123", "u@rico.ai", "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));

        firePaddleEvent({ name: "checkout.completed" });
        await expect(pending).resolves.toBe("completed");

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

describe("initPaddle — environment derived from the client token prefix", () => {
    // The token prefix is authoritative: a token only works in its own
    // environment. NEXT_PUBLIC_PADDLE_SANDBOX is a fallback for unrecognized
    // prefixes only, and a contradiction logs a config error.
    let envSet: ReturnType<typeof vi.fn>;

    function stubPaddleWithEnvSpy(): void {
        envSet = vi.fn();
        const paddle: PaddleInstance = {
            Setup: (opts) => { setupOpts = opts; },
            Checkout: { open: checkoutOpen },
            Environment: { set: envSet },
        };
        (window as unknown as { Paddle?: PaddleInstance }).Paddle = paddle;
    }

    it("test_ token → sandbox environment even when the flag says live", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_tok");
        vi.stubEnv("NEXT_PUBLIC_PADDLE_SANDBOX", "false");
        _resetInitPromise();
        stubPaddleWithEnvSpy();

        const pending = openPaddleCheckout("pri_test", "sess_1", null, "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));
        expect(envSet).toHaveBeenCalledWith("sandbox");
        expect(errSpy).toHaveBeenCalled(); // contradiction is reported
        firePaddleEvent({ name: "checkout.closed" });
        await pending;
        errSpy.mockRestore();
    });

    it("live_ token → production environment even when the flag says sandbox", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "live_tok");
        vi.stubEnv("NEXT_PUBLIC_PADDLE_SANDBOX", "true");
        _resetInitPromise();
        stubPaddleWithEnvSpy();

        const pending = openPaddleCheckout("pri_live", "sess_2", null, "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));
        expect(envSet).not.toHaveBeenCalled();
        expect(errSpy).toHaveBeenCalled(); // contradiction is reported
        firePaddleEvent({ name: "checkout.closed" });
        await pending;
        errSpy.mockRestore();
    });

    it("unrecognized prefix → falls back to the NEXT_PUBLIC_PADDLE_SANDBOX flag", async () => {
        vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "opaque_tok");
        vi.stubEnv("NEXT_PUBLIC_PADDLE_SANDBOX", "true");
        _resetInitPromise();
        stubPaddleWithEnvSpy();

        const pending = openPaddleCheckout("pri_x", "sess_3", null, "en");
        await vi.waitFor(() => expect(checkoutOpen).toHaveBeenCalledTimes(1));
        expect(envSet).toHaveBeenCalledWith("sandbox");
        firePaddleEvent({ name: "checkout.closed" });
        await pending;
    });
});

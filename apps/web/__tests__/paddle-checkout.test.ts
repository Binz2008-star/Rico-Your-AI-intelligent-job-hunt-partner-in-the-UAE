import { _resetInitPromise, initPaddle, openPaddleCheckout } from "@/lib/paddle";
import { beforeEach, describe, expect, it, vi } from "vitest";

describe("paddle.ts checkout error callback", () => {
    let script: HTMLScriptElement | null = null;
    let paddle: {
        Setup: ReturnType<typeof vi.fn>;
        Environment: { set: ReturnType<typeof vi.fn> };
        Checkout: { open: ReturnType<typeof vi.fn> };
    };

    beforeEach(() => {
        vi.resetAllMocks();
        _resetInitPromise();
        delete (window as { Paddle?: unknown }).Paddle;

        // Capture the script element created by initPaddle so tests can fire onload.
        script = null;
        const originalCreateElement = document.createElement.bind(document);
        vi.spyOn(document, "createElement").mockImplementation((tag: string, options?: any) => {
            const el = originalCreateElement(tag, options);
            if (tag === "script") {
                script = el as HTMLScriptElement;
            }
            return el;
        });

        // Minimal Paddle.js mock. Checkout.open records the eventCallback for direct access.
        paddle = {
            Setup: vi.fn(),
            Environment: { set: vi.fn() },
            Checkout: { open: vi.fn() },
        };
    });

    async function triggerPaddleEvent(event: { name: string; data?: Record<string, unknown> }) {
        await vi.waitFor(() => expect(paddle.Checkout.open).toHaveBeenCalled());
        const opts = paddle.Checkout.open.mock.calls[0]?.[0] as { eventCallback?: (event: { name: string; data?: Record<string, unknown> }) => void } | undefined;
        if (!opts?.eventCallback) throw new Error("openPaddleCheckout did not register an eventCallback");
        opts.eventCallback(event);
    }

    it("loads Paddle.js, sets sandbox environment, and resolves initPaddle", async () => {
        const initPromise = initPaddle();
        expect(script).not.toBeNull();
        expect(script?.src).toBe("https://cdn.paddle.com/paddle/v2/paddle.js");

        (window as { Paddle?: unknown }).Paddle = paddle;
        script?.onload?.(new Event("load"));

        const instance = await initPromise;
        expect(instance).toBe(paddle);
        expect(paddle.Environment.set).toHaveBeenCalledWith("sandbox");
        expect(paddle.Setup).toHaveBeenCalledWith({ token: "test_1a1754e60e504b4a93b1efc9604" });
    });

    it("openPaddleCheckout resolves on checkout.completed", async () => {
        (window as { Paddle?: unknown }).Paddle = paddle;

        const openPromise = openPaddleCheckout("pri_test", "sess_test", "user@example.com", "en");

        await triggerPaddleEvent({ name: "checkout.completed" });

        await expect(openPromise).resolves.toBeUndefined();
    });

    it("openPaddleCheckout resolves quietly on checkout.closed", async () => {
        (window as { Paddle?: unknown }).Paddle = paddle;

        const openPromise = openPaddleCheckout("pri_test", "sess_test", null, "ar");

        await triggerPaddleEvent({ name: "checkout.closed" });

        await expect(openPromise).resolves.toBeUndefined();
    });

    it("openPaddleCheckout rejects with Paddle's message on checkout.error", async () => {
        (window as { Paddle?: unknown }).Paddle = paddle;

        const openPromise = openPaddleCheckout("pri_test", "sess_test", "user@example.com", "en");

        await triggerPaddleEvent({
            name: "checkout.error",
            data: { message: "Invalid price ID" },
        });

        await expect(openPromise).rejects.toThrow("Invalid price ID");
    });

    it("openPaddleCheckout rejects when Checkout.open throws synchronously", async () => {
        (window as { Paddle?: unknown }).Paddle = paddle;
        paddle.Checkout.open.mockImplementation(() => {
            throw new Error("Paddle script not ready");
        });

        await expect(openPaddleCheckout("pri_test", "sess_test", "user@example.com", "en"))
            .rejects.toThrow("Paddle script not ready");
    });

    it("openPaddleCheckout rejects with fallback error when checkout.error has no message", async () => {
        (window as { Paddle?: unknown }).Paddle = paddle;

        const openPromise = openPaddleCheckout("pri_test", "sess_test", "user@example.com", "en");

        await triggerPaddleEvent({
            name: "checkout.error",
            data: {},
        });

        await expect(openPromise).rejects.toThrow("Paddle checkout error");
    });

    it("never logs emails, tokens, or token fragments during init + checkout", async () => {
        const consoleSpies = [
            vi.spyOn(console, "debug"),
            vi.spyOn(console, "log"),
            vi.spyOn(console, "info"),
        ];
        (window as { Paddle?: unknown }).Paddle = paddle;

        const openPromise = openPaddleCheckout("pri_test", "sess_secret_token_value", "user@example.com", "en");
        await triggerPaddleEvent({ name: "checkout.completed" });
        await openPromise;

        for (const spy of consoleSpies) {
            const logged = spy.mock.calls.flat().map(String).join(" ");
            expect(logged).not.toContain("user@example.com");
            expect(logged).not.toContain("sess_secret");
            expect(logged).not.toContain("test_1a1754e6");
        }
    });
});

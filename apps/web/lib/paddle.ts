/**
 * Paddle.js client-side initialization and overlay checkout helpers.
 *
 * SECURITY BOUNDARY:
 *   - NEXT_PUBLIC_PADDLE_CLIENT_TOKEN  → safe to expose (read-only Paddle.js token)
 *   - PADDLE_API_KEY                   → server-side only, NEVER here
 *
 * Paddle.js is loaded lazily on first call to initPaddle() so it does not
 * block the initial page render.
 */

declare global {
    interface Window {
        Paddle?: PaddleInstance;
    }
}

export interface PaddleEventDetail {
    name: string;
    data?: Record<string, unknown>;
    /** Paddle.js v2 delivers checkout.error detail here — NOT inside data. */
    error?: {
        type?: string;
        code?: string;
        detail?: string;
        documentation_url?: string;
    };
}

export interface PaddleInstance {
    Setup: (opts: {
        token: string;
        pwCustomer?: { email?: string };
        /** Paddle.js v2 only honors eventCallback here (Setup/Initialize) — never per-checkout. */
        eventCallback?: (event: PaddleEventDetail) => void;
    }) => void;
    Checkout: {
        open: (opts: PaddleCheckoutOptions) => void;
    };
    Environment: {
        set: (env: "sandbox" | "production") => void;
    };
}

export interface PaddleCheckoutOptions {
    items: Array<{ priceId: string; quantity: number }>;
    customData?: Record<string, string>;
    customer?: { email?: string };
    settings?: {
        displayMode?: "overlay" | "inline";
        theme?: "light" | "dark";
        locale?: string;
    };
    // NOTE: no eventCallback here. Paddle.js v2 silently ignores an
    // eventCallback passed to Checkout.open() — events only flow through the
    // callback registered at Setup time (see dispatchPaddleEvent below).
}

let _initPromise: Promise<PaddleInstance> | null = null;

/** Paddle environment a client-side token belongs to. */
export type PaddleEnvironment = "sandbox" | "production";

/**
 * Derive the Paddle environment from the client token itself.
 * Paddle client-side tokens are prefixed `test_` (sandbox) or `live_`
 * (production) — a token only ever works in its own environment, so the
 * prefix is authoritative. Returns null when the token is missing or has an
 * unrecognized prefix.
 */
export function getPaddleTokenEnvironment(): PaddleEnvironment | null {
    const token = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim();
    if (!token) return null;
    if (token.startsWith("test_")) return "sandbox";
    if (token.startsWith("live_")) return "production";
    return null;
}

/**
 * The listener for the currently open overlay checkout. Paddle renders one
 * overlay at a time, so a single active listener is sufficient. Registered by
 * openPaddleCheckout(); events arrive via the Setup-level dispatchPaddleEvent.
 */
let _activeCheckoutListener: ((event: PaddleEventDetail) => void) | null = null;

/**
 * Global Paddle.js v2 event dispatcher, registered once at Setup time.
 * Passing eventCallback to Checkout.open() is silently ignored by Paddle.js v2
 * (the checkout Promise would never settle and the upgrade button would hang),
 * so this is the only supported event path.
 */
function dispatchPaddleEvent(event: PaddleEventDetail): void {
    _activeCheckoutListener?.(event);
}

/** Exposed for unit tests only — resets the cached Paddle init promise. */
export function _resetInitPromise(): void {
    _initPromise = null;
    _activeCheckoutListener = null;
}

/**
 * Lazily load Paddle.js and initialize with the client token.
 * Safe to call multiple times — resolves the same promise on subsequent calls.
 */
export function initPaddle(): Promise<PaddleInstance> {
    if (_initPromise) return _initPromise;

    _initPromise = new Promise((resolve, reject) => {
        if (typeof window === "undefined") {
            reject(new Error("initPaddle must be called client-side"));
            return;
        }

        const token = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim();
        if (!token) {
            reject(new Error("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN is not set — Paddle checkout cannot initialize."));
            return;
        }

        const configure = (paddle: PaddleInstance): void => {
            // The token prefix (test_/live_) is authoritative: a token only
            // works in its own environment, so initializing against the flag
            // when the two disagree can only produce Paddle's opaque
            // "Something went wrong" overlay at purchase time.
            const flagSandbox =
                (process.env.NEXT_PUBLIC_PADDLE_SANDBOX ?? "true").trim().toLowerCase() !== "false";
            const tokenEnv = getPaddleTokenEnvironment();
            const sandbox = tokenEnv !== null ? tokenEnv === "sandbox" : flagSandbox;
            if (tokenEnv !== null && (tokenEnv === "sandbox") !== flagSandbox) {
                console.error(
                    `[paddle] NEXT_PUBLIC_PADDLE_SANDBOX=${flagSandbox} contradicts the ` +
                    `client token prefix (${token.slice(0, 5)}…) — using the token's ` +
                    `environment (${tokenEnv}). Align the Vercel env vars.`,
                );
            }
            if (sandbox) {
                paddle.Environment.set("sandbox");
            }

            // eventCallback MUST be registered here — Paddle.js v2 ignores it on
            // Checkout.open(), which would leave every checkout Promise unsettled.
            paddle.Setup({ token, eventCallback: dispatchPaddleEvent });
        };

        if (window.Paddle) {
            // Paddle.js already present but not configured by us — Setup is still
            // required so the token and the event dispatcher are registered.
            configure(window.Paddle);
            resolve(window.Paddle);
            return;
        }

        const script = document.createElement("script");
        script.src = "https://cdn.paddle.com/paddle/v2/paddle.js";
        script.async = true;
        script.onload = () => {
            const paddle = window.Paddle;
            if (!paddle) {
                reject(new Error("Paddle.js loaded but window.Paddle is undefined"));
                return;
            }
            configure(paddle);
            resolve(paddle);
        };
        script.onerror = () => reject(new Error("Failed to load Paddle.js"));
        document.head.appendChild(script);
    });

    return _initPromise;
}

/** Terminal outcome of an overlay checkout that did not error. */
export type PaddleCheckoutOutcome = "completed" | "closed";

/**
 * Open the Paddle overlay checkout for a given price ID.
 *
 * Resolves "completed" when Paddle reports checkout.completed and "closed"
 * when the user dismisses the overlay, so callers can re-confirm the
 * subscription with the backend only after a real completion. Rejects if
 * Paddle fires a checkout.error event, so callers can surface a meaningful
 * Rico error toast instead of the generic Paddle "Something went wrong"
 * overlay.
 *
 * SECURITY: checkoutSessionId must be a server-owned token from
 * createPaddleCheckoutSession() (POST /api/v1/billing/paddle/checkout-session),
 * passed as customData.checkout_session_id. The webhook resolves the Rico user
 * via that server-side record — never via a browser-supplied user_id.
 *
 * @param priceId           - Paddle price ID (e.g. NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID)
 * @param checkoutSessionId - Server-owned session token from createPaddleCheckoutSession()
 * @param userEmail         - Pre-fill customer email in checkout
 * @param language          - 'en' | 'ar' — sets checkout locale
 */
export async function openPaddleCheckout(
    priceId: string,
    checkoutSessionId: string,
    userEmail?: string | null,
    language: "en" | "ar" = "en",
): Promise<PaddleCheckoutOutcome> {
    const paddle = await initPaddle();

    return new Promise<PaddleCheckoutOutcome>((resolve, reject) => {
        const settle = (fn: () => void): void => {
            _activeCheckoutListener = null;
            fn();
        };

        // Events arrive through the Setup-level dispatcher (dispatchPaddleEvent);
        // Paddle.js v2 ignores eventCallback on Checkout.open().
        _activeCheckoutListener = (event: PaddleEventDetail) => {
            if (event.name === "checkout.error") {
                // Paddle.js v2 carries the failure in the TOP-LEVEL error
                // object ({type, code, detail}); data.message/data.error are
                // legacy fallbacks. Keep the exact code — it is the only way
                // to distinguish env/price/domain misconfiguration from a
                // payment problem.
                const paddleErr = event.error;
                const detail =
                    paddleErr?.detail ??
                    (event.data?.message as string | undefined) ??
                    (event.data?.error as string | undefined) ??
                    "Paddle checkout error";
                const message = paddleErr?.code ? `${detail} [${paddleErr.code}]` : detail;
                // No customer PII lives in the Paddle error object — log it in
                // full so production failures carry an exact code, not just
                // "Something went wrong".
                console.error("[paddle] checkout.error", {
                    type: paddleErr?.type,
                    code: paddleErr?.code,
                    detail,
                });
                settle(() => reject(new Error(message)));
            } else if (event.name === "checkout.completed") {
                settle(() => resolve("completed"));
            } else if (event.name === "checkout.closed") {
                // User dismissed — not an error; resolve quietly.
                settle(() => resolve("closed"));
            }
        };

        try {
            paddle.Checkout.open({
                items: [{ priceId, quantity: 1 }],
                customData: { checkout_session_id: checkoutSessionId },
                customer: userEmail ? { email: userEmail } : undefined,
                settings: {
                    displayMode: "overlay",
                    theme: "dark",
                    locale: language === "ar" ? "ar" : "en",
                },
            });
        } catch (err) {
            settle(() => reject(err instanceof Error ? err : new Error(String(err))));
        }
    });
}

/**
 * Return the Paddle price ID for the single Rico Monthly plan.
 * Returns null if NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID is not set —
 * callers must handle null and show a "not configured" message.
 */
export function getPaddlePriceId(): string | null {
    return process.env.NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID?.trim() || null;
}

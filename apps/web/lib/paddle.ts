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

const DEFAULT_SANDBOX_CLIENT_TOKEN = "test_1a1754e60e504b4a93b1efc9604";
const DEFAULT_SANDBOX_PRICE_ID = "pri_01kxer8h278hvw37ec59yg73hg";

declare global {
    interface Window {
        Paddle?: PaddleInstance;
    }
}

export interface PaddleEventDetail {
    name: string;
    data?: Record<string, unknown>;
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

        const token = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim() || DEFAULT_SANDBOX_CLIENT_TOKEN;

        const configure = (paddle: PaddleInstance): void => {
            const sandbox =
                (process.env.NEXT_PUBLIC_PADDLE_SANDBOX ?? "true").trim().toLowerCase() !== "false";
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

/**
 * Open the Paddle overlay checkout for a given price ID.
 *
 * Returns a Promise that rejects if Paddle fires a checkout.error event,
 * so callers can surface a meaningful Rico error toast instead of the generic
 * Paddle "Something went wrong" overlay.
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
): Promise<void> {
    const paddle = await initPaddle();

    return new Promise<void>((resolve, reject) => {
        const settle = (fn: () => void): void => {
            _activeCheckoutListener = null;
            fn();
        };

        // Events arrive through the Setup-level dispatcher (dispatchPaddleEvent);
        // Paddle.js v2 ignores eventCallback on Checkout.open().
        _activeCheckoutListener = (event: PaddleEventDetail) => {
            if (event.name === "checkout.error") {
                const detail =
                    (event.data?.message as string | undefined) ??
                    (event.data?.error as string | undefined) ??
                    "Paddle checkout error";
                settle(() => reject(new Error(detail)));
            } else if (event.name === "checkout.completed") {
                settle(resolve);
            } else if (event.name === "checkout.closed") {
                // User dismissed — not an error; resolve quietly.
                settle(resolve);
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
 * Return the Paddle price ID for the single Rico Monthly Sandbox plan.
 * A Vercel environment value overrides the deployed Sandbox default.
 */
export function getPaddlePriceId(): string | null {
    return process.env.NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID?.trim() || DEFAULT_SANDBOX_PRICE_ID;
}

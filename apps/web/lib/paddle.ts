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

export interface PaddleInstance {
    Setup: (opts: { token: string; pwCustomer?: { email?: string } }) => void;
    Checkout: {
        open: (opts: PaddleCheckoutOptions) => void;
    };
    Environment: {
        set: (env: "sandbox" | "production") => void;
    };
}

export interface PaddleEventDetail {
    name: string;
    data?: Record<string, unknown>;
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
    /** Paddle v2 event callback — use to capture checkout.error and checkout.closed */
    eventCallback?: (event: PaddleEventDetail) => void;
}

let _initPromise: Promise<PaddleInstance> | null = null;

/** Exposed for unit tests only — resets the cached Paddle init promise. */
export function _resetInitPromise(): void {
    _initPromise = null;
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

        if (window.Paddle) {
            resolve(window.Paddle);
            return;
        }

        const token = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim() || DEFAULT_SANDBOX_CLIENT_TOKEN;

        const script = document.createElement("script");
        script.src = "https://cdn.paddle.com/paddle/v2/paddle.js";
        script.async = true;
        script.onload = () => {
            const paddle = window.Paddle;
            if (!paddle) {
                reject(new Error("Paddle.js loaded but window.Paddle is undefined"));
                return;
            }

            const sandbox =
                (process.env.NEXT_PUBLIC_PADDLE_SANDBOX ?? "true").trim().toLowerCase() !== "false";
            if (sandbox) {
                paddle.Environment.set("sandbox");
            }

            paddle.Setup({ token });
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
        paddle.Checkout.open({
            items: [{ priceId, quantity: 1 }],
            customData: { checkout_session_id: checkoutSessionId },
            customer: userEmail ? { email: userEmail } : undefined,
            settings: {
                displayMode: "overlay",
                theme: "dark",
                locale: language === "ar" ? "ar" : "en",
            },
            eventCallback: (event: PaddleEventDetail) => {
                if (event.name === "checkout.error") {
                    const detail =
                        (event.data?.message as string | undefined) ??
                        (event.data?.error as string | undefined) ??
                        "Paddle checkout error";
                    reject(new Error(detail));
                } else if (event.name === "checkout.completed") {
                    resolve();
                } else if (event.name === "checkout.closed") {
                    // User dismissed — not an error; resolve quietly.
                    resolve();
                }
            },
        });
    });
}

/**
 * Return the Paddle price ID for the single Rico Monthly Sandbox plan.
 * A Vercel environment value overrides the deployed Sandbox default.
 */
export function getPaddlePriceId(): string | null {
    return process.env.NEXT_PUBLIC_PADDLE_PRO_MONTHLY_PRICE_ID?.trim() || DEFAULT_SANDBOX_PRICE_ID;
}

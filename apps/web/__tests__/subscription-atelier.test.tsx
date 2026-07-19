/**
 * subscription-atelier.test.tsx
 *
 * Targeted tests for the /subscription page (WorkspaceShell + runtime billing
 * config).
 *
 * Coverage:
 *  1. WorkspaceShell composition — SubscriptionPage renders WorkspaceShell when
 *     authorized, shows a loader when not.
 *  2. Upgrade button calls createPaddleCheckoutSession first (server session),
 *     then passes the returned session_token to openPaddleCheckout.
 *  3. Paddle checkout.error events surface as a Rico toast error message.
 *  4. Runtime GET /api/v1/billing/config decides whether Paddle checkout is
 *     offered: Paddle-active shows the Paddle CTA (no WhatsApp link anywhere);
 *     every other state — legacy manual config, Paddle-active without a client
 *     token, unreachable config — fails closed ("payment temporarily
 *     unavailable"; Paddle is the only billing path, never WhatsApp).
 *  5. checkout.completed re-confirms with GET /api/v1/subscription/me before
 *     any success is shown; a dismissed overlay does not.
 *  6. Footer says prices are in USD (no "Prices in AED" copy).
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Shared mocks ─────────────────────────────────────────────────────────────

// next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/subscription",
  useSearchParams: () => ({ get: () => null }),
}));

// next/link
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    React.createElement("a", { href }, children),
}));

// WorkspaceShell — thin pass-through so we can assert it's rendered
vi.mock("@/components/workspace/WorkspaceShell", () => ({
  WorkspaceShell: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "workspace-shell" }, children),
}));

// WorkspaceThemeContext — provide a light palette stub
vi.mock("@/components/workspace/theme", () => ({
  useWorkspaceTheme: () => ({
    bg: "#F1EADD", panel: "#F7F1E6", rail: "#EDE5D6", inset: "#EAE1D0",
    ink: "#1F1B15", ink70: "rgba(31,27,21,0.70)", ink55: "rgba(31,27,21,0.52)",
    ink40: "rgba(31,27,21,0.38)", hair: "rgba(31,27,21,0.16)",
    activeBg: "rgba(31,27,21,0.06)", track: "rgba(31,27,21,0.10)", red: "#C6492E",
  }),
  WorkspaceThemeContext: { Provider: ({ children }: { children: React.ReactNode }) => children },
}));

// LanguageContext
vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({ language: "en", setLanguage: vi.fn() }),
  LanguageProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// translations
vi.mock("@/lib/translations", () => ({
  useTranslation: () => (key: string) => key,
}));

// useToast
const toastFn = vi.fn();
vi.mock("@/hooks/useToast", () => ({
  useToast: () => ({ toasts: [], toast: toastFn }),
}));

// ToastContainer — no-op
vi.mock("@/components/ui/Toast", () => ({
  ToastContainer: () => null,
}));

// billing — real resolveBillingUiMode, controllable Paddle client capability
let mockHasPaddleClientConfig = true;
vi.mock("@/lib/billing", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/billing")>();
  return {
    ...actual,
    hasPaddleClientConfig: () => mockHasPaddleClientConfig,
    // resolveBillingUiMode reads the module-local hasPaddleClientConfig, so
    // reimplement it here against the controllable flag (same Paddle-only logic).
    resolveBillingUiMode: (config: { billing_mode?: string; paddle_active?: boolean } | null) =>
      config?.paddle_active && mockHasPaddleClientConfig ? "paddle" : "unavailable",
  };
});

// API stubs
const mockGetSubscriptionPlans = vi.fn().mockResolvedValue({
  plans: [{
    id: "rico_monthly", plan: "pro", name: "Rico Monthly",
    price_monthly: 21.5, currency: "USD",
    description: "Smart AI job hunting for active UAE professionals.",
    features: ["300 AI messages per month"],
    entitlements: {
      monthly_ai_message_limit: 300, saved_jobs_limit: 100,
      profile_optimization_limit: 20, cv_storage_limit: 5,
      other_document_limit: 10, premium_recommendations_enabled: false,
      application_automation_enabled: false,
    },
    is_popular: true,
  }],
});
const mockGetMySubscription = vi.fn().mockResolvedValue({
  subscription: { plan: "free", subscription_status: "active", current_period_end: null, cancel_at: null },
  is_active: false,
});
const mockCreatePaddleCheckoutSession = vi.fn().mockResolvedValue({
  session_token: "sess_test_abc123xyz",
});
const mockCreatePaddleCustomerPortalSession = vi.fn();
const mockRecordSubscriptionIntent = vi.fn().mockResolvedValue(undefined);
const mockGetBillingConfig = vi.fn().mockResolvedValue({
  billing_mode: "paddle", paddle_active: true, sandbox: true,
});
// WhatsApp assisted channel — fail-hidden by default so Paddle-only tests
// are unaffected; individual tests opt in.
const mockGetWhatsAppBillingConfig = vi.fn().mockResolvedValue({ whatsapp_active: false });
const mockCreateWhatsAppSubscriptionRequest = vi.fn().mockResolvedValue({
  reference: "RICO-TEST123456",
  status: "pending",
  plan: "Rico Monthly",
  price: "21.50",
  currency: "USD",
  whatsapp_url: "https://wa.me/971585989080?text=Hello",
  note_en: "Activation occurs after payment verification.",
  note_ar: "يتم تفعيل الاشتراك بعد التحقق من الدفع.",
});

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error { },
  getSubscriptionPlans: (...args: unknown[]) => mockGetSubscriptionPlans(...args),
  getMySubscription: (...args: unknown[]) => mockGetMySubscription(...args),
  createPaddleCheckoutSession: (...args: unknown[]) => mockCreatePaddleCheckoutSession(...args),
  createPaddleCustomerPortalSession: (...args: unknown[]) => mockCreatePaddleCustomerPortalSession(...args),
  recordSubscriptionIntent: (...args: unknown[]) => mockRecordSubscriptionIntent(...args),
  getBillingConfig: (...args: unknown[]) => mockGetBillingConfig(...args),
  getWhatsAppBillingConfig: (...args: unknown[]) => mockGetWhatsAppBillingConfig(...args),
  createWhatsAppSubscriptionRequest: (...args: unknown[]) => mockCreateWhatsAppSubscriptionRequest(...args),
}));

// Paddle — capture the eventCallback so tests can fire synthetic events
let capturedEventCallback: ((event: { name: string; data?: Record<string, unknown> }) => void) | undefined;
const mockPaddleCheckoutOpen = vi.fn((opts: { eventCallback?: typeof capturedEventCallback }) => {
  capturedEventCallback = opts.eventCallback;
});
const mockOpenPaddleCheckout = vi.fn(async (
  priceId: string,
  sessionToken: string,
  _email: string | null,
  _lang: string,
) => {
  // Simulate what openPaddleCheckout does: call paddle.Checkout.open
  mockPaddleCheckoutOpen({ eventCallback: capturedEventCallback });
  return Promise.resolve();
});
const mockGetPaddlePriceId = vi.fn(() => "pri_01kxer8h278hvw37ec59yg73hg");

vi.mock("@/lib/paddle", () => ({
  openPaddleCheckout: (...args: Parameters<typeof mockOpenPaddleCheckout>) => mockOpenPaddleCheckout(...args),
  getPaddlePriceId: () => mockGetPaddlePriceId(),
  _resetInitPromise: vi.fn(),
}));

// useRequireAuth — authorized by default
const mockUseRequireAuth = vi.fn(() => ({
  user: { user_id: "u1", name: "Test User", email: "test@rico.ai" },
  ready: true,
  authorized: true,
  logout: vi.fn(),
}));
vi.mock("@/hooks/useRequireAuth", () => ({
  useRequireAuth: () => mockUseRequireAuth(),
}));

// ── Imports under test (after mocks) ─────────────────────────────────────────
import SubscriptionPage from "../app/subscription/page";
import { SubscriptionAtelier } from "../components/subscription/SubscriptionAtelier";

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("SubscriptionPage — WorkspaceShell composition", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRequireAuth.mockReturnValue({
      user: { user_id: "u1", name: "Test User", email: "test@rico.ai" },
      ready: true,
      authorized: true,
      logout: vi.fn(),
    });
  });

  it("renders WorkspaceShell when authorized", async () => {
    render(React.createElement(SubscriptionPage));
    await waitFor(() => {
      expect(screen.getByTestId("workspace-shell")).toBeDefined();
    });
  });

  it("renders a loading state when not yet authorized", () => {
    mockUseRequireAuth.mockReturnValue({
      user: null as unknown as { user_id: string; name: string; email: string },
      ready: false,
      authorized: false,
      logout: vi.fn(),
    });
    render(React.createElement(SubscriptionPage));
    const loader = screen.getByRole("status");
    expect(loader).toBeDefined();
    expect(screen.queryByTestId("workspace-shell")).toBeNull();
  });
});

describe("SubscriptionAtelier — Paddle checkout flow", () => {
  const user = { user_id: "u1", name: "Test User", email: "test@rico.ai" };

  beforeEach(() => {
    vi.clearAllMocks();
    capturedEventCallback = undefined;
    mockHasPaddleClientConfig = true;
    mockGetBillingConfig.mockResolvedValue({ billing_mode: "paddle", paddle_active: true, sandbox: true });
    mockCreatePaddleCheckoutSession.mockResolvedValue({ session_token: "sess_test_abc123xyz", price_id: "pri_server_resolved" });
    mockOpenPaddleCheckout.mockResolvedValue("closed");
  });

  it("calls createPaddleCheckoutSession before openPaddleCheckout on upgrade", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/subscribeWithPaddle/i);
    fireEvent.click(upgradeBtn);

    await waitFor(() => {
      expect(mockCreatePaddleCheckoutSession).toHaveBeenCalledWith("pro", "monthly");
    });
    await waitFor(() => {
      expect(mockOpenPaddleCheckout).toHaveBeenCalled();
    });

    // createPaddleCheckoutSession must be called BEFORE openPaddleCheckout
    const checkoutOrder = mockCreatePaddleCheckoutSession.mock.invocationCallOrder[0];
    const openOrder = mockOpenPaddleCheckout.mock.invocationCallOrder[0];
    expect(checkoutOrder).toBeLessThan(openOrder);
  });

  it("passes the server session_token to openPaddleCheckout as the second argument", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/subscribeWithPaddle/i);
    fireEvent.click(upgradeBtn);

    await waitFor(() => {
      expect(mockOpenPaddleCheckout).toHaveBeenCalled();
    });

    const [, sessionToken] = mockOpenPaddleCheckout.mock.calls[0] as unknown as [string, string];
    expect(sessionToken).toBe("sess_test_abc123xyz");
  });

  it("shows a Rico toast error when openPaddleCheckout rejects (Paddle checkout.error)", async () => {
    mockOpenPaddleCheckout.mockRejectedValue(new Error("Invalid price ID"));

    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/subscribeWithPaddle/i);
    fireEvent.click(upgradeBtn);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Invalid price ID", "error");
    });
  });

  it("shows the checkout-failed translation key when the error has no message", async () => {
    mockOpenPaddleCheckout.mockRejectedValue(new Error(""));

    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/subscribeWithPaddle/i);
    fireEvent.click(upgradeBtn);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith(
        expect.stringContaining("subscriptionCheckoutFailed"),
        "error",
      );
    });
  });
});

describe("Runtime billing config — mode resolution and fail-closed behavior", () => {
  const user = { user_id: "u1", name: "Test User", email: "test@rico.ai" };

  beforeEach(() => {
    vi.clearAllMocks();
    mockHasPaddleClientConfig = true;
    mockGetBillingConfig.mockResolvedValue({ billing_mode: "paddle", paddle_active: true, sandbox: true });
    mockCreatePaddleCheckoutSession.mockResolvedValue({ session_token: "sess_test_abc123xyz", price_id: "pri_server_resolved" });
    mockOpenPaddleCheckout.mockResolvedValue("closed");
  });

  it("fetches GET /api/v1/billing/config on mount", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));
    await waitFor(() => expect(mockGetBillingConfig).toHaveBeenCalled());
  });

  it("Paddle-active config → Paddle CTA, no WhatsApp link anywhere", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));

    await screen.findByText(/subscribeWithPaddle/i);

    expect(document.querySelectorAll('a[href*="wa.me"]').length).toBe(0);
    expect(screen.queryByText(/continueOnWhatsApp/i)).toBeNull();
  });

  it("legacy manual config → fail-closed, NEVER a WhatsApp payment flow", async () => {
    mockGetBillingConfig.mockResolvedValue({ billing_mode: "manual", paddle_active: false, sandbox: true });
    render(React.createElement(SubscriptionAtelier, { user }));

    await screen.findByTestId("payment-unavailable");

    expect(document.querySelectorAll('a[href*="wa.me"]').length).toBe(0);
    expect(screen.queryByText(/continueOnWhatsApp/i)).toBeNull();
    expect(mockCreatePaddleCheckoutSession).not.toHaveBeenCalled();
    expect(mockOpenPaddleCheckout).not.toHaveBeenCalled();
  });

  it("Paddle-active config but missing client token → fail-closed, NEVER WhatsApp", async () => {
    mockHasPaddleClientConfig = false;
    render(React.createElement(SubscriptionAtelier, { user }));

    await screen.findByTestId("payment-unavailable");

    expect(screen.getAllByText(/paymentTemporarilyUnavailable/i).length).toBeGreaterThan(0);
    expect(document.querySelectorAll('a[href*="wa.me"]').length).toBe(0);
    expect(screen.queryByText(/continueOnWhatsApp/i)).toBeNull();
    expect(screen.queryByText(/subscribeWithPaddle/i)).toBeNull();
  });

  it("unreachable billing config → fail-closed, NEVER WhatsApp", async () => {
    mockGetBillingConfig.mockRejectedValue(new Error("network down"));
    render(React.createElement(SubscriptionAtelier, { user }));

    await screen.findByTestId("payment-unavailable");

    expect(document.querySelectorAll('a[href*="wa.me"]').length).toBe(0);
    expect(screen.queryByText(/continueOnWhatsApp/i)).toBeNull();
  });

  it("uses the server-resolved price_id from the checkout session", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/subscribeWithPaddle/i);
    fireEvent.click(upgradeBtn);

    await waitFor(() => expect(mockOpenPaddleCheckout).toHaveBeenCalled());
    const [priceId] = mockOpenPaddleCheckout.mock.calls[0] as unknown as [string];
    expect(priceId).toBe("pri_server_resolved");
  });
});

describe("Backend confirmation — success is never declared locally", () => {
  const user = { user_id: "u1", name: "Test User", email: "test@rico.ai" };

  beforeEach(() => {
    vi.clearAllMocks();
    mockHasPaddleClientConfig = true;
    mockGetBillingConfig.mockResolvedValue({ billing_mode: "paddle", paddle_active: true, sandbox: true });
    mockCreatePaddleCheckoutSession.mockResolvedValue({ session_token: "sess_test_abc123xyz", price_id: "pri_server_resolved" });
  });

  it("re-fetches GET /api/v1/subscription/me after checkout.completed", async () => {
    mockOpenPaddleCheckout.mockResolvedValue("completed");
    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/subscribeWithPaddle/i);
    const callsBeforeCheckout = mockGetMySubscription.mock.calls.length;
    fireEvent.click(upgradeBtn);

    await waitFor(() => {
      expect(mockGetMySubscription.mock.calls.length).toBeGreaterThan(callsBeforeCheckout);
    });
  });

  it("does NOT re-fetch subscription state when the overlay is merely dismissed", async () => {
    mockOpenPaddleCheckout.mockResolvedValue("closed");
    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/subscribeWithPaddle/i);
    const callsBeforeCheckout = mockGetMySubscription.mock.calls.length;
    fireEvent.click(upgradeBtn);

    await waitFor(() => expect(mockOpenPaddleCheckout).toHaveBeenCalled());
    expect(mockGetMySubscription.mock.calls.length).toBe(callsBeforeCheckout);
  });
});

describe("Pricing copy — USD, not AED", () => {
  const user = { user_id: "u1", name: "Test User", email: "test@rico.ai" };

  beforeEach(() => {
    vi.clearAllMocks();
    mockHasPaddleClientConfig = true;
    mockGetBillingConfig.mockResolvedValue({ billing_mode: "paddle", paddle_active: true, sandbox: true });
  });

  it("renders the USD footer key and no AED copy", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));
    await screen.findByText(/subscribeWithPaddle/i);

    expect(screen.getByText(/pricesInUSD/i)).toBeDefined();
    expect(screen.queryByText(/pricesInAED/i)).toBeNull();
    expect(screen.queryByText(/AED/)).toBeNull();
  });

  it("formats the monthly price with two decimals (USD 21.50)", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));
    await screen.findByText(/subscribeWithPaddle/i);

    expect(screen.getByText(/USD 21\.50/)).toBeDefined();
  });
});

describe("SubscriptionAtelier — WhatsApp assisted channel (secondary to Paddle)", () => {
  const user = { user_id: "u1", name: "Test User", email: "test@rico.ai" };
  let openSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockHasPaddleClientConfig = true;
    mockGetBillingConfig.mockResolvedValue({ billing_mode: "paddle", paddle_active: true, sandbox: true });
    mockGetWhatsAppBillingConfig.mockResolvedValue({ whatsapp_active: true });
    mockCreateWhatsAppSubscriptionRequest.mockResolvedValue({
      reference: "RICO-TEST123456",
      status: "pending",
      plan: "Rico Monthly",
      price: "21.50",
      currency: "USD",
      whatsapp_url: "https://wa.me/971585989080?text=Hello",
      note_en: "Activation occurs after payment verification.",
      note_ar: "يتم تفعيل الاشتراك بعد التحقق من الدفع.",
    });
    openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
  });

  afterEach(() => {
    openSpy.mockRestore();
  });

  it("renders the WhatsApp CTA as secondary alongside the Paddle CTA when active", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));

    const waBtn = await screen.findByTestId("subscribe-via-whatsapp");
    expect(waBtn).toBeDefined();
    // Paddle CTA still present and untouched (visual primary).
    expect(screen.getByText(/subscribeWithPaddle/i)).toBeDefined();
    // Honest expectation-setting copy is shown.
    expect(screen.getByText(/whatsappActivationNote/i)).toBeDefined();
  });

  it("is hidden entirely when the server reports the channel unavailable", async () => {
    mockGetWhatsAppBillingConfig.mockResolvedValue({ whatsapp_active: false });
    render(React.createElement(SubscriptionAtelier, { user }));
    await screen.findByText(/subscribeWithPaddle/i);
    expect(screen.queryByTestId("subscribe-via-whatsapp")).toBeNull();
  });

  it("is hidden when the WhatsApp config fetch fails (fail-hidden)", async () => {
    mockGetWhatsAppBillingConfig.mockRejectedValue(new Error("network down"));
    render(React.createElement(SubscriptionAtelier, { user }));
    await screen.findByText(/subscribeWithPaddle/i);
    expect(screen.queryByTestId("subscribe-via-whatsapp")).toBeNull();
  });

  it("creates the pending request BEFORE opening WhatsApp, with the server URL", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));
    const waBtn = await screen.findByTestId("subscribe-via-whatsapp");
    fireEvent.click(waBtn);

    await waitFor(() => expect(mockCreateWhatsAppSubscriptionRequest).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(openSpy).toHaveBeenCalledTimes(1));

    const reqOrder = mockCreateWhatsAppSubscriptionRequest.mock.invocationCallOrder[0];
    const openOrder = (openSpy.mock.invocationCallOrder as number[])[0];
    expect(reqOrder).toBeLessThan(openOrder);
    expect(openSpy).toHaveBeenCalledWith(
      "https://wa.me/971585989080?text=Hello", "_blank", "noopener,noreferrer",
    );
    // Never claims payment/activation succeeded — only the verification note.
    expect(toastFn).toHaveBeenCalledWith("whatsappActivationNote", "info");
  });

  it("shows an honest error and never opens WhatsApp when the request fails", async () => {
    mockCreateWhatsAppSubscriptionRequest.mockRejectedValue(new Error("request failed"));
    render(React.createElement(SubscriptionAtelier, { user }));
    const waBtn = await screen.findByTestId("subscribe-via-whatsapp");
    fireEvent.click(waBtn);

    await waitFor(() => expect(toastFn).toHaveBeenCalledWith("request failed", "error"));
    expect(openSpy).not.toHaveBeenCalled();
  });

  it("blocks repeated clicks while the request is in flight", async () => {
    let resolveReq: (v: unknown) => void = () => undefined;
    mockCreateWhatsAppSubscriptionRequest.mockImplementation(
      () => new Promise((resolve) => { resolveReq = resolve; }),
    );
    render(React.createElement(SubscriptionAtelier, { user }));
    const waBtn = await screen.findByTestId("subscribe-via-whatsapp");

    fireEvent.click(waBtn);
    fireEvent.click(waBtn);
    fireEvent.click(waBtn);

    await waitFor(() => expect(mockCreateWhatsAppSubscriptionRequest).toHaveBeenCalledTimes(1));
    resolveReq({
      reference: "RICO-TEST123456", status: "pending", plan: "Rico Monthly",
      price: "21.50", currency: "USD",
      whatsapp_url: "https://wa.me/971585989080?text=Hello",
      note_en: "", note_ar: "",
    });
    await waitFor(() => expect(openSpy).toHaveBeenCalledTimes(1));
  });

  it("records a whatsapp upgrade intent on click", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));
    const waBtn = await screen.findByTestId("subscribe-via-whatsapp");
    fireEvent.click(waBtn);
    await waitFor(() =>
      expect(mockRecordSubscriptionIntent).toHaveBeenCalledWith("pro", "whatsapp", "/subscription"),
    );
  });
});

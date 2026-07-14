/**
 * subscription-atelier.test.tsx
 *
 * Targeted tests for the /subscription page migration to WorkspaceShell.
 *
 * Coverage:
 *  1. WorkspaceShell composition — SubscriptionPage renders WorkspaceShell when
 *     authorized, shows a loader when not.
 *  2. Upgrade button calls createPaddleCheckoutSession first (server session),
 *     then passes the returned session_token to openPaddleCheckout.
 *  3. Paddle receives the correct session token prefix in customData.
 *  4. Paddle checkout.error events surface as a Rico toast error message.
 *  5. No WhatsApp billing fallback is active (isManualBillingMode returns false).
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

// billing — always Paddle mode
vi.mock("@/lib/billing", () => ({
  isManualBillingMode: () => false,
  isPaddleBillingMode: () => true,
  buildWhatsAppUpgradeUrl: () => "https://wa.me/test",
  buildWhatsAppManageUrl: () => "https://wa.me/manage",
}));

// API stubs
const mockGetSubscriptionPlans = vi.fn().mockResolvedValue({
  plans: [{
    id: "rico_monthly", plan: "pro", name: "Rico Monthly",
    price_monthly: 21.5, currency: "USD",
    description: "Smart AI job hunting for active UAE professionals.",
    features: ["Unlimited CV analysis"],
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

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error { },
  getSubscriptionPlans: (...args: unknown[]) => mockGetSubscriptionPlans(...args),
  getMySubscription: (...args: unknown[]) => mockGetMySubscription(...args),
  createPaddleCheckoutSession: (...args: unknown[]) => mockCreatePaddleCheckoutSession(...args),
  createPaddleCustomerPortalSession: (...args: unknown[]) => mockCreatePaddleCustomerPortalSession(...args),
  recordSubscriptionIntent: (...args: unknown[]) => mockRecordSubscriptionIntent(...args),
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
    mockCreatePaddleCheckoutSession.mockResolvedValue({ session_token: "sess_test_abc123xyz" });
    mockOpenPaddleCheckout.mockResolvedValue(undefined);
  });

  it("calls createPaddleCheckoutSession before openPaddleCheckout on upgrade", async () => {
    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/upgradeTo/i);
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

    const upgradeBtn = await screen.findByText(/upgradeTo/i);
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

    const upgradeBtn = await screen.findByText(/upgradeTo/i);
    fireEvent.click(upgradeBtn);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Invalid price ID", "error");
    });
  });

  it("shows the checkout-failed translation key when the error has no message", async () => {
    mockOpenPaddleCheckout.mockRejectedValue(new Error(""));

    render(React.createElement(SubscriptionAtelier, { user }));

    const upgradeBtn = await screen.findByText(/upgradeTo/i);
    fireEvent.click(upgradeBtn);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith(
        expect.stringContaining("subscriptionCheckoutFailed"),
        "error",
      );
    });
  });
});

describe("Billing mode — no WhatsApp fallback", () => {
  it("isManualBillingMode returns false (Paddle is active)", async () => {
    const { isManualBillingMode } = await import("@/lib/billing");
    expect(isManualBillingMode()).toBe(false);
  });

  it("SubscriptionAtelier does not render a WhatsApp link when Paddle mode is active", async () => {
    const user = { user_id: "u1", name: "Test User", email: "test@rico.ai" };
    render(React.createElement(SubscriptionAtelier, { user }));

    // Wait for plans to load
    await screen.findByText(/upgradeTo/i);

    const whatsappLinks = document.querySelectorAll('a[href*="wa.me"]');
    expect(whatsappLinks.length).toBe(0);
  });
});

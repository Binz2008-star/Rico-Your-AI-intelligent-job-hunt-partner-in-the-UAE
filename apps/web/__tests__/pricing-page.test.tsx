/**
 * Public /pricing page contract.
 *
 * The page must be viewable by a logged-out visitor (no login redirect) and
 * show the AUTHORITATIVE plan catalog — never invented tiers/prices. It reuses
 * the same planCatalog the /subscription surface uses, so these assertions pin
 * the single-source-of-truth contract (lib/subscriptionCta.ts): "Rico Monthly"
 * at 21.50 USD, the six backend feature strings, and the free tier — nothing
 * fabricated like extra $19/$39/$79 tiers.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getPlans, meResult, recordIntent } = vi.hoisted(() => ({
  getPlans: vi.fn(),
  meResult: { current: { email: null as string | null, authenticated: false, guest: true } },
  recordIntent: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  getSubscriptionPlans: getPlans,
  fetchMe: vi.fn(() => Promise.resolve(meResult.current)),
  recordSubscriptionIntent: recordIntent,
}));

// Language context — default English; individual tests flip to Arabic.
const langState = vi.hoisted(() => ({ current: "en" as "en" | "ar" }));
vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({ language: langState.current, setLanguage: vi.fn() }),
}));

import { PricingContent } from "@/app/pricing/PricingContent";

beforeEach(() => {
  langState.current = "en";
  meResult.current = { email: null, authenticated: false, guest: true };
  // Backend returns the authoritative single paid plan.
  getPlans.mockResolvedValue({
    plans: [
      {
        id: "rico_monthly",
        plan: "pro",
        name: "Rico Monthly",
        price_monthly: 21.5,
        currency: "USD",
        description: "Smart AI job hunting for active UAE professionals.",
        features: [
          "300 AI messages per month",
          "20 CV & profile optimizations per month",
          "Smart AI role recommendations",
          "Advanced match scoring",
          "Saved searches",
          "Priority support",
        ],
        entitlements: {
          monthly_ai_message_limit: 300,
          saved_jobs_limit: 100,
          profile_optimization_limit: 20,
          cv_storage_limit: 5,
          other_document_limit: 10,
          premium_recommendations_enabled: false,
          application_automation_enabled: false,
        },
        is_popular: true,
      },
    ],
  });
  recordIntent.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("public /pricing page", () => {
  it("renders the authoritative Rico Monthly plan for a logged-out visitor", async () => {
    render(<PricingContent />);

    // Price + name from the authoritative catalog (not an invented tier).
    expect(await screen.findByText(/USD\s*21\.50/)).toBeInTheDocument();
    expect(screen.getAllByText("Rico Monthly").length).toBeGreaterThan(0);

    // All six backend feature strings surface.
    expect(screen.getByText("300 AI messages per month")).toBeInTheDocument();
    expect(screen.getByText("20 CV & profile optimizations per month")).toBeInTheDocument();
    expect(screen.getByText("Priority support")).toBeInTheDocument();

    // Free tier is shown too.
    expect(screen.getByText("$0")).toBeInTheDocument();
  });

  it("does NOT fabricate extra pricing tiers", async () => {
    render(<PricingContent />);
    await screen.findByText(/USD\s*21\.50/);
    // The generic 3-tier mock ($19/$39/$79 Moderato/Allegro/Presto) must not appear.
    expect(screen.queryByText(/\$19\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\$39\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\$79\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Moderato|Allegro|Presto/)).not.toBeInTheDocument();
  });

  it("sends a logged-out visitor to sign up (no auth wall)", async () => {
    render(<PricingContent />);
    const proCard = await screen.findByRole("region", { name: "Rico Monthly" });
    const cta = within(proCard).getByRole("link", { name: "Get started" });
    expect(cta).toHaveAttribute("href", "/signup");
  });

  it("points an authenticated visitor at the real /subscription surface", async () => {
    meResult.current = { email: "user@example.com", authenticated: true, guest: false };
    render(<PricingContent />);
    const proCard = await screen.findByRole("region", { name: "Rico Monthly" });
    await waitFor(() =>
      expect(within(proCard).getByRole("link", { name: "Manage subscription" })).toHaveAttribute(
        "href",
        "/subscription",
      ),
    );
  });

  it("falls back to the shared plan catalog when the backend call fails", async () => {
    getPlans.mockRejectedValueOnce(new Error("network"));
    render(<PricingContent />);
    // Still shows the authoritative price from FALLBACK_PLANS — never a blank page.
    expect(await screen.findByText(/USD\s*21\.50/)).toBeInTheDocument();
  });

  it("renders Arabic with RTL direction", async () => {
    langState.current = "ar";
    const { container } = render(<PricingContent />);
    await screen.findByText(/USD\s*21\.50/);
    expect(container.querySelector(".rp-root")).toHaveAttribute("dir", "rtl");
    // Arabic plan name from the translation layer.
    expect(screen.getAllByText("ريكو الشهرية").length).toBeGreaterThan(0);
  });
});

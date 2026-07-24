import type { Metadata } from "next";
import { PricingContent } from "./PricingContent";

/**
 * /pricing — PUBLIC pricing surface.
 *
 * Unauthenticated, viewable by logged-out visitors. It surfaces the SAME
 * authoritative plan catalog as the auth-gated /subscription page
 * (GET /api/v1/subscription/plans → src/subscription_plans.py, with the shared
 * planCatalog fallback), read-only — no checkout runs here. This closes the
 * gap where the public landing "Pricing" / "Rates" nav pointed at the
 * auth-gated /subscription route, so guests hit a login wall instead of the
 * prices. /subscription remains the single place upgrades are actually
 * transacted (Paddle checkout requires an authenticated account).
 */

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Rico Hunt pricing — one simple monthly plan for smart, AI-assisted job hunting in the UAE. See exactly what's included before you sign up.",
  alternates: { canonical: "/pricing" },
};

export default function PricingPage() {
  return <PricingContent />;
}

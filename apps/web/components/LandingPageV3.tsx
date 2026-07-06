/**
 * LandingPageV3.tsx — orchestrator
 *
 * Assembles the landing redesign from isolated components.
 * Does NOT include PricingSection (option a — landing v2 without pricing).
 * Does NOT touch Navigation.tsx, TopNav.tsx, auth, billing, or /command.
 * LandingPageV2 is preserved; this file does not import or delete it.
 */

import HeroSection from "@/components/landing/HeroSection";
import HowItWorks from "@/components/landing/HowItWorks";
import FeaturesSection from "@/components/landing/FeaturesSection";
import TrustBar from "@/components/landing/TrustBar";

export default function LandingPageV3() {
  return (
    <main id="main-content" className="min-h-screen">
      <HeroSection />
      <TrustBar />
      <HowItWorks />
      <FeaturesSection />

      {/* Final CTA — static, no network calls */}
      <section
        aria-labelledby="final-cta-heading"
        className="py-16 md:py-24"
      >
        <div className="container mx-auto px-4 max-w-[1120px]">
          <div className="rounded-[32px] border border-white/10 bg-gradient-to-br from-[#21d19a]/[0.12] to-white/[0.03] p-8 md:p-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
            <div>
              <h2
                id="final-cta-heading"
                className="font-display text-[clamp(1.8rem,3.5vw,3rem)] leading-[1] tracking-[-0.04em] mb-3"
              >
                Rico should feel like the product already works.
              </h2>
              <p className="text-muted-foreground max-w-[55ch]">
                Less landing page, more live system. The hero is the proof. The
                rest supports trust, workflow clarity, and your next move.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 shrink-0">
              <a
                href="/sign-up"
                className="inline-flex items-center justify-center min-h-[44px] px-5 rounded-full bg-gradient-to-b from-[#37ddB0] to-[#21d19a] text-[#04110d] font-semibold text-sm shadow-[0_12px_30px_rgba(33,209,154,0.22)] hover:-translate-y-px transition-transform"
              >
                Start free
              </a>
              <a
                href="#hero"
                className="inline-flex items-center justify-center min-h-[44px] px-5 rounded-full border border-white/10 bg-white/[0.04] text-sm font-semibold hover:-translate-y-px transition-transform"
              >
                Replay demo
              </a>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

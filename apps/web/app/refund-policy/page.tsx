import type { Metadata } from "next";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy | Rico Hunt",
  description: "Refund and cancellation policy for Rico Hunt subscriptions.",
};

export default function RefundPolicyPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />

      <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
        <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-[#0a0a1a] text-sm font-black shadow-[0_0_28px_rgba(245,166,35,0.28)]">
            R
          </span>
          <span>
            Rico<span className="text-[#f5a623]"> Hunt</span>
          </span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link href="/about" className="text-sm text-text-secondary transition-colors hover:text-white">
            About
          </Link>
          <Link href="/contact" className="text-sm text-text-secondary transition-colors hover:text-white">
            Contact
          </Link>
          <Link href="/terms" className="text-sm text-text-secondary transition-colors hover:text-white">
            Terms
          </Link>
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">
            Privacy
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <h1 className="mb-2 text-3xl font-semibold text-white md:text-4xl">
            Refund and Cancellation Policy
          </h1>
          <p className="mb-8 text-sm text-text-secondary">
            Last updated: May 2026 · Clear terms for subscription management.
          </p>

          <div className="space-y-8 text-sm leading-7 text-text-secondary">
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">1. Subscription Cancellation</h2>
              <p>
                You may cancel your subscription at any time through the subscription management portal
                or by contacting support. Cancellation takes effect at the end of your current billing
                period. You will continue to have access to paid features until the period ends.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">2. Refund Eligibility</h2>
              <div className="space-y-3">
                <p>
                  <strong>Free Plan:</strong> No refunds apply as the Free plan has no charges.
                </p>
                <p>
                  <strong>Paid Subscriptions (Pro/Premium):</strong>
                </p>
                <ul className="ml-4 list-disc space-y-2">
                  <li>
                    <strong>14-Day Cooling-Off Period (UAE & EU consumers):</strong> If you are a
                    consumer in the UAE or EU, you may request a full refund within 14 days of your
                    initial subscription purchase, provided you have not substantially used the service.
                  </li>
                  <li>
                    <strong>Technical Failures:</strong> If the service is unavailable or materially
                    non-functional due to our infrastructure for more than 48 consecutive hours within
                    a billing period, you may request a prorated refund for that period.
                  </li>
                  <li>
                    <strong>Billing Errors:</strong> If you were incorrectly charged due to a system
                    error, we will refund the incorrect amount immediately upon verification.
                  </li>
                </ul>
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">3. Non-Refundable Situations</h2>
              <ul className="ml-4 list-disc space-y-2">
                <li>Partial months after the cooling-off period</li>
                <li>Downgrades from a higher to lower tier mid-cycle</li>
                <li>Unused messages, optimizations, or feature quotas</li>
                <li>Voluntary account deletion before subscription period ends</li>
                <li>Violations of Terms of Service resulting in account termination</li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">4. How to Request a Refund</h2>
              <p>
                To request a refund, email info@ricohunt.com with:
              </p>
              <ul className="ml-4 mt-2 list-disc space-y-2">
                <li>Your registered email address</li>
                <li>Subscription plan and purchase date</li>
                <li>Reason for refund request</li>
                <li>Any relevant screenshots or documentation</li>
              </ul>
              <p className="mt-3">
                Refund requests are processed within 5-7 business days. Approved refunds are issued
                to the original payment method and may take 5-10 business days to appear, depending
                on your bank or card issuer.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">5. Plan Changes</h2>
              <p>
                <strong>Upgrades:</strong> When upgrading from Pro to Premium, the new rate takes
                effect immediately. You will be charged a prorated amount for the remainder of the
                billing cycle.
              </p>
              <p className="mt-2">
                <strong>Downgrades:</strong> When downgrading, the lower tier takes effect at the
                start of the next billing cycle. No partial refunds are provided for the current cycle.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">6. Failed Payments</h2>
              <p>
                If a payment fails, we will attempt to retry the charge. You will have a 7-day grace
                period to update your payment method. After 7 days, your subscription will be
                suspended and moved to the Free plan. No refunds are provided for suspended subscriptions.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">7. Special Circumstances</h2>
              <p>
                We reserve the right to issue refunds outside this policy in exceptional circumstances,
                such as documented medical emergencies or force majeure events. These are evaluated
                on a case-by-case basis.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">8. Contact</h2>
              <p>
                For refund-related questions, contact:
                <br />
                Email: info@ricohunt.com
                <br />
                Response time: Within 48 hours
              </p>
            </section>
          </div>
        </GlassPanel>
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
        <p className="mb-1 text-sm font-semibold text-white">Rico Hunt</p>
        <p className="mb-1 text-xs text-text-tertiary">
          Powered by Eco Technology Environment Protection Services L.L.C
        </p>
        <p className="mb-3 text-xs text-text-tertiary">United Arab Emirates</p>
        <div className="mb-3 flex flex-wrap items-center justify-center gap-5">
          <Link href="/about" className="text-xs text-text-tertiary transition-colors hover:text-white">About</Link>
          <Link href="/contact" className="text-xs text-text-tertiary transition-colors hover:text-white">Contact</Link>
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">Terms</Link>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">Privacy</Link>
          <span className="text-xs font-medium text-white">Refunds</span>
          <Link href="/faq" className="text-xs text-text-tertiary transition-colors hover:text-white">FAQ</Link>
        </div>
        <p className="mb-1 text-xs text-text-tertiary">
          <a href="mailto:info@ricohunt.com" className="text-[#f5a623] transition-colors hover:opacity-80">info@ricohunt.com</a>
          {" · "}
          <a href="https://wa.me/971585989080" className="text-[#f5a623] transition-colors hover:opacity-80">+971 58 598 9080</a>
        </p>
        <p className="text-xs text-text-tertiary">© 2026 Rico Hunt. All rights reserved.</p>
      </footer>
    </div>
  );
}

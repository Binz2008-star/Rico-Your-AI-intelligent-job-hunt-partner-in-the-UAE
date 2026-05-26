import type { Metadata } from "next";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export const metadata: Metadata = {
  title: "Terms of Service | Rico Hunt",
  description: "Terms of Service for Rico Hunt — the UAE-focused AI career execution platform.",
};

export default function TermsPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />

      <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
        <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-magenta to-cyan text-sm font-black shadow-[0_0_28px_rgba(255,45,142,0.28)]">
            R
          </span>
          <span>
            Rico<span className="text-magenta">.ai</span>
          </span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">
            Privacy
          </Link>
          <Link href="/refund-policy" className="text-sm text-text-secondary transition-colors hover:text-white">
            Refunds
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <h1 className="mb-2 text-3xl font-semibold text-white md:text-4xl">
            Terms of Service
          </h1>
          <p className="mb-8 text-sm text-text-secondary">
            Last updated: May 2026 · These terms apply to all users of Rico Hunt.
          </p>

          <div className="space-y-8 text-sm leading-7 text-text-secondary">
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">1. Acceptance of Terms</h2>
              <p>
                By accessing or using Rico Hunt, you agree to be bound by these Terms of Service.
                If you do not agree, you may not use the service. These terms constitute a legally
                binding agreement between you and Rico Hunt.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">2. Description of Service</h2>
              <p>
                Rico Hunt provides an autonomous career execution platform that converts CVs into
                structured profiles, infers career tracks, searches UAE job markets, scores
                opportunities, and manages application pipelines. The service includes AI-powered
                messaging, role-graph optimization, and application tracking.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">3. User Accounts</h2>
              <p>
                You must provide accurate information when creating an account. You are responsible
                for maintaining the security of your account credentials. Notify us immediately of
                any unauthorized access. We reserve the right to suspend accounts that violate these terms.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">4. Subscription and Payments</h2>
              <p>
                Some features require a paid subscription. Payments are processed through Stripe.
                Subscriptions auto-renew unless cancelled. You may cancel at any time through the
                subscription management portal. No refunds for partial months unless required by law.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">5. User Content</h2>
              <p>
                You retain ownership of your CV and profile data. By uploading content, you grant
                Rico Hunt a license to process it for the purpose of providing the service. We do
                not sell your data to third parties. You may delete your account and data at any time.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">6. Prohibited Activities</h2>
              <p>
                You may not: (a) use the service for illegal purposes; (b) attempt to access
                systems or data without authorization; (c) interfere with other users&apos; access;
                (d) upload malicious code; (e) resell or redistribute the service without permission.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">7. Limitation of Liability</h2>
              <p>
                Rico Hunt provides the service &quot;as is&quot; without warranties of any kind. We are not
                liable for: (a) job application outcomes; (b) accuracy of third-party job listings;
                (c) AI-generated content errors; (d) service interruptions. Our total liability is
                limited to amounts paid in the 12 months preceding the claim.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">8. Governing Law</h2>
              <p>
                These terms are governed by the laws of the United Arab Emirates. Any disputes
                shall be resolved in the courts of Dubai, UAE. If you are a consumer in the EU,
                mandatory consumer protection laws of your country of residence may apply.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">9. Changes to Terms</h2>
              <p>
                We may update these terms from time to time. Material changes will be notified via
                email or through the service. Continued use after changes constitutes acceptance.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">10. Contact</h2>
              <p>
                For questions about these terms, contact us at: info@ricohunt.com
              </p>
            </section>
          </div>
        </GlassPanel>
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
        <div className="mb-3 flex items-center justify-center gap-6">
          <span className="text-xs font-medium text-white">Terms</span>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">Privacy</Link>
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">Refunds</Link>
        </div>
        <p className="mb-2 text-xs text-text-tertiary">For inquiries, support, and business communication: <a href="mailto:info@ricohunt.com" className="text-cyan transition-colors hover:text-white">info@ricohunt.com</a></p>
        <p className="text-xs text-text-tertiary">© 2026 Rico Hunt. All rights reserved.</p>
      </footer>
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export const metadata: Metadata = {
  title: "Privacy Policy | Rico Hunt",
  description: "Privacy Policy for Rico Hunt — how we collect, use, and protect your personal data.",
};

export default function PrivacyPage() {
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
          <Link href="/terms" className="text-sm text-text-secondary transition-colors hover:text-white">
            Terms
          </Link>
          <Link href="/refund-policy" className="text-sm text-text-secondary transition-colors hover:text-white">
            Refunds
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <h1 className="mb-2 text-3xl font-semibold text-white md:text-4xl">
            Privacy Policy
          </h1>
          <p className="mb-8 text-sm text-text-secondary">
            Last updated: May 2026 · We are committed to protecting your personal data.
          </p>

          <div className="space-y-8 text-sm leading-7 text-text-secondary">
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">1. Data We Collect</h2>
              <ul className="ml-4 list-disc space-y-2">
                <li>
                  <strong>Account Information:</strong> Email address, name, and authentication credentials.
                </li>
                <li>
                  <strong>CV/Resume Data:</strong> Employment history, skills, education, contact information
                  extracted from uploaded documents.
                </li>
                <li>
                  <strong>Usage Data:</strong> Messages sent to Rico, searches performed, jobs viewed,
                  applications tracked, and feature usage.
                </li>
                <li>
                  <strong>Technical Data:</strong> IP address, browser type, device information, and cookies.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">2. How We Use Your Data</h2>
              <ul className="ml-4 list-disc space-y-2">
                <li>To provide and improve the career execution service</li>
                <li>To infer career tracks and generate personalized job searches</li>
                <li>To score and rank job opportunities based on your profile</li>
                <li>To send notifications (email, Telegram) about relevant opportunities</li>
                <li>To process payments and manage subscriptions</li>
                <li>To comply with legal obligations and prevent fraud</li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">3. Data Processing & AI</h2>
              <p>
                Your CV and profile data are processed by AI systems (OpenAI, DeepSeek, Hugging Face)
                to generate career insights and job matches. We do not use your data to train public AI
                models. Processing occurs on secure infrastructure with appropriate safeguards.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">4. Data Sharing</h2>
              <p>
                We do not sell your personal data. We share data only with:
              </p>
              <ul className="ml-4 mt-2 list-disc space-y-2">
                <li>Payment processors (Stripe) for subscription management</li>
                <li>Cloud hosting providers (Render) for service operation</li>
                <li>AI providers for CV analysis and job matching</li>
                <li>Analytics providers to improve user experience</li>
                <li>Legal authorities when required by law</li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">5. Data Retention</h2>
              <p>
                We retain your data while your account is active. You may delete your account at any time,
                which will remove your CV, profile, and personal data within 30 days. Some data may be
                retained longer if required by law or for legitimate business purposes (e.g., financial records).
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">6. Your Rights</h2>
              <p>Depending on your jurisdiction, you may have the right to:</p>
              <ul className="ml-4 mt-2 list-disc space-y-2">
                <li>Access and receive a copy of your personal data</li>
                <li>Correct inaccurate or incomplete data</li>
                <li>Delete your account and associated data</li>
                <li>Object to or restrict certain processing activities</li>
                <li>Export your data in a portable format</li>
                <li>Withdraw consent where processing is consent-based</li>
              </ul>
              <p className="mt-3">
                To exercise these rights, contact us at info@ricohunt.com
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">7. Security</h2>
              <p>
                We implement industry-standard security measures including encryption in transit (TLS),
                secure authentication, and access controls. However, no system is 100% secure. You are
                responsible for maintaining the confidentiality of your account credentials.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">8. Cookies & Tracking</h2>
              <p>
                We use cookies and similar technologies for authentication, preferences, and analytics.
                You may disable cookies in your browser, though this may affect service functionality.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">9. International Transfers</h2>
              <p>
                Your data may be transferred to and processed in countries outside your jurisdiction,
                including the United States and European Union. We ensure appropriate safeguards are in
                place for such transfers.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">10. Contact Us</h2>
              <p>
                For privacy-related questions or to exercise your rights, contact:
                <br />
                Email: info@ricohunt.com
                <br />
                Address: Dubai, United Arab Emirates
              </p>
            </section>
          </div>
        </GlassPanel>
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
        <div className="mb-3 flex items-center justify-center gap-6">
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">Terms</Link>
          <span className="text-xs font-medium text-white">Privacy</span>
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">Refunds</Link>
        </div>
        <p className="mb-2 text-xs text-text-tertiary">For inquiries, support, and business communication: <a href="mailto:info@ricohunt.com" className="text-cyan transition-colors hover:text-white">info@ricohunt.com</a></p>
        <p className="text-xs text-text-tertiary">© 2026 Rico Hunt. All rights reserved.</p>
      </footer>
    </div>
  );
}

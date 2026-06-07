import type { Metadata } from "next";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export const metadata: Metadata = {
  title: "Terms of Service | Rico Hunt",
  description: "Terms of Service for Rico Hunt — the UAE-focused AI career platform.",
};

export default function TermsPage() {
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
            Last updated: June 2026 · These terms apply to all users of Rico Hunt.
          </p>

          <div className="space-y-8 text-sm leading-7 text-text-secondary">

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">1. Acceptance of Terms</h2>
              <p>
                By accessing or using Rico Hunt, you agree to be bound by these Terms of Service.
                If you do not agree, you may not use the service. These terms constitute a legally
                binding agreement between you and Rico Hunt, operated by Eco Technology Environment
                Protection Services L.L.C.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">2. Description of Service</h2>
              <p>
                Rico Hunt is an AI-powered career platform that helps professionals in the UAE and
                GCC discover job opportunities, manage applications, and improve their job search
                strategy. The service includes CV analysis, job matching, application tracking,
                and AI-powered career guidance.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">3. Service Limitations and Disclaimers</h2>
              <p className="mb-3">
                Before using Rico Hunt, please read the following important limitations:
              </p>
              <ul className="ml-4 list-disc space-y-3">
                <li>
                  <strong className="text-white">No employment guarantee.</strong> Rico Hunt does not
                  guarantee employment, job interviews, or application success. Using the platform does
                  not ensure you will receive a job offer.
                </li>
                <li>
                  <strong className="text-white">Not an employer or recruitment agency.</strong> Rico Hunt
                  is a software platform, not an employer, staffing agency, or recruitment agency. We do
                  not represent employers, negotiate on your behalf, or place candidates in roles.
                </li>
                <li>
                  <strong className="text-white">Jobs from external sources.</strong> Job listings shown
                  on Rico Hunt may come from external job data providers and public job sources. We do not
                  independently verify all listings. Job availability, accuracy, and legitimacy are the
                  responsibility of the posting employer.
                </li>
                <li>
                  <strong className="text-white">Verify before applying.</strong> You must independently
                  verify all job details — including the employer, role, salary, location, and application
                  requirements — before applying. Rico Hunt is not liable for inaccurate or outdated
                  job listings.
                </li>
                <li>
                  <strong className="text-white">AI outputs may be inaccurate.</strong> Rico uses
                  AI-generated content for CV analysis, job matching, and career guidance. AI outputs
                  can contain errors, omissions, or outdated information. Do not rely solely on
                  AI-generated content for career decisions.
                </li>
                <li>
                  <strong className="text-white">Your approval is required before applications.</strong> Rico
                  Hunt will not submit a job application on your behalf without your explicit confirmation.
                  You remain in full control of all application actions.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">4. User Accounts</h2>
              <p>
                You must provide accurate information when creating an account. You are responsible
                for maintaining the security of your account credentials. Notify us immediately of
                any unauthorized access. We reserve the right to suspend accounts that violate these terms.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">5. Subscription and Payments</h2>
              <p>
                Some features require a paid subscription. Payments are processed through Stripe.
                Subscriptions auto-renew unless cancelled. You may cancel at any time through the
                subscription management portal. No refunds for partial months unless required by law.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">6. User Content</h2>
              <p>
                You retain ownership of your CV and profile data. By uploading content, you grant
                Rico Hunt a license to process it for the purpose of providing the service. We do
                not sell your data to third parties. You may request deletion of your account and
                data at any time by contacting info@ricohunt.com.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">7. Prohibited Activities</h2>
              <p>
                You may not: (a) use the service for illegal purposes; (b) attempt to access
                systems or data without authorization; (c) interfere with other users&apos; access;
                (d) upload malicious code; (e) resell or redistribute the service without permission;
                (f) misrepresent your identity or qualifications.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">8. Limitation of Liability</h2>
              <p className="mb-3">
                Rico Hunt provides the service &quot;as is&quot; without warranties of any kind. To the
                fullest extent permitted by law, we are not liable for:
              </p>
              <ul className="ml-4 list-disc space-y-2">
                <li>Job application outcomes or employment decisions made by employers</li>
                <li>Accuracy, completeness, or availability of third-party job listings</li>
                <li>Errors, omissions, or inaccuracies in AI-generated content</li>
                <li>Service interruptions, data loss, or technical failures</li>
                <li>Any reliance placed on job listings without independent verification</li>
              </ul>
              <p className="mt-3">
                Our total liability to you is limited to amounts you have paid to Rico Hunt in the
                12 months preceding the claim.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">9. Governing Law</h2>
              <p>
                These terms are governed by the laws of the United Arab Emirates. Any disputes
                shall be resolved in the courts of the United Arab Emirates. If you are a consumer
                in the EU, mandatory consumer protection laws of your country of residence may apply.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">10. Changes to Terms</h2>
              <p>
                We may update these terms from time to time. Material changes will be notified via
                email or through the service. Continued use after changes constitutes acceptance.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">11. Contact</h2>
              <p className="mb-3">For questions about these terms, contact us:</p>
              <ul className="ml-4 list-none space-y-1">
                <li><strong className="text-white">Company:</strong> Eco Technology Environment Protection Services L.L.C</li>
                <li><strong className="text-white">Location:</strong> United Arab Emirates</li>
                <li>
                  <strong className="text-white">Email:</strong>{" "}
                  <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
                    info@ricohunt.com
                  </a>
                </li>
                <li>
                  <strong className="text-white">Phone / WhatsApp:</strong>{" "}
                  <a href="https://wa.me/971585989080" className="text-[#f5a623] hover:opacity-80">
                    +971 58 598 9080
                  </a>
                </li>
                <li>
                  <strong className="text-white">LinkedIn:</strong>{" "}
                  <a
                    href="https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#f5a623] hover:opacity-80"
                  >
                    Company LinkedIn
                  </a>
                </li>
              </ul>
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
          <span className="text-xs font-medium text-white">Terms</span>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">Privacy</Link>
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">Refunds</Link>
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

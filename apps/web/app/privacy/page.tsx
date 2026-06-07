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
          <p className="mb-6 text-sm text-text-secondary">
            Last updated: June 2026 · We are committed to protecting your personal data.
          </p>

          <div className="mb-8 rounded-xl border border-white/10 bg-white/5 p-5">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              Data Controller
            </p>
            <p className="text-sm font-medium text-white">
              Eco Technology Environment Protection Services L.L.C
            </p>
            <p className="mt-0.5 text-sm text-text-secondary">United Arab Emirates</p>
            <p className="mt-2 text-xs text-text-tertiary">
              For privacy requests or data deletion:{" "}
              <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
                info@ricohunt.com
              </a>
              {" · "}
              <a href="https://wa.me/971585989080" className="text-[#f5a623] hover:opacity-80">
                +971 58 598 9080
              </a>
            </p>
          </div>

          <div className="space-y-8 text-sm leading-7 text-text-secondary">

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">1. Data We Collect</h2>
              <p className="mb-3">We collect the following information when you use Rico Hunt:</p>
              <ul className="ml-4 list-disc space-y-2">
                <li><strong className="text-white">Account data:</strong> Name, email address, and authentication credentials.</li>
                <li><strong className="text-white">Contact data:</strong> Phone number or WhatsApp number, if provided.</li>
                <li><strong className="text-white">CV and resume files:</strong> Uploaded documents in any format.</li>
                <li><strong className="text-white">Extracted CV content:</strong> Text, skills, work experience, education, and other information parsed from your CV.</li>
                <li><strong className="text-white">Career preferences:</strong> Target roles, preferred sectors, salary expectations, and location preferences.</li>
                <li><strong className="text-white">Chat messages:</strong> Messages you send to Rico and the responses you receive.</li>
                <li><strong className="text-white">Job activity:</strong> Jobs you save, view, apply for, or mark in any way.</li>
                <li><strong className="text-white">Application data:</strong> Status and notes for job applications you track through the platform.</li>
                <li><strong className="text-white">Technical data:</strong> IP address, browser type, device information, and session cookies.</li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">2. How We Use Your Data</h2>
              <ul className="ml-4 list-disc space-y-2">
                <li>To create and maintain your account and career profile</li>
                <li>To analyze your CV and suggest relevant job roles</li>
                <li>To search, filter, and score job listings based on your profile</li>
                <li>To provide AI-powered career guidance and job-match insights</li>
                <li>To track and manage your job applications</li>
                <li>To send notifications about relevant opportunities</li>
                <li>To process payments and manage subscriptions</li>
                <li>To improve platform quality and fix issues</li>
                <li>To comply with legal obligations and prevent misuse</li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">3. CV Storage and AI Analysis</h2>
              <p className="mb-3">
                Rico may store your uploaded CV file and/or the text extracted from it. This data is used
                to build your career profile and power job matching.
              </p>
              <p>
                Rico may use AI tools to analyze CVs, extract skills and experience, suggest target roles,
                and provide job-match insights. Your CV and profile data may be sent to AI service
                providers to generate these results. We do not use your personal data to train public
                AI models.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">4. Third-Party Providers</h2>
              <p className="mb-3">
                Rico may use trusted third-party providers to deliver the service, including:
              </p>
              <ul className="ml-4 list-disc space-y-2">
                <li><strong className="text-white">Cloud hosting and infrastructure</strong> — for running the platform</li>
                <li><strong className="text-white">Database providers</strong> — for storing your account and profile data</li>
                <li><strong className="text-white">Authentication providers</strong> — for secure login</li>
                <li><strong className="text-white">AI service providers</strong> — for CV analysis, job matching, and chat</li>
                <li><strong className="text-white">Analytics providers</strong> — for understanding platform usage</li>
                <li><strong className="text-white">Email and messaging providers</strong> — for notifications and support</li>
                <li><strong className="text-white">Payment processors</strong> — for subscription billing</li>
                <li><strong className="text-white">Job data providers</strong> — for sourcing live job listings</li>
              </ul>
              <p className="mt-3">
                We share only the minimum data necessary for each provider to perform their function.
                We do not sell your personal information to any third party.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">5. Job Source Disclaimer</h2>
              <p>
                Jobs shown on Rico Hunt may come from external job data providers and public job sources.
                We do our best to surface relevant and accurate listings, but we cannot guarantee the
                accuracy, availability, or legitimacy of any individual job posting. You should verify
                all job details — including the employer, role, and terms — before applying.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">6. We Do Not Sell Your Data</h2>
              <p>
                Rico does not sell, rent, or trade your personal information to advertisers, recruiters,
                employers, or any other third parties for commercial purposes.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">7. Data Deletion</h2>
              <p>
                You can request deletion of your account and personal data at any time by emailing{" "}
                <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
                  info@ricohunt.com
                </a>{" "}
                from your registered account email address. We will process your request and confirm
                deletion within a reasonable timeframe.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">8. Data Retention</h2>
              <p>
                We retain your data while your account is active and as needed to provide the service.
                Data may also be retained for legal compliance, security, abuse prevention, and
                legitimate operational reasons, even after an account is deleted. Financial records
                are retained as required by applicable law.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">9. Security</h2>
              <p>
                We implement reasonable technical and organizational measures to protect your data,
                including encryption in transit (TLS) and access controls. However, no online service
                can guarantee complete security. You are responsible for keeping your account
                credentials safe.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">10. Cookies</h2>
              <p>
                We use cookies and similar technologies for authentication, session management, and
                basic analytics. You may disable cookies in your browser settings, though this may
                affect the functionality of the platform.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">11. Your Rights</h2>
              <p className="mb-3">Depending on your jurisdiction, you may have the right to:</p>
              <ul className="ml-4 list-disc space-y-2">
                <li>Access a copy of your personal data</li>
                <li>Correct inaccurate or incomplete data</li>
                <li>Request deletion of your account and data</li>
                <li>Object to or restrict certain processing</li>
                <li>Export your data in a portable format</li>
              </ul>
              <p className="mt-3">
                To exercise any of these rights, contact us at{" "}
                <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
                  info@ricohunt.com
                </a>
                .
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">12. Changes to This Policy</h2>
              <p>
                We may update this Privacy Policy from time to time. Material changes will be
                communicated via email or a notice within the platform. Continued use of Rico Hunt
                after changes constitutes acceptance of the updated policy.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">13. Contact</h2>
              <p className="mb-3">For privacy-related questions or to exercise your rights:</p>
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
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">Terms</Link>
          <span className="text-xs font-medium text-white">Privacy</span>
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

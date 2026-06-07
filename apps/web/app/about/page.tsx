import type { Metadata } from "next";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export const metadata: Metadata = {
  title: "About | Rico Hunt",
  description: "Rico Hunt is a UAE-focused AI career companion that reads your CV, finds matching jobs, and helps you execute your job search — without applying silently.",
};

export default function AboutPage() {
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
          <div className="mb-10">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              Our Story
            </p>
            <h1 className="mb-4 text-3xl font-semibold text-white md:text-4xl">
              Built for the UAE job market.<br />Built around your CV.
            </h1>
            <p className="text-base leading-7 text-text-secondary">
              Rico Hunt is an AI-powered career platform focused on helping professionals in the UAE and
              GCC discover relevant opportunities, improve their job search strategy, and manage
              applications more effectively. Rico Hunt is operated by{" "}
              <span className="text-white font-medium">
                Eco Technology Environment Protection Services L.L.C
              </span>
              , a UAE-registered company.
            </p>
          </div>

          <div className="space-y-10 text-sm leading-7 text-text-secondary">
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">The Problem We're Solving</h2>
              <p>
                The UAE job market is fast-moving and highly competitive. Most job seekers spend more time
                managing the logistics of job hunting than actually preparing for opportunities. Generic
                platforms surface hundreds of mismatched listings, force users through lengthy setup wizards,
                and offer little guidance on which roles actually fit their background.
              </p>
              <p className="mt-3">
                Rico is our answer to that problem: an AI career companion that reads your CV once, builds
                a structured understanding of your experience, and then works continuously in the background
                to surface UAE-specific opportunities that match who you actually are — not just keywords.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">How Rico Finds Jobs</h2>
              <p>
                Rico aggregates live job listings from across the UAE using the{" "}
                <span className="text-white">JSearch API</span> (powered by RapidAPI), which pulls
                real-time data from LinkedIn, Indeed, Glassdoor, Bayt, and other major job boards active
                in the region. Listings are filtered and scored against your CV and profile — so you only
                see roles where your background is genuinely relevant.
              </p>
              <p className="mt-3">
                Rico does not apply to jobs on your behalf without your explicit approval. Every application
                requires your confirmation. You stay in control at every step.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">What Rico Remembers</h2>
              <p>
                Unlike a search engine, Rico maintains a persistent profile of your career goals: your
                target roles, preferred sectors, salary expectations, and job history. This means every
                search session picks up where the last one left off — no re-entering your preferences,
                no losing your context.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">Our Principles</h2>
              <ul className="ml-4 list-disc space-y-2">
                <li>
                  <strong className="text-white">Transparency first:</strong> We tell you where job data
                  comes from and how your match scores are calculated.
                </li>
                <li>
                  <strong className="text-white">Your data is yours:</strong> We do not sell your CV or
                  profile to employers, recruiters, or third parties.
                </li>
                <li>
                  <strong className="text-white">No silent actions:</strong> Rico never applies, sends a
                  message, or takes a high-impact action without your confirmation.
                </li>
                <li>
                  <strong className="text-white">UAE-focused:</strong> Every feature is designed for the
                  UAE job market — sectors, visa requirements, salary norms, and employer expectations.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">Where We Are</h2>
              <p>
                Rico Hunt is operated by{" "}
                <span className="text-white font-medium">
                  Eco Technology Environment Protection Services L.L.C
                </span>
                , a UAE-registered company. The platform serves professionals
                across the UAE and the wider GCC region.
              </p>
              <p className="mt-3">
                The platform is currently in active development. We ship updates regularly based on user
                feedback. If you encounter a problem or have a suggestion, we want to hear from you.
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">Get in Touch</h2>
              <p>
                We&apos;re a small team and we read every message.
              </p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <a
                  href="mailto:info@ricohunt.com"
                  className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition-colors hover:bg-white/10"
                >
                  <span className="material-symbols-outlined text-base text-[#f5a623]">mail</span>
                  info@ricohunt.com
                </a>
                <a
                  href="https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20know%20more%20about%20Rico%20Hunt"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition-colors hover:bg-white/10"
                >
                  <span className="material-symbols-outlined text-base text-[#f5a623]">chat</span>
                  WhatsApp
                </a>
                <Link
                  href="/contact"
                  className="inline-flex items-center gap-2 rounded-lg bg-[#f5a623] px-4 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
                >
                  Send a message →
                </Link>
              </div>
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
          <span className="text-xs font-medium text-white">About</span>
          <Link href="/contact" className="text-xs text-text-tertiary transition-colors hover:text-white">Contact</Link>
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">Terms</Link>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">Privacy</Link>
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">Refunds</Link>
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

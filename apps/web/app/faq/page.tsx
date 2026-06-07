import type { Metadata } from "next";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export const metadata: Metadata = {
  title: "FAQ | Rico Hunt",
  description: "Frequently asked questions about Rico Hunt — where jobs come from, how AI matching works, what data we store, and how applications are handled.",
};

const faqs = [
  {
    question: "Where do the jobs on Rico Hunt come from?",
    answer: (
      <>
        <p>
          Rico Hunt sources live job listings using the{" "}
          <strong className="text-white">JSearch API</strong> (powered by RapidAPI), which
          aggregates real-time job data from major job boards active in the UAE and GCC region —
          including LinkedIn, Indeed, Glassdoor, Bayt, and others.
        </p>
        <p className="mt-3">
          We do not own or control the underlying listings. Job data is pulled from these
          external sources, filtered, and scored against your CV and career profile to surface
          the most relevant opportunities.
        </p>
      </>
    ),
  },
  {
    question: "Does Rico guarantee I will get a job?",
    answer: (
      <p>
        No. Rico Hunt is a job search tool — not an employment agency, recruiter, or placement
        service. We help you discover relevant roles, manage your applications, and improve your
        strategy. Whether you receive an interview or a job offer depends entirely on the
        employer. We make no guarantee of any employment outcome.
      </p>
    ),
  },
  {
    question: "Are the job listings verified or accurate?",
    answer: (
      <>
        <p>
          Rico Hunt displays job data sourced from third-party providers. We do our best to
          surface relevant and timely listings, but we cannot independently verify the accuracy,
          current availability, or legitimacy of every posting.
        </p>
        <p className="mt-3">
          <strong className="text-white">You should always verify job details directly</strong> —
          including the employer, role title, salary, location, visa requirements, and application
          process — before applying. Rico Hunt is not liable for inaccurate or outdated listings.
        </p>
      </>
    ),
  },
  {
    question: "Can Rico's AI make mistakes?",
    answer: (
      <>
        <p>
          Yes. Rico uses AI for CV analysis, job matching, and career guidance. AI-generated
          outputs can contain errors, omissions, or outdated information. Match scores and role
          suggestions are estimates — not guarantees of fit.
        </p>
        <p className="mt-3">
          Use AI insights as one input among many. Always review roles yourself and apply your
          own judgment before taking action.
        </p>
      </>
    ),
  },
  {
    question: "Will Rico apply to jobs without my permission?",
    answer: (
      <p>
        No. Rico Hunt will never submit a job application on your behalf without your explicit
        confirmation. Every application action requires your approval before it proceeds.
        You remain in full control at every step.
      </p>
    ),
  },
  {
    question: "Is Rico Hunt a recruitment agency?",
    answer: (
      <p>
        No. Rico Hunt is a software platform, not an employer, staffing agency, or recruitment
        agency. We do not represent employers, negotiate offers, or place candidates in roles.
        We are a tool to help you run your own job search more effectively.
      </p>
    ),
  },
  {
    question: "What data does Rico store about me?",
    answer: (
      <>
        <p>
          Rico may store your account details, uploaded CV, parsed CV content, career preferences,
          chat messages, and job activity. This data is used to personalise your experience and
          power job matching.
        </p>
        <p className="mt-3">
          We do not sell your personal data to employers, recruiters, or third parties. You can
          request deletion of your data at any time by emailing{" "}
          <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
            info@ricohunt.com
          </a>
          . For full details, see our{" "}
          <Link href="/privacy" className="text-[#f5a623] hover:opacity-80">
            Privacy Policy
          </Link>
          .
        </p>
      </>
    ),
  },
  {
    question: "Is Rico Hunt in early access?",
    answer: (
      <>
        <p>
          Yes. Rico Hunt is currently in active development and early access. Features are being
          added and refined based on user feedback. You may encounter rough edges or limitations
          as the platform evolves.
        </p>
        <p className="mt-3">
          If you encounter a problem or have a suggestion, we want to hear from you —{" "}
          <Link href="/contact" className="text-[#f5a623] hover:opacity-80">
            contact us
          </Link>{" "}
          or email{" "}
          <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
            info@ricohunt.com
          </a>
          .
        </p>
      </>
    ),
  },
  {
    question: "Who operates Rico Hunt?",
    answer: (
      <p>
        Rico Hunt is operated by{" "}
        <strong className="text-white">
          Eco Technology Environment Protection Services L.L.C
        </strong>
        , a company registered in the United Arab Emirates. For questions or support, contact us
        at{" "}
        <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">
          info@ricohunt.com
        </a>{" "}
        or via{" "}
        <a href="https://wa.me/971585989080" className="text-[#f5a623] hover:opacity-80">
          WhatsApp
        </a>
        .
      </p>
    ),
  },
];

export default function FAQPage() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#0a0a1a]">
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
          <div className="mb-10">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              Help &amp; Transparency
            </p>
            <h1 className="mb-4 text-3xl font-semibold text-white md:text-4xl">
              Frequently Asked Questions
            </h1>
            <p className="text-base leading-7 text-text-secondary">
              Answers to common questions about where jobs come from, how Rico works, and what
              to expect from the platform.
            </p>
          </div>

          <div className="space-y-6">
            {faqs.map((faq, index) => (
              <div
                key={index}
                className="rounded-xl border border-white/10 bg-white/5 p-6"
              >
                <h2 className="mb-3 text-base font-semibold text-white">
                  {faq.question}
                </h2>
                <div className="text-sm leading-7 text-text-secondary">
                  {faq.answer}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-10 rounded-xl border border-[#f5a623]/20 bg-[#f5a623]/5 p-6">
            <h2 className="mb-2 text-base font-semibold text-white">Still have a question?</h2>
            <p className="mb-4 text-sm text-text-secondary">
              We read every message. Reach out and we&apos;ll respond as soon as possible.
            </p>
            <div className="flex flex-wrap gap-3">
              <a
                href="mailto:info@ricohunt.com"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#f5a623] px-4 py-2 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
              >
                Email us →
              </a>
              <Link
                href="/contact"
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white transition-colors hover:bg-white/10"
              >
                Contact page
              </Link>
            </div>
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
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">Refunds</Link>
          <span className="text-xs font-medium text-white">FAQ</span>
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

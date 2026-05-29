"use client";

import { MotionConfig, motion } from "framer-motion";
import Link from "next/link";
import type { ReactNode } from "react";

const intelligenceLoop = [
  "Reading your CV",
  "Understanding your experience",
  "Finding matching UAE jobs",
  "Tracking your applications",
  "Sending job alerts",
];

// The core product story, told as one continuous flow. Each step names a concrete
// outcome so a first-time visitor understands the whole loop in a single glance.
const productFlow = [
  {
    step: "01",
    title: "Upload your CV",
    body: "Rico reads your experience, skills, education, and career history.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 16V4M12 4 8 8M12 4l4 4" />
        <path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
      </svg>
    ),
  },
  {
    step: "02",
    title: "Build your career profile",
    body: "Rico turns your CV into a living profile it can use to match you with better jobs.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0" />
      </svg>
    ),
  },
  {
    step: "03",
    title: "Find matching UAE jobs",
    body: "Rico searches for roles that fit your experience, target role, salary, and location.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="m21 21-4.3-4.3" />
      </svg>
    ),
  },
  {
    step: "04",
    title: "Track your applications",
    body: "Keep your saved jobs, opened links, applications, and follow-ups in one place.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    step: "05",
    title: "Get guidance and alerts",
    body: "Rico tells you what matters next — a new job match, a missing skill, or a follow-up reminder.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 12h4l2 6 4-12 2 6h6" />
      </svg>
    ),
  },
];

const memoryItems = [
  "Your CV and experience",
  "Target roles and preferred locations",
  "Salary expectations",
  "Application history",
  "Follow-up reminders",
];

const liveMatches = [
  {
    role: "HSE Manager",
    score: "94",
    signal: "Strong match with your safety and compliance experience",
  },
  {
    role: "Operations Manager",
    score: "89",
    signal: "Good match with your UAE experience",
  },
  {
    role: "Environmental Compliance Officer",
    score: "86",
    signal: "Matches your regulatory and inspection background",
  },
];

function RicoCardPanel({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, delay, ease: "easeOut" }}
      whileHover={{ y: -4 }}
      className={`rico-card rounded-[28px] p-5 transition-all duration-300 hover:border-[rgba(0,229,255,0.22)] hover:shadow-[0_28px_80px_rgba(0,0,0,0.38),0_0_50px_rgba(0,229,255,0.055)] md:p-6 ${className}`}
    >
      <div className="relative z-10 h-full">{children}</div>
    </motion.div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: "easeOut" }}
      className="mx-auto mb-10 max-w-3xl text-center"
    >
      <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.28em] text-cyan">
        {eyebrow}
      </p>
      <h2 className="font-display text-3xl font-semibold text-white md:text-5xl">
        {title}
      </h2>
      <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-text-secondary md:text-lg">
        {body}
      </p>
    </motion.div>
  );
}

export default function LandingPage() {
  return (
    <MotionConfig reducedMotion="user">
      <div className="relative min-h-screen overflow-x-hidden bg-background text-white">
        <div className="fixed inset-0 pointer-events-none z-0">
          <motion.div
            aria-hidden="true"
            animate={{ opacity: [0.45, 0.8, 0.45], scale: [1, 1.04, 1] }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -left-32 -top-40 h-[560px] w-[560px] rounded-full bg-magenta-dim blur-[140px]"
          />
          <motion.div
            aria-hidden="true"
            animate={{ opacity: [0.35, 0.72, 0.35], scale: [1.02, 1, 1.02] }}
            transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -right-28 top-[20%] h-[520px] w-[520px] rounded-full bg-cyan-dim blur-[140px]"
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.04)_0%,rgba(255,255,255,0)_18%,rgba(255,255,255,0.025)_100%)]" />
        </div>

        <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-black tracking-tight text-white"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-sm font-black text-[#0a0a1a] shadow-[0_0_28px_rgba(245,166,35,0.35)]">
              R
            </span>
            <span>
              Rico<span className="text-[#f5a623]"> Hunt</span>
            </span>
          </Link>
          <nav className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm text-text-secondary transition-colors hover:text-white"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="rounded-full border border-magenta/40 bg-magenta/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-magenta/25"
            >
              Sign up free
            </Link>
          </nav>
        </header>

        <main className="relative z-10">
          <section className="mx-auto grid min-h-[calc(100vh-73px)] max-w-7xl items-center gap-12 px-5 py-16 md:grid-cols-[1fr_0.88fr] md:px-10 lg:px-16">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.75, ease: "easeOut" }}
              className="max-w-3xl"
            >
              <p className="mb-5 inline-flex rounded-full border border-cyan/25 bg-cyan/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.26em] text-cyan">
                Your AI job-hunt partner in the UAE
              </p>
              <h1 className="font-display text-[clamp(2.5rem,7vw,5.5rem)] font-semibold leading-[1.02] tracking-tight text-text-primary">
                Upload your CV.{" "}
                <span className="bg-gradient-to-r from-magenta to-cyan bg-clip-text text-transparent">
                  Let Rico run your job search smarter.
                </span>
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-text-secondary md:text-xl">
                Rico is your AI job-hunt partner in the UAE. It reads your CV,
                understands your experience, finds matching jobs, tracks your
                applications, and guides your next move — in English and Arabic.
              </p>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-text-tertiary">
                Rico never applies silently. You approve every important action.
              </p>
              <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                  <Link
                    href="/upload"
                    className="inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-7 py-4 text-base font-semibold text-black transition-opacity hover:opacity-90 sm:w-auto"
                  >
                    Upload your CV
                  </Link>
                </motion.div>
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                  <Link
                    href="/signup"
                    className="inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-7 py-4 text-base font-semibold text-white backdrop-blur-xl transition-colors hover:bg-white/[0.08] sm:w-auto"
                  >
                    Start free
                  </Link>
                </motion.div>
              </div>
            </motion.div>

            <RicoCardPanel
              delay={0.15}
              className="mx-auto w-full max-w-[560px]"
            >
              <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                    What Rico does for you
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">
                    Working on your job search
                  </h2>
                </div>
                <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan">
                  Online
                </span>
              </div>
              <div className="space-y-4">
                {intelligenceLoop.map((item, index) => (
                  <div
                    key={item}
                    className="border-b border-white/5 pb-4 last:border-b-0 last:pb-0"
                  >
                    <div className="mb-2 flex items-center justify-between gap-4">
                      <p className="text-sm font-medium text-white">{item}</p>
                      <p className="font-mono text-[11px] text-text-tertiary">
                        {index === 0 ? "ready" : "watching"}
                      </p>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
                      <motion.div
                        initial={{ width: "18%" }}
                        animate={{ width: `${92 - index * 9}%` }}
                        transition={{
                          duration: 1.1,
                          delay: 0.25 + index * 0.1,
                          ease: "easeOut",
                        }}
                        className="h-full rounded-full bg-gradient-to-r from-magenta to-cyan"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </RicoCardPanel>
          </section>

          <section className="px-5 py-16 md:px-10 lg:px-16">
            <SectionHeading
              eyebrow="How Rico works"
              title="From CV to better job opportunities"
              body="Upload your CV once. Rico reads your experience and starts finding matching UAE jobs right away."
            />
            <div className="mx-auto max-w-7xl">
              {/* Connecting line behind the steps (desktop only) */}
              <div className="relative grid gap-4 md:grid-cols-5">
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute left-0 right-0 top-[34px] hidden h-px bg-gradient-to-r from-magenta/40 via-cyan/40 to-magenta/40 md:block"
                />
                {productFlow.map((node, index) => (
                  <motion.div
                    key={node.step}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: index * 0.08, ease: "easeOut" }}
                    className="relative flex flex-col items-center text-center"
                  >
                    <div className="relative z-10 flex h-[68px] w-[68px] items-center justify-center rounded-2xl border border-border-soft bg-surface-elevated shadow-[0_12px_40px_rgba(0,0,0,0.35)]">
                      <span className="h-7 w-7 text-cyan [&>svg]:h-full [&>svg]:w-full">
                        {node.icon}
                      </span>
                      <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-br from-magenta to-cyan font-mono text-[10px] font-bold text-black">
                        {index + 1}
                      </span>
                    </div>
                    <h3 className="mt-5 text-base font-semibold text-text-primary">
                      {node.title}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      {node.body}
                    </p>
                    {/* Down-arrow connector on mobile/stacked layout */}
                    {index < productFlow.length - 1 && (
                      <div
                        aria-hidden="true"
                        className="my-3 h-5 w-px bg-gradient-to-b from-cyan/50 to-transparent md:hidden"
                      />
                    )}
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          <section className="px-5 py-16 md:px-10 lg:px-16">
            <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
              <RicoCardPanel>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                  Rico remembers your career goals
                </p>
                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                  Every search gets smarter
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  Every search gets smarter because Rico remembers your CV,
                  target roles, preferred locations, and application history.
                </p>
              </RicoCardPanel>
              <RicoCardPanel delay={0.08}>
                <div className="grid gap-3 sm:grid-cols-2">
                  {memoryItems.map((item) => (
                    <div
                      key={item}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                    >
                      <div className="mb-4 h-1 w-10 rounded-full bg-gradient-to-r from-magenta to-cyan" />
                      <p className="text-sm font-medium text-white">{item}</p>
                    </div>
                  ))}
                </div>
              </RicoCardPanel>
            </div>
          </section>

          <section className="px-5 py-16 md:px-10 lg:px-16">
            <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[1.1fr_0.9fr]">
              <RicoCardPanel>
                <div className="mb-6 flex items-center justify-between gap-4">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan">
                      Smart job matching
                    </p>
                    <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                      Jobs that fit your CV, not random job-board noise
                    </h2>
                  </div>
                  <span className="hidden rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta sm:inline-flex">
                    UAE jobs
                  </span>
                </div>
                <div className="space-y-3">
                  {liveMatches.map((match) => (
                    <div
                      key={match.role}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="text-base font-semibold text-white">
                            {match.role}
                          </h3>
                          <p className="mt-1 text-sm text-text-tertiary">
                            {match.signal}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-mono text-2xl text-cyan">
                            {match.score}
                          </p>
                          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                            fit
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </RicoCardPanel>
              <RicoCardPanel delay={0.08}>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                  Job alerts when something important changes
                </p>
                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                  Rico tells you when to act
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  Rico watches your saved jobs, new matches, and application
                  status — and alerts you when something is worth your
                  attention.
                </p>
                <div className="mt-8 rounded-lg border border-cyan/[0.18] bg-cyan/10 p-4">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan">
                    Latest alert
                  </p>
                  <p className="mt-3 text-sm leading-6 text-white">
                    A new job matches your CV and target salary. Rico is ready
                    to show it to you.
                  </p>
                </div>
              </RicoCardPanel>
            </div>
          </section>

          <section className="px-5 py-16 md:px-10 lg:px-16">
            <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
              <RicoCardPanel>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan">
                  You stay in control
                </p>
                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                  Rico works for you, not instead of you
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  Rico finds jobs, ranks them, and tracks your progress. You
                  decide when to apply, when to pause, and which direction to
                  take your career.
                </p>
              </RicoCardPanel>
              <RicoCardPanel delay={0.08}>
                <div className="grid gap-4 md:grid-cols-3">
                  {[
                    "No setup wizard",
                    "No enterprise forms",
                    "No silent applying",
                  ].map((item) => (
                    <div
                      key={item}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                    >
                      <p className="text-sm font-semibold text-white">{item}</p>
                      <div className="mt-5 h-1 rounded-full bg-gradient-to-r from-magenta to-cyan" />
                    </div>
                  ))}
                </div>
              </RicoCardPanel>
            </div>
          </section>

          <section className="px-5 py-16 md:px-10 lg:px-16">
            <SectionHeading
              eyebrow="Pricing"
              title="Simple plans for serious career moves"
              body="Start free with 50 AI messages and 10 saved jobs. Upgrade when you need more."
            />
            <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-2">
              <RicoCardPanel
                delay={0.08}
                className="border-magenta/30 bg-magenta/[0.03]"
              >
                <div className="mb-4 inline-flex rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta">
                  Popular
                </div>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                  Pro
                </p>
                <h3 className="mt-4 text-4xl font-semibold text-white">
                  AED 29
                </h3>
                <p className="mt-2 text-sm text-text-secondary">/month</p>
                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                  <li>300 AI messages per month</li>
                  <li>100 saved jobs</li>
                  <li>20 profile optimisations per month</li>
                  <li>Smart AI role recommendations</li>
                  <li>Advanced match scoring</li>
                </ul>
                <Link
                  href="/subscription"
                  className="mt-8 inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-6 py-3 text-sm font-semibold text-black transition-opacity hover:opacity-90"
                >
                  Upgrade to Pro
                </Link>
              </RicoCardPanel>
              <RicoCardPanel delay={0.16}>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                  Premium
                </p>
                <h3 className="mt-4 text-4xl font-semibold text-white">
                  AED 49
                </h3>
                <p className="mt-2 text-sm text-text-secondary">/month</p>
                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                  <li>1500 AI messages per month</li>
                  <li>Unlimited saved jobs</li>
                  <li>100 profile optimisations per month</li>
                  <li>Everything in Pro</li>
                  <li>Auto-apply system</li>
                  <li>Premium recommendations</li>
                </ul>
                <Link
                  href="/subscription"
                  className="mt-8 inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/[0.08]"
                >
                  Upgrade to Premium
                </Link>
              </RicoCardPanel>
            </div>
            <div className="mx-auto mt-6 max-w-5xl">
              <div className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.03] px-5 py-4">
                <div>
                  <span className="text-[13px] font-semibold text-[#c0c0d8]">
                    Free
                  </span>
                  <span className="ml-3 text-[12px] text-[#5a5a7a]">
                    50 AI messages · 10 saved jobs · 1 profile optimisation/mo
                  </span>
                </div>
                <Link
                  href="/signup"
                  className="text-[12px] font-semibold text-[#7b6fff] hover:underline whitespace-nowrap"
                >
                  Sign up free →
                </Link>
              </div>
            </div>
          </section>

          <section className="px-5 pb-20 pt-10 md:px-10 lg:px-16">
            <RicoCardPanel className="mx-auto max-w-5xl text-center">
              <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                Start free
              </p>
              <h2 className="mx-auto mt-4 max-w-3xl text-3xl font-semibold text-white md:text-5xl">
                Upload your CV. Let Rico find your next job.
              </h2>
              <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-text-secondary">
                Upload your CV and Rico goes to work. It reads your experience,
                finds matching UAE jobs, and tells you what to do next — in
                English and Arabic.
              </p>
              <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
                <Link
                  href="/upload"
                  className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-7 py-4 text-base font-semibold text-black transition-opacity hover:opacity-90"
                >
                  Upload your CV
                </Link>
                <Link
                  href="/signup"
                  className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-7 py-4 text-base font-semibold text-white transition-colors hover:bg-white/[0.08]"
                >
                  Start free
                </Link>
              </div>
            </RicoCardPanel>
          </section>
        </main>
        <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
          <div className="mb-3 flex items-center justify-center gap-6">
            <Link
              href="/terms"
              className="text-xs text-text-tertiary transition-colors hover:text-white"
            >
              Terms
            </Link>
            <Link
              href="/privacy"
              className="text-xs text-text-tertiary transition-colors hover:text-white"
            >
              Privacy
            </Link>
            <Link
              href="/refund-policy"
              className="text-xs text-text-tertiary transition-colors hover:text-white"
            >
              Refunds
            </Link>
          </div>
          <p className="text-xs text-text-tertiary">
            © 2026 Rico Hunt. All rights reserved.
          </p>
        </footer>
      </div>
    </MotionConfig>
  );
}

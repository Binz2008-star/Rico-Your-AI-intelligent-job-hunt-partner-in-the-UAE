"use client";

import { MotionConfig, motion } from "framer-motion";
import Link from "next/link";
import type { ReactNode } from "react";

const intelligenceLoop = [
    "CV profile extraction",
    "Role intelligence",
    "Opportunity matching",
    "Application tracking",
    "Telegram and job alerts",
];

const howItWorks = [
    {
        eyebrow: "01",
        title: "Upload your CV",
        body: "Rico reads your history first, then builds a private career profile without a setup wizard.",
    },
    {
        eyebrow: "02",
        title: "Profile intelligence forms",
        body: "Skills, trajectory, seniority, preferences, compensation signals, and gaps become structured memory.",
    },
    {
        eyebrow: "03",
        title: "The market is filtered",
        body: "Roles are ranked by fit, timing, momentum, and what Rico already knows about your direction.",
    },
    {
        eyebrow: "04",
        title: "You approve the moves",
        body: "Rico tracks, drafts, and alerts in the background while important decisions stay under your control.",
    },
];

const memoryItems = [
    "Career stack and seniority",
    "Target roles and rejected paths",
    "Recruiter response history",
    "Compensation and location signals",
    "Application outcomes",
];

const liveMatches = [
    { role: "Senior Python Platform Engineer", score: "94", signal: "High trajectory fit" },
    { role: "AI Operations Lead", score: "89", signal: "Strong timing window" },
    { role: "Backend Automation Architect", score: "86", signal: "Compensation momentum" },
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
            <div className="relative z-10 h-full">
                {children}
            </div>
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
                    <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
                        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-magenta to-cyan text-sm font-black shadow-[0_0_28px_rgba(255,45,142,0.28)]">
                            R
                        </span>
                        <span>
                            Rico<span className="text-magenta">.ai</span>
                        </span>
                    </Link>
                    <nav className="flex items-center gap-3">
                        <Link href="/login" className="text-sm text-text-secondary transition-colors hover:text-white">
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
                                CV-first trajectory intelligence
                            </p>
                            <h1 className="font-display text-[clamp(3rem,8vw,6.8rem)] font-semibold leading-[0.95] tracking-normal text-white">
                                Rico AI is your autonomous{" "}
                                <span className="bg-gradient-to-r from-magenta to-cyan bg-clip-text text-transparent">
                                    career operating system
                                </span>
                            </h1>
                            <p className="mt-7 max-w-2xl text-lg leading-8 text-text-secondary md:text-xl">
                                Upload your CV once. Rico extracts your profile, remembers your trajectory,
                                watches the market, and asks before important career moves.
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
                                        Sign up free
                                    </Link>
                                </motion.div>
                            </div>
                        </motion.div>

                        <RicoCardPanel delay={0.15} className="mx-auto w-full max-w-[560px]">
                            <div className="mb-6 flex items-center justify-between gap-4">
                                <div>
                                    <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                                        Invisible background intelligence
                                    </p>
                                    <h2 className="mt-2 text-2xl font-semibold text-white">
                                        Live profile loop
                                    </h2>
                                </div>
                                <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan">
                                    Online
                                </span>
                            </div>
                            <div className="space-y-4">
                                {intelligenceLoop.map((item, index) => (
                                    <div key={item} className="border-b border-white/5 pb-4 last:border-b-0 last:pb-0">
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
                                                transition={{ duration: 1.1, delay: 0.25 + index * 0.1, ease: "easeOut" }}
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
                            title="A career system that starts from your history"
                            body="The landing flow is intentionally short: upload, extraction, matching, approval. Rico does the heavy work quietly."
                        />
                        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-2 lg:grid-cols-4">
                            {howItWorks.map((step, index) => (
                                <RicoCardPanel key={step.title} delay={0.08 * index}>
                                    <p className="font-mono text-xs text-cyan">{step.eyebrow}</p>
                                    <h3 className="mt-5 text-xl font-semibold text-white">{step.title}</h3>
                                    <p className="mt-4 text-sm leading-6 text-text-secondary">{step.body}</p>
                                </RicoCardPanel>
                            ))}
                        </div>
                    </section>

                    <section className="px-5 py-16 md:px-10 lg:px-16">
                        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
                            <RicoCardPanel>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                                    What Rico remembers
                                </p>
                                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                                    Memory that compounds every search
                                </h2>
                                <p className="mt-5 text-base leading-7 text-text-secondary">
                                    Rico turns your CV and outcomes into a living profile, so each match is judged against
                                    your actual trajectory instead of a one-time keyword search.
                                </p>
                            </RicoCardPanel>
                            <RicoCardPanel delay={0.08}>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    {memoryItems.map((item) => (
                                        <div key={item} className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4">
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
                                            Opportunity engine
                                        </p>
                                        <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                                            Live matching without the job-board noise
                                        </h2>
                                    </div>
                                    <span className="hidden rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta sm:inline-flex">
                                        Market scan
                                    </span>
                                </div>
                                <div className="space-y-3">
                                    {liveMatches.map((match) => (
                                        <div key={match.role} className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4">
                                            <div className="flex items-start justify-between gap-4">
                                                <div>
                                                    <h3 className="text-base font-semibold text-white">{match.role}</h3>
                                                    <p className="mt-1 text-sm text-text-tertiary">{match.signal}</p>
                                                </div>
                                                <div className="text-right">
                                                    <p className="font-mono text-2xl text-cyan">{match.score}</p>
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
                                    Telegram and job alerts
                                </p>
                                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                                    Signals arrive when timing changes
                                </h2>
                                <p className="mt-5 text-base leading-7 text-text-secondary">
                                    Rico can watch role movement, recruiter patterns, and application status, then surface
                                    the few signals that matter for your next move.
                                </p>
                                <div className="mt-8 rounded-lg border border-cyan/[0.18] bg-cyan/10 p-4">
                                    <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan">
                                        Next alert
                                    </p>
                                    <p className="mt-3 text-sm leading-6 text-white">
                                        A senior backend role crossed the fit threshold after your CV profile update.
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
                                    Autonomous intelligence, approval-first action
                                </h2>
                                <p className="mt-5 text-base leading-7 text-text-secondary">
                                    Rico can analyze, rank, draft, and track. You decide when to apply, when to pause,
                                    and what career direction is worth pursuing.
                                </p>
                            </RicoCardPanel>
                            <RicoCardPanel delay={0.08}>
                                <div className="grid gap-4 md:grid-cols-3">
                                    {["No setup wizard", "No enterprise forms", "No silent applying"].map((item) => (
                                        <div key={item} className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4">
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
                        <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-3">
                            <RicoCardPanel>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                                    Free
                                </p>
                                <h3 className="mt-4 text-4xl font-semibold text-white">AED 0</h3>
                                <p className="mt-2 text-sm text-text-secondary">/month</p>
                                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                                    <li>50 AI messages per month</li>
                                    <li>10 saved jobs</li>
                                    <li>1 profile optimisation</li>
                                </ul>
                                <Link
                                    href="/signup"
                                    className="mt-8 inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/[0.08]"
                                >
                                    Get started
                                </Link>
                            </RicoCardPanel>
                            <RicoCardPanel delay={0.08}>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                                    Pro
                                </p>
                                <h3 className="mt-4 text-4xl font-semibold text-white">AED 50</h3>
                                <p className="mt-2 text-sm text-text-secondary">/month</p>
                                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                                    <li>300 AI messages per month</li>
                                    <li>100 saved jobs</li>
                                    <li>20 profile optimisations per month</li>
                                </ul>
                                <Link
                                    href="/subscription"
                                    className="mt-8 inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/[0.08]"
                                >
                                    Upgrade to Pro
                                </Link>
                            </RicoCardPanel>
                            <RicoCardPanel delay={0.16} className="border-magenta/30 bg-magenta/[0.03]">
                                <div className="mb-4 inline-flex rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta">
                                    Popular
                                </div>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                                    Premium
                                </p>
                                <h3 className="mt-4 text-4xl font-semibold text-white">AED 150</h3>
                                <p className="mt-2 text-sm text-text-secondary">/month</p>
                                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                                    <li>1500 AI messages per month</li>
                                    <li>Unlimited saved jobs</li>
                                    <li>100 profile optimisations per month</li>
                                    <li>Premium recommendations</li>
                                    <li>Application automation</li>
                                </ul>
                                <Link
                                    href="/subscription"
                                    className="mt-8 inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-6 py-3 text-sm font-semibold text-black transition-opacity hover:opacity-90"
                                >
                                    Upgrade to Premium
                                </Link>
                            </RicoCardPanel>
                        </div>
                    </section>

                    <section className="px-5 pb-20 pt-10 md:px-10 lg:px-16">
                        <RicoCardPanel className="mx-auto max-w-5xl text-center">
                            <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                                Start free
                            </p>
                            <h2 className="mx-auto mt-4 max-w-3xl text-3xl font-semibold text-white md:text-5xl">
                                Give Rico your CV. Let the system build the intelligence layer.
                            </h2>
                            <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-text-secondary">
                                The first useful action is not a form. It is your career history becoming structured,
                                remembered, and ready for matching.
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
                                    Sign up free
                                </Link>
                            </div>
                        </RicoCardPanel>
                    </section>
                </main>
                <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
                    <div className="mb-3 flex items-center justify-center gap-6">
                        <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">Terms</Link>
                        <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">Privacy</Link>
                        <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">Refunds</Link>
                    </div>
                    <p className="text-xs text-text-tertiary">© 2026 Rico Hunt. All rights reserved.</p>
                </footer>
            </div>
        </MotionConfig>
    );
}

"use client";

/**
 * LandingPageV2 — production public landing, rebuilt to the approved
 * /design-preview prospectus (DEC-20260710-002, full public-landing parity).
 *
 * EN only. All copy is verbatim from the authoritative reference
 * (apps/web/public/design-preview/desktop-home-en-light.png + the shared
 * support-page colophon). No copy is invented. Sections intentionally NOT
 * implemented because they are below the 1800px reference capture / not in
 * any reference: the three-convictions body, an on-page rates section, and any
 * lower-tail copy. See the PR body "missing source needed" note.
 *
 * app/page.tsx is untouched — it still renders this default export and keeps
 * its auth redirect (ready && user -> /command).
 */

import { useState } from "react";
import Link from "next/link";
import { Fraunces } from "next/font/google";

/* Fraunces = the reference serif display, loaded landing-scoped (Inter +
   IBM Plex Mono are already global via app/layout). No new npm dependency. */
const fraunces = Fraunces({
    subsets: ["latin"],
    weight: ["400", "500", "600"],
    style: ["normal", "italic"],
    display: "swap",
    variable: "--font-fraunces-landing",
});

/* Reference palette: warm cream paper, near-black ink, one sun-red signal. */
const C = {
    bg: "#F1EADD",
    panel: "#F7F1E6",
    inset: "#EAE1D0",
    ink: "#1F1B15",
    ink70: "rgba(31,27,21,0.70)",
    ink55: "rgba(31,27,21,0.52)",
    ink40: "rgba(31,27,21,0.38)",
    hair: "rgba(31,27,21,0.16)",
    red: "#C6492E",
    footer: "#1A1712",
    footerInk: "#EFE7D6",
    footerInk60: "rgba(239,231,214,0.60)",
    footerHair: "rgba(239,231,214,0.20)",
} as const;

const SERIF = "var(--font-fraunces-landing), Georgia, serif";
const MONO = "var(--font-mono), ui-monospace, monospace";

/* Mono uppercase editorial label. */
function Mono({ children, className = "", style }: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) {
    return (
        <span className={`uppercase ${className}`} style={{ fontFamily: MONO, fontSize: 11, letterSpacing: "0.2em", ...style }}>
            {children}
        </span>
    );
}

/* Corner-tick plate (reference "PLATE 01" frame). */
function Plate({ className = "", style, children }: { className?: string; style?: React.CSSProperties; children: React.ReactNode }) {
    const t = "absolute w-2 h-2 pointer-events-none";
    const b = `1px solid ${C.hair}`;
    return (
        <div className={`relative rounded-[4px] ${className}`} style={{ background: C.panel, border: `1px solid ${C.hair}`, ...style }}>
            <span className={`${t} top-1.5 left-1.5`} style={{ borderTop: b, borderLeft: b }} aria-hidden="true" />
            <span className={`${t} top-1.5 right-1.5`} style={{ borderTop: b, borderRight: b }} aria-hidden="true" />
            <span className={`${t} bottom-1.5 left-1.5`} style={{ borderBottom: b, borderLeft: b }} aria-hidden="true" />
            <span className={`${t} bottom-1.5 right-1.5`} style={{ borderBottom: b, borderRight: b }} aria-hidden="true" />
            {children}
        </div>
    );
}

const NAV = [
    { label: "The idea", href: "#idea" },
    { label: "The system", href: "#system" },
    { label: "Rates", href: "/subscription" },
    { label: "Colophon", href: "#colophon" },
    { label: "Support", href: "/contact" },
];

function Masthead() {
    const [open, setOpen] = useState(false);
    return (
        <header style={{ borderBottom: `1px solid ${C.hair}` }}>
            <div className="max-w-6xl mx-auto px-5 sm:px-8">
                {/* row 1 */}
                <div className="flex items-center justify-between py-4 gap-4">
                    <div className="flex items-baseline gap-3 min-w-0">
                        <Link href="/" className="text-[1.35rem] leading-none tracking-tight" style={{ fontFamily: SERIF, color: C.ink }}>Rico Hunt</Link>
                        <Mono className="hidden sm:inline" style={{ color: C.ink55, letterSpacing: "0.18em" }}>— Volume I · Issue 03</Mono>
                    </div>
                    <nav className="hidden md:flex items-center gap-6">
                        {NAV.map((n) => (
                            <Link key={n.label} href={n.href} className="transition-opacity hover:opacity-60">
                                <Mono style={{ color: C.ink70, letterSpacing: "0.16em" }}>{n.label}</Mono>
                            </Link>
                        ))}
                    </nav>
                    <div className="flex items-center gap-3">
                        {/* EN / AR control — EN active; AR disabled (content not yet localized) */}
                        <span className="hidden sm:inline-flex items-center rounded-[3px] overflow-hidden" style={{ border: `1px solid ${C.hair}` }} title="Arabic — not yet available">
                            <span style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", background: C.ink, color: C.panel }}>EN</span>
                            <span aria-disabled="true" style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", color: C.ink40, cursor: "default" }}>عر</span>
                        </span>
                        <Link href="/command" className="whitespace-nowrap transition-opacity hover:opacity-60" style={{ borderBottom: `1px solid ${C.ink}` }}>
                            <span style={{ fontFamily: MONO, fontSize: 12, color: C.ink }}>Open Rico →</span>
                        </Link>
                        <button className="md:hidden p-1" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)} style={{ color: C.ink70 }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5">
                                {open ? <path strokeLinecap="round" d="M6 18L18 6M6 6l12 12" /> : <path strokeLinecap="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />}
                            </svg>
                        </button>
                    </div>
                </div>
                {/* row 2 */}
                <div className="flex items-center gap-4 pb-3">
                    <Mono style={{ color: C.ink55, letterSpacing: "0.16em" }}>Dubai · Abu Dhabi · Sharjah · 2026</Mono>
                    <span className="h-px flex-1" style={{ background: C.hair }} aria-hidden="true" />
                    <Mono className="hidden sm:inline" style={{ color: C.ink55, letterSpacing: "0.16em" }}>English · العربية</Mono>
                </div>
                {/* mobile nav */}
                {open && (
                    <div className="md:hidden flex flex-col gap-3 pb-4">
                        {NAV.map((n) => (
                            <Link key={n.label} href={n.href} onClick={() => setOpen(false)}>
                                <Mono style={{ color: C.ink70 }}>{n.label}</Mono>
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </header>
    );
}

function Hero() {
    return (
        <section className="max-w-6xl mx-auto px-5 sm:px-8 pt-16 sm:pt-24 pb-16">
            <p className="flex items-center gap-2.5 mb-10">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: C.red }} aria-hidden="true" />
                <Mono style={{ color: C.ink70, letterSpacing: "0.2em" }}>Prospectus — a quiet AI for a loud job market</Mono>
            </p>
            <h1 className="font-normal tracking-[-0.02em] text-[2.9rem] leading-[0.98] sm:text-[4.6rem] sm:leading-[0.95] max-w-4xl" style={{ fontFamily: SERIF, color: C.ink }}>
                A career,{" "}
                <span className="relative inline-block italic font-medium">
                    in conversation.
                    <svg className="absolute left-0 w-full" style={{ bottom: "0.06em", height: "0.16em" }} viewBox="0 0 300 8" preserveAspectRatio="none" aria-hidden="true">
                        <path d="M2 6 C 60 3, 120 5, 180 4 S 260 3, 298 5" fill="none" stroke={C.red} strokeWidth={4} strokeLinecap="round" />
                    </svg>
                </span>
            </h1>
            <p className="mt-8 max-w-xl text-[1.05rem] leading-relaxed" style={{ color: C.ink70 }}>
                Rico is a small, patient intelligence for people looking for real work in the UAE. It reads your CV, watches the market, and only writes back when there is a job worth writing back about.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-6">
                <Link href="/command" className="inline-flex items-center gap-2.5 px-6 py-3.5 rounded-full text-sm font-semibold transition-all hover:brightness-110" style={{ background: C.ink, color: C.panel }}>
                    Begin with Rico <span aria-hidden="true">→</span>
                </Link>
                <Link href="#system" className="underline underline-offset-4 decoration-1 transition-opacity hover:opacity-60" style={{ textDecorationColor: C.red }}>
                    <Mono style={{ color: C.ink70 }}>Read the notebook</Mono>
                </Link>
            </div>
        </section>
    );
}

function SystemSection() {
    return (
        <section id="system" className="max-w-6xl mx-auto px-5 sm:px-8 py-16" style={{ borderTop: `1px solid ${C.hair}` }}>
            <div className="grid lg:grid-cols-2 gap-12 lg:gap-16">
                {/* interview */}
                <div>
                    <div className="flex items-center gap-3 mb-8">
                        <Mono style={{ color: C.ink55 }}>Interview</Mono>
                        <span className="h-px w-10" style={{ background: C.hair }} aria-hidden="true" />
                        <Mono style={{ color: C.ink55 }}>Transcribed, in full</Mono>
                    </div>
                    <div className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-8">
                        <Mono style={{ color: C.ink40 }}>You</Mono>
                        <p className="text-[1.25rem] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
                            I want a senior product role in the UAE. Above thirty thousand. I don&apos;t want to read another job board.
                        </p>
                        <div>
                            <Mono style={{ color: C.red }}>Rico</Mono>
                            <p className="mt-2 leading-relaxed" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.14em", color: C.ink40, textTransform: "uppercase" }}>
                                Reads CV · Scans 6 feeds · Scores fit
                            </p>
                        </div>
                        <p className="text-[1.25rem] leading-snug italic" style={{ fontFamily: SERIF, color: C.ink }}>
                            Then don&apos;t. I&apos;ve read your CV. I&apos;ll watch the market for you and only speak when there&apos;s something worth your attention.
                        </p>
                    </div>
                    <div className="mt-10 pt-8" style={{ borderTop: `1px solid ${C.hair}` }}>
                        <Mono style={{ color: C.ink55 }}>Ask the next question</Mono>
                        {/* illustrative, non-interactive (reference is a static prospectus) */}
                        <div className="mt-4 text-[1.4rem]" style={{ fontFamily: SERIF, color: C.ink }} aria-hidden="true">
                            Product roles above AED 30k<span style={{ color: C.red }}>|</span>
                        </div>
                        <div className="mt-5 flex flex-wrap gap-2.5" aria-hidden="true">
                            {["Product roles above AED 30k", "Fintech openings in Abu Dhabi", "What's missing from my CV"].map((c) => (
                                <span key={c} className="px-3 py-1.5 rounded-full" style={{ border: `1px solid ${C.hair}`, fontFamily: MONO, fontSize: 11, color: C.ink70 }}>{c}</span>
                            ))}
                        </div>
                    </div>
                </div>
                {/* sample-match plate */}
                <Plate className="p-7 sm:p-8">
                    <div className="flex items-center gap-3 mb-6">
                        <Mono style={{ color: C.ink55 }}>Plate 01 — Sample match</Mono>
                        <span className="h-px flex-1" style={{ background: C.hair }} aria-hidden="true" />
                        <span className="px-2.5 py-0.5 rounded-full" style={{ border: `1px solid ${C.red}`, fontFamily: MONO, fontSize: 10, letterSpacing: "0.12em", color: C.red, textTransform: "uppercase" }}>Illustration</span>
                    </div>
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <Mono style={{ color: C.ink55 }}>Noon · Dubai</Mono>
                            <h3 className="mt-3 text-[2rem] leading-[1.05] font-normal" style={{ fontFamily: SERIF, color: C.ink }}>Senior Product<br />Manager</h3>
                            <p className="mt-3" style={{ fontFamily: MONO, fontSize: 13, color: C.ink70 }}>AED 32 – 42k</p>
                        </div>
                        <span className="inline-flex items-center justify-center w-16 h-16 rounded-full flex-shrink-0 text-xl" style={{ border: `1.5px solid ${C.red}`, fontFamily: SERIF, color: C.red }}>91</span>
                    </div>
                    <div className="my-6 h-px" style={{ background: C.hair }} aria-hidden="true" />
                    <Mono style={{ color: C.ink55 }}>Why this fits</Mono>
                    <ol className="mt-4 flex flex-col gap-3.5">
                        {[
                            "Five years of product depth, exactly the seniority asked for.",
                            "UAE e-commerce background reads as a strong domain signal.",
                            "Arabic fluency is a listed requirement — you match.",
                        ].map((t, i) => (
                            <li key={i} className="grid grid-cols-[auto_1fr] gap-3">
                                <Mono style={{ color: C.red }}>{String(i + 1).padStart(2, "0")}</Mono>
                                <span className="text-[0.95rem] leading-snug" style={{ color: C.ink }}>{t}</span>
                            </li>
                        ))}
                    </ol>
                    <div className="mt-6 p-4 rounded-[3px]" style={{ background: C.inset }}>
                        <Mono style={{ color: C.red }}>Worth knowing</Mono>
                        <p className="mt-1.5 text-[0.95rem]" style={{ color: C.ink70 }}>Occasional on-site weeks in Riyadh.</p>
                    </div>
                </Plate>
            </div>
        </section>
    );
}

function BilingualBand() {
    return (
        <section className="py-10" style={{ borderTop: `1px solid ${C.hair}`, borderBottom: `1px solid ${C.hair}` }}>
            <div className="max-w-6xl mx-auto px-5 sm:px-8">
                <p className="text-[1.35rem] sm:text-[1.6rem] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
                    Bilingual by design — <span className="italic">English and العربية.</span> · Approval-first — <span className="italic">Rico never applies without you.</span> · Delivered to Telegram — <span className="italic">your inbox stays quiet.</span>
                </p>
            </div>
        </section>
    );
}

function IdeaSection() {
    return (
        <section id="idea" className="max-w-6xl mx-auto px-5 sm:px-8 py-24 sm:py-32">
            <div className="grid lg:grid-cols-[auto_1fr] gap-8 lg:gap-16">
                <Mono style={{ color: C.ink55 }}>§ The idea</Mono>
                <h2 className="font-normal tracking-[-0.015em] text-[2.6rem] leading-[1.02] sm:text-[4rem] sm:leading-[0.98] max-w-3xl" style={{ fontFamily: SERIF, color: C.ink }}>
                    Three quiet convictions,{" "}
                    <span className="italic font-medium">held stubbornly.</span>
                </h2>
            </div>
        </section>
    );
}

/* Shared marketing colophon footer (the same footer pattern shown on the
   /design-preview support page). The preview-only disclaimer line
   ("Everything you see here is design…") is intentionally OMITTED to avoid
   preview leakage on production; the rest is verbatim. */
function Colophon() {
    const meta = [
        { k: "Set in", v: "Fraunces · Inter · IBM Plex Mono" },
        { k: "Palette", v: "Paper, ink, and one hot signal" },
        { k: "Languages", v: "English · العربية" },
        { k: "Filed from", v: "The UAE, 2026" },
    ];
    const elsewhere = [
        { label: "Support", href: "/contact" },
        { label: "Terms", href: "/terms" },
        { label: "Privacy", href: "/privacy" },
        { label: "Pricing", href: "/subscription" },
    ];
    return (
        <footer id="colophon" style={{ background: C.footer, color: C.footerInk }}>
            <div className="max-w-6xl mx-auto px-5 sm:px-8 py-16">
                <div className="grid lg:grid-cols-2 gap-12">
                    <div>
                        <span className="uppercase" style={{ fontFamily: MONO, fontSize: 11, letterSpacing: "0.2em", color: C.footerInk60 }}>Colophon</span>
                        <h2 className="mt-5 text-[2.2rem] sm:text-[2.8rem] leading-[1.02] font-normal" style={{ fontFamily: SERIF }}>
                            Filed quietly from <span className="italic" style={{ color: C.red }}>the desert.</span>
                        </h2>
                        <p className="mt-5 max-w-md leading-relaxed" style={{ color: C.footerInk60 }}>
                            Rico Hunt is an editorial-grade AI job partner for the UAE.
                        </p>
                    </div>
                    <div className="grid grid-cols-2 gap-x-8 gap-y-7 self-start lg:pt-2">
                        {meta.map((m) => (
                            <div key={m.k}>
                                <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>{m.k}</span>
                                <p className="mt-1.5 text-[0.95rem]" style={{ fontFamily: SERIF }}>{m.v}</p>
                            </div>
                        ))}
                        <div className="col-span-2 mt-2 pt-6" style={{ borderTop: `1px solid ${C.footerHair}` }}>
                            <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>Elsewhere</span>
                            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                                {elsewhere.map((e) => (
                                    <Link key={e.label} href={e.href} className="text-sm underline underline-offset-4 decoration-1 transition-opacity hover:opacity-70" style={{ color: C.footerInk, textDecorationColor: C.footerHair }}>{e.label}</Link>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
                <div className="mt-14 pt-6 flex items-center justify-between" style={{ borderTop: `1px solid ${C.footerHair}` }}>
                    <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>© 2026 Rico Hunt</span>
                    <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>Volume I · Issue 03</span>
                </div>
            </div>
        </footer>
    );
}

export default function LandingPageV2() {
    return (
        <div className={`min-h-screen overflow-x-hidden ${fraunces.variable}`} style={{ background: C.bg, color: C.ink, fontFamily: "var(--font-body), ui-sans-serif, sans-serif" }}>
            <Masthead />
            <main>
                <Hero />
                <SystemSection />
                <BilingualBand />
                <IdeaSection />
            </main>
            <Colophon />
        </div>
    );
}

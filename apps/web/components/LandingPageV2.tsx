"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

/* ─── Canvas ribbon animation ─────────────────────────────────────────────── */
function useRibbonCanvas(canvasRef: React.RefObject<HTMLCanvasElement | null>) {
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (reduced) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        let W = 0, H = 0;
        let lines: RibbonLine[] = [];
        let timer: ReturnType<typeof setInterval>;

        interface RibbonLine {
            segs: { x: number; y: number }[];
            isMag: boolean;
            spd: number;
            phase: number;
            alpha: number;
        }

        function resize() {
            W = canvas!.width = canvas!.offsetWidth;
            H = canvas!.height = canvas!.offsetHeight;
            buildLines();
        }

        function buildLines() {
            const n = W < 700 ? 22 : 42;
            const SX = W * 0.96;
            const SY = H * 0.04;
            lines = [];
            for (let i = 0; i < n; i++) {
                const spread = (i - n / 2) * 0.055;
                const segs: { x: number; y: number }[] = [];
                const L = 300;
                let cx = SX, cy = SY;
                let ang = Math.PI + spread * 0.0052 + (Math.random() - 0.5) * 0.04;
                for (let s = 0; s < L; s++) {
                    segs.push({ x: cx, y: cy });
                    ang += (Math.random() - 0.5) * 0.018;
                    cx += Math.cos(ang) * 8;
                    cy += Math.sin(ang) * 8;
                }
                lines.push({
                    segs,
                    isMag: Math.random() < 0.28,
                    spd: 0.4 + Math.random() * 0.6,
                    phase: Math.random() * 370,
                    alpha: 0.12 + Math.random() * 0.18,
                });
            }
        }

        let t = 0;
        function draw() {
            ctx!.clearRect(0, 0, W, H);
            t += 1;
            for (const L of lines) {
                const len = L.segs.length;
                const head = ((t * L.spd + L.phase) % (len + 70));
                const tailN = 28;
                for (let s = 1; s < len; s++) {
                    const a = L.segs[s - 1], b = L.segs[s];
                    const dist = Math.abs(s - head);
                    let alpha = L.alpha * 0.35;
                    if (dist < tailN) {
                        const bright = 1 - dist / tailN;
                        alpha = L.alpha * (0.35 + bright * 1.2);
                    }
                    ctx!.beginPath();
                    ctx!.moveTo(a.x, a.y);
                    ctx!.lineTo(b.x, b.y);
                    ctx!.lineWidth = dist < tailN ? 1.5 + (1 - dist / tailN) * 1.5 : 1;
                    if (L.isMag) {
                        ctx!.strokeStyle = dist < 4
                            ? `rgba(255,150,190,${alpha})`
                            : `rgba(255,72,149,${alpha})`;
                    } else {
                        ctx!.strokeStyle = dist < 4
                            ? `rgba(150,240,255,${alpha})`
                            : `rgba(0,218,243,${alpha})`;
                    }
                    ctx!.stroke();
                }
            }
        }

        resize();
        timer = setInterval(draw, 33);
        const ro = new ResizeObserver(resize);
        ro.observe(canvas);

        return () => {
            clearInterval(timer);
            ro.disconnect();
        };
    }, [canvasRef]);
}

/* ─── Logo marquee data ────────────────────────────────────────────────────── */
const EMPLOYERS_ROW1 = [
    "TALENTMATE", "BAYT", "GulfTalent", "Naukrigulf", "LinkedIn",
    "Emirates NBD", "ADNOC", "Etisalat", "Majid Al Futtaim", "DEWA",
];
const EMPLOYERS_ROW2 = [
    "Careem", "Noon", "Chalhoub Group", "Jumeirah Group", "DP World",
    "Abu Dhabi Islamic Bank", "Mashreq", "FAB", "RTA", "Emaar",
];

/* ─── Feature card data ────────────────────────────────────────────────────── */
const FEATURES = [
    {
        icon: (
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
            </svg>
        ),
        title: "AI Match Engine",
        desc: "Rico reads your CV and scores every UAE listing — surfacing only the roles where your profile lands in the top tier.",
        accent: "cyan",
    },
    {
        icon: (
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
        ),
        title: "CV Intelligence",
        desc: "Upload your CV once. Rico parses skills, seniority, and salary expectations and keeps your profile current automatically.",
        accent: "cyan",
    },
    {
        icon: (
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
            </svg>
        ),
        title: "Application Tracker",
        desc: "Every application in one timeline — status, follow-up reminders, and recruiter contact — so nothing falls through the cracks.",
        accent: "magenta",
    },
    {
        icon: (
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
            </svg>
        ),
        title: "Bilingual Chat",
        desc: "Ask Rico anything — in English or Arabic. Get job advice, salary benchmarks, and application tips tailored to the UAE market.",
        accent: "magenta",
    },
    {
        icon: (
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
            </svg>
        ),
        title: "Smart Alerts",
        desc: "Telegram and email notifications the moment a high-match job is posted — before the listing fills up.",
        accent: "cyan",
    },
    {
        icon: (
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
        ),
        title: "Approval Safeguards",
        desc: "Rico never applies on your behalf without your explicit sign-off. You stay in control of every submission.",
        accent: "magenta",
    },
];

/* ─── Why Rico data ────────────────────────────────────────────────────────── */
const WHY_RICO = [
    {
        num: "01",
        headline: "UAE-Specific Intelligence",
        body: "Rico is trained on UAE hiring patterns, local salary benchmarks, visa sponsorship norms, and the Arabic–English bilingual job market — not a generic global tool.",
    },
    {
        num: "02",
        headline: "End-to-End Automation",
        body: "From CV parsing to match scoring, application tracking to follow-up reminders — Rico handles every step of the search so you focus on the interviews.",
    },
    {
        num: "03",
        headline: "You Stay in Control",
        body: "Every apply action requires your approval. Rico surfaces opportunities and prepares your submissions; you decide what goes out and when.",
    },
];

/* ─── Success story carousel data ─────────────────────────────────────────── */
const STORIES = [
    {
        quote: "Rico found a Product Manager role at a fintech in DIFC I'd completely missed. The match score was 0.94 — and I got an interview in three days.",
        name: "Layla K.",
        title: "Product Manager, Dubai",
        score: "0.94",
    },
    {
        quote: "I was applying manually to 20+ jobs a week. Rico cut that to 5 high-quality matches and I landed two offers within a month.",
        name: "Ahmed R.",
        title: "Software Engineer, Abu Dhabi",
        score: "0.91",
    },
    {
        quote: "The Arabic chat feature was a game-changer. I could ask about salary norms in my industry and get real UAE data back.",
        name: "Sara M.",
        title: "Marketing Manager, Sharjah",
        score: "0.88",
    },
    {
        quote: "As a recent grad, I didn't know how to price myself. Rico's benchmarks told me exactly what to ask for — and I got it.",
        name: "Omar F.",
        title: "Data Analyst, Dubai",
        score: "0.89",
    },
];

/* ─── FAQ data ─────────────────────────────────────────────────────────────── */
const FAQS = [
    {
        q: "Is Rico free to use?",
        a: "Yes — the Free plan gives you 5 job matches per week, CV parsing, and basic application tracking at no cost. Pro and Premium plans unlock unlimited matches, priority alerts, and advanced analytics.",
    },
    {
        q: "Which job boards does Rico search?",
        a: "Rico aggregates listings from Bayt, LinkedIn, Naukrigulf, GulfTalent, and direct employer sites across the UAE — covering Dubai, Abu Dhabi, Sharjah, and the wider GCC.",
    },
    {
        q: "Will Rico apply on my behalf without asking?",
        a: "Never. RICO_REQUIRE_APPROVAL = true at all times. Rico prepares the application and presents it to you; you review it and give the go-ahead before anything is submitted.",
    },
    {
        q: "Does Rico support Arabic?",
        a: "Yes. The chat interface is fully bilingual — you can ask questions and receive answers in English or Arabic. CV parsing supports Arabic text and mixed-language documents.",
    },
    {
        q: "How is my data protected?",
        a: "CV data and chat history are stored securely in an isolated account. They are never sold, shared with employers, or used to train external models. You can delete your data at any time.",
    },
];

/* ─── Pricing data ─────────────────────────────────────────────────────────── */
const PLANS = [
    {
        name: "Free",
        price: "AED 0",
        period: "",
        badge: null,
        features: [
            "5 job matches / week",
            "CV parsing (1 upload)",
            "Basic application tracker",
            "English chat",
        ],
        cta: "Get started",
        href: "/signup",
        primary: false,
    },
    {
        name: "Pro",
        price: "AED 29",
        period: "/mo",
        badge: "Popular",
        features: [
            "Unlimited job matches",
            "CV parsing (unlimited)",
            "Full application tracker",
            "English + Arabic chat",
            "Telegram + email alerts",
            "Salary benchmarks",
        ],
        cta: "Start Pro",
        href: "/signup",
        primary: true,
    },
    {
        name: "Premium",
        price: "AED 49",
        period: "/mo",
        badge: null,
        features: [
            "Everything in Pro",
            "Priority match queue",
            "Application analytics",
            "Dedicated follow-up reminders",
            "Early access to new features",
        ],
        cta: "Start Premium",
        href: "/signup",
        primary: false,
    },
];

/* ─── Sub-components ──────────────────────────────────────────────────────── */

function MarqueeRow({ items, reverse }: { items: string[]; reverse?: boolean }) {
    const doubled = [...items, ...items];
    return (
        <div className="overflow-hidden py-2">
            <div
                className="flex gap-8 whitespace-nowrap"
                style={{
                    animation: `marquee${reverse ? "Rev" : ""} 28s linear infinite`,
                    willChange: "transform",
                }}
            >
                {doubled.map((name, i) => (
                    <span
                        key={i}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/[0.04] text-sm font-medium text-white/50 hover:text-white/80 hover:border-white/20 transition-colors cursor-default"
                    >
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400/60 inline-block" />
                        {name}
                    </span>
                ))}
            </div>
        </div>
    );
}

function FeatureCard({ feature }: { feature: typeof FEATURES[0] }) {
    const isCyan = feature.accent === "cyan";
    return (
        <div className="group relative rounded-2xl border border-white/10 bg-white/[0.03] p-6 hover:border-white/20 hover:bg-white/[0.06] transition-all duration-300 cursor-default overflow-hidden">
            {/* Animated glow on hover */}
            <div
                className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none rounded-2xl ${isCyan ? "shadow-[inset_0_0_40px_rgba(0,218,243,0.06)]" : "shadow-[inset_0_0_40px_rgba(255,72,149,0.06)]"}`}
            />
            {/* Streak line */}
            <div
                className={`absolute top-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${isCyan ? "bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent" : "bg-gradient-to-r from-transparent via-pink-400/50 to-transparent"}`}
            />
            {/* Dot grid */}
            <div className="absolute inset-0 opacity-0 group-hover:opacity-20 transition-opacity duration-500 pointer-events-none"
                style={{
                    backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.3) 1px, transparent 1px)",
                    backgroundSize: "24px 24px",
                }}
            />
            <div className={`mb-4 inline-flex p-2.5 rounded-xl ${isCyan ? "bg-cyan-500/10 text-cyan-400" : "bg-pink-500/10 text-pink-400"}`}>
                {feature.icon}
            </div>
            <h3 className="text-base font-semibold text-white mb-2">{feature.title}</h3>
            <p className="text-sm text-white/50 leading-relaxed">{feature.desc}</p>
        </div>
    );
}

function StoryCard({ story }: { story: typeof STORIES[0] }) {
    return (
        <div className="flex-shrink-0 w-80 rounded-2xl border border-white/10 bg-white/[0.04] p-6 flex flex-col gap-4">
            <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-cyan-400 bg-cyan-400/10 px-2 py-0.5 rounded-full">
                    Match {story.score}
                </span>
            </div>
            <p className="text-sm text-white/70 leading-relaxed flex-1">&ldquo;{story.quote}&rdquo;</p>
            <div>
                <p className="text-sm font-semibold text-white">{story.name}</p>
                <p className="text-xs text-white/40">{story.title}</p>
            </div>
        </div>
    );
}

function FaqItem({ faq }: { faq: typeof FAQS[0] }) {
    const [open, setOpen] = useState(false);
    return (
        <div className="border-b border-white/10 last:border-0">
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between py-5 text-left gap-4 group cursor-pointer"
                aria-expanded={open}
            >
                <span className="text-sm font-medium text-white/80 group-hover:text-white transition-colors">
                    {faq.q}
                </span>
                <span className={`flex-shrink-0 w-5 h-5 rounded-full border border-white/20 flex items-center justify-center transition-transform duration-200 ${open ? "rotate-45 border-cyan-400/50" : ""}`}>
                    <svg viewBox="0 0 12 12" fill="none" className="w-2.5 h-2.5 text-white/60">
                        <path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" />
                    </svg>
                </span>
            </button>
            {open && (
                <p className="pb-5 text-sm text-white/50 leading-relaxed pr-8">{faq.a}</p>
            )}
        </div>
    );
}

/* ─── Main component ──────────────────────────────────────────────────────── */

export default function LandingPageV2() {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    useRibbonCanvas(canvasRef);

    const carouselRef = useRef<HTMLDivElement>(null);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    function scrollCarousel(dir: number) {
        if (carouselRef.current) {
            carouselRef.current.scrollBy({ left: dir * 320, behavior: "smooth" });
        }
    }

    return (
        <div
            className="relative min-h-screen overflow-x-hidden"
            style={{ fontFamily: "var(--font-ibm-plex-sans), var(--font-body), sans-serif", background: "#000" }}
        >
            {/* Marquee keyframe styles */}
            <style>{`
                @keyframes marquee { from { transform: translateX(0) } to { transform: translateX(-50%) } }
                @keyframes marqueeRev { from { transform: translateX(-50%) } to { transform: translateX(0) } }
                @media (prefers-reduced-motion: reduce) {
                    [style*="marquee"] { animation: none !important; }
                }
            `}</style>

            {/* ── Canvas ribbons ── */}
            <canvas
                ref={canvasRef}
                aria-hidden="true"
                className="pointer-events-none fixed inset-0 w-full h-full"
                style={{ zIndex: 0 }}
            />

            {/* ── Nav ── */}
            <nav className="fixed top-4 left-4 right-4 z-50 flex items-center justify-between px-5 py-3 rounded-2xl border border-white/10 bg-black/70 backdrop-blur-xl">
                <Link href="/" className="flex items-center gap-2 group">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-cyan-400 to-pink-500 flex items-center justify-center">
                        <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4">
                            <path d="M8 2L14 6v4L8 14 2 10V6L8 2z" fill="white" fillOpacity={0.9} />
                        </svg>
                    </div>
                    <span className="font-semibold text-white text-sm tracking-tight">Rico AI</span>
                </Link>

                {/* Desktop links */}
                <div className="hidden md:flex items-center gap-6 text-sm text-white/60">
                    <a href="#features" className="hover:text-white transition-colors">Features</a>
                    <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
                    <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
                </div>

                <div className="flex items-center gap-3">
                    <Link
                        href="/login"
                        className="hidden sm:block text-sm text-white/60 hover:text-white transition-colors px-3 py-1.5"
                    >
                        Sign in
                    </Link>
                    <Link
                        href="/signup"
                        className="text-sm font-medium px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-cyan-400 text-black hover:brightness-110 transition-all"
                    >
                        Start with Rico
                    </Link>
                    {/* Mobile menu toggle */}
                    <button
                        className="md:hidden p-1.5 text-white/60 hover:text-white cursor-pointer"
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                        aria-label="Toggle menu"
                    >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5">
                            {mobileMenuOpen
                                ? <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                : <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                            }
                        </svg>
                    </button>
                </div>
            </nav>

            {/* Mobile menu */}
            {mobileMenuOpen && (
                <div className="fixed top-20 left-4 right-4 z-40 rounded-2xl border border-white/10 bg-black/90 backdrop-blur-xl p-5 flex flex-col gap-4 md:hidden">
                    <a href="#features" className="text-sm text-white/70 hover:text-white" onClick={() => setMobileMenuOpen(false)}>Features</a>
                    <a href="#pricing" className="text-sm text-white/70 hover:text-white" onClick={() => setMobileMenuOpen(false)}>Pricing</a>
                    <a href="#faq" className="text-sm text-white/70 hover:text-white" onClick={() => setMobileMenuOpen(false)}>FAQ</a>
                    <Link href="/login" className="text-sm text-white/70 hover:text-white" onClick={() => setMobileMenuOpen(false)}>Sign in</Link>
                </div>
            )}

            <main className="relative z-10">

                {/* ── Hero ── */}
                <section className="relative min-h-[100svh] flex flex-col items-center justify-center px-4 pt-28 pb-20 text-center">
                    {/* Eyebrow — minimal dot + label (mock style) */}
                    <div className="inline-flex items-center gap-2.5 mb-8">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                        <span className="text-[11px] font-medium uppercase tracking-[0.22em] text-cyan-400/90">
                            AI Career Operator · United Arab Emirates
                        </span>
                    </div>

                    <h1 className="max-w-4xl text-[2.6rem] leading-[1.05] sm:text-6xl sm:leading-[1.04] md:text-7xl lg:text-[5.25rem] lg:leading-[1.02] font-extralight text-white/90 tracking-tight mb-7">
                        Your AI career assistant for UAE jobs
                    </h1>

                    <p className="max-w-xl text-base sm:text-lg text-white/45 leading-relaxed mb-9 font-light">
                        Upload your CV, find matching UAE roles, and let Rico guide your next move — quietly, in the background, in English or <span className="text-white/60">العربية</span>.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center gap-3 mb-6">
                        <Link
                            href="/signup"
                            className="inline-flex items-center justify-center px-7 py-3.5 rounded-full bg-white text-black text-xs font-semibold uppercase tracking-[0.14em] hover:bg-white/90 transition-all shadow-[0_0_32px_rgba(255,255,255,0.12)]"
                        >
                            Start with Rico
                        </Link>
                        <Link
                            href="/onboarding"
                            className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-full border border-white/20 text-white/80 text-xs font-medium uppercase tracking-[0.14em] hover:bg-white/[0.06] hover:border-white/35 transition-all"
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
                            </svg>
                            Upload CV
                        </Link>
                    </div>

                    {/* Trust row */}
                    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 mb-16 text-[10px] font-medium uppercase tracking-[0.18em] text-white/35">
                        <span>English &amp; <span className="text-cyan-400/80">العربية</span></span>
                        <span className="text-white/15" aria-hidden="true">·</span>
                        <span>Telegram-first</span>
                        <span className="text-white/15" aria-hidden="true">·</span>
                        <span>No spam, ever</span>
                    </div>

                    {/* Illustrative sample — not a live listing */}
                    <div className="relative mx-auto max-w-sm w-full rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-sm p-5 text-left">
                        <div className="flex items-start justify-between mb-3">
                            <div>
                                <p className="flex items-center gap-1.5 text-xs text-pink-400/80 font-mono uppercase tracking-widest mb-1.5">
                                    <span className="w-1.5 h-1.5 rounded-full bg-pink-400/80" />
                                    Match Analysis
                                </p>
                                <p className="text-sm font-semibold text-white">Senior Manager — Audit Programs</p>
                                <p className="text-xs text-white/50">TALENTMATE · Abu Dhabi, UAE</p>
                            </div>
                            <div className="text-right">
                                <p className="text-2xl font-bold text-cyan-400 leading-none">0.91</p>
                                <p className="text-[10px] text-white/30 font-mono uppercase tracking-wide">Confidence</p>
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-1.5 mb-4">
                            {["Audit", "Risk & Controls", "UAE Market"].map(t => (
                                <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] border border-white/10 text-white/50">{t}</span>
                            ))}
                        </div>
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-white/30">AED 28,000 – 35,000 / mo</span>
                            <span className="text-[10px] font-mono uppercase tracking-widest text-white/25">Sample match</span>
                        </div>
                    </div>
                </section>

                {/* ── AMD-inspired: Why Rico ── */}
                <section className="relative px-4 py-20">
                    <div className="max-w-5xl mx-auto">
                        <div className="text-center mb-12">
                            <p className="text-xs font-mono text-cyan-400/70 uppercase tracking-widest mb-3">Why Rico</p>
                            <h2 className="text-2xl sm:text-3xl font-light text-white">
                                Built for the{" "}
                                <span className="font-semibold">UAE job market</span>
                            </h2>
                        </div>
                        <div className="grid md:grid-cols-3 gap-6">
                            {WHY_RICO.map((item) => (
                                <div key={item.num} className="p-6 rounded-2xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.05] transition-colors group">
                                    <p className="font-mono text-2xl font-bold text-white/10 group-hover:text-cyan-400/20 transition-colors mb-4">{item.num}</p>
                                    <h3 className="text-sm font-semibold text-white mb-2">{item.headline}</h3>
                                    <p className="text-sm text-white/40 leading-relaxed">{item.body}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* ── AMD-inspired: Employer logo marquee ── */}
                <section className="py-12 border-y border-white/[0.06] overflow-hidden">
                    <p className="text-center text-xs font-mono text-white/25 uppercase tracking-widest mb-6">
                        Jobs from leading UAE employers
                    </p>
                    <MarqueeRow items={EMPLOYERS_ROW1} />
                    <div className="mt-3">
                        <MarqueeRow items={EMPLOYERS_ROW2} reverse />
                    </div>
                </section>

                {/* ── Features grid ── */}
                <section id="features" className="px-4 py-20">
                    <div className="max-w-5xl mx-auto">
                        <div className="text-center mb-12">
                            <p className="text-xs font-mono text-cyan-400/70 uppercase tracking-widest mb-3">Features</p>
                            <h2 className="text-2xl sm:text-3xl font-light text-white">
                                Every tool your{" "}
                                <span className="font-semibold">job search needs</span>
                            </h2>
                        </div>
                        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {FEATURES.map((f) => (
                                <FeatureCard key={f.title} feature={f} />
                            ))}
                        </div>
                    </div>
                </section>

                {/* ── AMD-inspired: Success stories carousel ── */}
                <section className="py-20 border-y border-white/[0.06]">
                    <div className="max-w-5xl mx-auto px-4">
                        <div className="flex items-end justify-between mb-8">
                            <div>
                                <p className="text-xs font-mono text-pink-400/70 uppercase tracking-widest mb-2">Success Stories</p>
                                <h2 className="text-2xl sm:text-3xl font-light text-white">
                                    Real results,{" "}
                                    <span className="font-semibold">real candidates</span>
                                </h2>
                            </div>
                            <div className="hidden sm:flex items-center gap-2">
                                <button
                                    onClick={() => scrollCarousel(-1)}
                                    className="w-9 h-9 rounded-full border border-white/15 flex items-center justify-center text-white/50 hover:text-white hover:border-white/30 transition-colors cursor-pointer"
                                    aria-label="Scroll left"
                                >
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                                    </svg>
                                </button>
                                <button
                                    onClick={() => scrollCarousel(1)}
                                    className="w-9 h-9 rounded-full border border-white/15 flex items-center justify-center text-white/50 hover:text-white hover:border-white/30 transition-colors cursor-pointer"
                                    aria-label="Scroll right"
                                >
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <div
                            ref={carouselRef}
                            className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory scroll-smooth"
                            style={{ scrollbarWidth: "none" }}
                        >
                            {STORIES.map((s) => (
                                <div key={s.name} className="snap-start">
                                    <StoryCard story={s} />
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* ── AMD-inspired: Image-background CTA highlight ── */}
                <section className="px-4 py-20">
                    <div className="max-w-5xl mx-auto">
                        <div className="relative overflow-hidden rounded-3xl border border-cyan-500/20 bg-gradient-to-br from-cyan-950/60 via-black to-pink-950/40 p-10 sm:p-16 text-center">
                            {/* background glow blobs */}
                            <div className="absolute -top-20 -left-20 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
                            <div className="absolute -bottom-20 -right-20 w-72 h-72 bg-pink-500/10 rounded-full blur-3xl pointer-events-none" />
                            <div className="relative z-10">
                                <p className="text-xs font-mono text-cyan-400/70 uppercase tracking-widest mb-4">Get Started Today</p>
                                <h2 className="text-3xl sm:text-4xl font-light text-white mb-4 leading-tight">
                                    Your next UAE role{" "}
                                    <br className="hidden sm:block" />
                                    <span className="font-semibold bg-gradient-to-r from-cyan-400 to-cyan-300 bg-clip-text text-transparent">
                                        is already in Rico&apos;s queue
                                    </span>
                                </h2>
                                <p className="text-base text-white/40 max-w-md mx-auto mb-8 font-light">
                                    Upload your CV and get your first personalized match report in under 60 seconds.
                                </p>
                                <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                                    <Link
                                        href="/signup"
                                        className="px-7 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-cyan-400 text-black font-semibold text-sm hover:brightness-110 transition-all shadow-[0_0_40px_rgba(0,218,243,0.3)]"
                                    >
                                        Create free account
                                    </Link>
                                    <Link
                                        href="/chat"
                                        className="px-7 py-3 rounded-xl border border-white/20 text-white/70 font-medium text-sm hover:bg-white/[0.06] hover:border-white/30 transition-all"
                                    >
                                        Try chat first
                                    </Link>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* ── Pricing ── */}
                <section id="pricing" className="px-4 py-20">
                    <div className="max-w-5xl mx-auto">
                        <div className="text-center mb-12">
                            <p className="text-xs font-mono text-cyan-400/70 uppercase tracking-widest mb-3">Pricing</p>
                            <h2 className="text-2xl sm:text-3xl font-light text-white">
                                Simple,{" "}
                                <span className="font-semibold">transparent pricing</span>
                            </h2>
                        </div>
                        <div className="grid md:grid-cols-3 gap-5">
                            {PLANS.map((plan) => (
                                <div
                                    key={plan.name}
                                    className={`relative rounded-2xl border p-7 flex flex-col gap-6 ${plan.primary
                                        ? "border-cyan-500/40 bg-gradient-to-b from-cyan-950/50 to-black shadow-[0_0_48px_rgba(0,218,243,0.1)]"
                                        : "border-white/10 bg-white/[0.03]"
                                        }`}
                                >
                                    {plan.badge && (
                                        <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[11px] font-semibold bg-cyan-400 text-black">
                                            {plan.badge}
                                        </span>
                                    )}
                                    <div>
                                        <p className={`text-sm font-medium mb-1 ${plan.primary ? "text-cyan-400" : "text-white/60"}`}>{plan.name}</p>
                                        <div className="flex items-baseline gap-1">
                                            <span className="text-3xl font-bold text-white">{plan.price}</span>
                                            {plan.period && <span className="text-sm text-white/30">{plan.period}</span>}
                                        </div>
                                    </div>
                                    <ul className="flex flex-col gap-2.5 flex-1">
                                        {plan.features.map((f) => (
                                            <li key={f} className="flex items-start gap-2.5 text-sm text-white/55">
                                                <svg viewBox="0 0 16 16" fill="none" className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${plan.primary ? "text-cyan-400" : "text-white/30"}`}>
                                                    <path d="M3 8l3.5 3.5L13 4" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
                                                </svg>
                                                {f}
                                            </li>
                                        ))}
                                    </ul>
                                    <Link
                                        href={plan.href}
                                        className={`block text-center py-3 rounded-xl text-sm font-semibold transition-all ${plan.primary
                                            ? "bg-gradient-to-r from-cyan-500 to-cyan-400 text-black hover:brightness-110 shadow-[0_0_24px_rgba(0,218,243,0.2)]"
                                            : "border border-white/15 text-white/70 hover:bg-white/[0.06] hover:border-white/25"
                                            }`}
                                    >
                                        {plan.cta}
                                    </Link>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* ── FAQ ── */}
                <section id="faq" className="px-4 py-20">
                    <div className="max-w-2xl mx-auto">
                        <div className="text-center mb-12">
                            <p className="text-xs font-mono text-cyan-400/70 uppercase tracking-widest mb-3">FAQ</p>
                            <h2 className="text-2xl sm:text-3xl font-light text-white">
                                Common{" "}
                                <span className="font-semibold">questions</span>
                            </h2>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/[0.02] px-6">
                            {FAQS.map((faq) => (
                                <FaqItem key={faq.q} faq={faq} />
                            ))}
                        </div>
                    </div>
                </section>

                {/* ── Footer ── */}
                <footer className="border-t border-white/[0.06] px-4 py-10">
                    <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-cyan-400 to-pink-500 flex items-center justify-center">
                                <svg viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5">
                                    <path d="M8 2L14 6v4L8 14 2 10V6L8 2z" fill="white" fillOpacity={0.9} />
                                </svg>
                            </div>
                            <span className="text-sm font-semibold text-white/70">Rico AI</span>
                        </div>
                        <p className="text-xs text-white/25 text-center">
                            &copy; {new Date().getFullYear()} Rico Hunt. All rights reserved.
                        </p>
                        <div className="flex items-center gap-5 text-xs text-white/30">
                            <Link href="/chat" className="hover:text-white/60 transition-colors">Chat</Link>
                            <Link href="/login" className="hover:text-white/60 transition-colors">Sign in</Link>
                            <Link href="/signup" className="hover:text-white/60 transition-colors">Sign up</Link>
                        </div>
                    </div>
                </footer>

            </main>
        </div>
    );
}

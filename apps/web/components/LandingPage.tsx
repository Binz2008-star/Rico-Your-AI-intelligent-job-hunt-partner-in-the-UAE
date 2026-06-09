"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { MotionConfig, motion } from "framer-motion";
import Link from "next/link";

// Small inline icons (lucide-style) — MASTER.md forbids emoji-as-icon and
// requires a consistent SVG set. Stroke uses currentColor so callers theme via
// text-* utilities.
type IconProps = { className?: string };

function IconCheck({ className }: IconProps) {
    return (
        <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M20 6 9 17l-5-5" />
        </svg>
    );
}

function IconPin({ className }: IconProps) {
    return (
        <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
            <circle cx="12" cy="10" r="3" />
        </svg>
    );
}

function IconGlobe({ className }: IconProps) {
    return (
        <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <path d="M2 12h20" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10Z" />
        </svg>
    );
}

function IconShield({ className }: IconProps) {
    return (
        <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1Z" />
            <path d="m9 12 2 2 4-4" />
        </svg>
    );
}

function IconLock({ className }: IconProps) {
    return (
        <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
    );
}

export default function LandingPage() {
    const { language, setLanguage } = useLanguage();
    const isAr = language === "ar";

    const t = {
        // Header
        signIn: isAr ? "تسجيل الدخول" : "Sign in",
        signUpFree: isAr ? "ابدأ مجاناً" : "Start free",
        langToggle: isAr ? "EN" : "عربي",
        langToggleLabel: isAr ? "Switch to English" : "Switch to Arabic",

        // Screen 1 — Hero
        heroBadge: isAr ? "بحث ذكي عن وظيفة · الإمارات" : "AI Job Hunt · UAE",
        heroHeadline: isAr
            ? "بحث أذكى عن وظائف الإمارات يبدأ من سيرتك الذاتية."
            : "Smarter UAE job hunting starts with your CV.",
        heroSubtitle: isAr
            ? "ارفع سيرتك الذاتية. ريكو يجد الوظائف المناسبة في الإمارات، يشرح سبب الملاءمة، ويساعدك على متابعة كل طلب."
            : "Upload your CV. Rico finds UAE jobs that fit your experience, explains the match, and helps you track every application.",
        heroTrust: isAr
            ? "أنت في السيطرة. ريكو لا يتقدم بدون موافقتك."
            : "You stay in control. Rico never applies without your approval.",
        ctaUploadCV: isAr ? "ارفع سيرتك الذاتية" : "Upload your CV",
        ctaStartFree: isAr ? "ابدأ مجاناً" : "Start free",

        // Trust row
        trust1: isAr ? "متخصص في الإمارات" : "UAE-focused",
        trust2: isAr ? "عربي + إنجليزي" : "English + Arabic",
        trust3: isAr ? "موافقة يدوية" : "Manual approval",
        trust4: isAr ? "بياناتك لن تُباع" : "Data not sold",

        // Match preview card
        matchLabel: isAr ? "معاينة المطابقة" : "Rico Match Preview",
        matchRole: isAr ? "مسؤول امتثال بيئي" : "Environmental Compliance Officer",
        matchScoreLabel: isAr ? "ملاءمة" : "Fit score",
        matchWhyLabel: isAr ? "سبب الملاءمة:" : "Why it fits:",
        matchReasons: isAr
            ? ["خلفية في الامتثال بالإمارات", "خبرة في العمليات البيئية", "مهارات التفتيش وإعداد التقارير"]
            : ["UAE compliance background", "Environmental operations experience", "Inspection and reporting skills"],
        matchNextLabel: isAr ? "الخطوة التالية:" : "Next action:",
        matchNextAction: isAr ? "فتح رابط التقديم" : "Open apply link",

        // Operator micro-link
        operatorLink: isAr ? "إيكو تكنولوجي ذ.م.م" : "Eco Technology L.L.C",
        privacyLink: isAr ? "الخصوصية" : "Privacy",

        // Screen 2 — Problem / Solution / Proof
        s2Headline: isAr ? "توقف عن التخمين أي وظيفة تناسبك." : "Stop guessing which jobs fit you.",
        s2Pain: isAr
            ? "لوحات الوظائف مزدحمة. معظم الأدوار لا تتطابق مع سيرتك. الطلبات صعبة المتابعة."
            : "Job boards are noisy. Most roles do not match your CV. Applications are hard to track.",
        s2Solution: isAr
            ? "ريكو يقرأ سيرتك ويحوّلها إلى مركز قيادة لبحثك الوظيفي."
            : "Rico reads your CV and turns it into a job-search command center.",

        card1Title: isAr ? "اعثر على وظائف أفضل" : "Find better matches",
        card1Body: isAr
            ? "ريكو يرتّب الوظائف حسب الملاءمة الفعلية، لا مجرد الكلمات المفتاحية."
            : "Rico ranks jobs by fit, not just keywords.",
        card1Visual: isAr
            ? ["٩٤ ملاءمة", "٨٩ ملاءمة", "٨٦ ملاءمة"]
            : ["94 fit", "89 fit", "86 fit"],

        card2Title: isAr ? "اعرف سبب الملاءمة" : "Know why they fit",
        card2Body: isAr
            ? "شاهد السبب قبل أن تضيع وقتك في التقديم."
            : "See the reason before you waste time applying.",
        card2Visual: isAr
            ? ["تطابق الخبرة في الإمارات", "مهارات الامتثال متوفرة"]
            : ["UAE experience match", "Compliance skills present"],

        card3Title: isAr ? "تابع كل خطوة" : "Track every move",
        card3Body: isAr
            ? "الوظائف المحفوظة وطلباتك ومتابعاتك في مكان واحد."
            : "Saved jobs, applications, and follow-ups in one place.",
        card3Visual: isAr
            ? ["محفوظة", "مفتوحة", "متقدَّم إليها"]
            : ["Saved", "Opened", "Applied"],

        // Screen 3 — Pricing
        pricingHeadline: isAr
            ? "ابدأ مجاناً. ارتقِ حين يفيدك ريكو فعلاً."
            : "Start free. Upgrade only when Rico helps.",
        mostPopular: isAr ? "الأكثر طلباً" : "Most popular",
        perMonth: isAr ? "/شهر" : "/mo",

        freeName: isAr ? "مجانية" : "Free",
        freeFeatures: isAr
            ? ["٥٠ رسالة ذكاء اصطناعي شهرياً", "١٠ وظائف محفوظة", "ترتيب الوظائف حسب ملاءمة سيرتك", "عربي + إنجليزي"]
            : ["50 AI messages / month", "10 saved jobs", "CV-based match scoring", "English & Arabic"],
        freeBtn: isAr ? "ابدأ مجاناً" : "Start free",

        proName: isAr ? "الاحترافية" : "Pro",
        proFeatures: isAr
            ? ["٣٠٠ رسالة ذكاء اصطناعي شهرياً", "١٠٠ وظيفة محفوظة", "تحليل سبب ملاءمة كل وظيفة", "متابعة الطلبات وتذكيرات المتابعة"]
            : ["300 AI messages / month", "100 saved jobs", "“Why it fits” match insights", "Application tracking + follow-up reminders"],
        proBtn: isAr ? "اختر الاحترافية" : "Get Pro",

        premiumName: isAr ? "المميزة" : "Premium",
        premiumFeatures: isAr
            ? ["١٥٠٠ رسالة ذكاء اصطناعي شهرياً", "وظائف محفوظة بلا حدود", "صياغة مسودات الطلبات", "تنبيهات الوظائف عبر تيليجرام", "دعم ذو أولوية"]
            : ["1,500 AI messages / month", "Unlimited saved jobs", "Application draft generation", "Priority job alerts via Telegram", "Priority support"],
        premiumBtn: isAr ? "اختر المميزة" : "Get Premium",

        cancelAnytime: isAr ? "إلغاء في أي وقت" : "Cancel anytime",

        // Trust block
        builtInUaeTitle: isAr ? "صُمِّم ويُدار في الإمارات." : "Built and operated in the UAE.",
        trustBlock: isAr
            ? "تُشغَّل المنصة بواسطة شركة إيكو تكنولوجي لحماية البيئة ذ.م.م، شركة مسجلة في الإمارات العربية المتحدة. بياناتك تُستخدم لتقديم خدمة البحث الوظيفي ولن تُباع أبداً."
            : "Operated by Eco Technology Environment Protection Services L.L.C, a UAE-registered company. Your data is used to provide job-search assistance and is never sold.",

        // Objection-busting FAQ (the four questions every UAE job seeker asks)
        faqHeading: isAr ? "أسئلة قبل أن تبدأ" : "Before you start",
        faqSeeAll: isAr ? "كل الأسئلة ←" : "All FAQs →",
        faqItems: isAr
            ? [
                { q: "هل بياناتي آمنة؟", a: "تُخزَّن سيرتك وملفك بأمان ولا تُباع أبداً لأصحاب العمل أو المجندين. يمكنك حذف بياناتك في أي وقت." },
                { q: "هل يتقدم ريكو للوظائف نيابةً عني؟", a: "لا. لا يقدّم ريكو أي طلب دون موافقتك الصريحة. أنت تؤكد كل إجراء." },
                { q: "ما لوحات الوظائف التي يغطيها؟", a: "وظائف مباشرة في الإمارات والخليج عبر JSearch — تشمل لينكدإن وإنديد وغلاسدور وبيت." },
                { q: "هل يناسب مجالي؟", a: "يطابق ريكو الوظائف مع سيرتك الفعلية عبر القطاعات — الهندسة والمالية والصحة والعمليات وغيرها." },
            ]
            : [
                { q: "Is my data safe?", a: "Your CV and profile are stored securely and never sold to employers or recruiters. You can delete your data at any time." },
                { q: "Does Rico apply to jobs for me?", a: "No. Rico never submits an application without your explicit approval. You confirm every action." },
                { q: "Which job boards does it cover?", a: "Live UAE & GCC listings via JSearch — including LinkedIn, Indeed, Glassdoor, and Bayt." },
                { q: "Does it work for my field?", a: "Rico matches roles against your actual CV across sectors — engineering, finance, healthcare, operations, and more." },
            ],

        // Final CTA
        finalHeadline: isAr
            ? "ارفع سيرتك الذاتية. ريكو سيُريك ما يناسبك."
            : "Upload your CV. Rico will show you what fits.",
        finalBtn: isAr ? "ارفع سيرتك الذاتية" : "Upload your CV",

        // Footer
        footerAbout: isAr ? "عن ريكو" : "About",
        footerPrivacy: isAr ? "الخصوصية" : "Privacy",
        footerTerms: isAr ? "الشروط" : "Terms",
        footerContact: isAr ? "تواصل" : "Contact",
        footerRefunds: isAr ? "الاسترداد" : "Refunds",
        footerFaq: isAr ? "الأسئلة الشائعة" : "FAQ",
        footerRights: isAr ? "© 2026 ريكو هانت. جميع الحقوق محفوظة." : "© 2026 Rico Hunt. All rights reserved.",
    };

    return (
        <MotionConfig reducedMotion="user">
            <div
                dir={isAr ? "rtl" : "ltr"}
                className="relative min-h-screen overflow-x-hidden bg-[#0a0a1a] text-white"
            >
                {/* Background glows */}
                <div className="fixed inset-0 pointer-events-none z-0" aria-hidden="true">
                    <div className="absolute -left-32 -top-40 h-[500px] w-[500px] rounded-full bg-[rgba(180,0,120,0.07)] blur-[130px]" />
                    <div className="absolute -right-28 top-[40%] h-[400px] w-[400px] rounded-full bg-[rgba(0,200,220,0.05)] blur-[130px]" />
                </div>

                {/* ── HEADER ── */}
                <header className="relative z-10 flex items-center justify-between border-b border-white/[0.06] bg-black/60 px-5 py-4 backdrop-blur-xl md:px-10">
                    <Link
                        href="/"
                        className="flex items-center gap-2 text-lg font-black tracking-tight text-white"
                    >
                        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-[#0a0a1a] text-sm font-black shadow-[0_0_24px_rgba(245,166,35,0.35)]">
                            R
                        </span>
                        <span>Rico<span className="text-[#f5a623]"> Hunt</span></span>
                    </Link>
                    <nav className="flex items-center gap-2 sm:gap-3">
                        <button
                            type="button"
                            onClick={() => setLanguage(isAr ? "en" : "ar")}
                            aria-label={t.langToggleLabel}
                            className="text-[12px] font-semibold px-2.5 py-1 rounded-lg border border-white/10 text-white/60 hover:text-white hover:border-[#f5a623]/50 transition-colors"
                        >
                            {t.langToggle}
                        </button>
                        <Link
                            href="/login"
                            className="hidden text-sm text-white/60 transition-colors hover:text-white sm:block"
                        >
                            {t.signIn}
                        </Link>
                        <Link
                            href="/signup"
                            className="rounded-full border border-[#f5a623]/40 bg-[#f5a623]/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#f5a623]/25"
                        >
                            {t.signUpFree}
                        </Link>
                    </nav>
                </header>

                <main className="relative z-10">

                    {/* ══════════════════════════════════════════
                        SCREEN 1 — HERO / 5-SECOND CONVERSION
                    ══════════════════════════════════════════ */}
                    <section className="mx-auto max-w-5xl px-5 pt-12 pb-10 md:px-10">

                        {/* Badge */}
                        <motion.p
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.45 }}
                            className="mb-5 inline-flex rounded-full border border-[#f5a623]/25 bg-[#f5a623]/10 px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.26em] text-[#f5a623]"
                        >
                            {t.heroBadge}
                        </motion.p>

                        {/* Headline */}
                        <motion.h1
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.55, delay: 0.05 }}
                            className="text-[clamp(1.9rem,5.5vw,3.6rem)] font-semibold leading-[1.06] tracking-tight text-white"
                        >
                            {t.heroHeadline}
                        </motion.h1>

                        {/* Subtitle */}
                        <motion.p
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.5, delay: 0.1 }}
                            className="mt-4 max-w-2xl text-base leading-7 text-white/55 md:text-lg"
                        >
                            {t.heroSubtitle}
                        </motion.p>

                        {/* Trust sentence */}
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.45, delay: 0.16 }}
                            className="mt-2 text-sm text-white/35"
                        >
                            {t.heroTrust}
                        </motion.p>

                        {/* CTA buttons */}
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.45, delay: 0.2 }}
                            className="mt-7 flex flex-col gap-3 sm:flex-row"
                        >
                            <Link
                                href="/upload"
                                className="inline-flex items-center justify-center rounded-full bg-[#f5a623] px-7 py-3.5 text-base font-semibold text-[#0a0a1a] shadow-[0_0_32px_rgba(245,166,35,0.28)] transition-opacity hover:opacity-90"
                            >
                                {t.ctaUploadCV}
                            </Link>
                            <Link
                                href="/signup"
                                className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-7 py-3.5 text-base font-semibold text-white transition-colors hover:bg-white/[0.08]"
                            >
                                {t.ctaStartFree}
                            </Link>
                        </motion.div>

                        {/* Operator micro-link */}
                        <p className="mt-3 text-xs text-white/20">
                            {isAr ? (
                                <>
                                    <Link href="/about" className="text-[#f5a623]/60 hover:opacity-80">{t.operatorLink}</Link>
                                    {" · "}الإمارات{" · "}
                                    <Link href="/privacy" className="text-[#f5a623]/60 hover:opacity-80">{t.privacyLink}</Link>
                                </>
                            ) : (
                                <>
                                    <Link href="/about" className="text-[#f5a623]/60 hover:opacity-80">{t.operatorLink}</Link>
                                    {" · UAE · "}
                                    <Link href="/privacy" className="text-[#f5a623]/60 hover:opacity-80">{t.privacyLink}</Link>
                                </>
                            )}
                        </p>

                        {/* Compact trust row */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.4, delay: 0.28 }}
                            className="mt-6 flex flex-wrap gap-2"
                        >
                            {[
                                { label: t.trust1, icon: <IconPin className="h-3.5 w-3.5 text-[#f5a623]/80" /> },
                                { label: t.trust2, icon: <IconGlobe className="h-3.5 w-3.5 text-[#f5a623]/80" /> },
                                { label: t.trust3, icon: <IconShield className="h-3.5 w-3.5 text-[#f5a623]/80" /> },
                                { label: t.trust4, icon: <IconLock className="h-3.5 w-3.5 text-[#f5a623]/80" /> },
                            ].map(({ label, icon }) => (
                                <span
                                    key={label}
                                    className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-xs font-medium text-white/55"
                                >
                                    {icon}
                                    {label}
                                </span>
                            ))}
                        </motion.div>

                        {/* Match preview card */}
                        <motion.div
                            initial={{ opacity: 0, y: 18 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, delay: 0.32 }}
                            className="mt-7 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03]"
                        >
                            <div className="border-b border-white/[0.06] px-5 py-3">
                                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/35">
                                    {t.matchLabel}
                                </p>
                            </div>
                            <div className="px-5 py-4">
                                <div className="flex items-start justify-between gap-4">
                                    <p className="text-base font-semibold text-white">{t.matchRole}</p>
                                    <div className="shrink-0 text-right">
                                        <span className="font-mono text-[2rem] font-bold leading-none text-[#f5a623]">86</span>
                                        <p className="mt-0.5 font-mono text-[9px] uppercase tracking-widest text-white/25">
                                            {t.matchScoreLabel}
                                        </p>
                                    </div>
                                </div>
                                <p className="mt-3 text-[11px] font-semibold uppercase tracking-wider text-white/25">
                                    {t.matchWhyLabel}
                                </p>
                                <ul className="mt-1.5 space-y-1">
                                    {t.matchReasons.map((r) => (
                                        <li key={r} className="flex items-center gap-2 text-sm text-white/55">
                                            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#f5a623]" />
                                            {r}
                                        </li>
                                    ))}
                                </ul>
                                <div className="mt-4 flex items-center gap-2">
                                    <span className="text-xs text-white/25">{t.matchNextLabel}</span>
                                    <span className="rounded-full bg-[#f5a623]/15 px-3 py-0.5 text-xs font-semibold text-[#f5a623]">
                                        {t.matchNextAction}
                                    </span>
                                </div>
                            </div>
                        </motion.div>
                    </section>

                    {/* ══════════════════════════════════════════
                        SCREEN 2 — PROBLEM / SOLUTION / PROOF
                    ══════════════════════════════════════════ */}
                    <section className="mx-auto max-w-5xl px-5 py-10 md:px-10">
                        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.025] p-6 md:p-8">

                            <h2 className="text-2xl font-semibold text-white md:text-3xl">
                                {t.s2Headline}
                            </h2>
                            <p className="mt-3 text-sm leading-6 text-white/45">
                                {t.s2Pain}
                            </p>
                            <p className="mt-4 text-base font-medium text-white/75">
                                {t.s2Solution}
                            </p>

                            <div className="mt-6 grid gap-4 sm:grid-cols-3">

                                {/* Card 1 — Find better matches */}
                                <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                                    <div className="mb-3 flex gap-1.5">
                                        {t.card1Visual.map((v) => (
                                            <span
                                                key={v}
                                                className="rounded-full bg-[#f5a623]/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-[#f5a623]"
                                            >
                                                {v}
                                            </span>
                                        ))}
                                    </div>
                                    <h3 className="text-sm font-semibold text-white">{t.card1Title}</h3>
                                    <p className="mt-1 text-xs leading-5 text-white/45">{t.card1Body}</p>
                                </div>

                                {/* Card 2 — Know why */}
                                <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                                    <ul className="mb-3 space-y-1">
                                        {t.card2Visual.map((b) => (
                                            <li key={b} className="flex items-center gap-1.5 text-[11px] text-white/35">
                                                <span className="h-1 w-1 shrink-0 rounded-full bg-[#f5a623]/70" />
                                                {b}
                                            </li>
                                        ))}
                                    </ul>
                                    <h3 className="text-sm font-semibold text-white">{t.card2Title}</h3>
                                    <p className="mt-1 text-xs leading-5 text-white/45">{t.card2Body}</p>
                                </div>

                                {/* Card 3 — Track */}
                                <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                                    <div className="mb-3 flex flex-wrap gap-1.5">
                                        {t.card3Visual.map((s) => (
                                            <span
                                                key={s}
                                                className="rounded-full border border-white/[0.08] px-2 py-0.5 text-[11px] text-white/35"
                                            >
                                                {s}
                                            </span>
                                        ))}
                                    </div>
                                    <h3 className="text-sm font-semibold text-white">{t.card3Title}</h3>
                                    <p className="mt-1 text-xs leading-5 text-white/45">{t.card3Body}</p>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* ══════════════════════════════════════════
                        SCREEN 3 — PRICING + TRUST + FINAL CTA
                    ══════════════════════════════════════════ */}
                    <section className="mx-auto max-w-5xl px-5 pb-20 pt-4 md:px-10">

                        <h2 className="mb-6 text-2xl font-semibold text-white md:text-3xl">
                            {t.pricingHeadline}
                        </h2>

                        {/* Pricing grid */}
                        <div className="grid gap-3 sm:grid-cols-3">

                            {/* Free */}
                            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
                                <p className="font-mono text-[10px] uppercase tracking-widest text-white/35">
                                    {t.freeName}
                                </p>
                                <p className="mt-2 text-3xl font-bold text-white">
                                    {isAr ? "مجاناً" : "Free"}
                                </p>
                                <ul className="mt-4 space-y-2 text-sm text-white/55">
                                    {t.freeFeatures.map((f) => (
                                        <li key={f} className="flex items-start gap-2">
                                            <IconCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#f5a623]" />
                                            <span>{f}</span>
                                        </li>
                                    ))}
                                </ul>
                                <Link
                                    href="/signup"
                                    className="mt-5 inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/[0.08]"
                                >
                                    {t.freeBtn}
                                </Link>
                            </div>

                            {/* Pro */}
                            <div className="rounded-xl border border-[#f5a623]/30 bg-[#f5a623]/[0.04] p-5">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="font-mono text-[10px] uppercase tracking-widest text-[#f5a623]">
                                        {t.proName}
                                    </p>
                                    <span className="rounded-full bg-[#f5a623]/15 px-2 py-0.5 text-[10px] font-semibold text-[#f5a623]">
                                        {t.mostPopular}
                                    </span>
                                </div>
                                <p className="mt-2 text-3xl font-bold text-white">
                                    AED 29
                                    <span className="text-base font-normal text-white/35">{t.perMonth}</span>
                                </p>
                                <ul className="mt-4 space-y-2 text-sm text-white/55">
                                    {t.proFeatures.map((f) => (
                                        <li key={f} className="flex items-start gap-2">
                                            <IconCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#f5a623]" />
                                            <span>{f}</span>
                                        </li>
                                    ))}
                                </ul>
                                <Link
                                    href="/subscription"
                                    className="mt-5 inline-flex w-full items-center justify-center rounded-full bg-[#f5a623] py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
                                >
                                    {t.proBtn}
                                </Link>
                                <p className="mt-2 text-center text-[11px] text-white/30">{t.cancelAnytime}</p>
                            </div>

                            {/* Premium */}
                            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
                                <p className="font-mono text-[10px] uppercase tracking-widest text-white/35">
                                    {t.premiumName}
                                </p>
                                <p className="mt-2 text-3xl font-bold text-white">
                                    AED 49
                                    <span className="text-base font-normal text-white/35">{t.perMonth}</span>
                                </p>
                                <ul className="mt-4 space-y-2 text-sm text-white/55">
                                    {t.premiumFeatures.map((f) => (
                                        <li key={f} className="flex items-start gap-2">
                                            <IconCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#f5a623]" />
                                            <span>{f}</span>
                                        </li>
                                    ))}
                                </ul>
                                <Link
                                    href="/subscription"
                                    className="mt-5 inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/[0.08]"
                                >
                                    {t.premiumBtn}
                                </Link>
                                <p className="mt-2 text-center text-[11px] text-white/30">{t.cancelAnytime}</p>
                            </div>
                        </div>

                        {/* Trust block */}
                        <div className="mt-5 flex items-start gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-5 py-4">
                            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                                <IconPin className="h-4 w-4" />
                            </span>
                            <div>
                                <p className="text-sm font-semibold text-white">{t.builtInUaeTitle}</p>
                                <p className="mt-1 text-xs leading-6 text-white/30">{t.trustBlock}</p>
                            </div>
                        </div>

                        {/* Objection-busting FAQ */}
                        <div className="mt-12">
                            <div className="mb-5 flex items-end justify-between gap-4">
                                <h2 className="text-2xl font-semibold text-white md:text-3xl">{t.faqHeading}</h2>
                                <Link
                                    href="/faq"
                                    className="shrink-0 text-sm font-medium text-[#f5a623] transition-opacity hover:opacity-80"
                                >
                                    {t.faqSeeAll}
                                </Link>
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                {t.faqItems.map((item) => (
                                    <div
                                        key={item.q}
                                        className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5"
                                    >
                                        <h3 className="text-sm font-semibold text-white">{item.q}</h3>
                                        <p className="mt-2 text-sm leading-6 text-white/50">{item.a}</p>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Final CTA */}
                        <div className="mt-12 text-center">
                            <h2 className="text-xl font-semibold text-white md:text-2xl">
                                {t.finalHeadline}
                            </h2>
                            <Link
                                href="/upload"
                                className="mt-5 inline-flex items-center justify-center rounded-full bg-[#f5a623] px-8 py-4 text-base font-semibold text-[#0a0a1a] shadow-[0_0_40px_rgba(245,166,35,0.22)] transition-opacity hover:opacity-90"
                            >
                                {t.finalBtn}
                            </Link>
                        </div>
                    </section>
                </main>

                {/* ── FOOTER ── */}
                <footer className="relative z-10 border-t border-white/[0.06] bg-black/40 px-5 py-8 text-center">
                    <p className="mb-1 text-sm font-semibold text-white">Rico Hunt</p>
                    <p className="mb-3 text-xs text-white/20">
                        Powered by Eco Technology Environment Protection Services L.L.C · UAE
                    </p>
                    <div className="mb-3 flex flex-wrap items-center justify-center gap-4">
                        <Link href="/about" className="text-xs text-white/25 transition-colors hover:text-white">{t.footerAbout}</Link>
                        <Link href="/contact" className="text-xs text-white/25 transition-colors hover:text-white">{t.footerContact}</Link>
                        <Link href="/terms" className="text-xs text-white/25 transition-colors hover:text-white">{t.footerTerms}</Link>
                        <Link href="/privacy" className="text-xs text-white/25 transition-colors hover:text-white">{t.footerPrivacy}</Link>
                        <Link href="/refund-policy" className="text-xs text-white/25 transition-colors hover:text-white">{t.footerRefunds}</Link>
                        <Link href="/faq" className="text-xs text-white/25 transition-colors hover:text-white">{t.footerFaq}</Link>
                        <a
                            href="https://wa.me/971585989080"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-white/25 transition-colors hover:text-white"
                        >
                            WhatsApp
                        </a>
                    </div>
                    <p className="mb-1 text-xs text-white/15">
                        <a href="mailto:info@ricohunt.com" className="text-[#f5a623]/50 hover:opacity-80">
                            info@ricohunt.com
                        </a>
                        {" · "}
                        <a href="https://wa.me/971585989080" className="text-[#f5a623]/50 hover:opacity-80">
                            +971 58 598 9080
                        </a>
                    </p>
                    <p className="text-xs text-white/15">{t.footerRights}</p>
                </footer>
            </div>
        </MotionConfig>
    );
}

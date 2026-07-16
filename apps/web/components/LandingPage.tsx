"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { MotionConfig, motion } from "framer-motion";
import Link from "next/link";

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
        freeF1: isAr ? "٥٠ رسالة ذكاء اصطناعي" : "50 AI messages",
        freeF2: isAr ? "١٠ وظائف محفوظة" : "10 saved jobs",
        freeBtn: isAr ? "ابدأ مجاناً" : "Start free",

        proName: isAr ? "ريكو الشهرية" : "Rico Monthly",
        proF1: isAr ? "٣٠٠ رسالة ذكاء اصطناعي" : "300 AI messages",
        proF2: isAr ? "١٠٠ وظيفة محفوظة" : "100 saved jobs",
        proBtn: isAr ? "اشترك الآن" : "Get Rico Monthly",

        // Trust block
        trustBlock: isAr
            ? "تُشغَّل المنصة بواسطة شركة إيكو تكنولوجي لحماية البيئة ذ.م.م، شركة مسجلة في الإمارات العربية المتحدة. بياناتك تُستخدم لتقديم خدمة البحث الوظيفي ولن تُباع أبداً."
            : "Operated by Eco Technology Environment Protection Services L.L.C, a UAE-registered company. Your data is used to provide job-search assistance and is never sold.",

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
                            {[t.trust1, t.trust2, t.trust3, t.trust4].map((item) => (
                                <span
                                    key={item}
                                    className="inline-flex items-center rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-xs font-medium text-white/45"
                                >
                                    {item}
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
                        <div className="grid gap-3 sm:grid-cols-2">

                            {/* Free */}
                            <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5">
                                <p className="font-mono text-[10px] uppercase tracking-widest text-white/35">
                                    {t.freeName}
                                </p>
                                <p className="mt-2 text-3xl font-bold text-white">
                                    {isAr ? "مجاناً" : "Free"}
                                </p>
                                <ul className="mt-4 space-y-1.5 text-sm text-white/45">
                                    <li>{t.freeF1}</li>
                                    <li>{t.freeF2}</li>
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
                                    USD 21.50
                                    <span className="text-base font-normal text-white/35">{t.perMonth}</span>
                                </p>
                                <ul className="mt-4 space-y-1.5 text-sm text-white/45">
                                    <li>{t.proF1}</li>
                                    <li>{t.proF2}</li>
                                </ul>
                                <Link
                                    href="/subscription"
                                    className="mt-5 inline-flex w-full items-center justify-center rounded-full bg-[#f5a623] py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
                                >
                                    {t.proBtn}
                                </Link>
                            </div>
                        </div>

                        {/* Trust block */}
                        <div className="mt-5 rounded-xl border border-white/[0.05] bg-white/[0.02] px-5 py-4">
                            <p className="text-xs leading-6 text-white/30">{t.trustBlock}</p>
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

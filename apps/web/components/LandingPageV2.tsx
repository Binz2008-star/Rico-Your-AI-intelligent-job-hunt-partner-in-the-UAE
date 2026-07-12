"use client";

/**
 * LandingPageV2 — production public landing, rebuilt to the approved
 * /design-preview prospectus (DEC-20260710-002, full public-landing parity).
 *
 * Bilingual EN + AR. English copy is verbatim from the authoritative reference
 * and preserved byte-for-byte from #936/#937/#938. Arabic copy is verbatim from
 * rico-lovable-source.zip → src/lib/landing-content.ts → AR. Language uses the
 * app-global LanguageProvider (useLanguage); selecting AR persists global Arabic
 * state and flips <html dir="rtl">. No new font dependency — Arabic uses the
 * system Arabic fallback for v1. Arabic typography is handled safely:
 * letter-spacing removed on mono/eyebrow labels, synthesised italic suppressed.
 *
 * app/page.tsx is untouched — it still renders this default export and keeps
 * its auth redirect (ready && user -> /command).
 */

import { useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";
import { atelierFraunces as fraunces } from "@/components/atelier-kit/fonts";
import { ATELIER as C, ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono, Plate } from "@/components/atelier-kit/primitives";

/* Local aliases — kept so the rest of this file (and its inline styles)
   reads identically to before the PR 0 extraction; values are unchanged. */
const SERIF = ATELIER_FONT.serif;
const MONO = ATELIER_FONT.mono;
const BODY = ATELIER_FONT.body;

/* -------------------------------------------------------------------------- */
/*  Bilingual content. EN is byte-for-byte the shipped #936/#937/#938 copy;    */
/*  AR is verbatim from rico-lovable-source.zip → src/lib/landing-content.ts.   */
/* -------------------------------------------------------------------------- */
type Lang = "en" | "ar";

const COPY: Record<Lang, {
    volumeIssue: string;
    nav: { label: string; href: string }[];
    openRico: string;
    place: string;
    bilingualBadge: string;
    hero: { eyebrow: string; titleA: string; titleB: string; body: string; primary: string; secondary: string };
    interview: { eyebrow: string; transcribed: string; you: string; youQuote: string; rico: string; ricoAside: string; ricoQuote: string; askNext: string; suggestions: string[] };
    plate: { label: string; illustration: string; companyLoc: string; title: string[]; salary: string; whyFits: string; reasons: string[]; worthKnowing: string; concern: string };
    band: { a: string; b: string }[];
    idea: { eyebrow: string; titleA: string; titleB: string; items: { n: string; title: string; body: string }[] };
    footer: { eyebrow: string; titleA: string; titleB: string; body: string; meta: { k: string; v: string }[]; elsewhereLabel: string; elsewhere: { label: string; href: string }[]; copyright: string; volumeIssueTail: string };
}> = {
    en: {
        volumeIssue: "— Volume I · Issue 03",
        nav: [
            { label: "The idea", href: "#idea" },
            { label: "The system", href: "#system" },
            { label: "Rates", href: "/subscription" },
            { label: "Colophon", href: "#colophon" },
            { label: "Support", href: "/contact" },
        ],
        openRico: "Open Rico",
        place: "Dubai · Abu Dhabi · Sharjah · 2026",
        bilingualBadge: "English · العربية",
        hero: {
            eyebrow: "Prospectus — a quiet AI for a loud job market",
            titleA: "A career,",
            titleB: "in conversation.",
            body: "Rico is a small, patient intelligence for people looking for real work in the UAE. It reads your CV, watches the market, and only writes back when there is a job worth writing back about.",
            primary: "Begin with Rico",
            secondary: "Read the notebook",
        },
        interview: {
            eyebrow: "Interview",
            transcribed: "Transcribed, in full",
            you: "You",
            youQuote: "I want a senior product role in the UAE. Above thirty thousand. I don't want to read another job board.",
            rico: "Rico",
            ricoAside: "Reads CV · Scans 6 feeds · Scores fit",
            ricoQuote: "Then don't. I've read your CV. I'll watch the market for you and only speak when there's something worth your attention.",
            askNext: "Ask the next question",
            suggestions: ["Product roles above AED 30k", "Fintech openings in Abu Dhabi", "What's missing from my CV"],
        },
        plate: {
            label: "Plate 01 — Sample match",
            illustration: "Illustration",
            companyLoc: "Noon · Dubai",
            title: ["Senior Product", "Manager"],
            salary: "AED 32 – 42k",
            whyFits: "Why this fits",
            reasons: [
                "Five years of product depth, exactly the seniority asked for.",
                "UAE e-commerce background reads as a strong domain signal.",
                "Arabic fluency is a listed requirement — you match.",
            ],
            worthKnowing: "Worth knowing",
            concern: "Occasional on-site weeks in Riyadh.",
        },
        band: [
            { a: "Bilingual by design — ", b: "English and العربية." },
            { a: "Approval-first — ", b: "Rico never applies without you." },
            { a: "Delivered to Telegram — ", b: "your inbox stays quiet." },
        ],
        idea: {
            eyebrow: "§ The idea",
            titleA: "Three quiet convictions,",
            titleB: "held stubbornly.",
            items: [
                { n: "01", title: "The conversation is the product", body: "Rico is not a dashboard with a chatbot bolted on. It is a single quiet voice that reads you, reads the market, and only interrupts with reason." },
                { n: "02", title: "Reasoning, not percentages", body: "Every score opens up. Why this role fits. What is missing. What to do about it. No black-box confidence bars." },
                { n: "03", title: "Approval before action", body: "Rico can draft, tailor, and prepare. It never presses submit. The safety gate is not a setting — it is the shape of the thing." },
            ],
        },
        footer: {
            eyebrow: "Colophon",
            titleA: "Filed quietly from",
            titleB: "the desert.",
            body: "Rico Hunt is an editorial-grade AI job partner for the UAE.",
            meta: [
                { k: "Set in", v: "Fraunces · Inter · IBM Plex Mono" },
                { k: "Palette", v: "Paper, ink, and one hot signal" },
                { k: "Languages", v: "English · العربية" },
                { k: "Filed from", v: "The UAE, 2026" },
            ],
            elsewhereLabel: "Elsewhere",
            elsewhere: [
                { label: "Support", href: "/contact" },
                { label: "Terms", href: "/terms" },
                { label: "Privacy", href: "/privacy" },
                { label: "Pricing", href: "/subscription" },
            ],
            copyright: "© 2026 Rico Hunt",
            volumeIssueTail: "Volume I · Issue 03",
        },
    },
    ar: {
        volumeIssue: "— المجلّد الأول · العدد ٠٣",
        nav: [
            { label: "الفكرة", href: "#idea" },
            { label: "المنظومة", href: "#system" },
            { label: "الاشتراكات", href: "/subscription" },
            { label: "الهويّة", href: "#colophon" },
            { label: "الدعم", href: "/contact" },
        ],
        openRico: "افتح ريكو",
        place: "دبي · أبوظبي · الشارقة · ٢٠٢٦",
        bilingualBadge: "العربية · English",
        hero: {
            eyebrow: "نشرةٌ تعريفية — ذكاءٌ هادئ لسوق عملٍ صاخب",
            titleA: "مسيرةٌ مهنيّة،",
            titleB: "في حوارٍ صريح.",
            body: "ريكو مساعدٌ ذكيٌّ متأنٍّ لكل من يبحث عن عملٍ حقيقيٍّ في الإمارات. يقرأ سيرتك الذاتيّة، ويتابع السوق نيابةً عنك، ولا يكتب إليك إلّا حين تلوح فرصةٌ تستحقّ اهتمامك.",
            primary: "ابدأ مع ريكو",
            secondary: "تصفّح الدفتر",
        },
        interview: {
            eyebrow: "المقابلة",
            transcribed: "منقولةٌ بحذافيرها",
            you: "أنت",
            youQuote: "أبحث عن دورٍ قياديّ في إدارة المنتَج بالإمارات، براتبٍ يتجاوز الثلاثين ألفًا. لم أعُد أطيق تصفّح مواقع التوظيف.",
            rico: "ريكو",
            ricoAside: "قراءة السيرة · متابعة ٦ مصادر · احتساب الملاءمة",
            ricoQuote: "لا داعي. قرأتُ سيرتك، وسأتابع السوق نيابةً عنك، ولن أطرق بابك إلّا حين يكون هناك ما يستحقّ.",
            askNext: "اطرح السؤال التالي",
            suggestions: ["أدوار المنتَج فوق ٣٠ ألف درهم", "شواغر التقنية الماليّة في أبوظبي", "ما الذي ينقص سيرتي الذاتيّة؟"],
        },
        plate: {
            label: "لوحة ٠١ — عيّنة مطابقة",
            illustration: "توضيحيّة",
            companyLoc: "نون · دبي",
            title: ["مدير منتَج أوّل"],
            salary: "٣٢ – ٤٢ ألف درهم",
            whyFits: "لماذا يناسبك",
            reasons: [
                "خمس سنواتٍ من عمق العمل في المنتَج — وهي بالضبط درجة الأقدميّة المطلوبة.",
                "خلفيّتك في التجارة الإلكترونيّة بالإمارات إشارةٌ قويّة في هذا المجال.",
                "إجادة العربيّة شرطٌ مذكور في الإعلان — وأنت تُتقنها.",
            ],
            worthKnowing: "جديرٌ بالانتباه",
            concern: "أسابيع دوامٍ حضوريّ متقطّعة في الرياض.",
        },
        band: [
            { a: "ثنائيّ اللغة بالتصميم — ", b: "العربية والإنجليزية." },
            { a: "موافقتك أوّلًا — ", b: "ريكو لا يتقدّم بطلبٍ من دونك." },
            { a: "يصلك عبر تيليجرام — ", b: "ليبقى بريدك هادئًا." },
        ],
        idea: {
            eyebrow: "§ الفكرة",
            titleA: "ثلاث قناعاتٍ هادئة،",
            titleB: "نتمسّك بها بعناد.",
            items: [
                { n: "٠١", title: "الحوار هو المنتَج", body: "ريكو ليس لوحة تحكّمٍ أُلصق بها روبوت محادثة. إنما صوتٌ واحدٌ هادئ يقرأك، ويقرأ السوق، ولا يقاطعك إلّا بسببٍ وجيه." },
                { n: "٠٢", title: "أسبابٌ لا نِسَب", body: "خلف كلّ درجةٍ تفسيرٌ صريح: لماذا يناسبك هذا الدور، وما الذي ينقصك، وكيف تعالجه. لا صناديق سوداء ولا أشرطة ثقةٍ بلا معنى." },
                { n: "٠٣", title: "الموافقة قبل الفعل", body: "يستطيع ريكو أن يصوغ، ويُكيّف، ويجهّز. لكنّه لا يضغط «أرسل» أبدًا. حاجز الأمان ليس إعدادًا — إنّه شكل الأداة ذاتها." },
            ],
        },
        footer: {
            eyebrow: "الهويّة",
            titleA: "صادرٌ بهدوء",
            titleB: "من الصحراء.",
            body: "ريكو هَنت مساعدٌ ذكيٌّ بجودةٍ تحريريّة للباحثين عن عملٍ في الإمارات.",
            meta: [
                { k: "الطباعة", v: "Fraunces · Inter · IBM Plex Mono" },
                { k: "اللوحة", v: "ورقٌ، حبرٌ، وإشارةٌ ساخنة واحدة" },
                { k: "اللّغتان", v: "العربية · English" },
                { k: "من", v: "الإمارات، ٢٠٢٦" },
            ],
            elsewhereLabel: "روابط",
            elsewhere: [
                { label: "الدعم", href: "/contact" },
                { label: "الشروط", href: "/terms" },
                { label: "الخصوصيّة", href: "/privacy" },
                { label: "الاشتراكات", href: "/subscription" },
            ],
            copyright: "© ٢٠٢٦ Rico Hunt",
            volumeIssueTail: "المجلّد الأول · العدد ٠٣",
        },
    },
};

/* Motion / interaction parity with the approved /design-preview prospectus
   (Atelier source: src/components/landing/Hero.tsx + styles.css). All motion is
   scoped under `.lpv2-root`, uses CSS/native React only (no new dependency), and
   is disabled under prefers-reduced-motion — both here and via the global guard
   in app/globals.css. Restored, verbatim to the reference:
     · red-bullet kicker pulse            (atelier: animate-pulse)
     · hero underline pen draw-in         (atelier-spark, stroke-dashoffset)
     · ask-next composer blinking caret   (atelier-caret)
     · interview dialog staggered fade-up (atelier-fade-up, +60ms/line)
     · hover = color shift, not opacity fade (nav→ink; CTAs→sun; footer→sun-soft)
   The `.lpv2-ar` rules apply the reference's Arabic-typography guards: no
   synthesised italic (Arabic has no italic), and the arrow nudge is mirrored. */
const LANDING_MOTION_CSS = `
.lpv2-root { --lpv2-ink:#1F1B15; --lpv2-sun:#C6492E; --lpv2-sun-soft:#E0895A; }

.lpv2-root .lpv2-nav,
.lpv2-root .lpv2-openrico,
.lpv2-root .lpv2-secondary,
.lpv2-root .lpv2-foot,
.lpv2-root .lpv2-cta { transition: color .2s ease, border-color .2s ease, background-color .2s ease; }
.lpv2-root .lpv2-nav:hover span { color: var(--lpv2-ink); }
.lpv2-root .lpv2-openrico:hover { border-bottom-color: var(--lpv2-sun); }
.lpv2-root .lpv2-openrico:hover span { color: var(--lpv2-sun); }
.lpv2-root .lpv2-secondary:hover span { color: var(--lpv2-sun); }
.lpv2-root .lpv2-foot:hover { color: var(--lpv2-sun-soft); text-decoration-line: underline; }
.lpv2-root .lpv2-cta:hover { background-color: var(--lpv2-sun); }
.lpv2-root .lpv2-arrow { display:inline-block; transition: transform .2s ease; }
.lpv2-root .lpv2-cta:hover .lpv2-arrow { transform: translateX(2px); }
.lpv2-root.lpv2-ar .lpv2-cta:hover .lpv2-arrow { transform: translateX(-2px); }

/* Arabic typography guards (mirror the reference :lang(ar) rules):
   - wide letter-spacing shreds the connected Arabic script — remove it everywhere
     (overrides the inline tracking on mono/eyebrow labels via !important);
   - uppercase labels render in the system Arabic sans (IBM Plex Mono has no Arabic);
   - synthesised italic looks broken — render upright. */
.lpv2-root.lpv2-ar, .lpv2-root.lpv2-ar * { letter-spacing: 0 !important; }
.lpv2-root.lpv2-ar .uppercase { font-family: var(--font-body), ui-sans-serif, system-ui, sans-serif !important; }
.lpv2-root.lpv2-ar .italic { font-style: normal; }

/* keyboard focus — visible ring on every interactive element (was browser-default only) */
.lpv2-root a:focus-visible,
.lpv2-root button:focus-visible { outline: 2px solid var(--lpv2-sun); outline-offset: 3px; border-radius: 2px; }

.lpv2-root .lpv2-pulse { animation: lpv2-pulse 2.4s cubic-bezier(0.4,0,0.6,1) infinite; }
.lpv2-root .lpv2-underline { stroke-dasharray:300; stroke-dashoffset:300; animation: lpv2-spark 1.15s cubic-bezier(0.16,1,0.3,1) .2s forwards; }
.lpv2-root .lpv2-caret { animation: lpv2-caret 1s steps(1,end) infinite; }
.lpv2-root .lpv2-fade-up { animation: lpv2-fade-up .75s cubic-bezier(0.16,1,0.3,1) both; }

@keyframes lpv2-pulse { 0%,100% { opacity:1 } 50% { opacity:.35 } }
@keyframes lpv2-spark { to { stroke-dashoffset:0 } }
@keyframes lpv2-caret { 0%,45% { opacity:1 } 50%,100% { opacity:0 } }
@keyframes lpv2-fade-up { from { opacity:0; transform:translateY(10px) } to { opacity:1; transform:translateY(0) } }

@media (prefers-reduced-motion: reduce) {
  .lpv2-root .lpv2-pulse,
  .lpv2-root .lpv2-underline,
  .lpv2-root .lpv2-caret,
  .lpv2-root .lpv2-fade-up { animation: none !important; }
  .lpv2-root .lpv2-underline { stroke-dashoffset: 0 !important; }
  .lpv2-root .lpv2-fade-up { opacity:1 !important; transform:none !important; }
  .lpv2-root .lpv2-caret { opacity:1 !important; }
}
`;

function Masthead() {
    const [open, setOpen] = useState(false);
    const { language, setLanguage } = useLanguage();
    const t = COPY[language];
    const isAr = language === "ar";
    const arrow = isAr ? "←" : "→";
    return (
        <header style={{ borderBottom: `1px solid ${C.hair}` }}>
            <div className="max-w-6xl mx-auto px-5 sm:px-8">
                {/* row 1 */}
                <div className="flex items-center justify-between py-4 gap-4">
                    <div className="flex items-baseline gap-3 min-w-0">
                        <Link href="/" className="text-[1.35rem] leading-none tracking-tight" style={{ fontFamily: SERIF, color: C.ink }}>Rico Hunt</Link>
                        <Mono className="hidden sm:inline" style={{ color: C.ink55, letterSpacing: "0.18em" }}>{t.volumeIssue}</Mono>
                    </div>
                    <nav className="hidden md:flex items-center gap-6">
                        {t.nav.map((n) => (
                            <Link key={n.href} href={n.href} className="lpv2-nav">
                                <Mono style={{ color: C.ink70, letterSpacing: "0.16em" }}>{n.label}</Mono>
                            </Link>
                        ))}
                    </nav>
                    <div className="flex items-center gap-3">
                        {/* EN / AR control — enabled; selecting a language sets the app-global preference. */}
                        <span className="hidden sm:inline-flex items-center rounded-[3px] overflow-hidden" style={{ border: `1px solid ${C.hair}` }}>
                            <button type="button" onClick={() => setLanguage("en")} aria-pressed={!isAr} style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", background: !isAr ? C.ink : "transparent", color: !isAr ? C.panel : C.ink40, cursor: "pointer" }}>EN</button>
                            <button type="button" onClick={() => setLanguage("ar")} aria-pressed={isAr} style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", background: isAr ? C.ink : "transparent", color: isAr ? C.panel : C.ink40, cursor: "pointer" }}>عر</button>
                        </span>
                        <Link href="/command" className="lpv2-openrico whitespace-nowrap" style={{ borderBottom: `1px solid ${C.ink}` }}>
                            <span style={{ fontFamily: MONO, fontSize: 12, color: C.ink }}>{t.openRico} {arrow}</span>
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
                    <Mono style={{ color: C.ink55, letterSpacing: "0.16em" }}>{t.place}</Mono>
                    <span className="h-px flex-1" style={{ background: C.hair }} aria-hidden="true" />
                    <Mono className="hidden sm:inline" style={{ color: C.ink55, letterSpacing: "0.16em" }}>{t.bilingualBadge}</Mono>
                </div>
                {/* mobile nav */}
                {open && (
                    <div className="md:hidden flex flex-col gap-3 pb-4">
                        {t.nav.map((n) => (
                            <Link key={n.href} href={n.href} onClick={() => setOpen(false)}>
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
    const { language } = useLanguage();
    const t = COPY[language].hero;
    const isAr = language === "ar";
    return (
        <section className="max-w-6xl mx-auto px-5 sm:px-8 pt-16 sm:pt-24 pb-16">
            <p className="flex items-center gap-2.5 mb-10">
                <span className="lpv2-pulse w-2 h-2 rounded-full flex-shrink-0" style={{ background: C.red }} aria-hidden="true" />
                <Mono style={{ color: C.ink70, letterSpacing: "0.2em" }}>{t.eyebrow}</Mono>
            </p>
            <h1 className="font-normal tracking-[-0.02em] text-[2.9rem] leading-[0.98] sm:text-[4.6rem] sm:leading-[0.95] max-w-4xl" style={{ fontFamily: SERIF, color: C.ink }}>
                {t.titleA}{" "}
                <span className="relative inline-block italic font-medium">
                    {t.titleB}
                    <svg className="absolute left-0 w-full" style={{ bottom: "0.06em", height: "0.16em" }} viewBox="0 0 300 8" preserveAspectRatio="none" aria-hidden="true">
                        <path className="lpv2-underline" d="M2 6 C 60 3, 120 5, 180 4 S 260 3, 298 5" fill="none" stroke={C.red} strokeWidth={4} strokeLinecap="round" />
                    </svg>
                </span>
            </h1>
            <p className="mt-8 max-w-xl text-[1.05rem] leading-relaxed" style={{ color: C.ink70 }}>
                {t.body}
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-6">
                <Link href="/command" className="lpv2-cta group inline-flex items-center gap-2.5 px-6 py-3.5 rounded-full text-sm font-semibold" style={{ background: C.ink, color: C.panel }}>
                    {t.primary} <span className="lpv2-arrow" aria-hidden="true">{isAr ? "←" : "→"}</span>
                </Link>
                <Link href="#system" className="lpv2-secondary underline underline-offset-4 decoration-1" style={{ textDecorationColor: C.red }}>
                    <Mono style={{ color: C.ink70 }}>{t.secondary}</Mono>
                </Link>
            </div>
        </section>
    );
}

function SystemSection() {
    const { language } = useLanguage();
    const t = COPY[language].interview;
    const p = COPY[language].plate;
    return (
        <section id="system" className="max-w-6xl mx-auto px-5 sm:px-8 py-16" style={{ borderTop: `1px solid ${C.hair}` }}>
            <div className="grid lg:grid-cols-2 gap-12 lg:gap-16">
                {/* interview */}
                <div>
                    <div className="flex items-center gap-3 mb-8">
                        <Mono style={{ color: C.ink55 }}>{t.eyebrow}</Mono>
                        <span className="h-px w-10" style={{ background: C.hair }} aria-hidden="true" />
                        <Mono style={{ color: C.ink55 }}>{t.transcribed}</Mono>
                    </div>
                    <div className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-8">
                        <Mono className="lpv2-fade-up" style={{ color: C.ink40 }}>{t.you}</Mono>
                        <p className="lpv2-fade-up text-[1.25rem] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
                            {t.youQuote}
                        </p>
                        <div className="lpv2-fade-up" style={{ animationDelay: "120ms" }}>
                            <Mono style={{ color: C.red }}>{t.rico}</Mono>
                            <p className="mt-2 leading-relaxed" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.14em", color: C.ink40, textTransform: "uppercase" }}>
                                {t.ricoAside}
                            </p>
                        </div>
                        <p className="lpv2-fade-up text-[1.25rem] leading-snug italic" style={{ fontFamily: SERIF, color: C.ink, animationDelay: "120ms" }}>
                            {t.ricoQuote}
                        </p>
                    </div>
                    <div className="mt-10 pt-8" style={{ borderTop: `1px solid ${C.hair}` }}>
                        <Mono style={{ color: C.ink55 }}>{t.askNext}</Mono>
                        {/* illustrative, non-interactive (reference is a static prospectus) */}
                        <div className="mt-4 text-[1.4rem]" style={{ fontFamily: SERIF, color: C.ink }} aria-hidden="true">
                            {t.suggestions[0]}
                            <span className="lpv2-caret inline-block align-baseline" style={{ width: 2, height: "0.9em", marginInlineStart: 3, transform: "translateY(3px)", background: C.red }} />
                        </div>
                        <div className="mt-5 flex flex-wrap gap-2.5" aria-hidden="true">
                            {t.suggestions.map((c) => (
                                <span key={c} className="px-3 py-1.5 rounded-full" style={{ border: `1px solid ${C.hair}`, fontFamily: MONO, fontSize: 11, color: C.ink70 }}>{c}</span>
                            ))}
                        </div>
                    </div>
                </div>
                {/* sample-match plate */}
                <Plate className="p-7 sm:p-8">
                    <div className="flex items-center gap-3 mb-6">
                        <Mono style={{ color: C.ink55 }}>{p.label}</Mono>
                        <span className="h-px flex-1" style={{ background: C.hair }} aria-hidden="true" />
                        <span className="px-2.5 py-0.5 rounded-full" style={{ border: `1px solid ${C.red}`, fontFamily: MONO, fontSize: 10, letterSpacing: "0.12em", color: C.red, textTransform: "uppercase" }}>{p.illustration}</span>
                    </div>
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <Mono style={{ color: C.ink55 }}>{p.companyLoc}</Mono>
                            <h3 className="mt-3 text-[2rem] leading-[1.05] font-normal" style={{ fontFamily: SERIF, color: C.ink }}>
                                {p.title.map((line, i) => (i === 0 ? line : <span key={i}><br />{line}</span>))}
                            </h3>
                            <p className="mt-3" style={{ fontFamily: MONO, fontSize: 13, color: C.ink70 }}>{p.salary}</p>
                        </div>
                        <span className="inline-flex items-center justify-center w-16 h-16 rounded-full flex-shrink-0 text-xl" style={{ border: `1.5px solid ${C.red}`, fontFamily: SERIF, color: C.red }}>91</span>
                    </div>
                    <div className="my-6 h-px" style={{ background: C.hair }} aria-hidden="true" />
                    <Mono style={{ color: C.ink55 }}>{p.whyFits}</Mono>
                    <ol className="mt-4 flex flex-col gap-3.5">
                        {p.reasons.map((reason, i) => (
                            <li key={i} className="grid grid-cols-[auto_1fr] gap-3">
                                <Mono style={{ color: C.red }}>{String(i + 1).padStart(2, "0")}</Mono>
                                <span className="text-[0.95rem] leading-snug" style={{ color: C.ink }}>{reason}</span>
                            </li>
                        ))}
                    </ol>
                    <div className="mt-6 p-4 rounded-[3px]" style={{ background: C.inset }}>
                        <Mono style={{ color: C.red }}>{p.worthKnowing}</Mono>
                        <p className="mt-1.5 text-[0.95rem]" style={{ color: C.ink70 }}>{p.concern}</p>
                    </div>
                </Plate>
            </div>
        </section>
    );
}

function BilingualBand() {
    const { language } = useLanguage();
    const band = COPY[language].band;
    return (
        <section className="py-10" style={{ borderTop: `1px solid ${C.hair}`, borderBottom: `1px solid ${C.hair}` }}>
            <div className="max-w-6xl mx-auto px-5 sm:px-8">
                <p className="text-[1.35rem] sm:text-[1.6rem] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
                    {band.map((seg, i) => (
                        <span key={i}>
                            {i > 0 && " · "}
                            {seg.a}
                            <span className="italic">{seg.b}</span>
                        </span>
                    ))}
                </p>
            </div>
        </section>
    );
}

function IdeaSection() {
    const { language } = useLanguage();
    const t = COPY[language].idea;
    return (
        <section id="idea" className="max-w-6xl mx-auto px-5 sm:px-8 py-24 sm:py-32">
            <div className="grid lg:grid-cols-[auto_1fr] gap-8 lg:gap-16">
                <Mono style={{ color: C.ink55 }}>{t.eyebrow}</Mono>
                <h2 className="font-normal tracking-[-0.015em] text-[2.6rem] leading-[1.02] sm:text-[4rem] sm:leading-[0.98] max-w-3xl" style={{ fontFamily: SERIF, color: C.ink }}>
                    {t.titleA}{" "}
                    <span className="italic font-medium">{t.titleB}</span>
                </h2>
            </div>
            <ol className="mt-16">
                {t.items.map((m, i) => (
                    <li key={m.n} className="lpv2-fade-up grid gap-3 sm:grid-cols-[110px_minmax(0,1fr)_minmax(0,1.5fr)] sm:gap-10 lg:gap-14 py-9" style={{ borderTop: `1px solid ${C.hair}`, animationDelay: `${i * 80}ms` }}>
                        <span className="leading-none text-[3.25rem] sm:text-[4.25rem]" style={{ fontFamily: SERIF, color: C.red }}>{m.n}</span>
                        <h3 className="self-center leading-tight text-[1.5rem] sm:text-[1.75rem]" style={{ fontFamily: SERIF, color: C.ink }}>{m.title}</h3>
                        <p className="self-center leading-relaxed text-[1.05rem]" style={{ color: C.ink70 }}>{m.body}</p>
                    </li>
                ))}
            </ol>
        </section>
    );
}

/* Shared marketing colophon footer (the same footer pattern shown on the
   /design-preview support page). The preview-only disclaimer line
   ("Everything you see here is design…") is intentionally OMITTED to avoid
   preview leakage on production; the rest is verbatim. */
function Colophon() {
    const { language } = useLanguage();
    const t = COPY[language].footer;
    return (
        <footer id="colophon" style={{ background: C.footer, color: C.footerInk }}>
            <div className="max-w-6xl mx-auto px-5 sm:px-8 py-16">
                <div className="grid lg:grid-cols-2 gap-12">
                    <div>
                        <span className="uppercase" style={{ fontFamily: MONO, fontSize: 11, letterSpacing: "0.2em", color: C.footerInk60 }}>{t.eyebrow}</span>
                        <h2 className="mt-5 text-[2.2rem] sm:text-[2.8rem] leading-[1.02] font-normal" style={{ fontFamily: SERIF }}>
                            {t.titleA} <span className="italic" style={{ color: C.red }}>{t.titleB}</span>
                        </h2>
                        <p className="mt-5 max-w-md leading-relaxed" style={{ color: C.footerInk60 }}>
                            {t.body}
                        </p>
                    </div>
                    <div className="grid grid-cols-2 gap-x-8 gap-y-7 self-start lg:pt-2">
                        {t.meta.map((m) => (
                            <div key={m.k}>
                                <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>{m.k}</span>
                                <p className="mt-1.5 text-[0.95rem]" style={{ fontFamily: SERIF }}>{m.v}</p>
                            </div>
                        ))}
                        <div className="col-span-2 mt-2 pt-6" style={{ borderTop: `1px solid ${C.footerHair}` }}>
                            <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>{t.elsewhereLabel}</span>
                            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                                {t.elsewhere.map((e) => (
                                    <Link key={e.href} href={e.href} className="lpv2-foot text-sm underline underline-offset-4 decoration-1" style={{ color: C.footerInk, textDecorationColor: C.footerHair }}>{e.label}</Link>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
                <div className="mt-14 pt-6 flex items-center justify-between" style={{ borderTop: `1px solid ${C.footerHair}` }}>
                    <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>{t.copyright}</span>
                    <span className="uppercase" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.18em", color: C.footerInk60 }}>{t.volumeIssueTail}</span>
                </div>
            </div>
        </footer>
    );
}

export default function LandingPageV2() {
    const { language } = useLanguage();
    const isAr = language === "ar";
    return (
        <div
            className={`lpv2-root ${isAr ? "lpv2-ar" : ""} min-h-screen overflow-x-hidden ${fraunces.variable}`}
            dir={isAr ? "rtl" : "ltr"}
            lang={language}
            style={{ background: C.bg, color: C.ink, fontFamily: "var(--font-body), ui-sans-serif, sans-serif" }}
        >
            <style dangerouslySetInnerHTML={{ __html: LANDING_MOTION_CSS }} />
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

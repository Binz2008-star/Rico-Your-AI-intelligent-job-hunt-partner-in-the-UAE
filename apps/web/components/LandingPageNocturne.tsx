"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { AnimatePresence, motion, MotionConfig, useInView, useMotionValue, useScroll, useSpring, useTransform } from "framer-motion";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Aura } from "./ui/rico/Aura";
import { Eyebrow } from "./ui/rico/Eyebrow";
import { FitRing } from "./ui/rico/FitRing";
import { GlassCard } from "./ui/rico/GlassCard";
import { RicoLogoMark } from "./ui/rico/RicoLogoMark";
import { RicoButton } from "./ui/rico/RicoButton";

// Reusable fade-up wrapper — uses `animate` (not whileInView) so content is always
// visible on mount regardless of scroll position or IntersectionObserver state.
function FadeUp({ children, delay = 0, className = "" }: { children: React.ReactNode; delay?: number; className?: string }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay, ease: [0.22, 0.61, 0.36, 1] }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// Animated counter that counts up when it enters the viewport
function CountUp({ to, duration = 1.4 }: { to: number; duration?: number }) {
    const ref = useRef<HTMLSpanElement>(null);
    const inView = useInView(ref, { once: true, margin: "0px" });
    const [count, setCount] = useState(0);
    useEffect(() => {
        if (!inView) return;
        const start = performance.now();
        const tick = (now: number) => {
            const p = Math.min((now - start) / (duration * 1000), 1);
            const eased = 1 - Math.pow(1 - p, 3);
            setCount(Math.round(eased * to));
            if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    }, [inView, to, duration]);
    return <span ref={ref}>{count}</span>;
}

// Mouse-tracking 3-D tilt wrapper for the hero match card
function TiltCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
    const cardX = useMotionValue(0);
    const cardY = useMotionValue(0);
    const rotateX = useSpring(useTransform(cardY, [-0.5, 0.5], [5, -5]), { stiffness: 300, damping: 30 });
    const rotateY = useSpring(useTransform(cardX, [-0.5, 0.5], [-5, 5]), { stiffness: 300, damping: 30 });

    const onMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();
        cardX.set((e.clientX - rect.left) / rect.width - 0.5);
        cardY.set((e.clientY - rect.top) / rect.height - 0.5);
    };
    const onMouseLeave = () => { cardX.set(0); cardY.set(0); };

    return (
        <motion.div
            className={`relative [transform-style:preserve-3d] ${className}`}
            style={{ rotateX, rotateY }}
            onMouseMove={onMouseMove}
            onMouseLeave={onMouseLeave}
        >
            {children}
        </motion.div>
    );
}

// SVG Icons
const ShieldIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" /></svg>;
const CheckIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" /></svg>;
const GlobeIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15 15 0 010 20M12 2a15 15 0 000 20" /></svg>;
const LanguagesIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8" /></svg>;
const HomeIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12l9-9 9 9M5 10v10h14V10" /></svg>;
const SearchIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>;
const BookmarkIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21l-7-4-7 4V5a2 2 0 012-2h10a2 2 0 012 2z" /></svg>;
const UserIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a6 6 0 0112 0v1" /></svg>;
const SparklesIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" /></svg>;
const MessageSquareIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>;
const BarChartIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 20V10M12 20V4M6 20v-6" /></svg>;
const CreditCardIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20" /></svg>;
const ChevronDownIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>;
const LockIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" /></svg>;

export default function LandingPageNocturne() {
    const { language, setLanguage } = useLanguage();
    const isAr = language === "ar";
    const [openFaq, setOpenFaq] = useState<number | null>(null);
    const [headerScrolled, setHeaderScrolled] = useState(false);
    const { scrollYProgress } = useScroll();
    const scrollProgress = useSpring(scrollYProgress, { stiffness: 200, damping: 30, restDelta: 0.001 });

    useEffect(() => {
        const onScroll = () => setHeaderScrolled(window.scrollY > 12);
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    const t = {
        signIn: isAr ? "تسجيل الدخول" : "Sign in",
        startFree: isAr ? "ابدأ مجاناً" : "Start free",
        langToggle: isAr ? "EN" : "عربي",
        eyebrow: isAr ? "ذكاء وظيفي · الإمارات" : "AI Job Intelligence · UAE",
        headline1: isAr ? "سيرتك الذاتية، مفهومة." : "Your CV, understood.",
        headline2: isAr ? "وظيفتك القادمة في انتظارك." : "Your next role, found.",
        subtitle: isAr
            ? "ارفع مرة واحدة. يقرأ ريكو خبرتك، ويعرض وظائف الإمارات التي تناسبك فعلاً، ويشرح السبب — بالعربية والإنجليزية."
            : "Upload once. Rico reads your experience, surfaces UAE roles that fit, and tells you why — in English and Arabic.",
        ctaUpload: isAr ? "ارفع سيرتك الذاتية" : "Upload your CV",
        ctaHow: isAr ? "كيف يعمل" : "See how it works",
        trust1: isAr ? "متخصص في الإمارات" : "UAE-focused",
        trust2: isAr ? "عربي + إنجليزي" : "English + Arabic",
        trust3: isAr ? "أنت توافق على كل طلب" : "You approve every application",
        matchLabel: isAr ? "معاينة المطابقة" : "Rico match preview",
        matchBy: isAr ? "قراءة من سيرتك · منذ ثانيتين" : "Read from your CV · 2s ago",
        matchRole: isAr ? "مسؤول امتثال بيئي" : "Environmental Compliance Officer",
        matchMeta: isAr ? "أبوظبي · دوام كامل · منشورة اليوم" : "Abu Dhabi · Full-time · Posted today",
        matchReason1: isAr ? "خلفية في الامتثال بالإمارات" : "UAE compliance background",
        matchReason2: isAr ? "خبرة في العمليات البيئية" : "Environmental operations experience",
        matchReason3: isAr ? "مهارات التفتيش وإعداد التقارير" : "Inspection & reporting skills",
        matchNext: isAr ? "التالي: فتح رابط التقديم" : "Next: open apply link",
        matchReview: isAr ? "مراجعة" : "Review",
        trustBar1: isAr ? "بياناتك لن تُباع أبداً" : "Your data is never sold",
        trustBar2: isAr ? "موافقة يدوية — دائماً" : "Manual approval — always",
        trustBar3: isAr ? "مبني لسوق الإمارات" : "Built for the UAE market",
        trustBar4: isAr ? "ثنائي اللغة" : "Bilingual EN / AR",
        stepsEyebrow: isAr ? "كيف يعمل" : "How it works",
        stepsTitle: isAr ? "ثلاث خطوات. بلا تعقيد." : "Three steps. No noise.",
        stepsSubtitle: isAr
            ? "لوحات الوظائف تدفنك في أدوار لا تناسبك. ريكو يحوّل سيرتك إلى بحث يقوم بالتصفية نيابة عنك."
            : "Job boards bury you in roles that don't fit. Rico turns your CV into a search that does the filtering for you.",
        step1Num: "01",
        step1Title: isAr ? "ارفع سيرتك الذاتية" : "Upload your CV",
        step1Body: isAr
            ? "ملف واحد. يقرأ ريكو خبرتك الحقيقية — ليس مجرد الكلمات المفتاحية — بالإنجليزية أو العربية."
            : "One file. Rico reads your real experience — not just keywords — in English or Arabic.",
        step2Num: "02",
        step2Title: isAr ? "شاهد ما يناسبك" : "See what fits",
        step2Body: isAr
            ? "وظائف مرتبة حسب التوافق الفعلي، كل منها مع درجة تقييم وأسبابها."
            : "Roles ranked by genuine fit, each with a score and the reasons behind it.",
        step3Num: "03",
        step3Title: isAr ? "تابع كل خطوة" : "Track every move",
        step3Body: isAr
            ? "المحفوظة والمفتوحة والمتقدَّم إليها — بحثك الكامل في مركز قيادة هادئ."
            : "Saved, opened, applied — your whole search in one calm command center.",
        // Phase 4 - Product/Command
        cmdEyebrow: isAr ? "مركز القيادة" : "Command center",
        cmdTitle: isAr ? "تحدث مع ريكو كخبير توظيف." : "Talk to Rico like a CV reader.",
        cmdSubtitle: isAr
            ? "اسأل بالعربية أو الإنجليزية. يجيب ريكو من خبرتك وسوق الإمارات — ولا يتحرك بدون موافقتك."
            : "Ask in Arabic or English. Rico answers from your experience and the UAE market — and never acts without your approval.",
        chatMsg1: isAr ? "اعثر على أدوار امتثال في أبوظبي تناسب خلفيتي." : "Find compliance roles in Abu Dhabi matching my background.",
        chatMsg2: isAr
            ? "وجدت 7 وظائف متوافقة. الأنسب: مسؤول امتثال بيئي — 86% توافق. خبرتك في الامتثال الإماراتي متناسقة. هل تريد رابط التقديم؟"
            : "Found 7 matches. Top: Environmental Compliance Officer — 86 fit. Your UAE compliance experience aligns. Want the apply link?",
        chatMsg3: isAr ? "أرني الاثنتين التاليتين أولاً." : "Show me the next two first.",
        chatInput: isAr ? "اسأل ريكو أي شيء عن بحثك الوظيفي..." : "Ask Rico anything about your job search...",
        // Phase 4 - Dashboard
        dashEyebrow: isAr ? "لوحة التحكم" : "Your dashboard",
        dashTitle: isAr ? "شاشة واحدة. البحث بالكامل." : "One screen. The whole hunt.",
        dashSubtitle: isAr
            ? "كل وظيفة محفوظة، وكل تقديم، وكل رسالة — منظمة حسب الأولوية وليس التاريخ فقط."
            : "Every saved job, every application, every message — organized by priority, not just date.",
        // Phase 4 - Pricing
        pricingEyebrow: isAr ? "الأسعار" : "Pricing",
        pricingTitle: isAr ? "ابدأ مجاناً. ادفع فقط عندما يثبت ريكو جدارته." : "Start free. Pay only when Rico earns it.",
        freeName: isAr ? "مجانية" : "Free",
        freePrice: isAr ? "٠ درهم" : "AED 0",
        freeF1: isAr ? "٥٠ رسالة ذكاء اصطناعي/شهر" : "50 AI messages/month",
        freeF2: isAr ? "١٠ وظائف محفوظة" : "10 saved jobs",
        freeF3: isAr ? "تقييم ملاءمة السيرة والأسباب" : "CV fit scoring & reasons",
        proName: isAr ? "الاحترافية" : "Pro",
        proPrice: "AED 29",
        proF1: isAr ? "٣٠٠ رسالة AI/شهر" : "300 AI messages/month",
        proF2: isAr ? "١٠٠ وظيفة محفوظة" : "100 saved jobs",
        proF3: isAr ? "مطابقة أولوية وتنبيهات" : "Priority matching & alerts",
        proF4: isAr ? "مساعد مسودات التقديم" : "Application draft assistant",
        popular: isAr ? "الأكثر شعبية" : "Most popular",
        premiumName: isAr ? "المميزة" : "Premium",
        premiumPrice: "AED 49",
        premiumF1: isAr ? "١٥٠٠ رسالة AI/شهر" : "1,500 AI messages/month",
        premiumF2: isAr ? "وظائف محفوظة بلا حدود" : "Unlimited saved jobs",
        premiumF3: isAr ? "تحسين السيرة عربي + إنجليزي" : "CV optimization AR+EN",
        premiumF4: isAr ? "تذكيرات متابعة ورؤى" : "Follow-up reminders & insights",
        cancelAnytime: isAr ? "إلغاء في أي وقت. لا تحتاج بطاقة للبدء." : "Cancel anytime. No card required to start.",
        // Phase 5 - Credibility
        credEyebrow: isAr ? "لماذا تثق في ريكو" : "Why trust Rico",
        credTitle: isAr ? "شركة حقيقية، ليس نظاماً مغلقاً." : "A real company, not a black box.",
        credSubtitle: isAr
            ? "مطور ويُدار في الإمارات — مع حماية الخصوصية وتحكمك مصممين من البداية."
            : "Built and operated in the UAE — with privacy and your control designed in from the start.",
        credPoint1Title: isAr ? "أنت تبقى في السيطرة" : "You stay in control",
        credPoint1Body: isAr
            ? "ريكو لا يتقدم ولا يرسل ولا يشارك أي شيء بدون موافقتك الصريحة."
            : "Rico never applies, sends, or shares anything without your explicit approval.",
        credPoint2Title: isAr ? "بياناتك لن تُباع أبداً" : "Your data is never sold",
        credPoint2Body: isAr
            ? "تُستخدم فقط لبحثك الوظيفي — دون أي استخدام آخر."
            : "It's used only to power your job search — full stop.",
        credPoint3Title: isAr ? "ثنائي اللغة حقاً" : "Truly bilingual",
        credPoint3Body: isAr
            ? "عربي وإنجليزي، من البداية للنهاية — بما في ذلك اليمين لليسار بالكامل."
            : "Arabic and English, end to end — including right-to-left throughout.",
        founderLabel: isAr ? "بُني بواسطة روبن إدوان" : "Built by Roben Edwan",
        founderMeta: isAr
            ? "المؤسس، إيكو تكنولوجي ذ.م.م · مسجلة في الإمارات"
            : "Founder, Eco Technology L.L.C · UAE-registered",
        // Phase 5 - FAQ
        faqEyebrow: isAr ? "الأسئلة الشائعة" : "Questions",
        faqTitle: isAr ? "أبرز الأسئلة." : "What people ask first.",
        faq1Q: isAr ? "هل يتقدم ريكو بالوظائف نيابة عني؟" : "Does Rico apply to jobs for me?",
        faq1A: isAr
            ? "لا — إلا إذا طلبت ذلك. يجد ويرتب الوظائف المتوافقة ويُعد المسودات، لكنك توافق وترسل كل طلب بنفسك."
            : "No — not unless you say so. Rico finds and ranks matches and prepares drafts, but you approve and send every application yourself.",
        faq2Q: isAr ? "هل سيرتي الذاتية وبياناتي آمنة؟" : "Is my CV and data safe?",
        faq2A: isAr
            ? "نعم. بياناتك تُستخدم فقط لتفعيل بحثك ولن تُباع. ريكو يُشغَّل بواسطة شركة مسجلة في الإمارات."
            : "Yes. Your data is used only to power your job search and is never sold. Rico is operated by a UAE-registered company.",
        faq3Q: isAr ? "هل يعمل في مجالي؟" : "Does it work in my field?",
        faq3A: isAr
            ? "يقرأ خبرتك الفعلية بدلاً من مطابقة الكلمات المفتاحية، لذا يعمل في جميع القطاعات: المالية والعمليات والهندسة وغيرها."
            : "Rico reads your actual experience rather than matching keywords, so it works across sectors — finance, operations, engineering, and more.",
        faq4Q: isAr ? "هل يمكنني استخدامه بالعربية؟" : "Can I use it in Arabic?",
        faq4A: isAr
            ? "بالكامل. المنتج بالكامل — المطابقات والمحادثة والتتبع — يعمل بالعربية والإنجليزية."
            : "Fully. The entire product — matches, chat, and tracking — works in Arabic and English.",
        // Phase 5 - Final CTA
        finalTitle: isAr ? "دع ريكو يقرأ سيرتك. اكتشف الوظائف المناسبة — اليوم." : "Let Rico read your CV. See what fits — tonight.",
        finalSubtitle: isAr ? "مجاني للبدء. لا بطاقة ائتمان. أنت المتحكم طوال الطريق." : "Free to start. No card. You're in control the whole way.",
        finalCta: isAr ? "ارفع سيرتك الذاتية" : "Upload your CV",
        // Phase 5 - Footer
        footerAbout: isAr ? "من نحن" : "About",
        footerContact: isAr ? "تواصل" : "Contact",
        footerTerms: isAr ? "الشروط" : "Terms",
        footerPrivacy: isAr ? "الخصوصية" : "Privacy",
        footerRefunds: isAr ? "الاسترداد" : "Refunds",
        footerFaq: isAr ? "الأسئلة" : "FAQ",
        footerWhatsapp: isAr ? "واتساب" : "WhatsApp",
        footerRights: isAr ? "© 2026 ريكو هانت. جميع الحقوق محفوظة." : "© 2026 Rico Hunt. All rights reserved.",
        footerPowered: isAr
            ? "تُدار بواسطة Eco Technology L.L.C · الإمارات"
            : "Powered by Eco Technology Environment Protection Services L.L.C · UAE",
    };

    return (
        <MotionConfig reducedMotion="user">
        {/* Scroll progress bar — gold line at the top of the viewport */}
        <motion.div
            className="fixed top-0 inset-x-0 h-[2px] origin-left z-[60] motion-reduce:hidden"
            style={{ scaleX: scrollProgress, background: "linear-gradient(90deg, rgb(var(--gold-hover)), rgb(var(--gold)))" }}
            aria-hidden="true"
        />
        <div dir={isAr ? "rtl" : "ltr"} className="relative min-h-screen overflow-x-hidden bg-void text-text-primary">
            {/* Atmosphere — layered command-center depth (all fixed, non-interactive) */}
            <div className="fixed inset-0 pointer-events-none z-0 motion-reduce:opacity-50" aria-hidden="true">
                {/* Stage light: faint ember radial from top center */}
                <div className="absolute inset-x-0 -top-[30%] h-[80%] bg-[radial-gradient(ellipse_55%_60%_at_50%_0%,rgb(var(--gold)/0.08),transparent_70%)]" />
                {/* Drifting glows (slow float = parallax against the 3px card drift) */}
                <div className="absolute -left-40 -top-40 h-[620px] w-[620px] rounded-full bg-ember/[0.07] blur-[140px] animate-float" />
                <div className="absolute -right-40 top-[40%] h-[520px] w-[520px] rounded-full bg-aura/[0.04] blur-[140px] animate-float-delayed" />
                <div className="absolute bottom-[-160px] left-[30%] h-[520px] w-[520px] rounded-full bg-ember/[0.04] blur-[140px]" />
                {/* Beam: vertical light shaft behind the hero card column */}
                <div className="absolute top-0 start-[58%] h-[70vh] w-[44%] bg-[linear-gradient(180deg,rgb(var(--gold)/0.05),transparent_75%)] [mask-image:radial-gradient(ellipse_60%_90%_at_50%_0%,#000,transparent)] blur-2xl" />
                {/* Grid: faint plotting lines, fading out radially */}
                <div className="absolute inset-0 opacity-[0.35] bg-[linear-gradient(rgb(var(--overlay)/0.045)_1px,transparent_1px),linear-gradient(90deg,rgb(var(--overlay)/0.045)_1px,transparent_1px)] bg-[size:72px_72px] [mask-image:radial-gradient(ellipse_75%_60%_at_50%_22%,#000_30%,transparent_78%)]" />
                {/* Vignette: pulls focus to center, grounds the edges */}
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_115%_95%_at_50%_40%,transparent_55%,rgb(var(--bg)/0.55)_100%)]" />
            </div>

            {/* Header */}
            <header className={`sticky top-0 z-50 backdrop-blur-xl bg-void/55 transition-[border-color,box-shadow] duration-200 ${headerScrolled ? "border-b border-overlay/15 shadow-[0_1px_16px_rgba(0,0,0,0.35)]" : "border-b border-transparent"}`}>
                {/* Gradient hairline + ember accent — ties the bar into the stage light */}
                <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-overlay/20 to-transparent" aria-hidden="true" />
                <div className="absolute inset-x-[30%] bottom-0 h-px bg-gradient-to-r from-transparent via-ember/30 to-transparent" aria-hidden="true" />
                <div className="max-w-[1140px] mx-auto px-6 h-16 flex items-center justify-between">
                    <Link href="/" className="flex items-center gap-2.5 font-display font-bold text-lg tracking-tight">
                        <RicoLogoMark />
                        <span>Rico<span className="text-ember font-bold"> Hunt</span></span>
                    </Link>
                    <nav className="flex items-center gap-2.5">
                        <div className="hidden md:flex items-center gap-1 me-1">
                            <a href="#how" className="text-sm text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded-lg hover:bg-surface/40">{t.stepsEyebrow}</a>
                            <a href="#pricing" className="text-sm text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded-lg hover:bg-surface/40">{t.pricingEyebrow}</a>
                            <a href="#faq" className="text-sm text-text-secondary hover:text-text-primary transition-colors px-2 py-1 rounded-lg hover:bg-surface/40">{t.faqEyebrow}</a>
                        </div>
                        <button type="button" onClick={() => setLanguage(isAr ? "en" : "ar")} className="font-mono text-xs text-text-secondary border border-overlay/7 px-2.5 py-1.5 rounded-lg hover:text-text-primary hover:border-ember transition-colors bg-transparent">{t.langToggle}</button>
                        <Link href="/login" className="hidden sm:block text-sm text-text-secondary hover:text-text-primary transition-colors">{t.signIn}</Link>
                        <Link href="/signup"><RicoButton variant="primary" size="sm">{t.startFree}</RicoButton></Link>
                    </nav>
                </div>
            </header>

            <main className="relative z-10">
                {/* Hero */}
                <section className="py-16 md:py-[78px] pb-12 md:pb-[70px]">
                    <div className="max-w-[1140px] mx-auto px-4 sm:px-6 grid lg:grid-cols-[1.05fr_0.95fr] gap-8 md:gap-14 items-center">
                        <FadeUp>
                            <Eyebrow className="mb-6">{t.eyebrow}</Eyebrow>
                            <h1 className="font-display font-semibold text-[clamp(2.3rem,5.6vw,4.2rem)] leading-[1.03] tracking-[-0.028em]">
                                <span className="bg-gradient-to-b from-text-primary to-text-secondary bg-clip-text text-transparent">
                                    {t.headline1.split(" ").map((word, i, arr) => (
                                        <motion.span
                                            key={`h1-${i}`}
                                            initial={{ opacity: 0, y: 14 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ duration: 0.5, delay: i * 0.04, ease: [0.22, 0.61, 0.36, 1] }}
                                            className="inline-block"
                                        >{word}{i < arr.length - 1 ? " " : ""}</motion.span>
                                    ))}
                                </span>
                                <br />
                                <span className="bg-gradient-to-b from-ember-bright to-ember bg-clip-text text-transparent">
                                    {t.headline2.split(" ").map((word, i, arr) => (
                                        <motion.span
                                            key={`h2-${i}`}
                                            initial={{ opacity: 0, y: 14 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ duration: 0.5, delay: (t.headline1.split(" ").length + i) * 0.04, ease: [0.22, 0.61, 0.36, 1] }}
                                            className="inline-block"
                                        >{word}{i < arr.length - 1 ? " " : ""}</motion.span>
                                    ))}
                                </span>
                            </h1>
                            <p className="mt-6 max-w-[42ch] text-lg leading-relaxed text-text-secondary">{t.subtitle}</p>
                            <div className="mt-9 flex flex-wrap gap-3">
                                <Link href="/upload"><RicoButton variant="primary" size="md">{t.ctaUpload}</RicoButton></Link>
                                <Link href="#how"><RicoButton variant="ghost" size="md">{t.ctaHow}</RicoButton></Link>
                            </div>
                            <div className="mt-8 flex flex-wrap gap-2">
                                {[t.trust1, t.trust2, t.trust3].map((item, i) => (
                                    <motion.span
                                        key={item}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.4, delay: 0.45 + i * 0.06, ease: "easeOut" }}
                                        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-text-tertiary border border-overlay/7 rounded-full px-3 py-1.5 bg-surface/30"
                                    >
                                        <span className="h-1 w-1 rounded-full bg-aura shadow-[0_0_6px_rgb(var(--aura)/0.5)]" />{item}
                                    </motion.span>
                                ))}
                            </div>
                        </FadeUp>
                        <FadeUp delay={0.18} className="relative mt-8 lg:mt-0 [perspective:1300px]">
                            {/* Halo grounding the card in the stage light (breathes with the orb) */}
                            <div aria-hidden="true" className="absolute -inset-10 bg-[radial-gradient(ellipse_at_50%_38%,rgb(var(--gold)/0.10),transparent_65%)] blur-2xl animate-glow-pulse motion-reduce:animate-none" />
                            {/* Floor shadow — sells the float */}
                            <div aria-hidden="true" className="absolute -bottom-10 inset-x-12 h-10 bg-[radial-gradient(ellipse_at_center,rgb(var(--shadow-color)/0.6),transparent_70%)] blur-md" />
                            {/* Tilt layer — mouse-tracking 3-D */}
                            <TiltCard>
                            <GlassCard className="p-5 relative overflow-visible animate-drift motion-reduce:animate-none">
                                {/* Top edge-light */}
                                <div aria-hidden="true" className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-ember/40 to-transparent" />
                                <div className="flex items-center gap-2.5 pb-4 mb-4 border-b border-overlay/7 -mx-5 -mt-5 px-5 pt-5 rounded-t-rico-lg bg-gradient-to-b from-overlay/[0.04] to-transparent">
                                    <div className="w-[30px] h-[30px] rounded-full bg-[radial-gradient(circle_at_38%_34%,#fff,rgb(var(--gold-hover))_38%,rgb(var(--gold))_70%)] shadow-[0_0_18px_rgb(var(--gold)/0.65)] motion-safe:animate-breathe" />
                                    <div>
                                        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-secondary">{t.matchLabel}</p>
                                        <p className="text-xs text-text-tertiary">{t.matchBy}</p>
                                    </div>
                                </div>
                                <div className="flex gap-4 items-center">
                                    <div className="flex-1">
                                        <p className="font-display font-semibold text-base">{t.matchRole}</p>
                                        <p className="text-xs text-text-tertiary">{t.matchMeta}</p>
                                        <div className="mt-3 space-y-1.5">
                                            {[t.matchReason1, t.matchReason2, t.matchReason3].map((r) => (
                                                <div key={r} className="flex items-center gap-2 text-sm text-text-secondary">
                                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-aura flex-shrink-0"><path d="M20 6L9 17l-5-5" /></svg>{r}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="relative">
                                        <div aria-hidden="true" className="absolute -inset-3 rounded-full bg-aura/10 blur-xl" />
                                        <FitRing className="relative" value={86} size={96} label={isAr ? "ملاءمة" : "Fit"} />
                                    </div>
                                </div>
                                <div className="mt-4 pt-3 border-t border-overlay/7 flex items-center justify-between">
                                    <p className="text-xs text-text-tertiary">{isAr ? "التالي: " : "Next: "}<span className="text-text-primary font-medium">{isAr ? "فتح رابط التقديم" : "open apply link"}</span></p>
                                    <RicoButton variant="ghost" size="sm">{t.matchReview}</RicoButton>
                                </div>
                            </GlassCard>
                            </TiltCard>
                        </FadeUp>
                    </div>
                </section>

                {/* Trust Bar */}
                <div className="border-y border-overlay/7 py-4 md:py-6 bg-surface/30 backdrop-blur-sm">
                    <div className="max-w-[1140px] mx-auto px-4 sm:px-6 flex flex-wrap justify-center md:justify-between gap-4 md:gap-6">
                        {[t.trustBar1, t.trustBar2, t.trustBar3, t.trustBar4].map((item, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0, y: 16 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.45, delay: i * 0.08, ease: "easeOut" }}
                                className="flex items-center gap-2.5 text-sm text-text-secondary"
                            >
                                <span className="w-[34px] h-[34px] rounded-[10px] bg-surface border border-overlay/7 flex items-center justify-center text-ember">
                                    {i === 0 && <ShieldIcon />}{i === 1 && <CheckIcon />}{i === 2 && <GlobeIcon />}{i === 3 && <LanguagesIcon />}
                                </span>{item}
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Steps */}
                <section id="how" className="py-16 md:py-24">
                    <div className="max-w-[1140px] mx-auto px-4 sm:px-6">
                        <FadeUp className="max-w-[600px] mb-8 md:mb-12">
                            <Eyebrow className="mb-4">{t.stepsEyebrow}</Eyebrow>
                            <h2 className="font-display font-semibold text-[clamp(1.5rem,3.6vw,2.6rem)] leading-[1.1] tracking-[-0.02em] mb-3">{t.stepsTitle}</h2>
                            <p className="text-text-secondary text-sm md:text-base">{t.stepsSubtitle}</p>
                        </FadeUp>
                        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4 md:gap-5">
                            <motion.div initial={{ opacity: 0, y: 32 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "0px" }} transition={{ duration: 0.55, delay: 0, ease: [0.22, 0.61, 0.36, 1] }}>
                            <GlassCard className="p-6" role="article" aria-label={t.step1Title}>
                                <span className="font-mono text-xs text-ember tracking-[0.2em]">{t.step1Num}</span>
                                <h3 className="font-display font-semibold text-lg mt-3 mb-2">{t.step1Title}</h3>
                                <p className="text-sm text-text-secondary">{t.step1Body}</p>
                                <div className="mt-5 h-24 rounded-xl bg-surface border border-overlay/7 flex items-center justify-center">
                                    <div className="flex flex-col gap-1.5 w-[60%]">
                                        <div className="h-1.5 rounded bg-overlay/12 w-[80%]" /><div className="h-1.5 rounded bg-overlay/12 w-full" /><div className="h-1.5 rounded bg-overlay/12 w-[55%]" /><div className="h-1.5 rounded bg-ember/50 w-[90%]" />
                                    </div>
                                </div>
                            </GlassCard>
                            </motion.div>
                            <motion.div initial={{ opacity: 0, y: 32 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "0px" }} transition={{ duration: 0.55, delay: 0.1, ease: [0.22, 0.61, 0.36, 1] }}>
                            <GlassCard className="p-6" role="article" aria-label={t.step2Title}>
                                <span className="font-mono text-xs text-ember tracking-[0.2em]">{t.step2Num}</span>
                                <h3 className="font-display font-semibold text-lg mt-3 mb-2">{t.step2Title}</h3>
                                <p className="text-sm text-text-secondary">{t.step2Body}</p>
                                <div className="mt-5 h-24 rounded-xl bg-surface border border-overlay/7 flex items-center justify-center">
                                    <div className="flex gap-1.5 items-end h-14">
                                        <div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[38px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[46px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[54px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[30px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[42px]" />
                                    </div>
                                </div>
                            </GlassCard>
                            </motion.div>
                            <motion.div initial={{ opacity: 0, y: 32 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "0px" }} transition={{ duration: 0.55, delay: 0.2, ease: [0.22, 0.61, 0.36, 1] }}>
                            <GlassCard className="p-6" role="article" aria-label={t.step3Title}>
                                <span className="font-mono text-xs text-ember tracking-[0.2em]">{t.step3Num}</span>
                                <h3 className="font-display font-semibold text-lg mt-3 mb-2">{t.step3Title}</h3>
                                <p className="text-sm text-text-secondary">{t.step3Body}</p>
                                <div className="mt-5 h-24 rounded-xl bg-surface border border-overlay/7 flex items-center justify-center gap-2">
                                    <span className="font-mono text-[10px] px-2 py-1 rounded-md border border-overlay/7 text-text-tertiary">{isAr ? "محفوظة" : "Saved"}</span>
                                    <span className="font-mono text-[10px] px-2 py-1 rounded-md border border-ember/40 text-ember">{isAr ? "مفتوحة" : "Opened"}</span>
                                    <span className="font-mono text-[10px] px-2 py-1 rounded-md border border-aura/40 text-aura">{isAr ? "متقدَّم" : "Applied"}</span>
                                </div>
                            </GlassCard>
                            </motion.div>
                        </div>
                    </div>
                </section>

                {/* Phase 4 - Product Window / Command UI */}
                <section id="command" className="py-16 md:py-24 pt-0" aria-labelledby="command-heading">
                    <div className="max-w-[1140px] mx-auto px-4 sm:px-6">
                        <FadeUp className="max-w-[600px] mb-8 md:mb-12">
                            <Eyebrow className="mb-4">{t.cmdEyebrow}</Eyebrow>
                            <h2 id="command-heading" className="font-display font-semibold text-[clamp(1.5rem,3.6vw,2.6rem)] leading-[1.1] tracking-[-0.02em] mb-3">{t.cmdTitle}</h2>
                            <p className="text-text-secondary text-sm md:text-base">{t.cmdSubtitle}</p>
                        </FadeUp>
                        {/* Window Frame */}
                        <FadeUp delay={0.12}>
                        <div className="rounded-rico-lg overflow-hidden border border-overlay/12 shadow-[0_40px_120px_rgba(0,0,0,0.6)]" role="img" aria-label="Rico command center interface preview">
                            {/* Title Bar */}
                            <div className="flex items-center gap-2 px-4 py-3 bg-surface-elevated border-b border-overlay/7">
                                <div className="flex gap-1.5">
                                    <span className="w-2.5 h-2.5 rounded-full bg-overlay/20" /><span className="w-2.5 h-2.5 rounded-full bg-overlay/20" /><span className="w-2.5 h-2.5 rounded-full bg-overlay/20" />
                                </div>
                                <span className="font-mono text-[11.5px] text-text-tertiary ml-2">ricohunt.com / command</span>
                            </div>
                            {/* App Content */}
                            <div className="grid grid-cols-1 md:grid-cols-[64px_1fr] min-h-[440px] bg-void">
                                {/* Rail */}
                                <div className="hidden md:flex border-r border-overlay/7 py-5 flex-col items-center gap-5 bg-void">
                                    <span className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center text-ember bg-ember/10 border border-ember/30"><HomeIcon /></span>
                                    <span className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center text-text-tertiary hover:text-text-secondary transition-colors cursor-pointer"><SearchIcon /></span>
                                    <span className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center text-text-tertiary hover:text-text-secondary transition-colors cursor-pointer"><BookmarkIcon /></span>
                                    <span className="w-[34px] h-[34px] rounded-[10px] flex items-center justify-center text-text-tertiary hover:text-text-secondary transition-colors cursor-pointer"><UserIcon /></span>
                                </div>
                                {/* Chat Area */}
                                <div className="p-6 flex flex-col">
                                    <div className="flex-1 space-y-4 max-w-[560px]">
                                        {/* User Message */}
                                        <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: 0.1 }} className="self-end bg-surface-elevated border border-overlay/7 rounded-[14px] rounded-br-[5px] px-4 py-3 text-sm max-w-[90%] md:max-w-[78%] ms-auto">
                                            {t.chatMsg1}
                                        </motion.div>
                                        {/* Rico Response */}
                                        <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: 0.3 }} className="self-start bg-gradient-to-br from-ember/13 to-ember/5 border border-ember/20 rounded-[14px] rounded-bl-[5px] px-4 py-3 text-sm max-w-[90%] md:max-w-[78%]">
                                            <div className="flex items-center gap-2 mb-2 font-mono text-[10.5px] uppercase tracking-[0.16em] text-ember">
                                                <Aura size="sm" variant="ember" animate={false} aria-hidden="true" />
                                                <span>Rico</span>
                                            </div>
                                            {t.chatMsg2}
                                        </motion.div>
                                        {/* User Follow-up */}
                                        <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: 0.5 }} className="self-end bg-surface-elevated border border-overlay/7 rounded-[14px] rounded-br-[5px] px-4 py-3 text-sm max-w-[90%] md:max-w-[78%] ms-auto">
                                            {t.chatMsg3}
                                        </motion.div>
                                    </div>
                                    {/* Input */}
                                    <div className="mt-5 flex items-center gap-3 p-3 rounded-xl bg-void border border-overlay/12 max-w-[560px]">
                                        <Aura size="sm" variant="ember" animate={false} aria-hidden="true" />
                                        <span className="text-sm text-text-tertiary flex-1">{t.chatInput}</span>
                                        <span className="w-8 h-8 rounded-lg bg-ember flex items-center justify-center text-void">
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        </FadeUp>
                    </div>
                </section>

                {/* Phase 4 - Dashboard Preview */}
                <section className="py-16 md:py-24 pt-0" aria-labelledby="dashboard-heading">
                    <div className="max-w-[1140px] mx-auto px-4 sm:px-6">
                        <FadeUp className="max-w-[600px] mb-8 md:mb-12">
                            <Eyebrow className="mb-4">{t.dashEyebrow}</Eyebrow>
                            <h2 id="dashboard-heading" className="font-display font-semibold text-[clamp(1.5rem,3.6vw,2.6rem)] leading-[1.1] tracking-[-0.02em] mb-3">{t.dashTitle}</h2>
                            <p className="text-text-secondary text-sm md:text-base">{t.dashSubtitle}</p>
                        </FadeUp>
                        <GlassCard className="p-6 md:p-8 overflow-x-auto">
                            <div className="min-w-[600px]">
                                {/* Dashboard Header */}
                                <div className="flex items-center justify-between mb-6 pb-4 border-b border-overlay/7">
                                    <div className="flex items-center gap-3">
                                        <span className="w-10 h-10 rounded-xl bg-ember/10 border border-ember/30 flex items-center justify-center text-ember"><BarChartIcon /></span>
                                        <div>
                                            <p className="font-display font-semibold">{isAr ? "نظرة عامة" : "Overview"}</p>
                                            <p className="text-xs text-text-tertiary">{isAr ? "٣ وظائف نشطة · آخر تحديث: منذ ٢ ساعة" : "3 active jobs · Last updated: 2 hours ago"}</p>
                                        </div>
                                    </div>
                                    <div className="flex gap-2">
                                        <span className="px-3 py-1.5 rounded-lg bg-surface border border-overlay/7 text-xs text-text-secondary">{isAr ? "آخر ٧ أيام" : "Last 7 days"}</span>
                                    </div>
                                </div>
                                {/* Stats Grid */}
                                <div className="grid grid-cols-4 gap-4 mb-6">
                                    <div className="p-4 rounded-xl bg-surface border border-overlay/7">
                                        <p className="text-xs text-text-tertiary mb-1">{isAr ? "محفوظة" : "Saved"}</p>
                                        <p className="font-display text-2xl font-semibold text-text-primary"><CountUp to={12} /></p>
                                    </div>
                                    <div className="p-4 rounded-xl bg-surface border border-overlay/7">
                                        <p className="text-xs text-text-tertiary mb-1">{isAr ? "مفتوحة" : "Opened"}</p>
                                        <p className="font-display text-2xl font-semibold text-ember"><CountUp to={8} /></p>
                                    </div>
                                    <div className="p-4 rounded-xl bg-surface border border-overlay/7">
                                        <p className="text-xs text-text-tertiary mb-1">{isAr ? "متقدم" : "Applied"}</p>
                                        <p className="font-display text-2xl font-semibold text-aura"><CountUp to={5} /></p>
                                    </div>
                                    <div className="p-4 rounded-xl bg-surface border border-overlay/7">
                                        <p className="text-xs text-text-tertiary mb-1">{isAr ? "مقابلة" : "Interview"}</p>
                                        <p className="font-display text-2xl font-semibold text-aura"><CountUp to={2} /></p>
                                    </div>
                                </div>
                                {/* Job List Preview */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface/50 border border-overlay/7">
                                        <div className="flex items-center gap-3">
                                            <FitRing value={94} size={44} label="" />
                                            <div>
                                                <p className="font-medium text-sm">{isAr ? "مدير امتثال" : "Compliance Manager"}</p>
                                                <p className="text-xs text-text-tertiary">{isAr ? "مصرف · دبي" : "Bank · Dubai"}</p>
                                            </div>
                                        </div>
                                        <span className="px-2.5 py-1 rounded-md bg-aura/10 border border-aura/30 text-aura text-xs font-mono">{isAr ? "متقدم" : "Applied"}</span>
                                    </div>
                                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface/50 border border-overlay/7">
                                        <div className="flex items-center gap-3">
                                            <FitRing value={89} size={44} label="" />
                                            <div>
                                                <p className="font-medium text-sm">{isAr ? "محلل مالي" : "Financial Analyst"}</p>
                                                <p className="text-xs text-text-tertiary">{isAr ? "استشارات · أبوظبي" : "Consulting · Abu Dhabi"}</p>
                                            </div>
                                        </div>
                                        <span className="px-2.5 py-1 rounded-md bg-aura/10 border border-aura/30 text-aura text-xs font-mono">{isAr ? "مقابلة" : "Interview"}</span>
                                    </div>
                                </div>
                            </div>
                        </GlassCard>
                    </div>
                </section>

                {/* Phase 4 - Pricing */}
                <section id="pricing" className="py-16 md:py-24 pt-0" aria-labelledby="pricing-heading">
                    <div className="max-w-[1140px] mx-auto px-4 sm:px-6">
                        <FadeUp className="max-w-[600px] mb-8 md:mb-12 md:mx-auto md:text-center">
                            <Eyebrow className="mb-4 md:justify-center">{t.pricingEyebrow}</Eyebrow>
                            <h2 id="pricing-heading" className="font-display font-semibold text-[clamp(1.5rem,3.6vw,2.6rem)] leading-[1.1] tracking-[-0.02em] mb-3">{t.pricingTitle}</h2>
                        </FadeUp>
                        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4 md:gap-5">
                            {/* Free */}
                            <motion.div initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "0px" }} transition={{ duration: 0.5, delay: 0, ease: [0.22, 0.61, 0.36, 1] }}>
                            <GlassCard className="p-6 flex flex-col">
                                <div className="mb-6">
                                    <p className="font-mono text-xs uppercase tracking-[0.16em] text-text-tertiary">{t.freeName}</p>
                                    <p className="font-display text-3xl font-semibold mt-2">{t.freePrice}</p>
                                </div>
                                <ul className="space-y-3 mb-8 flex-1">
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.freeF1}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.freeF2}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.freeF3}</li>
                                </ul>
                                <Link href="/signup"><RicoButton variant="ghost" size="md" className="w-full">{t.startFree}</RicoButton></Link>
                            </GlassCard>
                            </motion.div>
                            {/* Pro - Featured */}
                            <motion.div initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "0px" }} transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 0.61, 0.36, 1] }}>
                            <GlassCard className="p-6 flex flex-col relative border-ember/30">
                                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-ember text-void text-xs font-mono font-semibold">{t.popular}</span>
                                <div className="mb-6">
                                    <p className="font-mono text-xs uppercase tracking-[0.16em] text-ember">{t.proName}</p>
                                    <p className="font-display text-3xl font-semibold mt-2">{t.proPrice}<span className="text-base font-normal text-text-tertiary">/mo</span></p>
                                </div>
                                <ul className="space-y-3 mb-8 flex-1">
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.proF1}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.proF2}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.proF3}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.proF4}</li>
                                </ul>
                                <Link href="/subscription"><RicoButton variant="primary" size="md" className="w-full">{t.proName}</RicoButton></Link>
                            </GlassCard>
                            </motion.div>
                            {/* Premium */}
                            <motion.div initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "0px" }} transition={{ duration: 0.5, delay: 0.2, ease: [0.22, 0.61, 0.36, 1] }}>
                            <GlassCard className="p-6 flex flex-col">
                                <div className="mb-6">
                                    <p className="font-mono text-xs uppercase tracking-[0.16em] text-text-tertiary">{t.premiumName}</p>
                                    <p className="font-display text-3xl font-semibold mt-2">{t.premiumPrice}<span className="text-base font-normal text-text-tertiary">/mo</span></p>
                                </div>
                                <ul className="space-y-3 mb-8 flex-1">
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.premiumF1}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.premiumF2}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.premiumF3}</li>
                                    <li className="flex items-center gap-2 text-sm text-text-secondary"><CheckIcon />{t.premiumF4}</li>
                                </ul>
                                <Link href="/subscription"><RicoButton variant="ghost" size="md" className="w-full">{t.premiumName}</RicoButton></Link>
                            </GlassCard>
                            </motion.div>
                        </div>
                        <p className="text-center text-sm text-text-tertiary mt-6">{t.cancelAnytime}</p>
                    </div>
                </section>

                {/* Phase 5 - Credibility */}
                <section className="py-16 md:py-24 pt-0" aria-labelledby="credibility-heading">
                    <div className="max-w-[1140px] mx-auto px-4 sm:px-6">
                        <FadeUp>
                        <GlassCard className="p-6 md:p-8 lg:p-10">
                            <div className="grid md:grid-cols-2 gap-10 items-center">
                                <div>
                                    <Eyebrow className="mb-4">{t.credEyebrow}</Eyebrow>
                                    <h2 id="credibility-heading" className="font-display font-semibold text-[clamp(1.5rem,3vw,2rem)] leading-[1.15] tracking-[-0.02em] mb-4">{t.credTitle}</h2>
                                    <p className="text-text-secondary mb-6">{t.credSubtitle}</p>
                                    <div className="flex items-center gap-3 p-3 rounded-xl bg-surface border border-overlay/7">
                                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-ember/30 to-ember/10 flex items-center justify-center text-ember font-bold text-lg">RE</div>
                                        <div>
                                            <p className="font-semibold text-sm">{t.founderLabel}</p>
                                            <p className="text-xs text-text-tertiary">{t.founderMeta}</p>
                                        </div>
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    <div className="flex gap-4 p-4 rounded-xl bg-surface border border-overlay/7">
                                        <span className="w-10 h-10 rounded-lg bg-ember/10 border border-ember/30 flex items-center justify-center text-ember flex-shrink-0"><ShieldIcon /></span>
                                        <div>
                                            <p className="font-semibold text-sm mb-1">{t.credPoint1Title}</p>
                                            <p className="text-xs text-text-tertiary">{t.credPoint1Body}</p>
                                        </div>
                                    </div>
                                    <div className="flex gap-4 p-4 rounded-xl bg-surface border border-overlay/7">
                                        <span className="w-10 h-10 rounded-lg bg-aura/10 border border-aura/30 flex items-center justify-center text-aura flex-shrink-0"><LockIcon /></span>
                                        <div>
                                            <p className="font-semibold text-sm mb-1">{t.credPoint2Title}</p>
                                            <p className="text-xs text-text-tertiary">{t.credPoint2Body}</p>
                                        </div>
                                    </div>
                                    <div className="flex gap-4 p-4 rounded-xl bg-surface border border-overlay/7">
                                        <span className="w-10 h-10 rounded-lg bg-ember/10 border border-ember/30 flex items-center justify-center text-ember flex-shrink-0"><LanguagesIcon /></span>
                                        <div>
                                            <p className="font-semibold text-sm mb-1">{t.credPoint3Title}</p>
                                            <p className="text-xs text-text-tertiary">{t.credPoint3Body}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </GlassCard>
                        </FadeUp>
                    </div>
                </section>

                {/* Phase 5 - FAQ */}
                <section id="faq" className="py-16 md:py-24 pt-0" aria-labelledby="faq-heading">
                    <div className="max-w-[720px] mx-auto px-4 sm:px-6">
                        <FadeUp className="mb-8 md:mb-10 text-center">
                            <Eyebrow className="mb-4 justify-center">{t.faqEyebrow}</Eyebrow>
                            <h2 id="faq-heading" className="font-display font-semibold text-[clamp(1.5rem,3.6vw,2.6rem)] leading-[1.1] tracking-[-0.02em]">{t.faqTitle}</h2>
                        </FadeUp>
                        <div className="space-y-3">
                            {[
                                { q: t.faq1Q, a: t.faq1A },
                                { q: t.faq2Q, a: t.faq2A },
                                { q: t.faq3Q, a: t.faq3A },
                                { q: t.faq4Q, a: t.faq4A },
                            ].map((faq, i) => (
                                <GlassCard key={i} className="p-0 overflow-hidden">
                                    <button
                                        className="w-full flex items-center justify-between p-5 text-start"
                                        onClick={() => setOpenFaq(openFaq === i ? null : i)}
                                        aria-expanded={openFaq === i}
                                        aria-controls={`faq-answer-${i}`}
                                    >
                                        <span className="font-display font-semibold text-base">{faq.q}</span>
                                        <span className={`transform transition-transform duration-200 ${openFaq === i ? 'rotate-180' : ''}`}><ChevronDownIcon /></span>
                                    </button>
                                    <AnimatePresence initial={false}>
                                        {openFaq === i && (
                                            <motion.div
                                                id={`faq-answer-${i}`}
                                                key={`faq-answer-${i}`}
                                                initial={{ height: 0, opacity: 0 }}
                                                animate={{ height: "auto", opacity: 1 }}
                                                exit={{ height: 0, opacity: 0 }}
                                                transition={{ duration: 0.3, ease: [0.22, 0.61, 0.36, 1] }}
                                                className="overflow-hidden"
                                            >
                                                <p className="px-5 pb-5 text-sm text-text-secondary">{faq.a}</p>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </GlassCard>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Phase 5 - Final CTA */}
                <section className="py-16 md:py-24" aria-labelledby="final-cta-heading">
                    <FadeUp className="max-w-[600px] mx-auto px-4 sm:px-6 text-center">
                        <div className="mb-6 flex justify-center">
                            <Aura size="md" variant="ember" aria-hidden="true" />
                        </div>
                        <h2 id="final-cta-heading" className="font-display font-semibold text-[clamp(1.7rem,3.6vw,2.6rem)] leading-[1.1] tracking-[-0.02em] mb-4">{t.finalTitle}</h2>
                        <p className="text-text-secondary mb-8">{t.finalSubtitle}</p>
                        <Link href="/upload"><RicoButton variant="primary" size="lg">{t.finalCta}</RicoButton></Link>
                    </FadeUp>
                </section>
            </main>

            {/* Phase 5 - Footer */}
            <footer className="relative z-10 border-t border-overlay/7 py-8 md:py-12" role="contentinfo">
                <div className="max-w-[1140px] mx-auto px-4 sm:px-6">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                        <Link href="/" className="flex items-center gap-2 font-display font-bold text-lg">
                            <RicoLogoMark animate={false} />
                            <span>Rico<span className="text-ember font-bold"> Hunt</span></span>
                        </Link>
                        <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2">
                            <Link href="/about" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{t.footerAbout}</Link>
                            <Link href="/contact" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{t.footerContact}</Link>
                            <Link href="/terms" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{t.footerTerms}</Link>
                            <Link href="/privacy" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{t.footerPrivacy}</Link>
                            <Link href="/refund-policy" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{t.footerRefunds}</Link>
                            <Link href="/faq" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{t.footerFaq}</Link>
                            <a href="https://wa.me/971585989080" target="_blank" rel="noopener noreferrer" className="text-sm text-text-secondary hover:text-text-primary transition-colors">{t.footerWhatsapp}</a>
                        </nav>
                    </div>
                    <div className="mt-8 pt-6 border-t border-overlay/7 text-center">
                        <p className="text-xs text-text-tertiary">{t.footerPowered}</p>
                        <p className="text-xs text-text-tertiary mt-1">{t.footerRights}</p>
                    </div>
                </div>
            </footer>
        </div>
        </MotionConfig>
    );
}

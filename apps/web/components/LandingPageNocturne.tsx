"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { Aura } from "./ui/rico/Aura";
import { Eyebrow } from "./ui/rico/Eyebrow";
import { FitRing } from "./ui/rico/FitRing";
import { GlassCard } from "./ui/rico/GlassCard";
import { RicoButton } from "./ui/rico/RicoButton";

// SVG Icons
const ShieldIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" /></svg>;
const CheckIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" /></svg>;
const GlobeIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15 15 0 010 20M12 2a15 15 0 000 20" /></svg>;
const LanguagesIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8" /></svg>;
const HomeIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12l9-9 9 9M5 10v10h14V10" /></svg>;
const SearchIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>;
const BookmarkIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21l-7-4-7 4V5a2 2 0 012-2h10a2 2 0 012 2z" /></svg>;
const UserIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a6 6 0 0112 0v1" /></svg>;

export default function LandingPageNocturne() {
    const { language, setLanguage } = useLanguage();
    const isAr = language === "ar";

    const t = {
        signIn: isAr ? "تسجيل الدخول" : "Sign in",
        startFree: isAr ? "ابدأ مجاناً" : "Start free",
        langToggle: isAr ? "EN" : "عربي",
        eyebrow: isAr ? "ذكاء وظيفي · الإمارات" : "AI Job Intelligence · UAE",
        headline1: isAr ? "سيرتك الذاتية، مفهومة." : "Your CV, understood.",
        headline2: isAr ? "دورك القادم، موجود." : "Your next role, found.",
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
        stepsTitle: isAr ? "ثلاث خطوات. لا تشويش." : "Three steps. No noise.",
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
            ? "أدوار مرتّبة حسب الملاءمة الحقيقية، كل منها مع نقاط وأسباب."
            : "Roles ranked by genuine fit, each with a score and the reasons behind it.",
        step3Num: "03",
        step3Title: isAr ? "تابع كل خطوة" : "Track every move",
        step3Body: isAr
            ? "المحفوظة والمفتوحة والمتقدَّم إليها — بحثك الكامل في مركز قيادة هادئ."
            : "Saved, opened, applied — your whole search in one calm command center.",
    };

    return (
        <div dir={isAr ? "rtl" : "ltr"} className="relative min-h-screen overflow-x-hidden bg-void text-text-primary">
            {/* Background glows */}
            <div className="fixed inset-0 pointer-events-none z-0" aria-hidden="true">
                <div className="absolute -left-40 -top-40 h-[620px] w-[620px] rounded-full bg-ember/10 blur-[120px]" />
                <div className="absolute -right-40 top-[40%] h-[520px] w-[520px] rounded-full bg-aura/6 blur-[120px]" />
                <div className="absolute bottom-[-160px] left-[30%] h-[520px] w-[520px] rounded-full bg-ember/5 blur-[120px]" />
            </div>

            {/* Header */}
            <header className="sticky top-0 z-50 backdrop-blur-xl bg-void/55 border-b border-overlay/7">
                <div className="max-w-[1140px] mx-auto px-6 h-16 flex items-center justify-between">
                    <Link href="/" className="flex items-center gap-2.5 font-display font-bold text-lg tracking-tight">
                        <span className="flex h-[30px] w-[30px] items-center justify-center rounded-[9px] bg-gradient-to-br from-ember-bright to-ember text-void font-bold text-sm shadow-[0_0_22px_rgba(240,169,74,0.5)]">R</span>
                        <span>Rico<span className="text-ember font-bold"> Hunt</span></span>
                    </Link>
                    <nav className="flex items-center gap-2.5">
                        <button type="button" onClick={() => setLanguage(isAr ? "en" : "ar")} className="font-mono text-xs text-text-secondary border border-overlay/7 px-2.5 py-1.5 rounded-lg hover:text-text-primary hover:border-ember transition-colors bg-transparent">{t.langToggle}</button>
                        <Link href="/login" className="hidden sm:block text-sm text-text-secondary hover:text-text-primary transition-colors">{t.signIn}</Link>
                        <Link href="/signup"><RicoButton variant="primary" size="sm">{t.startFree}</RicoButton></Link>
                    </nav>
                </div>
            </header>

            <main className="relative z-10">
                {/* Hero */}
                <section className="py-[78px] pb-[70px]">
                    <div className="max-w-[1140px] mx-auto px-6 grid lg:grid-cols-[1.05fr_0.95fr] gap-14 items-center">
                        <div>
                            <Eyebrow className="mb-5">{t.eyebrow}</Eyebrow>
                            <h1 className="font-display font-semibold text-[clamp(2.2rem,5.4vw,4rem)] leading-[1.04] tracking-[-0.025em]">
                                {t.headline1}<br /><span className="text-ember">{t.headline2}</span>
                            </h1>
                            <p className="mt-5 max-w-[42ch] text-lg text-text-secondary">{t.subtitle}</p>
                            <div className="mt-8 flex flex-wrap gap-3">
                                <Link href="/upload"><RicoButton variant="primary" size="md">{t.ctaUpload}</RicoButton></Link>
                                <Link href="#how"><RicoButton variant="ghost" size="md">{t.ctaHow}</RicoButton></Link>
                            </div>
                            <div className="mt-7 flex flex-wrap gap-2">
                                {[t.trust1, t.trust2, t.trust3].map((item) => (
                                    <span key={item} className="inline-flex items-center gap-1.5 font-mono text-[11.5px] text-text-secondary border border-overlay/7 rounded-full px-3 py-1.5">
                                        <span className="h-1 w-1 rounded-full bg-aura shadow-[0_0_8px_var(--aura)]" />{item}
                                    </span>
                                ))}
                            </div>
                        </div>
                        <div className="relative">
                            <GlassCard className="p-5 relative overflow-visible">
                                <div className="absolute -top-12 right-4"><Aura size="sm" variant="ember" /></div>
                                <div className="flex items-center gap-2.5 pb-4 mb-4 border-b border-overlay/7">
                                    <div className="w-[30px] h-[30px] rounded-full bg-gradient-to-br from-white via-ember-bright to-ember shadow-[0_0_16px_rgba(240,169,74,0.6)] animate-breathe" />
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
                                    <FitRing value={86} size={96} label={isAr ? "ملاءمة" : "Fit"} />
                                </div>
                                <div className="mt-4 pt-3 border-t border-overlay/7 flex items-center justify-between">
                                    <p className="text-xs text-text-tertiary">{isAr ? "التالي: " : "Next: "}<span className="text-text-primary font-medium">{isAr ? "فتح رابط التقديم" : "open apply link"}</span></p>
                                    <RicoButton variant="ghost" size="sm">{t.matchReview}</RicoButton>
                                </div>
                            </GlassCard>
                        </div>
                    </div>
                </section>

                {/* Trust Bar */}
                <div className="border-y border-overlay/7 py-6">
                    <div className="max-w-[1140px] mx-auto px-6 flex flex-wrap justify-between gap-6">
                        {[t.trustBar1, t.trustBar2, t.trustBar3, t.trustBar4].map((item, i) => (
                            <div key={i} className="flex items-center gap-2.5 text-sm text-text-secondary">
                                <span className="w-[34px] h-[34px] rounded-[10px] bg-surface border border-overlay/7 flex items-center justify-center text-ember">
                                    {i === 0 && <ShieldIcon />}{i === 1 && <CheckIcon />}{i === 2 && <GlobeIcon />}{i === 3 && <LanguagesIcon />}
                                </span>{item}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Steps */}
                <section id="how" className="py-24">
                    <div className="max-w-[1140px] mx-auto px-6">
                        <div className="max-w-[600px] mb-12">
                            <Eyebrow className="mb-4">{t.stepsEyebrow}</Eyebrow>
                            <h2 className="font-display font-semibold text-[clamp(1.7rem,3.6vw,2.6rem)] leading-[1.1] tracking-[-0.02em] mb-3">{t.stepsTitle}</h2>
                            <p className="text-text-secondary">{t.stepsSubtitle}</p>
                        </div>
                        <div className="grid md:grid-cols-3 gap-5">
                            <GlassCard className="p-6">
                                <span className="font-mono text-xs text-ember tracking-[0.2em]">{t.step1Num}</span>
                                <h3 className="font-display font-semibold text-lg mt-3 mb-2">{t.step1Title}</h3>
                                <p className="text-sm text-text-secondary">{t.step1Body}</p>
                                <div className="mt-5 h-24 rounded-xl bg-surface border border-overlay/7 flex items-center justify-center">
                                    <div className="flex flex-col gap-1.5 w-[60%]">
                                        <div className="h-1.5 rounded bg-overlay/12 w-[80%]" /><div className="h-1.5 rounded bg-overlay/12 w-full" /><div className="h-1.5 rounded bg-overlay/12 w-[55%]" /><div className="h-1.5 rounded bg-ember/50 w-[90%]" />
                                    </div>
                                </div>
                            </GlassCard>
                            <GlassCard className="p-6">
                                <span className="font-mono text-xs text-ember tracking-[0.2em]">{t.step2Num}</span>
                                <h3 className="font-display font-semibold text-lg mt-3 mb-2">{t.step2Title}</h3>
                                <p className="text-sm text-text-secondary">{t.step2Body}</p>
                                <div className="mt-5 h-24 rounded-xl bg-surface border border-overlay/7 flex items-center justify-center">
                                    <div className="flex gap-1.5 items-end h-14">
                                        <div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[38px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[46px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[54px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[30px]" /><div className="w-3 rounded-t bg-gradient-to-t from-aura-dim to-aura h-[42px]" />
                                    </div>
                                </div>
                            </GlassCard>
                            <GlassCard className="p-6">
                                <span className="font-mono text-xs text-ember tracking-[0.2em]">{t.step3Num}</span>
                                <h3 className="font-display font-semibold text-lg mt-3 mb-2">{t.step3Title}</h3>
                                <p className="text-sm text-text-secondary">{t.step3Body}</p>
                                <div className="mt-5 h-24 rounded-xl bg-surface border border-overlay/7 flex items-center justify-center gap-2">
                                    <span className="font-mono text-[10px] px-2 py-1 rounded-md border border-overlay/7 text-text-tertiary">{isAr ? "محفوظة" : "Saved"}</span>
                                    <span className="font-mono text-[10px] px-2 py-1 rounded-md border border-ember/40 text-ember">{isAr ? "مفتوحة" : "Opened"}</span>
                                    <span className="font-mono text-[10px] px-2 py-1 rounded-md border border-aura/40 text-aura">{isAr ? "متقدَّم" : "Applied"}</span>
                                </div>
                            </GlassCard>
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
}

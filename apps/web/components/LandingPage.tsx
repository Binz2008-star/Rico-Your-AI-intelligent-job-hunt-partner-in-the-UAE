"use client";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { MobileControls } from "@/components/MobileControls";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import { MotionConfig, motion } from "framer-motion";
import Link from "next/link";
import type { ReactNode } from "react";

const intelligenceLoopKeys = [
    "landingIntelligenceCvProfileExtraction",
    "landingIntelligenceRoleIntelligence",
    "landingIntelligenceOpportunityMatching",
    "landingIntelligenceApplicationTracking",
    "landingIntelligenceTelegramAlerts",
];

const howItWorksKeys = [
    {
        eyebrow: "01",
        titleKey: "landingHowItWorks01Title",
        bodyKey: "landingHowItWorks01Body",
    },
    {
        eyebrow: "02",
        titleKey: "landingHowItWorks02Title",
        bodyKey: "landingHowItWorks02Body",
    },
    {
        eyebrow: "03",
        titleKey: "landingHowItWorks03Title",
        bodyKey: "landingHowItWorks03Body",
    },
    {
        eyebrow: "04",
        titleKey: "landingHowItWorks04Title",
        bodyKey: "landingHowItWorks04Body",
    },
];

const memoryItemKeys = [
    "landingMemoryCareerStack",
    "landingMemoryTargetRoles",
    "landingMemoryRecruiterHistory",
    "landingMemoryCompensation",
    "landingMemoryOutcomes",
];

const liveMatchKeys = [
    {
        roleKey: "landingLiveMatch1Role",
        score: "94",
        signalKey: "landingLiveMatch1Signal",
    },
    { roleKey: "landingLiveMatch2Role", score: "89", signalKey: "landingLiveMatch2Signal" },
    {
        roleKey: "landingLiveMatch3Role",
        score: "86",
        signalKey: "landingLiveMatch3Signal",
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
    const { language } = useLanguage();
    const t = useTranslation(language);

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
                        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-magenta to-cyan text-sm font-black shadow-[0_0_28px_rgba(255,45,142,0.28)]">
                            R
                        </span>
                        <span>
                            Rico<span className="text-magenta">.ai</span>
                        </span>
                    </Link>
                    <nav className="flex items-center gap-3">
                        <div className="sm:hidden">
                            <MobileControls />
                        </div>
                        <div className="hidden sm:flex items-center gap-2">
                            <LanguageSwitcher />
                            <ThemeSwitcher />
                        </div>
                        <Link
                            href="/login"
                            className="text-sm text-text-secondary transition-colors hover:text-white hidden sm:block"
                        >
                            {t("login")}
                        </Link>
                        <Link
                            href="/signup"
                            className="rounded-full border border-magenta/40 bg-magenta/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-magenta/25 hidden sm:block"
                        >
                            {t("signUpFree")}
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
                                {t("landingHeroBadge")}
                            </p>
                            <h1 className="font-display text-[clamp(3rem,8vw,6.8rem)] font-semibold leading-[0.95] tracking-normal text-white">
                                {t("landingMainHeroTitle")}{" "}
                                <span className="bg-gradient-to-r from-magenta to-cyan bg-clip-text text-transparent">
                                    {t("landingMainHeroHighlight")}
                                </span>
                            </h1>
                            <p className="mt-7 max-w-2xl text-lg leading-8 text-text-secondary md:text-xl">
                                {t("landingMainHeroBody")}
                            </p>
                            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                                    <Link
                                        href="/upload"
                                        className="inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-7 py-4 text-base font-semibold text-black transition-opacity hover:opacity-90 sm:w-auto"
                                    >
                                        {t("uploadYourCV")}
                                    </Link>
                                </motion.div>
                                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                                    <Link
                                        href="/signup"
                                        className="inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-7 py-4 text-base font-semibold text-white backdrop-blur-xl transition-colors hover:bg-white/[0.08] sm:w-auto"
                                    >
                                        {t("signUpFree")}
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
                                        {t("landingSectionInvisibleIntelligence")}
                                    </p>
                                    <h2 className="mt-2 text-2xl font-semibold text-white">
                                        {t("landingSectionLiveProfileLoop")}
                                    </h2>
                                </div>
                                <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan">
                                    {t("landingLiveProfileOnline")}
                                </span>
                            </div>
                            <div className="space-y-4">
                                {intelligenceLoopKeys.map((key, index) => (
                                    <div
                                        key={key}
                                        className="border-b border-white/5 pb-4 last:border-b-0 last:pb-0"
                                    >
                                        <div className="mb-2 flex items-center justify-between gap-4">
                                            <p className="text-sm font-medium text-white">{t(key)}</p>
                                            <p className="font-mono text-[11px] text-text-tertiary">
                                                {index === 0 ? t("landingLiveProfileReady") : t("landingLiveProfileWatching")}
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
                            eyebrow={t("landingSectionHowRicoWorks")}
                            title={t("landingSectionHowRicoWorksTitle")}
                            body={t("landingSectionHowRicoWorksBody")}
                        />
                        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-2 lg:grid-cols-4">
                            {howItWorksKeys.map((step, index) => (
                                <RicoCardPanel key={step.titleKey} delay={0.08 * index}>
                                    <p className="font-mono text-xs text-cyan">{step.eyebrow}</p>
                                    <h3 className="mt-5 text-xl font-semibold text-white">
                                        {t(step.titleKey)}
                                    </h3>
                                    <p className="mt-4 text-sm leading-6 text-text-secondary">
                                        {t(step.bodyKey)}
                                    </p>
                                </RicoCardPanel>
                            ))}
                        </div>
                    </section>

                    <section className="px-5 py-16 md:px-10 lg:px-16">
                        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
                            <RicoCardPanel>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                                    {t("landingSectionWhatRicoRemembers")}
                                </p>
                                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                                    {t("landingSectionWhatRicoRemembersTitle")}
                                </h2>
                                <p className="mt-5 text-base leading-7 text-text-secondary">
                                    {t("landingSectionWhatRicoRemembersBody")}
                                </p>
                            </RicoCardPanel>
                            <RicoCardPanel delay={0.08}>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    {memoryItemKeys.map((key) => (
                                        <div
                                            key={key}
                                            className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                                        >
                                            <div className="mb-4 h-1 w-10 rounded-full bg-gradient-to-r from-magenta to-cyan" />
                                            <p className="text-sm font-medium text-white">{t(key)}</p>
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
                                            {t("landingSectionOpportunityEngine")}
                                        </p>
                                        <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                                            {t("landingSectionOpportunityEngineTitle")}
                                        </h2>
                                    </div>
                                    <span className="hidden rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta sm:inline-flex">
                                        {t("landingMarketScan")}
                                    </span>
                                </div>
                                <div className="space-y-3">
                                    {liveMatchKeys.map((match) => (
                                        <div
                                            key={match.roleKey}
                                            className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                                        >
                                            <div className="flex items-start justify-between gap-4">
                                                <div>
                                                    <h3 className="text-base font-semibold text-white">
                                                        {t(match.roleKey)}
                                                    </h3>
                                                    <p className="mt-1 text-sm text-text-tertiary">
                                                        {t(match.signalKey)}
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
                                    {t("landingSectionTelegramAlerts")}
                                </p>
                                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                                    {t("landingSectionTelegramAlertsTitle")}
                                </h2>
                                <p className="mt-5 text-base leading-7 text-text-secondary">
                                    {t("landingSectionTelegramAlertsBody")}
                                </p>
                                <div className="mt-8 rounded-lg border border-cyan/[0.18] bg-cyan/10 p-4">
                                    <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan">
                                        {t("landingNextAlert")}
                                    </p>
                                    <p className="mt-3 text-sm leading-6 text-white">
                                        {t("landingNextAlertMessage")}
                                    </p>
                                </div>
                            </RicoCardPanel>
                        </div>
                    </section>

                    <section className="px-5 py-16 md:px-10 lg:px-16">
                        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
                            <RicoCardPanel>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan">
                                    {t("landingSectionYouStayInControl")}
                                </p>
                                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                                    Autonomous intelligence, approval-first action
                                </h2>
                                <p className="mt-5 text-base leading-7 text-text-secondary">
                                    {t("landingSectionYouStayInControlBody")}
                                </p>
                            </RicoCardPanel>
                            <RicoCardPanel delay={0.08}>
                                <div className="grid gap-4 md:grid-cols-3">
                                    {[
                                        t("landingNoSetupWizard"),
                                        t("landingNoEnterpriseForms"),
                                        t("landingNoSilentApplying"),
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
                            eyebrow={t("landingSectionPricing")}
                            title={t("landingSectionPricingTitle")}
                            body={t("landingSectionPricingBody")}
                        />
                        <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-2">
                            <RicoCardPanel
                                delay={0.08}
                                className="border-magenta/30 bg-magenta/[0.03]"
                            >
                                <div className="mb-4 inline-flex rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta">
                                    {t("landingPricingPopular")}
                                </div>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                                    {t("landingPricingPro")}
                                </p>
                                <h3 className="mt-4 text-4xl font-semibold text-white">
                                    {t("landingPricingProPrice")}
                                </h3>
                                <p className="mt-2 text-sm text-text-secondary">{t("landingPricingPerMonth")}</p>
                                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                                    <li>{t("landingPricingProFeature1")}</li>
                                    <li>{t("landingPricingProFeature2")}</li>
                                    <li>{t("landingPricingProFeature3")}</li>
                                    <li>{t("landingPricingProFeature4")}</li>
                                    <li>{t("landingPricingProFeature5")}</li>
                                </ul>
                                <Link
                                    href="/subscription"
                                    className="mt-8 inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-6 py-3 text-sm font-semibold text-black transition-opacity hover:opacity-90"
                                >
                                    {t("landingPricingUpgradeToPro")}
                                </Link>
                            </RicoCardPanel>
                            <RicoCardPanel delay={0.16}>
                                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                                    {t("landingPricingPremium")}
                                </p>
                                <h3 className="mt-4 text-4xl font-semibold text-white">
                                    {t("landingPricingPremiumPrice")}
                                </h3>
                                <p className="mt-2 text-sm text-text-secondary">{t("landingPricingPerMonth")}</p>
                                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                                    <li>{t("landingPricingPremiumFeature1")}</li>
                                    <li>{t("landingPricingPremiumFeature2")}</li>
                                    <li>{t("landingPricingPremiumFeature3")}</li>
                                    <li>{t("landingPricingPremiumFeature4")}</li>
                                    <li>{t("landingPricingPremiumFeature5")}</li>
                                    <li>{t("landingPricingPremiumFeature6")}</li>
                                </ul>
                                <Link
                                    href="/subscription"
                                    className="mt-8 inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/[0.08]"
                                >
                                    {t("landingPricingUpgradeToPremium")}
                                </Link>
                            </RicoCardPanel>
                        </div>
                        <div className="mx-auto mt-6 max-w-5xl">
                            <div className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.03] px-5 py-4">
                                <div>
                                    <span className="text-[13px] font-semibold text-[#c0c0d8]">
                                        {t("landingFreePlanLabel")}
                                    </span>
                                    <span className="ml-3 text-[12px] text-[#5a5a7a]">
                                        {t("landingPricingFreePlanDesc")}
                                    </span>
                                </div>
                                <Link
                                    href="/signup"
                                    className="text-[12px] font-semibold text-[#7b6fff] hover:underline whitespace-nowrap"
                                >
                                    {t("signUpFree")} →
                                </Link>
                            </div>
                        </div>
                    </section>

                    <section className="px-5 pb-20 pt-10 md:px-10 lg:px-16">
                        <RicoCardPanel className="mx-auto max-w-5xl text-center">
                            <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                                {t("landingHeroEyebrow")}
                            </p>
                            <h2 className="mx-auto mt-4 max-w-3xl text-3xl font-semibold text-white md:text-5xl">
                                {t("landingHeroTitle")}
                            </h2>
                            <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-text-secondary">
                                {t("landingHeroBody")}
                            </p>
                            <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
                                <Link
                                    href="/upload"
                                    className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-7 py-4 text-base font-semibold text-black transition-opacity hover:opacity-90"
                                >
                                    {t("uploadYourCV")}
                                </Link>
                                <Link
                                    href="/signup"
                                    className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-7 py-4 text-base font-semibold text-white transition-colors hover:bg-white/[0.08]"
                                >
                                    {t("signUpFree")}
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
                            {t("landingFooterTerms")}
                        </Link>
                        <Link
                            href="/privacy"
                            className="text-xs text-text-tertiary transition-colors hover:text-white"
                        >
                            {t("landingFooterPrivacy")}
                        </Link>
                        <Link
                            href="/refund-policy"
                            className="text-xs text-text-tertiary transition-colors hover:text-white"
                        >
                            {t("landingFooterRefunds")}
                        </Link>
                    </div>
                    <p className="text-xs text-text-tertiary">
                        {t("landingFooterAllRights")}
                    </p>
                </footer>
            </div>
        </MotionConfig>
    );
}

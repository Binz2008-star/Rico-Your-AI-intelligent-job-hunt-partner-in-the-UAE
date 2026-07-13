"use client";

import { AppShell } from "@/components/layout/AppShell";
import { ToastContainer } from "@/components/ui/Toast";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import {
    ApiError,
    createPaddleCheckoutSession,
    createPaddleCustomerPortalSession,
    getMySubscription,
    getSubscriptionPlans,
    logout,
    recordSubscriptionIntent,
    type SubscriptionMeResponse,
    type SubscriptionPlan,
} from "@/lib/api";
import { buildWhatsAppManageUrl, buildWhatsAppUpgradeUrl, isManualBillingMode } from "@/lib/billing";
import { getPaddlePriceId, openPaddleCheckout } from "@/lib/paddle";
import type { TranslationKey } from "@/lib/translations";
import { useTranslation } from "@/lib/translations";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

const SUBSCRIPTION_MAINTENANCE_MODE = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true";
const MANUAL_BILLING = isManualBillingMode();

// Single-plan scope: Rico Monthly only.
const FALLBACK_PLANS: SubscriptionPlan[] = [
    {
        id: "rico_monthly",
        plan: "pro",
        name: "Rico Monthly",
        price_monthly: 21.50,
        currency: "USD",
        description: "Smart AI job hunting for active UAE professionals.",
        features: [
            "Unlimited CV analysis",
            "Smart AI role recommendations",
            "Advanced match scoring",
            "Saved searches",
            "Priority support",
            "Higher daily job limits",
        ],
        entitlements: {
            monthly_ai_message_limit: 300,
            saved_jobs_limit: 100,
            profile_optimization_limit: 20,
            cv_storage_limit: 5,
            other_document_limit: 10,
            premium_recommendations_enabled: false,
            application_automation_enabled: false,
        },
        is_popular: true,
    },
];

const PLAN_TIER: Record<string, number> = { free: 0, pro: 1 };

const PLAN_NAME_KEY: Record<string, TranslationKey> = {
    "Rico Monthly": "planProName",
};

const PLAN_DESC_KEY: Record<string, TranslationKey> = {
    "Smart AI job hunting for active UAE professionals.": "planProDesc",
};

const PLAN_FEATURE_KEY: Record<string, TranslationKey> = {
    "Unlimited CV analysis": "planFeatureUnlimitedCV",
    "Smart AI role recommendations": "planFeatureSmartRec",
    "Advanced match scoring": "planFeatureAdvancedScoring",
    "Saved searches": "planFeatureSavedSearches",
    "Priority support": "planFeaturePrioritySupport",
    "Higher daily job limits": "planFeatureHigherLimits",
};

function PlanCard({
    plan,
    currentPlan,
    isActive,
    isLoggedIn,
    loading,
    subLoading,
    anyCheckoutPending,
    onUpgrade,
    onManage,
    onIntent,
    maintenanceMode,
    manualBilling,
    userEmail,
    t,
}: {
    plan: SubscriptionPlan;
    currentPlan: string | null;
    isActive: boolean;
    isLoggedIn: boolean;
    loading: boolean;
    subLoading: boolean;
    anyCheckoutPending: boolean;
    onUpgrade: (plan: "pro") => void;
    onManage: () => void;
    onIntent: (plan: "pro") => void;
    maintenanceMode: boolean;
    manualBilling: boolean;
    userEmail: string | null;
    t: (key: TranslationKey) => string;
}) {
    const isCurrent = currentPlan === plan.plan && (isActive || manualBilling);
    const isHigherPlan =
        isLoggedIn &&
        (isActive || manualBilling) &&
        (PLAN_TIER[currentPlan ?? ""] ?? -1) > (PLAN_TIER[plan.plan] ?? 0);
    const isProPlan = plan.plan === "pro";

    const localName = PLAN_NAME_KEY[plan.name] ? t(PLAN_NAME_KEY[plan.name]) : plan.name;
    const localDesc = plan.description
        ? (PLAN_DESC_KEY[plan.description] ? t(PLAN_DESC_KEY[plan.description]) : plan.description)
        : undefined;
    const localFeatures = plan.features.map(f => PLAN_FEATURE_KEY[f] ? t(PLAN_FEATURE_KEY[f]) : f);

    return (
        <div
            className={`relative flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border p-6 backdrop-blur-md transition-colors duration-200 ${plan.is_popular
                ? "border-gold/40 bg-surface-elevated/75 shadow-[0_0_40px_rgba(245,166,35,0.08)]"
                : "border-border-soft bg-surface-elevated/65"
                }`}
        >
            {/* Glow */}
            <div
                className={`absolute right-0 top-0 h-28 w-28 rounded-full blur-3xl pointer-events-none ${plan.is_popular ? "bg-gold/10" : "bg-gold/5"
                    }`}
            />

            <div className="relative z-10 flex min-h-7 flex-wrap items-start gap-2">
                {isCurrent && (
                    <span className="rounded-full border border-gold/30 bg-gold/10 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-text-primary">
                        {t('currentPlan')}
                    </span>
                )}
                {plan.is_popular && (
                    <span className="rounded-full border border-gold/35 bg-gold/10 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-text-primary">
                        {t('mostPopular')}
                    </span>
                )}
            </div>

            <div className="relative z-10 mt-4 min-h-[74px]">
                <h2 className="text-[22px] font-bold text-text-primary font-display">
                    {localName}
                </h2>
                {localDesc && (
                    <p className="mt-1 text-[13px] text-text-secondary">{localDesc}</p>
                )}
            </div>

            <div className="relative z-10 mt-5 flex items-baseline gap-1">
                <span className="text-[38px] font-black text-text-primary leading-none">
                    {plan.currency} {plan.price_monthly}
                </span>
                <span className="text-[13px] text-text-secondary font-medium">
                    /mo
                </span>
            </div>

            <ul className="relative z-10 mt-6 flex flex-1 flex-col gap-2.5">
                {localFeatures.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-[13px] text-text-secondary">
                        <span
                            className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-black ring-1 ${isProPlan
                                ? "bg-gold/10 text-text-primary ring-gold/25"
                                : "bg-gold/[0.06] text-text-primary ring-gold/15"
                                }`}
                        >
                            ✓
                        </span>
                        {feature}
                    </li>
                ))}
            </ul>

            <div className="relative z-10 mt-8">
                {maintenanceMode ? (
                    <button
                        type="button"
                        disabled
                        className="min-h-11 w-full rounded-xl border border-rico-amber/25 bg-rico-amber/10 px-4 py-3 text-[13px] font-bold text-text-primary opacity-70"
                    >
                        {t('temporarilyUnavailable')}
                    </button>
                ) : subLoading && isLoggedIn ? (
                    <div className="h-11 w-full rounded-xl border border-border-soft bg-surface-glass animate-pulse" />
                ) : isCurrent ? (
                    <button
                        onClick={onManage}
                        className="min-h-11 w-full rounded-xl border border-gold/25 bg-gold/10 px-4 py-3 text-center text-[13px] font-semibold text-text-primary transition-colors hover:bg-gold/15"
                    >
                        {t('manageSubscription')}
                    </button>
                ) : isHigherPlan ? (
                    <div className="flex min-h-11 w-full items-center justify-center rounded-xl border border-border-soft bg-surface-glass px-4 py-3 text-center text-[13px] font-semibold text-text-secondary cursor-default select-none">
                        ✓ {t('includedInYourPlan')}
                    </div>
                ) : isLoggedIn ? (
                    manualBilling ? (
                        <a
                            href={buildWhatsAppUpgradeUrl(plan.plan, userEmail, plan.price_monthly)}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={() => onIntent(plan.plan)}
                            className={`flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-[13px] font-bold transition-colors ${plan.is_popular
                                ? "bg-gold text-[#0a0a1a] hover:bg-gold-hover shadow-[0_0_20px_rgba(245,166,35,0.3)]"
                                : "border border-gold/30 bg-gold/10 text-text-primary hover:bg-gold/15"
                                }`}
                        >
                            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                            </svg>
                            {t('continueOnWhatsApp')}
                        </a>
                    ) : (
                        <button
                            onClick={() => { onIntent(plan.plan); onUpgrade(plan.plan); }}
                            disabled={anyCheckoutPending}
                            className={`min-h-11 w-full rounded-xl px-4 py-3 text-[13px] font-bold transition-colors disabled:opacity-40 ${plan.is_popular
                                ? "bg-gold text-[#0a0a1a] hover:bg-gold-hover shadow-[0_0_20px_rgba(245,166,35,0.3)]"
                                : "border border-gold/30 bg-gold/10 text-text-primary hover:bg-gold/15"
                                }`}
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    {t('connecting')}
                                </span>
                            ) : (
                                `${t('upgradeTo')} ${localName}`
                            )}
                        </button>
                    )
                ) : (
                    <a
                        href="/login"
                        className={`flex min-h-11 w-full items-center justify-center rounded-xl px-4 py-3 text-center text-[13px] font-bold transition-colors ${plan.is_popular
                            ? "border border-gold/35 bg-gold/10 text-text-primary hover:bg-gold/20"
                            : "border border-gold/25 bg-gold/[0.06] text-text-primary hover:bg-gold/15"
                            }`}
                    >
                        {t('loginToUpgrade')}
                    </a>
                )}
            </div>

            {/* WhatsApp sub-copy in manual mode */}
            {manualBilling && isLoggedIn && !isCurrent && !isHigherPlan && !subLoading && !maintenanceMode && (
                <p className="relative z-10 mt-3 text-center text-[11px] leading-snug text-text-secondary">
                    {t('whatsappPaymentConfirm')}
                    <br />
                    {t('whatsappPaymentUseEmail')}
                </p>
            )}
        </div>
    );
}

function CancelBanner() {
    const params = useSearchParams();
    const router = useRouter();
    const [dismissed, setDismissed] = useState(false);
    const { language } = useLanguage();
    const t = useTranslation(language);

    if (dismissed || params.get("checkout") !== "cancelled") return null;

    return (
        <div className="flex items-start gap-3 rounded-xl border border-rico-amber/35 bg-rico-amber/10 px-5 py-4">
            <span className="text-rico-amber text-[18px] mt-0.5">⚠</span>
            <div>
                <p className="text-[13px] font-semibold text-text-primary">{t('checkoutCancelled')}</p>
                <p className="mt-0.5 text-[12px] text-text-secondary">
                    {t('checkoutCancelledDesc')}
                </p>
            </div>
            <button
                onClick={() => {
                    setDismissed(true);
                    router.replace("/subscription");
                }}
                className="ml-auto text-text-secondary hover:text-text-primary text-[18px] leading-none flex-shrink-0"
                aria-label="Dismiss"
            >
                ×
            </button>
        </div>
    );
}

function FreePlanRow({ currentPlan, isLoggedIn }: { currentPlan: string | null; isLoggedIn: boolean }) {
    const isCurrent = currentPlan === "free";
    const { language } = useLanguage();
    const t = useTranslation(language);
    return (
        <div className="flex flex-col gap-3 rounded-xl border border-border-soft bg-surface/70 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
                <span className="text-[13px] font-semibold text-text-secondary">{t('freePlan')}</span>
                <span className="ms-3 text-[12px] text-text-secondary">
                    {t('freePlanDesc')}
                </span>
            </div>
            <div className="flex flex-wrap items-center gap-3">
                {isCurrent && (
                    <span className="text-[11px] font-bold uppercase tracking-widest text-text-secondary border border-border-soft rounded-full px-3 py-1">
                        {t('current')}
                    </span>
                )}
                {isCurrent && isLoggedIn ? (
                    <a
                        href="/command"
                        className="text-[12px] font-semibold text-gold hover:underline whitespace-nowrap"
                    >
                        {t('openRico')} →
                    </a>
                ) : !isLoggedIn ? (
                    <a
                        href="/signup"
                        className="text-[12px] font-semibold text-gold hover:underline whitespace-nowrap"
                    >
                        {t('signUpFree')} →
                    </a>
                ) : null}
            </div>
        </div>
    );
}

export default function SubscriptionPage() {
    const { user, ready } = useAuth();
    const { toasts, toast } = useToast();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const tRef = useRef(t);
    const maintenanceMode = SUBSCRIPTION_MAINTENANCE_MODE;

    useEffect(() => {
        tRef.current = t;
    }, [t]);

    const localizedFallbackPlans = useMemo((): SubscriptionPlan[] => [
        {
            ...FALLBACK_PLANS[0],
            name: t('planProName'),
            description: t('planProDesc'),
            features: [
                t('planFeatureUnlimitedCV'), t('planFeatureSmartRec'),
                t('planFeatureAdvancedScoring'), t('planFeatureSavedSearches'),
                t('planFeaturePrioritySupport'), t('planFeatureHigherLimits'),
            ],
        },
    ], [language]);

    const [apiPlans, setApiPlans] = useState<SubscriptionPlan[]>([]);
    const plans = maintenanceMode ? localizedFallbackPlans : apiPlans;
    const [sub, setSub] = useState<SubscriptionMeResponse | null>(null);
    const [loadingPlans, setLoadingPlans] = useState(!maintenanceMode);
    const [subLoading, setSubLoading] = useState(false);
    const [planError, setPlanError] = useState(false);
    const [subscriptionError, setSubscriptionError] = useState(false);
    const [checkingOut, setCheckingOut] = useState<"pro" | null>(null);
    const backendMaintenanceSubMessage = t('backendMaintenanceSub');
    const subscriptionCheckoutFailedMessage = t('subscriptionCheckoutFailed');
    const subscriptionPaymentConfiguringMessage = t('subscriptionPaymentConfiguring');
    const subscriptionPortalFailedMessage = t('subscriptionPortalFailed');

    const loadPlans = useCallback(() => {
        if (maintenanceMode) {
            return;
        }
        setLoadingPlans(true);
        setPlanError(false);
        getSubscriptionPlans()
            .then((r) => setApiPlans(r.plans))
            .catch(() => {
                setPlanError(true);
                toast(tRef.current('couldNotLoadPlans'), "error");
            })
            .finally(() => setLoadingPlans(false));
    }, [maintenanceMode, toast]);

    useEffect(() => {
        if (maintenanceMode) return;
        let cancelled = false;
        getSubscriptionPlans()
            .then((r) => {
                if (!cancelled) setApiPlans(r.plans);
            })
            .catch(() => {
                if (cancelled) return;
                setPlanError(true);
                toast(tRef.current('couldNotLoadPlans'), "error");
            })
            .finally(() => {
                if (!cancelled) setLoadingPlans(false);
            });
        return () => {
            cancelled = true;
        };
    }, [maintenanceMode, toast]);

    const userEmail = user?.email ?? null;
    useEffect(() => {
        if (!userEmail || maintenanceMode) return;
        void (async () => {
            setSubLoading(true);
            try {
                const data = await getMySubscription();
                setSub(data);
            } catch {
                setSubscriptionError(true);
                toast(tRef.current('couldNotLoadSubscription'), "error");
            } finally {
                setSubLoading(false);
            }
        })();
    }, [maintenanceMode, toast, userEmail]);

    const handleUpgrade = useCallback(
        async (plan: "pro") => {
            if (maintenanceMode) {
                toast(backendMaintenanceSubMessage, "error");
                return;
            }
            // Safety guard: if env var is missing/wrong and manual mode is active,
            // open WhatsApp directly — never call the Paddle checkout API.
            if (MANUAL_BILLING) {
                const price = plans.find((p) => p.plan === plan)?.price_monthly ?? null;
                window.open(buildWhatsAppUpgradeUrl(plan, userEmail, price), "_blank", "noopener,noreferrer");
                return;
            }
            const priceId = getPaddlePriceId();
            if (!priceId) {
                toast(subscriptionPaymentConfiguringMessage, "error");
                return;
            }
            setCheckingOut(plan);
            try {
                // Server-owned checkout session first — the webhook resolves
                // identity via this record, never via a browser-supplied user_id.
                const session = await createPaddleCheckoutSession(plan, "monthly");
                await openPaddleCheckout(priceId, session.session_token, userEmail, language as "en" | "ar");
            } catch (err) {
                const msg =
                    err instanceof ApiError
                        ? err.message
                        : subscriptionCheckoutFailedMessage;
                toast(msg, "error");
            } finally {
                setCheckingOut(null);
            }
        },
        [backendMaintenanceSubMessage, language, maintenanceMode, plans, subscriptionCheckoutFailedMessage, subscriptionPaymentConfiguringMessage, toast, userEmail]
    );

    const handleIntent = useCallback((plan: "pro") => {
        void recordSubscriptionIntent(plan, MANUAL_BILLING ? "manual" : "paddle", "/subscription");
    }, []);

    const handleManage = useCallback(async () => {
        if (maintenanceMode) {
            toast(backendMaintenanceSubMessage, "error");
            return;
        }
        if (MANUAL_BILLING) {
            // In manual mode direct to WhatsApp for plan changes
            window.open(buildWhatsAppManageUrl(), "_blank", "noopener,noreferrer");
            return;
        }
        try {
            const { portal_url } = await createPaddleCustomerPortalSession();
            window.location.href = portal_url;
        } catch (err) {
            const msg =
                err instanceof ApiError
                    ? err.message
                    : subscriptionPortalFailedMessage;
            toast(msg, "error");
        }
    }, [backendMaintenanceSubMessage, maintenanceMode, subscriptionPortalFailedMessage, toast]);

    const currentPlan = user ? sub?.subscription?.plan ?? null : null;
    const isActive = Boolean(sub?.is_active);
    const isLoggedIn = Boolean(user);
    const router = useRouter();

    const handleLogout = useCallback(async () => {
        try {
            await logout();
        } finally {
            router.push("/login");
        }
    }, [router]);

    return (
        <AppShell
            title={t('subscriptionTitle')}
            subtitle={t('subscriptionSubtitle')}
            sidebarProps={{
                user: user ? { name: user.name ?? undefined, email: user.email } : undefined,
                onLogout: handleLogout,
            }}
        >
            <div
                dir={language === "ar" ? "rtl" : "ltr"}
                className="flex w-full max-w-6xl flex-col gap-6 text-start sm:gap-8"
            >

                {maintenanceMode && (
                    <>
                        <div className="flex items-start gap-3 rounded-xl border border-rico-amber/35 bg-rico-amber/10 px-5 py-4">
                            <span className="text-rico-amber text-[18px] mt-0.5">⚠</span>
                            <div>
                                <p className="text-[13px] font-semibold text-text-primary">{t('backendMaintenanceSub')}</p>
                                <p className="mt-0.5 text-[12px] text-text-secondary">
                                    {t('backendMaintenanceSubDesc')}
                                </p>
                            </div>
                        </div>
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 px-5 py-4">
                            <p className="text-[13px] font-semibold text-text-primary">{t('subscriptionStatusUnavailable')}</p>
                            <p className="mt-1 text-[12px] text-text-secondary">
                                {t('subscriptionStatusUnavailableDesc')}
                            </p>
                        </div>
                    </>
                )}

                {!maintenanceMode && subscriptionError && (
                    <div className="flex flex-col gap-3 rounded-xl border border-rico-red/35 bg-rico-red/10 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-[13px] text-text-primary">{t('couldNotLoadSubscription')}</p>
                        <button
                            type="button"
                            onClick={() => {
                                setSubscriptionError(false);
                                void getMySubscription()
                                    .then(setSub)
                                    .catch(() => setSubscriptionError(true));
                            }}
                            className="rounded-lg border border-rico-red/30 px-3 py-1.5 text-[12px] font-semibold text-text-primary hover:bg-rico-red/10"
                        >
                            {t('retry')}
                        </button>
                    </div>
                )}

                {/* Paddle cancel redirect banner (only relevant in Paddle mode) */}
                {!MANUAL_BILLING && (
                    <Suspense>
                        <CancelBanner />
                    </Suspense>
                )}

                {/* Past-due payment warning */}
                {!maintenanceMode && sub && sub.subscription.subscription_status === "past_due" && (
                    <div className="flex items-start gap-3 rounded-xl border border-rico-red/35 bg-rico-red/10 px-5 py-4">
                        <span className="text-rico-red text-[18px] mt-0.5">⚠</span>
                        <div>
                            <p className="text-[13px] font-semibold text-text-primary">{t('paymentIssue')}</p>
                            <p className="mt-0.5 text-[12px] text-text-secondary">
                                {t('paymentIssueDesc')}
                            </p>
                        </div>
                    </div>
                )}

                {/* Current plan banner for active paid subscribers */}
                {!maintenanceMode && sub && isActive && currentPlan && currentPlan !== "free" && (
                    <div className="flex items-center gap-3 rounded-xl border border-gold/30 bg-gold/10 px-5 py-4">
                        <span className="text-gold text-[20px]">✦</span>
                        <div>
                            <p className="text-[13px] font-semibold text-text-primary">
                                {t('activePlan')} {t('planProName')}
                            </p>
                            {sub.subscription.current_period_end && (
                                <p className="mt-0.5 text-[12px] text-text-secondary">
                                    {sub.subscription.cancel_at
                                        ? `${t('expiresOn')} `
                                        : `${t('renews')} `}
                                    {new Date(
                                        sub.subscription.cancel_at ?? sub.subscription.current_period_end
                                    ).toLocaleDateString("en-AE", {
                                        day: "numeric", month: "long", year: "numeric",
                                    })}
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {/* Plan cards */}
                {loadingPlans ? (
                    <div className="grid gap-5 lg:grid-cols-2">
                        {[0, 1].map((i) => (
                            <div
                                key={i}
                                className="min-h-[520px] rounded-2xl bg-surface-elevated/65 border border-border-soft animate-pulse"
                            />
                        ))}
                    </div>
                ) : planError ? (
                    <div className="flex flex-col gap-3 rounded-xl border border-rico-red/35 bg-rico-red/10 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-[13px] text-text-primary">{t('couldNotLoadPlans')}</p>
                        <button
                            type="button"
                            onClick={loadPlans}
                            className="rounded-lg border border-rico-red/30 px-3 py-1.5 text-[12px] font-semibold text-text-primary hover:bg-rico-red/10"
                        >
                            {t('retry')}
                        </button>
                    </div>
                ) : plans.length > 0 ? (
                    <div className="grid items-stretch gap-5 lg:grid-cols-2">
                        {plans.map((plan) => (
                            <PlanCard
                                key={plan.id}
                                plan={plan}
                                currentPlan={currentPlan}
                                isActive={isActive}
                                isLoggedIn={ready ? isLoggedIn : false}
                                loading={checkingOut === plan.plan}
                                subLoading={subLoading}
                                anyCheckoutPending={checkingOut !== null}
                                onUpgrade={handleUpgrade}
                                onManage={handleManage}
                                onIntent={handleIntent}
                                maintenanceMode={maintenanceMode}
                                manualBilling={MANUAL_BILLING}
                                userEmail={userEmail}
                                t={t}
                            />
                        ))}
                    </div>
                ) : (
                    <p className="text-[13px] text-text-secondary">
                        {t('couldNotLoadPlansRefresh')}
                    </p>
                )}

                {/* Free tier row */}
                <FreePlanRow currentPlan={currentPlan} isLoggedIn={ready ? isLoggedIn : false} />

                {/* FAQ Section */}
                <div className="mt-12">
                    <h3 className="text-[18px] font-semibold text-text-primary mb-6">{t('faqTitle')}</h3>
                    <div className="space-y-4">
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 p-5">
                            <h4 className="text-[14px] font-semibold text-text-primary mb-2">{t('faqHowUpgrade')}</h4>
                            <p className="text-[13px] text-text-secondary">
                                {MANUAL_BILLING
                                    ? t('faqHowUpgradeManual')
                                    : t('faqHowUpgradePaddle')}
                            </p>
                        </div>
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 p-5">
                            <h4 className="text-[14px] font-semibold text-text-primary mb-2">{t('faqPaymentMethods')}</h4>
                            <p className="text-[13px] text-text-secondary">
                                {MANUAL_BILLING
                                    ? t('faqPaymentMethodsManual')
                                    : t('faqPaymentMethodsPaddle')}
                            </p>
                        </div>
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 p-5">
                            <h4 className="text-[14px] font-semibold text-text-primary mb-2">{t('faqActivationTime')}</h4>
                            <p className="text-[13px] text-text-secondary">
                                {MANUAL_BILLING
                                    ? t('faqActivationTimeManual')
                                    : t('faqActivationTimePaddle')}
                            </p>
                        </div>
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 p-5">
                            <h4 className="text-[14px] font-semibold text-text-primary mb-2">{t('faqChangeCancel')}</h4>
                            <p className="text-[13px] text-text-secondary">
                                {MANUAL_BILLING
                                    ? t('faqChangeCancelManual')
                                    : t('faqChangeCancelPaddle')}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Footer note */}
                <p className="text-center text-[11px] text-text-secondary">
                    {t('pricesInAED')}
                </p>
            </div>

            <ToastContainer toasts={toasts} />
        </AppShell>
    );
}

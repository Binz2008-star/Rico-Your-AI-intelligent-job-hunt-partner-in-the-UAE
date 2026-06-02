"use client";

import { AppShell } from "@/components/layout/AppShell";
import { ToastContainer } from "@/components/ui/Toast";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import {
    ApiError,
    createCheckoutSession,
    createCustomerPortalSession,
    getMySubscription,
    getSubscriptionPlans,
    logout,
    recordSubscriptionIntent,
    type SubscriptionMeResponse,
    type SubscriptionPlan,
} from "@/lib/api";
import { buildWhatsAppManageUrl, buildWhatsAppUpgradeUrl, isManualBillingMode } from "@/lib/billing";
import { useTranslation } from "@/lib/translations";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

const SUBSCRIPTION_MAINTENANCE_MODE = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true";
const MANUAL_BILLING = isManualBillingMode();

const FALLBACK_PLANS: SubscriptionPlan[] = [
    {
        id: "pro_monthly",
        plan: "pro",
        name: "Pro",
        price_monthly: 29,
        currency: "AED",
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
            premium_recommendations_enabled: false,
            application_automation_enabled: false,
        },
        is_popular: true,
    },
    {
        id: "premium_monthly",
        plan: "premium",
        name: "Premium",
        price_monthly: 49,
        currency: "AED",
        description: "Full automation and premium AI recommendations.",
        features: [
            "Everything in Pro",
            "Auto-apply system",
            "Priority AI ranking",
            "Advanced job automation",
            "Premium job pipelines",
            "Recruiter visibility (coming soon)",
        ],
        entitlements: {
            monthly_ai_message_limit: 1500,
            saved_jobs_limit: null,
            profile_optimization_limit: 100,
            premium_recommendations_enabled: true,
            application_automation_enabled: true,
        },
        is_popular: false,
    },
];

const PLAN_TIER: Record<string, number> = { free: 0, pro: 1, premium: 2 };

const PLAN_NAME_KEY: Record<string, string> = {
    Pro: "planProName",
    Premium: "planPremiumName",
};

const PLAN_DESC_KEY: Record<string, string> = {
    "Smart AI job hunting for active UAE professionals.": "planProDesc",
    "Full automation and premium AI recommendations.": "planPremiumDesc",
};

const PLAN_FEATURE_KEY: Record<string, string> = {
    "Unlimited CV analysis": "planFeatureUnlimitedCV",
    "Smart AI role recommendations": "planFeatureSmartRec",
    "Advanced match scoring": "planFeatureAdvancedScoring",
    "Saved searches": "planFeatureSavedSearches",
    "Priority support": "planFeaturePrioritySupport",
    "Higher daily job limits": "planFeatureHigherLimits",
    "Everything in Pro": "planFeatureEverythingPro",
    "Auto-apply system": "planFeatureAutoApply",
    "Priority AI ranking": "planFeaturePriorityAI",
    "Advanced job automation": "planFeatureAdvancedAuto",
    "Premium job pipelines": "planFeaturePremiumPipelines",
    "Recruiter visibility (coming soon)": "planFeatureRecruiter",
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
    t,
}: {
    plan: SubscriptionPlan;
    currentPlan: string | null;
    isActive: boolean;
    isLoggedIn: boolean;
    loading: boolean;
    subLoading: boolean;
    anyCheckoutPending: boolean;
    onUpgrade: (plan: "pro" | "premium") => void;
    onManage: () => void;
    onIntent: (plan: "pro" | "premium") => void;
    maintenanceMode: boolean;
    manualBilling: boolean;
    t: (key: string) => string;
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
            className={`relative flex flex-col rounded-2xl border p-6 backdrop-blur-md overflow-hidden transition-all ${plan.is_popular
                ? "border-[rgba(255,45,142,0.4)] bg-surface-elevated/60 shadow-[0_0_40px_rgba(255,45,142,0.08)]"
                : "border-border-subtle bg-surface-elevated/40"
                }`}
        >
            {/* Glow */}
            <div
                className={`absolute -top-10 -right-10 w-36 h-36 blur-3xl rounded-full pointer-events-none ${plan.is_popular ? "bg-[#ff2d8e]/8" : "bg-[#5b4fff]/5"
                    }`}
            />

            {/* Popular badge */}
            {plan.is_popular && (
                <div className="absolute top-4 right-4">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] px-2 py-1 rounded-full bg-[rgba(255,45,142,0.15)] text-[#ff2d8e] border border-[rgba(255,45,142,0.3)]">
                        {t('mostPopular')}
                    </span>
                </div>
            )}

            {/* Current plan badge */}
            {isCurrent && (
                <div className="absolute top-4 left-4">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] px-2 py-1 rounded-full bg-[rgba(0,229,255,0.12)] text-[#00e5ff] border border-[rgba(0,229,255,0.3)]">
                        {t('currentPlan')}
                    </span>
                </div>
            )}

            <div className={isCurrent ? "mt-8" : plan.is_popular ? "mt-6" : "mt-0"}>
                <h2 className="text-[22px] font-bold text-text-primary font-['Cabinet_Grotesk',sans-serif]">
                    {localName}
                </h2>
                {localDesc && (
                    <p className="mt-1 text-[13px] text-text-secondary">{localDesc}</p>
                )}
            </div>

            <div className="mt-5 flex items-baseline gap-1">
                <span className="text-[38px] font-black text-text-primary leading-none">
                    {plan.price_monthly}
                </span>
                <span className="text-[13px] text-text-tertiary font-medium">
                    {plan.currency}/mo
                </span>
            </div>

            <ul className="mt-6 flex flex-col gap-2.5 flex-1">
                {localFeatures.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-[13px] text-text-secondary">
                        <span
                            className={`mt-0.5 w-4 h-4 flex-shrink-0 rounded-full flex items-center justify-center text-[10px] font-black ${isProPlan
                                ? "bg-[rgba(255,45,142,0.2)] text-[#ff2d8e]"
                                : "bg-[rgba(91,79,255,0.2)] text-[#7b6fff]"
                                }`}
                        >
                            ✓
                        </span>
                        {feature}
                    </li>
                ))}
            </ul>

            <div className="mt-8">
                {maintenanceMode ? (
                    <button
                        type="button"
                        disabled
                        className="w-full py-3 rounded-xl text-[13px] font-bold transition-all opacity-50 bg-[rgba(245,166,35,0.08)] text-[#f5a623] border border-[rgba(245,166,35,0.25)]"
                    >
                        {t('temporarilyUnavailable')}
                    </button>
                ) : subLoading && isLoggedIn ? (
                    <div className="w-full py-3 rounded-xl bg-surface-glass border border-border-subtle animate-pulse h-[44px]" />
                ) : isCurrent ? (
                    <button
                        onClick={onManage}
                        className="w-full py-3 rounded-xl text-center text-[13px] font-semibold text-[#00e5ff] bg-[rgba(0,229,255,0.06)] border border-[rgba(0,229,255,0.2)] hover:bg-[rgba(0,229,255,0.1)] transition-colors"
                    >
                        {t('manageSubscription')}
                    </button>
                ) : isHigherPlan ? (
                    <div className="w-full py-3 rounded-xl text-center text-[13px] font-semibold text-text-tertiary bg-surface-glass border border-border-subtle cursor-default select-none">
                        ✓ {t('includedInYourPlan')}
                    </div>
                ) : isLoggedIn ? (
                    manualBilling ? (
                        <a
                            href={buildWhatsAppUpgradeUrl(plan.plan)}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={() => onIntent(plan.plan)}
                            className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl text-[13px] font-bold transition-all ${plan.is_popular
                                ? "bg-[#ff2d8e] text-white hover:bg-[#ff4a9e] shadow-[0_0_20px_rgba(255,45,142,0.3)]"
                                : "bg-[rgba(91,79,255,0.15)] text-[#7b6fff] border border-[rgba(91,79,255,0.35)] hover:bg-[rgba(91,79,255,0.25)]"
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
                            className={`w-full py-3 rounded-xl text-[13px] font-bold transition-all disabled:opacity-40 ${plan.is_popular
                                ? "bg-[#ff2d8e] text-white hover:bg-[#ff4a9e] shadow-[0_0_20px_rgba(255,45,142,0.3)]"
                                : "bg-[rgba(91,79,255,0.15)] text-[#7b6fff] border border-[rgba(91,79,255,0.35)] hover:bg-[rgba(91,79,255,0.25)]"
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
                        className={`block w-full py-3 rounded-xl text-center text-[13px] font-bold transition-all ${plan.is_popular
                            ? "bg-[rgba(255,45,142,0.15)] text-[#ff2d8e] border border-[rgba(255,45,142,0.35)] hover:bg-[rgba(255,45,142,0.25)]"
                            : "bg-[rgba(91,79,255,0.1)] text-[#7b6fff] border border-[rgba(91,79,255,0.25)] hover:bg-[rgba(91,79,255,0.2)]"
                            }`}
                    >
                        {t('loginToUpgrade')}
                    </a>
                )}
            </div>

            {/* WhatsApp sub-copy in manual mode */}
            {manualBilling && isLoggedIn && !isCurrent && !isHigherPlan && !subLoading && !maintenanceMode && (
                <p className="mt-3 text-[11px] text-text-tertiary text-center leading-snug">
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
        <div className="flex items-start gap-3 rounded-xl border border-[rgba(245,166,35,0.35)] bg-[rgba(245,166,35,0.08)] px-5 py-4">
            <span className="text-[#f5a623] text-[18px] mt-0.5">⚠</span>
            <div>
                <p className="text-[13px] font-semibold text-[#f5a623]">{t('checkoutCancelled')}</p>
                <p className="mt-0.5 text-[12px] text-[#a08040]">
                    {t('checkoutCancelledDesc')}
                </p>
            </div>
            <button
                onClick={() => {
                    setDismissed(true);
                    router.replace("/subscription");
                }}
                className="ml-auto text-[#a08040] hover:text-[#f5a623] text-[18px] leading-none flex-shrink-0"
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
        <div className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface/60 px-5 py-4">
            <div>
                <span className="text-[13px] font-semibold text-text-secondary">{t('freePlan')}</span>
                <span className="ml-3 text-[12px] text-text-tertiary">
                    {t('freePlanDesc')}
                </span>
            </div>
            <div className="flex items-center gap-3">
                {isCurrent && (
                    <span className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary border border-border-soft rounded-full px-3 py-1">
                        {t('current')}
                    </span>
                )}
                {isCurrent && isLoggedIn ? (
                    <a
                        href="/command"
                        className="text-[12px] font-semibold text-[#7b6fff] hover:underline whitespace-nowrap"
                    >
                        {t('openRico')} →
                    </a>
                ) : !isLoggedIn ? (
                    <a
                        href="/signup"
                        className="text-[12px] font-semibold text-[#7b6fff] hover:underline whitespace-nowrap"
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
    const maintenanceMode = SUBSCRIPTION_MAINTENANCE_MODE;

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
        {
            ...FALLBACK_PLANS[1],
            name: t('planPremiumName'),
            description: t('planPremiumDesc'),
            features: [
                t('planFeatureEverythingPro'), t('planFeatureAutoApply'),
                t('planFeaturePriorityAI'), t('planFeatureAdvancedAuto'),
                t('planFeaturePremiumPipelines'), t('planFeatureRecruiter'),
            ],
        },
    ], [t]);

    const [apiPlans, setApiPlans] = useState<SubscriptionPlan[]>([]);
    const plans = maintenanceMode ? localizedFallbackPlans : apiPlans;
    const [sub, setSub] = useState<SubscriptionMeResponse | null>(null);
    const [loadingPlans, setLoadingPlans] = useState(!maintenanceMode);
    const [subLoading, setSubLoading] = useState(false);
    const [planError, setPlanError] = useState(false);
    const [subscriptionError, setSubscriptionError] = useState(false);
    const [checkingOut, setCheckingOut] = useState<"pro" | "premium" | null>(null);

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
                toast(t('couldNotLoadPlans'), "error");
            })
            .finally(() => setLoadingPlans(false));
    }, [maintenanceMode, t, toast]);

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
                toast(t('couldNotLoadPlans'), "error");
            })
            .finally(() => {
                if (!cancelled) setLoadingPlans(false);
            });
        return () => {
            cancelled = true;
        };
    }, [maintenanceMode, t, toast]);

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
                toast(t('couldNotLoadSubscription'), "error");
            } finally {
                setSubLoading(false);
            }
        })();
    }, [maintenanceMode, t, toast, userEmail]);

    const handleUpgrade = useCallback(
        async (plan: "pro" | "premium") => {
            if (maintenanceMode) {
                toast(t('backendMaintenanceSub'), "error");
                return;
            }
            // In manual mode the CTA is a direct WhatsApp link — this handler is only
            // reached in Stripe mode.
            setCheckingOut(plan);
            try {
                const result = await createCheckoutSession(plan);
                if (result.provider === "mock") {
                    toast(t('subscriptionPaymentConfiguring'), "error");
                } else {
                    window.location.href = result.checkout_url;
                }
            } catch (err) {
                const msg =
                    err instanceof ApiError
                        ? err.message
                        : t('subscriptionCheckoutFailed');
                toast(msg, "error");
            } finally {
                setCheckingOut(null);
            }
        },
        [maintenanceMode, t, toast]
    );

    const handleIntent = useCallback((plan: "pro" | "premium") => {
        void recordSubscriptionIntent(plan, MANUAL_BILLING ? "manual" : "stripe", "/subscription");
    }, []);

    const handleManage = useCallback(async () => {
        if (maintenanceMode) {
            toast(t('backendMaintenanceSub'), "error");
            return;
        }
        if (MANUAL_BILLING) {
            // In manual mode direct to WhatsApp for plan changes
            window.open(buildWhatsAppManageUrl(), "_blank", "noopener,noreferrer");
            return;
        }
        try {
            const result = await createCustomerPortalSession();
            if (result.provider === "mock") {
                toast(t('subscriptionPortalNotConfigured'), "error");
            } else {
                window.location.href = result.checkout_url;
            }
        } catch (err) {
            const msg =
                err instanceof ApiError
                    ? err.message
                    : t('subscriptionPortalFailed');
            toast(msg, "error");
        }
    }, [maintenanceMode, t, toast]);

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
            <div className="max-w-3xl flex flex-col gap-8">

                {maintenanceMode && (
                    <>
                        <div className="flex items-start gap-3 rounded-xl border border-[rgba(245,166,35,0.35)] bg-[rgba(245,166,35,0.08)] px-5 py-4">
                            <span className="text-[#f5a623] text-[18px] mt-0.5">⚠</span>
                            <div>
                                <p className="text-[13px] font-semibold text-[#f5a623]">{t('backendMaintenanceSub')}</p>
                                <p className="mt-0.5 text-[12px] text-[#a08040]">
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
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-[rgba(255,94,91,0.35)] bg-[rgba(255,94,91,0.08)] px-5 py-4">
                        <p className="text-[13px] text-[#ffaaaa]">{t('couldNotLoadSubscription')}</p>
                        <button
                            type="button"
                            onClick={() => {
                                setSubscriptionError(false);
                                void getMySubscription()
                                    .then(setSub)
                                    .catch(() => setSubscriptionError(true));
                            }}
                            className="rounded-lg border border-[rgba(255,94,91,0.3)] px-3 py-1.5 text-[12px] font-semibold text-[#ffaaaa] hover:bg-[rgba(255,94,91,0.12)]"
                        >
                            {t('retry')}
                        </button>
                    </div>
                )}

                {/* Stripe cancel redirect banner (only relevant in Stripe mode) */}
                {!MANUAL_BILLING && (
                    <Suspense>
                        <CancelBanner />
                    </Suspense>
                )}

                {/* Past-due payment warning */}
                {!maintenanceMode && sub && sub.subscription.subscription_status === "past_due" && (
                    <div className="flex items-start gap-3 rounded-xl border border-[rgba(255,94,91,0.35)] bg-[rgba(255,94,91,0.08)] px-5 py-4">
                        <span className="text-[#ff5e5b] text-[18px] mt-0.5">⚠</span>
                        <div>
                            <p className="text-[13px] font-semibold text-[#ff5e5b]">{t('paymentIssue')}</p>
                            <p className="mt-0.5 text-[12px] text-[#ffaaaa]">
                                {t('paymentIssueDesc')}
                            </p>
                        </div>
                    </div>
                )}

                {/* Current plan banner for active paid subscribers */}
                {!maintenanceMode && sub && isActive && currentPlan && currentPlan !== "free" && (
                    <div className="flex items-center gap-3 rounded-xl border border-[rgba(0,229,255,0.3)] bg-[rgba(0,229,255,0.06)] px-5 py-4">
                        <span className="text-[#00e5ff] text-[20px]">✦</span>
                        <div>
                            <p className="text-[13px] font-semibold text-[#00e5ff]">
                                {t('activePlan')} {currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)} Plan
                            </p>
                            {sub.subscription.current_period_end && (
                                <p className="mt-0.5 text-[12px] text-[#5a8a8a]">
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
                    <div className="grid gap-5 sm:grid-cols-2">
                        {[0, 1].map((i) => (
                            <div
                                key={i}
                                className="h-72 rounded-2xl bg-surface-elevated/40 border border-border-subtle animate-pulse"
                            />
                        ))}
                    </div>
                ) : planError ? (
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-[rgba(255,94,91,0.35)] bg-[rgba(255,94,91,0.08)] px-5 py-4">
                        <p className="text-[13px] text-[#ffaaaa]">{t('couldNotLoadPlans')}</p>
                        <button
                            type="button"
                            onClick={loadPlans}
                            className="rounded-lg border border-[rgba(255,94,91,0.3)] px-3 py-1.5 text-[12px] font-semibold text-[#ffaaaa] hover:bg-[rgba(255,94,91,0.12)]"
                        >
                            {t('retry')}
                        </button>
                    </div>
                ) : plans.length > 0 ? (
                    <div className="grid gap-5 sm:grid-cols-2">
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
                                t={t}
                            />
                        ))}
                    </div>
                ) : (
                    <p className="text-[13px] text-text-tertiary">
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
                            <p className="text-[13px] text-text-tertiary">
                                {MANUAL_BILLING
                                    ? t('faqHowUpgradeManual')
                                    : t('faqHowUpgradeStripe')}
                            </p>
                        </div>
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 p-5">
                            <h4 className="text-[14px] font-semibold text-text-primary mb-2">{t('faqPaymentMethods')}</h4>
                            <p className="text-[13px] text-text-tertiary">
                                {MANUAL_BILLING
                                    ? t('faqPaymentMethodsManual')
                                    : t('faqPaymentMethodsStripe')}
                            </p>
                        </div>
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 p-5">
                            <h4 className="text-[14px] font-semibold text-text-primary mb-2">{t('faqActivationTime')}</h4>
                            <p className="text-[13px] text-text-tertiary">
                                {MANUAL_BILLING
                                    ? t('faqActivationTimeManual')
                                    : t('faqActivationTimeStripe')}
                            </p>
                        </div>
                        <div className="rounded-xl border border-border-subtle bg-surface-elevated/40 p-5">
                            <h4 className="text-[14px] font-semibold text-text-primary mb-2">{t('faqChangeCancel')}</h4>
                            <p className="text-[13px] text-text-tertiary">
                                {MANUAL_BILLING
                                    ? t('faqChangeCancelManual')
                                    : t('faqChangeCancelStripe')}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Footer note */}
                <p className="text-[11px] text-text-tertiary text-center">
                    {t('pricesInAED')}
                </p>
            </div>

            <ToastContainer toasts={toasts} />
        </AppShell>
    );
}

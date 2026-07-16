"use client";

/**
 * SubscriptionAtelier — the billing/plan page rendered inside WorkspaceShell.
 *
 * Mirrors all logic from the legacy AppShell SubscriptionPage:
 *  - single Rico Monthly plan
 *  - server-created Paddle checkout session (session_token → customData.checkout_session_id)
 *  - customer portal redirect
 *  - EN/AR + RTL
 *  - maintenance mode banner
 *  - cancel-redirect banner
 *
 * Paddle error callback: openPaddleCheckout now returns a Promise that rejects
 * on checkout.error, so the user sees a Rico toast ("Something went wrong: <detail>")
 * rather than the Paddle error overlay.
 */

import { ToastContainer } from "@/components/ui/Toast";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useToast } from "@/hooks/useToast";
import {
    ApiError,
    createPaddleCheckoutSession,
    createPaddleCustomerPortalSession,
    getMySubscription,
    getSubscriptionPlans,
    recordSubscriptionIntent,
    type SubscriptionMeResponse,
    type SubscriptionPlan,
} from "@/lib/api";
import type { StoredUser } from "@/lib/auth";
import { buildWhatsAppManageUrl, buildWhatsAppUpgradeUrl, isManualBillingMode } from "@/lib/billing";
import { getPaddlePriceId, openPaddleCheckout } from "@/lib/paddle";
import type { TranslationKey } from "@/lib/translations";
import { useTranslation } from "@/lib/translations";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

const SUBSCRIPTION_MAINTENANCE_MODE = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true";
const MANUAL_BILLING = isManualBillingMode();

const FALLBACK_PLANS: SubscriptionPlan[] = [
    {
        id: "rico_monthly",
        plan: "pro",
        name: "Rico Monthly",
        price_monthly: 21.50,
        currency: "USD",
        description: "Smart AI job hunting for active UAE professionals.",
        // Must match src/subscription_plans.py RICO_MONTHLY_PLAN.features (issue #1067).
        features: [
            "300 AI messages per month",
            "20 CV & profile optimizations per month",
            "Smart AI role recommendations",
            "Advanced match scoring",
            "Saved searches",
            "Priority support",
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

// Keys MUST equal the backend feature strings (src/subscription_plans.py) so
// API-returned plans localize correctly (issue #1067).
const PLAN_FEATURE_KEY: Record<string, TranslationKey> = {
    "300 AI messages per month": "planFeatureAiMessages",
    "20 CV & profile optimizations per month": "planFeatureCvAnalysis",
    "Smart AI role recommendations": "planFeatureSmartRec",
    "Advanced match scoring": "planFeatureAdvancedScoring",
    "Saved searches": "planFeatureSavedSearches",
    "Priority support": "planFeaturePrioritySupport",
};

// ── Internal sub-components ───────────────────────────────────────────────────

function CancelBannerInner() {
    const params = useSearchParams();
    const router = useRouter();
    const [dismissed, setDismissed] = useState(false);
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();

    if (dismissed || params.get("checkout") !== "cancelled") return null;

    return (
        <div
            style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "0.75rem",
                borderRadius: 10,
                border: "1px solid rgba(198,73,46,0.30)",
                background: "rgba(198,73,46,0.07)",
                padding: "0.875rem 1.25rem",
            }}
        >
            <span style={{ color: c.red, fontSize: "1.1rem", flexShrink: 0, marginTop: 2 }}>⚠</span>
            <div style={{ flex: 1 }}>
                <p style={{ margin: 0, fontSize: "0.82rem", fontWeight: 600, color: c.ink }}>
                    {t("checkoutCancelled")}
                </p>
                <p style={{ margin: "0.25rem 0 0", fontSize: "0.78rem", color: c.ink70 }}>
                    {t("checkoutCancelledDesc")}
                </p>
            </div>
            <button
                type="button"
                onClick={() => { setDismissed(true); router.replace("/subscription"); }}
                style={{ background: "transparent", border: "none", color: c.ink40, fontSize: "1.1rem", cursor: "pointer", flexShrink: 0, lineHeight: 1 }}
                aria-label="Dismiss"
            >
                ×
            </button>
        </div>
    );
}

function CancelBanner() {
    return (
        <Suspense>
            <CancelBannerInner />
        </Suspense>
    );
}

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
    c,
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
    c: ReturnType<typeof useWorkspaceTheme>;
}) {
    const isCurrent = currentPlan === plan.plan && (isActive || manualBilling);
    const isHigherPlan =
        isLoggedIn &&
        (isActive || manualBilling) &&
        (PLAN_TIER[currentPlan ?? ""] ?? -1) > (PLAN_TIER[plan.plan] ?? 0);

    const localName = PLAN_NAME_KEY[plan.name] ? t(PLAN_NAME_KEY[plan.name]) : plan.name;
    const localDesc = plan.description
        ? (PLAN_DESC_KEY[plan.description] ? t(PLAN_DESC_KEY[plan.description]) : plan.description)
        : undefined;
    const localFeatures = plan.features.map(f => PLAN_FEATURE_KEY[f] ? t(PLAN_FEATURE_KEY[f]) : f);

    return (
        <div
            style={{
                display: "flex",
                flexDirection: "column",
                borderRadius: 14,
                border: `1px solid ${plan.is_popular ? "rgba(198,73,46,0.35)" : c.hair}`,
                background: c.panel,
                padding: "1.5rem",
            }}
        >
            {/* Badges */}
            <div style={{ minHeight: "1.75rem", display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                {isCurrent && (
                    <span style={{ borderRadius: 100, border: `1px solid ${c.hair}`, background: c.activeBg, padding: "0.2rem 0.625rem", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: c.ink70 }}>
                        {t("currentPlan")}
                    </span>
                )}
                {plan.is_popular && (
                    <span style={{ borderRadius: 100, border: "1px solid rgba(198,73,46,0.30)", background: "rgba(198,73,46,0.08)", padding: "0.2rem 0.625rem", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: c.red }}>
                        {t("mostPopular")}
                    </span>
                )}
            </div>

            {/* Name / desc */}
            <div style={{ marginTop: "1rem" }}>
                <h2 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700, color: c.ink }}>{localName}</h2>
                {localDesc && (
                    <p style={{ margin: "0.25rem 0 0", fontSize: "0.8rem", color: c.ink70 }}>{localDesc}</p>
                )}
            </div>

            {/* Price */}
            <div style={{ marginTop: "1.25rem", display: "flex", alignItems: "baseline", gap: "0.25rem" }}>
                <span style={{ fontSize: "2.1rem", fontWeight: 800, color: c.ink, lineHeight: 1 }}>
                    {plan.currency} {plan.price_monthly}
                </span>
                <span style={{ fontSize: "0.78rem", color: c.ink40, fontWeight: 500 }}>/mo</span>
            </div>

            {/* Features */}
            <ul style={{ marginTop: "1.25rem", flex: 1, display: "flex", flexDirection: "column", gap: "0.625rem", listStyle: "none", padding: 0, margin: "1.25rem 0 0" }}>
                {localFeatures.map((feature, i) => (
                    <li key={i} style={{ display: "flex", alignItems: "flex-start", gap: "0.625rem", fontSize: "0.8rem", color: c.ink70 }}>
                        <span style={{ marginTop: 2, flexShrink: 0, width: 16, height: 16, display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", fontSize: "0.6rem", fontWeight: 700, background: "rgba(198,73,46,0.08)", color: c.red, border: "1px solid rgba(198,73,46,0.20)" }}>
                            ✓
                        </span>
                        {feature}
                    </li>
                ))}
            </ul>

            {/* CTA */}
            <div style={{ marginTop: "1.75rem" }}>
                {maintenanceMode ? (
                    <button disabled style={{ width: "100%", padding: "0.625rem 1rem", borderRadius: 8, border: `1px solid ${c.hair}`, background: "transparent", color: c.ink40, fontSize: "0.82rem", fontWeight: 600, cursor: "not-allowed", opacity: 0.6 }}>
                        {t("temporarilyUnavailable")}
                    </button>
                ) : subLoading && isLoggedIn ? (
                    <div style={{ height: 40, borderRadius: 8, border: `1px solid ${c.hair}`, background: c.inset, opacity: 0.6 }} />
                ) : isCurrent ? (
                    <button
                        type="button"
                        onClick={onManage}
                        style={{ width: "100%", padding: "0.625rem 1rem", borderRadius: 8, border: `1px solid ${c.hair}`, background: c.activeBg, color: c.ink, fontSize: "0.82rem", fontWeight: 600, cursor: "pointer" }}
                    >
                        {t("manageSubscription")}
                    </button>
                ) : isHigherPlan ? (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "0.625rem 1rem", borderRadius: 8, border: `1px solid ${c.hair}`, background: c.inset, color: c.ink40, fontSize: "0.82rem", fontWeight: 600 }}>
                        ✓ {t("includedInYourPlan")}
                    </div>
                ) : isLoggedIn ? (
                    manualBilling ? (
                        <a
                            href={buildWhatsAppUpgradeUrl(plan.plan, userEmail, plan.price_monthly)}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={() => onIntent(plan.plan as "pro")}
                            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", width: "100%", padding: "0.625rem 1rem", borderRadius: 8, border: "none", background: plan.is_popular ? c.red : "transparent", borderColor: plan.is_popular ? undefined : c.hair, borderWidth: plan.is_popular ? 0 : 1, borderStyle: "solid", color: plan.is_popular ? "#fff" : c.ink, fontSize: "0.82rem", fontWeight: 700, textDecoration: "none", boxSizing: "border-box" }}
                        >
                            {t("continueOnWhatsApp")}
                        </a>
                    ) : (
                        <button
                            type="button"
                            onClick={() => { onIntent(plan.plan as "pro"); onUpgrade(plan.plan as "pro"); }}
                            disabled={anyCheckoutPending}
                            style={{ width: "100%", padding: "0.625rem 1rem", borderRadius: 8, border: plan.is_popular ? "none" : `1px solid ${c.hair}`, background: plan.is_popular ? c.red : "transparent", color: plan.is_popular ? "#fff" : c.ink, fontSize: "0.82rem", fontWeight: 700, cursor: anyCheckoutPending ? "not-allowed" : "pointer", opacity: anyCheckoutPending ? 0.5 : 1 }}
                        >
                            {loading ? (
                                <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}>
                                    <span style={{ width: 13, height: 13, border: "2px solid currentColor", borderTopColor: "transparent", borderRadius: "50%", display: "inline-block", animation: "atelier-spin 0.7s linear infinite" }} />
                                    {t("connecting")}
                                </span>
                            ) : (
                                `${t("upgradeTo")} ${localName}`
                            )}
                        </button>
                    )
                ) : (
                    <a
                        href="/login"
                        style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", padding: "0.625rem 1rem", borderRadius: 8, border: `1px solid ${c.hair}`, background: c.activeBg, color: c.ink, fontSize: "0.82rem", fontWeight: 700, textDecoration: "none", boxSizing: "border-box" }}
                    >
                        {t("loginToUpgrade")}
                    </a>
                )}
            </div>

            {manualBilling && isLoggedIn && !isCurrent && !isHigherPlan && !subLoading && !maintenanceMode && (
                <p style={{ marginTop: "0.75rem", fontSize: "0.7rem", lineHeight: 1.4, color: c.ink40, textAlign: "center" }}>
                    {t("whatsappPaymentConfirm")}<br />{t("whatsappPaymentUseEmail")}
                </p>
            )}
        </div>
    );
}

function FreePlanRow({
    currentPlan,
    isLoggedIn,
    t,
    c,
}: {
    currentPlan: string | null;
    isLoggedIn: boolean;
    t: (key: TranslationKey) => string;
    c: ReturnType<typeof useWorkspaceTheme>;
}) {
    const isCurrent = currentPlan === "free";
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", borderRadius: 10, border: `1px solid ${c.hair}`, background: c.inset, padding: "1rem 1.25rem" }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "0.75rem" }}>
                <div>
                    <span style={{ fontSize: "0.82rem", fontWeight: 600, color: c.ink70 }}>{t("freePlan")}</span>
                    <span style={{ marginInlineStart: "0.75rem", fontSize: "0.78rem", color: c.ink40 }}>{t("freePlanDesc")}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    {isCurrent && (
                        <span style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: c.ink40, border: `1px solid ${c.hair}`, borderRadius: 100, padding: "0.2rem 0.6rem" }}>
                            {t("current")}
                        </span>
                    )}
                    {isCurrent && isLoggedIn ? (
                        <a href="/command" style={{ fontSize: "0.78rem", fontWeight: 600, color: c.red, textDecoration: "none" }}>
                            {t("openRico")} →
                        </a>
                    ) : !isLoggedIn ? (
                        <a href="/signup" style={{ fontSize: "0.78rem", fontWeight: 600, color: c.red, textDecoration: "none" }}>
                            {t("signUpFree")} →
                        </a>
                    ) : null}
                </div>
            </div>
        </div>
    );
}

function FaqItem({ q, a, c }: { q: string; a: string; c: ReturnType<typeof useWorkspaceTheme> }) {
    return (
        <div style={{ borderRadius: 10, border: `1px solid ${c.hair}`, background: c.panel, padding: "1rem 1.25rem" }}>
            <h4 style={{ margin: 0, fontSize: "0.85rem", fontWeight: 600, color: c.ink }}>{q}</h4>
            <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: c.ink70, lineHeight: 1.5 }}>{a}</p>
        </div>
    );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function SubscriptionAtelier({ user }: { user: StoredUser }) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const tRef = useRef(t);
    const c = useWorkspaceTheme();
    const { toasts, toast } = useToast();
    const maintenanceMode = SUBSCRIPTION_MAINTENANCE_MODE;

    useEffect(() => { tRef.current = t; }, [t]);

    const localizedFallbackPlans = useMemo((): SubscriptionPlan[] => [
        {
            ...FALLBACK_PLANS[0],
            name: t("planProName"),
            description: t("planProDesc"),
            features: [
                t("planFeatureAiMessages"), t("planFeatureCvAnalysis"),
                t("planFeatureSmartRec"), t("planFeatureAdvancedScoring"),
                t("planFeatureSavedSearches"), t("planFeaturePrioritySupport"),
            ],
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
    ], [language]);

    const [apiPlans, setApiPlans] = useState<SubscriptionPlan[]>([]);
    const plans = maintenanceMode ? localizedFallbackPlans : apiPlans;
    const [sub, setSub] = useState<SubscriptionMeResponse | null>(null);
    const [loadingPlans, setLoadingPlans] = useState(!maintenanceMode);
    const [subLoading, setSubLoading] = useState(false);
    const [planError, setPlanError] = useState(false);
    const [subscriptionError, setSubscriptionError] = useState(false);
    const [checkingOut, setCheckingOut] = useState<"pro" | null>(null);

    const backendMaintenanceSubMessage = t("backendMaintenanceSub");
    const subscriptionCheckoutFailedMessage = t("subscriptionCheckoutFailed");
    const subscriptionPaymentConfiguringMessage = t("subscriptionPaymentConfiguring");
    const subscriptionPortalFailedMessage = t("subscriptionPortalFailed");

    const loadPlans = useCallback(() => {
        if (maintenanceMode) return;
        setLoadingPlans(true);
        setPlanError(false);
        getSubscriptionPlans()
            .then((r) => setApiPlans(r.plans))
            .catch(() => { setPlanError(true); toast(tRef.current("couldNotLoadPlans"), "error"); })
            .finally(() => setLoadingPlans(false));
    }, [maintenanceMode, toast]);

    useEffect(() => {
        if (maintenanceMode) return;
        let cancelled = false;
        getSubscriptionPlans()
            .then((r) => { if (!cancelled) setApiPlans(r.plans); })
            .catch(() => {
                if (cancelled) return;
                setPlanError(true);
                toast(tRef.current("couldNotLoadPlans"), "error");
            })
            .finally(() => { if (!cancelled) setLoadingPlans(false); });
        return () => { cancelled = true; };
    }, [maintenanceMode, toast]);

    const userEmail = user.email;

    useEffect(() => {
        if (!userEmail || maintenanceMode) return;
        let cancelled = false;
        void (async () => {
            setSubLoading(true);
            try {
                const data = await getMySubscription();
                if (!cancelled) setSub(data);
            } catch {
                if (!cancelled) {
                    setSubscriptionError(true);
                    toast(tRef.current("couldNotLoadSubscription"), "error");
                }
            } finally {
                if (!cancelled) setSubLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [maintenanceMode, toast, userEmail]);

    const handleUpgrade = useCallback(
        async (plan: "pro") => {
            if (maintenanceMode) { toast(backendMaintenanceSubMessage, "error"); return; }
            if (MANUAL_BILLING) {
                const price = plans.find((p) => p.plan === plan)?.price_monthly ?? null;
                window.open(buildWhatsAppUpgradeUrl(plan, userEmail, price), "_blank", "noopener,noreferrer");
                return;
            }
            const priceId = getPaddlePriceId();
            if (!priceId) { toast(subscriptionPaymentConfiguringMessage, "error"); return; }
            setCheckingOut(plan);
            try {
                const session = await createPaddleCheckoutSession(plan, "monthly");
                await openPaddleCheckout(priceId, session.session_token, userEmail, language as "en" | "ar");
            } catch (err) {
                const msg =
                    err instanceof ApiError
                        ? err.message
                        : (err instanceof Error && err.message)
                            ? err.message
                            : subscriptionCheckoutFailedMessage;
                toast(msg, "error");
            } finally {
                setCheckingOut(null);
            }
        },
        [backendMaintenanceSubMessage, language, maintenanceMode, plans, subscriptionCheckoutFailedMessage, subscriptionPaymentConfiguringMessage, toast, userEmail],
    );

    const handleIntent = useCallback((plan: "pro") => {
        void recordSubscriptionIntent(plan, MANUAL_BILLING ? "manual" : "paddle", "/subscription");
    }, []);

    const handleManage = useCallback(async () => {
        if (maintenanceMode) { toast(backendMaintenanceSubMessage, "error"); return; }
        if (MANUAL_BILLING) {
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
                    : (err instanceof Error && err.message)
                        ? err.message
                        : subscriptionPortalFailedMessage;
            toast(msg, "error");
        }
    }, [backendMaintenanceSubMessage, maintenanceMode, subscriptionPortalFailedMessage, toast]);

    const currentPlan = sub?.subscription?.plan ?? null;
    const isActive = Boolean(sub?.is_active);
    const isLoggedIn = true;
    const dir = language === "ar" ? "rtl" : "ltr";

    return (
        <div dir={dir} style={{ width: "100%", maxWidth: 800 }}>
            <style>{`@keyframes atelier-spin { to { transform: rotate(360deg); } }`}</style>

            {/* Page heading */}
            <div style={{ marginBottom: "1.75rem" }}>
                <h1 style={{ margin: 0, fontSize: "1.35rem", fontWeight: 700, color: c.ink }}>
                    {t("subscriptionTitle")}
                </h1>
                <p style={{ margin: "0.35rem 0 0", fontSize: "0.82rem", color: c.ink70 }}>
                    {t("subscriptionSubtitle")}
                </p>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>

                {/* Maintenance banner */}
                {maintenanceMode && (
                    <>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", borderRadius: 10, border: "1px solid rgba(198,73,46,0.30)", background: "rgba(198,73,46,0.07)", padding: "0.875rem 1.25rem" }}>
                            <span style={{ color: c.red, fontSize: "1.1rem", flexShrink: 0, marginTop: 2 }}>⚠</span>
                            <div>
                                <p style={{ margin: 0, fontSize: "0.82rem", fontWeight: 600, color: c.ink }}>{t("backendMaintenanceSub")}</p>
                                <p style={{ margin: "0.25rem 0 0", fontSize: "0.78rem", color: c.ink70 }}>{t("backendMaintenanceSubDesc")}</p>
                            </div>
                        </div>
                        <div style={{ borderRadius: 10, border: `1px solid ${c.hair}`, background: c.panel, padding: "1rem 1.25rem" }}>
                            <p style={{ margin: 0, fontSize: "0.82rem", fontWeight: 600, color: c.ink }}>{t("subscriptionStatusUnavailable")}</p>
                            <p style={{ margin: "0.25rem 0 0", fontSize: "0.78rem", color: c.ink70 }}>{t("subscriptionStatusUnavailableDesc")}</p>
                        </div>
                    </>
                )}

                {/* Subscription load error */}
                {!maintenanceMode && subscriptionError && (
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "1rem", borderRadius: 10, border: "1px solid rgba(198,73,46,0.30)", background: "rgba(198,73,46,0.07)", padding: "0.875rem 1.25rem" }}>
                        <p style={{ margin: 0, fontSize: "0.82rem", color: c.ink }}>{t("couldNotLoadSubscription")}</p>
                        <button
                            type="button"
                            onClick={() => {
                                setSubscriptionError(false);
                                void getMySubscription().then(setSub).catch(() => setSubscriptionError(true));
                            }}
                            style={{ flexShrink: 0, padding: "0.3rem 0.75rem", fontSize: "0.78rem", fontWeight: 600, color: c.ink, background: "transparent", border: `1px solid ${c.hair}`, borderRadius: 6, cursor: "pointer" }}
                        >
                            {t("retry")}
                        </button>
                    </div>
                )}

                {/* Checkout cancel banner (Paddle mode only) */}
                {!MANUAL_BILLING && <CancelBanner />}

                {/* Past-due warning */}
                {!maintenanceMode && sub && sub.subscription.subscription_status === "past_due" && (
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", borderRadius: 10, border: "1px solid rgba(198,73,46,0.30)", background: "rgba(198,73,46,0.07)", padding: "0.875rem 1.25rem" }}>
                        <span style={{ color: c.red, fontSize: "1.1rem", flexShrink: 0, marginTop: 2 }}>⚠</span>
                        <div>
                            <p style={{ margin: 0, fontSize: "0.82rem", fontWeight: 600, color: c.ink }}>{t("paymentIssue")}</p>
                            <p style={{ margin: "0.25rem 0 0", fontSize: "0.78rem", color: c.ink70 }}>{t("paymentIssueDesc")}</p>
                        </div>
                    </div>
                )}

                {/* Active plan banner */}
                {!maintenanceMode && sub && isActive && currentPlan && currentPlan !== "free" && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", borderRadius: 10, border: `1px solid ${c.hair}`, background: c.activeBg, padding: "0.875rem 1.25rem" }}>
                        <span style={{ color: c.red, fontSize: "1.1rem", flexShrink: 0 }}>✦</span>
                        <div>
                            <p style={{ margin: 0, fontSize: "0.82rem", fontWeight: 600, color: c.ink }}>
                                {t("activePlan")} {t("planProName")}
                            </p>
                            {sub.subscription.current_period_end && (
                                <p style={{ margin: "0.2rem 0 0", fontSize: "0.75rem", color: c.ink70 }}>
                                    {sub.subscription.cancel_at ? `${t("expiresOn")} ` : `${t("renews")} `}
                                    {new Date(
                                        sub.subscription.cancel_at ?? sub.subscription.current_period_end
                                    ).toLocaleDateString("en-AE", { day: "numeric", month: "long", year: "numeric" })}
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {/* Plan cards */}
                {loadingPlans ? (
                    <div style={{ borderRadius: 14, border: `1px solid ${c.hair}`, background: c.panel, minHeight: 320, opacity: 0.6 }} />
                ) : planError ? (
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "1rem", borderRadius: 10, border: "1px solid rgba(198,73,46,0.30)", background: "rgba(198,73,46,0.07)", padding: "0.875rem 1.25rem" }}>
                        <p style={{ margin: 0, fontSize: "0.82rem", color: c.ink }}>{t("couldNotLoadPlans")}</p>
                        <button
                            type="button"
                            onClick={loadPlans}
                            style={{ flexShrink: 0, padding: "0.3rem 0.75rem", fontSize: "0.78rem", fontWeight: 600, color: c.ink, background: "transparent", border: `1px solid ${c.hair}`, borderRadius: 6, cursor: "pointer" }}
                        >
                            {t("retry")}
                        </button>
                    </div>
                ) : plans.length > 0 ? (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1rem" }}>
                        {plans.map((plan) => (
                            <PlanCard
                                key={plan.id}
                                plan={plan}
                                currentPlan={currentPlan}
                                isActive={isActive}
                                isLoggedIn={isLoggedIn}
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
                                c={c}
                            />
                        ))}
                    </div>
                ) : (
                    <p style={{ fontSize: "0.82rem", color: c.ink70 }}>{t("couldNotLoadPlansRefresh")}</p>
                )}

                {/* Free tier row */}
                <FreePlanRow currentPlan={currentPlan} isLoggedIn={isLoggedIn} t={t} c={c} />

                {/* FAQ */}
                <div style={{ marginTop: "1.5rem" }}>
                    <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 600, color: c.ink }}>{t("faqTitle")}</h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
                        <FaqItem q={t("faqHowUpgrade")} a={MANUAL_BILLING ? t("faqHowUpgradeManual") : t("faqHowUpgradePaddle")} c={c} />
                        <FaqItem q={t("faqPaymentMethods")} a={MANUAL_BILLING ? t("faqPaymentMethodsManual") : t("faqPaymentMethodsPaddle")} c={c} />
                        <FaqItem q={t("faqActivationTime")} a={MANUAL_BILLING ? t("faqActivationTimeManual") : t("faqActivationTimePaddle")} c={c} />
                        <FaqItem q={t("faqChangeCancel")} a={MANUAL_BILLING ? t("faqChangeCancelManual") : t("faqChangeCancelPaddle")} c={c} />
                    </div>
                </div>

                {/* Footer note */}
                <p style={{ textAlign: "center", fontSize: "0.7rem", color: c.ink40 }}>{t("pricesInAED")}</p>

            </div>

            <ToastContainer toasts={toasts} />
        </div>
    );
}

"use client";

import { DashboardShell } from "@/components/DashboardShell";
import { ToastContainer } from "@/components/ui/Toast";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import {
    ApiError,
    createCheckoutSession,
    createCustomerPortalSession,
    getMySubscription,
    getSubscriptionPlans,
    type SubscriptionMeResponse,
    type SubscriptionPlan,
} from "@/lib/api";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

const SUBSCRIPTION_MAINTENANCE_MODE = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === 'true';

const FALLBACK_PLANS: SubscriptionPlan[] = [
    {
        id: "pro_monthly",
        plan: "pro",
        name: "Pro",
        price_monthly: 50,
        currency: "AED",
        description: "Higher Rico usage for active job seekers.",
        features: [
            "300 AI messages per month",
            "100 saved jobs",
            "20 profile optimizations per month",
        ],
        entitlements: {
            monthly_ai_message_limit: 300,
            saved_jobs_limit: 100,
            profile_optimization_limit: 20,
            premium_recommendations_enabled: false,
            application_automation_enabled: false,
        },
        is_popular: false,
    },
    {
        id: "premium_monthly",
        plan: "premium",
        name: "Premium",
        price_monthly: 150,
        currency: "AED",
        description: "Full Rico automation and premium recommendations.",
        features: [
            "1500 AI messages per month",
            "Unlimited saved jobs",
            "100 profile optimizations per month",
            "Premium recommendations",
            "Application automation",
        ],
        entitlements: {
            monthly_ai_message_limit: 1500,
            saved_jobs_limit: null,
            profile_optimization_limit: 100,
            premium_recommendations_enabled: true,
            application_automation_enabled: true,
        },
        is_popular: true,
    },
];

function PlanCard({
    plan,
    currentPlan,
    isActive,
    isLoggedIn,
    loading,
    anyCheckoutPending,
    onUpgrade,
    onManage,
    maintenanceMode,
}: {
    plan: SubscriptionPlan;
    currentPlan: string | null;
    isActive: boolean;
    isLoggedIn: boolean;
    loading: boolean;
    anyCheckoutPending: boolean;
    onUpgrade: (plan: "pro" | "premium") => void;
    onManage: () => void;
    maintenanceMode: boolean;
}) {
    const isCurrent = currentPlan === plan.plan && isActive;
    const isProPlan = plan.plan === "pro";

    return (
        <div
            className={`relative flex flex-col rounded-2xl border p-6 backdrop-blur-md overflow-hidden transition-all ${
                plan.is_popular
                    ? "border-[rgba(255,45,142,0.4)] bg-[#13132a]/60 shadow-[0_0_40px_rgba(255,45,142,0.08)]"
                    : "border-white/[0.06] bg-[#13132a]/40"
            }`}
        >
            {/* Glow */}
            <div
                className={`absolute -top-10 -right-10 w-36 h-36 blur-3xl rounded-full pointer-events-none ${
                    plan.is_popular ? "bg-[#ff2d8e]/8" : "bg-[#5b4fff]/5"
                }`}
            />

            {/* Popular badge */}
            {plan.is_popular && (
                <div className="absolute top-4 right-4">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] px-2 py-1 rounded-full bg-[rgba(255,45,142,0.15)] text-[#ff2d8e] border border-[rgba(255,45,142,0.3)]">
                        Most Popular
                    </span>
                </div>
            )}

            {/* Current plan badge */}
            {isCurrent && (
                <div className="absolute top-4 left-4">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] px-2 py-1 rounded-full bg-[rgba(0,229,255,0.12)] text-[#00e5ff] border border-[rgba(0,229,255,0.3)]">
                        Current Plan
                    </span>
                </div>
            )}

            <div className={isCurrent ? "mt-8" : plan.is_popular ? "mt-6" : "mt-0"}>
                <h2 className="text-[22px] font-bold text-white font-['Cabinet_Grotesk',sans-serif]">
                    {plan.name}
                </h2>
                {plan.description && (
                    <p className="mt-1 text-[13px] text-[#8080a0]">{plan.description}</p>
                )}
            </div>

            <div className="mt-5 flex items-baseline gap-1">
                <span className="text-[38px] font-black text-white leading-none">
                    {plan.price_monthly}
                </span>
                <span className="text-[13px] text-[#5a5a7a] font-medium">
                    {plan.currency}/mo
                </span>
            </div>

            <ul className="mt-6 flex flex-col gap-2.5 flex-1">
                {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5 text-[13px] text-[#c0c0d8]">
                        <span
                            className={`mt-0.5 w-4 h-4 flex-shrink-0 rounded-full flex items-center justify-center text-[10px] font-black ${
                                isProPlan
                                    ? "bg-[rgba(91,79,255,0.2)] text-[#7b6fff]"
                                    : "bg-[rgba(255,45,142,0.2)] text-[#ff2d8e]"
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
                        Backend maintenance
                    </button>
                ) : isCurrent ? (
                    <button
                        onClick={onManage}
                        className="w-full py-3 rounded-xl text-center text-[13px] font-semibold text-[#00e5ff] bg-[rgba(0,229,255,0.06)] border border-[rgba(0,229,255,0.2)] hover:bg-[rgba(0,229,255,0.1)] transition-colors"
                    >
                        Manage Subscription
                    </button>
                ) : isLoggedIn ? (
                    <button
                        onClick={() => onUpgrade(plan.plan)}
                        disabled={anyCheckoutPending}
                        className={`w-full py-3 rounded-xl text-[13px] font-bold transition-all disabled:opacity-40 ${
                            plan.is_popular
                                ? "bg-[#ff2d8e] text-white hover:bg-[#ff4a9e] shadow-[0_0_20px_rgba(255,45,142,0.3)]"
                                : "bg-[rgba(91,79,255,0.15)] text-[#7b6fff] border border-[rgba(91,79,255,0.35)] hover:bg-[rgba(91,79,255,0.25)]"
                        }`}
                    >
                        {loading ? (
                            <span className="flex items-center justify-center gap-2">
                                <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                Connecting…
                            </span>
                        ) : (
                            `Upgrade to ${plan.name}`
                        )}
                    </button>
                ) : (
                    <a
                        href="/login"
                        className={`block w-full py-3 rounded-xl text-center text-[13px] font-bold transition-all ${
                            plan.is_popular
                                ? "bg-[rgba(255,45,142,0.15)] text-[#ff2d8e] border border-[rgba(255,45,142,0.35)] hover:bg-[rgba(255,45,142,0.25)]"
                                : "bg-[rgba(91,79,255,0.1)] text-[#7b6fff] border border-[rgba(91,79,255,0.25)] hover:bg-[rgba(91,79,255,0.2)]"
                        }`}
                    >
                        Log in to upgrade
                    </a>
                )}
            </div>
        </div>
    );
}

function CancelBanner() {
  const params = useSearchParams();
  const router = useRouter();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || params.get("checkout") !== "cancelled") return null;

  return (
    <div className="flex items-start gap-3 rounded-xl border border-[rgba(245,166,35,0.35)] bg-[rgba(245,166,35,0.08)] px-5 py-4">
      <span className="text-[#f5a623] text-[18px] mt-0.5">⚠</span>
      <div>
        <p className="text-[13px] font-semibold text-[#f5a623]">Checkout cancelled</p>
        <p className="mt-0.5 text-[12px] text-[#a08040]">
          No payment was made. You can try again whenever you&apos;re ready.
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

function FreePlanRow({ currentPlan }: { currentPlan: string | null }) {
    const isCurrent = currentPlan === "free";
    return (
        <div className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-[#0d0d1f]/60 px-5 py-4">
            <div>
                <span className="text-[13px] font-semibold text-[#c0c0d8]">Free</span>
                <span className="ml-3 text-[12px] text-[#5a5a7a]">
                    50 AI messages · 10 saved jobs · 1 profile optimisation/mo
                </span>
            </div>
            {isCurrent && (
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#5a5a7a] border border-white/[0.08] rounded-full px-3 py-1">
                    Current
                </span>
            )}
        </div>
    );
}

export default function SubscriptionPage() {
    const { user, ready } = useAuth();
    const { toasts, toast } = useToast();
    const maintenanceMode = SUBSCRIPTION_MAINTENANCE_MODE;

    const [plans, setPlans] = useState<SubscriptionPlan[]>(maintenanceMode ? FALLBACK_PLANS : []);
    const [sub, setSub] = useState<SubscriptionMeResponse | null>(null);
    const [loadingPlans, setLoadingPlans] = useState(!maintenanceMode);
    const [planError, setPlanError] = useState(false);
    const [subscriptionError, setSubscriptionError] = useState(false);
    const [checkingOut, setCheckingOut] = useState<"pro" | "premium" | null>(null);
    const [mockNotice, setMockNotice] = useState<"pro" | "premium" | null>(null);

    const loadPlans = useCallback(() => {
        if (maintenanceMode) {
            return;
        }
        setLoadingPlans(true);
        setPlanError(false);
        getSubscriptionPlans()
            .then((r) => setPlans(r.plans))
            .catch(() => {
                setPlanError(true);
                toast("Could not load plans", "error");
            })
            .finally(() => setLoadingPlans(false));
    }, [maintenanceMode, toast]);

    useEffect(() => {
        if (maintenanceMode) return;
        let cancelled = false;
        getSubscriptionPlans()
            .then((r) => {
                if (!cancelled) setPlans(r.plans);
            })
            .catch(() => {
                if (cancelled) return;
                setPlanError(true);
                toast("Could not load plans", "error");
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
        getMySubscription()
            .then(setSub)
            .catch(() => {
                setSubscriptionError(true);
                toast("Could not load subscription status", "error");
            });
    }, [maintenanceMode, toast, userEmail]);

    const handleUpgrade = useCallback(
        async (plan: "pro" | "premium") => {
            if (maintenanceMode) {
                toast("Checkout is paused during backend maintenance", "error");
                return;
            }
            setCheckingOut(plan);
            setMockNotice(null);
            try {
                const result = await createCheckoutSession(plan);
                if (result.provider === "mock") {
                    setMockNotice(plan);
                    if (process.env.NODE_ENV !== "development") {
                        toast("Stripe Checkout is not configured", "error");
                    }
                } else {
                    window.location.href = result.checkout_url;
                }
            } catch (err) {
                const msg =
                    err instanceof ApiError
                        ? err.message
                        : "Checkout failed. Please try again.";
                toast(msg, "error");
            } finally {
                setCheckingOut(null);
            }
        },
        [maintenanceMode, toast]
    );

    const handleManage = useCallback(async () => {
        if (maintenanceMode) {
            toast("Subscription management is paused during backend maintenance", "error");
            return;
        }
        try {
            const result = await createCustomerPortalSession();
            if (result.provider === "mock") {
                toast("Stripe Customer Portal is not configured", "error");
            } else {
                window.location.href = result.checkout_url;
            }
        } catch (err) {
            const msg =
                err instanceof ApiError
                    ? err.message
                    : "Failed to open customer portal. Please try again.";
            toast(msg, "error");
        }
    }, [maintenanceMode, toast]);

    const currentPlan = user ? sub?.subscription?.plan ?? null : null;
    const isActive = Boolean(sub?.is_active);
    const isLoggedIn = Boolean(user);

    return (
        <DashboardShell
            title="Subscription"
            subtitle="Upgrade your Rico AI plan"
        >
            <div className="max-w-3xl flex flex-col gap-8">

                {/* Backend maintenance banner — only shown when NEXT_PUBLIC_MAINTENANCE_MODE=true */}
                {maintenanceMode && (
                    <>
                        <div className="flex items-start gap-3 rounded-xl border border-[rgba(245,166,35,0.35)] bg-[rgba(245,166,35,0.08)] px-5 py-4">
                            <span className="text-[#f5a623] text-[18px] mt-0.5">⚠</span>
                            <div>
                                <p className="text-[13px] font-semibold text-[#f5a623]">Backend maintenance in progress</p>
                                <p className="mt-0.5 text-[12px] text-[#a08040]">
                                    Rico&apos;s backend service is temporarily offline while hosting is being restored.
                                    Subscription, login, Telegram, and Stripe webhook features are paused.
                                    Do not attempt payment validation until the backend is back online.
                                </p>
                            </div>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-[#13132a]/40 px-5 py-4">
                            <p className="text-[13px] font-semibold text-white">Subscription status unavailable</p>
                            <p className="mt-1 text-[12px] text-[#8080a0]">
                                Plan cards below are static reference information. Checkout, current-plan lookup,
                                renewal dates, and portal access are disabled until the backend returns.
                            </p>
                        </div>
                    </>
                )}

                {!maintenanceMode && subscriptionError && (
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-[rgba(255,94,91,0.35)] bg-[rgba(255,94,91,0.08)] px-5 py-4">
                        <p className="text-[13px] text-[#ffaaaa]">Could not load your current subscription status.</p>
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
                            Retry
                        </button>
                    </div>
                )}

                {/* Stripe cancel redirect banner */}
                <Suspense>
                  <CancelBanner />
                </Suspense>

                {/* Mock checkout notice - only show in development */}
                {mockNotice && process.env.NODE_ENV === "development" && (
                    <div className="flex items-start gap-3 rounded-xl border border-[rgba(245,166,35,0.35)] bg-[rgba(245,166,35,0.08)] px-5 py-4">
                        <span className="text-[#f5a623] text-[18px] mt-0.5">⚠</span>
                        <div>
                            <p className="text-[13px] font-semibold text-[#f5a623]">
                                Stripe Checkout not yet active
                            </p>
                            <p className="mt-0.5 text-[12px] text-[#a08040]">
                                The payment provider is running in mock mode. Real checkout
                                sessions will be available once the backend is updated with
                                Stripe credentials. No charge has been made.
                            </p>
                        </div>
                        <button
                            onClick={() => setMockNotice(null)}
                            className="ml-auto text-[#a08040] hover:text-[#f5a623] text-[18px] leading-none flex-shrink-0"
                            aria-label="Dismiss"
                        >
                            ×
                        </button>
                    </div>
                )}

                {/* Past-due payment warning */}
                {!maintenanceMode && sub && sub.subscription.subscription_status === "past_due" && (
                    <div className="flex items-start gap-3 rounded-xl border border-[rgba(255,94,91,0.35)] bg-[rgba(255,94,91,0.08)] px-5 py-4">
                        <span className="text-[#ff5e5b] text-[18px] mt-0.5">⚠</span>
                        <div>
                            <p className="text-[13px] font-semibold text-[#ff5e5b]">Payment failed</p>
                            <p className="mt-0.5 text-[12px] text-[#ffaaaa]">
                                Your last payment did not go through. Please update your payment method to keep your plan active.
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
                                Active {currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)} Plan
                            </p>
                            {sub.subscription.current_period_end && (
                                <p className="mt-0.5 text-[12px] text-[#5a8a8a]">
                                    {sub.subscription.cancel_at
                                        ? "Cancels on "
                                        : "Renews "}
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
                                className="h-72 rounded-2xl bg-[#13132a]/40 border border-white/[0.04] animate-pulse"
                            />
                        ))}
                    </div>
                ) : planError ? (
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-[rgba(255,94,91,0.35)] bg-[rgba(255,94,91,0.08)] px-5 py-4">
                        <p className="text-[13px] text-[#ffaaaa]">Could not load subscription plans.</p>
                        <button
                            type="button"
                            onClick={loadPlans}
                            className="rounded-lg border border-[rgba(255,94,91,0.3)] px-3 py-1.5 text-[12px] font-semibold text-[#ffaaaa] hover:bg-[rgba(255,94,91,0.12)]"
                        >
                            Retry
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
                                anyCheckoutPending={checkingOut !== null}
                                onUpgrade={handleUpgrade}
                                onManage={handleManage}
                                maintenanceMode={maintenanceMode}
                            />
                        ))}
                    </div>
                ) : (
                    <p className="text-[13px] text-[#5a5a7a]">
                        Could not load plans. Please refresh the page.
                    </p>
                )}

                {/* Free tier row */}
                <FreePlanRow currentPlan={currentPlan} />

                {/* FAQ Section */}
                <div className="mt-12">
                    <h3 className="text-[18px] font-semibold text-white mb-6">Frequently Asked Questions</h3>
                    <div className="space-y-4">
                        <div className="rounded-xl border border-white/[0.06] bg-[#13132a]/40 p-5">
                            <h4 className="text-[14px] font-semibold text-white mb-2">How do I cancel my subscription?</h4>
                            <p className="text-[13px] text-[#5a5a7a]">
                                You can cancel or manage your subscription at any time by clicking the &quot;Manage Subscription&quot; button on your active plan. This will take you to the Stripe Customer Portal where you can cancel, change plans, or update payment methods.
                            </p>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-[#13132a]/40 p-5">
                            <h4 className="text-[14px] font-semibold text-white mb-2">What happens when I cancel?</h4>
                            <p className="text-[13px] text-[#5a5a7a]">
                                Your subscription remains active until the end of your current billing period. You&apos;ll continue to have access to all features until then. After cancellation, your account will revert to the Free tier.
                            </p>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-[#13132a]/40 p-5">
                            <h4 className="text-[14px] font-semibold text-white mb-2">Can I change my plan later?</h4>
                            <p className="text-[13px] text-[#5a5a7a]">
                                Yes, you can upgrade or downgrade your plan at any time through the Customer Portal. When upgrading, you&apos;ll be charged the prorated difference immediately. When downgrading, the new rate takes effect at the next billing cycle.
                            </p>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-[#13132a]/40 p-5">
                            <h4 className="text-[14px] font-semibold text-white mb-2">What payment methods do you accept?</h4>
                            <p className="text-[13px] text-[#5a5a7a]">
                                We accept all major credit and debit cards through Stripe. Your payment information is securely processed and never stored on our servers.
                            </p>
                        </div>
                    </div>
                </div>

                {/* Footer note */}
                <p className="text-[11px] text-[#5a5a7a] text-center">
                    Prices in AED. Billed monthly. Cancel any time.
                </p>
            </div>

            <ToastContainer toasts={toasts} />
        </DashboardShell>
    );
}

"use client";
/**
 * PaddleBillingSection
 *
 * Renders the billing section when NEXT_PUBLIC_BILLING_MODE=paddle.
 * Shows current plan, status, renewal/expiry date, and action buttons.
 *
 * SECURITY: PADDLE_API_KEY is never imported here. Checkout is opened via
 * the Paddle.js overlay (client token only). Portal sessions are created
 * server-side via POST /api/v1/billing/customer-portal.
 */

import { useLanguage } from "@/contexts/LanguageContext";
import type { PaddleBillingStatus } from "@/lib/api";
import { createPaddleCheckoutSession, createPaddleCustomerPortalSession, getPaddleBillingStatus } from "@/lib/api";
import { getPaddlePriceId, openPaddleCheckout } from "@/lib/paddle";
import { useTranslation } from "@/lib/translations";
import { useCallback, useEffect, useState } from "react";

interface Props {
    userId: string;
    userEmail?: string | null;
    /** Atelier palette colours — passed from the parent shell */
    colors: {
        ink: string;
        ink70: string;
        ink40: string;
        surface: string;
        red: string;
        borderDefault: string;
    };
}

export function PaddleBillingSection({ userId, userEmail, colors }: Props) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";

    const [status, setStatus] = useState<PaddleBillingStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [portalLoading, setPortalLoading] = useState(false);
    const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

    const fetchStatus = useCallback(async (signal?: AbortSignal) => {
        setLoading(true);
        setError(null);
        try {
            const data = await getPaddleBillingStatus(signal);
            setStatus(data);
        } catch (err: unknown) {
            if (err instanceof Error && err.name === "AbortError") return;
            setError(t("paddleBillingLoadError"));
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        const controller = new AbortController();
        fetchStatus(controller.signal);
        return () => controller.abort();
    }, [fetchStatus]);

    const handlePortal = async () => {
        setPortalLoading(true);
        try {
            const { portal_url } = await createPaddleCustomerPortalSession();
            window.open(portal_url, "_blank", "noopener,noreferrer");
        } catch {
            setError(t("paddlePortalError"));
        } finally {
            setPortalLoading(false);
        }
    };

    const handleCheckout = async () => {
        const priceId = getPaddlePriceId();
        if (!priceId) {
            setError(t("paddleNotConfigured"));
            return;
        }
        setCheckoutLoading("pro_monthly");
        try {
            // Server-owned checkout session first — the webhook resolves
            // identity via this record, never via a browser-supplied user_id.
            const session = await createPaddleCheckoutSession("pro", "monthly");
            await openPaddleCheckout(priceId, session.session_token, userEmail, language as "en" | "ar");
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            setError(msg);
        } finally {
            setCheckoutLoading(null);
        }
    };

    const planLabel = (plan: string) => {
        if (plan === "pro") return t("paddlePlanPro");
        return t("paddlePlanFree");
    };

    const statusLabel = (s: string) => {
        switch (s) {
            case "active": return t("paddleStatusActive");
            case "trialing": return t("paddleStatusTrialing");
            case "past_due": return t("paddleStatusPastDue");
            case "paused": return t("paddlePaused");
            case "canceled": return t("paddleCanceled");
            default: return t("paddleStatusInactive");
        }
    };

    const formatDate = (iso: string | null) => {
        if (!iso) return "—";
        return new Date(iso).toLocaleDateString(isAr ? "ar-AE" : "en-GB", {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
    };

    const isActive = status?.status === "active" || status?.status === "trialing";
    const hasPaidPlan = status?.plan && status.plan !== "free";
    const isCancelScheduled = !!status?.cancel_at && isActive;

    return (
        <div
            style={{
                borderTop: `1px solid ${colors.borderDefault}`,
                paddingTop: "2rem",
                marginTop: "2rem",
                direction: isAr ? "rtl" : "ltr",
            }}
        >
            {/* Section header */}
            <div style={{ marginBottom: "1.25rem" }}>
                <h3
                    style={{
                        fontSize: "0.85rem",
                        fontWeight: 500,
                        letterSpacing: isAr ? "0" : "0.08em",
                        textTransform: isAr ? "none" : "uppercase",
                        color: colors.ink40,
                        margin: 0,
                    }}
                >
                    {t("paddleBillingTitle")}
                </h3>
                <p style={{ fontSize: "0.8rem", color: colors.ink40, margin: "0.25rem 0 0" }}>
                    {t("paddleBillingSubtitle")}
                </p>
            </div>

            {/* Error banner */}
            {error && (
                <div
                    style={{
                        background: "rgba(220,38,38,0.08)",
                        border: "1px solid rgba(220,38,38,0.25)",
                        borderRadius: 6,
                        padding: "0.6rem 0.85rem",
                        color: colors.red,
                        fontSize: "0.82rem",
                        marginBottom: "1rem",
                    }}
                >
                    {error}
                </div>
            )}

            {loading ? (
                <p style={{ fontSize: "0.82rem", color: colors.ink40 }}>{t("loading")}</p>
            ) : (
                <>
                    {/* Current plan row */}
                    <div
                        style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "0.6rem",
                        }}
                    >
                        <span style={{ fontSize: "0.82rem", color: colors.ink70 }}>
                            {t("paddleCurrentPlan")}
                        </span>
                        <span
                            style={{
                                fontSize: "0.85rem",
                                fontWeight: 600,
                                color: hasPaidPlan ? colors.red : colors.ink70,
                            }}
                        >
                            {planLabel(status?.plan ?? "free")}
                        </span>
                    </div>

                    {/* Status row */}
                    {hasPaidPlan && (
                        <div
                            style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "0.6rem",
                            }}
                        >
                            <span style={{ fontSize: "0.82rem", color: colors.ink70 }}>
                                {/* Status label */}
                                {statusLabel(status?.status ?? "inactive")}
                            </span>
                            <span style={{ fontSize: "0.82rem", color: colors.ink40 }}>
                                {isCancelScheduled
                                    ? `${t("paddleCancelScheduled")} ${formatDate(status!.cancel_at)}`
                                    : isActive
                                        ? `${t(status?.canceled_at ? "paddleExpiresOn" : "paddleRenewsOn")} ${formatDate(status!.current_period_end)}`
                                        : null}
                            </span>
                        </div>
                    )}

                    {/* Billing cycle */}
                    {hasPaidPlan && status?.billing_cycle && (
                        <div
                            style={{
                                display: "flex",
                                justifyContent: "space-between",
                                marginBottom: "1rem",
                            }}
                        >
                            <span style={{ fontSize: "0.82rem", color: colors.ink70 }}>
                                {isAr ? "دورة الفوترة" : "Billing cycle"}
                            </span>
                            <span style={{ fontSize: "0.82rem", color: colors.ink40 }}>
                                {status.billing_cycle === "yearly"
                                    ? isAr ? "سنوي" : "Yearly"
                                    : isAr ? "شهري" : "Monthly"}
                            </span>
                        </div>
                    )}

                    {/* Action buttons */}
                    {!hasPaidPlan && (
                        <p
                            style={{
                                fontSize: "0.78rem",
                                color: colors.ink40,
                                margin: "0 0 0.75rem",
                                lineHeight: 1.4,
                            }}
                        >
                            {isAr
                                ? "ريكو الشهرية · الدرهم الإماراتي 79/شهر · يُحسب بالدولار عند الدفع"
                                : "Rico Monthly · AED 79/month · Billed in USD equivalent via Paddle"}
                        </p>
                    )}
                    <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                        {hasPaidPlan ? (
                            <button
                                onClick={handlePortal}
                                disabled={portalLoading}
                                style={{
                                    padding: "0.5rem 1rem",
                                    fontSize: "0.82rem",
                                    borderRadius: 6,
                                    border: `1px solid ${colors.borderDefault}`,
                                    background: "transparent",
                                    color: colors.ink,
                                    cursor: portalLoading ? "not-allowed" : "pointer",
                                    opacity: portalLoading ? 0.6 : 1,
                                }}
                            >
                                {portalLoading
                                    ? t("paddleManageSubscriptionLoading")
                                    : t("paddleManageSubscription")}
                            </button>
                        ) : (
                            <button
                                onClick={() => handleCheckout()}
                                disabled={!!checkoutLoading}
                                style={{
                                    padding: "0.5rem 1rem",
                                    fontSize: "0.82rem",
                                    borderRadius: 6,
                                    border: "none",
                                    background: colors.red,
                                    color: "#fff",
                                    cursor: checkoutLoading ? "not-allowed" : "pointer",
                                    opacity: checkoutLoading ? 0.6 : 1,
                                }}
                            >
                                {checkoutLoading === "pro_monthly"
                                    ? t("paddleCheckoutLoading")
                                    : t("paddleUpgradeMonthly")}
                            </button>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}

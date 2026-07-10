"use client";

import { AtelierAuthShell } from "@/components/auth/AtelierAuthShell";
import { verifyEmail, resendVerification } from "@/lib/api";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import React, { Suspense, useEffect, useState } from "react";

type Status = "loading" | "success" | "error";

function VerifyEmailContent() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const token = searchParams.get("token") ?? "";

    const [status, setStatus] = useState<Status>(() => token ? "loading" : "error");
    const [message, setMessage] = useState(() => token ? "" : t("atlVerifyNoToken"));
    const [resendEmail, setResendEmail] = useState("");
    const [resendLoading, setResendLoading] = useState(false);
    const [resendMessage, setResendMessage] = useState("");

    useEffect(() => {
        if (!token) return;

        verifyEmail(token)
            .then((res) => {
                setStatus("success");
                // Pre-fill email on login page so the user doesn't have to retype it.
                const destination = res?.email
                    ? `/login?email=${encodeURIComponent(res.email)}`
                    : "/login";
                setTimeout(() => router.push(destination), 2000);
            })
            .catch(() => {
                setStatus("error");
                setMessage(t("atlVerifyInvalid"));
            });
    }, [token, router, t]);

    const handleResend = async () => {
        if (!resendEmail) return;
        setResendLoading(true);
        setResendMessage("");
        try {
            await resendVerification(resendEmail);
            setResendMessage(t("verificationEmailSent"));
        } catch {
            setResendMessage(t("couldNotResend"));
        } finally {
            setResendLoading(false);
        }
    };

    if (status === "loading") {
        return (
            <div className="atl-status">
                <span className="atl-status-badge" aria-hidden="true">
                    <span className="atl-spin" />
                </span>
                <div>
                    <h1 className="atl-auth-title">{t("atlVerifyingTitle")}</h1>
                    <p className="atl-auth-sub" style={{ marginBottom: 0 }}>{t("atlVerifyingSub")}</p>
                </div>
            </div>
        );
    }

    if (status === "success") {
        return (
            <div className="atl-status">
                <span className="atl-status-badge" aria-hidden="true">
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 6L9 17l-5-5" />
                    </svg>
                </span>
                <div>
                    <h1 className="atl-auth-title">{t("atlVerifiedTitle")}</h1>
                    <p className="atl-auth-sub" style={{ marginBottom: 0 }}>{t("atlVerifiedSub")}</p>
                </div>
                <div className="atl-auth-foot" style={{ textAlign: "start" }}>
                    <Link href="/login" className="atl-link">{t("atlSignInNow")}</Link>
                </div>
            </div>
        );
    }

    return (
        <div className="atl-status">
            <span className="atl-status-badge is-error" aria-hidden="true">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 8v5M12 16.5h.01" />
                </svg>
            </span>
            <div>
                <h1 className="atl-auth-title">{t("atlVerifyFailedTitle")}</h1>
                <p className="atl-auth-sub" style={{ marginBottom: 0 }}>{message}</p>
            </div>

            <div className="atl-field">
                <label htmlFor="resend-email" className="atl-field-label">{t("atlResetNeedEmail")}</label>
                <input
                    id="resend-email"
                    type="email"
                    value={resendEmail}
                    onChange={(e) => setResendEmail(e.target.value)}
                    className="atl-input"
                    placeholder="you@example.com"
                    autoComplete="email"
                />
            </div>
            {resendMessage && <p className="atl-note" style={{ textAlign: "start" }}>{resendMessage}</p>}
            <button
                onClick={handleResend}
                disabled={resendLoading || !resendEmail}
                className="atl-btn atl-btn-ghost"
            >
                {resendLoading ? (
                    <><span className="atl-spin" /><span>{t("atlSending")}</span></>
                ) : (
                    <span>{t("resendVerification")}</span>
                )}
            </button>

            <hr className="atl-auth-divider" />
            <div className="atl-auth-foot">
                <Link href="/login" className="atl-link">{t("atlBackToSignIn")}</Link>
            </div>
        </div>
    );
}

export default function VerifyEmailPage() {
    return (
        <Suspense fallback={
            <AtelierAuthShell><p className="atl-note">…</p></AtelierAuthShell>
        }>
            <AtelierAuthShell>
                <VerifyEmailContent />
            </AtelierAuthShell>
        </Suspense>
    );
}

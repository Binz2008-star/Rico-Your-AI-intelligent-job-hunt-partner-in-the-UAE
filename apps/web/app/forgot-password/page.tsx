"use client";

import { useState } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/api";
import { AtelierAuthShell } from "@/components/auth/AtelierAuthShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const { language } = useLanguage();
  const t = useTranslation(language);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await forgotPassword(email.trim());
    } catch {
      // Always show generic success — never reveal whether an email exists
    } finally {
      setLoading(false);
      setSubmitted(true);
    }
  }

  return (
    <AtelierAuthShell>
      {submitted ? (
        <div className="atl-status">
          <span className="atl-status-badge" aria-hidden="true">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2.5" y="4.5" width="19" height="15" rx="2" />
              <path d="M3 6l9 6 9-6" />
            </svg>
          </span>
          <div>
            <h1 className="atl-auth-title">{t("atlCheckInboxTitle")}</h1>
            <p className="atl-auth-sub" style={{ marginBottom: 0 }}>
              {t("resetInstructionsSent")}
            </p>
          </div>
          <p className="atl-note">{t("checkSpamFolder")}</p>

          <hr className="atl-auth-divider" />
          <div className="atl-auth-foot">
            <Link href="/login" className="atl-link">{t("atlBackToSignIn")}</Link>
          </div>
        </div>
      ) : (
        <>
          <h1 className="atl-auth-title">{t("atlForgotTitle")}</h1>
          <p className="atl-auth-sub">{t("atlForgotSub")}</p>

          <form onSubmit={handleSubmit} className="atl-auth-form">
            <div className="atl-field">
              <label htmlFor="email" className="atl-field-label">{t("atlEmail")}</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
                className="atl-input"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !email.trim()}
              className="atl-btn atl-btn-primary"
            >
              {loading ? (
                <><span className="atl-spin" /><span>{t("atlSending")}</span></>
              ) : (
                <span>{t("atlSendResetLink")}</span>
              )}
            </button>
          </form>

          <hr className="atl-auth-divider" />
          <div className="atl-auth-foot">
            <Link href="/login" className="atl-link">{t("atlBackToSignIn")}</Link>
          </div>
        </>
      )}
    </AtelierAuthShell>
  );
}

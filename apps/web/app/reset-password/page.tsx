"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { resetPassword } from "@/lib/api";
import { AtelierAuthShell } from "@/components/auth/AtelierAuthShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";

function ResetPasswordForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const token        = searchParams.get("token") ?? "";
  const { language } = useLanguage();
  const t = useTranslation(language);

  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const [success,  setSuccess]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError(t("passwordsDoNotMatch"));
      return;
    }
    setLoading(true);
    try {
      await resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("atlResetLinkInvalid")
      );
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="atl-status">
        <h1 className="atl-auth-title">{t("atlForgotTitle")}</h1>
        <p className="atl-auth-sub" style={{ marginBottom: 0 }}>{t("atlMissingResetToken")}</p>
        <hr className="atl-auth-divider" />
        <div className="atl-auth-foot">
          <Link href="/forgot-password" className="atl-link">{t("atlRequestNewLink")}</Link>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="atl-status">
        <span className="atl-status-badge" aria-hidden="true">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        </span>
        <div>
          <h1 className="atl-auth-title">{t("passwordUpdated")}</h1>
          <p className="atl-auth-sub" style={{ marginBottom: 0 }}>{t("signInNewPassword")}</p>
        </div>
        <button onClick={() => router.push("/login")} className="atl-btn atl-btn-primary">
          {t("atlSignInNow")}
        </button>
      </div>
    );
  }

  return (
    <>
      <h1 className="atl-auth-title">{t("atlResetTitle")}</h1>
      <p className="atl-auth-sub">{t("atlResetSub")}</p>

      <form onSubmit={handleSubmit} className="atl-auth-form">
        <div className="atl-field">
          <label htmlFor="password" className="atl-field-label">{t("atlNewPassword")}</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            placeholder="••••••••"
            className="atl-input"
          />
          <p className="atl-hint">{t("atlPasswordRule")}</p>
        </div>

        <div className="atl-field">
          <label htmlFor="confirm" className="atl-field-label">{t("atlConfirmNewPassword")}</label>
          <input
            id="confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            autoComplete="new-password"
            placeholder="••••••••"
            className="atl-input"
          />
        </div>

        {error && <p className="atl-alert atl-alert-error">{error}</p>}

        <button
          type="submit"
          disabled={loading || !password || !confirm}
          className="atl-btn atl-btn-primary"
        >
          {loading ? (
            <><span className="atl-spin" /><span>{t("atlUpdating")}</span></>
          ) : (
            <span>{t("atlUpdatePassword")}</span>
          )}
        </button>
      </form>

      <hr className="atl-auth-divider" />
      <div className="atl-auth-foot">
        <Link href="/login" className="atl-link">{t("atlBackToSignIn")}</Link>
      </div>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <AtelierAuthShell>
      <Suspense fallback={<p className="atl-note">…</p>}>
        <ResetPasswordForm />
      </Suspense>
    </AtelierAuthShell>
  );
}

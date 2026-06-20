"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { resetPassword } from "@/lib/api";
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
        err instanceof Error ? err.message : t("resetLinkInvalid")
      );
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-sm text-red-400">
          {t("missingResetToken")}
        </p>
        <Link
          href="/forgot-password"
          className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors underline underline-offset-2"
        >
          {t("requestNewLink")}
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-400">
          {t("passwordUpdated")}
        </div>
        <p className="text-sm text-zinc-300">
          {t("signInNewPassword")}
        </p>
        <button
          onClick={() => router.push("/login")}
          className="w-full rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-indigo-500"
        >
          {t("signIn")}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="password" className="mb-1.5 block text-sm text-zinc-400">
          {t("newPassword")}
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          maxLength={128}
          autoComplete="new-password"
          placeholder={t("minChars8")}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <p className="mt-1.5 text-xs text-zinc-500">
          Min 8 characters · uppercase · lowercase · digit or symbol
        </p>
      </div>

      <div>
        <label htmlFor="confirm" className="mb-1.5 block text-sm text-zinc-400">
          {t("confirmPassword")}
        </label>
        <input
          id="confirm"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          autoComplete="new-password"
          placeholder={t("repeatNewPassword")}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      {/* Error */}
      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !password || !confirm}
        className="w-full rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? t("updating") : t("setNewPassword")}
      </button>

      <p className="text-center text-xs">
        <Link
          href="/login"
          className="text-zinc-400 hover:text-white transition-colors"
        >
          {t("backToSignIn")}
        </Link>
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  const { language } = useLanguage();
  const t = useTranslation(language);
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-8 text-center">
          <Link href="/" className="inline-flex items-center gap-2 text-lg font-bold text-white tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-[#f5a623] text-sm font-black text-[#0a0a1a] shadow-[0_4px_12px_rgba(245,166,35,0.35)]">R</span>
            Rico <span className="text-[#f5a623]">Hunt</span>
          </Link>
          <p className="mt-1 text-sm text-zinc-400">{t("setANewPassword")}</p>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
          <Suspense
            fallback={<p className="text-center text-sm text-zinc-500">{t("loading")}</p>}
          >
            <ResetPasswordForm />
          </Suspense>
        </div>
      </div>
    </main>
  );
}

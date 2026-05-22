"use client";

import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { resetPassword } from "@/lib/api";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function ResetPasswordForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const token        = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const [success,  setSuccess]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Reset failed. The link may have expired."
      );
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-sm text-red-400">
          Missing reset token. Please use the link from your reset email.
        </p>
        <Link
          href="/forgot-password"
          className="text-xs text-primary hover:text-primary/80 transition-colors underline underline-offset-2"
        >
          Request a new link
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
          Password updated
        </div>
        <p className="text-sm text-on-surface">
          You can now sign in with your new password.
        </p>
        <button
          onClick={() => router.push("/login")}
          className="w-full rounded-lg bg-primary/10 py-3 text-sm font-semibold text-primary transition-all hover:bg-primary/20"
        >
          Sign in
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="password" className="mb-1.5 block text-[10px] uppercase tracking-widest text-on-surface-variant">
          New password
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
          placeholder="Minimum 8 characters"
          className="w-full rounded-lg border border-white/10 bg-surface-container px-3 py-2.5 text-sm text-on-surface placeholder-on-surface-variant/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30 transition-all"
        />
      </div>

      <div>
        <label htmlFor="confirm" className="mb-1.5 block text-[10px] uppercase tracking-widest text-on-surface-variant">
          Confirm password
        </label>
        <input
          id="confirm"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          autoComplete="new-password"
          placeholder="Repeat new password"
          className="w-full rounded-lg border border-white/10 bg-surface-container px-3 py-2.5 text-sm text-on-surface placeholder-on-surface-variant/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30 transition-all"
        />
      </div>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !password || !confirm}
        className="w-full rounded-lg bg-primary/10 py-3 text-sm font-semibold text-primary transition-all hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Updating…" : "Set new password"}
      </button>

      <p className="text-center text-xs">
        <Link
          href="/login"
          className="text-on-surface-variant hover:text-on-surface transition-colors"
        >
          ← Back to sign in
        </Link>
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" className="animate-pulse-magenta" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" className="animate-pulse-magenta" style={{ animationDelay: "-2s" }} />

      <div className="relative z-10 w-full max-w-sm">
        {/* Brand */}
        <div className="mb-8 text-center">
          <Link href="/" className="inline-flex items-center gap-2.5 justify-center">
            <div className="w-9 h-9 rounded-[10px] bg-gradient-to-br from-magenta to-cyan flex items-center justify-center text-sm font-black text-white shadow-[0_4px_16px_rgba(255,45,142,0.3)]">
              R
            </div>
            <span className="font-display font-black text-xl text-white tracking-tight">Rico AI</span>
          </Link>
          <p className="mt-3 text-sm text-on-surface-variant">Set a new password</p>
        </div>

        <GlassPanel className="rounded-2xl border border-white/10 p-6">
          <Suspense
            fallback={<p className="text-center text-sm text-on-surface-variant">Loading…</p>}
          >
            <ResetPasswordForm />
          </Suspense>
        </GlassPanel>
      </div>
    </main>
  );
}

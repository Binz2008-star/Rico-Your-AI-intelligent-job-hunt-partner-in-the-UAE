"use client";

import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { forgotPassword } from "@/lib/api";
import Link from "next/link";
import { useState } from "react";

export default function ForgotPasswordPage() {
  const [email,     setEmail]     = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading,   setLoading]   = useState(false);

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
          <p className="mt-3 text-sm text-on-surface-variant">Reset your password</p>
        </div>

        <GlassPanel className="rounded-2xl border border-white/10 p-6">
          {submitted ? (
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
                Email sent
              </div>
              <p className="text-sm text-on-surface">
                If that address is registered, a reset link is on its way.
              </p>
              <p className="text-xs text-on-surface-variant">
                Can&apos;t find it? Check your spam folder.
              </p>
              <Link
                href="/login"
                className="mt-2 text-xs text-primary hover:text-primary/80 transition-colors underline underline-offset-2"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="email" className="mb-1.5 block text-[10px] uppercase tracking-widest text-on-surface-variant">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  placeholder="you@example.com"
                  className="w-full rounded-lg border border-white/10 bg-surface-container px-3 py-2.5 text-sm text-on-surface placeholder-on-surface-variant/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={loading || !email.trim()}
                className="w-full rounded-lg bg-primary/10 px-6 py-3 text-sm font-semibold text-primary transition-all hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Sending…" : "Send reset link"}
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
          )}
        </GlassPanel>
      </div>
    </main>
  );
}

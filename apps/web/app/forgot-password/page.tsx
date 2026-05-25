"use client";

import { useState } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/api";
import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { PageTransition, StaggerChildren } from "@/components/ui/PageTransition";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

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
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <AuraGlow variant="magenta" position="top-right" className="animate-pulse-magenta" />
      <AuraGlow variant="cyan" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

      <PageTransition>
        <GlassPanel className="w-full max-w-md p-8 rounded-2xl border border-white/10 transition-all duration-300">
          <StaggerChildren baseDelay={100} className="text-center mb-8">
            <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">Reset Password</h1>
            <p className="text-body-md text-on-surface-variant">Enter your email to receive reset instructions</p>
          </StaggerChildren>

          <div className="rounded-xl border border-white/10 bg-surface-container/60 p-6">
            {submitted ? (
              <div className="flex flex-col items-center gap-4 text-center">
                <div className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
                  Check your email
                </div>
                <p className="text-sm text-on-surface">
                  If an account exists for this email, we&apos;ll send reset instructions.
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
                  <label htmlFor="email" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
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
                    className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-on-surface focus:outline-none focus:border-primary transition-all"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className="w-full bg-primary/10 text-primary rounded-lg px-6 py-4 font-label-caps uppercase tracking-widest hover:bg-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <MaterialIcon icon="hourglass_empty" className="animate-spin" />
                      <span>Sending...</span>
                    </>
                  ) : (
                    <>
                      <span>Send reset link</span>
                      <MaterialIcon icon="send" />
                    </>
                  )}
                </button>

                <p className="text-center text-xs text-on-surface-variant">
                  <Link
                    href="/login"
                    className="text-primary hover:text-primary/80 transition-colors"
                  >
                    ← Back to sign in
                  </Link>
                </p>
              </form>
            )}
          </div>
        </GlassPanel>
      </PageTransition>

      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute inset-0 opacity-[0.04] bg-[url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27%3E%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%27.85%27 numOctaves=%274%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27 opacity=%27.025%27/%3E%3C/svg%3E')]" />
      </div>
    </div>
  );
}

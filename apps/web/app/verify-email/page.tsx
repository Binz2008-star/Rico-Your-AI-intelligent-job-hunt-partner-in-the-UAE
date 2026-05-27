"use client";

import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { PageTransition } from "@/components/ui/PageTransition";
import { verifyEmail, resendVerification } from "@/lib/api";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import React, { Suspense, useEffect, useState } from "react";

type Status = "loading" | "success" | "error";

function VerifyEmailContent() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const token = searchParams.get("token") ?? "";

    const [status, setStatus] = useState<Status>("loading");
    const [message, setMessage] = useState("");
    const [resendEmail, setResendEmail] = useState("");
    const [resendLoading, setResendLoading] = useState(false);
    const [resendMessage, setResendMessage] = useState("");

    useEffect(() => {
        if (!token) {
            setStatus("error");
            setMessage("No verification token found. Please use the link from your email.");
            return;
        }

        verifyEmail(token)
            .then(() => {
                setStatus("success");
                setTimeout(() => router.push("/login"), 2000);
            })
            .catch(() => {
                setStatus("error");
                setMessage("This verification link is invalid, expired, or has already been used.");
            });
    }, [token, router]);

    const handleResend = async () => {
        if (!resendEmail) return;
        setResendLoading(true);
        setResendMessage("");
        try {
            await resendVerification(resendEmail);
            setResendMessage("Verification email sent. Please check your inbox.");
        } catch {
            setResendMessage("Couldn't resend right now. Please try again in a moment.");
        } finally {
            setResendLoading(false);
        }
    };

    return (
        <main className="flex min-h-screen items-center justify-center bg-background px-4 relative overflow-hidden">
            <AuraGlow variant="cyan" position="top-right" className="animate-pulse-magenta" />
            <AuraGlow variant="magenta" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: "-2s" }} />

            <div className="w-full max-w-sm relative z-10">
                <PageTransition>
                    <GlassPanel className="w-full p-8 rounded-2xl border border-white/10 text-center">
                        {status === "loading" && (
                            <>
                                <MaterialIcon icon="hourglass_empty" className="text-primary text-4xl animate-spin mb-4" />
                                <p className="text-on-surface-variant text-sm">Verifying your email…</p>
                            </>
                        )}

                        {status === "success" && (
                            <>
                                <div className="w-16 h-16 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4">
                                    <MaterialIcon icon="check_circle" className="text-primary text-3xl" />
                                </div>
                                <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">Email verified!</h1>
                                <p className="text-on-surface-variant text-sm mb-6">
                                    Welcome to RicoHunt. You can now sign in.
                                </p>
                                <Link
                                    href="/login"
                                    className="inline-flex items-center gap-2 text-sm text-primary hover:text-primary/80 transition-colors"
                                >
                                    <MaterialIcon icon="arrow_forward" className="text-sm" />
                                    Sign in now
                                </Link>
                            </>
                        )}

                        {status === "error" && (
                            <>
                                <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4">
                                    <MaterialIcon icon="error_outline" className="text-red-400 text-3xl" />
                                </div>
                                <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">Verification failed</h1>
                                <p className="text-on-surface-variant text-sm mb-6">{message}</p>

                                <div className="space-y-3">
                                    <p className="text-xs text-on-surface-variant">Need a new link? Enter your email:</p>
                                    <input
                                        type="email"
                                        value={resendEmail}
                                        onChange={(e) => setResendEmail(e.target.value)}
                                        className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-2.5 text-on-surface text-sm focus:outline-none focus:border-primary transition-all"
                                        placeholder="you@example.com"
                                    />
                                    {resendMessage && (
                                        <p className="text-xs text-primary/80">{resendMessage}</p>
                                    )}
                                    <button
                                        onClick={handleResend}
                                        disabled={resendLoading || !resendEmail}
                                        className="w-full bg-primary/10 text-primary rounded-lg px-4 py-2.5 text-sm font-label-caps uppercase tracking-widest hover:bg-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                    >
                                        {resendLoading ? (
                                            <MaterialIcon icon="hourglass_empty" className="text-sm animate-spin" />
                                        ) : (
                                            <MaterialIcon icon="refresh" className="text-sm" />
                                        )}
                                        Resend verification email
                                    </button>
                                </div>

                                <div className="mt-6">
                                    <Link href="/login" className="text-sm text-on-surface-variant hover:text-primary transition-colors">
                                        Back to login
                                    </Link>
                                </div>
                            </>
                        )}
                    </GlassPanel>
                </PageTransition>
            </div>
        </main>
    );
}

export default function VerifyEmailPage() {
    return (
        <Suspense fallback={
            <main className="flex min-h-screen items-center justify-center bg-background px-4">
                <p className="text-sm text-on-surface-variant">Loading…</p>
            </main>
        }>
            <VerifyEmailContent />
        </Suspense>
    );
}

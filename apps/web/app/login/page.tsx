"use client";

import { LoginForm } from '@/components/auth/LoginForm';
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function LoginPageContent() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const searchParams = useSearchParams();
    const initialEmail = searchParams.get("email") ?? "";
    return (
        <main className="flex min-h-screen items-center justify-center bg-background px-4 relative overflow-hidden">
            {/* Ambient glow - cinematic magenta/cyan */}
            <div className="fixed inset-0 pointer-events-none">
                <div className="absolute -top-[200px] -left-[100px] w-[600px] h-[600px] rounded-full bg-magenta-dim blur-[140px]" />
                <div className="absolute bottom-0 -right-[100px] w-[400px] h-[400px] rounded-full bg-cyan-dim blur-[140px]" />
            </div>

            <div className="w-full max-w-sm relative z-10">
                {/* Brand */}
                <div className="mb-8 text-center">
                    <Link href="/" className="inline-flex items-center gap-2.5 justify-center">
                        <div className="w-9 h-9 rounded-[10px] bg-[#f5a623] flex items-center justify-center text-sm font-black text-[#0a0a1a] shadow-[0_4px_16px_rgba(245,166,35,0.35)]">
                            R
                        </div>
                        <span className="font-display font-black text-xl text-text-primary tracking-tight">Rico <span className="text-[#f5a623]">Hunt</span></span>
                    </Link>
                    <p className="mt-3 text-sm text-text-muted">{t('signInToAgent')}</p>
                </div>

                <LoginForm initialEmail={initialEmail} />
            </div>
        </main>
    );
}

export default function LoginPage() {
    return (
        <Suspense>
            <LoginPageContent />
        </Suspense>
    );
}

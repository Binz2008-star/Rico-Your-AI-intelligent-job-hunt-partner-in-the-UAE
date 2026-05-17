"use client";

import { LoginForm } from '@/components/auth/LoginForm';
import Link from "next/link";

export default function LoginPage() {
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
                        <div className="w-9 h-9 rounded-[10px] bg-gradient-to-br from-magenta to-cyan flex items-center justify-center text-sm font-black text-white shadow-[0_4px_16px_rgba(255,45,142,0.3)]">
                            R
                        </div>
                        <span className="font-display font-black text-xl text-white tracking-tight">Rico AI</span>
                    </Link>
                    <p className="mt-3 text-sm text-text-muted">Sign in to your autonomous job agent</p>
                </div>

                <LoginForm />
            </div>
        </main>
    );
}

'use client';

import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { useAuthStore } from '@/lib/store/useAuthStore';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

export function LoginForm() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const { login, isLoading } = useAuthStore();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await login(email, password);
            router.push('/command');
            router.refresh();
        } catch (error) {
            console.error('Login failed:', error);
        }
    };

    return (
        <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
            <AuraGlow variant="magenta" position="top-right" className="animate-pulse-magenta" />
            <AuraGlow variant="cyan" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

            <GlassPanel className="w-full max-w-md p-8 rounded-2xl border border-white/10">
                <div className="text-center mb-8">
                    <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">Welcome Back</h1>
                    <p className="text-body-md text-on-surface-variant">Access your trajectory intelligence</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label htmlFor="email" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                            Email
                        </label>
                        <input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-on-surface focus:outline-none focus:border-primary transition-all"
                            placeholder="you@example.com"
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="password" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                            Password
                        </label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-on-surface focus:outline-none focus:border-primary transition-all"
                            placeholder="••••••••"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-primary/10 text-primary rounded-lg px-6 py-4 font-label-caps uppercase tracking-widest hover:bg-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {isLoading ? (
                            <>
                                <MaterialIcon icon="hourglass_empty" className="animate-spin" />
                                <span>Authenticating...</span>
                            </>
                        ) : (
                            <>
                                <span>Access Intelligence</span>
                                <MaterialIcon icon="arrow_forward" />
                            </>
                        )}
                    </button>
                </form>

                <div className="mt-6 text-center">
                    <a href="/signup" className="text-sm text-on-surface-variant hover:text-primary transition-colors">
                        Create account
                    </a>
                </div>
            </GlassPanel>

            <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
                <div className="absolute inset-0 opacity-[0.04] bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />
            </div>
        </div>
    );
}

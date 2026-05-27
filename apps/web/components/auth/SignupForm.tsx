'use client';

import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { PageTransition, StaggerChildren } from '@/components/ui/PageTransition';
import { authApi } from '@/lib/api/auth';
import axios from 'axios';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

function mapSignupError(err: unknown): { message: string; showLoginLink: boolean } {
    if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 409) {
            return {
                message: 'This email is already registered. Please log in instead.',
                showLoginLink: true,
            };
        }
        if (status === 400 || status === 422) {
            return {
                message: 'Please check your details and try again.',
                showLoginLink: false,
            };
        }
    }
    return {
        message: "We couldn't create your account right now. Please try again in a moment.",
        showLoginLink: false,
    };
}

export function SignupForm() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [showLoginLink, setShowLoginLink] = useState(false);
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');
        setShowLoginLink(false);
        try {
            await authApi.register({ email, password, name });
            router.push('/upload');
            router.refresh();
        } catch (err) {
            if (process.env.NODE_ENV === 'development') {
                console.error('[signup]', err);
            }
            const mapped = mapSignupError(err);
            setError(mapped.message);
            setShowLoginLink(mapped.showLoginLink);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
            <AuraGlow variant="cyan" position="top-right" className="animate-pulse-magenta" />
            <AuraGlow variant="magenta" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

            <PageTransition>
                <GlassPanel className="w-full max-w-md p-8 rounded-2xl border border-white/10 transition-all duration-300">
                    <StaggerChildren baseDelay={100} className="text-center mb-8">
                        <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">Initialize Intelligence</h1>
                        <p className="text-body-md text-on-surface-variant">Begin your trajectory evolution</p>
                    </StaggerChildren>

                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div>
                            <label htmlFor="name" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                                Name
                            </label>
                            <input
                                id="name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-on-surface focus:outline-none focus:border-primary transition-all"
                                placeholder="Your name"
                                required
                            />
                        </div>

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
                                    <span>Initializing...</span>
                                </>
                            ) : (
                                <>
                                    <span>Begin Journey</span>
                                    <MaterialIcon icon="rocket_launch" />
                                </>
                            )}
                        </button>
                    </form>

                    {error && (
                        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center animate-[fadeSlideIn_0.3s_ease-out]">
                            {error}
                            {showLoginLink && (
                                <div className="mt-2">
                                    <Link
                                        href="/login"
                                        className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                                    >
                                        <MaterialIcon icon="login" className="text-sm" />
                                        Go to login
                                    </Link>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="mt-6 text-center">
                        <a href="/login" className="text-sm text-on-surface-variant hover:text-primary transition-colors">
                            Already have an account?
                        </a>
                    </div>
                </GlassPanel>
            </PageTransition>

            <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
                <div className="absolute inset-0 opacity-[0.04] bg-[url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27%3E%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%27.85%27 numOctaves=%274%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27 opacity=%27.025%27/%3E%3C/svg%3E')]" />
            </div>
        </div>
    );
}

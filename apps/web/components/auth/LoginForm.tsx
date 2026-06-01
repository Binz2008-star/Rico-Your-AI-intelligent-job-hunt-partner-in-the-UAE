'use client';

import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { PageTransition, StaggerChildren } from '@/components/ui/PageTransition';
import { ApiError, resendVerification } from '@/lib/api';
import { useAuthStore } from '@/lib/store/useAuthStore';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation } from '@/lib/translations';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

export function LoginForm() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [failedAttempts, setFailedAttempts] = useState(0);
    const [showUnverified, setShowUnverified] = useState(false);
    const [resendLoading, setResendLoading] = useState(false);
    const [resendMessage, setResendMessage] = useState('');
    const { login, isLoading } = useAuthStore();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const router = useRouter();
    const maintenanceMode = process.env.NEXT_PUBLIC_MAINTENANCE_MODE === 'true';

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (maintenanceMode) return;
        setError('');
        setShowUnverified(false);
        setResendMessage('');
        try {
            await login(email, password);
            router.push('/command');
            router.refresh();
        } catch (err) {
            if (process.env.NODE_ENV === 'development') {
                console.error('[login]', err);
            }
            if (err instanceof ApiError && err.statusCode === 403) {
                setShowUnverified(true);
                setError(t('pleaseVerifyEmail'));
            } else if (err instanceof ApiError && err.statusCode === 401) {
                setError(t('emailPasswordIncorrect'));
                setFailedAttempts(prev => prev + 1);
            } else {
                setError(t('couldNotLogin'));
                setFailedAttempts(prev => prev + 1);
            }
        }
    };

    const handleResend = async () => {
        if (!email) return;
        setResendLoading(true);
        setResendMessage('');
        try {
            await resendVerification(email);
            setResendMessage(t('verificationEmailSent'));
        } catch {
            setResendMessage(t('couldNotResend'));
        } finally {
            setResendLoading(false);
        }
    };

    return (
        <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
            <AuraGlow variant="magenta" position="top-right" className="animate-pulse-magenta" />
            <AuraGlow variant="cyan" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

            <PageTransition>
                <GlassPanel className="w-full max-w-md p-8 rounded-2xl border border-white/10 transition-all duration-300">
                    <StaggerChildren baseDelay={100} className="text-center mb-8">
                        <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">{t('welcomeBack')}</h1>
                        <p className="text-body-md text-on-surface-variant">{t('accessTrajectory')}</p>
                    </StaggerChildren>

                    {maintenanceMode && (
                        <div className="mb-6 rounded-lg border border-amber-400/30 bg-amber-400/10 p-4 text-left">
                            <p className="text-sm font-semibold text-amber-300">{t('backendMaintenance')}</p>
                            <p className="mt-1 text-xs leading-relaxed text-amber-100/80">
                                {t('backendMaintenanceAuth')}
                            </p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div>
                            <label htmlFor="email" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                                {t('email')}
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
                            <div className="flex items-center justify-between mb-2">
                                <label htmlFor="password" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
                                    {t('password')}
                                </label>
                                <a
                                    href="/forgot-password"
                                    className="text-xs text-primary hover:text-primary/80 transition-colors"
                                >
                                    {t('forgotPassword')}
                                </a>
                            </div>
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
                            disabled={isLoading || maintenanceMode}
                            className="w-full bg-primary/10 text-primary rounded-lg px-6 py-4 font-label-caps uppercase tracking-widest hover:bg-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {maintenanceMode ? (
                                <span>{t('backendMaintenance')}</span>
                            ) : isLoading ? (
                                <>
                                    <MaterialIcon icon="hourglass_empty" className="animate-spin" />
                                    <span>{t('authenticating')}</span>
                                </>
                            ) : (
                                <>
                                    <span>{t('accessIntelligence')}</span>
                                    <MaterialIcon icon="arrow_forward" />
                                </>
                            )}
                        </button>
                    </form>

                    {error && (
                        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center animate-[fadeSlideIn_0.3s_ease-out]">
                            {error}

                            {showUnverified && (
                                <div className="mt-3 pt-3 border-t border-red-500/20 space-y-2">
                                    {resendMessage ? (
                                        <p className="text-xs text-primary/80">{resendMessage}</p>
                                    ) : (
                                        <button
                                            onClick={handleResend}
                                            disabled={resendLoading || !email}
                                            className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors disabled:opacity-50"
                                        >
                                            {resendLoading ? (
                                                <MaterialIcon icon="hourglass_empty" className="text-sm animate-spin" />
                                            ) : (
                                                <MaterialIcon icon="refresh" className="text-sm" />
                                            )}
                                            {t('resendVerification')}
                                        </button>
                                    )}
                                </div>
                            )}

                            {!showUnverified && failedAttempts >= 2 && (
                                <div className="mt-3 pt-3 border-t border-red-500/20">
                                    <p className="text-xs text-red-300/80 mb-2">{t('stillHavingTrouble')}</p>
                                    <Link
                                        href="/forgot-password"
                                        className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                                    >
                                        <MaterialIcon icon="lock_reset" className="text-sm" />
                                        {t('resetPassword')}
                                    </Link>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="mt-6 text-center">
                        <a href="/signup" className="text-sm text-on-surface-variant hover:text-primary transition-colors">
                            {t('createAccount')}
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

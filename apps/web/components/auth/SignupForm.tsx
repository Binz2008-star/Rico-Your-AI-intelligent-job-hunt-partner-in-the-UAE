'use client';

import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { PageTransition, StaggerChildren } from '@/components/ui/PageTransition';
import { ApiError, register, resendVerification } from '@/lib/api';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation, type TranslationKey } from '@/lib/translations';
import Link from 'next/link';
import React, { useState } from 'react';

function mapSignupError(err: unknown): { messageKey: TranslationKey; showLoginLink: boolean } {
    if (err instanceof ApiError) {
        if (err.statusCode === 409) {
            return {
                messageKey: 'emailAlreadyRegistered',
                showLoginLink: true,
            };
        }
        if (err.statusCode === 400 || err.statusCode === 422) {
            return {
                messageKey: 'checkDetails',
                showLoginLink: false,
            };
        }
    }
    return {
        messageKey: 'couldNotCreateAccount',
        showLoginLink: false,
    };
}

export function SignupForm() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [showLoginLink, setShowLoginLink] = useState(false);
    const [verificationSent, setVerificationSent] = useState(false);
    const [registeredEmail, setRegisteredEmail] = useState('');
    const [resendLoading, setResendLoading] = useState(false);
    const [resendMessage, setResendMessage] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');
        setShowLoginLink(false);
        try {
            const result = await register(email, password);
            if (result.email_verification_required) {
                setRegisteredEmail(result.email);
                setVerificationSent(true);
            }
        } catch (err) {
            if (process.env.NODE_ENV === 'development') {
                console.error('[signup]', err);
            }
            const mapped = mapSignupError(err);
            setError(t(mapped.messageKey));
            setShowLoginLink(mapped.showLoginLink);
        } finally {
            setIsLoading(false);
        }
    };

    const handleResend = async () => {
        if (!registeredEmail) return;
        setResendLoading(true);
        setResendMessage('');
        try {
            await resendVerification(registeredEmail);
            setResendMessage(t('verificationEmailSent'));
        } catch {
            setResendMessage(t('couldNotResend'));
        } finally {
            setResendLoading(false);
        }
    };

    if (verificationSent) {
        return (
            <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
                <AuraGlow variant="cyan" position="top-right" className="animate-pulse-magenta" />
                <AuraGlow variant="magenta" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

                <PageTransition>
                    <GlassPanel className="w-full max-w-md p-8 rounded-2xl border border-white/10 text-center">
                        <div className="mb-6">
                            <div className="w-16 h-16 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4">
                                <MaterialIcon icon="mark_email_unread" className="text-primary text-3xl" />
                            </div>
                            <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">{t('checkYourEmail')}</h1>
                            <p className="text-body-md text-on-surface-variant">
                                {t('accountCreated')}{' '}
                                <span className="text-primary">{registeredEmail}</span>.
                            </p>
                            <p className="mt-2 text-sm text-on-surface-variant">
                                {t('clickLinkToActivate')}
                            </p>
                        </div>

                        {resendMessage && (
                            <p className="mb-4 text-sm text-primary/80">{resendMessage}</p>
                        )}

                        <button
                            onClick={handleResend}
                            disabled={resendLoading}
                            className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-sm text-on-surface-variant hover:text-on-surface hover:border-white/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {resendLoading ? (
                                <>
                                    <MaterialIcon icon="hourglass_empty" className="animate-spin text-sm" />
                                    <span>{t('sending')}</span>
                                </>
                            ) : (
                                <>
                                    <MaterialIcon icon="refresh" className="text-sm" />
                                    <span>{t('resendVerification')}</span>
                                </>
                            )}
                        </button>

                        <div className="mt-6 text-center">
                            <Link href="/login" className="text-sm text-on-surface-variant hover:text-primary transition-colors">
                                {t('backToLogin')}
                            </Link>
                        </div>
                    </GlassPanel>
                </PageTransition>

                <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
                    <div className="absolute inset-0 opacity-[0.04] bg-[url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27%3E%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%27.85%27 numOctaves=%274%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27 opacity=%27.025%27/%3E%3C/svg%3E')]" />
                </div>
            </div>
        );
    }

    return (
        <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
            <AuraGlow variant="cyan" position="top-right" className="animate-pulse-magenta" />
            <AuraGlow variant="magenta" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

            <PageTransition>
                <GlassPanel className="w-full max-w-md p-8 rounded-2xl border border-white/10 transition-all duration-300">
                    <StaggerChildren baseDelay={100} className="text-center mb-8">
                        <h1 className="font-headline-xl text-headline-xl text-on-surface mb-2">{t('initializeIntelligence')}</h1>
                        <p className="text-body-md text-on-surface-variant">{t('beginTrajectory')}</p>
                    </StaggerChildren>

                    <form onSubmit={handleSubmit} className="space-y-6">
                        <div>
                            <label htmlFor="name" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                                {t('name')}
                            </label>
                            <input
                                id="name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-on-surface focus:outline-none focus:border-primary transition-all"
                                placeholder={t('yourName')}
                                required
                            />
                        </div>

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
                                placeholder={t('emailPlaceholder')}
                                required
                            />
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">
                                {t('password')}
                            </label>
                            <input
                                id="password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-surface-container border border-white/10 rounded-lg px-4 py-3 text-on-surface focus:outline-none focus:border-primary transition-all"
                                placeholder={t('passwordPlaceholder')}
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
                                    <span>{t('initializing')}</span>
                                </>
                            ) : (
                                <>
                                    <span>{t('beginJourney')}</span>
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
                                        {t('goToLogin')}
                                    </Link>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="mt-6 text-center">
                        <a href="/login" className="text-sm text-on-surface-variant hover:text-primary transition-colors">
                            {t('alreadyHaveAccount')}
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

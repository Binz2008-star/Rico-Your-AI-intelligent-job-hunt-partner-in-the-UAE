'use client';

import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { PageTransition } from '@/components/ui/PageTransition';
import { ApiError, register, resendVerification } from '@/lib/api';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation, type TranslationKey } from '@/lib/translations';
import Link from 'next/link';
import React, { useState } from 'react';

function mapSignupError(err: unknown): { messageKey: TranslationKey; showLoginLink: boolean } {
    if (err instanceof ApiError) {
        if (err.statusCode === 409) {
            return { messageKey: 'emailAlreadyRegistered', showLoginLink: true };
        }
        if (err.statusCode === 400 || err.statusCode === 422) {
            return { messageKey: 'checkDetails', showLoginLink: false };
        }
    }
    return { messageKey: 'couldNotCreateAccount', showLoginLink: false };
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
            const result = await register(email, password, null, name);
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

    const inputClass =
        'w-full bg-[#0d0d1f] border border-white/10 rounded-xl pl-10 pr-4 py-3 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-gold/50 focus:shadow-[0_0_0_3px_rgba(245,166,35,0.07)] transition-all duration-200';

    if (verificationSent) {
        return (
            <div className="relative min-h-screen flex items-center justify-center overflow-hidden px-4">
                <AuraGlow variant="cyan" position="top-right" className="animate-pulse-magenta" />
                <AuraGlow variant="magenta" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />
                <PageTransition>
                    <div className="w-full max-w-sm">
                        <GlassPanel className="p-8 rounded-2xl border border-white/10 text-center">
                            <div className="w-16 h-16 rounded-full bg-gold/10 border border-gold/20 flex items-center justify-center mx-auto mb-5">
                                <MaterialIcon icon="mark_email_unread" className="text-gold text-3xl" />
                            </div>
                            <h1 className="text-2xl font-bold text-white mb-2">{t('checkYourEmail')}</h1>
                            <p className="text-sm text-white/60 leading-relaxed mb-1">
                                {t('accountCreated')}{' '}
                                <span className="text-gold font-medium">{registeredEmail}</span>.
                            </p>
                            <p className="text-sm text-white/50 mb-6">{t('clickLinkToActivate')}</p>

                            {resendMessage && (
                                <p className="mb-4 text-sm text-gold/80">{resendMessage}</p>
                            )}

                            <button
                                onClick={handleResend}
                                disabled={resendLoading}
                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white/70 hover:text-white hover:border-white/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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

                            <div className="mt-5 text-center">
                                <Link href="/login" className="text-sm text-white/50 hover:text-gold transition-colors">
                                    {t('backToLogin')}
                                </Link>
                            </div>
                        </GlassPanel>
                    </div>
                </PageTransition>
            </div>
        );
    }

    return (
        <div className="relative min-h-screen flex items-center justify-center overflow-hidden px-4 py-12">
            {/* Ambient glows */}
            <AuraGlow variant="cyan" position="top-right" className="animate-pulse-magenta" />
            <AuraGlow variant="magenta" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />
            {/* Subtle grain */}
            <div className="fixed inset-0 pointer-events-none opacity-[0.04] bg-[url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27%3E%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%27.85%27 numOctaves=%274%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27 opacity=%27.025%27/%3E%3C/svg%3E')]" />

            <PageTransition>
                <div className="w-full max-w-[400px]">
                    {/* Brand mark */}
                    <div className="text-center mb-7">
                        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gold/10 border border-gold/25 mb-4 shadow-[0_0_28px_rgba(245,166,35,0.12)]">
                            <MaterialIcon icon="auto_awesome" className="text-gold text-[28px]" />
                        </div>
                        <h1 className="text-[28px] font-bold text-white tracking-tight">
                            Rico <span className="text-gold">AI</span>
                        </h1>
                        <p className="text-sm text-white/45 mt-1">{t('beginTrajectory')}</p>
                    </div>

                    {/* Card */}
                    <GlassPanel className="p-6 rounded-2xl border border-white/[0.08]">
                        <form onSubmit={handleSubmit} className="space-y-4" noValidate>

                            {/* Name */}
                            <div>
                                <label htmlFor="name" className="block text-xs font-semibold text-white/50 uppercase tracking-wide mb-1.5">
                                    {t('name')}
                                </label>
                                <div className="relative">
                                    <MaterialIcon icon="person" className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-[18px] pointer-events-none select-none" />
                                    <input
                                        id="name"
                                        type="text"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        className={inputClass}
                                        placeholder={t('yourName')}
                                        autoComplete="name"
                                    />
                                </div>
                            </div>

                            {/* Email */}
                            <div>
                                <label htmlFor="email" className="block text-xs font-semibold text-white/50 uppercase tracking-wide mb-1.5">
                                    {t('email')}
                                </label>
                                <div className="relative">
                                    <MaterialIcon icon="email" className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-[18px] pointer-events-none select-none" />
                                    <input
                                        id="email"
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        className={inputClass}
                                        placeholder={t('emailPlaceholder')}
                                        autoComplete="email"
                                        required
                                    />
                                </div>
                            </div>

                            {/* Password */}
                            <div>
                                <label htmlFor="password" className="block text-xs font-semibold text-white/50 uppercase tracking-wide mb-1.5">
                                    {t('password')}
                                </label>
                                <div className="relative">
                                    <MaterialIcon icon="lock" className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-[18px] pointer-events-none select-none" />
                                    <input
                                        id="password"
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className={inputClass}
                                        placeholder="••••••••"
                                        autoComplete="new-password"
                                        minLength={8}
                                        required
                                    />
                                </div>
                                <p className="mt-1.5 text-[11px] text-white/30">{t('passwordMinLength')}</p>
                            </div>

                            {/* Error */}
                            {error && (
                                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-start gap-2 animate-[fadeSlideIn_0.3s_ease-out]">
                                    <MaterialIcon icon="error_outline" className="text-base shrink-0 mt-0.5" />
                                    <div>
                                        {error}
                                        {showLoginLink && (
                                            <div className="mt-1.5">
                                                <Link
                                                    href="/login"
                                                    className="inline-flex items-center gap-1 text-xs text-gold hover:text-gold/80 transition-colors"
                                                >
                                                    <MaterialIcon icon="login" className="text-sm" />
                                                    {t('goToLogin')}
                                                </Link>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* CTA */}
                            <button
                                type="submit"
                                disabled={isLoading}
                                className="w-full bg-gold text-[#0a0a1a] rounded-xl px-6 py-3.5 text-sm font-bold uppercase tracking-wider hover:bg-gold-hover active:scale-[0.99] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-[0_4px_20px_rgba(245,166,35,0.30)] mt-1"
                            >
                                {isLoading ? (
                                    <>
                                        <MaterialIcon icon="hourglass_empty" className="animate-spin text-[18px]" />
                                        <span>{t('initializing')}</span>
                                    </>
                                ) : (
                                    <>
                                        <span>{t('beginJourney')}</span>
                                        <MaterialIcon icon="rocket_launch" className="text-[18px]" />
                                    </>
                                )}
                            </button>
                        </form>
                    </GlassPanel>

                    {/* Login link */}
                    <p className="mt-5 text-center text-sm text-white/40">
                        {t('alreadyHaveAccount')}{' '}
                        <Link href="/login" className="text-gold hover:text-gold/80 font-semibold transition-colors">
                            {t('login')}
                        </Link>
                    </p>
                </div>
            </PageTransition>
        </div>
    );
}

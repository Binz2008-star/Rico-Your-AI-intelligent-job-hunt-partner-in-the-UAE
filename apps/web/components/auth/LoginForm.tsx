'use client';

import { AtelierAuthShell } from '@/components/auth/AtelierAuthShell';
import { ApiError, resendVerification } from '@/lib/api';
import { useAuthStore } from '@/lib/store/useAuthStore';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation } from '@/lib/translations';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

export function LoginForm({ initialEmail = '' }: { initialEmail?: string }) {
    const [email, setEmail] = useState(initialEmail);
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
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
        <AtelierAuthShell>
            <h1 className="atl-auth-title">{t('atlLoginTitle')}</h1>
            <p className="atl-auth-sub">{t('atlLoginSub')}</p>

            {maintenanceMode && (
                <div className="atl-alert atl-alert-error" style={{ marginBottom: 18 }}>
                    <strong>{t('backendMaintenance')}</strong>
                    <p style={{ margin: '6px 0 0' }}>{t('backendMaintenanceAuth')}</p>
                </div>
            )}

            <form onSubmit={handleSubmit} className="atl-auth-form">
                <div className="atl-field">
                    <label htmlFor="email" className="atl-field-label">{t('atlEmail')}</label>
                    <input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="atl-input"
                        placeholder="you@example.com"
                        autoComplete="email"
                        required
                    />
                </div>

                <div className="atl-field">
                    <div className="atl-field-labelrow">
                        <label htmlFor="password" className="atl-field-label">{t('atlPassword')}</label>
                        <Link href="/forgot-password" className="atl-link-quiet">
                            {t('atlForgotPasswordLink')}
                        </Link>
                    </div>
                    <div className="atl-input-wrap">
                        <input
                            id="password"
                            type={showPassword ? 'text' : 'password'}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="atl-input"
                            placeholder="••••••••"
                            autoComplete="current-password"
                            required
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword((prev) => !prev)}
                            aria-label={showPassword ? t('hidePassword') : t('showPassword')}
                            aria-pressed={showPassword}
                            className="atl-reveal"
                        >
                            {showPassword ? (
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                    <path d="M17.9 17.9A10.4 10.4 0 0 1 12 20C5 20 1 12 1 12a19.6 19.6 0 0 1 5.1-6M9.9 4.2A9.5 9.5 0 0 1 12 4c7 0 11 8 11 8a19.5 19.5 0 0 1-2.2 3.2M1 1l22 22M9.9 9.9a3 3 0 0 0 4.2 4.2" />
                                </svg>
                            ) : (
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                    <circle cx="12" cy="12" r="3" />
                                </svg>
                            )}
                        </button>
                    </div>
                </div>

                <button type="submit" disabled={isLoading || maintenanceMode} className="atl-btn atl-btn-primary">
                    {maintenanceMode ? (
                        <span>{t('backendMaintenance')}</span>
                    ) : isLoading ? (
                        <><span className="atl-spin" /><span>{t('atlAuthenticating')}</span></>
                    ) : (
                        <span>{t('atlSignIn')}</span>
                    )}
                </button>
            </form>

            {error && (
                <div className="atl-alert atl-alert-error" style={{ marginTop: 16 }}>
                    {error}

                    {showUnverified && (
                        <div className="atl-alert-inline">
                            {resendMessage ? (
                                <span>{resendMessage}</span>
                            ) : (
                                <button
                                    type="button"
                                    onClick={handleResend}
                                    disabled={resendLoading || !email}
                                    className="atl-link"
                                >
                                    {resendLoading ? t('atlSending') : t('resendVerification')}
                                </button>
                            )}
                        </div>
                    )}

                    {!showUnverified && failedAttempts >= 2 && (
                        <div className="atl-alert-inline">
                            <span>{t('stillHavingTrouble')}</span>
                            <Link href="/forgot-password" className="atl-link">
                                {t('resetPassword')}
                            </Link>
                        </div>
                    )}
                </div>
            )}

            <p className="atl-auth-legal">
                {t('atlLegal')}{' '}
                <Link href="/terms">{t('atlLegalTerms')}</Link>{' '}
                {t('atlLegalAnd')}{' '}
                <Link href="/privacy">{t('atlLegalPrivacy')}</Link>.
            </p>

            <hr className="atl-auth-divider" />

            <div className="atl-auth-foot">
                <Link href="/signup" className="atl-link">{t('atlNoAccount')}</Link>
            </div>
        </AtelierAuthShell>
    );
}

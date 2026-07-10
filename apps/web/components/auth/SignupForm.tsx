'use client';

import { AtelierAuthShell } from '@/components/auth/AtelierAuthShell';
import { ApiError, register, resendVerification } from '@/lib/api';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation } from '@/lib/translations';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

function mapSignupError(
    err: unknown,
    texts: { alreadyRegistered: string; checkDetails: string; couldNotCreate: string },
): { message: string; showLoginLink: boolean } {
    if (err instanceof ApiError) {
        if (err.statusCode === 409) {
            return { message: texts.alreadyRegistered, showLoginLink: true };
        }
        if (err.statusCode === 400 || err.statusCode === 422) {
            return { message: err.message || texts.checkDetails, showLoginLink: false };
        }
    }
    return { message: texts.couldNotCreate, showLoginLink: false };
}

export function SignupForm() {
    const router = useRouter();
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
            } else {
                router.push('/onboarding');
            }
        } catch (err) {
            if (process.env.NODE_ENV === 'development') {
                console.error('[signup]', err);
            }
            const mapped = mapSignupError(err, {
                alreadyRegistered: t('emailAlreadyRegistered'),
                checkDetails: t('checkDetails'),
                couldNotCreate: t('couldNotCreateAccount'),
            });
            setError(mapped.message);
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
            <AtelierAuthShell>
                <div className="atl-status">
                    <span className="atl-status-badge" aria-hidden="true">
                        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="2.5" y="4.5" width="19" height="15" rx="2" />
                            <path d="M3 6l9 6 9-6" />
                        </svg>
                    </span>
                    <div>
                        <h1 className="atl-auth-title">{t('atlCheckInboxTitle')}</h1>
                        <p className="atl-auth-sub" style={{ marginBottom: 0 }}>
                            {t('atlCheckSentTo')}{' '}
                            <span className="atl-emph">{registeredEmail}</span>.{' '}
                            {t('atlClickToActivate')}
                        </p>
                    </div>

                    {resendMessage && <p className="atl-note">{resendMessage}</p>}

                    <button
                        type="button"
                        onClick={handleResend}
                        disabled={resendLoading}
                        className="atl-btn atl-btn-ghost"
                    >
                        {resendLoading ? (
                            <><span className="atl-spin" /><span>{t('atlSending')}</span></>
                        ) : (
                            <span>{t('atlResendCode')}</span>
                        )}
                    </button>
                </div>

                <hr className="atl-auth-divider" />

                <div className="atl-auth-foot">
                    <Link href="/login" className="atl-link">{t('atlBackToSignIn')}</Link>
                </div>
            </AtelierAuthShell>
        );
    }

    return (
        <AtelierAuthShell>
            <h1 className="atl-auth-title">{t('atlSignupTitle')}</h1>
            <p className="atl-auth-sub">{t('atlSignupSub')}</p>

            <form onSubmit={handleSubmit} className="atl-auth-form">
                <div className="atl-field">
                    <label htmlFor="name" className="atl-field-label">{t('atlFullName')}</label>
                    <input
                        id="name"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="atl-input"
                        placeholder={t('yourName')}
                        autoComplete="name"
                        required
                    />
                </div>

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
                    <label htmlFor="password" className="atl-field-label">{t('atlPassword')}</label>
                    <input
                        id="password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="atl-input"
                        placeholder="••••••••"
                        autoComplete="new-password"
                        required
                    />
                    <p className="atl-hint">{t('atlPasswordRule')}</p>
                </div>

                <button type="submit" disabled={isLoading} className="atl-btn atl-btn-primary">
                    {isLoading ? (
                        <><span className="atl-spin" /><span>{t('atlCreating')}</span></>
                    ) : (
                        <span>{t('atlCreateAccount')}</span>
                    )}
                </button>
            </form>

            {error && (
                <div className="atl-alert atl-alert-error" style={{ marginTop: 16 }}>
                    {error}
                    {showLoginLink && (
                        <div className="atl-alert-inline">
                            <Link href="/login" className="atl-link">{t('goToLogin')}</Link>
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
                <Link href="/login" className="atl-link">{t('atlHaveAccount')}</Link>
            </div>
        </AtelierAuthShell>
    );
}

"use client";

/**
 * /profile — the editorial profile experience (owner design 2026-07-17).
 *
 * This page is a thin auth + data shell: identity gating and load/error/empty
 * states live here; the whole rendered experience (hero, section rail, dirty
 * save bar, documents, integrations, billing) lives in ProfileEditorial.
 *
 * Auth contract (pinned by __tests__/auth-guard.test.tsx):
 *  - no <main> and no profile request until an authenticated identity is
 *    confirmed; guests are redirected to /login?next=/profile behind the
 *    neutral AuthGate loader.
 */

import { AuthGate } from "@/components/auth/AuthGate";
import { ProfileEditorial } from "@/components/profile/ProfileEditorial";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { ToastContainer } from "@/components/ui/Toast";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useToast } from "@/hooks/useToast";
import { ApiError, fetchProfile, type ProfileResponse } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import { Suspense, useCallback, useEffect, useState } from "react";

export default function ProfilePage() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const { toasts, toast } = useToast();
    const { authorized } = useRequireAuth();

    const [profile, setProfile] = useState<ProfileResponse | null>(null);
    const [error, setError] = useState<"auth" | "other" | null>(null);
    const [loading, setLoading] = useState(true);

    const loadProfile = useCallback(async () => {
        try {
            const data = await fetchProfile();
            setProfile(data);
            setError(null);
        } catch (err: unknown) {
            const is401 = err instanceof ApiError && err.statusCode === 401;
            setError(is401 ? "auth" : "other");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        // Do not fire the private profile request until an authenticated
        // identity is confirmed (guests never trigger it).
        if (!authorized) return;
        const timeoutId = window.setTimeout(() => {
            void loadProfile();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [authorized, loadProfile]);

    const handleRetry = useCallback(() => {
        setError(null);
        setLoading(true);
        void loadProfile();
    }, [loadProfile]);

    // Never render the private shell until an authenticated identity is confirmed.
    if (!authorized) return <AuthGate />;

    return (
        <WorkspaceShell>
            <div
                dir={language === "ar" ? "rtl" : "ltr"}
                lang={language}
                className="w-full max-w-6xl py-3 text-start sm:py-4"
            >
                {loading && <LoadingState variant="card" message={t("profileLoading")} />}

                {!loading && error && (
                    <ErrorState
                        variant={error === "auth" ? "auth" : "network"}
                        title={error === "auth" ? t("profileAuthRequired") : t("profileConnectionFailed")}
                        message={error === "auth" ? t("profileAuthRequiredMsg") : t("profileConnectionFailedMsg")}
                        onRetry={handleRetry}
                    />
                )}

                {!loading && !error && profile && !profile.profile_exists && (
                    <div className="flex flex-col gap-4">
                        <EmptyState
                            title={t("profileNoProfileTitle")}
                            description={t("profileNoProfileDesc")}
                            actionLabel={t("profileStartSetup")}
                            actionHref="/command"
                        />

                        <div className="rounded-xl border border-border-soft bg-surface-elevated/70 p-5">
                            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                                {t("profileWhatRicoSetsUp")}
                            </h3>
                            <ul className="flex flex-col gap-2 text-sm text-text-secondary">
                                {[
                                    t("profileSetupRoles"),
                                    t("profileSetupCities"),
                                    t("profileSetupSalary"),
                                    t("profileSetupExperience"),
                                    t("profileSetupVisa"),
                                ].map((item) => (
                                    <li key={item} className="flex items-start gap-2">
                                        <span className="mt-0.5 text-gold">·</span>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                )}

                {!loading && !error && profile?.profile_exists && (
                    // ProfileEditorial reads ?section= via useSearchParams — Next 14
                    // requires that consumer to sit under a Suspense boundary.
                    <Suspense fallback={<LoadingState variant="card" message={t("profileLoading")} />}>
                        <ProfileEditorial profile={profile} refresh={loadProfile} notify={toast} />
                    </Suspense>
                )}
            </div>
            <ToastContainer toasts={toasts} />
        </WorkspaceShell>
    );
}

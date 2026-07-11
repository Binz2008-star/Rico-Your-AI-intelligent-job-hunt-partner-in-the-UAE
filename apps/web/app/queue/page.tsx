"use client";

import { AppShell } from "@/components/layout/AppShell";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { ApplicationDraftCard } from "@/components/queue/ApplicationDraftCard";
import {
    getApplicationQueue,
    getFollowUpReminders,
    approveApplication,
    rejectApplication,
    type ApplicationDraft,
} from "@/lib/api";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { AuthGate } from "@/components/auth/AuthGate";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import { useCallback, useEffect, useState } from "react";

export default function QueuePage() {
    // Authenticated-only: guests are redirected to /login?next=/queue and see a
    // neutral loader (never the private AppShell); no private API fires until an
    // authenticated identity is confirmed.
    const { user, authorized, logout: doLogout } = useRequireAuth();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [drafts, setDrafts] = useState<ApplicationDraft[]>([]);
    const [followUps, setFollowUps] = useState<ApplicationDraft[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!authorized) return;
        const ctrl = new AbortController();
        setLoading(true);
        Promise.all([
            getApplicationQueue(ctrl.signal),
            getFollowUpReminders(ctrl.signal).catch(() => [] as ApplicationDraft[]),
        ])
            .then(([queue, reminders]) => {
                setDrafts(queue);
                setFollowUps(reminders);
                setError(null);
            })
            .catch((err) => {
                if (err.name !== "AbortError") setError(t("queueErrLoad"));
            })
            .finally(() => setLoading(false));
        return () => ctrl.abort();
    }, [authorized, t]);

    const handleApprove = useCallback(async (id: string) => {
        await approveApplication(id);
        setDrafts((prev) => prev.filter((d) => d.id !== id));
    }, []);

    const handleReject = useCallback(async (id: string) => {
        await rejectApplication(id);
        setDrafts((prev) => prev.filter((d) => d.id !== id));
    }, []);

    const handleLogout = useCallback(async () => {
        await doLogout();
    }, [doLogout]);

    if (!authorized) return <AuthGate />;

    return (
        <AppShell
            title={t("queueTitle")}
            subtitle={t("queueSubtitle")}
            sidebarProps={{ user: user ?? undefined, onLogout: handleLogout }}
        >
            {loading ? (
                <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                        <div
                            key={i}
                            className="h-64 animate-pulse rounded-xl border border-overlay/10 bg-surface-subtle/40 motion-reduce:animate-none"
                        />
                    ))}
                </div>
            ) : error ? (
                <div className="flex flex-col items-center gap-3 py-20 text-center">
                    <MaterialIcon icon="error_outline" size={40} className="text-text-tertiary" />
                    <p className="text-text-secondary">{error}</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="mt-2 rounded-lg border border-overlay/10 px-4 py-2 text-sm text-text-secondary hover:bg-surface-subtle"
                    >
                        {t("queueRetry")}
                    </button>
                </div>
            ) : drafts.length === 0 ? (
                <div className="flex flex-col items-center gap-4 py-24 text-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gold/10">
                        <MaterialIcon icon="rocket_launch" size={32} className="text-gold" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-text-primary">{t("queueEmptyTitle")}</h2>
                        <p className="mt-2 max-w-md text-sm leading-relaxed text-text-secondary">
                            {t("queueEmptyDesc")}
                        </p>
                        <p className="mt-1.5 max-w-md text-sm text-text-tertiary">
                            {t("queueEmptyHint")}
                        </p>
                    </div>
                    <a
                        href="/command"
                        className="mt-2 flex items-center gap-2 rounded-lg bg-gold px-5 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
                    >
                        <MaterialIcon icon="auto_awesome" size={16} />
                        {t("queueAskRico")}
                    </a>
                </div>
            ) : (
                <div className="space-y-6">
                    <div className="flex items-center gap-3 rounded-xl border border-gold/20 bg-gold/5 px-5 py-4">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gold/15">
                            <MaterialIcon icon="task_alt" size={18} className="text-gold" />
                        </div>
                        <div>
                            <p className="text-sm font-semibold text-gold">{t("queueApproveBanner")}</p>
                            <p className="mt-0.5 text-xs leading-relaxed text-text-tertiary">
                                {t("queueApproveBannerDesc")}
                            </p>
                        </div>
                    </div>

                    {followUps.length > 0 && (
                        <div className="rounded-xl border border-overlay/10 bg-surface-subtle/40 px-5 py-4">
                            <div className="mb-3 flex items-center gap-2">
                                <MaterialIcon icon="history" size={16} className="text-text-tertiary" />
                                <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                                    {t("queueFollowUpDue")}
                                </p>
                            </div>
                            <div className="space-y-2">
                                {followUps.map((fu) => (
                                    <div key={fu.id} className="flex items-center justify-between gap-3">
                                        <div className="min-w-0">
                                            <span className="truncate text-sm font-medium text-text-primary">{fu.job_title}</span>
                                            <span className="ms-2 text-xs text-text-tertiary">{fu.company}</span>
                                        </div>
                                        {fu.apply_url && (
                                            <a
                                                href={fu.apply_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="shrink-0 text-xs text-gold underline-offset-2 hover:underline"
                                            >
                                                {t("queueSendFollowUp")} ↗
                                            </a>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <p className="text-sm text-text-secondary">
                        <span className="font-semibold text-text-primary">{drafts.length}</span>{" "}
                        {drafts.length === 1 ? t("queueReadyCount") : t("queueReadyCountPlural")} —{" "}
                        <span className="text-text-tertiary">{t("queueApproveToSend")}</span>
                    </p>
                    {drafts.map((draft) => (
                        <ApplicationDraftCard
                            key={draft.id}
                            draft={draft}
                            onApprove={handleApprove}
                            onReject={handleReject}
                        />
                    ))}
                </div>
            )}
        </AppShell>
    );
}

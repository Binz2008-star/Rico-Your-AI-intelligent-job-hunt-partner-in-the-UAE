"use client";

import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { ApplicationDraftCard } from "@/components/queue/ApplicationDraftCard";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import {
    approveApplication,
    getApplicationQueue,
    getFollowUpReminders,
    rejectApplication,
    type ApplicationDraft,
} from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const COPY = {
    en: {
        eyebrow: "Application queue",
        title: "Ready for your review.",
        intro: "Approve the applications Rico prepared, or send them back before anything leaves your workspace.",
        reviewLabel: "Review queue",
        followUpLabel: "Follow-ups due",
    },
    ar: {
        eyebrow: "قائمة الطلبات",
        title: "جاهزة لمراجعتك.",
        intro: "راجع الطلبات التي جهزها ريكو ووافق عليها أو أعدها قبل إرسال أي شيء من مساحة عملك.",
        reviewLabel: "قائمة المراجعة",
        followUpLabel: "متابعات مستحقة",
    },
} as const;

export function QueueAtelier() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    const copy = COPY[language];
    const [drafts, setDrafts] = useState<ApplicationDraft[]>([]);
    const [followUps, setFollowUps] = useState<ApplicationDraft[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        const ctrl = new AbortController();
        setLoading(true);
        setError(null);

        Promise.all([
            getApplicationQueue(ctrl.signal),
            getFollowUpReminders(ctrl.signal).catch(() => [] as ApplicationDraft[]),
        ])
            .then(([queue, reminders]) => {
                setDrafts(queue);
                setFollowUps(reminders);
            })
            .catch((err: unknown) => {
                if (err instanceof Error && err.name === "AbortError") return;
                setError(t("queueErrLoad"));
            })
            .finally(() => {
                if (!ctrl.signal.aborted) setLoading(false);
            });

        return () => ctrl.abort();
    }, [reloadKey, t]);

    const handleApprove = useCallback(async (id: string) => {
        await approveApplication(id);
        setDrafts((current) => current.filter((draft) => draft.id !== id));
    }, []);

    const handleReject = useCallback(async (id: string) => {
        await rejectApplication(id);
        setDrafts((current) => current.filter((draft) => draft.id !== id));
    }, []);

    return (
        <main
            dir={language === "ar" ? "rtl" : "ltr"}
            className="mx-auto w-full max-w-[1180px] px-5 py-8 sm:px-8 sm:py-10 lg:px-10"
            style={{ color: c.ink, fontFamily: ATELIER_FONT.body }}
        >
            <header className="border-b pb-7" style={{ borderColor: c.hair }}>
                <Mono style={{ color: c.red }}>{copy.eyebrow}</Mono>
                <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-end">
                    <h1
                        className="max-w-3xl text-[38px] leading-[0.98] sm:text-[52px]"
                        style={{ fontFamily: ATELIER_FONT.serif, color: c.ink }}
                    >
                        {copy.title}
                    </h1>
                    <p className="max-w-xl text-sm leading-6" style={{ color: c.ink55 }}>
                        {copy.intro}
                    </p>
                </div>
            </header>

            <section className="mt-7" aria-labelledby="queue-review-heading">
                <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                    <div>
                        <Mono style={{ color: c.ink40 }}>{copy.reviewLabel}</Mono>
                        <h2 id="queue-review-heading" className="mt-1 text-xl font-semibold" style={{ color: c.ink }}>
                            {drafts.length} {drafts.length === 1 ? t("queueReadyCount") : t("queueReadyCountPlural")}
                        </h2>
                    </div>
                    {!loading && !error && drafts.length > 0 && (
                        <p className="text-xs" style={{ color: c.ink40 }}>{t("queueApproveToSend")}</p>
                    )}
                </div>

                {loading ? (
                    <div className="grid gap-4" role="status" aria-live="polite">
                        <span className="sr-only">{t("loading")}</span>
                        {[1, 2, 3].map((item) => (
                            <div
                                key={item}
                                className="h-48 animate-pulse rounded-[6px] border motion-reduce:animate-none"
                                style={{ borderColor: c.hair, background: c.activeBg }}
                            />
                        ))}
                    </div>
                ) : error ? (
                    <div className="rounded-[6px] border px-6 py-12 text-center" style={{ borderColor: c.hair, background: c.panel }}>
                        <MaterialIcon icon="error_outline" size={34} style={{ color: c.red }} />
                        <p className="mt-3 text-sm" style={{ color: c.ink70 }}>{error}</p>
                        <button
                            type="button"
                            onClick={() => setReloadKey((key) => key + 1)}
                            className="mt-5 rounded-[4px] border px-4 py-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
                            style={{ borderColor: c.ink, color: c.ink, background: c.panel }}
                        >
                            {t("queueRetry")}
                        </button>
                    </div>
                ) : drafts.length === 0 ? (
                    <div className="rounded-[6px] border px-6 py-14 text-center" style={{ borderColor: c.hair, background: c.panel }}>
                        <div
                            className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border"
                            style={{ borderColor: c.hair, color: c.red, background: c.activeBg }}
                        >
                            <MaterialIcon icon="rocket_launch" size={27} />
                        </div>
                        <h2 className="mt-5 text-2xl" style={{ fontFamily: ATELIER_FONT.serif, color: c.ink }}>
                            {t("queueEmptyTitle")}
                        </h2>
                        <p className="mx-auto mt-2 max-w-lg text-sm leading-6" style={{ color: c.ink55 }}>
                            {t("queueEmptyDesc")}
                        </p>
                        <p className="mx-auto mt-1 max-w-lg text-xs" style={{ color: c.ink40 }}>
                            {t("queueEmptyHint")}
                        </p>
                        <Link
                            href="/command"
                            className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-[4px] px-5 py-2.5 text-sm font-semibold text-white transition-transform hover:-translate-y-0.5"
                            style={{ background: c.red }}
                        >
                            <MaterialIcon icon="auto_awesome" size={16} />
                            {t("queueAskRico")}
                        </Link>
                    </div>
                ) : (
                    <div className="grid gap-4">
                        <div className="flex items-start gap-3 rounded-[6px] border px-4 py-4" style={{ borderColor: c.hair, background: c.activeBg }}>
                            <MaterialIcon icon="task_alt" size={19} style={{ color: c.red }} />
                            <div>
                                <p className="text-sm font-semibold" style={{ color: c.ink }}>{t("queueApproveBanner")}</p>
                                <p className="mt-1 text-xs leading-5" style={{ color: c.ink55 }}>{t("queueApproveBannerDesc")}</p>
                            </div>
                        </div>
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
            </section>

            {!loading && followUps.length > 0 && (
                <section className="mt-10 border-t pt-7" style={{ borderColor: c.hair }} aria-labelledby="queue-followups-heading">
                    <Mono style={{ color: c.red }}>{copy.followUpLabel}</Mono>
                    <h2 id="queue-followups-heading" className="mt-1 text-xl" style={{ fontFamily: ATELIER_FONT.serif, color: c.ink }}>
                        {t("queueFollowUpDue")}
                    </h2>
                    <div className="mt-4 divide-y rounded-[6px] border" style={{ borderColor: c.hair, background: c.panel }}>
                        {followUps.map((followUp) => (
                            <div key={followUp.id} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between" style={{ borderColor: c.hair }}>
                                <div className="min-w-0">
                                    <p className="truncate text-sm font-semibold" style={{ color: c.ink }}>{followUp.job_title}</p>
                                    <p className="mt-0.5 truncate text-xs" style={{ color: c.ink55 }}>{followUp.company}</p>
                                </div>
                                {followUp.apply_url && (
                                    <a
                                        href={followUp.apply_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="shrink-0 text-sm font-semibold underline-offset-4 hover:underline"
                                        style={{ color: c.red }}
                                    >
                                        {t("queueSendFollowUp")} ↗
                                    </a>
                                )}
                            </div>
                        ))}
                    </div>
                </section>
            )}
        </main>
    );
}

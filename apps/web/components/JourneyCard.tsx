"use client";

import {
    ApiError,
    getJourneyToday,
    type JourneyPlanAction,
    type JourneySnapshot,
    type JourneyStage,
    type JourneyToday,
} from "@/lib/api";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const STAGES: JourneyStage[] = [
    "discovery",
    "searching",
    "applying",
    "interviewing",
    "offer",
];

const STAGE_LABEL_KEYS: Record<JourneyStage, TranslationKey> = {
    discovery: "journeyStageDiscovery",
    searching: "journeyStageSearching",
    applying: "journeyStageApplying",
    interviewing: "journeyStageInterviewing",
    offer: "journeyStageOffer",
};

const ACTION_LABEL_KEYS: Record<string, TranslationKey> = {
    search: "journeyActionSearch",
    review_matches: "journeyActionReviewMatches",
    apply: "journeyActionApply",
    follow_up: "journeyActionFollowUp",
    review_drafts: "journeyActionReviewDrafts",
    interview_prep: "journeyActionInterviewPrep",
    review_offer: "journeyActionReviewOffer",
    check_in: "journeyActionCheckIn",
};

const PRIORITY_KEYS: Record<JourneyPlanAction["priority"], TranslationKey> = {
    high: "journeyPriorityHigh",
    medium: "journeyPriorityMedium",
    low: "journeyPriorityLow",
};

const PRIORITY_STYLES: Record<JourneyPlanAction["priority"], string> = {
    high: "bg-gold/10 text-gold ring-1 ring-gold/25",
    medium: "bg-rico-amber/10 text-text-secondary ring-1 ring-rico-amber/25",
    low: "bg-surface-glass text-text-tertiary ring-1 ring-border-soft",
};

function actionCount(action: JourneyPlanAction, journey: JourneySnapshot): number {
    switch (action.action) {
        case "apply":
            return journey.saved_count;
        case "follow_up":
            return journey.follow_up_due_count;
        default:
            return 0;
    }
}

type LoadState =
    | { status: "loading" }
    | { status: "error" }
    | { status: "ready"; data: JourneyToday };

export function JourneyCard() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const [state, setState] = useState<LoadState>({ status: "loading" });

    const load = useCallback(async (signal?: AbortSignal) => {
        setState({ status: "loading" });
        try {
            const data = await getJourneyToday(signal);
            setState({ status: "ready", data });
        } catch (err) {
            if (err instanceof Error && err.name === "AbortError") return;
            if (err instanceof ApiError && err.statusCode === 401) {
                // Auth is handled by the page shell; render nothing rather than
                // an error card for a signed-out flash.
                setState({ status: "error" });
                return;
            }
            setState({ status: "error" });
        }
    }, []);

    useEffect(() => {
        const controller = new AbortController();
        void load(controller.signal);
        return () => controller.abort();
    }, [load]);

    if (state.status === "loading") {
        return (
            <div
                data-testid="journey-loading"
                className="rounded-2xl border border-border-soft bg-surface-glass p-6"
            >
                <div className="h-4 w-40 animate-pulse rounded bg-border-soft" />
                <div className="mt-4 h-3 w-full animate-pulse rounded bg-border-soft" />
                <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-border-soft" />
                <span className="sr-only">{t("journeyLoading")}</span>
            </div>
        );
    }

    if (state.status === "error") {
        return (
            <div
                data-testid="journey-error"
                className="rounded-2xl border border-rico-red/25 bg-surface-glass p-6"
            >
                <p className="text-sm text-text-secondary">{t("journeyErrorText")}</p>
                <button
                    type="button"
                    onClick={() => void load()}
                    className="mt-3 inline-flex items-center rounded-full border border-border-soft px-4 py-1.5 text-xs font-semibold text-text-primary transition-colors hover:border-gold/40"
                >
                    {t("retry")}
                </button>
            </div>
        );
    }

    const { journey, plan } = state.data;
    const currentIndex = STAGES.indexOf(journey.state);
    const isEmpty =
        journey.state === "discovery" &&
        journey.saved_count === 0 &&
        journey.prepared_count === 0 &&
        journey.applied_count === 0 &&
        journey.interviewing_count === 0 &&
        journey.offer_count === 0;

    const counts: Array<{ key: TranslationKey; value: number; testId: string }> = [
        { key: "journeyCountSaved", value: journey.saved_count, testId: "journey-count-saved" },
        { key: "journeyCountPrepared", value: journey.prepared_count, testId: "journey-count-prepared" },
        { key: "journeyCountApplied", value: journey.applied_count, testId: "journey-count-applied" },
        { key: "journeyCountFollowUps", value: journey.follow_up_due_count, testId: "journey-count-followups" },
        { key: "journeyCountInterviews", value: journey.interviewing_count, testId: "journey-count-interviews" },
        { key: "journeyCountOffers", value: journey.offer_count, testId: "journey-count-offers" },
    ];

    return (
        <div
            data-testid="journey-card"
            className="rounded-2xl border border-border-soft bg-surface-glass p-6"
        >
            {/* Stage header */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
                        {t("journeyStageLabel")}
                    </p>
                    <p
                        data-testid="journey-stage"
                        className="font-headline mt-1 text-2xl font-semibold text-text-primary"
                    >
                        {t(STAGE_LABEL_KEYS[journey.state])}
                    </p>
                </div>

                {/* Stage stepper — flex order follows document direction (RTL-safe) */}
                <ol className="flex items-center gap-2" aria-label={t("journeyCardTitle")}>
                    {STAGES.map((stage, i) => (
                        <li key={stage} className="flex items-center gap-2">
                            <span
                                data-testid={`journey-step-${stage}`}
                                data-active={i <= currentIndex}
                                title={t(STAGE_LABEL_KEYS[stage])}
                                className={
                                    i <= currentIndex
                                        ? "h-2.5 w-2.5 rounded-full bg-gold shadow-[0_0_10px_rgba(245,166,35,0.6)]"
                                        : "h-2.5 w-2.5 rounded-full bg-border-soft"
                                }
                            />
                            {i < STAGES.length - 1 && (
                                <span className="h-px w-4 bg-border-soft" aria-hidden />
                            )}
                        </li>
                    ))}
                </ol>
            </div>

            {isEmpty ? (
                <div data-testid="journey-empty" className="mt-5">
                    <p className="text-sm font-semibold text-text-primary">{t("journeyEmptyTitle")}</p>
                    <p className="mt-1 text-sm text-text-tertiary">{t("journeyEmptyDesc")}</p>
                    <Link
                        href="/command"
                        className="mt-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-xs font-semibold text-primary transition-all hover:bg-primary/15"
                    >
                        {t("journeyEmptyCta")}
                    </Link>
                </div>
            ) : (
                <>
                    {/* Counts */}
                    <div className="mt-5 flex flex-wrap gap-2">
                        {counts.map(({ key, value, testId }) => (
                            <span
                                key={key}
                                data-testid={testId}
                                className="inline-flex items-center gap-1.5 rounded-full border border-border-soft px-3 py-1 text-xs text-text-secondary"
                            >
                                <span className="font-semibold text-text-primary">{value}</span>
                                {t(key)}
                            </span>
                        ))}
                    </div>

                    {/* Today's plan */}
                    <div className="mt-6">
                        <h3 className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
                            {t("journeyTodayTitle")}
                        </h3>
                        <ul data-testid="journey-plan" className="mt-3 flex flex-col gap-2.5">
                            {plan.actions.map((action, i) => {
                                const key = ACTION_LABEL_KEYS[action.action];
                                const count = actionCount(action, journey);
                                const message = key
                                    ? t(key).replace("{count}", String(count))
                                    : action.message;
                                return (
                                    <li
                                        key={`${action.action}-${i}`}
                                        className="flex items-start gap-3 rounded-xl border border-border-soft bg-surface-glass px-4 py-3"
                                    >
                                        <span
                                            className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${PRIORITY_STYLES[action.priority] ?? PRIORITY_STYLES.low}`}
                                        >
                                            {t(PRIORITY_KEYS[action.priority] ?? "journeyPriorityLow")}
                                        </span>
                                        <span className="text-sm leading-relaxed text-text-secondary">
                                            {message}
                                        </span>
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                </>
            )}
        </div>
    );
}

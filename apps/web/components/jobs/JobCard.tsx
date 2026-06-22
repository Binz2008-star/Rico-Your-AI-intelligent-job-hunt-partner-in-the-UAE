"use client";

import { Button } from "@/components/ui/Button";
import { ScoreBadge } from "@/components/ui/ScoreBadge";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { cn } from "@/lib/utils";
import type { Job, MatchExplanation } from "@/types";
import { useMemo, useState } from "react";

interface JobCardProps {
    job: Job;
    onAction?: (jobId: string, action: string) => Promise<void>;
    isSubmitting?: boolean;
    className?: string;
}

type JobAction = "apply" | "mark_applied" | "save" | "ignore";

const LOGO_COLORS = [
    "from-amber-500/20 to-amber-400/10 text-amber-200",
    "from-fuchsia-500/20 to-pink-400/10 text-pink-200",
    "from-violet-500/20 to-fuchsia-400/10 text-violet-200",
    "from-emerald-500/20 to-cyan-400/10 text-emerald-200",
    "from-amber-500/20 to-orange-400/10 text-amber-100",
];

type VerdictKey = "jobCardStrongFit" | "jobCardWorthChecking" | "jobCardLowAlignment";

const VERDICT_KEYS: Record<MatchExplanation["verdict"], VerdictKey> = {
    strong_fit: "jobCardStrongFit",
    worth_checking: "jobCardWorthChecking",
    weak_fit: "jobCardLowAlignment",
};

const VERDICT_STYLES: Record<MatchExplanation["verdict"], string> = {
    strong_fit: "bg-emerald-500/10 text-emerald-200 border-emerald-400/20",
    worth_checking: "bg-amber-500/10 text-amber-100 border-amber-400/20",
    weak_fit: "bg-rose-500/10 text-rose-200 border-rose-400/20",
};

function getCompanyIdentity(company?: string) {
    const name = company?.trim() || "Unknown";
    const initials = name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((word) => word[0])
        .join("")
        .toUpperCase() || "?";

    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }

    return {
        initials,
        colorClass: LOGO_COLORS[Math.abs(hash) % LOGO_COLORS.length],
    };
}

function getJobMeta(job: Job) {
    return [job.company || "Unknown", job.location || "Remote"].filter(Boolean).join(" · ");
}

function hasUsableUrl(value?: string): boolean {
    const normalized = value?.trim();
    return Boolean(normalized && normalized !== "#");
}

function BulletList({ items, tone }: { items: string[]; tone: "gold" | "fuchsia" }) {
    if (items.length === 0) return null;

    return (
        <ul className="space-y-2 text-[12px] leading-relaxed text-[rgba(255,255,255,0.72)]">
            {items.map((item, idx) => (
                <li key={`${tone}-${idx}-${item}`} className="flex gap-2">
                    <span
                        aria-hidden="true"
                        className={cn(
                            "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                            tone === "gold" ? "bg-gold" : "bg-fuchsia-300"
                        )}
                    />
                    <span>{item}</span>
                </li>
            ))}
        </ul>
    );
}

function MatchExplanationPanel({ explanation, t }: { explanation: MatchExplanation; t: (k: TranslationKey) => string }) {
    return (
        <section
            aria-label="Rico match analysis"
            className="relative z-10 mt-4 rounded-[24px] border border-overlay/8 bg-surface-elevated/50 p-4 md:p-5 backdrop-blur-sm"
        >
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className="rico-kicker mb-1">{t("jobCardMatchAnalysis")}</p>
                    <span
                        className={cn(
                            "inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em]",
                            VERDICT_STYLES[explanation.verdict]
                        )}
                    >
                        {t(VERDICT_KEYS[explanation.verdict])}
                    </span>
                </div>

                <div className="rounded-full border border-gold/15 bg-gold/5 px-3 py-1 text-[10px] uppercase tracking-[0.16em] text-gold/80">
                    {explanation.confidence} confidence
                </div>
            </div>

            {explanation.summary && (
                <p className="mb-5 text-[13px] leading-relaxed text-[rgba(255,255,255,0.82)]">
                    {explanation.summary}
                </p>
            )}

            <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-overlay/6 bg-surface/50 p-4">
                    <p className="rico-kicker mb-2">{t("jobCardWhyLikes")}</p>
                    <BulletList items={explanation.why_this_fits} tone="gold" />
                </div>

                <div className="rounded-2xl border border-overlay/6 bg-surface/50 p-4">
                    <p className="rico-kicker mb-2">{t("jobCardWorthChecking")}</p>
                    <BulletList items={explanation.worth_checking} tone="fuchsia" />
                </div>
            </div>

            <div className="mt-4 rounded-2xl border border-gold/15 bg-gold/[0.05] p-4">
                <p className="rico-kicker mb-2">{t("jobCardRecommendedStep")}</p>
                <p className="text-[13px] leading-relaxed text-[rgba(255,255,255,0.8)]">
                    {explanation.recommended_next_step}
                </p>
            </div>
        </section>
    );
}

export function JobCard({ job, onAction, isSubmitting, className }: JobCardProps) {
    const [localAction, setLocalAction] = useState<JobAction | null>(null);
    const [isDone, setIsDone] = useState(false);
    const [showMarkApplied, setShowMarkApplied] = useState(false);
    const { language } = useLanguage();
    const t = useTranslation(language);

    const companyIdentity = useMemo(() => getCompanyIdentity(job.company), [job.company]);
    const isBusy = Boolean(localAction || isSubmitting);
    // Canonical link gate: prefer the backend's usable_link / link_unavailable
    // signal; fall back to inspecting the URL fields for older responses. When
    // there is no trusted link we must NOT render a dead-end "Apply" button.
    const linkUnavailable =
        typeof job.link_unavailable === "boolean"
            ? job.link_unavailable
            : !(hasUsableUrl(job.usable_link) || hasUsableUrl(job.apply_url) || hasUsableUrl(job.source_url));
    const fallbackSearchUrl = `https://www.google.com/search?q=${encodeURIComponent(
        [job.title, job.company, job.location, "careers"].filter(Boolean).join(" "),
    )}`;
    const isLive =
        job.verification_status === "live"
            ? true
            : job.verification_status === "lead_needs_verification"
                ? false
                : hasUsableUrl(job.usable_link) || hasUsableUrl(job.apply_url) || hasUsableUrl(job.source_url);
    const verificationBadge = isLive
        ? {
            label: t("jobCardLiveBadge"),
            className: "border-emerald-400/20 bg-emerald-500/10 text-emerald-100",
        }
        : {
            label: t("jobCardLeadBadge"),
            className: "border-amber-400/25 bg-amber-500/10 text-amber-100",
        };

    const handleActionClick = async (action: JobAction) => {
        if (!onAction || isBusy) return;
        setLocalAction(action);
        try {
            await onAction(job.job_id, action);
            if (action === "apply") {
                setShowMarkApplied(true);
            } else {
                setIsDone(true);
            }
        } finally {
            setLocalAction(null);
        }
    };

    return (
        <article
            aria-label={`${job.title || "Untitled role"} at ${job.company || "Unknown company"}`}
            className={cn(
                "rico-card group rounded-[28px] p-5 md:p-6 transition-all duration-300",
                "hover:-translate-y-1 hover:scale-[1.01] hover:border-[rgba(245,166,35,0.18)] hover:shadow-[0_30px_90px_rgba(0,0,0,0.42)]",
                isDone && "opacity-60 grayscale-[0.3]",
                className
            )}
        >
            <div className="absolute inset-0 pointer-events-none opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                <div className="absolute start-0 top-0 h-40 w-40 rounded-full bg-gold/[0.06] blur-3xl animate-pulse" />
                <div className="absolute bottom-0 end-0 h-40 w-40 rounded-full bg-gold/[0.04] blur-3xl animate-pulse" />
            </div>

            <div className="relative z-10 flex gap-4 items-start">
                <div
                    aria-hidden="true"
                    className={cn(
                        "flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br text-sm font-bold shadow-inner",
                        companyIdentity.colorClass
                    )}
                >
                    {companyIdentity.initials}
                </div>

                <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h3 className="text-[17px] font-semibold tracking-[-0.03em] text-white leading-tight">
                                {job.title ?? "Untitled Role"}
                            </h3>
                            <p className="mt-1 truncate text-[13px] text-[rgba(255,255,255,0.48)]">
                                {getJobMeta(job)}
                            </p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-2">
                            <ScoreBadge score={job.score} />
                            <span
                                className={cn(
                                    "max-w-[150px] rounded-full border px-2.5 py-1 text-end text-[10px] font-bold uppercase leading-snug tracking-[0.12em]",
                                    verificationBadge.className
                                )}
                            >
                                {verificationBadge.label}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {job.reason && (
                <section className="relative z-10 mt-4 rounded-2xl border border-overlay/8 bg-surface-elevated/50 p-4 backdrop-blur-sm" aria-label="Rico insight">
                    <p className="rico-kicker mb-2">Rico insight</p>
                    <p className="text-[13px] leading-relaxed text-[rgba(255,255,255,0.68)]">
                        {job.reason}
                    </p>
                </section>
            )}

            {job.match_explanation ? (
                <MatchExplanationPanel explanation={job.match_explanation} t={t} />
            ) : job.score > 0 ? (
                <p className="relative z-10 mt-3 text-[11px] font-mono text-text-tertiary">
                    {t("jobCardScoreNoBreakdown")}
                </p>
            ) : null}

            <div className="relative z-10 mt-4 flex flex-wrap items-center gap-2">
                {(job.salary_range || job.salary) && (
                    <span className="rico-chip-accent rounded-full px-3 py-1 text-[11px] font-semibold">
                        {job.salary_range || job.salary}
                    </span>
                )}

                {Array.isArray(job.tags) && job.tags.map((tag) => (
                    <span key={tag} className="rico-chip rounded-full px-3 py-1 text-[11px]">
                        {tag}
                    </span>
                ))}
            </div>

            {showMarkApplied ? (
                <div className="relative z-10 mt-5 flex gap-2 border-t rico-divider pt-4">
                    <Button
                        variant="teal"
                        size="sm"
                        loading={localAction === "mark_applied" || isSubmitting}
                        onClick={() => handleActionClick("mark_applied")}
                        className="flex-1"
                    >
                        {t("jobCardMarkApplied")}
                    </Button>
                </div>
            ) : !isDone ? (
                <div className="relative z-10 mt-5 flex gap-2 border-t rico-divider pt-4">
                    {linkUnavailable ? (
                        // No trusted apply link — render a safe fallback search CTA
                        // instead of a dead-end Apply button (P0: never link to nothing).
                        <a
                            href={fallbackSearchUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1"
                        >
                            <Button variant="outline" size="sm" className="w-full">
                                {t("jobCardSearchThisJob")}
                            </Button>
                        </a>
                    ) : (
                        <Button
                            variant="teal"
                            size="sm"
                            loading={localAction === "apply" || isSubmitting}
                            onClick={() => handleActionClick("apply")}
                            className="flex-1"
                        >
                            {t("jobCardApplyNow")}
                        </Button>
                    )}
                    <Button
                        variant="ghost"
                        size="sm"
                        loading={localAction === "save"}
                        onClick={() => handleActionClick("save")}
                    >
                        {t("jobCardSave")}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        loading={localAction === "ignore"}
                        onClick={() => handleActionClick("ignore")}
                    >
                        {t("jobCardIgnore")}
                    </Button>
                </div>
            ) : (
                <div className="relative z-10 mt-5 flex items-center gap-2 border-t rico-divider pt-4">
                    <span aria-hidden="true" className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(74,222,128,0.8)]" />
                    <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[rgba(255,255,255,0.48)]">
                        {t("jobCardDone")}
                    </p>
                </div>
            )}
        </article>
    );
}

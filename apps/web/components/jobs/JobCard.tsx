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
    // WhatsApp share: prefer the job's trusted link; otherwise share the role
    // details with a Rico Hunt reference so the message is never a dead link.
    const shareJobUrl =
        [job.usable_link, job.apply_url, job.source_url].find(hasUsableUrl)?.trim() ??
        "https://ricohunt.com";
    const whatsappHref = `https://wa.me/?text=${encodeURIComponent(
        `${[job.title, job.company, job.location].filter(Boolean).join(" — ")}\n${shareJobUrl}\n\n${t("jobCardShareText")} https://ricohunt.com`,
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
                    <a
                        href={whatsappHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={t("jobCardShare")}
                        title={t("jobCardShare")}
                        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-overlay/10 text-[rgba(255,255,255,0.55)] transition-colors hover:border-emerald-400/40 hover:text-emerald-300"
                    >
                        <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
                            <path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.87 9.87 0 0 0 4.74 1.21c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2zm0 18.15a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.24-8.24 2.2 0 4.27.86 5.82 2.42a8.18 8.18 0 0 1 2.41 5.83c0 4.54-3.7 8.23-8.23 8.23zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.17.24-.64.8-.78.97-.14.16-.29.18-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.12-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.41-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.15-1.18-.06-.1-.23-.16-.48-.29z" />
                        </svg>
                    </a>
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

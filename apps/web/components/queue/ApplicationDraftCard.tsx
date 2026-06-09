"use client";

import { cn } from "@/lib/utils";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import type { ApplicationDraft } from "@/lib/api";
import { useState } from "react";

interface ApplicationDraftCardProps {
    draft: ApplicationDraft;
    onApprove: (id: string) => Promise<void>;
    onReject: (id: string) => Promise<void>;
}

type Tab = "cover_letter" | "cv";

export function ApplicationDraftCard({
    draft,
    onApprove,
    onReject,
}: ApplicationDraftCardProps) {
    const [tab, setTab] = useState<Tab>("cover_letter");
    const [approving, setApproving] = useState(false);
    const [rejecting, setRejecting] = useState(false);
    const [done, setDone] = useState<"approved" | "rejected" | null>(null);
    const { language } = useLanguage();
    const t = useTranslation(language);

    async function handleApprove() {
        setApproving(true);
        try {
            await onApprove(draft.id);
            setDone("approved");
        } finally {
            setApproving(false);
        }
    }

    async function handleReject() {
        setRejecting(true);
        try {
            await onReject(draft.id);
            setDone("rejected");
        } finally {
            setRejecting(false);
        }
    }

    if (done === "rejected") return null;

    return (
        <div
            className={cn(
                "rounded-xl border border-overlay/10 bg-surface/80 backdrop-blur-sm transition-all",
                done === "approved" && "border-green-500/30 bg-green-500/5 opacity-60",
            )}
        >
            {/* Header */}
            <div className="flex items-start justify-between gap-3 px-5 py-4">
                <div className="min-w-0">
                    <h3 className="truncate text-base font-semibold text-text-primary">
                        {draft.job_title}
                    </h3>
                    <p className="mt-0.5 truncate text-sm text-text-secondary">
                        {draft.company}
                    </p>
                </div>
                {done === "approved" ? (
                    <span className="flex shrink-0 items-center gap-1 rounded-full bg-green-500/15 px-2.5 py-1 text-xs font-semibold text-green-400">
                        <MaterialIcon icon="task_alt" size={14} />
                        {t("draftApproved")}
                    </span>
                ) : (
                    <span className="shrink-0 rounded-full bg-gold/10 px-2.5 py-1 text-xs font-semibold text-gold">
                        {t("draftAwaitingReview")}
                    </span>
                )}
            </div>

            {/* Tab switcher */}
            <div className="flex border-b border-overlay/10 px-5">
                {(["cover_letter", "cv"] as Tab[]).map((tabKey) => (
                    <button
                        key={tabKey}
                        onClick={() => setTab(tabKey)}
                        className={cn(
                            "me-4 border-b-2 pb-2 text-sm font-medium transition-colors",
                            tab === tabKey
                                ? "border-gold text-gold"
                                : "border-transparent text-text-tertiary hover:text-text-secondary",
                        )}
                    >
                        {tabKey === "cover_letter" ? t("draftCoverLetter") : t("draftTailoredCv")}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div className="max-h-64 overflow-y-auto px-5 py-4">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-text-secondary">
                    {tab === "cover_letter" ? draft.cover_letter : draft.tailored_cv}
                </pre>
            </div>

            {/* Actions */}
            {done !== "approved" && (
                <div className="flex items-center gap-3 border-t border-overlay/10 px-5 py-4">
                    {draft.apply_url && (
                        <a
                            href={draft.apply_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-text-tertiary underline-offset-2 hover:text-text-secondary hover:underline"
                        >
                            {t("draftViewPosting")}
                        </a>
                    )}
                    <div className="ms-auto flex gap-2">
                        <button
                            onClick={handleReject}
                            disabled={rejecting || approving}
                            aria-label={t("draftDecline")}
                            className="flex items-center gap-1.5 rounded-lg border border-overlay/10 px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:border-red-500/30 hover:bg-red-500/5 hover:text-red-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/40 disabled:opacity-40"
                        >
                            <MaterialIcon icon="close" size={15} />
                            {t("draftDecline")}
                        </button>
                        <button
                            onClick={handleApprove}
                            disabled={approving || rejecting}
                            aria-label={t("draftApprove")}
                            className="flex items-center gap-1.5 rounded-lg bg-gold px-4 py-2 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 disabled:opacity-40"
                        >
                            <MaterialIcon icon="task_alt" size={15} />
                            {approving ? t("draftApproving") : t("draftApprove")}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

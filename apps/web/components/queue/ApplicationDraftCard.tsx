"use client";

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import type { ApplicationDraft } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface ApplicationDraftCardProps {
    draft: ApplicationDraft;
    onApprove: (id: string) => Promise<void>;
    onReject: (id: string) => Promise<void>;
}

type Tab = "cover_letter" | "cv";

export function ApplicationDraftCard({ draft, onApprove, onReject }: ApplicationDraftCardProps) {
    const [tab, setTab] = useState<Tab>("cover_letter");
    const [approving, setApproving] = useState(false);
    const [rejecting, setRejecting] = useState(false);
    const [done, setDone] = useState<"approved" | "rejected" | null>(null);
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();

    // Approved is a "verified receipt" end-state: use the Atelier moss success
    // hue (theme-correct per island), not a raw green. Kept local since the
    // workspace palette has no success token.
    const approved = done === "approved";
    const moss = c.dark ? "#6FBE8F" : "#3A754F";
    const mossBorder = c.dark ? "rgba(111,190,143,0.38)" : "rgba(60,122,82,0.38)";
    const mossBg = c.dark ? "rgba(111,190,143,0.10)" : "rgba(60,122,82,0.08)";

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
        <article
            className={cn("overflow-hidden rounded-[6px] border transition-opacity", approved && "opacity-60")}
            style={{
                borderColor: approved ? mossBorder : c.hair,
                background: c.panel,
                color: c.ink,
                fontFamily: ATELIER_FONT.body,
            }}
        >
            <header className="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
                <div className="min-w-0">
                    <h3 className="truncate text-lg" style={{ fontFamily: ATELIER_FONT.serif, color: c.ink }}>
                        {draft.job_title}
                    </h3>
                    <p className="mt-1 truncate text-sm" style={{ color: c.ink55 }}>{draft.company}</p>
                </div>
                <span
                    className="inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em]"
                    style={{
                        borderColor: approved ? mossBorder : c.hair,
                        color: approved ? moss : c.red,
                        background: approved ? mossBg : c.activeBg,
                    }}
                >
                    <MaterialIcon icon={approved ? "task_alt" : "schedule"} size={13} />
                    {approved ? t("draftApproved") : t("draftAwaitingReview")}
                </span>
            </header>

            <div className="flex border-y px-4 sm:px-5" style={{ borderColor: c.hair }} role="tablist">
                {(["cover_letter", "cv"] as Tab[]).map((tabKey) => {
                    const selected = tab === tabKey;
                    return (
                        <button
                            type="button"
                            role="tab"
                            id={`tab-${tabKey}-${draft.id}`}
                            aria-selected={selected}
                            aria-controls={`panel-${draft.id}`}
                            key={tabKey}
                            onClick={() => setTab(tabKey)}
                            className="me-5 border-b-2 py-3 text-sm font-medium transition-colors"
                            style={{ borderColor: selected ? c.red : "transparent", color: selected ? c.ink : c.ink40 }}
                        >
                            {tabKey === "cover_letter" ? t("draftCoverLetter") : t("draftTailoredCv")}
                        </button>
                    );
                })}
            </div>

            <div
                id={`panel-${draft.id}`}
                role="tabpanel"
                aria-labelledby={`tab-${tab}-${draft.id}`}
                tabIndex={0}
                className="max-h-64 overflow-y-auto px-4 py-5 sm:px-5"
                style={{ background: c.activeBg }}
            >
                <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6" style={{ color: c.ink70 }}>
                    {tab === "cover_letter" ? draft.cover_letter : draft.tailored_cv}
                </pre>
            </div>

            {done !== "approved" && (
                <footer className="flex flex-col gap-3 border-t px-4 py-4 sm:flex-row sm:items-center sm:px-5" style={{ borderColor: c.hair }}>
                    {draft.apply_url && (
                        <a
                            href={draft.apply_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs font-medium underline-offset-4 hover:underline"
                            style={{ color: c.ink55 }}
                        >
                            {t("draftViewPosting")} ↗
                        </a>
                    )}
                    <div className="flex gap-2 sm:ms-auto">
                        <button
                            type="button"
                            onClick={handleReject}
                            disabled={rejecting || approving}
                            aria-label={t("draftDecline")}
                            className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-[4px] border px-3 py-2 text-sm font-semibold transition-transform hover:-translate-y-0.5 disabled:opacity-40 sm:flex-none"
                            style={{ borderColor: c.hair, color: c.ink70, background: c.panel }}
                        >
                            <MaterialIcon icon="close" size={15} />
                            {t("draftDecline")}
                        </button>
                        <button
                            type="button"
                            onClick={handleApprove}
                            disabled={approving || rejecting}
                            aria-label={t("draftApprove")}
                            className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-[4px] px-4 py-2 text-sm font-semibold text-white transition-transform hover:-translate-y-0.5 disabled:opacity-40 sm:flex-none"
                            style={{ background: c.red }}
                        >
                            <MaterialIcon icon="task_alt" size={15} />
                            {approving ? t("draftApproving") : t("draftApprove")}
                        </button>
                    </div>
                </footer>
            )}
        </article>
    );
}

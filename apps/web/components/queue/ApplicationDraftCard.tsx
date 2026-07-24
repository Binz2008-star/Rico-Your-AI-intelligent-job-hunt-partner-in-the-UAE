"use client";

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import type { ApplicationDraft, ApplyActionResponse } from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import { cn } from "@/lib/utils";
import { useRef, useState } from "react";

interface ApplicationDraftCardProps {
    draft: ApplicationDraft;
    /** Perform the approval mutation and return the server's persisted status
     *  envelope. The canonical proof of approval is `ok === true &&
     *  status === "approved"` — nothing else (never absence from the pending
     *  queue) may render the verified receipt. Rejects when the request could
     *  not be completed (network / timeout / non-2xx); such a rejection is
     *  AMBIGUOUS — the mutation may still have persisted server-side. */
    onApprove: (id: string) => Promise<ApplyActionResponse>;
    /** Fired once when approval is canonically confirmed, so the parent can
     *  reconcile counts without unmounting this card's verified end-state. */
    onResolved?: (id: string) => void;
    /** Reload the whole queue from the authoritative source. Used ONLY to
     *  refresh the list after an unconfirmed approval — never as approval proof,
     *  and it never repeats the approval mutation. */
    onReloadQueue?: () => void;
    onReject: (id: string) => Promise<void>;
}

type Tab = "cover_letter" | "cv";

// idle → approving → approved     (response { ok: true, status: "approved" })
//                  → unconfirmed  (rejected request OR resolved-but-not-approved)
type Phase =
    | "idle"
    | "approving"
    | "approved"
    | "unconfirmed"
    | "rejecting"
    | "rejected";

// Surface-local strings for the approval states, following this surface's
// existing local-COPY idiom (see QueueAtelier). Shared keys stay in t().
const COPY = {
    en: {
        // Ambiguous / unconfirmed: a rejected request may have persisted
        // server-side, and the pending-only queue cannot positively prove
        // "approved" vs "rejected". So we never claim failure and never repeat
        // the mutation — the only offered action re-reads the queue.
        unconfirmedTitle: "Approval status could not be confirmed",
        unconfirmedBody:
            "Your approval may have been saved, but we couldn't confirm it. Reload the queue to see the current status — this will not re-send the approval.",
        reloadQueue: "Reload queue",
        savedNote: "Saved to your applications.",
    },
    ar: {
        unconfirmedTitle: "تعذّر تأكيد حالة الموافقة",
        unconfirmedBody:
            "قد تكون موافقتك قد حُفظت، لكن تعذّر تأكيد ذلك. أعد تحميل القائمة لمعرفة الحالة الحالية — لن تُعاد الموافقة.",
        reloadQueue: "إعادة تحميل القائمة",
        savedNote: "حُفظت في طلباتك.",
    },
} as const;

export function ApplicationDraftCard({ draft, onApprove, onResolved, onReloadQueue, onReject }: ApplicationDraftCardProps) {
    const [tab, setTab] = useState<Tab>("cover_letter");
    const [phase, setPhase] = useState<Phase>("idle");
    // Guards against a synchronous double-click sending the mutation twice:
    // the second invocation returns before touching onApprove.
    const inFlight = useRef(false);
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    const copy = COPY[language];

    const approved = phase === "approved";
    const busy = phase === "approving" || phase === "rejecting";

    // Approved is a "verified receipt" end-state: use the Atelier moss success
    // hue (theme-correct per island), not a raw green. Kept local since the
    // workspace palette has no success token.
    const moss = c.dark ? "#6FBE8F" : "#3A754F";
    const mossBorder = c.dark ? "rgba(111,190,143,0.38)" : "rgba(60,122,82,0.38)";
    const mossBg = c.dark ? "rgba(111,190,143,0.10)" : "rgba(60,122,82,0.08)";

    async function runApprove() {
        // Exactly-once guard — a re-entrant click while a mutation is already
        // in flight is ignored, so double-click never double-submits.
        if (inFlight.current) return;
        inFlight.current = true;
        setPhase("approving");
        try {
            let res: ApplyActionResponse;
            try {
                res = await onApprove(draft.id);
            } catch {
                // Ambiguous: the request did not complete cleanly. It MAY have
                // persisted server-side, so we must NOT claim failure and must
                // NOT auto-repeat the mutation.
                setPhase("unconfirmed");
                return;
            }
            // Canonical positive proof — the server's explicit persisted status.
            if (res.ok === true && res.status === "approved") {
                setPhase("approved");
                onResolved?.(draft.id);
            } else {
                // Clean response, but not an approved confirmation → no receipt.
                setPhase("unconfirmed");
            }
        } finally {
            inFlight.current = false;
        }
    }

    // Re-read the queue from the authoritative source. Never repeats the
    // approval mutation. If the draft is no longer pending it leaves the list;
    // if it is still pending the card returns to idle for a fresh decision.
    function reloadQueue() {
        setPhase("idle");
        onReloadQueue?.();
    }

    async function handleReject() {
        setPhase("rejecting");
        try {
            await onReject(draft.id);
            setPhase("rejected");
        } catch {
            setPhase("idle");
        }
    }

    if (phase === "rejected") return null;

    const approveLabel = phase === "approving" ? t("draftApproving") : t("draftApprove");

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

            {approved ? (
                <div className="flex items-center gap-2 border-t px-4 py-3 sm:px-5" style={{ borderColor: c.hair }}>
                    <MaterialIcon icon="verified" size={16} style={{ color: moss }} />
                    <p className="text-xs font-medium" style={{ color: moss }}>{copy.savedNote}</p>
                </div>
            ) : phase === "unconfirmed" ? (
                <div className="border-t px-4 py-4 sm:px-5" style={{ borderColor: c.hair }} role="status" aria-live="polite">
                    <p className="text-sm font-semibold" style={{ color: c.ink }}>{copy.unconfirmedTitle}</p>
                    <p className="mt-1 text-xs leading-5" style={{ color: c.ink55 }}>{copy.unconfirmedBody}</p>
                    <button
                        type="button"
                        onClick={reloadQueue}
                        className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-[4px] border px-4 py-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
                        style={{ borderColor: c.ink, color: c.ink, background: c.panel }}
                    >
                        <MaterialIcon icon="refresh" size={15} />
                        {copy.reloadQueue}
                    </button>
                </div>
            ) : (
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
                            disabled={busy}
                            aria-label={t("draftDecline")}
                            className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-[4px] border px-3 py-2 text-sm font-semibold transition-transform hover:-translate-y-0.5 disabled:opacity-40 sm:flex-none"
                            style={{ borderColor: c.hair, color: c.ink70, background: c.panel }}
                        >
                            <MaterialIcon icon="close" size={15} />
                            {t("draftDecline")}
                        </button>
                        <button
                            type="button"
                            onClick={runApprove}
                            disabled={busy}
                            aria-label={t("draftApprove")}
                            className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-[4px] px-4 py-2 text-sm font-semibold text-white transition-transform hover:-translate-y-0.5 disabled:opacity-40 sm:flex-none"
                            style={{ background: c.red }}
                        >
                            <MaterialIcon icon="task_alt" size={15} />
                            {approveLabel}
                        </button>
                    </div>
                </footer>
            )}
        </article>
    );
}

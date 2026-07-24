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
    /** STEP 1 — perform the approval mutation. Resolves when the mutation call
     *  succeeds; rejects if it failed (nothing persisted). */
    onApprove: (id: string) => Promise<void>;
    /** STEP 2 — canonical read-back. Resolves true only when the persisted
     *  approved state is confirmed against the authoritative source. Performs
     *  no mutation, so it is safe to retry. */
    onConfirm: (id: string) => Promise<boolean>;
    /** Fired once when approval is confirmed, so the parent can reconcile
     *  counts without unmounting this card's verified end-state. */
    onResolved?: (id: string) => void;
    onReject: (id: string) => Promise<void>;
}

type Tab = "cover_letter" | "cv";

// idle → approving → verifying → approved  (happy path)
//                  → verifying → verifyFailed  (mutation ok, read-back not confirmed / errored)
//        → error  (mutation itself failed — nothing persisted)
type Phase =
    | "idle"
    | "approving"
    | "verifying"
    | "approved"
    | "verifyFailed"
    | "error"
    | "rejecting"
    | "rejected";

// Surface-local strings for the read-back states, following this surface's
// existing local-COPY idiom (see QueueAtelier). Shared keys stay in t().
const COPY = {
    en: {
        confirming: "Confirming…",
        verifyFailedTitle: "Approved — but not yet confirmed",
        verifyFailedBody:
            "Your approval was sent, but we couldn't confirm it saved. Retry the check — this will not re-send the approval.",
        retryCheck: "Retry check",
        errorTitle: "Approval didn't go through",
        errorBody: "Nothing was changed. You can try approving again.",
        retryApprove: "Try again",
        savedNote: "Saved to your applications.",
    },
    ar: {
        confirming: "جارٍ التأكيد…",
        verifyFailedTitle: "تمت الموافقة — لكن دون تأكيد بعد",
        verifyFailedBody:
            "أُرسلت موافقتك، لكن تعذّر تأكيد حفظها. أعد المحاولة للتحقق — لن تُعاد الموافقة.",
        retryCheck: "إعادة التحقق",
        errorTitle: "لم تكتمل الموافقة",
        errorBody: "لم يتغيّر شيء. يمكنك المحاولة مجددًا.",
        retryApprove: "إعادة المحاولة",
        savedNote: "حُفظت في طلباتك.",
    },
} as const;

export function ApplicationDraftCard({ draft, onApprove, onConfirm, onResolved, onReject }: ApplicationDraftCardProps) {
    const [tab, setTab] = useState<Tab>("cover_letter");
    const [phase, setPhase] = useState<Phase>("idle");
    const { language } = useLanguage();
    const t = useTranslation(language);
    const c = useWorkspaceTheme();
    const copy = COPY[language];

    const approved = phase === "approved";
    const busy = phase === "approving" || phase === "verifying" || phase === "rejecting";

    // Approved is a "verified receipt" end-state: use the Atelier moss success
    // hue (theme-correct per island), not a raw green. Kept local since the
    // workspace palette has no success token.
    const moss = c.dark ? "#6FBE8F" : "#3A754F";
    const mossBorder = c.dark ? "rgba(111,190,143,0.38)" : "rgba(60,122,82,0.38)";
    const mossBg = c.dark ? "rgba(111,190,143,0.10)" : "rgba(60,122,82,0.08)";

    async function runApprove() {
        // STEP 1 — mutation
        setPhase("approving");
        try {
            await onApprove(draft.id);
        } catch {
            setPhase("error"); // mutation failed — nothing persisted
            return;
        }
        // STEP 2 — canonical read-back
        await runConfirm();
    }

    // Read-back only. Reachable from the happy path AND from a "Retry check"
    // after verifyFailed — it never re-invokes the approval mutation.
    async function runConfirm() {
        setPhase("verifying");
        try {
            const confirmed = await onConfirm(draft.id);
            if (confirmed) {
                setPhase("approved");
                onResolved?.(draft.id);
            } else {
                setPhase("verifyFailed"); // mutation ok, persisted state not confirmed
            }
        } catch {
            setPhase("verifyFailed"); // read-back errored — do NOT claim verified
        }
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

    const approveLabel =
        phase === "approving" ? t("draftApproving")
            : phase === "verifying" ? copy.confirming
                : t("draftApprove");

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
            ) : phase === "verifyFailed" ? (
                <div className="border-t px-4 py-4 sm:px-5" style={{ borderColor: c.hair }} role="status" aria-live="polite">
                    <p className="text-sm font-semibold" style={{ color: c.ink }}>{copy.verifyFailedTitle}</p>
                    <p className="mt-1 text-xs leading-5" style={{ color: c.ink55 }}>{copy.verifyFailedBody}</p>
                    <button
                        type="button"
                        onClick={runConfirm}
                        className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-[4px] border px-4 py-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
                        style={{ borderColor: c.ink, color: c.ink, background: c.panel }}
                    >
                        <MaterialIcon icon="refresh" size={15} />
                        {copy.retryCheck}
                    </button>
                </div>
            ) : phase === "error" ? (
                <div className="border-t px-4 py-4 sm:px-5" style={{ borderColor: c.hair }} role="alert">
                    <p className="text-sm font-semibold" style={{ color: c.ink }}>{copy.errorTitle}</p>
                    <p className="mt-1 text-xs leading-5" style={{ color: c.ink55 }}>{copy.errorBody}</p>
                    <div className="mt-3 flex gap-2">
                        <button
                            type="button"
                            onClick={runApprove}
                            className="inline-flex min-h-10 items-center gap-1.5 rounded-[4px] px-4 py-2 text-sm font-semibold text-white transition-transform hover:-translate-y-0.5"
                            style={{ background: c.red }}
                        >
                            <MaterialIcon icon="task_alt" size={15} />
                            {copy.retryApprove}
                        </button>
                        <button
                            type="button"
                            onClick={handleReject}
                            className="inline-flex min-h-10 items-center gap-1.5 rounded-[4px] border px-3 py-2 text-sm font-semibold transition-transform hover:-translate-y-0.5"
                            style={{ borderColor: c.hair, color: c.ink70, background: c.panel }}
                        >
                            <MaterialIcon icon="close" size={15} />
                            {t("draftDecline")}
                        </button>
                    </div>
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

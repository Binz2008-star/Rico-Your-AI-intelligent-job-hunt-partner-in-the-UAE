"use client";

import type { RicoAttachmentAnalysis } from "@/lib/schemas";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";

export interface AttachmentAnalysisCardProps {
    analyses: RicoAttachmentAnalysis[];
    /** Atelier surface (authenticated /command, slice 4c). Default false =
     *  pre-4c presentation, unchanged. */
    atelier?: boolean;
}

const PURPOSE_LABELS: Record<string, string> = {
    cv_resume: "CV / Resume",
    job_post: "Job Post",
    recruiter_message: "Recruiter Message",
    application_form: "Application Form",
    certificate: "Certificate / License",
    offer_letter: "Offer Letter",
    contract_or_legalish: "Contract / Legal Document",
    company_profile: "Company Profile",
    public_comment: "Public Comment",
    application_evidence: "Application Confirmation",
    unknown_document: "Unrecognized Document",
};

function purposeLabel(purpose: string): string {
    return PURPOSE_LABELS[purpose] ?? purpose.replace(/_/g, " ");
}

/**
 * CAREER-OS-04 — render the agentic `attachment_analysis` envelope produced when a
 * non-CV file is uploaded. Read-only: it describes what the file is and any warnings.
 * It never triggers a profile/settings write (file-derived data stays confirm-first).
 */
export function AttachmentAnalysisCard({ analyses, atelier = false }: AttachmentAnalysisCardProps) {
    const c = useWorkspaceTheme();
    if (!analyses?.length) return null;

    if (!atelier) {
        return (
            <div className="mt-3 space-y-2">
                {analyses.map((a) => (
                    <div
                        key={a.id}
                        data-testid="attachment-analysis-card"
                        className="rounded-xl border border-gold/20 bg-surface-2 p-4 space-y-2"
                    >
                        <div className="flex items-center justify-between gap-2">
                            <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">
                                Detected attachment
                            </p>
                            <span className="text-[11px] text-text-muted shrink-0">
                                {Math.round((a.confidence ?? 0) * 100)}% confidence
                            </span>
                        </div>

                        <div className="flex items-baseline gap-2">
                            <span className="text-[13px] font-medium text-text-primary">
                                {purposeLabel(a.purpose)}
                            </span>
                            {a.filename && (
                                <span className="text-[11px] text-text-muted truncate">{a.filename}</span>
                            )}
                        </div>

                        {a.extracted_summary && (
                            <p className="text-[12px] text-text-secondary">{a.extracted_summary}</p>
                        )}

                        {a.warnings?.length > 0 && (
                            <ul className="space-y-0.5 pt-0.5" aria-label="warnings">
                                {a.warnings.map((w, i) => (
                                    <li
                                        key={i}
                                        className="text-[11px] text-amber-400/90 flex items-start gap-1.5"
                                    >
                                        <span aria-hidden="true">⚠</span>
                                        <span>{w}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                ))}
            </div>
        );
    }

    /* Atelier surface — paper panel, mono kicker, ink hierarchy. */
    return (
        <div className="mt-3 space-y-2">
            {analyses.map((a) => (
                <div
                    key={a.id}
                    data-testid="attachment-analysis-card"
                    className="rounded-xl p-4 space-y-2"
                    style={{ background: c.panel, border: `1px solid ${c.hair}` }}
                >
                    <div className="flex items-center justify-between gap-2">
                        <p
                            className="text-[10px] font-medium uppercase"
                            style={{ color: c.ink40, fontFamily: ATELIER_FONT.mono, letterSpacing: "0.08em" }}
                        >
                            Detected attachment
                        </p>
                        <span
                            className="text-[10px] shrink-0 tabular-nums"
                            style={{ color: c.ink40, fontFamily: ATELIER_FONT.mono }}
                        >
                            {Math.round((a.confidence ?? 0) * 100)}% confidence
                        </span>
                    </div>

                    <div className="flex items-baseline gap-2">
                        <span
                            className="text-[13px] font-medium"
                            style={{ color: c.ink, fontFamily: ATELIER_FONT.body }}
                        >
                            {purposeLabel(a.purpose)}
                        </span>
                        {a.filename && (
                            <span className="text-[11px] truncate" style={{ color: c.ink55 }}>
                                {a.filename}
                            </span>
                        )}
                    </div>

                    {a.extracted_summary && (
                        <p className="text-[12px] leading-relaxed" style={{ color: c.ink55, fontFamily: ATELIER_FONT.body }}>
                            {a.extracted_summary}
                        </p>
                    )}

                    {a.warnings?.length > 0 && (
                        <ul className="space-y-0.5 pt-0.5" aria-label="warnings">
                            {a.warnings.map((w, i) => (
                                <li
                                    key={i}
                                    className="text-[11px] text-amber-400/90 flex items-start gap-1.5"
                                >
                                    <span aria-hidden="true">⚠</span>
                                    <span>{w}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            ))}
        </div>
    );
}

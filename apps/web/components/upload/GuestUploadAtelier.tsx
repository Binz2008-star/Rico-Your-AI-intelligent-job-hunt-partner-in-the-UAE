"use client";

/**
 * GuestUploadAtelier — the public (unauthenticated) CV-upload surface in the
 * approved Atelier direction, rendered inside the public AtelierAuthShell so a
 * guest never sees the authenticated workspace navigation.
 *
 * Behaviour is preserved byte-for-byte from the previous GuestUploadView:
 *  - guest identity `public:${sid}` from localStorage `rico_sid`
 *  - `uploadCV(file, guestId)` → ProcessingOverlay → `/command?cv=ready`
 *  - PDF only, backend-authoritative (no success shown before the backend
 *    confirms and the parse pipeline completes), error surfacing, drag+drop.
 * Only the presentation moves to the Atelier island (scoped `.atl-*` classes
 * and the atelier token vars); the flow itself is unchanged.
 */

import { PageTransition } from "@/components/ui/PageTransition";
import { ProcessingOverlay } from "@/components/ui/ProcessingOverlay";
import { AtelierAuthShell } from "@/components/auth/AtelierAuthShell";
import { useLanguage } from "@/contexts/LanguageContext";
import { uploadCV } from "@/lib/api";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

function getGuestUploadUserId(): string {
    let sessionId = window.localStorage.getItem("rico_sid");
    if (!sessionId) {
        sessionId = `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
        window.localStorage.setItem("rico_sid", sessionId);
    }
    return `public:${sessionId}`;
}

export function GuestUploadAtelier() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const router = useRouter();

    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [uploadComplete, setUploadComplete] = useState(false);
    const [error, setError] = useState("");

    const handleUpload = useCallback(async (file: File) => {
        setIsUploading(true);
        setError("");
        try {
            // Backend-authoritative: only advance to the processing/success
            // stage after uploadCV resolves. A rejected upload throws and is
            // surfaced below — never a false success.
            await uploadCV(file, getGuestUploadUserId());
            setIsUploading(false);
            setIsProcessing(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : t("uploadError"));
            setIsUploading(false);
        }
    }, [t]);

    const handleProcessingComplete = useCallback(() => {
        setIsProcessing(false);
        setUploadComplete(true);
        setTimeout(() => router.push("/command?cv=ready"), 2000);
    }, [router]);

    const label = (k: TranslationKey) => t(k);

    return (
        <AtelierAuthShell>
            <ProcessingOverlay
                active={isProcessing}
                onComplete={handleProcessingComplete}
                stages={[
                    label("processingStage1"),
                    label("processingStage2"),
                    label("processingStage3"),
                    label("processingStage4"),
                    label("processingStage5"),
                ]}
            />

            {uploadComplete ? (
                <PageTransition>
                    <div className="atl-status">
                        <span className="atl-status-badge" aria-hidden="true">
                            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M20 6L9 17l-5-5" />
                            </svg>
                        </span>
                        <div>
                            <h1 className="atl-auth-title">{t("uploadReadyHeading")}</h1>
                            <p className="atl-auth-sub" style={{ marginBottom: 0 }}>{t("uploadReadyBody")}</p>
                        </div>
                    </div>
                </PageTransition>
            ) : (
                <PageTransition>
                    <>
                        <h1 className="atl-auth-title">{t("uploadYourCV")}</h1>
                        <p className="atl-auth-sub">{t("uploadCvSubtitle")}</p>

                        {error && (
                            <div
                                role="alert"
                                style={{
                                    marginBottom: 20,
                                    borderRadius: 8,
                                    border: "1px solid color-mix(in srgb, var(--red, #C6492E) 40%, transparent)",
                                    background: "color-mix(in srgb, var(--red, #C6492E) 8%, transparent)",
                                    padding: "12px 14px",
                                    fontSize: 14,
                                    color: "var(--red, #C6492E)",
                                    textAlign: "center",
                                }}
                            >
                                {error}
                            </div>
                        )}

                        <div
                            onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                            onDragLeave={() => setIsDragging(false)}
                            onDrop={e => { e.preventDefault(); setIsDragging(false); const f = e.dataTransfer.files[0]; if (f) handleUpload(f); }}
                            style={{
                                display: "flex",
                                minHeight: 260,
                                flexDirection: "column",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: 8,
                                borderRadius: 12,
                                border: `1px dashed ${isDragging ? "var(--sun, #C99A46)" : "var(--rule, rgba(31,27,21,0.16))"}`,
                                background: isDragging
                                    ? "color-mix(in srgb, var(--sun, #C99A46) 6%, var(--paper, #F7F1E6))"
                                    : "var(--paper, #F7F1E6)",
                                padding: "32px 20px",
                                textAlign: "center",
                                transition: "border-color .15s ease, background-color .15s ease",
                            }}
                        >
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--ink-soft)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ marginBottom: 12 }}>
                                <path d="M12 15V4M8 8l4-4 4 4M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
                            </svg>
                            <p style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)" }}>
                                {isDragging ? t("uploadDropHere") : t("uploadDragDrop")}
                            </p>
                            <p style={{ fontSize: 13, color: "var(--ink-soft)" }}>{t("uploadOr")}</p>
                            <label className="atl-btn atl-btn-primary" style={{ marginTop: 14, cursor: isUploading ? "not-allowed" : "pointer" }} aria-disabled={isUploading}>
                                <input
                                    type="file"
                                    accept=".pdf"
                                    onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = ""; }}
                                    style={{ position: "absolute", width: 1, height: 1, padding: 0, margin: -1, overflow: "hidden", clip: "rect(0,0,0,0)", whiteSpace: "nowrap", border: 0 }}
                                    disabled={isUploading}
                                />
                                {isUploading ? (
                                    <><span className="atl-spin" />{t("uploadProcessing")}</>
                                ) : (
                                    <>{t("uploadSelectFile")}</>
                                )}
                            </label>
                            <p style={{ marginTop: 20, fontSize: 11, letterSpacing: "0.02em", color: "var(--ink-mute)", textTransform: "uppercase" }}>
                                {t("uploadPDF")}
                            </p>
                        </div>

                        <p className="atl-note" style={{ marginTop: 16 }}>{t("uploadSecureProcessing")}</p>
                    </>
                </PageTransition>
            )}
        </AtelierAuthShell>
    );
}

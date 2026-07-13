"use client";

/**
 * UploadAtelier — the authenticated "My files" / CV manager in the approved
 * WorkspaceShell (Shell C) Atelier direction. Rendered inside WorkspaceShell,
 * so it reads the shell's local light/dark palette via useWorkspaceTheme()
 * (parity with ProfileAtelier / SettingsAtelier).
 *
 * All data + behaviour is preserved from the previous FileManagerView:
 *  - listUserFiles + fetchProfile (role-mismatch compute)
 *  - CV upload → uploadCV parse+preview pipeline → ProcessingOverlay →
 *    cvPendingConfirm (the file only lands in My Files after /command confirm)
 *  - cover_letter/other → uploadUserFile → reload
 *  - setPrimary / delete / rename, quota (422) messaging, error/loading/empty
 *  - backend-authoritative: no success shown before the backend confirms.
 * Only the presentation moves to the workspace palette.
 */

import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { ProcessingOverlay } from "@/components/ui/ProcessingOverlay";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono } from "@/components/atelier-kit/primitives";
import { useWorkspaceTheme, type WorkspacePalette } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import {
    ApiError,
    deleteUserFile,
    fetchProfile,
    listUserFiles,
    setPrimaryFile,
    updateUserFile,
    uploadCV,
    uploadUserFile,
    type UserDocument,
} from "@/lib/api";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

const SERIF = ATELIER_FONT.serif;

type DocTypeOption = "cv" | "cover_letter" | "other";

function formatDate(iso?: string | null): string {
    if (!iso) return "";
    try {
        return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    } catch {
        return "";
    }
}

function formatSize(bytes: number): string {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── File card ──────────────────────────────────────────────────────────────────

interface FileCardProps {
    doc: UserDocument;
    t: (k: TranslationKey) => string;
    palette: WorkspacePalette;
    onSetPrimary: (id: string) => void;
    onDelete: (id: string) => void;
    onRename: (id: string, newLabel: string) => void;
}

function FileCard({ doc, t, palette, onSetPrimary, onDelete, onRename }: FileCardProps) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(doc.label ?? doc.filename);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (!editing) setDraft(doc.label ?? doc.filename);
    }, [doc.label, doc.filename, editing]);

    useEffect(() => {
        if (editing) inputRef.current?.focus();
    }, [editing]);

    const displayName = doc.label || doc.filename;
    const isLegacy = doc.is_legacy;
    const docTypeLabel =
        doc.doc_type === "cv" ? t("filesTypeCV") :
        doc.doc_type === "cover_letter" ? t("filesCoverLetter") :
        t("filesOther");
    const docIcon =
        doc.doc_type === "cv" ? "description" :
        doc.doc_type === "cover_letter" ? "mail" :
        "insert_drive_file";

    const actionBtn = "flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition-colors";

    return (
        <div className="relative rounded-xl p-4" style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}>
            {doc.is_primary && (
                <span
                    className="absolute top-3 end-3 flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    style={{ background: `color-mix(in srgb, ${palette.red} 14%, transparent)`, color: palette.red }}
                >
                    <MaterialIcon icon="star" className="text-[11px]" />
                    {t("filesPrimary")}
                </span>
            )}

            <div className="flex items-start gap-3 pe-16">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: palette.inset, color: palette.ink70 }}>
                    <MaterialIcon icon={docIcon} className="text-xl" />
                </div>
                <div className="min-w-0 flex-1">
                    {editing ? (
                        <div className="flex items-center gap-2">
                            <input
                                ref={inputRef}
                                value={draft}
                                onChange={e => setDraft(e.target.value)}
                                onKeyDown={e => {
                                    if (e.key === "Enter") { onRename(doc.id, draft); setEditing(false); }
                                    if (e.key === "Escape") setEditing(false);
                                }}
                                className="min-w-0 flex-1 rounded-lg px-2 py-1 text-sm focus:outline-none"
                                style={{ border: `1px solid ${palette.hair}`, background: palette.inset, color: palette.ink }}
                            />
                            <button onClick={() => { onRename(doc.id, draft); setEditing(false); }} className="rounded-lg px-2 py-1 text-[11px] font-semibold" style={{ background: `color-mix(in srgb, ${palette.red} 14%, transparent)`, color: palette.red }}>
                                {t("filesSaveLabel")}
                            </button>
                            <button onClick={() => setEditing(false)} className="text-[11px]" style={{ color: palette.ink40 }}>
                                {t("filesCancelLabel")}
                            </button>
                        </div>
                    ) : (
                        <p className="truncate text-sm font-semibold" style={{ color: palette.ink }}>{displayName}</p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                        <span className="rounded px-1.5 py-0.5 text-[9px] uppercase tracking-wide" style={{ border: `1px solid ${palette.hair}`, color: palette.ink55 }}>
                            {docTypeLabel}
                        </span>
                        {doc.created_at && <span className="text-[11px]" style={{ color: palette.ink40 }}>{formatDate(doc.created_at)}</span>}
                        {doc.file_size > 0 && <span className="text-[11px]" style={{ color: palette.ink40 }}>{formatSize(doc.file_size)}</span>}
                    </div>
                </div>
            </div>

            {doc.doc_type === "cv" && (doc.skills_count || doc.years_experience || doc.current_role) && (
                <div className="mt-3 flex flex-wrap gap-3 pt-3 text-[11px]" style={{ borderTop: `1px solid ${palette.hair}`, color: palette.ink55 }}>
                    {doc.current_role && <span>{doc.current_role}</span>}
                    {doc.skills_count ? <span>{doc.skills_count} {t("filesSkills")}</span> : null}
                    {doc.years_experience ? <span>{doc.years_experience} {t("filesYearsExp")}</span> : null}
                </div>
            )}

            {isLegacy && <p className="mt-2 text-[10px]" style={{ color: palette.ink40 }}>{t("filesLegacyNote")}</p>}

            <div className="mt-3 flex flex-wrap items-center gap-2 pt-3" style={{ borderTop: `1px solid ${palette.hair}` }}>
                {doc.doc_type === "cv" && !doc.is_primary && !isLegacy && (
                    <button onClick={() => onSetPrimary(doc.id)} className={actionBtn} style={{ color: palette.ink70 }}>
                        <MaterialIcon icon="star" className="text-sm" />
                        {t("filesSetPrimary")}
                    </button>
                )}
                {!editing && (
                    <button onClick={() => { setDraft(doc.label ?? doc.filename); setEditing(true); }} className={actionBtn} style={{ color: palette.ink70 }}>
                        <MaterialIcon icon="edit" className="text-sm" />
                        {t("filesRename")}
                    </button>
                )}
                {!isLegacy && (
                    confirmDelete ? (
                        <div className="flex items-center gap-2">
                            <span className="text-[11px]" style={{ color: palette.red }}>{t("filesDeleteConfirm")}</span>
                            <button onClick={() => onDelete(doc.id)} className="rounded-lg px-2 py-1 text-[11px] font-semibold" style={{ color: palette.red }}>{t("filesDelete")}</button>
                            <button onClick={() => setConfirmDelete(false)} className="text-[11px]" style={{ color: palette.ink40 }}>{t("filesCancelLabel")}</button>
                        </div>
                    ) : (
                        <button onClick={() => setConfirmDelete(true)} className={actionBtn} style={{ color: palette.ink40 }}>
                            <MaterialIcon icon="delete" className="text-sm" />
                            {t("filesDelete")}
                        </button>
                    )
                )}
            </div>
        </div>
    );
}

// ── Upload zone ─────────────────────────────────────────────────────────────────

interface UploadZoneProps {
    docType: DocTypeOption;
    onDocTypeChange: (t: DocTypeOption) => void;
    onFileSelected: (file: File) => void;
    isUploading: boolean;
    t: (k: TranslationKey) => string;
    palette: WorkspacePalette;
}

function UploadZone({ docType, onDocTypeChange, onFileSelected, isUploading, t, palette }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) onFileSelected(file);
    }, [onFileSelected]);

    const tabs: { key: DocTypeOption; label: string }[] = [
        { key: "cv", label: t("filesUploadCv") },
        { key: "cover_letter", label: t("filesUploadCoverLetter") },
        { key: "other", label: t("filesUploadOther") },
    ];

    return (
        <div className="rounded-xl p-5" style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}>
            <div className="mb-4 flex gap-1.5">
                {tabs.map(tab => {
                    const active = docType === tab.key;
                    return (
                        <button
                            key={tab.key}
                            onClick={() => onDocTypeChange(tab.key)}
                            className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
                            style={active ? { background: palette.ink, color: palette.bg } : { color: palette.ink70 }}
                        >
                            {tab.label}
                        </button>
                    );
                })}
            </div>

            <div
                onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className="flex min-h-[160px] flex-col items-center justify-center rounded-xl px-4 py-6 text-center transition-colors"
                style={{
                    border: `1px dashed ${isDragging ? palette.red : palette.hair}`,
                    background: isDragging ? `color-mix(in srgb, ${palette.red} 5%, ${palette.inset})` : palette.inset,
                }}
            >
                <MaterialIcon icon="upload_file" className="mb-3 text-3xl" style={{ color: palette.ink40 }} />
                <p className="text-sm font-medium" style={{ color: palette.ink70 }}>
                    {isDragging ? t("uploadDropHere") : t("uploadDragDrop")}
                </p>
                <p className="mt-1 text-xs" style={{ color: palette.ink40 }}>{t("uploadOr")}</p>
                <label className="mt-3 inline-flex cursor-pointer">
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={e => { const f = e.target.files?.[0]; if (f) onFileSelected(f); e.target.value = ""; }}
                        className="sr-only"
                        disabled={isUploading}
                    />
                    <span className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold transition-opacity hover:opacity-90 aria-disabled:opacity-60" style={{ background: palette.red, color: palette.bg }}>
                        {isUploading ? (
                            <><MaterialIcon icon="hourglass_empty" className="animate-spin" />{t("uploadProcessing")}</>
                        ) : (
                            <>{t("uploadSelectFile")}<MaterialIcon icon="folder_open" /></>
                        )}
                    </span>
                </label>
            </div>

            <p className="mt-3 flex items-center justify-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: palette.ink40 }}>
                <MaterialIcon icon="lock" className="text-xs" />
                {t("uploadSecureProcessing")}
            </p>
        </div>
    );
}

// ── Authenticated file manager ───────────────────────────────────────────────────

export function UploadAtelier() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";
    const palette = useWorkspaceTheme();

    const [files, setFiles] = useState<UserDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [uploadOpen, setUploadOpen] = useState(false);
    const [docType, setDocType] = useState<DocTypeOption>("cv");
    const [isUploading, setIsUploading] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [cvPendingConfirm, setCvPendingConfirm] = useState(false);
    const [roleMismatch, setRoleMismatch] = useState<{ cvRole: string; targetRoles: string[] } | null>(null);

    const loadFiles = useCallback(async () => {
        try {
            const [res, profile] = await Promise.all([
                listUserFiles(),
                fetchProfile().catch(() => null),
            ]);
            setFiles(res.files);
            const primaryCv = res.files.find((f) => f.doc_type === "cv" && f.is_primary && f.current_role);
            const targets = profile?.target_roles ?? [];
            if (primaryCv?.current_role && targets.length > 0) {
                const cvRole = primaryCv.current_role.toLowerCase();
                const matched = targets.some((r) => {
                    const t2 = r.toLowerCase();
                    return cvRole.includes(t2) || t2.includes(cvRole);
                });
                setRoleMismatch(matched ? null : { cvRole: primaryCv.current_role, targetRoles: targets });
            } else {
                setRoleMismatch(null);
            }
        } catch (err) {
            if (err instanceof ApiError && (err.statusCode === 404 || err.statusCode === 500 || err.statusCode === 503)) {
                setFiles([]);
            } else {
                setError(t("uploadErrLoad"));
            }
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => { loadFiles(); }, [loadFiles]);

    const handleFileSelected = useCallback(async (file: File) => {
        setIsUploading(true);
        setError("");
        setCvPendingConfirm(false);
        try {
            if (docType === "cv") {
                const cvResult = await uploadCV(file);
                setIsUploading(false);
                if (!cvResult.ok) {
                    setError(cvResult.message ?? t("uploadError"));
                    return;
                }
                setIsProcessing(true);
            } else {
                await uploadUserFile(file, docType as "cover_letter" | "other");
                setIsUploading(false);
                setUploadOpen(false);
                await loadFiles();
            }
        } catch (err) {
            setIsUploading(false);
            if (err instanceof ApiError && err.statusCode === 422) {
                setError(t("uploadErrQuota"));
            } else {
                setError(err instanceof Error ? err.message : t("uploadError"));
            }
        }
    }, [docType, loadFiles, t]);

    const handleCvProcessingComplete = useCallback(() => {
        setIsProcessing(false);
        setCvPendingConfirm(true);
    }, []);

    const handleSetPrimary = useCallback(async (id: string) => {
        try { await setPrimaryFile(id); await loadFiles(); } catch { /* silent */ }
    }, [loadFiles]);

    const handleDelete = useCallback(async (id: string) => {
        try { await deleteUserFile(id); await loadFiles(); } catch { /* silent */ }
    }, [loadFiles]);

    const handleRename = useCallback(async (id: string, label: string) => {
        try {
            await updateUserFile(id, { label: label.trim() || undefined });
            await loadFiles();
        } catch (err) {
            setError(err instanceof Error ? err.message : t("uploadError"));
        }
    }, [loadFiles, t]);

    return (
        <div className="flex w-full max-w-3xl flex-col gap-4" dir={isAr ? "rtl" : "ltr"} style={{ color: palette.ink }}>
            <ProcessingOverlay
                active={isProcessing}
                onComplete={handleCvProcessingComplete}
                stages={[
                    t("processingStage1"),
                    t("processingStage2"),
                    t("processingStage3"),
                    t("processingStage4"),
                    t("processingStage5"),
                ]}
            />

            <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                    <Mono style={{ color: palette.ink55 }}>{t("filesPageTitle")}</Mono>
                    <h1 className="mt-2 text-[2rem] font-normal leading-[1.05]" style={{ fontFamily: SERIF, color: palette.ink }}>
                        {t("filesPageTitle")}
                    </h1>
                    <p className="mt-1 text-sm" style={{ color: palette.ink70 }}>{t("filesPageSubtitle")}</p>
                </div>
                <button
                    onClick={() => setUploadOpen(p => !p)}
                    className="flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-opacity hover:opacity-90"
                    style={{ background: palette.red, color: palette.bg }}
                >
                    <MaterialIcon icon={uploadOpen ? "close" : "add"} className="text-base" />
                    {t("filesUploadNew")}
                </button>
            </div>

            {error && (
                <div className="rounded-lg px-4 py-3 text-sm" role="alert" style={{ border: `1px solid color-mix(in srgb, ${palette.red} 30%, transparent)`, background: `color-mix(in srgb, ${palette.red} 8%, transparent)`, color: palette.red }}>
                    {error}
                </div>
            )}

            {roleMismatch && !error && (
                <div className="flex flex-col gap-1 rounded-lg px-4 py-3 text-sm" role="alert" style={{ border: `1px solid ${palette.hair}`, background: palette.inset, color: palette.ink }}>
                    <span className="font-semibold">{t("filesRoleMismatchTitle")}</span>
                    <span className="text-[12px]" style={{ color: palette.ink70 }}>
                        {t("filesRoleMismatchBody").replace("{cvRole}", roleMismatch.cvRole).replace("{targetRoles}", roleMismatch.targetRoles.join(", "))}
                    </span>
                </div>
            )}

            {cvPendingConfirm && !error && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3 text-sm" role="status" style={{ border: `1px solid color-mix(in srgb, ${palette.red} 30%, transparent)`, background: `color-mix(in srgb, ${palette.red} 7%, transparent)`, color: palette.ink }}>
                    <span>
                        <span className="font-semibold">{t("uploadCvPreviewReady")}</span>
                        {" — "}
                        {t("uploadCvConfirmHint")}
                    </span>
                    <Link href="/command" className="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold transition-opacity hover:opacity-90" style={{ background: palette.red, color: palette.bg }}>
                        <MaterialIcon icon="chat" className="text-sm" />
                        {t("navAskRico")}
                    </Link>
                </div>
            )}

            {uploadOpen && (
                <UploadZone
                    docType={docType}
                    onDocTypeChange={setDocType}
                    onFileSelected={handleFileSelected}
                    isUploading={isUploading}
                    t={t}
                    palette={palette}
                />
            )}

            {loading ? (
                <div className="py-12 text-center">
                    <MaterialIcon icon="hourglass_empty" className="animate-spin text-2xl" style={{ color: palette.ink40 }} />
                </div>
            ) : files.length === 0 ? (
                <div className="flex flex-col items-center gap-3 rounded-xl py-14 text-center" style={{ border: `1px solid ${palette.hair}`, background: palette.panel }}>
                    <MaterialIcon icon="folder_open" className="text-4xl" style={{ color: palette.ink40 }} />
                    <p className="font-semibold" style={{ color: palette.ink }}>{t("filesEmpty")}</p>
                    <p className="text-sm" style={{ color: palette.ink70 }}>{t("filesEmptyHint")}</p>
                    <button onClick={() => setUploadOpen(true)} className="mt-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-opacity hover:opacity-90" style={{ background: palette.red, color: palette.bg }}>
                        {t("uploadYourCV")}
                    </button>
                </div>
            ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                    {files.map(doc => (
                        <FileCard
                            key={doc.id}
                            doc={doc}
                            t={t}
                            palette={palette}
                            onSetPrimary={handleSetPrimary}
                            onDelete={handleDelete}
                            onRename={handleRename}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

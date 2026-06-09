'use client';

import { AppShell } from '@/components/layout/AppShell';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { PageTransition } from '@/components/ui/PageTransition';
import { ProcessingOverlay } from '@/components/ui/ProcessingOverlay';
import {
    deleteUserFile,
    fetchMe,
    listUserFiles,
    setPrimaryFile,
    updateUserFile,
    uploadCV,
    uploadUserFile,
    type UserDocument,
} from '@/lib/api';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation, type TranslationKey } from '@/lib/translations';
import { useRouter } from 'next/navigation';
import React, { useCallback, useEffect, useRef, useState } from 'react';

// ── Helpers ────────────────────────────────────────────────────────────────────

function getGuestUploadUserId(): string {
    let sessionId = window.localStorage.getItem('rico_sid');
    if (!sessionId) {
        sessionId = `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
        window.localStorage.setItem('rico_sid', sessionId);
    }
    return `public:${sessionId}`;
}

function formatDate(iso?: string | null): string {
    if (!iso) return '';
    try {
        return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
    } catch {
        return '';
    }
}

function formatSize(bytes: number): string {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type DocTypeOption = 'cv' | 'cover_letter' | 'other';

// ── File card ──────────────────────────────────────────────────────────────────

interface FileCardProps {
    doc: UserDocument;
    isAr: boolean;
    t: (k: TranslationKey) => string;
    onSetPrimary: (id: string) => void;
    onDelete: (id: string) => void;
    onRename: (id: string, newLabel: string) => void;
}

function FileCard({ doc, isAr, t, onSetPrimary, onDelete, onRename }: FileCardProps) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(doc.label ?? doc.filename);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (editing) inputRef.current?.focus();
    }, [editing]);

    const displayName = doc.label || doc.filename;
    const isLegacy = doc.is_legacy;

    const docTypeLabel =
        doc.doc_type === 'cv' ? t('filesTypeCV') :
        doc.doc_type === 'cover_letter' ? t('filesCoverLetter') :
        t('filesOther');

    const docIcon =
        doc.doc_type === 'cv' ? 'description' :
        doc.doc_type === 'cover_letter' ? 'mail' :
        'insert_drive_file';

    return (
        <div className="group relative rounded-xl border border-border-soft bg-surface-elevated/70 p-4 transition-colors hover:border-gold/20">
            {/* Primary badge */}
            {doc.is_primary && (
                <span className="absolute top-3 end-3 flex items-center gap-1 rounded-full bg-gold/15 px-2 py-0.5 text-[10px] font-semibold text-gold">
                    <MaterialIcon icon="star" className="text-[11px]" />
                    {t('filesPrimary')}
                </span>
            )}

            {/* Top row */}
            <div className="flex items-start gap-3 pr-16">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-subtle text-text-secondary">
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
                                    if (e.key === 'Enter') { onRename(doc.id, draft); setEditing(false); }
                                    if (e.key === 'Escape') setEditing(false);
                                }}
                                className="min-w-0 flex-1 rounded-lg border border-gold/30 bg-surface-glass px-2 py-1 text-sm text-text-primary focus:outline-none"
                            />
                            <button
                                onClick={() => { onRename(doc.id, draft); setEditing(false); }}
                                className="rounded-lg bg-gold/15 px-2 py-1 text-[11px] font-semibold text-gold"
                            >
                                {t('filesSaveLabel')}
                            </button>
                            <button
                                onClick={() => setEditing(false)}
                                className="text-[11px] text-text-tertiary hover:text-text-secondary"
                            >
                                {t('filesCancelLabel')}
                            </button>
                        </div>
                    ) : (
                        <p className="truncate text-sm font-semibold text-text-primary">{displayName}</p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="h-4 px-1.5 text-[9px] uppercase tracking-wide">
                            {docTypeLabel}
                        </Badge>
                        {doc.created_at && (
                            <span className="text-[11px] text-text-tertiary">{formatDate(doc.created_at)}</span>
                        )}
                        {doc.file_size > 0 && (
                            <span className="text-[11px] text-text-tertiary">{formatSize(doc.file_size)}</span>
                        )}
                    </div>
                </div>
            </div>

            {/* CV meta row */}
            {doc.doc_type === 'cv' && (doc.skills_count || doc.years_experience || doc.current_role) && (
                <div className="mt-3 flex flex-wrap gap-3 border-t border-border-subtle pt-3 text-[11px] text-text-tertiary">
                    {doc.current_role && <span>{doc.current_role}</span>}
                    {doc.skills_count ? <span>{doc.skills_count} {t('filesSkills')}</span> : null}
                    {doc.years_experience ? <span>{doc.years_experience} {t('filesYearsExp')}</span> : null}
                </div>
            )}

            {/* Legacy note */}
            {isLegacy && (
                <p className="mt-2 text-[10px] text-text-tertiary">{t('filesLegacyNote')}</p>
            )}

            {/* Action row */}
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-3">
                {doc.doc_type === 'cv' && !doc.is_primary && !isLegacy && (
                    <button
                        onClick={() => onSetPrimary(doc.id)}
                        className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-text-secondary transition-colors hover:bg-gold/10 hover:text-gold"
                    >
                        <MaterialIcon icon="star" className="text-sm" />
                        {t('filesSetPrimary')}
                    </button>
                )}
                {!editing && (
                    <button
                        onClick={() => { setDraft(doc.label ?? doc.filename); setEditing(true); }}
                        className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-text-secondary transition-colors hover:bg-white/[0.05] hover:text-text-primary"
                    >
                        <MaterialIcon icon="edit" className="text-sm" />
                        {t('filesRename')}
                    </button>
                )}
                {!isLegacy && (
                    confirmDelete ? (
                        <div className="flex items-center gap-2">
                            <span className="text-[11px] text-rico-red">{t('filesDeleteConfirm')}</span>
                            <button onClick={() => onDelete(doc.id)} className="rounded-lg px-2 py-1 text-[11px] font-semibold text-rico-red transition-colors hover:bg-rico-red/10">
                                {t('filesDelete')}
                            </button>
                            <button onClick={() => setConfirmDelete(false)} className="text-[11px] text-text-tertiary">
                                {t('filesCancelLabel')}
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={() => setConfirmDelete(true)}
                            className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-text-tertiary transition-colors hover:bg-rico-red/10 hover:text-rico-red"
                        >
                            <MaterialIcon icon="delete" className="text-sm" />
                            {t('filesDelete')}
                        </button>
                    )
                )}
            </div>
        </div>
    );
}

// ── Upload zone ───────────────────────────────────────────────────────────────

interface UploadZoneProps {
    docType: DocTypeOption;
    onDocTypeChange: (t: DocTypeOption) => void;
    onFileSelected: (file: File) => void;
    isUploading: boolean;
    t: (k: TranslationKey) => string;
}

function UploadZone({ docType, onDocTypeChange, onFileSelected, isUploading, t }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) onFileSelected(file);
    }, [onFileSelected]);

    const tabs: { key: DocTypeOption; label: string }[] = [
        { key: 'cv', label: t('filesUploadCv') },
        { key: 'cover_letter', label: t('filesUploadCoverLetter') },
        { key: 'other', label: t('filesUploadOther') },
    ];

    return (
        <div className="rounded-xl border border-border-soft bg-surface-elevated/60 p-5">
            {/* Type tabs */}
            <div className="mb-4 flex gap-1.5">
                {tabs.map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => onDocTypeChange(tab.key)}
                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                            docType === tab.key
                                ? 'bg-gold text-[#0a0a1a]'
                                : 'text-text-secondary hover:bg-white/[0.06] hover:text-text-primary'
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Drop zone */}
            <div
                onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`flex min-h-[160px] flex-col items-center justify-center rounded-xl border border-dashed px-4 py-6 text-center transition-colors ${
                    isDragging
                        ? 'border-gold/50 bg-gold/[0.04]'
                        : 'border-border-subtle bg-surface-glass hover:border-gold/25'
                }`}
            >
                <MaterialIcon icon="upload_file" className="mb-3 text-3xl text-text-tertiary" />
                <p className="text-sm font-medium text-text-secondary">
                    {isDragging ? t('uploadDropHere') : t('uploadDragDrop')}
                </p>
                <p className="mt-1 text-xs text-text-tertiary">{t('uploadOr')}</p>
                <label className="mt-3 inline-flex cursor-pointer">
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={e => { const f = e.target.files?.[0]; if (f) onFileSelected(f); e.target.value = ''; }}
                        className="sr-only"
                        disabled={isUploading}
                    />
                    <span className="inline-flex items-center gap-2 rounded-lg bg-gold px-5 py-2.5 text-sm font-bold text-[#0a0a1a] transition-opacity hover:opacity-90 aria-disabled:opacity-60">
                        {isUploading ? (
                            <>
                                <MaterialIcon icon="hourglass_empty" className="animate-spin" />
                                {t('uploadProcessing')}
                            </>
                        ) : (
                            <>
                                {t('uploadSelectFile')}
                                <MaterialIcon icon="folder_open" />
                            </>
                        )}
                    </span>
                </label>
            </div>

            <p className="mt-3 flex items-center justify-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-tertiary">
                <MaterialIcon icon="lock" className="text-xs" />
                {t('uploadSecureProcessing')}
            </p>
        </div>
    );
}

// ── File manager view (authenticated) ─────────────────────────────────────────

interface FileManagerViewProps {
    isAr: boolean;
    t: (k: TranslationKey) => string;
    router: ReturnType<typeof useRouter>;
}

function FileManagerView({ isAr, t, router }: FileManagerViewProps) {
    const [files, setFiles] = useState<UserDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [uploadOpen, setUploadOpen] = useState(false);
    const [docType, setDocType] = useState<DocTypeOption>('cv');
    const [isUploading, setIsUploading] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);

    const loadFiles = useCallback(async () => {
        try {
            const res = await listUserFiles();
            setFiles(res.files);
        } catch {
            setError('Could not load files');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadFiles(); }, [loadFiles]);

    const handleFileSelected = useCallback(async (file: File) => {
        setIsUploading(true);
        setError('');
        try {
            if (docType === 'cv') {
                await uploadCV(file, getGuestUploadUserId());
                setIsUploading(false);
                setIsProcessing(true);
            } else {
                await uploadUserFile(file, docType as 'cover_letter' | 'other');
                setIsUploading(false);
                setUploadOpen(false);
                await loadFiles();
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : t('uploadError'));
            setIsUploading(false);
        }
    }, [docType, loadFiles, t]);

    const handleCvProcessingComplete = useCallback(async () => {
        setIsProcessing(false);
        setUploadOpen(false);
        await loadFiles();
    }, [loadFiles]);

    const handleSetPrimary = useCallback(async (id: string) => {
        try {
            await setPrimaryFile(id);
            await loadFiles();
        } catch { /* silent */ }
    }, [loadFiles]);

    const handleDelete = useCallback(async (id: string) => {
        try {
            await deleteUserFile(id);
            await loadFiles();
        } catch { /* silent */ }
    }, [loadFiles]);

    const handleRename = useCallback(async (id: string, label: string) => {
        try {
            await updateUserFile(id, { label: label.trim() || undefined });
            await loadFiles();
        } catch { /* silent */ }
    }, [loadFiles]);

    return (
        <div className="flex w-full max-w-3xl flex-col gap-4" dir={isAr ? 'rtl' : 'ltr'}>
            {/* Processing overlay for CV uploads */}
            <ProcessingOverlay active={isProcessing} onComplete={handleCvProcessingComplete} />

            {/* Header row */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold text-text-primary">{t('filesPageTitle')}</h2>
                    <p className="mt-0.5 text-sm text-text-secondary">{t('filesPageSubtitle')}</p>
                </div>
                <button
                    onClick={() => setUploadOpen(p => !p)}
                    className="flex items-center gap-2 rounded-full bg-gold px-4 py-2 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
                >
                    <MaterialIcon icon={uploadOpen ? 'close' : 'add'} className="text-base" />
                    {t('filesUploadNew')}
                </button>
            </div>

            {/* Error */}
            {error && (
                <div className="rounded-lg border border-rico-red/25 bg-rico-red/10 px-4 py-3 text-sm text-rico-red" role="alert">
                    {error}
                </div>
            )}

            {/* Upload panel */}
            {uploadOpen && (
                <UploadZone
                    docType={docType}
                    onDocTypeChange={setDocType}
                    onFileSelected={handleFileSelected}
                    isUploading={isUploading}
                    t={t}
                />
            )}

            {/* File list */}
            {loading ? (
                <div className="py-12 text-center">
                    <MaterialIcon icon="hourglass_empty" className="animate-spin text-2xl text-text-tertiary" />
                </div>
            ) : files.length === 0 ? (
                <Card className="bg-surface-elevated/50">
                    <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
                        <MaterialIcon icon="folder_open" className="text-4xl text-text-tertiary" />
                        <p className="font-semibold text-text-primary">{t('filesEmpty')}</p>
                        <p className="text-sm text-text-secondary">{t('filesEmptyHint')}</p>
                        <button
                            onClick={() => setUploadOpen(true)}
                            className="mt-2 rounded-full bg-gold px-5 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90"
                        >
                            {t('uploadYourCV')}
                        </button>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                    {files.map(doc => (
                        <FileCard
                            key={doc.id}
                            doc={doc}
                            isAr={isAr}
                            t={t}
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

// ── Guest upload view (unchanged flow) ────────────────────────────────────────

interface GuestUploadViewProps {
    isAr: boolean;
    t: (k: TranslationKey) => string;
    router: ReturnType<typeof useRouter>;
}

function GuestUploadView({ isAr, t, router }: GuestUploadViewProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [uploadComplete, setUploadComplete] = useState(false);
    const [error, setError] = useState('');

    const handleUpload = useCallback(async (file: File) => {
        setIsUploading(true);
        setError('');
        try {
            await uploadCV(file, getGuestUploadUserId());
            setIsUploading(false);
            setIsProcessing(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('uploadError'));
            setIsUploading(false);
        }
    }, [t]);

    const handleProcessingComplete = useCallback(() => {
        setIsProcessing(false);
        setUploadComplete(true);
        setTimeout(() => router.push('/command?cv=ready'), 2000);
    }, [router]);

    return (
        <div dir={isAr ? 'rtl' : 'ltr'} className="flex w-full max-w-5xl flex-col gap-6 text-start">
            <ProcessingOverlay active={isProcessing} onComplete={handleProcessingComplete} />

            {uploadComplete ? (
                <PageTransition>
                    <Card className="bg-surface-elevated/70">
                        <CardContent className="flex flex-col items-center px-5 py-12 text-center sm:px-8">
                            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gold/10 text-gold">
                                <MaterialIcon icon="check_circle" className="text-4xl" />
                            </div>
                            <h1 className="text-2xl font-bold text-text-primary sm:text-3xl">
                                {t('uploadReadyHeading')}
                            </h1>
                            <p className="mt-3 max-w-xl text-sm leading-6 text-text-secondary sm:text-base">
                                {t('uploadReadyBody')}
                            </p>
                            <div className="mt-6 h-1 w-10 animate-pulse rounded-full bg-gold" />
                        </CardContent>
                    </Card>
                </PageTransition>
            ) : (
                <PageTransition>
                    <>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                            <div className="min-w-0">
                                <h2 className="text-xl font-semibold text-text-primary">{t('uploadYourCV')}</h2>
                                <p className="mt-1 max-w-2xl text-sm leading-6 text-text-secondary">
                                    {t('uploadCvSubtitle')}
                                </p>
                            </div>
                            <Badge variant="secondary" className="text-[11px]">{t('uploadPDF')}</Badge>
                        </div>

                        {error && (
                            <div className="rounded-lg border border-rico-red/25 bg-rico-red/10 p-3 text-center text-sm text-rico-red" role="alert">
                                {error}
                            </div>
                        )}

                        <Card
                            className={`bg-surface-elevated/70 transition-colors ${isDragging ? 'border-gold/50 bg-gold/[0.04]' : 'hover:border-gold/25'}`}
                            onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                            onDragLeave={() => setIsDragging(false)}
                            onDrop={e => { e.preventDefault(); setIsDragging(false); const f = e.dataTransfer.files[0]; if (f) handleUpload(f); }}
                        >
                            <CardContent className="p-5 sm:p-8 lg:p-10">
                                <div className="flex min-h-[360px] flex-col items-center justify-center rounded-xl border border-dashed border-border-soft bg-surface-glass px-4 py-8 text-center sm:px-8">
                                    <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-subtle text-text-secondary">
                                        <MaterialIcon icon="upload_file" className="text-4xl" />
                                    </div>
                                    <p className="text-base font-semibold text-text-primary sm:text-lg">
                                        {isDragging ? t('uploadDropHere') : t('uploadDragDrop')}
                                    </p>
                                    <p className="mt-2 text-sm text-text-secondary">{t('uploadOr')}</p>
                                    <label className="mt-6 inline-flex cursor-pointer">
                                        <input type="file" accept=".pdf" onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = ''; }} className="sr-only" disabled={isUploading} />
                                        <span className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-gold px-6 py-3 text-sm font-bold text-[#0a0a1a] transition-colors hover:bg-gold-hover aria-disabled:opacity-60">
                                            {isUploading ? (<><MaterialIcon icon="hourglass_empty" className="animate-spin" /><span>{t('uploadProcessing')}</span></>) : (<><span>{t('uploadSelectFile')}</span><MaterialIcon icon="folder_open" /></>)}
                                        </span>
                                    </label>
                                    <div className="mt-8 w-full max-w-sm border-t border-border-subtle pt-6">
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-tertiary">{t('uploadSupportedFormats')}</p>
                                        <div className="mt-3 flex justify-center">
                                            <Badge variant="outline" className="text-[10px]">{t('uploadPDF')}</Badge>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <div className="flex items-start justify-center gap-2 text-center">
                            <MaterialIcon icon="lock" className="mt-0.5 text-sm text-text-tertiary" />
                            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-tertiary">
                                {t('uploadSecureProcessing')}
                            </p>
                        </div>
                    </>
                </PageTransition>
            )}
        </div>
    );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function UploadPage() {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === 'ar';
    const router = useRouter();
    const [isAuth, setIsAuth] = useState<boolean | null>(null);

    useEffect(() => {
        fetchMe().then(me => setIsAuth(me.authenticated)).catch(() => setIsAuth(false));
    }, []);

    const title = isAuth ? t('filesPageTitle') : t('uploadYourCV');
    const subtitle = isAuth ? t('filesPageSubtitle') : t('uploadCvSubtitle');

    return (
        <AppShell title={title} subtitle={subtitle}>
            {isAuth === null ? (
                <div className="py-20 text-center">
                    <MaterialIcon icon="hourglass_empty" className="animate-spin text-2xl text-text-tertiary" />
                </div>
            ) : isAuth ? (
                <FileManagerView isAr={isAr} t={t} router={router} />
            ) : (
                <GuestUploadView isAr={isAr} t={t} router={router} />
            )}
        </AppShell>
    );
}

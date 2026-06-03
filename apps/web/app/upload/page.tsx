'use client';

import { AppShell } from '@/components/layout/AppShell';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { PageTransition } from '@/components/ui/PageTransition';
import { ProcessingOverlay } from '@/components/ui/ProcessingOverlay';
import { uploadCV } from '@/lib/api';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTranslation } from '@/lib/translations';
import { useRouter } from 'next/navigation';
import React, { useCallback, useState } from 'react';

function getGuestUploadUserId(): string {
    let sessionId = window.localStorage.getItem('rico_sid');
    if (!sessionId) {
        sessionId = `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
        window.localStorage.setItem('rico_sid', sessionId);
    }
    return `public:${sessionId}`;
}

export default function UploadPage() {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [uploadComplete, setUploadComplete] = useState(false);
    const [error, setError] = useState('');
    const router = useRouter();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isRTL = language === 'ar';

    const handleUpload = useCallback(async (file: File) => {
        setIsUploading(true);
        setError('');
        try {
            await uploadCV(file, getGuestUploadUserId());
            setIsUploading(false);
            setIsProcessing(true);
        } catch (err) {
            console.error('Upload failed:', err);
            setError(err instanceof Error ? err.message : t('uploadError'));
            setIsUploading(false);
        }
    }, [t]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback(() => {
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback(async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) {
            await handleUpload(file);
        }
    }, [handleUpload]);

    const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            await handleUpload(file);
        }
        e.target.value = '';
    }, [handleUpload]);

    const handleProcessingComplete = useCallback(() => {
        setIsProcessing(false);
        setUploadComplete(true);
        setTimeout(() => router.push('/command?cv=ready'), 2000);
    }, [router]);

    return (
        <AppShell
            title={t('uploadYourCV')}
            subtitle={t('uploadCvSubtitle')}
        >
            {/* Cinematic processing overlay */}
            <ProcessingOverlay active={isProcessing} onComplete={handleProcessingComplete} />

            <div
                dir={isRTL ? 'rtl' : 'ltr'}
                className="flex w-full max-w-5xl flex-col gap-6 text-start"
            >
                {uploadComplete ? (
                    <PageTransition>
                        <Card className="bg-surface-elevated/70">
                            <CardContent className="flex flex-col items-center px-5 py-12 text-center sm:px-8">
                                <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-magenta-soft text-magenta">
                                    <MaterialIcon icon="check_circle" className="text-4xl" />
                                </div>
                                <h1 className="text-2xl font-bold text-text-primary sm:text-3xl">
                                    {t('uploadReadyHeading')}
                                </h1>
                                <p className="mt-3 max-w-xl text-sm leading-6 text-text-secondary sm:text-base">
                                    {t('uploadReadyBody')}
                                </p>
                                <div className="mt-6 h-1 w-10 rounded-full bg-magenta animate-pulse" />
                            </CardContent>
                        </Card>
                    </PageTransition>
                ) : (
                    <PageTransition>
                        <>
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                <div className="min-w-0">
                                    <h2 className="text-xl font-semibold text-text-primary">
                                        {t('uploadYourCV')}
                                    </h2>
                                    <p className="mt-1 max-w-2xl text-sm leading-6 text-text-secondary">
                                        {t('uploadCvSubtitle')}
                                    </p>
                                </div>
                                <Badge variant="secondary" className="text-[11px]">
                                    {t('uploadPDF')}
                                </Badge>
                            </div>

                            {error && (
                                <div className="rounded-lg border border-rico-red/25 bg-rico-red/10 p-3 text-center text-sm text-rico-red" role="alert">
                                    {error}
                                </div>
                            )}

                            <Card
                                className={`bg-surface-elevated/70 transition-colors ${isDragging ? 'border-magenta/50 bg-magenta-soft/40' : 'hover:border-magenta/25'
                                    }`}
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
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
                                            <input
                                                type="file"
                                                accept=".pdf"
                                                onChange={handleFileSelect}
                                                className="sr-only"
                                                disabled={isUploading}
                                            />
                                            <span className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-magenta px-6 py-3 text-sm font-bold text-background transition-colors hover:bg-magenta-hover aria-disabled:opacity-60">
                                                {isUploading ? (
                                                    <>
                                                        <MaterialIcon icon="hourglass_empty" className="animate-spin" />
                                                        <span>{t('uploadProcessing')}</span>
                                                    </>
                                                ) : (
                                                    <>
                                                        <span>{t('uploadSelectFile')}</span>
                                                        <MaterialIcon icon="folder_open" />
                                                    </>
                                                )}
                                            </span>
                                        </label>

                                        <div className="mt-8 w-full max-w-sm border-t border-border-subtle pt-6">
                                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-tertiary">
                                                {t('uploadSupportedFormats')}
                                            </p>
                                            <div className="mt-3 flex justify-center">
                                                <Badge variant="outline" className="text-[10px]">
                                                    {t('uploadPDF')}
                                                </Badge>
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
        </AppShell>
    );
}

'use client';

import { AuraGlow } from '@/components/ui/AuraGlow';
import { GlassPanel } from '@/components/ui/GlassPanel';
import { MaterialIcon } from '@/components/ui/MaterialIcon';
import { PageTransition } from '@/components/ui/PageTransition';
import { ProcessingOverlay } from '@/components/ui/ProcessingOverlay';
import { uploadCV } from '@/lib/api';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

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

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) {
            await handleUpload(file);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            await handleUpload(file);
        }
    };

    const handleProcessingComplete = () => {
        setIsProcessing(false);
        setUploadComplete(true);
        setTimeout(() => router.push('/command?cv=ready'), 2000);
    };

    const handleUpload = async (file: File) => {
        setIsUploading(true);
        setError('');
        try {
            await uploadCV(file, getGuestUploadUserId());
            setIsUploading(false);
            setIsProcessing(true);
        } catch (err) {
            console.error('Upload failed:', err);
            setError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
            setIsUploading(false);
        }
    };

    return (
        <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
            {/* Cinematic processing overlay */}
            <ProcessingOverlay active={isProcessing} onComplete={handleProcessingComplete} />

            {/* Atmospheric Background */}
            <AuraGlow variant="magenta" position="top-right" className="animate-pulse-magenta" />
            <AuraGlow variant="cyan" position="bottom-left" className="animate-pulse-magenta" style={{ animationDelay: '-2s' }} />

            {/* Main Content */}
            <main className="relative z-10 w-full max-w-2xl px-container-padding-mobile md:px-container-padding-desktop">
                {uploadComplete ? (
                    <PageTransition>
                        <GlassPanel className="p-12 rounded-2xl border border-border-soft text-center">
                            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
                                <MaterialIcon icon="check_circle" className="text-primary text-5xl" />
                            </div>
                            <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4">Your profile is ready</h1>
                            <p className="text-body-lg text-on-surface-variant mb-4">
                                Rico has read your CV and prepared your job search profile. Redirecting to your dashboard...
                            </p>
                            <div className="flex justify-center">
                                <div className="w-8 h-0.5 bg-[var(--magenta)] rounded-full animate-pulse" />
                            </div>
                        </GlassPanel>
                    </PageTransition>
                ) : (
                    <PageTransition>
                        <>
                            <div className="text-center mb-12">
                                <h1 className="font-headline-xl text-headline-xl text-on-surface mb-4 tracking-tight">
                                    Upload your CV
                                </h1>
                                <p className="font-body-lg text-body-lg text-on-surface-variant">
                                    Let Rico build your career profile and find matching UAE jobs
                                </p>
                            </div>

                            {error && (
                                <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center animate-[fadeSlideIn_0.3s_ease-out]">
                                    {error}
                                </div>
                            )}

                            <GlassPanel
                                className={`p-16 rounded-2xl border border-border-soft text-center transition-all ${isDragging ? 'border-primary/50 bg-primary/5' : 'hover:border-primary/30'
                                    }`}
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                            >
                                <div className="mb-8">
                                    <MaterialIcon icon="upload_file" className="text-6xl text-on-surface-variant/40 mb-4" />
                                    <p className="text-body-lg text-on-surface-variant mb-2">
                                        {isDragging ? 'Drop your CV here' : 'Drag and drop your CV'}
                                    </p>
                                    <p className="text-sm text-on-surface-variant/60">or</p>
                                </div>

                                <label className="inline-block cursor-pointer">
                                    <input
                                        type="file"
                                        accept=".pdf"
                                        onChange={handleFileSelect}
                                        className="hidden"
                                        disabled={isUploading}
                                    />
                                    <span className="inline-flex items-center gap-2 px-8 py-4 bg-primary/10 text-primary rounded-full hover:bg-primary/20 transition-all">
                                        {isUploading ? (
                                            <>
                                                <MaterialIcon icon="hourglass_empty" className="animate-spin" />
                                                <span className="text-label-caps">Processing...</span>
                                            </>
                                        ) : (
                                            <>
                                                <span className="text-label-caps">Select File</span>
                                                <MaterialIcon icon="folder_open" />
                                            </>
                                        )}
                                    </span>
                                </label>

                                <div className="mt-8 pt-8 border-t border-border-subtle">
                                    <p className="text-[10px] text-on-surface-variant/40 uppercase tracking-widest mb-4">
                                        Supported formats
                                    </p>
                                    <div className="flex justify-center gap-4">
                                        <span className="text-label-caps text-[10px] px-3 py-1 border border-border-soft rounded-full">PDF</span>
                                    </div>
                                </div>
                            </GlassPanel>

                            <div className="mt-8 flex items-center justify-center gap-3">
                                <MaterialIcon icon="lock" className="text-on-surface-variant/40 text-sm" />
                                <p className="text-[10px] text-on-surface-variant/40 uppercase tracking-widest">
                                    Secure CV processing — your CV is used only to build your Rico profile
                                </p>
                            </div>
                        </>
                    </PageTransition>
                )}
            </main>

            {/* Decoration */}
            <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
                <div className="absolute inset-0 opacity-[0.04] bg-[url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27%3E%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%27.85%27 numOctaves=%274%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27 opacity=%27.025%27/%3E%3C/svg%3E')]" />
            </div>
        </div>
    );
}

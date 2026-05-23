'use client';

import React, { useEffect, useState } from 'react';

const PROCESSING_STAGES = [
    'Analyzing document structure...',
    'Extracting career trajectory...',
    'Mapping skill topology...',
    'Building intelligence profile...',
    'Calibrating opportunity vectors...',
];

interface ProcessingOverlayProps {
    active: boolean;
    onComplete?: () => void;
}

/**
 * Cinematic processing overlay with pulsing rings and rotating status text.
 * Shows during CV upload / profile generation.
 */
export function ProcessingOverlay({ active, onComplete }: ProcessingOverlayProps) {
    const [stageIndex, setStageIndex] = useState(0);

    useEffect(() => {
        const resetTimer = setTimeout(() => setStageIndex(0), 0);

        if (!active) {
            return () => clearTimeout(resetTimer);
        }
        const interval = setInterval(() => {
            setStageIndex((prev) => {
                const next = prev + 1;
                if (next >= PROCESSING_STAGES.length) {
                    clearInterval(interval);
                    onComplete?.();
                    return prev;
                }
                return next;
            });
        }, 1800);
        return () => {
            clearTimeout(resetTimer);
            clearInterval(interval);
        };
    }, [active, onComplete]);

    if (!active) return null;

    return (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm">
            {/* Pulsing rings */}
            <div className="relative w-32 h-32 mb-10">
                <div className="absolute inset-0 rounded-full border border-[var(--magenta)]/30 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite]" />
                <div className="absolute inset-3 rounded-full border border-[var(--cyan)]/20 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite_0.4s]" />
                <div className="absolute inset-6 rounded-full border border-[var(--magenta)]/10 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite_0.8s]" />
                {/* Core dot */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-4 h-4 rounded-full bg-[var(--magenta)] shadow-[0_0_24px_var(--magenta-glow)]" />
                </div>
            </div>

            {/* Stage text */}
            <p
                key={stageIndex}
                className="text-[10px] uppercase tracking-[0.25em] text-white/60 animate-[fadeSlideIn_0.5s_ease-out]"
            >
                {PROCESSING_STAGES[stageIndex]}
            </p>

            {/* Progress dots */}
            <div className="flex gap-1.5 mt-6">
                {PROCESSING_STAGES.map((_, i) => (
                    <div
                        key={i}
                        className={`w-1.5 h-1.5 rounded-full transition-all duration-500 ${
                            i <= stageIndex
                                ? 'bg-[var(--magenta)] shadow-[0_0_8px_var(--magenta-glow)]'
                                : 'bg-white/10'
                        }`}
                    />
                ))}
            </div>
        </div>
    );
}

'use client';

import React, { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface PageTransitionProps {
    children: React.ReactNode;
    className?: string;
    /** Delay in ms before content appears (stagger children) */
    delay?: number;
}

/**
 * Cinematic page entrance animation.
 * Fades in + slides up on mount. Zero external dependencies.
 */
export function PageTransition({ children, className, delay = 0 }: PageTransitionProps) {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const timer = setTimeout(() => setVisible(true), delay);
        return () => clearTimeout(timer);
    }, [delay]);

    return (
        <div
            className={cn(
                'transition-all duration-700 ease-out',
                visible
                    ? 'opacity-100 translate-y-0'
                    : 'opacity-0 translate-y-6',
                className,
            )}
        >
            {children}
        </div>
    );
}

/**
 * Staggered children entrance — each child fades in sequentially.
 */
export function StaggerChildren({
    children,
    baseDelay = 80,
    className,
}: {
    children: React.ReactNode;
    baseDelay?: number;
    className?: string;
}) {
    return (
        <div className={className}>
            {React.Children.map(children, (child, i) => (
                <PageTransition delay={baseDelay * (i + 1)} key={i}>
                    {child}
                </PageTransition>
            ))}
        </div>
    );
}

'use client';

import { cn } from '@/lib/utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import { MaterialIcon } from '../ui/MaterialIcon';

interface NavigationProps {
    className?: string;
}

export const Navigation = React.forwardRef<HTMLElement, NavigationProps>(
    ({ className }, ref) => {
        const pathname = usePathname();

        const navClass = (href: string, activeIcon: string) =>
            pathname === href
                ? activeIcon
                : 'text-on-surface-variant/60 px-6 py-2 flex flex-col items-center gap-1 hover:bg-white/5 transition-all duration-300 active:scale-95';

        return (
            <nav
                ref={ref as any}
                className={cn(
                    // bottom inset keeps the floating pill clear of the iOS home indicator
                    'fixed bottom-[max(1.5rem,env(safe-area-inset-bottom))] left-1/2 -translate-x-1/2 z-50',
                    'flex items-center gap-1 rounded-full border border-white/10 px-2 py-2',
                    'bg-[rgba(10,10,24,0.72)] backdrop-blur-2xl',
                    'shadow-[0_22px_60px_rgba(5,5,16,0.32)]',
                    className
                )}
                aria-label="Section navigation"
            >
                <Link
                    href="/command"
                    aria-current={pathname === "/command" ? "page" : undefined}
                    className={navClass('/command', 'rounded-full border border-primary/25 bg-primary/10 px-5 py-2 text-primary flex flex-col items-center gap-1 shadow-[0_10px_30px_rgba(91,79,255,0.18)] transition-all duration-300 active:scale-95')}
                >
                    <MaterialIcon icon="auto_awesome" filled size={20} />
                    <span className="text-label-caps text-[10px]">Command</span>
                </Link>
                <Link
                    href="/signals"
                    aria-current={pathname === "/signals" ? "page" : undefined}
                    className={navClass('/signals', 'rounded-full border border-primary/25 bg-primary/10 px-5 py-2 text-primary flex flex-col items-center gap-1 shadow-[0_10px_30px_rgba(91,79,255,0.18)] transition-all duration-300 active:scale-95')}
                >
                    <MaterialIcon icon="insights" size={20} />
                    <span className="text-label-caps text-[10px]">Signals</span>
                </Link>
                <Link
                    href="/flow"
                    aria-current={pathname === "/flow" ? "page" : undefined}
                    className={navClass('/flow', 'rounded-full border border-primary/25 bg-primary/10 px-5 py-2 text-primary flex flex-col items-center gap-1 shadow-[0_10px_30px_rgba(91,79,255,0.18)] transition-all duration-300 active:scale-95')}
                >
                    <MaterialIcon icon="waves" size={20} />
                    <span className="text-label-caps text-[10px]">Flow</span>
                </Link>
                <Link
                    href="/archive"
                    aria-current={pathname === "/archive" ? "page" : undefined}
                    className={navClass('/archive', 'rounded-full border border-primary/25 bg-primary/10 px-5 py-2 text-primary flex flex-col items-center gap-1 shadow-[0_10px_30px_rgba(91,79,255,0.18)] transition-all duration-300 active:scale-95')}
                >
                    <MaterialIcon icon="history" size={20} />
                    <span className="text-label-caps text-[10px]">Archive</span>
                </Link>
            </nav>
        );
    }
);

Navigation.displayName = 'Navigation';

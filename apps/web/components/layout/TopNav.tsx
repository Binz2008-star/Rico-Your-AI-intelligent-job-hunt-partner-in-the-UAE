'use client';

import { cn } from '@/lib/utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import { MaterialIcon } from '../ui/MaterialIcon';

interface TopNavProps {
    className?: string;
}

export const TopNav = React.forwardRef<HTMLElement, TopNavProps>(
    ({ className }, ref) => {
        const pathname = usePathname();

        const linkClass = (href: string) =>
            pathname === href
                ? 'rounded-full border border-primary/30 bg-primary/10 px-4 py-2 text-primary shadow-[0_8px_24px_rgba(91,79,255,0.18)]'
                : 'rounded-full border border-transparent px-4 py-2 text-on-surface-variant/75 hover:border-white/10 hover:bg-white/[0.03] hover:text-on-surface transition-all duration-300';

        return (
            <header
                ref={ref as any}
                className={cn(
                    'fixed top-4 w-full z-50 px-4 md:px-container-padding-desktop',
                    className
                )}
            >
                <div className="mx-auto flex w-full max-w-7xl items-center justify-between rounded-full border border-white/10 bg-[rgba(10,10,24,0.6)] px-4 py-3 backdrop-blur-2xl shadow-[0_18px_50px_rgba(5,5,16,0.28)]">
                    <Link href="/" className="flex items-center gap-3 text-on-surface">
                        <span className="flex h-9 w-9 items-center justify-center rounded-[12px] bg-gradient-to-br from-[#5b4fff] to-[#8b5cf6] text-sm font-black text-white shadow-[0_4px_18px_rgba(91,79,255,0.32)]">
                            R
                        </span>
                        <span className="font-headline-lg text-[18px] tracking-tight">
                            Rico<span className="text-primary"> AI</span>
                        </span>
                    </Link>
                    <div className="flex items-center gap-3">
                        <nav className="hidden md:flex items-center gap-2" aria-label="Primary navigation">
                            <Link
                                href="/command"
                                aria-current={pathname === "/command" ? "page" : undefined}
                                className={linkClass("/command")}
                            >
                                Command
                            </Link>
                            <Link
                                href="/signals"
                                aria-current={pathname === "/signals" ? "page" : undefined}
                                className={linkClass("/signals")}
                            >
                                Signals
                            </Link>
                            <Link
                                href="/flow"
                                aria-current={pathname === "/flow" ? "page" : undefined}
                                className={linkClass("/flow")}
                            >
                                Flow
                            </Link>
                            <Link
                                href="/archive"
                                aria-current={pathname === "/archive" ? "page" : undefined}
                                className={linkClass("/archive")}
                            >
                                Archive
                            </Link>
                        </nav>
                        <Link
                            href="/profile"
                            aria-label="Profile"
                            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-primary transition-all hover:border-primary/30 hover:bg-primary/10"
                        >
                            <MaterialIcon icon="account_circle" />
                        </Link>
                    </div>
                </div>
            </header>
        );
    }
);

TopNav.displayName = 'TopNav';

import React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { MaterialIcon } from '../ui/MaterialIcon';

interface TopNavProps {
  className?: string;
}

export const TopNav = React.forwardRef<HTMLElement, TopNavProps>(
  ({ className }, ref) => {
    return (
      <header
        ref={ref as any}
        className={cn(
          'fixed top-0 w-full z-50',
          'flex justify-between items-center',
          'px-container-padding-desktop py-8',
          'bg-transparent',
          className
        )}
      >
        <div className="flex justify-between items-center w-full max-w-7xl">
          <Link href="/" className="font-headline-xl text-headline-xl tracking-tighter text-on-surface">
            Rico AI
          </Link>
          <div className="flex items-center gap-8">
            <nav className="hidden md:flex items-center gap-10">
              <Link
                href="/orchestrate"
                className="text-primary font-bold transition-colors duration-500 hover:text-primary"
              >
                Orchestrate
              </Link>
              <Link
                href="/signals"
                className="text-on-surface-muted font-normal hover:text-primary transition-colors duration-500"
              >
                Signals
              </Link>
              <Link
                href="/flow"
                className="text-on-surface-muted font-normal hover:text-primary transition-colors duration-500"
              >
                Flow
              </Link>
              <Link
                href="/archive"
                className="text-on-surface-muted font-normal hover:text-primary transition-colors duration-500"
              >
                Archive
              </Link>
            </nav>
            <div className="flex items-center gap-4">
              <MaterialIcon icon="account_circle" className="text-primary cursor-pointer hover:scale-110 transition-transform" />
            </div>
          </div>
        </div>
      </header>
    );
  }
);

TopNav.displayName = 'TopNav';

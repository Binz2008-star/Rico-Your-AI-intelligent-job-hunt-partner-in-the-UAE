import React from 'react';
import { cn } from '@/lib/utils';

interface AuraGlowProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'cyan' | 'magenta';
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'center';
}

export const AuraGlow = React.forwardRef<HTMLDivElement, AuraGlowProps>(
  ({ className, variant = 'cyan', position = 'top-left', ...props }, ref) => {
    const positionClasses = {
      'top-left': 'top-[-20%] left-[-10%]',
      'top-right': 'top-[-20%] right-[-10%]',
      'bottom-left': 'bottom-[-20%] left-[-10%]',
      'bottom-right': 'bottom-[-20%] right-[-10%]',
      'center': 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2',
    };

    const variantClasses = {
      cyan: 'aura-glow-cyan',
      magenta: 'aura-glow-magenta',
    };

    return (
      <div
        ref={ref}
        className={cn(
          'fixed pointer-events-none z-0 w-[60%] h-[60%]',
          positionClasses[position],
          variantClasses[variant],
          className
        )}
        {...props}
      />
    );
  }
);

AuraGlow.displayName = 'AuraGlow';

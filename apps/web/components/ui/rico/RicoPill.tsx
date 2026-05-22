"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";

type RicoPillVariant = "default" | "cyan" | "magenta";

interface RicoPillProps {
  children: ReactNode;
  variant?: RicoPillVariant;
  className?: string;
}

/**
 * RicoPill — Design system pill/chip
 *
 * Uses the new --rico-* design tokens for consistent pill styling.
 * Variants: default, cyan (brand secondary), magenta (brand primary)
 */
export function RicoPill({ children, variant = "default", className }: RicoPillProps) {
  const variantStyles: Record<RicoPillVariant, string> = {
    default: "bg-[rgba(255,255,255,0.04)] border-[var(--rico-border-soft)] text-[var(--rico-fg-2)]",
    cyan: "bg-[rgba(0,218,243,0.10)] border-[rgba(0,218,243,0.20)] text-[var(--rico-secondary-dim)]",
    magenta: "bg-[rgba(255,177,200,0.10)] border-[rgba(255,177,200,0.20)] text-[var(--rico-primary)]",
  };

  return (
    <div
      className={cn(
        // Base pill styles
        "inline-flex items-center gap-2",
        // Padding and sizing from design system
        "px-3.5 py-1.5",
        // Typography
        "text-[11px] font-normal",
        // Border radius (full pill)
        "rounded-[var(--r-full)]",
        // Border
        "border",
        // Variant
        variantStyles[variant],
        className
      )}
    >
      {children}
    </div>
  );
}

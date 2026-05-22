"use client";

import { cn } from "@/lib/utils";

type RicoStatusNodeVariant = "cyan" | "magenta";
type RicoStatusNodeAnimation = "none" | "flicker";

interface RicoStatusNodeProps {
  variant?: RicoStatusNodeVariant;
  animation?: RicoStatusNodeAnimation;
  className?: string;
}

/**
 * RicoStatusNode — Design system status indicator
 *
 * Uses the new --rico-* design tokens for consistent status indicators.
 * 6px circles with 10px outer glow (signature design system pattern).
 * Variants: cyan (active/secondary), magenta (primary)
 * Animations: none, flicker (for live status)
 */
export function RicoStatusNode({
  variant = "cyan",
  animation = "none",
  className,
}: RicoStatusNodeProps) {
  const variantStyles: Record<RicoStatusNodeVariant, string> = {
    cyan: "bg-[var(--rico-secondary-dim)] shadow-[0_0_10px_var(--rico-cyan-glow)]",
    magenta: "bg-[var(--rico-primary)] shadow-[0_0_10px_var(--rico-magenta-glow)]",
  };

  const animationStyles: Record<RicoStatusNodeAnimation, string> = {
    none: "",
    flicker: "animate-rico-flicker",
  };

  return (
    <div
      className={cn(
        // Base node styles from design system
        "w-1.5 h-1.5 rounded-full",
        "inline-block flex-shrink-0",
        // Variant
        variantStyles[variant],
        // Animation
        animationStyles[animation],
        className
      )}
      style={
        animation === "flicker"
          ? {
              animation: "rico-flicker 2s ease-in-out infinite",
            }
          : undefined
      }
    />
  );
}

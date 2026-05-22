"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface RicoGlassIslandProps {
  children: ReactNode;
  className?: string;
}

/**
 * RicoGlassIsland — Signature glass container
 *
 * Uses the new --rico-* design tokens for consistent glass styling.
 * Implements the design system's glass island pattern with backdrop blur
 * and subtle stroke borders.
 */
export function RicoGlassIsland({ children, className }: RicoGlassIslandProps) {
  return (
    <div
      className={cn(
        // Base glass styling from design system
        "relative overflow-hidden",
        // Background and backdrop
        "bg-[rgba(255,255,255,0.03)] backdrop-blur-[40px]",
        // Glass stroke borders (top and left for depth)
        "border-t-[0.5px] border-l-[0.5px]",
        "border-[rgba(255,255,255,0.10)]",
        // Radius from design system
        "rounded-[var(--r-xl)]",
        // Smooth transition
        "transition-all duration-[var(--dur-state)] ease-[var(--ease-out)]",
        "hover:bg-[rgba(255,255,255,0.05)]",
        className
      )}
    >
      {children}
    </div>
  );
}

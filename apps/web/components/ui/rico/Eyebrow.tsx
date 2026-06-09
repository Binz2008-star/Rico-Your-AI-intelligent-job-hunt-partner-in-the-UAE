"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface EyebrowProps {
  children: ReactNode;
  centered?: boolean;
  className?: string;
}

/**
 * Eyebrow — Section label with the 22px ember rule
 *
 * Mono uppercase with wide tracking (0.28em), preceded by a 22px
 * horizontal line in ember. Used for section intros across the design.
 *
 * Reference: Nocturne eyebrow with ember line rule.
 */
export function Eyebrow({ children, centered = false, className }: EyebrowProps) {
  return (
    <span
      className={cn(
        // Mono, uppercase, wide tracking
        "font-mono text-xs uppercase tracking-[0.28em] text-ember",
        // Flex layout with the 22px rule
        "inline-flex items-center gap-2",
        centered && "justify-center",
        className
      )}
    >
      {/* The 22px ember rule */}
      <span className="w-[22px] h-px bg-ember/70" aria-hidden="true" />
      {children}
    </span>
  );
}

"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface RicoSectionHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  className?: string;
  eyebrowClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
}

/**
 * RicoSectionHeader — Design system section header
 *
 * Uses the new --rico-* design tokens for consistent section headers.
 * Follows the design system's typography scale and spacing.
 */
export function RicoSectionHeader({
  eyebrow,
  title,
  description,
  className,
  eyebrowClassName,
  titleClassName,
  descriptionClassName,
}: RicoSectionHeaderProps) {
  return (
    <div className={cn("space-y-4", className)}>
      {eyebrow && (
        <p
          className={cn(
            // Eyebrow typography from design system
            "text-[11px] font-semibold",
            "tracking-[0.28em] uppercase",
            // Color
            "text-[var(--rico-secondary-dim)]",
            eyebrowClassName
          )}
        >
          {eyebrow}
        </p>
      )}
      <h2
        className={cn(
          // Title typography from design system
          "text-[clamp(40px,5vw,64px)] font-semibold",
          "tracking-[-0.02em] leading-[1.1]",
          // Color
          "text-[var(--rico-fg-1)]",
          titleClassName
        )}
      >
        {title}
      </h2>
      {description && (
        <p
          className={cn(
            // Description typography from design system
            "text-base leading-[1.5]",
            // Color
            "text-[var(--rico-fg-2)]",
            "max-w-2xl",
            descriptionClassName
          )}
        >
          {description}
        </p>
      )}
    </div>
  );
}

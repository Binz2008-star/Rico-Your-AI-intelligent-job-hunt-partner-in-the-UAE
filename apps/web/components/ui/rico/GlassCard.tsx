"use client";

import { cn } from "@/lib/utils";
import { ElementType, ComponentPropsWithoutRef, ReactNode } from "react";

interface GlassCardProps<T extends ElementType = "div"> {
  as?: T;
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  elevated?: boolean;
}

/**
 * GlassCard — Nocturne glass panel
 *
 * Polymorphic container with the signature Nocturne glass treatment:
 * - Gradient: surface-elevated → ink
 * - Hairline border (overlay/7%)
 * - Backdrop blur
 * - Inset highlight
 * - Optional interactive state (hover lift + cursor-pointer)
 *
 * Use elevated={true} for modal/floating cards (stronger shadow).
 */
export function GlassCard<T extends ElementType = "div">({
  as,
  children,
  className,
  interactive = false,
  elevated = false,
  ...props
}: GlassCardProps<T> & Omit<ComponentPropsWithoutRef<T>, keyof GlassCardProps<T>>) {
  const Component = as || "div";

  return (
    <Component
      className={cn(
        // Glass gradient: surface-elevated → ink
        "bg-gradient-to-b from-surface-elevated/85 to-surface/70",
        // Hairline border + inner ring (double-border glass depth)
        "border border-overlay/7",
        "relative before:pointer-events-none before:absolute before:inset-px before:rounded-[inherit] before:border before:border-overlay/5 before:content-['']",
        // Radius — Nocturne reference .glass-card (22px)
        "rounded-rico-lg",
        // Shadow + inset highlight — theme-aware via --shadow-color (soft on light)
        "[box-shadow:inset_0_1px_0_rgb(var(--overlay)_/_0.05),0_30px_80px_rgb(var(--shadow-color)_/_0.5)]",
        // Hover polish (all cards, hover-only): border brightens, shadow deepens
        "transition-[border-color,box-shadow,transform] duration-300",
        "hover:border-overlay/12",
        !elevated &&
          "hover:[box-shadow:inset_0_1px_0_rgb(var(--overlay)_/_0.06),0_34px_90px_rgb(var(--shadow-color)_/_0.55)]",
        // Backdrop blur
        "backdrop-blur-xl",
        // Interactive states
        interactive && [
          "cursor-pointer",
          "hover:-translate-y-0.5",
          "focus-visible:ring-2 focus-visible:ring-ember focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
        ],
        // Elevated variant (modal/floating — stronger, still theme-aware)
        elevated && "[box-shadow:inset_0_1px_0_rgb(var(--overlay)_/_0.05),0_40px_120px_rgb(var(--shadow-color)_/_0.6)]",
        className
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

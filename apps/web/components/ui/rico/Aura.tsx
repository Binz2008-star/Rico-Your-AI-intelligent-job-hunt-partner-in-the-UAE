"use client";

import { cn } from "@/lib/utils";

interface AuraProps {
  size?: "sm" | "md" | "lg";
  variant?: "ember" | "aura";
  className?: string;
  animate?: boolean;
}

/**
 * Aura — Breathing core component
 *
 * The signature Rico presence indicator. A radial gradient core with
 * two pulsing rings. Used in hero, chat avatar, loading states, final CTA.
 *
 * Variants:
 * - ember: Rico's voice (default) — warm amber signature
 * - aura: Intelligence/data — teal for fit scores, data moments
 *
 * Reduced motion: rings freeze, core glow stays (no layout shift)
 */
export function Aura({
  size = "md",
  variant = "ember",
  className,
  animate = true,
}: AuraProps) {
  const sizeClasses = {
    sm: "w-[54px] h-[54px]",
    md: "w-[90px] h-[90px]",
    lg: "w-[118px] h-[118px]",
  };

  const coreSizeClasses = {
    sm: "w-[24px] h-[24px]",
    md: "w-[40px] h-[40px]",
    lg: "w-[54px] h-[54px]",
  };

  const ringOffset = {
    sm: "-8px",
    md: "-14px",
    lg: "-18px",
  };

  const isEmber = variant === "ember";

  return (
    <div
      className={cn(
        "relative grid place-items-center",
        sizeClasses[size],
        className
      )}
      aria-hidden="true"
    >
      {/* Outer ring */}
      <span
        className={cn(
          "absolute inset-0 rounded-full border",
          isEmber ? "border-ember/25" : "border-aura/25",
          animate && "animate-pulse-ring"
        )}
        style={{
          animationDelay: "0ms",
          inset: ringOffset[size],
        }}
      />

      {/* Inner ring */}
      <span
        className={cn(
          "absolute inset-0 rounded-full border",
          isEmber ? "border-ember/40" : "border-aura/40",
          animate && "animate-pulse-ring"
        )}
        style={{
          animationDelay: "600ms",
        }}
      />

      {/* Core */}
      <span
        className={cn(
          "relative rounded-full",
          coreSizeClasses[size],
          isEmber
            ? "bg-[radial-gradient(circle_at_38%_34%,#fff,var(--gold-hover)_38%,var(--gold)_70%)]"
            : "bg-[radial-gradient(circle_at_38%_34%,#fff,var(--aura)_38%,var(--aura-dim)_70%)]",
          isEmber ? "shadow-[0_0_30px_rgba(240,169,74,0.7)]" : "shadow-[0_0_30px_rgba(111,233,208,0.5)]",
          animate && "animate-breathe"
        )}
      />
    </div>
  );
}

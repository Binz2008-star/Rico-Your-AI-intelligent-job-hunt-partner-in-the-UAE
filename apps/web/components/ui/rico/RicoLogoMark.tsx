"use client";

import { cn } from "@/lib/utils";

interface RicoLogoMarkProps {
  /** Badge square in px (default 30 — header size) */
  size?: number;
  /** Subtle breathing halo behind the badge */
  animate?: boolean;
  className?: string;
}

/**
 * RicoLogoMark — the Rico Hunt brand badge.
 *
 * Gold ember badge carrying a precision-target mark (ring, center dot,
 * four cardinal ticks): "the right role, located." Replaces the old
 * letter-R badge.
 *
 * Decorative — always pair with a visible "Rico Hunt" text label; the
 * whole badge is aria-hidden. The mark uses text-void so it renders
 * white-on-amber in light mode and ink-on-gold in dark mode (same
 * contrast behavior as the previous R letter). Geometry is symmetric,
 * so RTL mirroring is a no-op. The halo animates opacity only (no
 * layout impact) and freezes under prefers-reduced-motion.
 */
export function RicoLogoMark({
  size = 30,
  animate = true,
  className,
}: RicoLogoMarkProps) {
  const markSize = Math.round(size * 0.6);
  const radius = Math.round(size * 0.3);

  return (
    <span
      aria-hidden="true"
      className={cn("relative inline-grid shrink-0 place-items-center", className)}
      style={{ width: size, height: size }}
    >
      {/* Breathing halo */}
      {animate && (
        <span
          className="absolute inset-0 bg-ember/45 blur-[10px] animate-glow-pulse motion-reduce:animate-none"
          style={{ borderRadius: radius }}
        />
      )}

      {/* Badge */}
      <span
        className="absolute inset-0 bg-gradient-to-br from-ember-bright to-ember shadow-[0_0_18px_rgb(var(--gold)/0.4)]"
        style={{ borderRadius: radius }}
      />

      {/* Precision target mark */}
      <svg
        width={markSize}
        height={markSize}
        viewBox="0 0 24 24"
        fill="none"
        focusable="false"
        className="relative text-void"
      >
        <circle cx="12" cy="12" r="6.4" stroke="currentColor" strokeWidth="1.9" />
        <circle cx="12" cy="12" r="2.1" fill="currentColor" />
        <path
          d="M12 2.6v2.9M12 18.5v2.9M2.6 12h2.9M18.5 12h2.9"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

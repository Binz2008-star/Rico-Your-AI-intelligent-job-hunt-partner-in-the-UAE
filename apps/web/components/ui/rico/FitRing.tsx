"use client";

import { cn } from "@/lib/utils";

interface FitRingProps {
  value: number; // 0-100
  size?: number;
  strokeWidth?: number;
  label?: string;
  className?: string;
  threshold?: number; // color switch threshold, default 60
}

/**
 * FitRing — SVG score ring with color-by-threshold
 *
 * Displays a fit score (0-100) as a circular progress ring.
 * Color indicates quality: ember (< threshold, needs work) or aura (≥ threshold, good fit).
 * Default threshold: 60.
 *
 * Accessibility: role="img", aria-label includes value and label.
 */
export function FitRing({
  value,
  size = 96,
  strokeWidth = 6,
  label = "Fit",
  className,
  threshold = 60,
}: FitRingProps) {
  const clampedValue = Math.max(0, Math.min(100, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clampedValue / 100);

  // Color by threshold: ember for low (< 60), aura for good (≥ 60).
  // Token-driven so the ring follows the theme (AA-darkened in light mode).
  const isGoodFit = clampedValue >= threshold;
  const strokeColor = isGoodFit ? "rgb(var(--aura))" : "rgb(var(--gold))";

  // Scale the center type with the ring so small rings (e.g. size={44}) don't overflow.
  const valueFontSize = Math.round(size * 0.27);
  const labelFontSize = Math.max(8, Math.round(size * 0.094));

  return (
    <div
      className={cn("relative flex-shrink-0", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Fit score: ${clampedValue}${label ? ` ${label}` : ""}`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="-rotate-90"
      >
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(var(--overlay) / 0.08)"
          strokeWidth={strokeWidth}
        />

        {/* Value arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>

      {/* Center label */}
      <div className="absolute inset-0 grid place-content-center text-center">
        <span
          className={cn(
            "font-display font-semibold leading-none",
            isGoodFit ? "text-aura" : "text-ember"
          )}
          style={{ fontSize: valueFontSize }}
        >
          {clampedValue}
        </span>
        {label && (
          <span
            className="font-mono uppercase tracking-[0.18em] text-text-tertiary -mt-0.5"
            style={{ fontSize: labelFontSize }}
          >
            {label}
          </span>
        )}
      </div>
    </div>
  );
}

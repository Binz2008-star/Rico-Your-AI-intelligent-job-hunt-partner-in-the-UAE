"use client";

import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, ReactNode } from "react";

type RicoButtonVariant = "primary" | "magenta" | "ghost" | "outline";
type RicoButtonSize = "sm" | "md" | "lg";

interface RicoButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: RicoButtonVariant;
  size?: RicoButtonSize;
  disabled?: boolean;
}

/**
 * RicoButton — Design system button
 *
 * Uses the new --rico-* design tokens for consistent button styling.
 * Variants: primary (white-on-black), magenta (brand), ghost (transparent), outline
 * Sizes: sm, md, lg
 */
export function RicoButton({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  className,
  ...props
}: RicoButtonProps) {
  const variantStyles: Record<RicoButtonVariant, string> = {
    primary: "bg-[var(--rico-fg-1)] text-black hover:bg-[var(--rico-primary)] hover:text-[var(--rico-bg)]",
    magenta: "bg-[var(--rico-primary-container)] text-white hover:bg-[var(--rico-primary)] hover:text-[var(--rico-on-primary)]",
    ghost: "bg-transparent text-[var(--rico-fg-2)] border-[var(--rico-border-soft)] hover:bg-[rgba(255,255,255,0.05)] hover:text-[var(--rico-fg-1)] hover:border-[var(--rico-border-medium)]",
    outline: "bg-transparent text-[var(--rico-fg-1)] border-[var(--rico-border-soft)]",
  };

  const sizeStyles: Record<RicoButtonSize, string> = {
    sm: "px-4 py-2 text-[10px]",
    md: "px-6 py-3 text-[12px]",
    lg: "px-8 py-3.5 text-[13px]",
  };

  return (
    <button
      disabled={disabled}
      className={cn(
        // Base button styles
        "inline-flex items-center justify-center gap-2",
        // Typography from design system
        "font-semibold",
        "tracking-[0.10em] uppercase leading-none",
        // Border radius (full pill)
        "rounded-[var(--r-full)]",
        // Border
        "border border-transparent",
        // Cursor and user select
        "cursor-pointer select-none",
        "whitespace-nowrap",
        // Transition from design system
        "transition-all duration-[var(--dur-hover)] ease-[var(--ease-out)]",
        // Disabled state
        disabled && "opacity-40 cursor-not-allowed",
        // Variant and size
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

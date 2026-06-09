"use client";

import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, ReactNode } from "react";

type RicoButtonVariant = "primary" | "ember" | "magenta" | "ghost" | "outline";
type RicoButtonSize = "sm" | "md" | "lg";

interface RicoButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    children: ReactNode;
    variant?: RicoButtonVariant;
    size?: RicoButtonSize;
    disabled?: boolean;
}

/**
 * RicoButton — Nocturne design system button
 *
 * Variants:
 * - primary: ember bg + dark text (CTA, main actions)
 * - ember/magenta: glass bg + ember hover (alias for back-compat)
 * - ghost: transparent + ember border hover (secondary)
 * - outline: minimal border (tertiary)
 *
 * Note: "magenta" is retained as alias for "ember" (Nocturne rebrand).
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
        // Nocturne primary: ember bg, dark text, hover brightens
        primary:
            "bg-ember text-void hover:bg-ember-bright hover:shadow-[0_8px_30px_rgb(var(--gold)/0.35)] hover:-translate-y-px",
        // Ember: glass bg with ember accent on hover (alias: magenta for back-compat)
        ember:
            "bg-surface/50 text-text-primary border-overlay/12 hover:border-ember hover:bg-ember/5",
        // Back-compat: magenta now maps to ember
        magenta:
            "bg-surface/50 text-text-primary border-overlay/12 hover:border-ember hover:bg-ember/5",
        // Ghost: minimal, hover reveals
        ghost:
            "bg-transparent text-text-secondary border-overlay/12 hover:bg-overlay/5 hover:text-text-primary hover:border-overlay/16",
        // Outline: static border
        outline:
            "bg-transparent text-text-primary border-overlay/12",
    };

    const sizeStyles: Record<RicoButtonSize, string> = {
        sm: "px-4 py-2 text-[10px]",
        md: "px-6 py-3 text-[12px]",
        lg: "px-8 py-3.5 text-[13px]",
    };

    return (
        <button
            type="button"
            disabled={disabled}
            className={cn(
                // Base button styles
                "inline-flex items-center justify-center gap-2",
                // Typography from design system
                "font-semibold font-body",
                "tracking-[0.10em] uppercase leading-none",
                // Border radius (Nocturne: rounded-lg, not full pill)
                "rounded-lg",
                // Border
                "border",
                // Cursor and user select
                "cursor-pointer select-none",
                "whitespace-nowrap",
                // Focus ring: ember (Nocturne)
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ember focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
                // Transition
                "transition-all duration-200 ease-out",
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

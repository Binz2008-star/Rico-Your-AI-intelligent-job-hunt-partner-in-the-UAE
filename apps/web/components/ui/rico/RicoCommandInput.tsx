"use client";

import { cn } from "@/lib/utils";
import { InputHTMLAttributes, forwardRef } from "react";

interface RicoCommandInputProps extends InputHTMLAttributes<HTMLInputElement> {
  placeholder?: string;
}

/**
 * RicoCommandInput — Design system command input
 *
 * Uses the new --rico-* design tokens for consistent input styling.
 * Implements the design system's boxed glass input pattern.
 */
export const RicoCommandInput = forwardRef<HTMLInputElement, RicoCommandInputProps>(
  ({ placeholder = "Type a command...", className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        placeholder={placeholder}
        className={cn(
          // Base input styles
          "w-full",
          // Background and border from design system
          "bg-[rgba(255,255,255,0.04)]",
          "border border-[var(--rico-border-soft)]",
          // Border radius from design system
          "rounded-[var(--r-lg)]",
          // Typography from design system
          "text-[14px]",
          // Padding
          "px-3.5 py-3",
          // Color
          "text-[var(--rico-fg-1)]",
          // Placeholder color
          "placeholder:text-[var(--rico-fg-4)]",
          // Outline
          "outline-none",
          // Transition from design system
          "transition-all duration-[var(--dur-state)] ease-[var(--ease-out)]",
          // Focus state
          "focus:border-[var(--rico-primary-container)]",
          className
        )}
        {...props}
      />
    );
  }
);

RicoCommandInput.displayName = "RicoCommandInput";

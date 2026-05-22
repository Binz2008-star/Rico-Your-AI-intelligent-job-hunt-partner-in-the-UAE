"use client";

import { cn } from "@/lib/utils";
import { TextareaHTMLAttributes, forwardRef } from "react";

interface RicoCommandInputProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  placeholder?: string;
}

/**
 * RicoCommandInput — Design system command input
 *
 * Uses the new --rico-* design tokens for consistent input styling.
 * Implements the design system's boxed glass input pattern.
 * Rendered as a textarea (rows=1, resize-none) so Shift+Enter works for new lines.
 */
export const RicoCommandInput = forwardRef<HTMLTextAreaElement, RicoCommandInputProps>(
  ({ placeholder = "Type a command...", className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        rows={1}
        placeholder={placeholder}
        className={cn(
          // Base input styles
          "w-full",
          // Single-line appearance, multiline capable
          "resize-none min-h-[46px]",
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

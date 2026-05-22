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
 * Uses textarea to support multiline input with Shift+Enter for new lines.
 */
export const RicoCommandInput = forwardRef<HTMLTextAreaElement, RicoCommandInputProps>(
  ({ placeholder = "Type a command...", className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        placeholder={placeholder}
        rows={1}
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
          // Resize behavior
          "resize-none",
          // Min height for single line
          "min-h-[46px]",
          className
        )}
        {...props}
      />
    );
  }
);

RicoCommandInput.displayName = "RicoCommandInput";

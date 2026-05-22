"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";

type RicoMessageBubbleVariant = "user" | "assistant" | "system" | "error";

interface RicoMessageBubbleProps {
  children: ReactNode;
  variant?: RicoMessageBubbleVariant;
  className?: string;
  /**
   * Optional: wrap assistant messages in subtle glass for longer content
   * Default: false (typography-only style)
   */
  useGlassWrap?: boolean;
}

/**
 * RicoMessageBubble — Design system message bubble
 *
 * Typography-first approach (default):
 * - user: right-aligned, var(--rico-fg-1), no background
 * - assistant: left-aligned, var(--rico-fg-2), no background
 * - system: centered, var(--rico-fg-3), italic
 * - error: centered, var(--rico-error-bg), var(--rico-error)
 *
 * Internal style variants (for reference):
 * 1. typography-only (default) — clean, minimal, no background
 * 2. subtle glass assistant wrap — useGlassWrap=true for longer structured content
 * 3. compact structured/system style — variant="system" for system messages
 *
 * Accessible text semantics preserved.
 * Handles streaming/reflow gracefully with whitespace-pre-wrap.
 */
export function RicoMessageBubble({
  children,
  variant = "assistant",
  className,
  useGlassWrap = false,
}: RicoMessageBubbleProps) {
  const variantStyles: Record<RicoMessageBubbleVariant, string> = {
    user: "text-right text-[var(--rico-fg-1)]",
    assistant: "text-left text-[var(--rico-fg-2)]",
    system: "text-center text-[var(--rico-fg-3)] italic text-[13px]",
    error: "text-center text-[var(--rico-error)] bg-[var(--rico-error-bg)] px-4 py-2 rounded-lg",
  };

  const shouldUseGlass = variant === "assistant" && useGlassWrap;

  const content = (
    <div
      className={cn(
        // Base typography
        "text-[14px] leading-relaxed",
        // Whitespace handling for streaming/reflow
        "whitespace-pre-wrap",
        // Variant-specific styles
        variantStyles[variant],
        className
      )}
    >
      {children}
    </div>
  );

  if (shouldUseGlass) {
    return (
      <div className="max-w-[82%]">
        <div className="bg-[rgba(255,255,255,0.03)] backdrop-blur-[24px] border-t-[0.5px] border-l-[0.5px] border-[rgba(255,255,255,0.10)] rounded-[var(--r-xl)] px-4 py-3">
          {content}
        </div>
      </div>
    );
  }

  return content;
}

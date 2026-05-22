"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";
import Link from "next/link";

interface RicoDockNavItem {
  label: string;
  href?: string;
  isActive?: boolean;
  onClick?: () => void;
}

interface RicoDockNavProps {
  items: RicoDockNavItem[];
  className?: string;
}

/**
 * RicoDockNav — Design system bottom floating dock navigation
 *
 * Uses the new --rico-* design tokens for consistent dock navigation.
 * Implements the design system's signature floating dock pattern.
 * Renders as Link when href is present, otherwise as button.
 */
export function RicoDockNav({ items, className }: RicoDockNavProps) {
  const itemClassName = cn(
    // Base button styles
    "inline-flex items-center gap-2",
    // Padding
    "px-5 py-2.5",
    // Typography from design system
    "text-[11px] font-semibold",
    "tracking-[0.10em] uppercase",
    // Border radius (full pill)
    "rounded-[var(--r-full)]",
    // Border
    "border-0",
    // Cursor
    "cursor-pointer",
    // Transition from design system
    "transition-all duration-[var(--dur-hover)] ease-[var(--ease-out)]",
    // Default state
    "bg-transparent",
    "text-[rgba(226,189,198,0.6)]",
    "hover:bg-[rgba(255,255,255,0.05)] hover:text-[var(--rico-fg-1)]",
    // Active state
    "bg-[rgba(0,218,243,0.10)] text-[var(--rico-secondary-dim)]"
  );

  return (
    <div
      className={cn(
        // Fixed positioning from design system
        "fixed bottom-10 left-1/2 -translate-x-1/2 z-50",
        // Flex layout
        "flex items-center gap-2",
        // Padding
        "px-2 py-2",
        // Background and backdrop from design system
        "bg-[rgba(255,255,255,0.03)] backdrop-blur-[24px]",
        // Glass stroke borders
        "border-t-[0.5px] border-l-[0.5px]",
        "border-[rgba(255,255,255,0.10)]",
        // Border radius (full pill)
        "rounded-[var(--r-full)]",
        // Shadow from design system
        "shadow-[var(--shadow-dock)]",
        className
      )}
    >
      {items.map((item, index) => {
        if (item.href) {
          return (
            <Link
              key={index}
              href={item.href}
              className={cn(itemClassName, item.isActive && "bg-[rgba(0,218,243,0.10)] text-[var(--rico-secondary-dim)]")}
            >
              {item.label}
            </Link>
          );
        }

        return (
          <button
            key={index}
            onClick={item.onClick}
            className={cn(itemClassName, item.isActive && "bg-[rgba(0,218,243,0.10)] text-[var(--rico-secondary-dim)]")}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

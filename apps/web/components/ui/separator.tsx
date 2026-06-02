"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

interface SeparatorProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical"
  decorative?: boolean
}

const Separator = React.forwardRef<HTMLDivElement, SeparatorProps>(
  (
    { className, orientation = "horizontal", decorative = true, ...props },
    ref
  ) => {
    const semanticProps = decorative
      ? { "aria-hidden": true as const }
      : { role: "separator" as const, "aria-orientation": orientation }

    return (
      <div
        ref={ref}
        className={cn(
          "shrink-0 bg-border-soft",
          orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]",
          className
        )}
        {...semanticProps}
        {...props}
      />
    )
  }
)
Separator.displayName = "Separator"

export { Separator }

import * as React from "react"

import { cn } from "@/lib/utils"

export type BadgeVariant = "default" | "secondary" | "outline" | "ghost"

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
    variant?: BadgeVariant
}

const variantClasses: Record<BadgeVariant, string> = {
    default: "border-transparent bg-gold text-[#0a0a1a] hover:bg-gold-hover",
    secondary: "border-transparent bg-gold/10 text-gold hover:bg-gold/15",
    outline: "border-border-medium text-text-secondary hover:border-border-strong hover:text-white",
    ghost: "border-transparent text-text-muted hover:text-text-secondary",
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
    return (
        <span
            className={cn(
                "inline-flex items-center justify-center rounded-full border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 transition-colors",
                variantClasses[variant],
                className
            )}
            {...props}
        />
    )
}

export { Badge }


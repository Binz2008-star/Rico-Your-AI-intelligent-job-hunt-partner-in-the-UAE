"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

// Phase 1: Dependency-free placeholder Tooltip
// Full Radix UI implementation deferred to later phase

const TooltipProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => <>{children}</>

const Tooltip: React.FC<{ children: React.ReactNode; open?: boolean; onOpenChange?: (open: boolean) => void }> = ({ children }) => <>{children}</>

const TooltipTrigger: React.FC<{ children: React.ReactNode; asChild?: boolean }> = ({ children }) => <>{children}</>

const TooltipContent: React.FC<{ children: React.ReactNode; className?: string; sideOffset?: number }> = ({ children, className }) => (
    <div className={cn("hidden", className)}>{children}</div>
)

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger }


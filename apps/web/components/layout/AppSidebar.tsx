"use client";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MaterialIcon } from "../ui/MaterialIcon";
import { mainNavSections, navMeta, utilityNavItems } from "./app-nav";

interface AppSidebarProps {
    className?: string;
    user?: {
        name?: string;
        email?: string;
    };
    onLogout?: () => void;
}

export function AppSidebar({ className, user, onLogout }: AppSidebarProps) {
    const pathname = usePathname();

    const initials = user?.name
        ? user.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()
        : navMeta.brand.shortName;

    return (
        <TooltipProvider>
            <aside
                className={cn(
                    "flex h-full w-64 flex-col border-r border-border-soft bg-surface",
                    className
                )}
            >
                {/* Brand Header */}
                <div className="flex items-center gap-3 px-5 py-5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#f5a623] text-sm font-black text-[#0a0a1a] shadow-lg">
                        {navMeta.brand.shortName}
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-semibold text-text-primary">
                            {navMeta.brand.name}
                        </span>
                        <span className="text-[10px] text-text-muted">
                            {navMeta.brand.tagline}
                        </span>
                    </div>
                </div>

                <Separator />

                {/* Status Indicator */}
                <div className="flex items-center gap-2 px-5 py-3">
                    <span
                        className="h-2 w-2 rounded-full animate-pulse"
                        style={{ backgroundColor: navMeta.status.color }}
                    />
                    <span
                        className="text-xs font-medium"
                        style={{ color: navMeta.status.color }}
                    >
                        {navMeta.status.label} · {navMeta.status.region}
                    </span>
                </div>

                <Separator />

                {/* Main Navigation */}
                <nav className="flex-1 overflow-y-auto px-3 py-4">
                    {mainNavSections.map((section) => (
                        <div key={section.title} className="mb-6">
                            <h3 className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                                {section.title}
                            </h3>
                            <ul className="space-y-0.5">
                                {section.items.map((item) => {
                                    const isActive = pathname === item.href;
                                    return (
                                        <li key={item.href}>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Link
                                                        href={item.href}
                                                        className={cn(
                                                            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                                                            isActive
                                                                ? "bg-magenta-soft text-magenta"
                                                                : "text-text-secondary hover:bg-surface-subtle hover:text-text-primary"
                                                        )}
                                                    >
                                                        <MaterialIcon
                                                            icon={item.icon}
                                                            size={18}
                                                            className={cn(
                                                                "flex-shrink-0",
                                                                isActive ? "opacity-100" : "opacity-60"
                                                            )}
                                                        />
                                                        <span className="flex-1">{item.label}</span>
                                                        {item.badge && (
                                                            <Badge variant={isActive ? "default" : "secondary"}>
                                                                {item.badge}
                                                            </Badge>
                                                        )}
                                                    </Link>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {item.label}
                                                </TooltipContent>
                                            </Tooltip>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    ))}

                    {/* Utility Nav */}
                    <div>
                        <h3 className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                            Actions
                        </h3>
                        <ul className="space-y-0.5">
                            {utilityNavItems.map((item) => {
                                const isActive = pathname === item.href;
                                return (
                                    <li key={item.href}>
                                        <Link
                                            href={item.href}
                                            className={cn(
                                                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                                                isActive
                                                    ? "bg-cyan-soft text-cyan"
                                                    : "text-text-secondary hover:bg-surface-subtle hover:text-text-primary"
                                            )}
                                        >
                                            <MaterialIcon
                                                icon={item.icon}
                                                size={18}
                                                className={cn(
                                                    "flex-shrink-0",
                                                    isActive ? "opacity-100" : "opacity-60"
                                                )}
                                            />
                                            <span>{item.label}</span>
                                        </Link>
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                </nav>

                <Separator />

                {/* User Footer */}
                <div className="p-4">
                    <button
                        onClick={onLogout}
                        className="flex w-full items-center gap-3 rounded-lg p-2 transition-colors hover:bg-surface-subtle group"
                    >
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f5a623] text-xs font-bold text-[#0a0a1a]">
                            {initials}
                        </div>
                        <div className="flex-1 min-w-0 text-left">
                            <p className="text-sm font-medium text-text-primary truncate">
                                {user?.name ?? "User"}
                            </p>
                            <p className="text-xs text-text-muted truncate">
                                {user?.email ?? ""}
                            </p>
                        </div>
                        <MaterialIcon
                            icon="logout"
                            size={16}
                            className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity"
                        />
                    </button>
                </div>
            </aside>
        </TooltipProvider>
    );
}

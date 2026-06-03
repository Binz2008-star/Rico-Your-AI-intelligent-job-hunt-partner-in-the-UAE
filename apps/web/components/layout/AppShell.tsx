"use client";

import { cn } from "@/lib/utils";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";

interface AppShellProps {
    children: React.ReactNode;
    className?: string;
    title?: string;
    subtitle?: string;
    sidebarProps?: React.ComponentProps<typeof AppSidebar>;
    topbarProps?: Omit<React.ComponentProps<typeof AppTopbar>, "title" | "subtitle">;
    showSidebar?: boolean;
    showTopbar?: boolean;
}

export function AppShell({
    children,
    className,
    title,
    subtitle,
    sidebarProps,
    topbarProps,
    showSidebar = true,
    showTopbar = true,
}: AppShellProps) {
    return (
        <div className={cn("flex h-[100dvh] min-h-screen w-full bg-background", className)}>
            {/* Sidebar */}
            {showSidebar && <AppSidebar {...sidebarProps} />}

            {/* Main Content Area */}
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
                {/* Topbar */}
                {showTopbar && (
                    <AppTopbar title={title} subtitle={subtitle} {...topbarProps} />
                )}

                {/* Scrollable Content */}
                <main className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 lg:px-8">
                    <div className="mx-auto w-full max-w-7xl">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}

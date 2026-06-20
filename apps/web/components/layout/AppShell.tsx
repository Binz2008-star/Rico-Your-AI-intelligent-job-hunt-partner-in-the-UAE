"use client";

import { AuraGlow } from "@/components/ui/AuraGlow";
import { useLanguage } from "@/contexts/LanguageContext";
import { buildWhatsAppManageUrl } from "@/lib/billing";
import { cn } from "@/lib/utils";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { MobileBottomNav } from "./MobileBottomNav";

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
    const { language } = useLanguage();
    return (
        <div dir={language === "ar" ? "rtl" : "ltr"} className={cn("relative flex h-[100dvh] min-h-screen w-full bg-background", className)}>
            {/* Cinematic ambient glows — Pulse-style, same as DashboardShell */}
            <AuraGlow aria-hidden="true" variant="magenta" position="top-left" className="animate-pulse-magenta" />
            <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" className="animate-pulse-magenta" style={{ animationDelay: "-2s" }} />

            {/* Sidebar */}
            {showSidebar && <AppSidebar {...sidebarProps} />}

            {/* Main Content Area */}
            <div className="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
                {/* Topbar */}
                {showTopbar && (
                    <AppTopbar title={title} subtitle={subtitle} {...topbarProps} />
                )}

                {/* Scrollable Content */}
                <main className="flex-1 overflow-y-auto px-4 py-5 pb-24 sm:px-6 sm:pb-5 lg:px-8">
                    <div className="mx-auto w-full max-w-7xl">
                        {children}
                    </div>
                </main>
            </div>

            {/* Mobile bottom dock — only rendered below md breakpoint */}
            <MobileBottomNav />

            {/* Floating help button — bottom-right, links to WhatsApp support */}
            <a
                href={buildWhatsAppManageUrl()}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Support on WhatsApp"
                className="fixed bottom-6 end-5 z-50 flex h-11 w-11 items-center justify-center rounded-full border border-overlay/15 bg-surface-elevated/90 text-text-secondary shadow-lg backdrop-blur-sm transition-colors hover:bg-surface-subtle hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 md:bottom-8 md:end-6"
            >
                <span className="text-[17px] leading-none">?</span>
            </a>
        </div>
    );
}

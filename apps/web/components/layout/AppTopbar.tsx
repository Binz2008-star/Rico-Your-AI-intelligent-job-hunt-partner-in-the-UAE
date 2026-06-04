"use client";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MaterialIcon } from "../ui/MaterialIcon";

interface AppTopbarProps {
    className?: string;
    title?: string;
    subtitle?: string;
    actions?: React.ReactNode;
    showNav?: boolean;
}

const breadcrumbMap: Record<string, { labelKey: TranslationKey; icon: string }> = {
    "/dashboard": { labelKey: "navBreadcrumbOverview", icon: "dashboard" },
    "/profile": { labelKey: "profileTitle", icon: "person" },
    "/settings": { labelKey: "settings", icon: "settings" },
    "/subscription": { labelKey: "subscriptionTitle", icon: "workspace_premium" },
    "/jobs": { labelKey: "navBreadcrumbJobs", icon: "work" },
    "/saved-searches": { labelKey: "navBreadcrumbSaved", icon: "bookmark" },
    "/upload": { labelKey: "navBreadcrumbUpload", icon: "upload_file" },
    "/flow": { labelKey: "navBreadcrumbFlow", icon: "waves" },
    "/signals": { labelKey: "navBreadcrumbSignals", icon: "insights" },
    "/archive": { labelKey: "navBreadcrumbArchive", icon: "history" },
};

export function AppTopbar({
    className,
    title,
    subtitle,
    actions,
    showNav = true,
}: AppTopbarProps) {
    const pathname = usePathname();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const breadcrumb = breadcrumbMap[pathname];

    const displayTitle = title ?? (breadcrumb ? t(breadcrumb.labelKey) : "");

    return (
        <header
            className={cn(
                "sticky top-0 z-30 flex min-h-16 items-center justify-between gap-3 border-b border-overlay/8 bg-surface/80 px-4 py-3 backdrop-blur-xl sm:px-6",
                className
            )}
        >
            {/* Left: Breadcrumb / Title */}
            <div className="flex min-w-0 items-center gap-2 sm:gap-4">
                {showNav && (
                    <Link
                        href="/dashboard"
                        className="hidden items-center gap-2 text-text-secondary transition-colors hover:text-text-primary sm:flex"
                    >
                        <MaterialIcon icon="dashboard" size={18} />
                        <span className="text-sm font-medium">{t("navHome")}</span>
                    </Link>
                )}

                {showNav && displayTitle && (
                    <>
                        <MaterialIcon icon="chevron_right" size={16} className="hidden text-text-tertiary sm:block" />
                        <div className="flex min-w-0 items-center gap-2">
                            <MaterialIcon icon={breadcrumb?.icon ?? "chevron_right"} size={18} className="text-text-secondary" />
                            <h1 className="truncate text-sm font-semibold text-text-primary">{displayTitle}</h1>
                            {subtitle && (
                                <Badge variant="ghost" className="hidden sm:inline-flex">
                                    {subtitle}
                                </Badge>
                            )}
                        </div>
                    </>
                )}

                {!showNav && displayTitle && (
                    <h1 className="text-base font-semibold text-text-primary">{displayTitle}</h1>
                )}
            </div>

            {/* Right: Actions */}
            <div className="flex shrink-0 items-center gap-2 sm:gap-3">
                {actions}

                {/* Language & Theme */}
                <LanguageSwitcher />
                <ThemeToggle />

                {/* Quick Actions */}
                <Link
                    href="/command"
                    className={cn(
                        "flex items-center gap-2 rounded-lg border border-gold/25 bg-gold/8 px-3 py-1.5",
                        "text-xs font-semibold text-gold transition-colors hover:bg-gold/15 cursor-pointer"
                    )}
                >
                    <MaterialIcon icon="auto_awesome" size={16} />
                    <span className="hidden sm:inline">Command</span>
                </Link>
            </div>
        </header>
    );
}

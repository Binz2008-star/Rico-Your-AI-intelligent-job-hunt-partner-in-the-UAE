"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface DockTab {
    href: string;
    labelKey: TranslationKey;
    icon: React.ReactNode;
    activeIcon: React.ReactNode;
}

const TABS: DockTab[] = [
    {
        href: "/command",
        labelKey: "navAskRico",
        icon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 2a10 10 0 1 0 10 10" />
                <path d="M12 8v4l3 3" />
                <path d="M18.5 2.5a2.5 2.5 0 0 1 3.5 3.5l-6 6H13v-3l5.5-6z" />
            </svg>
        ),
        activeIcon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3" fill="currentColor" />
                <path d="M12 2a10 10 0 1 0 10 10" />
                <path d="M18.5 2.5a2.5 2.5 0 0 1 3.5 3.5l-6 6H13v-3l5.5-6z" />
            </svg>
        ),
    },
    {
        href: "/flow",
        labelKey: "navPipeline",
        icon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" />
            </svg>
        ),
        activeIcon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" fill="currentColor" />
            </svg>
        ),
    },
    {
        href: "/profile",
        labelKey: "profileTitle",
        icon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="8" r="4" />
                <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
            </svg>
        ),
        activeIcon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="8" r="4" fill="currentColor" fillOpacity="0.2" />
                <circle cx="12" cy="8" r="4" />
                <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
            </svg>
        ),
    },
    {
        href: "/settings",
        labelKey: "settings",
        icon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
        ),
        activeIcon: (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3" fill="currentColor" fillOpacity="0.3" />
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
        ),
    },
];

export function MobileBottomNav() {
    const pathname = usePathname();
    const { language } = useLanguage();
    const t = useTranslation(language);

    return (
        <nav
            className="md:hidden fixed bottom-0 inset-x-0 z-40 flex items-stretch border-t border-overlay/10 bg-surface/90 backdrop-blur-xl"
            style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
            aria-label="Mobile navigation"
        >
            {TABS.map((tab) => {
                const isActive = pathname === tab.href || pathname.startsWith(tab.href + "/");
                return (
                    <Link
                        key={tab.href}
                        href={tab.href}
                        aria-current={isActive ? "page" : undefined}
                        className={cn(
                            "relative flex flex-1 flex-col items-center justify-center gap-1 py-2.5 min-h-[56px] transition-colors duration-150 cursor-pointer",
                            isActive ? "text-gold" : "text-text-tertiary hover:text-text-secondary"
                        )}
                    >
                        {isActive && (
                            <span
                                className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] rounded-full bg-gold"
                                aria-hidden="true"
                            />
                        )}

                        <span className="flex items-center justify-center">
                            {isActive ? tab.activeIcon : tab.icon}
                        </span>

                        <span className={cn(
                            "text-[10px] font-semibold tracking-wide",
                            isActive ? "text-gold" : "text-text-tertiary"
                        )}>
                            {t(tab.labelKey)}
                        </span>
                    </Link>
                );
            })}
        </nav>
    );
}

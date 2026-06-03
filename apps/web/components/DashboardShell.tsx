"use client";

import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useLanguage } from "@/contexts/LanguageContext";
import { logout } from "@/lib/api";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

const MOBILE_NAV = [
    { href: "/command", icon: "auto_awesome", labelEn: "Command", labelAr: "الأوامر" },
    { href: "/jobs",    icon: "work",          labelEn: "Jobs",    labelAr: "وظائف" },
    { href: "/flow",   icon: "account_tree",  labelEn: "Flow",    labelAr: "التتبع" },
    { href: "/profile", icon: "account_circle", labelEn: "Profile", labelAr: "الملف" },
] as const;

interface DashboardShellProps {
    children: React.ReactNode;
    title?: string;
    subtitle?: string;
    actions?: React.ReactNode;
}

export function DashboardShell({
    children,
    title,
    subtitle,
    actions,
}: DashboardShellProps) {
    const router = useRouter();
    const pathname = usePathname();
    const { language } = useLanguage();
    const isRTL = language === "ar";
    const [signingOut, setSigningOut] = useState(false);

    async function handleLogout() {
        setSigningOut(true);
        try {
            await logout();
        } finally {
            router.push("/login");
            setSigningOut(false);
        }
    }

    return (
        <div className="relative min-h-screen overflow-x-hidden" dir={isRTL ? "rtl" : "ltr"}>
            <AuraGlow aria-hidden="true" variant="magenta" position="top-left" className="animate-pulse-magenta" />
            <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" className="animate-pulse-magenta" style={{ animationDelay: "-2s" }} />

            {/* Mobile bottom navigation — hidden on md+ where the header controls suffice */}
            <nav
                aria-label="Mobile navigation"
                className="fixed bottom-0 left-0 right-0 z-50 md:hidden border-t border-white/[0.08] bg-[rgba(10,10,24,0.88)] backdrop-blur-xl"
                style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
            >
                <div className="flex items-center justify-around px-1 py-1">
                    {MOBILE_NAV.map(({ href, icon, labelEn, labelAr }) => {
                        const active = pathname === href || (href !== "/command" && pathname.startsWith(href));
                        return (
                            <Link
                                key={href}
                                href={href}
                                aria-current={active ? "page" : undefined}
                                className={`flex flex-col items-center gap-0.5 px-3 py-2 rounded-xl transition-colors min-w-[56px] ${
                                    active
                                        ? "text-primary bg-primary/10"
                                        : "text-on-surface-variant hover:text-on-surface hover:bg-white/[0.04]"
                                }`}
                            >
                                <MaterialIcon icon={icon} size={22} />
                                <span className="text-[10px] font-medium leading-none">
                                    {isRTL ? labelAr : labelEn}
                                </span>
                            </Link>
                        );
                    })}
                </div>
            </nav>

            <main className="relative z-10 mx-auto max-w-7xl px-container-padding-mobile pb-28 pt-24 md:pb-24 md:px-container-padding-desktop md:pt-28">
                <GlassPanel className="mb-8 rounded-[28px] border border-white/10 px-5 py-5 md:px-8 md:py-7">
                    <div className="flex flex-col gap-6">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                            <div className="space-y-3">
                                {title && (
                                    <h1 className="font-headline-xl text-headline-xl tracking-tight text-on-surface">
                                        {title}
                                    </h1>
                                )}
                                {subtitle && (
                                    <p className="max-w-2xl text-body-md text-on-surface-variant">
                                        {subtitle}
                                    </p>
                                )}
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                                {actions}
                                <ThemeToggle />
                                <LanguageSwitcher />
                                <Link
                                    href="/command"
                                    className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-[12px] font-semibold text-primary transition-all hover:bg-primary/15"
                                >
                                    <MaterialIcon icon="auto_awesome" size={16} />
                                    {isRTL ? "مركز الأوامر" : "Command Center"}
                                </Link>
                                <button
                                    type="button"
                                    onClick={handleLogout}
                                    disabled={signingOut}
                                    className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-[12px] font-semibold text-on-surface-variant transition-all hover:border-white/20 hover:text-on-surface disabled:opacity-50"
                                >
                                    <MaterialIcon icon="logout" size={16} />
                                    {signingOut
                                        ? (isRTL ? "جاري الخروج..." : "Signing out...")
                                        : (isRTL ? "تسجيل الخروج" : "Sign out")}
                                </button>
                            </div>
                        </div>

                    </div>
                </GlassPanel>

                <div className="space-y-6">
                    {children}
                </div>
            </main>

        </div>
    );
}

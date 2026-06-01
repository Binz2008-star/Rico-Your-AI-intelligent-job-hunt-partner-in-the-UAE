"use client";

import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/contexts/LanguageContext";
import { logout } from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

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
            <main className="relative z-10 mx-auto max-w-7xl px-container-padding-mobile pb-24 pt-24 md:px-container-padding-desktop md:pt-28">
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

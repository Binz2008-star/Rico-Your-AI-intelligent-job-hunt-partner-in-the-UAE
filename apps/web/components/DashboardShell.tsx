"use client";

import { Navigation } from "@/components/layout/Navigation";
import { TopNav } from "@/components/layout/TopNav";
import { AuraGlow } from "@/components/ui/AuraGlow";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { MaterialIcon } from "@/components/ui/MaterialIcon";
import { logout } from "@/lib/api";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

interface DashboardShellProps {
    children: React.ReactNode;
    title?: string;
    subtitle?: string;
    actions?: React.ReactNode;
}

type DashboardRoute = {
    href: string;
    label: string;
    icon?: string;
};

const APP_ROUTES: readonly DashboardRoute[] = [
    { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
    { href: "/jobs", label: "Jobs", icon: "work" },
    { href: "/applications", label: "Applications", icon: "fact_check" },
    { href: "/profile", label: "Profile", icon: "account_circle" },
    { href: "/saved-searches", label: "Saved" },
    { href: "/settings", label: "Settings", icon: "settings" },
];

function isActive(pathname: string, href: string): boolean {
    return pathname === href || pathname.startsWith(`${href}/`);
}

export function DashboardShell({
    children,
    title,
    subtitle,
    actions,
}: DashboardShellProps) {
    const pathname = usePathname();
    const router = useRouter();
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
        <div className="relative min-h-screen overflow-x-hidden">
            <AuraGlow aria-hidden="true" variant="magenta" position="top-left" className="animate-pulse-magenta" />
            <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" className="animate-pulse-magenta" style={{ animationDelay: "-2s" }} />
            <TopNav />

            <main className="relative z-10 mx-auto max-w-7xl px-container-padding-mobile pb-52 pt-36 md:px-container-padding-desktop md:pt-40">
                <GlassPanel className="mb-8 rounded-[28px] border border-white/10 px-5 py-5 md:px-8 md:py-7">
                    <div className="flex flex-col gap-6">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                            <div className="space-y-3">
                                <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-on-surface-variant/70">
                                    <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                                    Authenticated Workspace
                                </span>
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
                                <Link
                                    href="/command"
                                    className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-[12px] font-semibold text-primary transition-all hover:bg-primary/15"
                                >
                                    <MaterialIcon icon="auto_awesome" size={16} />
                                    Command Center
                                </Link>
                                <button
                                    type="button"
                                    onClick={handleLogout}
                                    disabled={signingOut}
                                    className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-[12px] font-semibold text-on-surface-variant transition-all hover:border-white/20 hover:text-on-surface disabled:opacity-50"
                                >
                                    <MaterialIcon icon="logout" size={16} />
                                    {signingOut ? "Signing out..." : "Sign out"}
                                </button>
                            </div>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            {APP_ROUTES.map((route) => {
                                const active = isActive(pathname, route.href);
                                return (
                                    <Link
                                        key={route.href}
                                        href={route.href}
                                        aria-current={active ? "page" : undefined}
                                        className={cn(
                                            "inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-[11px] uppercase tracking-[0.14em] transition-all",
                                            active
                                                ? "border-primary/35 bg-primary/12 text-on-surface shadow-[0_10px_30px_rgba(91,79,255,0.16)]"
                                                : "border-white/8 bg-white/[0.02] text-on-surface-variant/75 hover:border-white/16 hover:text-on-surface"
                                        )}
                                    >
                                        {route.icon ? <MaterialIcon icon={route.icon} size={15} /> : null}
                                        {route.label}
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                </GlassPanel>

                <div className="space-y-6">
                    {children}
                </div>
            </main>

            <Navigation />
        </div>
    );
}

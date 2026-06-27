"use client";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useLanguage } from "@/contexts/LanguageContext";
import { useSidebarStatus } from "@/hooks/useSidebarStatus";
import { buildWhatsAppManageUrl } from "@/lib/billing";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MaterialIcon } from "../ui/MaterialIcon";
import { mainNavSections, navMeta } from "./app-nav";

const NAV_SECTION_KEYS: Record<string, TranslationKey> = {
    "Search": "navSectionSearch",
    "Career": "navSectionCareer",
    "Account": "navSectionAccount",
};

const NAV_ITEM_KEYS: Record<string, TranslationKey> = {
    "/command": "navAskRico",
    "/flow": "navPipeline",
    "/queue": "applications",
    "/profile": "profileTitle",
    "/upload": "navMyCv",
    "/subscription": "navProPlan",
    "/settings": "settings",
};

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
    const { language } = useLanguage();
    const t = useTranslation(language);

    // onLogout is threaded through only for authenticated sessions (the command
    // page ties it to chatAudience==="authenticated"; AppShell pages are
    // protected). Gating on it avoids logged-out fetches and a duplicate /me
    // round-trip that calling useAuth() again would cost.
    const enabled = Boolean(onLogout);
    const status = useSidebarStatus(enabled);

    const emailPrefix = user?.email?.split("@")[0] ?? "";
    const displayName = user?.name ?? emailPrefix ?? "User";
    const initials = user?.name
        ? user.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()
        : emailPrefix
        ? emailPrefix.slice(0, 2).toUpperCase()
        : navMeta.brand.shortName;

    return (
        <TooltipProvider>
            <aside
                className={cn(
                    "hidden h-full w-64 flex-col border-e border-overlay/10 bg-surface backdrop-blur-none shadow-[inset_-1px_0_0_rgba(255,255,255,0.04)] md:flex",
                    className
                )}
            >
                {/* Brand Header */}
                <div className="flex items-center gap-3 px-5 py-5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gold text-sm font-black text-[#0a0a1a] shadow-[0_2px_10px_rgba(245,166,35,0.18)]">
                        {navMeta.brand.shortName}
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-semibold text-text-primary">
                            {navMeta.brand.name}
                        </span>
                        <span className="text-[10px] text-text-tertiary">
                            {t("navBrandTagline")}
                        </span>
                    </div>
                </div>

                <Separator />

                {/* Status Indicator */}
                <div className="flex items-center gap-2 px-5 py-3">
                    <span
                        className="h-2 w-2 rounded-full animate-pulse motion-reduce:animate-none"
                        style={{ backgroundColor: navMeta.status.color }}
                    />
                    <span
                        className="text-xs font-medium"
                        style={{ color: navMeta.status.color }}
                    >
                        {t("navStatusLive")} · {navMeta.status.region}
                    </span>
                </div>

                <Separator />

                {/* Career status modules — read-only; each hides silently on failure */}
                {enabled && (status.loading || status.readiness || status.pipeline || status.error) && (
                    <div className="space-y-3 px-3 pt-4">
                        {status.error ? (
                            <button
                                type="button"
                                onClick={status.refresh}
                                aria-label={t("navStatusRetry")}
                                className="flex w-full items-center justify-center gap-2 rounded-lg border border-overlay/10 bg-surface-subtle/40 p-3 text-[11px] font-medium text-text-tertiary transition-colors hover:border-gold/25 hover:bg-surface-subtle hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                            >
                                <MaterialIcon icon="refresh" size={14} className="opacity-70" />
                                <span>{t("navStatusRetry")}</span>
                            </button>
                        ) : (
                          <>
                        {status.loading && !status.readiness ? (
                            <div className="h-[70px] animate-pulse rounded-lg border border-overlay/10 bg-surface-subtle/40 motion-reduce:animate-none" />
                        ) : status.readiness ? (
                            <div>
                                <h3 className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                                    {t("navModuleReadiness")}
                                </h3>
                                <Link
                                    href="/profile"
                                    className="block rounded-lg border border-overlay/10 bg-surface-subtle/40 p-3 transition-colors hover:border-gold/25 hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs font-medium text-text-secondary">{t("navModuleProfile")}</span>
                                        {status.readiness.completeness != null && (
                                            <span className="text-xs font-semibold text-gold">
                                                {status.readiness.completeness}%
                                            </span>
                                        )}
                                    </div>
                                    {status.readiness.completeness != null && (
                                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-overlay/10">
                                            <div
                                                className="h-full rounded-full bg-gold transition-all"
                                                style={{ width: `${status.readiness.completeness}%` }}
                                            />
                                        </div>
                                    )}
                                    <p className="mt-2 text-[10px] text-text-tertiary">
                                        {status.readiness.targetRoles > 0
                                            ? `${status.readiness.targetRoles} target role${status.readiness.targetRoles === 1 ? "" : "s"} set`
                                            : t("navAddTargetRole")}
                                    </p>
                                </Link>
                            </div>
                        ) : null}

                        {status.loading && !status.pipeline ? (
                            <div className="h-[70px] animate-pulse rounded-lg border border-overlay/10 bg-surface-subtle/40 motion-reduce:animate-none" />
                        ) : status.pipeline ? (
                            <div>
                                <h3 className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                                    {t("navModulePipeline")}
                                </h3>
                                <Link
                                    href="/flow"
                                    className="block rounded-lg border border-overlay/10 bg-surface-subtle/40 p-3 transition-colors hover:border-gold/25 hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                                >
                                    <div className="flex items-baseline justify-between">
                                        <span className="text-xs font-medium text-text-secondary">{t("navModuleInPipeline")}</span>
                                        <span className="text-[10px] text-text-tertiary">
                                            {status.pipeline.total} {status.pipeline.total === 1 ? "job" : "jobs"}
                                        </span>
                                    </div>
                                    <div className="mt-2 grid grid-cols-3 gap-1 text-center">
                                        {([
                                            ["navApplied", status.pipeline.applied],
                                            ["navInterview", status.pipeline.interview],
                                            ["navOffer", status.pipeline.offer],
                                        ] as const).map(([key, n]) => (
                                            <div key={key} className="rounded-md bg-overlay/5 py-1.5">
                                                <div className="text-sm font-semibold text-text-primary">{n}</div>
                                                <div className="text-[9px] uppercase tracking-wide text-text-tertiary">
                                                    {t(key)}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </Link>
                            </div>
                        ) : null}
                          </>
                        )}
                    </div>
                )}

                {/* Main Navigation */}
                <nav className="flex-1 overflow-y-auto px-3 py-4">
                    {mainNavSections.map((section) => (
                        <div key={section.title} className="mb-6">
                            <h3 className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                                {NAV_SECTION_KEYS[section.title] ? t(NAV_SECTION_KEYS[section.title]) : section.title}
                            </h3>
                            <ul className="space-y-0.5">
                                {section.items.map((item) => {
                                    // href is the source of truth for navigation.
                                    // chatPrompt only prefills when already on /command — never overrides a real destination.
                                    const isOnCommand = pathname === "/command";
                                    const navHref = (item.chatPrompt && isOnCommand)
                                        ? `/command?q=${encodeURIComponent(item.chatPrompt)}`
                                        : item.href;
                                    const isActive = pathname === item.href;
                                    return (
                                        <li key={item.href}>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Link
                                                        href={navHref}
                                                        aria-current={isActive ? "page" : undefined}
                                                        className={cn(
                                                            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
                                                            isActive
                                                                ? "bg-gold/10 text-gold ring-1 ring-gold/20 shadow-[0_0_16px_rgba(245,166,35,0.12)]"
                                                                : "text-text-secondary hover:bg-surface-subtle hover:text-text-primary hover:ring-1 hover:ring-overlay/10"
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
                                                        <span className="flex-1">{NAV_ITEM_KEYS[item.href] ? t(NAV_ITEM_KEYS[item.href]) : item.label}</span>
                                                        {item.href === "/subscription" && status.plan ? (
                                                            <span
                                                                className={cn(
                                                                    "rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                                                                    status.plan.plan === "free"
                                                                        ? "bg-overlay/10 text-text-tertiary"
                                                                        : "bg-gold/15 text-gold"
                                                                )}
                                                            >
                                                                {status.plan.plan}
                                                            </span>
                                                        ) : item.href === "/queue" && status.queueCount > 0 ? (
                                                            <span className="rounded-full bg-gold px-1.5 py-0.5 text-[9px] font-bold text-[#0a0a1a]">
                                                                {status.queueCount}
                                                            </span>
                                                        ) : item.badge ? (
                                                            <Badge variant={isActive ? "default" : "secondary"}>
                                                                {item.badge}
                                                            </Badge>
                                                        ) : null}
                                                    </Link>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {NAV_ITEM_KEYS[item.href] ? t(NAV_ITEM_KEYS[item.href]) : item.label}
                                                </TooltipContent>
                                            </Tooltip>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    ))}

                </nav>

                {/* Quick support — reuses existing WhatsApp helper, no extra data */}
                {enabled && (
                    <div className="px-3 pb-1">
                        <a
                            href={buildWhatsAppManageUrl()}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-subtle hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                        >
                            <MaterialIcon icon="chat" size={18} className="flex-shrink-0 opacity-60" />
                            <span>{t("navSupportWhatsapp")}</span>
                        </a>
                    </div>
                )}

                <Separator />

                {/* User Footer */}
                <div className="p-4">
                    <button
                        onClick={onLogout}
                        aria-label={onLogout ? t("logout") : undefined}
                        className="flex w-full items-center gap-3 rounded-lg p-2 transition-colors hover:bg-surface-subtle group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                    >
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gold text-xs font-bold text-[#0a0a1a]">
                            {initials}
                        </div>
                        <div className="flex-1 min-w-0 text-start">
                            <p className="text-sm font-medium text-text-primary truncate">
                                {displayName}
                            </p>
                            <p className="truncate text-xs text-text-tertiary">
                                {user?.email ?? ""}
                            </p>
                        </div>
                        <MaterialIcon
                            icon="logout"
                            size={16}
                            className="text-text-tertiary opacity-0 transition-opacity group-hover:opacity-100"
                        />
                    </button>
                </div>
            </aside>
        </TooltipProvider>
    );
}

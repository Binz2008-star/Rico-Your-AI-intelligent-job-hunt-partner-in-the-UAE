"use client";

/**
 * WorkspaceShell — "Shell C", the authenticated workspace chrome from the
 * approved /design-preview reference (DEC-20260710-002 + DEC-20260712-001:
 * owner adopted the reference left-sidebar for the workspace).
 *
 * Single approved shell on the authenticated workspace routes (2026-07-18
 * single-shell ruling). The visual language is the owner-supplied Command
 * Workspace artifact (applied 2026-07-21, superseding the earlier v5
 * rebuild): sun "R" badge brand, paper-lift active rail rows with a solid
 * sun marker, sun-tint count pill, per-route mode accents fed to the
 * `--wsx5-mode*` custom properties, drifting accent ambience in BOTH
 * themes, document-content entrance, and the Rico presence indicator.
 * Behavior (nav source of truth, language, drawer, mission summary,
 * app/document variants) is unchanged.
 *
 * Self-contained light-first Atelier "island": everything is scoped under
 * `.wsx-root` (+ the `.wsx5` token island), uses the shared atelier-kit and
 * v5 tokens, and applies a LOCAL light/dark theme. Like AtelierAuthShell it
 * deliberately does NOT read/write the global ThemeContext, so the dark
 * Nocturne app default is never disturbed. Language comes from the global
 * useLanguage(); dir/lang mirror onto the root.
 */

import { atelierFraunces, atelierNaskhArabic, atelierSansArabic } from "@/components/atelier-kit/fonts";
import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { RailGoalMini } from "@/components/workspace/RailGoalMini";
import { WORKSPACE_THEME, WorkspaceThemeContext, readStoredWorkspaceDark, writeStoredWorkspaceDark } from "@/components/workspace/theme";
import { v5Amiri, v5Inter, v5PlexArabic, v5PlexMono } from "@/components/workspace/v5/fonts";
import "@/components/workspace/v5/motion.css";
import { RicoPresence } from "@/components/workspace/v5/RicoPresence";
import { V5_FONT, V5_MODE_ACCENTS, type V5ModeKey } from "@/components/workspace/v5/tokens";
import { useLanguage } from "@/contexts/LanguageContext";
import { useMissionSummary } from "@/hooks/useMissionSummary";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export type NavItem = { key: string; href: string; label: { en: string; ar: string }; icon: React.ReactNode };

/* 1.6px stroked line icons (reference style). */
const ic = (paths: React.ReactNode) => (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {paths}
    </svg>
);

/* Exported for CommandObsidianShell (/command-only chrome) so both shells
   share one nav source of truth. */
export const WORKSPACE_NAV: NavItem[] = [
    { key: "command", href: "/command", label: { en: "Command", ar: "الأوامر" }, icon: ic(<><path d="M4 5h16M4 12h10M4 19h16" /></>) },
    { key: "profile", href: "/profile", label: { en: "Profile", ar: "الملف" }, icon: ic(<><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></>) },
    { key: "applications", href: "/applications", label: { en: "Applications", ar: "الطلبات" }, icon: ic(<><path d="M4 4h16v5H4zM4 10h16v5H4zM4 16h16v4H4z" /></>) },
    { key: "upload", href: "/upload", label: { en: "Upload CV", ar: "رفع السيرة" }, icon: ic(<><path d="M12 15V4M8 8l4-4 4 4M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" /></>) },
    { key: "subscription", href: "/subscription", label: { en: "Subscription", ar: "الاشتراك" }, icon: ic(<><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20M6 15h4" /></>) },
    { key: "settings", href: "/settings", label: { en: "Settings", ar: "الإعدادات" }, icon: ic(<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></>) },
];

/* v5 per-route accents (AI_WORKSPACE/COMMAND_V5_IMPLEMENTATION_MAP.md):
   live v5 modes map to their accent triple; every other workspace route
   shares the neutral overview terra. Light theme only — the dark island
   keeps its existing accent language untouched. */
const ROUTE_V5_MODE: Record<string, V5ModeKey> = {
    "/dashboard": "overview",
    "/command": "search",
    "/applications": "applications",
    "/upload": "documents",
};
function v5ModeForPath(path: string): V5ModeKey {
    for (const [prefix, mode] of Object.entries(ROUTE_V5_MODE)) {
        if (path === prefix || path.startsWith(prefix + "/")) return mode;
    }
    return "overview";
}

export function WorkspaceShell({
    children,
    variant = "document",
    defaultDark = false,
    mobileChrome = false,
    mobileExtras,
}: {
    children: React.ReactNode;
    /**
     * "document" (default) — scrolling page content with padding and max-width,
     * plus the shell's own mobile top bar/drawer. Byte-identical behavior for
     * the routes shipped before this prop existed.
     * "app" — full-height application surface (e.g. /command): the main region
     * becomes a full-bleed flex column that manages its own scrolling. By
     * default the shell renders no mobile chrome (the child owns its mobile
     * header/dock); pass `mobileChrome` to give the app surface the SAME shell
     * mobile top bar + drawer as every document route — one navigation owner,
     * no per-route legacy header/dock (2026-07-18 single-shell defect).
     */
    variant?: "document" | "app";
    /** Start the local light/dark island in dark (e.g. the chat surface). */
    defaultDark?: boolean;
    /** App variant only: render the shell's own mobile top bar + drawer. */
    mobileChrome?: boolean;
    /** Extra route-specific actions rendered at the end of the mobile drawer
     *  (e.g. /command's New chat / Clear chat / Log out). */
    mobileExtras?: React.ReactNode;
}) {
    const { language, setLanguage } = useLanguage();
    const pathname = usePathname();
    const isAr = language === "ar";
    const isApp = variant === "app";
    const showMobileChrome = !isApp || mobileChrome;
    // `defaultDark` (SSR-safe, per-route) is only the FIRST-EVER value.
    // The effect below applies the user's own stored choice, if any, right
    // after mount — so an explicit toggle survives switching tabs/pages or a
    // full reload instead of reverting to this route's default every time.
    const [dark, setDark] = useState(defaultDark);
    useEffect(() => {
        const stored = readStoredWorkspaceDark();
        if (stored !== null && stored !== dark) setDark(stored);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const [open, setOpen] = useState(false);
    const c = dark ? WORKSPACE_THEME.dark : WORKSPACE_THEME.light;
    const SERIF = ATELIER_FONT.serif;

    // Mission summary for the rail goal-mini + applications nav count
    // (PR-V4-2a; single cached fetch, fail-hidden). Document routes only —
    // the app variant (/command, public-capable) never fetches; /dashboard
    // is skipped because its goal panel already renders the same data.
    const missionSummary = useMissionSummary(!isApp && pathname !== "/dashboard");
    const applicationsCount = missionSummary?.applications_sent ?? 0;

    const routeAcc = V5_MODE_ACCENTS[v5ModeForPath(pathname)];

    /* Artifact brand: sun "R" badge + plain display wordmark (both themes). */
    const Brand = (
        <Link href="/dashboard" className="flex items-center gap-2" style={{ textDecoration: "none" }}>
            <span
                aria-hidden="true"
                style={{
                    width: 26,
                    height: 26,
                    borderRadius: 999,
                    background: c.red,
                    color: "#fff",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: SERIF,
                    fontSize: 12,
                    fontWeight: 600,
                    flexShrink: 0,
                }}
            >
                R
            </span>
            <span style={{ fontFamily: SERIF, fontSize: "1.05rem", fontWeight: 500, letterSpacing: "-0.01em", lineHeight: 1, color: c.ink }}>
                Rico
            </span>
            <Mono style={{ color: c.ink40, letterSpacing: "0.18em" }}>{isAr ? "مساحة العمل" : "Workspace"}</Mono>
        </Link>
    );

    /* Artifact rail rows: active row lifts to paper with a solid sun start
       marker and sun icon; the count rides in a sun-tint pill (both themes —
       the artifact uses the sun accent in the rail for every mode). */
    const NavList = (
        <nav className="flex flex-col gap-1">
            {WORKSPACE_NAV.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                    <Link
                        key={item.key}
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className="wsx-nav flex items-center gap-3 rounded-[8px] px-3 py-2.5"
                        style={{
                            position: "relative",
                            color: active ? c.ink : c.ink70,
                            background: active ? c.bg : "transparent",
                            textDecoration: "none",
                        }}
                        aria-current={active ? "page" : undefined}
                    >
                        {active && (
                            <span
                                aria-hidden="true"
                                data-testid="wsx5-nav-marker"
                                style={{
                                    position: "absolute",
                                    insetInlineStart: -1,
                                    top: 8,
                                    bottom: 8,
                                    width: 2,
                                    borderRadius: 2,
                                    background: c.red,
                                }}
                            />
                        )}
                        <span
                            style={{
                                color: active ? c.red : c.ink40,
                                display: "inline-flex",
                                animation: active ? "wsx5-pop-in 480ms var(--wsx5-spring)" : undefined,
                            }}
                        >
                            {item.icon}
                        </span>
                        <span style={{ fontSize: 13.5, fontFamily: V5_FONT.sans, fontWeight: active ? 600 : 450 }}>
                            {isAr ? item.label.ar : item.label.en}
                        </span>
                        {item.key === "applications" && applicationsCount > 0 && (
                            <span
                                dir="ltr"
                                data-testid="nav-applications-count"
                                className="ms-auto"
                                style={{
                                    fontFamily: ATELIER_FONT.mono,
                                    fontSize: 10,
                                    ...(active
                                        ? {
                                            color: c.red,
                                            background: `${c.red}1F`,
                                            padding: "1px 7px",
                                            borderRadius: 999,
                                        }
                                        : { color: c.ink40 }),
                                }}
                            >
                                {applicationsCount}
                            </span>
                        )}
                    </Link>
                );
            })}
        </nav>
    );

    const Controls = (
        <div className="flex items-center gap-2">
            <RicoPresence state="ready" size="sm" label={isAr ? "ريكو جاهز" : "Rico is ready"} />
            <span className="flex-1" aria-hidden="true" />
            <span className="wsx-lang-toggle flex gap-[3px]">
                <button
                    type="button"
                    onClick={() => setLanguage("en")}
                    aria-pressed={!isAr}
                    className="wsx-lang-btn rounded-[6px] border"
                    style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10.5, fontWeight: 500, padding: "5px 11px", borderColor: c.hair, background: !isAr ? c.ink : c.bg, color: !isAr ? c.bg : c.ink55, cursor: "pointer" }}
                >EN</button>
                <button
                    type="button"
                    onClick={() => setLanguage("ar")}
                    aria-pressed={isAr}
                    className="wsx-lang-btn rounded-[6px] border"
                    style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10.5, fontWeight: 500, padding: "5px 11px", borderColor: c.hair, background: isAr ? c.ink : c.bg, color: isAr ? c.bg : c.ink55, cursor: "pointer" }}
                >عربي</button>
            </span>
            <button
                type="button"
                onClick={() => setDark((v) => {
                    const next = !v;
                    writeStoredWorkspaceDark(next);
                    return next;
                })}
                aria-pressed={dark}
                aria-label={dark ? (isAr ? "الوضع الفاتح" : "Light mode") : (isAr ? "الوضع الداكن" : "Dark mode")}
                className="inline-flex items-center justify-center rounded-[6px]"
                style={{ width: 30, height: 26, border: `1px solid ${c.hair}`, color: c.ink70, cursor: "pointer", background: "transparent" }}
            >
                {dark ? (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
                ) : (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
                )}
            </button>
        </div>
    );

    return (
        <div
            className={`wsx-root wsx5 ${isAr ? "wsx-ar" : ""} ${isApp ? "h-[100dvh] overflow-hidden" : "min-h-screen"} ${atelierFraunces.variable} ${atelierNaskhArabic.variable} ${atelierSansArabic.variable} ${v5Inter.variable} ${v5PlexMono.variable} ${v5Amiri.variable} ${v5PlexArabic.variable}`}
            dir={isAr ? "rtl" : "ltr"}
            lang={language}
            style={
                {
                    background: c.bg,
                    color: c.ink,
                    fontFamily: ATELIER_FONT.body,
                    /* per-route mode accents feed the artifact's animated
                       display-word gradient and micro ticks */
                    "--wsx5-modeA": routeAcc.modeA,
                    "--wsx5-modeB": routeAcc.modeB,
                    "--wsx5-modeAText": routeAcc.modeAText,
                } as React.CSSProperties
            }
        >
            <style dangerouslySetInnerHTML={{
                __html: `
                .wsx-root .wsx-nav { transition: background-color .15s ease, color .15s ease; }
                .wsx-root .wsx-nav:hover { background-color: ${c.activeBg}; color: ${c.ink}; }
                .wsx-root .wsx-action { transition: border-color .15s ease, transform .15s ease; }
                .wsx-root .wsx-action:hover { border-color: ${c.red} !important; }
                .wsx-root a:focus-visible, .wsx-root button:focus-visible { outline: 2px solid ${c.red}; outline-offset: 2px; border-radius: 4px; }
                .wsx-root.wsx-ar * { letter-spacing: 0 !important; }
                .wsx-lang-toggle .wsx-lang-btn { transition: border-color .2s cubic-bezier(.4,0,.2,1), color .2s cubic-bezier(.4,0,.2,1), background-color .2s cubic-bezier(.4,0,.2,1); }
                .wsx-lang-toggle .wsx-lang-btn:hover:not([aria-pressed="true"]) { border-color: ${c.red}; color: ${c.red}; }
            ` }} />
            {/* Artifact route ambience — accent-tinted radials with a slow
                drift, both themes; decorative, zero pointer impact. */}
            <div
                aria-hidden="true"
                data-testid="wsx5-atmosphere"
                style={{
                    position: "fixed",
                    inset: "-12%",
                    pointerEvents: "none",
                    zIndex: 0,
                    background: `radial-gradient(42% 44% at 15% 18%, ${routeAcc.modeA}21, transparent 60%), radial-gradient(48% 50% at 86% 82%, ${routeAcc.modeB}24, transparent 62%), radial-gradient(40% 42% at 72% 10%, ${routeAcc.modeA}18, transparent 60%)`,
                    animation: "wsx5-ambient 20s ease-in-out infinite",
                }}
            />
            <div
                className={`lg:grid ${isApp ? "h-full flex flex-col" : ""}`}
                style={{ gridTemplateColumns: "244px 1fr", position: "relative", zIndex: 1 }}
            >
                {/* ── Desktop sidebar ── */}
                <aside
                    className="hidden lg:flex flex-col justify-between sticky top-0 h-screen px-5 py-6"
                    style={{ background: c.rail, borderInlineEnd: `1px solid ${c.hair}` }}
                >
                    <div className="flex flex-col gap-8">
                        <div className="pb-5" style={{ borderBottom: `1px solid ${c.hair}` }}>{Brand}</div>
                        <RailGoalMini mission={missionSummary} language={language} c={c} />
                        {NavList}
                    </div>
                    {Controls}
                </aside>

                {/* ── Mobile top bar (document routes, and app routes that opt in) ── */}
                {showMobileChrome && (
                    <div data-testid="wsx-mobile-bar" className="lg:hidden sticky top-0 z-20 flex shrink-0 items-center justify-between px-5 py-4" style={{ background: c.rail, borderBottom: `1px solid ${c.hair}` }}>
                        {Brand}
                        <button type="button" aria-label="Menu" aria-expanded={open} onClick={() => setOpen((v) => !v)} className="p-1" style={{ color: c.ink70, background: "transparent", cursor: "pointer" }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} className="w-6 h-6" aria-hidden="true">
                                {open ? <path strokeLinecap="round" d="M6 18L18 6M6 6l12 12" /> : <path strokeLinecap="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />}
                            </svg>
                        </button>
                    </div>
                )}
                {showMobileChrome && open && (
                    <div className="lg:hidden px-5 py-4 flex shrink-0 flex-col gap-4" style={{ background: c.rail, borderBottom: `1px solid ${c.hair}` }}>
                        <RailGoalMini mission={missionSummary} language={language} c={c} onNavigate={() => setOpen(false)} />
                        {NavList}
                        {Controls}
                        {mobileExtras}
                    </div>
                )}

                {/* ── Main content ── */}
                <main className={isApp ? "flex flex-1 lg:h-full min-h-0 w-full flex-col overflow-hidden" : "px-5 sm:px-8 lg:px-12 py-8 lg:py-12 max-w-5xl w-full"}>
                    <WorkspaceThemeContext.Provider value={c}>
                        {isApp ? (
                            children
                        ) : (
                            /* v5 entrance: document content rises in once per
                               navigation; collapses under reduced motion. */
                            <div className="wsx5-play">
                                <div data-wsx5-anim="rise">{children}</div>
                            </div>
                        )}
                    </WorkspaceThemeContext.Provider>
                </main>
            </div>
        </div>
    );
}

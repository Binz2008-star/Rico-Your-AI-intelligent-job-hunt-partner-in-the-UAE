"use client";

/**
 * WorkspaceShell — "Shell C", the authenticated workspace chrome from the
 * approved /design-preview reference (DEC-20260710-002 + DEC-20260712-001:
 * owner adopted the reference left-sidebar for the workspace).
 *
 * PR 5A wires this shell to /dashboard only. Other workspace routes
 * (/profile, /settings, /applications, /upload, /subscription) keep their
 * current shell until their own follow-up PRs — this component just links to
 * them.
 *
 * Self-contained light-first Atelier "island": everything is scoped under
 * `.wsx-root`, uses the shared atelier-kit tokens, and applies a LOCAL
 * light/dark theme (default light, matching the reference). Like
 * AtelierAuthShell it deliberately does NOT read/write the global
 * ThemeContext, so the dark Nocturne app default is never disturbed.
 * Language comes from the global useLanguage(); dir/lang mirror onto the root.
 *
 * /command is out of scope for any redesign — the sidebar only *links* to it.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { atelierFraunces } from "@/components/atelier-kit/fonts";
import { Mono } from "@/components/atelier-kit/primitives";
import { WORKSPACE_THEME, WorkspaceThemeContext } from "@/components/workspace/theme";

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
    { key: "settings", href: "/settings", label: { en: "Settings", ar: "الإعدادات" }, icon: ic(<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></>) },
];

export function WorkspaceShell({
    children,
    variant = "document",
    defaultDark = false,
}: {
    children: React.ReactNode;
    /**
     * "document" (default) — scrolling page content with padding and max-width,
     * plus the shell's own mobile top bar/drawer. Byte-identical behavior for
     * the routes shipped before this prop existed.
     * "app" — full-height application surface (e.g. /command): the main region
     * becomes a full-bleed flex column that manages its own scrolling, and the
     * shell renders no mobile chrome (the child owns its mobile header/dock).
     */
    variant?: "document" | "app";
    /** Start the local light/dark island in dark (e.g. the chat surface). */
    defaultDark?: boolean;
}) {
    const { language, setLanguage } = useLanguage();
    const pathname = usePathname();
    const isAr = language === "ar";
    const isApp = variant === "app";
    const [dark, setDark] = useState(defaultDark);
    const [open, setOpen] = useState(false);
    const c = dark ? WORKSPACE_THEME.dark : WORKSPACE_THEME.light;
    const SERIF = ATELIER_FONT.serif;

    const Brand = (
        <Link href="/dashboard" className="flex items-baseline gap-2" style={{ textDecoration: "none" }}>
            <span style={{ fontFamily: SERIF, fontSize: "1.35rem", color: c.ink, lineHeight: 1 }}>Rico</span>
            <Mono style={{ color: c.ink40, letterSpacing: "0.18em" }}>{isAr ? "مساحة العمل" : "Workspace"}</Mono>
        </Link>
    );

    const NavList = (
        <nav className="flex flex-col gap-1">
            {WORKSPACE_NAV.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                    <Link
                        key={item.key}
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className="wsx-nav flex items-center gap-3 rounded-[7px] px-3 py-2.5"
                        style={{
                            color: active ? c.ink : c.ink70,
                            background: active ? c.activeBg : "transparent",
                            textDecoration: "none",
                        }}
                        aria-current={active ? "page" : undefined}
                    >
                        <span style={{ color: active ? c.red : c.ink40, display: "inline-flex" }}>{item.icon}</span>
                        <span style={{ fontSize: 14 }}>{isAr ? item.label.ar : item.label.en}</span>
                    </Link>
                );
            })}
        </nav>
    );

    const Controls = (
        <div className="flex items-center gap-2">
            <span className="inline-flex items-center rounded-[3px] overflow-hidden" style={{ border: `1px solid ${c.hair}` }}>
                <button type="button" onClick={() => setLanguage("en")} aria-pressed={!isAr} style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10, padding: "3px 7px", background: !isAr ? c.ink : "transparent", color: !isAr ? c.bg : c.ink40, cursor: "pointer" }}>EN</button>
                <button type="button" onClick={() => setLanguage("ar")} aria-pressed={isAr} style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10, padding: "3px 7px", background: isAr ? c.ink : "transparent", color: isAr ? c.bg : c.ink40, cursor: "pointer" }}>عربي</button>
            </span>
            <button
                type="button"
                onClick={() => setDark((v) => !v)}
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
            className={`wsx-root ${isAr ? "wsx-ar" : ""} ${isApp ? "h-[100dvh] overflow-hidden" : "min-h-screen"} ${atelierFraunces.variable}`}
            dir={isAr ? "rtl" : "ltr"}
            lang={language}
            style={{ background: c.bg, color: c.ink, fontFamily: ATELIER_FONT.body }}
        >
            <style dangerouslySetInnerHTML={{ __html: `
                .wsx-root .wsx-nav { transition: background-color .15s ease, color .15s ease; }
                .wsx-root .wsx-nav:hover { background-color: ${c.activeBg}; color: ${c.ink}; }
                .wsx-root .wsx-action { transition: border-color .15s ease, transform .15s ease; }
                .wsx-root .wsx-action:hover { border-color: ${c.red} !important; }
                .wsx-root a:focus-visible, .wsx-root button:focus-visible { outline: 2px solid ${c.red}; outline-offset: 2px; border-radius: 4px; }
                .wsx-root.wsx-ar * { letter-spacing: 0 !important; }
            ` }} />
            <div className={`lg:grid ${isApp ? "h-full" : ""}`} style={{ gridTemplateColumns: "244px 1fr" }}>
                {/* ── Desktop sidebar ── */}
                <aside
                    className="hidden lg:flex flex-col justify-between sticky top-0 h-screen px-5 py-6"
                    style={{ background: c.rail, borderInlineEnd: `1px solid ${c.hair}` }}
                >
                    <div className="flex flex-col gap-8">
                        <div className="pb-5" style={{ borderBottom: `1px solid ${c.hair}` }}>{Brand}</div>
                        {NavList}
                    </div>
                    {Controls}
                </aside>

                {/* ── Mobile top bar (document variant only — app children own their mobile chrome) ── */}
                {!isApp && (
                    <div className="lg:hidden sticky top-0 z-20 flex items-center justify-between px-5 py-4" style={{ background: c.rail, borderBottom: `1px solid ${c.hair}` }}>
                        {Brand}
                        <button type="button" aria-label="Menu" aria-expanded={open} onClick={() => setOpen((v) => !v)} className="p-1" style={{ color: c.ink70, background: "transparent", cursor: "pointer" }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} className="w-6 h-6" aria-hidden="true">
                                {open ? <path strokeLinecap="round" d="M6 18L18 6M6 6l12 12" /> : <path strokeLinecap="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />}
                            </svg>
                        </button>
                    </div>
                )}
                {!isApp && open && (
                    <div className="lg:hidden px-5 py-4 flex flex-col gap-4" style={{ background: c.rail, borderBottom: `1px solid ${c.hair}` }}>
                        {NavList}
                        {Controls}
                    </div>
                )}

                {/* ── Main content ── */}
                <main className={isApp ? "flex h-full min-h-0 w-full flex-col overflow-hidden" : "px-5 sm:px-8 lg:px-12 py-8 lg:py-12 max-w-5xl w-full"}>
                    <WorkspaceThemeContext.Provider value={c}>
                        {children}
                    </WorkspaceThemeContext.Provider>
                </main>
            </div>
        </div>
    );
}

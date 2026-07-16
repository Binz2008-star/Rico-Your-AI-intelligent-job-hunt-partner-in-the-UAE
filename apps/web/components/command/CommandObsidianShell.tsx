"use client";

/**
 * CommandObsidianShell — slice C1 of the Command Obsidian program
 * (owner directive 2026-07-16; canonical source:
 * `design-handoffs/reviewed/2026-07-16-command-obsidian-v4/`).
 *
 * Route-scoped chrome for the AUTHENTICATED `/command` surface only, replacing
 * WorkspaceShell there: the recording's dark operator console — obsidian
 * canvas with grid grain + acid-lime aura, a full-width h-12 top status bar
 * (panel toggles · Rico · workspace eyebrow · compact icon nav · live status ·
 * EN/ع · theme), a collapsible 260px start rail carrying the `leftRail`
 * content (the canonical Sessions position — CommandConversationRail; general
 * app navigation deliberately does NOT occupy it, per the owner's 2026-07-16
 * correction), and a flexible console area whose children (transcript column
 * + CommandRail) come from CommandPage unchanged.
 *
 * Theme delivery: provides COMMAND_OBSIDIAN through the existing
 * WorkspaceThemeContext, so every merged 4a–4e surface (composer, message
 * rows, state cards, right rail, MissionContextBar) repaints with zero
 * component changes. Local light/dark island, dark ("Obsidian night") first —
 * the global Nocturne ThemeContext is never touched, and no global
 * `:root`/`body` styling is added (the prototype's body::before/::after
 * texture is re-implemented here as scoped, pointer-events-none layers).
 *
 * Desktop (lg+) chrome only, matching the surface it replaces: below lg the
 * page keeps MobileCommandHeader + MobileBottomNav exactly as before (they
 * still render at all widths for chat behavior parity — this shell's bars are
 * hidden below lg). Mobile drawer parity is slice C6.
 *
 * ZERO chat-behavior change: no handler, message, streaming, attachment,
 * safety, or API code lives here.
 */

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { COMMAND_OBSIDIAN } from "@/components/command/obsidianTheme";
import { WORKSPACE_NAV } from "@/components/workspace/WorkspaceShell";
import { WorkspaceThemeContext } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const EYEBROW: React.CSSProperties = {
    fontFamily: ATELIER_FONT.mono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.22em",
};

/* Canonical top-bar panel glyphs (PanelLeft / PanelRight, 1.6px strokes). */
function PanelIcon({ side }: { side: "start" | "end" }) {
    return (
        <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className="rtl:-scale-x-100"
        >
            <rect x="3" y="4" width="18" height="16" rx="2" />
            {side === "start" ? <path d="M9 4v16" /> : <path d="M15 4v16" />}
        </svg>
    );
}

export function CommandObsidianShell({
    children,
    leftRail,
    busy = false,
    leftOpen = true,
    rightOpen = true,
    onToggleLeft,
    onToggleRight,
    onLogout,
}: {
    children: React.ReactNode;
    /** Content of the start rail — the canonical Sessions position. */
    leftRail?: React.ReactNode;
    /** True while Rico is thinking/streaming — drives the top-bar status. */
    busy?: boolean;
    leftOpen?: boolean;
    rightOpen?: boolean;
    onToggleLeft?: () => void;
    onToggleRight?: () => void;
    /** Called when the user clicks Log out in the desktop account menu. */
    onLogout?: () => void;
}) {
    const { language, setLanguage } = useLanguage();
    const t = useTranslation(language);
    const pathname = usePathname();
    const isAr = language === "ar";
    const [dark, setDark] = useState(true); // "Obsidian night" default
    const c = dark ? COMMAND_OBSIDIAN.dark : COMMAND_OBSIDIAN.light;

    const [accountOpen, setAccountOpen] = useState(false);
    const accountRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        if (!accountOpen) return;
        function handle(e: MouseEvent) {
            if (accountRef.current && !accountRef.current.contains(e.target as Node)) {
                setAccountOpen(false);
            }
        }
        document.addEventListener("mousedown", handle);
        return () => document.removeEventListener("mousedown", handle);
    }, [accountOpen]);

    return (
        <div
            data-testid="command-obsidian-shell"
            data-obsidian-mode={dark ? "dark" : "light"}
            dir={isAr ? "rtl" : "ltr"}
            lang={language}
            className="relative flex h-[100dvh] min-h-0 flex-col overflow-hidden"
            style={{ background: c.bg, color: c.ink, fontFamily: ATELIER_FONT.body, colorScheme: dark ? "dark" : "light" }}
        >
            {/* ── Scoped canvas layers (canonical body::before/::after, route-local) ── */}
            <div
                aria-hidden="true"
                className="pointer-events-none absolute inset-0 z-0"
                style={{
                    opacity: 0.05,
                    backgroundImage: `linear-gradient(to right, ${c.ink55} 1px, transparent 1px), linear-gradient(to bottom, ${c.ink55} 1px, transparent 1px)`,
                    backgroundSize: "64px 64px",
                    maskImage: "radial-gradient(ellipse at 50% 30%, black 30%, transparent 75%)",
                    WebkitMaskImage: "radial-gradient(ellipse at 50% 30%, black 30%, transparent 75%)",
                }}
            />
            <div
                aria-hidden="true"
                className="pointer-events-none absolute left-1/2 z-0 -translate-x-1/2"
                style={{
                    top: "-20vh",
                    width: "90vw",
                    height: "60vh",
                    opacity: dark ? 0.2 : 0.08,
                    background: `radial-gradient(ellipse at center, ${c.red} 0%, transparent 60%)`,
                    filter: "blur(60px)",
                }}
            />

            {/* ── Top status bar (lg+; mobile keeps MobileCommandHeader) ── */}
            <header
                data-testid="command-obsidian-topbar"
                className="relative z-20 hidden h-12 shrink-0 items-center gap-3 px-4 backdrop-blur md:px-6 lg:flex"
                style={{ background: `${c.bg}D9`, borderBottom: `1px solid ${c.hair}` }}
            >
                <button
                    type="button"
                    onClick={onToggleLeft}
                    aria-label={t("cmdToggleNavRail")}
                    aria-expanded={leftOpen}
                    className="obs-ghost rounded-md p-1.5"
                    style={{ color: leftOpen ? c.ink : c.ink55, background: "transparent", border: "none", cursor: "pointer" }}
                >
                    <PanelIcon side="start" />
                </button>
                <Link
                    href="/dashboard"
                    className="text-[15px] leading-none tracking-tight"
                    style={{ color: c.ink, fontFamily: ATELIER_FONT.serif, textDecoration: "none" }}
                >
                    Rico
                </Link>
                <span className="hidden sm:inline" style={{ ...EYEBROW, color: c.ink55, letterSpacing: isAr ? "0.04em" : "0.22em" }}>
                    {t("cmdWorkspaceTag")}
                </span>
                {/* Compact icon nav — general app navigation relocated out of the
                    Sessions rail position (owner correction 2026-07-16). */}
                <nav aria-label={t("cmdNavRailTitle")} className="ms-3 flex items-center gap-0.5" data-testid="command-obsidian-topnav">
                    {WORKSPACE_NAV.map((item) => {
                        const active = pathname === item.href || pathname.startsWith(item.href + "/");
                        const label = isAr ? item.label.ar : item.label.en;
                        return (
                            <Link
                                key={item.key}
                                href={item.href}
                                aria-label={label}
                                title={label}
                                aria-current={active ? "page" : undefined}
                                className="obs-ghost inline-flex items-center justify-center rounded-md p-1.5"
                                style={{ color: active ? c.red : c.ink55 }}
                            >
                                {item.icon}
                            </Link>
                        );
                    })}
                </nav>
                <span
                    data-testid="command-obsidian-status"
                    className="ms-auto flex items-center gap-2"
                    style={{ ...EYEBROW, color: c.ink55, letterSpacing: isAr ? "0.04em" : "0.22em" }}
                >
                    <span
                        aria-hidden="true"
                        className={`h-1.5 w-1.5 rounded-full ${busy ? "animate-pulse" : ""}`}
                        style={{ background: busy ? c.red : c.track }}
                    />
                    {busy ? t("cmdStatusWorking") : t("cmdStatusReady")}
                </span>
                <span className="ms-2 inline-flex items-center overflow-hidden rounded-[3px]" style={{ border: `1px solid ${c.hair}` }}>
                    <button
                        type="button"
                        onClick={() => setLanguage("en")}
                        aria-pressed={!isAr}
                        style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10, padding: "3px 7px", background: !isAr ? c.ink : "transparent", color: !isAr ? c.bg : c.ink55, border: "none", cursor: "pointer" }}
                    >
                        EN
                    </button>
                    <button
                        type="button"
                        onClick={() => setLanguage("ar")}
                        aria-pressed={isAr}
                        style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10, padding: "3px 7px", background: isAr ? c.ink : "transparent", color: isAr ? c.bg : c.ink55, border: "none", cursor: "pointer" }}
                    >
                        عربي
                    </button>
                </span>
                <button
                    type="button"
                    onClick={() => setDark((v) => !v)}
                    aria-pressed={dark}
                    aria-label={dark ? (isAr ? "الوضع الفاتح" : "Light mode") : (isAr ? "الوضع الداكن" : "Dark mode")}
                    className="obs-ghost inline-flex items-center justify-center rounded-md"
                    style={{ width: 28, height: 24, border: `1px solid ${c.hair}`, color: c.ink70, background: "transparent", cursor: "pointer" }}
                >
                    {dark ? (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
                    ) : (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
                    )}
                </button>
                {/* Compact account menu — desktop logout control (hotfix for
                    authenticated desktop having no Logout after CommandObsidianShell
                    replaced WorkspaceShell chrome). Reuses the existing handleLogout
                    passed via onLogout; no duplicated auth/token-clearing logic. */}
                {onLogout && (
                    <div className="relative ms-2" ref={accountRef} data-testid="command-obsidian-account">
                        <button
                            type="button"
                            onClick={() => setAccountOpen((v) => !v)}
                            aria-label={isAr ? "الحساب" : "Account"}
                            aria-expanded={accountOpen}
                            aria-haspopup="menu"
                            className="obs-ghost inline-flex items-center justify-center rounded-md"
                            style={{ width: 28, height: 24, border: `1px solid ${c.hair}`, color: c.ink70, background: "transparent", cursor: "pointer" }}
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <circle cx="12" cy="8" r="4" />
                                <path d="M4 20a8 8 0 0 1 16 0" />
                            </svg>
                        </button>
                        {accountOpen && (
                            <div
                                role="menu"
                                className="absolute end-0 top-[calc(100%+4px)] z-50 w-44 rounded-lg py-1"
                                style={{ background: c.panel, border: `1px solid ${c.hair}`, boxShadow: "0 8px 24px rgba(0,0,0,0.35)" }}
                                data-testid="command-obsidian-account-menu"
                            >
                                <Link
                                    href="/profile"
                                    role="menuitem"
                                    onClick={() => setAccountOpen(false)}
                                    className="obs-ghost flex w-full items-center gap-2.5 px-3 py-2 text-[12px]"
                                    style={{ color: c.ink70, textDecoration: "none" }}
                                >
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 20a8 8 0 0 1 16 0" /></svg>
                                    {t("profileTitle")}
                                </Link>
                                <Link
                                    href="/settings"
                                    role="menuitem"
                                    onClick={() => setAccountOpen(false)}
                                    className="obs-ghost flex w-full items-center gap-2.5 px-3 py-2 text-[12px]"
                                    style={{ color: c.ink70, textDecoration: "none" }}
                                >
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
                                    {t("settings")}
                                </Link>
                                <div style={{ borderTop: `1px solid ${c.hair}` }} className="my-1" />
                                <button
                                    type="button"
                                    role="menuitem"
                                    onClick={() => { setAccountOpen(false); onLogout(); }}
                                    className="obs-ghost flex w-full items-center gap-2.5 px-3 py-2 text-[12px]"
                                    style={{ color: c.ink70, background: "transparent", border: "none", cursor: "pointer" }}
                                    data-testid="command-obsidian-logout"
                                >
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
                                    {t("logout")}
                                </button>
                            </div>
                        )}
                    </div>
                )}
                <button
                    type="button"
                    onClick={onToggleRight}
                    aria-label={t("cmdToggleShortlistRail")}
                    aria-expanded={rightOpen}
                    className="obs-ghost ms-2 rounded-md p-1.5"
                    style={{ color: rightOpen ? c.ink : c.ink55, background: "transparent", border: "none", cursor: "pointer" }}
                >
                    <PanelIcon side="end" />
                </button>
            </header>

            {/* ── Console body: start rail · children (transcript + right rail) ──
                The palette provider wraps BOTH the left rail and the main area so
                every consumer (conversation rail, composer, messages, right rail)
                reads the same Obsidian palette. */}
            <WorkspaceThemeContext.Provider value={c}>
                <div className="relative z-10 flex min-h-0 flex-1">
                    <aside
                        data-testid="command-obsidian-leftrail"
                        className={`${leftOpen ? "lg:flex lg:w-[260px]" : "lg:w-0"} hidden shrink-0 flex-col overflow-hidden transition-[width] duration-300`}
                        style={{ borderInlineEnd: leftOpen ? `1px solid ${c.hair}` : "none", background: `${c.rail}99` }}
                    >
                        {leftRail}
                    </aside>

                    <main className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden">
                        {children}
                    </main>
                </div>
            </WorkspaceThemeContext.Provider>

            <style dangerouslySetInnerHTML={{
                __html: `
                [data-testid="command-obsidian-shell"] .obs-nav { transition: background-color .15s ease, color .15s ease; }
                [data-testid="command-obsidian-shell"] .obs-nav:hover { background-color: ${c.activeBg}; color: ${c.ink}; }
                [data-testid="command-obsidian-shell"] .obs-ghost { transition: background-color .15s ease, color .15s ease; }
                [data-testid="command-obsidian-shell"] .obs-ghost:hover { background-color: ${c.activeBg}; color: ${c.ink}; }
                [data-testid="command-obsidian-shell"] a:focus-visible,
                [data-testid="command-obsidian-shell"] button:focus-visible { outline: 2px solid ${c.red}; outline-offset: 2px; border-radius: 4px; }
                [data-testid="command-obsidian-shell"] ::selection { background: ${c.red}; color: ${dark ? "#0a0b0d" : "#f4f5f0"}; }
                [lang="ar"][data-testid="command-obsidian-shell"] * { letter-spacing: 0 !important; }
            ` }} />
        </div>
    );
}

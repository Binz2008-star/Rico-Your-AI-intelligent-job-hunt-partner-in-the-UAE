"use client";

/**
 * CommandObsidianShell — slice C1 of the Command Obsidian program
 * (owner directive 2026-07-16; canonical source:
 * `design-handoffs/reviewed/2026-07-16-command-obsidian-v4/`).
 *
 * Route-scoped chrome for the AUTHENTICATED `/command` surface only, replacing
 * WorkspaceShell there: the recording's dark operator console — obsidian
 * canvas with grid grain + acid-lime aura, a full-width h-12 top status bar
 * (panel toggles · Rico · workspace eyebrow · live status · EN/ع · theme),
 * a collapsible 260px start rail carrying the shared workspace nav, and a
 * flexible console area whose children (transcript column + CommandRail)
 * come from CommandPage unchanged.
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
import { useState } from "react";

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
    busy = false,
    leftOpen = true,
    rightOpen = true,
    onToggleLeft,
    onToggleRight,
}: {
    children: React.ReactNode;
    /** True while Rico is thinking/streaming — drives the top-bar status. */
    busy?: boolean;
    leftOpen?: boolean;
    rightOpen?: boolean;
    onToggleLeft?: () => void;
    onToggleRight?: () => void;
}) {
    const { language, setLanguage } = useLanguage();
    const t = useTranslation(language);
    const pathname = usePathname();
    const isAr = language === "ar";
    const [dark, setDark] = useState(true); // "Obsidian night" default
    const c = dark ? COMMAND_OBSIDIAN.dark : COMMAND_OBSIDIAN.light;

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

            {/* ── Console body: start rail · children (transcript + right rail) ── */}
            <div className="relative z-10 flex min-h-0 flex-1">
                <aside
                    data-testid="command-obsidian-navrail"
                    className={`${leftOpen ? "lg:flex lg:w-[260px]" : "lg:w-0"} hidden shrink-0 flex-col overflow-hidden transition-[width] duration-300`}
                    style={{ borderInlineEnd: leftOpen ? `1px solid ${c.hair}` : "none", background: `${c.rail}99` }}
                >
                    <div className="flex w-[260px] flex-1 flex-col p-4">
                        <div className="mb-4" style={{ ...EYEBROW, color: c.ink55, letterSpacing: isAr ? "0.04em" : "0.22em" }}>
                            {t("cmdNavRailTitle")}
                        </div>
                        <nav className="flex flex-col gap-0.5">
                            {WORKSPACE_NAV.map((item) => {
                                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                                return (
                                    <Link
                                        key={item.key}
                                        href={item.href}
                                        className="obs-nav flex items-center gap-3 rounded-md px-2 py-2"
                                        style={{
                                            color: active ? c.ink : c.ink70,
                                            background: active ? c.panel : "transparent",
                                            textDecoration: "none",
                                        }}
                                        aria-current={active ? "page" : undefined}
                                    >
                                        {active && <span aria-hidden="true" className="h-1 w-1 shrink-0 rounded-full" style={{ background: c.red }} />}
                                        <span style={{ color: active ? c.red : c.ink40, display: "inline-flex" }}>{item.icon}</span>
                                        <span style={{ fontSize: 13.5 }}>{isAr ? item.label.ar : item.label.en}</span>
                                    </Link>
                                );
                            })}
                        </nav>
                    </div>
                </aside>

                <WorkspaceThemeContext.Provider value={c}>
                    <main className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden">
                        {children}
                    </main>
                </WorkspaceThemeContext.Provider>
            </div>

            <style dangerouslySetInnerHTML={{ __html: `
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

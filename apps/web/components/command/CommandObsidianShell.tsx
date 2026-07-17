"use client";

/**
 * CommandObsidianShell — /command console chrome, hosted INSIDE the shared
 * WorkspaceShell (visual-consistency correction, owner directive 2026-07-17).
 *
 * Historically this was a self-contained dark "operator console" with its own
 * copied palette (COMMAND_ATELIER), its own top bar duplicating the brand,
 * nav, language and theme controls, and scoped grain/aura canvas layers — so
 * /command read as a separate product from the rest of the workspace. It now
 * composes `WorkspaceShell variant="app"`: the sidebar, navigation, EN/عربي
 * and light/dark controls, palette (WORKSPACE_THEME) and light-first default
 * are byte-identical to Profile / Applications / Upload / Settings /
 * Subscription. Dark stays a user choice via the shared sidebar toggle — it is
 * no longer a /command-only forced default.
 *
 * What remains route-scoped (this file) is only what /command genuinely needs:
 *  - a slim console bar (lg+): Sessions/shortlist panel toggles, the live
 *    READY / WORKING / REPLYING status, and the desktop account/logout menu
 *    (WorkspaceShell has no logout control);
 *  - the collapsible 260px Sessions rail (`leftRail` —
 *    CommandConversationRail);
 *  - the Atelier editorial token layer: Tailwind utilities used by the reply
 *    surface (RicoReply / RicoUserBubble / RicoThinking — bg-ink, text-paper,
 *    border-rule, from-ink/50 …) resolve through CSS vars emitted here from
 *    the ACTIVE shared workspace palette, so both modes stay automatic with
 *    zero duplicated color values.
 *
 * Desktop (lg+) chrome only, matching the surface it replaces: below lg the
 * page keeps MobileCommandHeader + MobileBottomNav exactly as before.
 *
 * ZERO chat-behavior change: no handler, message, streaming, attachment,
 * safety, or API code lives here.
 */

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
import { WORKSPACE_THEME, useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const EYEBROW: React.CSSProperties = {
    fontFamily: ATELIER_FONT.mono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.22em",
};

/* Atelier editorial token layer: the reply surface styles through Tailwind
   utilities backed by CSS vars — `rgb(var(--ink) / <alpha-value>)`. The shared
   WORKSPACE_THEME expresses its soft shades as rgba() strings, so translucent
   tokens are composited over the page background to flat "r g b" channels
   (visually identical, and alpha modifiers like from-ink/50 keep working). */
function parseColor(color: string): { r: number; g: number; b: number; a: number } | null {
    const hex = color.trim().match(/^#([0-9a-f]{6})$/i);
    if (hex) {
        const h = hex[1];
        return {
            r: parseInt(h.slice(0, 2), 16),
            g: parseInt(h.slice(2, 4), 16),
            b: parseInt(h.slice(4, 6), 16),
            a: 1,
        };
    }
    const fn = color
        .trim()
        .match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/i);
    if (fn) {
        return { r: +fn[1], g: +fn[2], b: +fn[3], a: fn[4] === undefined ? 1 : +fn[4] };
    }
    return null;
}

function channels(color: string, over: string): string {
    const fg = parseColor(color);
    if (!fg) return "0 0 0";
    const bg = parseColor(over);
    if (fg.a >= 1 || !bg) return `${fg.r} ${fg.g} ${fg.b}`;
    const mix = (f: number, b: number) => Math.round(fg.a * f + (1 - fg.a) * b);
    return `${mix(fg.r, bg.r)} ${mix(fg.g, bg.g)} ${mix(fg.b, bg.b)}`;
}

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

export function CommandObsidianShell(props: {
    children: React.ReactNode;
    /** Content of the start rail — the canonical Sessions position. */
    leftRail?: React.ReactNode;
    /** True while Rico is thinking/streaming — drives the console status. */
    busy?: boolean;
    /** A streamed reply is actively rendering (slice C2) — REPLYING status. */
    replying?: boolean;
    leftOpen?: boolean;
    rightOpen?: boolean;
    onToggleLeft?: () => void;
    onToggleRight?: () => void;
    /** Called when the user clicks Log out in the desktop account menu. */
    onLogout?: () => void;
}) {
    return (
        <WorkspaceShell variant="app">
            <CommandConsole {...props} />
        </WorkspaceShell>
    );
}

function CommandConsole({
    children,
    leftRail,
    busy = false,
    replying = false,
    leftOpen = true,
    rightOpen = true,
    onToggleLeft,
    onToggleRight,
    onLogout,
}: Parameters<typeof CommandObsidianShell>[0]) {
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";
    const c = useWorkspaceTheme();
    // The shared shell owns the light/dark island; infer the active mode for
    // the data attribute consumers (tests, debugging) key off.
    const dark = c.bg === WORKSPACE_THEME.dark.bg;

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
            className="relative flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden"
            style={{
                background: c.bg,
                color: c.ink,
                colorScheme: dark ? "dark" : "light",
                // Atelier editorial token layer — derived from the shared
                // workspace palette so the reply surface and any bg-ink /
                // text-paper / border-rule / from-ink/50 utilities resolve.
                ["--ink" as string]: channels(c.ink, c.bg),
                ["--ink-soft" as string]: channels(c.ink70, c.bg),
                ["--ink-mute" as string]: channels(c.ink55, c.bg),
                ["--paper" as string]: channels(c.bg, c.bg),
                ["--paper-2" as string]: channels(c.panel, c.bg),
                ["--rule" as string]: channels(c.hair, c.bg),
                ["--sun" as string]: channels(c.red, c.bg),
            } as React.CSSProperties}
        >
            {/* ── Console bar (lg+; mobile keeps MobileCommandHeader). Brand, nav,
                language and theme controls live in the shared workspace sidebar —
                only command-specific controls remain here. ── */}
            <header
                data-testid="command-obsidian-topbar"
                className="relative z-20 hidden h-11 shrink-0 items-center gap-3 px-4 md:px-6 lg:flex"
                style={{ background: c.rail, borderBottom: `1px solid ${c.hair}` }}
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
                        className={`h-1.5 w-1.5 rounded-full ${busy || replying ? "animate-pulse" : ""}`}
                        style={{ background: busy || replying ? c.red : c.track }}
                    />
                    {replying ? t("cmdStatusReplying") : busy ? t("cmdStatusWorking") : t("cmdStatusReady")}
                </span>
                {/* Compact account menu — desktop logout control (WorkspaceShell has
                    no logout). Reuses the existing handleLogout passed via onLogout;
                    no duplicated auth/token-clearing logic. */}
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
                                className="absolute end-0 top-[calc(100%+4px)] z-50 w-44 rounded-lg py-1 animate-fade-in-scale motion-reduce:animate-none origin-top"
                                style={{ background: c.panel, border: `1px solid ${c.hair}`, boxShadow: dark ? "0 8px 24px rgba(0,0,0,0.35)" : "0 8px 24px rgba(31,27,21,0.12)" }}
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

            {/* ── Console body: start rail · children (transcript + right rail) ── */}
            <div className="relative z-10 flex min-h-0 flex-1">
                <aside
                    data-testid="command-obsidian-leftrail"
                    className={`${leftOpen ? "lg:flex lg:w-[260px]" : "lg:w-0"} hidden shrink-0 flex-col overflow-hidden transition-[width] duration-300`}
                    style={{ borderInlineEnd: leftOpen ? `1px solid ${c.hair}` : "none", background: c.rail }}
                >
                    {leftRail}
                </aside>

                <main className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden">
                    {children}
                </main>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                [data-testid="command-obsidian-shell"] .obs-nav { transition: background-color .15s ease, color .15s ease; }
                [data-testid="command-obsidian-shell"] .obs-nav:hover { background-color: ${c.activeBg}; color: ${c.ink}; }
                [data-testid="command-obsidian-shell"] .obs-ghost { transition: background-color .15s ease, color .15s ease; }
                [data-testid="command-obsidian-shell"] .obs-ghost:hover { background-color: ${c.activeBg}; color: ${c.ink}; }
                [data-testid="command-obsidian-shell"] a:focus-visible,
                [data-testid="command-obsidian-shell"] button:focus-visible { outline: 2px solid ${c.red}; outline-offset: 2px; border-radius: 4px; }
                [data-testid="command-obsidian-shell"] ::selection { background: ${c.red}; color: ${c.bg}; }
                [data-testid="command-obsidian-shell"] .serif { font-family: var(--font-fraunces-landing), var(--font-naskh-arabic, "Noto Naskh Arabic"), Georgia, serif; }
                [data-testid="command-obsidian-shell"] .serif-italic { font-family: var(--font-fraunces-landing), var(--font-naskh-arabic, "Noto Naskh Arabic"), Georgia, serif; font-style: italic; }
                /* ── Reply-experience motion layer (2026-07-17) ─────────────────
                   Reasoning shimmer: a sun-red sweep through the thinking label.
                   Gradient text needs transparent fill, so reduced-motion gets a
                   solid-color fallback instead of a frozen transparent state. */
                [data-testid="command-obsidian-shell"] .atl-reason-shimmer {
                    background-image: linear-gradient(90deg, ${c.ink55} 0%, ${c.ink} 35%, ${c.red} 50%, ${c.ink} 65%, ${c.ink55} 100%);
                    background-size: 200% 100%;
                    -webkit-background-clip: text;
                    background-clip: text;
                    -webkit-text-fill-color: transparent;
                    color: transparent;
                    animation: shimmer 2.4s linear infinite;
                }
                @media (prefers-reduced-motion: reduce) {
                    [data-testid="command-obsidian-shell"] .atl-reason-shimmer {
                        animation: none;
                        background-image: none;
                        -webkit-text-fill-color: currentColor;
                        color: inherit;
                    }
                }
                /* Job cards: gentle hover lift + deepened shadow (inline base
                   shadow is overridden here, so !important is required). */
                [data-testid="command-obsidian-shell"] .atl-match-card {
                    transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
                }
                [data-testid="command-obsidian-shell"] .atl-match-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 1px 2px rgba(0,0,0,0.06), 0 12px 28px rgba(0,0,0,0.12) !important;
                }
                @media (prefers-reduced-motion: reduce) {
                    [data-testid="command-obsidian-shell"] .atl-match-card:hover { transform: none; }
                }
                /* Staggered entrance for sibling cards in one reply. */
                [data-testid="command-obsidian-shell"] .atl-match-card:nth-of-type(2) { animation-delay: 70ms; }
                [data-testid="command-obsidian-shell"] .atl-match-card:nth-of-type(3) { animation-delay: 140ms; }
                [data-testid="command-obsidian-shell"] .atl-match-card:nth-of-type(4) { animation-delay: 210ms; }
                [data-testid="command-obsidian-shell"] .atl-match-card:nth-of-type(5) { animation-delay: 280ms; }
                [data-testid="command-obsidian-shell"] .atl-match-card:nth-of-type(n+6) { animation-delay: 340ms; }
                [lang="ar"][data-testid="command-obsidian-shell"] * { letter-spacing: 0 !important; }
            ` }} />
        </div>
    );
}

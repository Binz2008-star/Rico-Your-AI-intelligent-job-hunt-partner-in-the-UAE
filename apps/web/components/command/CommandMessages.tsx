"use client";

/**
 * CommandMessages — PR 4b of the Atelier full-site migration program.
 *
 * Atelier presentation for the /command message stream and empty state,
 * derived from the approved in-repo reference (`components/ui/rico/
 * RicoMessageBubble.tsx`): typography-first — user turns are end-aligned
 * emphasized ink, Rico turns are flowing text behind a serif "R" mark.
 * No messenger pills.
 *
 * SCOPE: message row shell + empty state only. Job cards, tool/action
 * cards, streaming/thinking states, and the right rail are slices 4c–4e
 * and render unchanged as children of the row.
 *
 * ZERO behavior change: all handlers, message data, and nested content
 * live in CommandPage. The public/guest surface keeps the pre-4b classes
 * verbatim — the Atelier surface is authenticated-only, matching 4a.
 */

import React from "react";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";

/* ── Atelier "R" mark (replaces the gold rico-orb on the Atelier surface) ── */

export function AtelierRicoMark({
    size = 24,
    hidden = false,
}: {
    size?: number;
    hidden?: boolean;
}) {
    const c = useWorkspaceTheme();
    return (
        <div
            aria-hidden="true"
            data-testid="atelier-rico-mark"
            className={`flex shrink-0 items-center justify-center rounded-full ${hidden ? "invisible" : ""}`}
            style={{
                width: size,
                height: size,
                background: c.panel,
                border: `1px solid ${c.hair}`,
                color: c.red,
                fontFamily: ATELIER_FONT.serif,
                fontSize: Math.round(size * 0.5),
                lineHeight: 1,
                marginTop: 2,
            }}
        >
            <span>R</span>
        </div>
    );
}

/* ── Message row ─────────────────────────────────────────────────────────── */

export interface CommandMessageRowProps {
    /** Atelier surface (authenticated) vs. original public surface. */
    authenticated: boolean;
    role: "user" | "rico";
    isFirstInGroup: boolean;
    /** profile_preview renders on a paper panel; other Rico turns flow. */
    isStructured: boolean;
    /** True for a message hydrated from history rather than freshly
     *  sent/streamed — suppresses the entrance animation. */
    skipEntranceAnimation?: boolean;
    children: React.ReactNode;
}

/**
 * Row shell: alignment, grouping rhythm, Rico mark, and the message
 * surface. Inner content (captions, markdown, cards, actions) is passed
 * through untouched.
 */
export function CommandMessageRow({
    authenticated,
    role,
    isFirstInGroup,
    isStructured,
    skipEntranceAnimation = false,
    children,
}: CommandMessageRowProps) {
    const c = useWorkspaceTheme();
    const entranceClass = skipEntranceAnimation ? "" : "animate-in fade-in motion-reduce:animate-none";

    if (!authenticated) {
        /* Pre-4b public surface, unchanged. */
        return (
            <div
                dir="ltr"
                className={`flex min-h-6 ${entranceClass} ${role === "user" ? "justify-end items-end" : "justify-start items-start gap-2.5"} ${isFirstInGroup ? "mt-4" : "mt-1"}`}
            >
                {role === "rico" && (
                    <div
                        className={`rico-orb !w-6 !h-6 !text-[10px] mt-0.5 shrink-0 ${isFirstInGroup ? "" : "invisible"}`}
                        aria-hidden="true"
                    ><span>R</span></div>
                )}
                <div dir="auto" className={`${role === "user"
                    ? "max-w-[84%] break-words rounded-2xl rounded-tr-sm bg-gold px-3.5 py-2.5 text-start text-[14px] font-medium leading-relaxed text-white sm:max-w-[72%]"
                    : isStructured
                        ? "flex-1 min-w-0 rounded-xl border border-border-subtle/70 bg-surface-elevated/60 p-3 text-start text-[13px] leading-relaxed text-rico-text"
                        : "flex-1 min-w-0 break-words text-start text-[14px] leading-relaxed text-rico-text"
                    }`}>
                    {children}
                </div>
            </div>
        );
    }

    /* Atelier surface — typography-first, per the approved reference. */
    if (role === "user") {
        return (
            <div
                dir="ltr"
                data-testid="atelier-user-row"
                className={`flex min-h-6 animate-in fade-in motion-reduce:animate-none justify-end items-end ${isFirstInGroup ? "mt-5" : "mt-1.5"}`}
            >
                <div
                    dir="auto"
                    className="max-w-[84%] min-w-0 break-words whitespace-pre-wrap text-start text-[14.5px] leading-relaxed sm:max-w-[72%] rounded-xl px-3.5 py-2"
                    style={{
                        color: c.ink,
                        fontFamily: ATELIER_FONT.body,
                        fontWeight: 500,
                        background: c.panel,
                        border: `1px solid ${c.hair}`,
                    }}
                >
                    {children}
                </div>
            </div>
        );
    }

    return (
        <div
            dir="ltr"
            data-testid="atelier-rico-row"
            className={`flex min-h-6 animate-in fade-in motion-reduce:animate-none justify-start items-start gap-2.5 ${isFirstInGroup ? "mt-5" : "mt-1.5"}`}
        >
            <AtelierRicoMark hidden={!isFirstInGroup} />
            <div
                dir="auto"
                className={
                    isStructured
                        ? "flex-1 min-w-0 rounded-xl p-3 text-start text-[13px] leading-relaxed"
                        : "flex-1 min-w-0 break-words text-start text-[14px] leading-relaxed"
                }
                style={{
                    color: c.ink,
                    fontFamily: ATELIER_FONT.body,
                    ...(isStructured
                        ? { background: c.panel, border: `1px solid ${c.hair}` }
                        : null),
                }}
            >
                {children}
            </div>
        </div>
    );
}

/* ── Markdown color scope ────────────────────────────────────────────────── */

/**
 * Scopes the `--rico-*` text variables consumed by RicoMarkdownContent to
 * Atelier ink/sun-red. Applied ONLY around the markdown text — job/action
 * cards elsewhere in the row keep the global variables (4c scope).
 */
export function AtelierMarkdownScope({
    authenticated,
    children,
}: {
    authenticated: boolean;
    children: React.ReactNode;
}) {
    const c = useWorkspaceTheme();
    if (!authenticated) return <>{children}</>;
    return (
        <div
            data-testid="atelier-markdown-scope"
            style={
                {
                    "--rico-fg-1": c.ink,
                    "--rico-fg-2": c.ink55,
                    "--rico-fg-3": c.ink40,
                    "--rico-primary": c.red,
                } as React.CSSProperties
            }
        >
            {children}
        </div>
    );
}

/* ── Empty state ─────────────────────────────────────────────────────────── */

export interface CommandQuickAction {
    key: string;
    label: string;
    icon: React.ReactNode;
    onClick: () => void;
}

export interface CommandEmptyStateProps {
    authenticated: boolean;
    /** "hero" = mark + title + subtitle + chips (no messages yet);
     *  "chips" = chips only (welcome message already on screen). */
    variant: "hero" | "chips";
    title: string;
    subtitle: string;
    actions: CommandQuickAction[];
    disabled: boolean;
}

export function CommandEmptyState({
    authenticated,
    variant,
    title,
    subtitle,
    actions,
    disabled,
}: CommandEmptyStateProps) {
    const c = useWorkspaceTheme();

    if (!authenticated) {
        /* Pre-4b public surface, unchanged. */
        if (variant === "hero") {
            return (
                <div className="flex flex-col items-center gap-5 pb-4 pt-6 sm:pt-10 animate-in fade-in motion-reduce:animate-none">
                    <div className="flex flex-col items-center gap-3 text-center">
                        <div className="rico-orb !w-12 !h-12 !text-[18px]" aria-hidden="true"><span>R</span></div>
                        <div>
                            <p className="text-[22px] font-bold tracking-tight text-text-primary sm:text-[26px]">{title}</p>
                            <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary sm:text-[14px]">{subtitle}</p>
                        </div>
                    </div>
                    <div className="grid w-full max-w-xl grid-cols-1 gap-2 min-[480px]:grid-cols-2">
                        {actions.map((qa) => (
                            <button
                                type="button"
                                key={qa.key}
                                onClick={qa.onClick}
                                disabled={disabled}
                                className="group flex min-h-[52px] cursor-pointer items-center gap-3 rounded-2xl border border-border-subtle bg-surface-glass px-4 py-3 text-start text-[12px] text-text-secondary transition-all hover:border-gold/30 hover:bg-surface-subtle hover:text-text-primary disabled:opacity-50 rico-focus-strong"
                            >
                                <span className="shrink-0 text-text-muted transition-colors group-hover:text-gold" aria-hidden="true">{qa.icon}</span>
                                <span>{qa.label}</span>
                            </button>
                        ))}
                    </div>
                </div>
            );
        }
        return (
            <div className="grid grid-cols-1 gap-2 pb-4 min-[480px]:grid-cols-2">
                {actions.map((qa) => (
                    <button
                        type="button"
                        key={qa.key}
                        onClick={qa.onClick}
                        disabled={disabled}
                        className="group flex min-h-[44px] cursor-pointer items-center gap-3 rounded-xl border border-border-subtle bg-surface-glass px-3 py-2.5 text-start text-[11px] text-text-secondary transition-all hover:border-gold/25 hover:bg-surface-subtle hover:text-text-primary disabled:opacity-50 rico-focus-strong"
                    >
                        <span className="shrink-0 text-text-muted transition-colors group-hover:text-gold" aria-hidden="true">{qa.icon}</span>
                        <span>{qa.label}</span>
                    </button>
                ))}
            </div>
        );
    }

    /* Atelier surface. */
    const chip = (qa: CommandQuickAction, compact: boolean, index = 0) => (
        <button
            type="button"
            key={qa.key}
            onClick={qa.onClick}
            disabled={disabled}
            data-testid="atelier-quick-chip"
            className={`atl-chip group flex cursor-pointer items-center gap-3 rounded-xl text-start transition-all disabled:opacity-50 animate-fade-up motion-reduce:animate-none ${compact ? "min-h-[44px] px-3 py-2.5 text-[12px]" : "min-h-[52px] px-4 py-3 text-[13px]"}`}
            style={{
                background: c.panel,
                border: `1px solid ${c.hair}`,
                color: c.ink55,
                fontFamily: ATELIER_FONT.body,
                animationDelay: `${index * 60}ms`,
            }}
        >
            <span className="atl-chip-icon shrink-0 transition-colors" style={{ color: c.ink40 }} aria-hidden="true">
                {qa.icon}
            </span>
            <span>{qa.label}</span>
        </button>
    );

    /* Scoped hover styles (inline styles can't express :hover). */
    const hoverCss = (
        <style dangerouslySetInnerHTML={{ __html: `
            .atl-chip { transition: border-color .18s ease, color .18s ease, transform .18s ease, box-shadow .18s ease; }
            .atl-chip:hover:not(:disabled) { border-color: ${c.red} !important; color: ${c.ink} !important; transform: translateY(-1px); box-shadow: 0 6px 16px rgba(0,0,0,0.08); }
            .atl-chip:hover:not(:disabled) .atl-chip-icon { color: ${c.red} !important; }
            @media (prefers-reduced-motion: reduce) { .atl-chip:hover:not(:disabled) { transform: none; } }
        ` }} />
    );

    if (variant === "hero") {
        return (
            <div
                data-testid="atelier-empty-hero"
                className="flex flex-col items-center gap-6 pb-4 pt-6 sm:pt-12 animate-in fade-in motion-reduce:animate-none"
            >
                <div className="flex flex-col items-center gap-4 text-center">
                    <AtelierRicoMark size={48} />
                    <div>
                        <p
                            className="text-[24px] tracking-tight sm:text-[30px]"
                            style={{ color: c.ink, fontFamily: ATELIER_FONT.serif, fontWeight: 600 }}
                        >
                            {title}
                        </p>
                        <p
                            className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed sm:text-[14px]"
                            style={{ color: c.ink55, fontFamily: ATELIER_FONT.body }}
                        >
                            {subtitle}
                        </p>
                    </div>
                </div>
                <div className="grid w-full max-w-xl grid-cols-1 gap-2 min-[480px]:grid-cols-2">
                    {actions.map((qa, i) => chip(qa, false, i))}
                </div>
                {hoverCss}
            </div>
        );
    }

    return (
        <div data-testid="atelier-empty-chips" className="grid grid-cols-1 gap-2 pb-4 min-[480px]:grid-cols-2">
            {actions.map((qa, i) => chip(qa, true, i))}
            {hoverCss}
        </div>
    );
}

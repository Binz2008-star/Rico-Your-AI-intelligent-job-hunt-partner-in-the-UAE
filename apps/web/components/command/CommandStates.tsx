"use client";

/**
 * CommandStates — PR 4c of the Atelier full-site migration program.
 *
 * Atelier presentation for the /command working/thinking, streaming,
 * option-chip, retry, rate-limit, and slow-request states. Per the program
 * spec these are built in Atelier paper/ink/sun-red tokens — shimmer over
 * spinner for the thinking state, a sun-red tail caret for streaming — and
 * NOT the legacy `--gold` / `rico-thinking-row` Nocturne classes.
 *
 * Every component keeps a `atelier={false}` branch that reproduces the
 * pre-4c public/guest markup verbatim, matching the 4a/4b pattern: the
 * Atelier surface is authenticated-only.
 *
 * ZERO behavior change: handlers, timers, and visibility logic keep their
 * existing contracts (incl. the e2e-pinned `visible`/`invisible` classes on
 * the slow banner).
 */

import React, { useEffect, useState } from "react";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { AtelierRicoMark } from "@/components/command/CommandMessages";
import type { TranslationKey } from "@/lib/translations";

/* ── Thinking / working state ────────────────────────────────────────────── */

export function CommandWorkingState({
    atelier,
    message,
}: {
    atelier: boolean;
    message: string;
}) {
    const c = useWorkspaceTheme();

    if (!atelier) {
        /* Pre-4c public surface, unchanged. */
        return (
            <div className="rico-thinking-row" role="status" aria-live="polite" aria-label={message}>
                <span className="sr-only">{message}</span>
                <div className="rico-orb" aria-hidden="true"><span>R</span></div>
                <div className="rico-thinking-label">
                    <span>{message}</span>
                    <span className="rico-dots" aria-hidden="true"><i /><i /><i /></span>
                </div>
            </div>
        );
    }

    /* Atelier: mark + shimmering ink label (shimmer over spinner). */
    return (
        <div
            className="flex items-center gap-2.5"
            role="status"
            aria-live="polite"
            aria-label={message}
            data-testid="atelier-working-state"
        >
            <span className="sr-only">{message}</span>
            <AtelierRicoMark />
            <span
                aria-hidden="true"
                className="atl4c-shimmer text-[13px]"
                style={{ fontFamily: ATELIER_FONT.body }}
            >
                {message}
            </span>
            <style dangerouslySetInnerHTML={{ __html: `
                .atl4c-shimmer {
                    background: linear-gradient(90deg, ${c.ink40} 0%, ${c.ink} 50%, ${c.ink40} 100%);
                    background-size: 200% 100%;
                    -webkit-background-clip: text;
                    background-clip: text;
                    color: transparent;
                    animation: atl4c-sweep 1.6s linear infinite;
                }
                @keyframes atl4c-sweep {
                    from { background-position: 200% 0; }
                    to { background-position: 0% 0; }
                }
                @media (prefers-reduced-motion: reduce) {
                    .atl4c-shimmer { animation: none; background: none; color: ${c.ink55}; -webkit-text-fill-color: ${c.ink55}; }
                }
            ` }} />
        </div>
    );
}

/* ── Search elapsed timer (below the working state while searching) ──────── */

export function CommandSearchTimer({
    atelier,
    t,
}: {
    atelier: boolean;
    t: (k: TranslationKey) => string;
}) {
    const c = useWorkspaceTheme();
    const [elapsed, setElapsed] = useState(0);
    useEffect(() => {
        const id = setInterval(() => setElapsed((s) => s + 1), 1000);
        return () => clearInterval(id);
    }, []);
    const hint =
        elapsed >= 20 ? t("cmdSearchWakingUp")
            : elapsed >= 10 ? t("cmdSearchStillLooking")
                : null;

    if (!atelier) {
        /* Pre-4c public surface, unchanged. */
        return (
            <div className="pl-[42px] flex flex-col gap-1">
                <span className="text-[11px] tabular-nums text-text-muted" aria-live="off">{elapsed}s</span>
                {hint && (
                    <p className="text-[11px] text-text-muted animate-pulse motion-reduce:animate-none" role="status">
                        {hint}
                    </p>
                )}
            </div>
        );
    }

    return (
        <div className="pl-[34px] flex flex-col gap-1" data-testid="atelier-search-timer">
            <span
                className="text-[11px] tabular-nums"
                aria-live="off"
                style={{ color: c.ink40, fontFamily: ATELIER_FONT.mono }}
            >
                {elapsed}s
            </span>
            {hint && (
                <p
                    className="text-[11px] animate-pulse motion-reduce:animate-none"
                    role="status"
                    style={{ color: c.ink55, fontFamily: ATELIER_FONT.body }}
                >
                    {hint}
                </p>
            )}
        </div>
    );
}

/* ── Streaming tail caret ────────────────────────────────────────────────── */

/** Sun-red pulsing caret appended after streaming Rico text (Atelier only). */
export function AtelierStreamCaret() {
    const c = useWorkspaceTheme();
    return (
        <span
            aria-hidden="true"
            data-testid="atelier-stream-caret"
            className="atl4c-caret ml-0.5 inline-block align-text-bottom rounded-[1px]"
            style={{ width: 2.5, height: 15, background: c.red }}
        >
            <style dangerouslySetInnerHTML={{ __html: `
                .atl4c-caret { animation: atl4c-blink 1s steps(2, start) infinite; }
                @keyframes atl4c-blink { to { visibility: hidden; } }
                @media (prefers-reduced-motion: reduce) { .atl4c-caret { animation: none; } }
            ` }} />
        </span>
    );
}

/* ── Option chips (m.options and role-confirmation next_actions) ─────────── */

export interface CommandOptionChip {
    key: string;
    label: string;
    onClick: () => void;
}

export function CommandOptionChips({
    atelier,
    options,
    size = "md",
}: {
    atelier: boolean;
    options: CommandOptionChip[];
    /** md = m.options row (12px); sm = role-confirmation next_actions (11px). */
    size?: "md" | "sm";
}) {
    const c = useWorkspaceTheme();
    if (!options.length) return null;

    if (!atelier) {
        /* Pre-4c public surface, unchanged. */
        const cls =
            size === "sm"
                ? "text-[11px] px-3 py-1.5 rounded-xl border border-gold/30 text-gold hover:bg-gold/10 hover:border-gold/50 transition-colors rico-focus-strong"
                : "text-[12px] px-3 py-2 rounded-xl border border-gold/30 text-gold hover:bg-gold/10 hover:border-gold/50 transition-colors rico-focus-strong";
        return (
            <div className={size === "sm" ? "flex flex-wrap gap-2 pt-1" : "flex flex-wrap gap-2 mt-2"}>
                {options.map((opt) => (
                    <button type="button" key={opt.key} onClick={opt.onClick} className={cls}>
                        {opt.label}
                    </button>
                ))}
            </div>
        );
    }

    return (
        <div
            className={size === "sm" ? "flex flex-wrap gap-2 pt-1" : "flex flex-wrap gap-2 mt-2"}
            data-testid="atelier-option-chips"
        >
            {options.map((opt) => (
                <button
                    type="button"
                    key={opt.key}
                    onClick={opt.onClick}
                    className={`atl4c-chip rounded-xl transition-colors ${size === "sm" ? "text-[11px] px-3 py-1.5" : "text-[12px] px-3 py-2"}`}
                    style={{
                        background: "transparent",
                        border: `1px solid ${c.hair}`,
                        color: c.ink55,
                        fontFamily: ATELIER_FONT.body,
                    }}
                >
                    {opt.label}
                </button>
            ))}
            <style dangerouslySetInnerHTML={{ __html: `
                .atl4c-chip:hover { border-color: ${c.red} !important; color: ${c.red} !important; }
            ` }} />
        </div>
    );
}

/* ── Retry button (error turns) ──────────────────────────────────────────── */

export function CommandRetryButton({
    atelier,
    onClick,
    disabled,
    label,
    icon,
}: {
    atelier: boolean;
    onClick: () => void;
    disabled: boolean;
    label: string;
    icon: React.ReactNode;
}) {
    const c = useWorkspaceTheme();

    if (!atelier) {
        /* Pre-4c public surface, unchanged. */
        return (
            <button
                type="button"
                onClick={onClick}
                disabled={disabled}
                className="inline-flex items-center gap-1 text-[10px] text-gold transition-colors hover:text-gold-hover disabled:opacity-50 rico-focus-strong"
                aria-label={label}
            >
                {icon}
                {label}
            </button>
        );
    }

    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            className="inline-flex items-center gap-1 text-[10px] transition-opacity hover:opacity-75 disabled:opacity-50"
            aria-label={label}
            data-testid="atelier-retry-button"
            style={{ color: c.red, fontFamily: ATELIER_FONT.mono, letterSpacing: "0.04em" }}
        >
            {icon}
            {label}
        </button>
    );
}

/* ── Source rate-limited notice ──────────────────────────────────────────── */

export function CommandRateLimitNotice({
    atelier,
    children,
}: {
    atelier: boolean;
    children: React.ReactNode;
}) {
    const c = useWorkspaceTheme();

    if (!atelier) {
        /* Pre-4c public surface, unchanged. */
        return (
            <div className="mt-2 flex items-start gap-2 rounded-lg border border-gold/30 bg-gold/8 px-3 py-2 text-[11px] text-gold">
                {children}
            </div>
        );
    }

    return (
        <div
            className="mt-2 flex items-start gap-2 rounded-lg px-3 py-2 text-[11px]"
            data-testid="atelier-rate-limit-notice"
            style={{
                background: c.panel,
                border: `1px solid ${c.hair}`,
                color: c.ink55,
                fontFamily: ATELIER_FONT.body,
            }}
        >
            {children}
        </div>
    );
}

/* ── Cold-start / slow-request banner ────────────────────────────────────── */

/**
 * Overlay banner shown when a request is slow. The `visible`/`invisible`
 * class contract is pinned by e2e (`command-composer-stability.spec.ts`)
 * and preserved on both surfaces.
 */
export function CommandSlowBanner({
    atelier,
    shown,
    label,
}: {
    atelier: boolean;
    shown: boolean;
    label: string;
}) {
    const c = useWorkspaceTheme();
    const visibility = shown ? "visible opacity-100" : "invisible opacity-0";

    if (!atelier) {
        /* Pre-4c public surface, unchanged. */
        return (
            <div
                role="status"
                aria-hidden={!shown}
                data-testid="command-slow-banner"
                className={`pointer-events-none absolute inset-x-0 top-0 z-20 mx-2 mt-2 flex min-h-9 items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-[11px] font-medium text-amber-300 shadow-lg shadow-background/40 transition-opacity duration-200 sm:mx-4 ${visibility}`}
            >
                <span aria-hidden="true">⚡</span>
                {label}
            </div>
        );
    }

    return (
        <div
            role="status"
            aria-hidden={!shown}
            data-testid="command-slow-banner"
            className={`pointer-events-none absolute inset-x-0 top-0 z-20 mx-2 mt-2 flex min-h-9 items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-medium shadow-lg transition-opacity duration-200 sm:mx-4 ${visibility}`}
            style={{
                background: c.panel,
                border: `1px solid ${c.hair}`,
                color: c.ink,
                fontFamily: ATELIER_FONT.body,
                boxShadow: "0 4px 16px rgba(0,0,0,0.35)",
            }}
        >
            <span aria-hidden="true" style={{ color: c.red }}>⚡</span>
            {label}
        </div>
    );
}

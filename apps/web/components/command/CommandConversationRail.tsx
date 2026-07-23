"use client";

/**
 * CommandConversationRail — the /command Sessions surface.
 *
 * TRUTHFUL BY CONSTRUCTION (C1 correction, owner directive 2026-07-16): the
 * rail renders only real state. Historically that meant exactly one
 * conversation, because the backend had no multi-session API. That capability
 * gap is now closed (#1193): `GET /api/v1/rico/chat/sessions` derives threads
 * from real chat history, so in `multiSession` mode the rail lists every
 * server-known thread — title from each thread's real first user turn, real
 * turn counts — and switches between them via the page's real handlers. It
 * still never fabricates sessions: a brand-new thread appears only as the
 * user-minted draft it actually is.
 *
 * When `multiSession` is false (guest sessions, or a backend without the
 * sessions endpoint yet) the rail renders the original single-conversation
 * surface unchanged.
 *
 * Motion layer reuses the shell's established vocabulary (fade-up entrance
 * with stagger, fade-in-scale, pulse) and always pairs with
 * motion-reduce:animate-none.
 *
 * Presentation-only: every action is an existing CommandPage handler.
 */

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import React from "react";

/** One rail entry: a server-derived thread or the local unsent draft. */
export interface RailSessionEntry {
    id: string;
    /** First real user turn of the thread; null = no user message yet. */
    title: string | null;
    userTurns: number;
    /** Client-minted via "+ new", no server rows yet. */
    draft?: boolean;
}

/** Derive the conversation title from the real transcript (pure, unit-tested):
 *  the first user turn, trimmed and capped — or the fallback when the user
 *  hasn't written yet. Never invents content. */
export function deriveConversationTitle(
    messages: Array<{ role: "user" | "rico"; text: string }>,
    fallback: string,
    max = 44,
): string {
    const first = messages.find((m) => m.role === "user" && m.text.trim().length > 0);
    if (!first) return fallback;
    const title = first.text.trim().replace(/\s+/g, " ");
    return title.length > max ? title.slice(0, max - 1).trimEnd() + "…" : title;
}

/** Real user turns only — the synthetic Rico welcome/greeting must never be
 *  counted as conversation activity (owner blocker, 2026-07-16). */
export function countUserTurns(
    messages: Array<{ role: "user" | "rico"; text: string }>,
): number {
    return messages.filter((m) => m.role === "user" && m.text.trim().length > 0).length;
}

/** A conversation is REAL only when server history was loaded or the user has
 *  actually written. A welcome-only transcript is not a conversation. */
export function hasRealConversation(
    messages: Array<{ role: "user" | "rico"; text: string }>,
    historyState: "pending" | "has_history" | "empty",
): boolean {
    return historyState === "has_history" || countUserTurns(messages) > 0;
}

export function CommandConversationRail({
    audience,
    messages,
    historyState,
    historyLoadError,
    busy,
    confirmClear,
    clearingHistory,
    onNewChat,
    onClearHistory,
    onCancelClear,
    multiSession = false,
    sessions = [],
    activeSessionId = "default",
    switchingSessionId = null,
    sessionSwitchError = false,
    onSelectSession,
    variant = "full",
}: {
    audience: "checking" | "public" | "authenticated";
    messages: Array<{ role: "user" | "rico"; text: string }>;
    historyState: "pending" | "has_history" | "empty";
    /** True when the authenticated server-history fetch failed (real signal). */
    historyLoadError: boolean;
    busy: boolean;
    confirmClear: boolean;
    clearingHistory: boolean;
    onNewChat: () => void;
    onClearHistory: () => void;
    onCancelClear: () => void;
    /** Multi-thread mode — on only when the sessions API answered (#1193). */
    multiSession?: boolean;
    sessions?: RailSessionEntry[];
    activeSessionId?: string;
    /** Thread whose history is being fetched right now (switch in flight). */
    switchingSessionId?: string | null;
    /** True when the last thread switch failed to load (real signal). */
    sessionSwitchError?: boolean;
    onSelectSession?: (id: string) => void;
    /** "full": today's text rail (unchanged), used at ≥1200px and inside the
     *  Sessions drawer (768–899px). "compact": a ~64–80px icon/initial-only
     *  column for the 900–1199px tier (TASK-20260723-002). A static prop set
     *  once per call site — never computed from a viewport measurement — so
     *  which variant renders where is decided entirely by which CSS-gated
     *  wrapper the instance sits inside (no JS breakpoint state machine). */
    variant?: "full" | "compact";
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";

    const eyebrow: React.CSSProperties = {
        fontFamily: ATELIER_FONT.mono,
        fontSize: 9,
        fontWeight: 500,
        textTransform: "uppercase",
        letterSpacing: isAr ? "0.04em" : "0.1em",
    };

    const loading = audience === "checking" || (audience === "authenticated" && historyState === "pending");
    const title = deriveConversationTitle(messages, t("cmdSessionsCurrentFallback"));
    // Real-conversation model (owner blocker): a synthetic welcome-only
    // transcript shows the fallback title with NO count and NO Clear History.
    const userTurnCount = countUserTurns(messages);
    const real = hasRealConversation(messages, historyState);
    // Delete/clear is offered for a real live transcript, or (multi-session)
    // an active thread with persisted user turns — never for an unsent draft.
    const activeEntry = multiSession ? sessions.find((s) => s.id === activeSessionId) : undefined;
    const clearable = multiSession ? real || (activeEntry ? activeEntry.userTurns > 0 : false) : real;

    if (variant === "compact") {
        // 900–1199px (TASK-20260723-002): a narrow icon/initial-only column,
        // not a shrunk copy of the text list — real session identity via a
        // derived initial, an active-state ring, a native title tooltip, and
        // a full accessible name (never an anonymous dot). Clear-history is
        // intentionally not duplicated at this width — it stays reachable via
        // the full rail (≥1200px) or the Sessions drawer (768–899px), which
        // both render the unmodified full variant below.
        return (
            <div
                data-testid="command-conversation-rail-compact"
                className="flex w-20 flex-1 min-h-0 flex-col items-center gap-2 overflow-y-auto py-3"
            >
                <button
                    type="button"
                    onClick={onNewChat}
                    disabled={busy}
                    data-testid="command-rail-new-chat-compact"
                    aria-label={t("cmdSessionsNew")}
                    title={t("cmdSessionsNew")}
                    className="obs-ghost flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                    style={{ border: `1px dashed ${c.hair}`, color: c.ink55, background: "transparent", cursor: busy ? "default" : "pointer" }}
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                        <line x1="12" y1="5" x2="12" y2="19" />
                        <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                </button>
                {multiSession ? (
                    sessions.map((s) => {
                        const isActive = s.id === activeSessionId;
                        const isSwitching = switchingSessionId === s.id;
                        const rowTitle = isActive ? title : (s.title ?? t("cmdSessionsCurrentFallback"));
                        const initial = rowTitle.trim().charAt(0).toUpperCase() || "?";
                        return (
                            <button
                                key={s.id}
                                type="button"
                                onClick={() => { if (!isActive) onSelectSession?.(s.id); }}
                                disabled={busy || clearingHistory || switchingSessionId !== null}
                                aria-current={isActive ? "true" : undefined}
                                aria-label={`${t("cmdSessionOpen")}: ${rowTitle}`}
                                title={rowTitle}
                                data-testid={isActive ? "command-rail-current-compact" : "command-rail-session-compact"}
                                data-session-id={s.id}
                                className="obs-session-row flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold"
                                style={{
                                    background: isActive ? c.panel : "transparent",
                                    color: isActive ? c.ink : c.ink70,
                                    border: isActive ? `1.5px solid ${c.red}` : `1px solid ${c.hair}`,
                                    cursor: isActive || busy || switchingSessionId !== null ? "default" : "pointer",
                                    opacity: isSwitching ? 0.6 : 1,
                                }}
                            >
                                {initial}
                            </button>
                        );
                    })
                ) : (
                    <div
                        data-testid="command-rail-current-compact"
                        aria-label={title}
                        title={title}
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold"
                        style={{ background: c.panel, color: c.ink, border: `1.5px solid ${c.red}` }}
                    >
                        {title.trim().charAt(0).toUpperCase() || "?"}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div data-testid="command-conversation-rail" className="flex w-[220px] flex-1 min-h-0 flex-col p-5 px-3.5">
            {/* Header: SESSIONS */}
            <div className="mb-2.5 flex items-center justify-between px-1">
                <span style={{ ...eyebrow, color: c.ink55 }}>{t("cmdSessionsTitle")}</span>
            </div>

            <button
                type="button"
                onClick={onNewChat}
                disabled={busy}
                data-testid="command-rail-new-chat"
                className="mb-1 w-full rounded-lg border border-dashed border-rule bg-transparent py-2 px-3 text-center text-ink-soft transition-colors hover:border-sun hover:text-sun hover:bg-sun/10 disabled:opacity-50"
                style={{ fontFamily: ATELIER_FONT.mono, fontSize: 11.5, cursor: busy ? "default" : "pointer" }}
            >
                {t("cmdSessionsNew")}
            </button>

            {/* Body: real conversation state only */}
            <div className="flex-1 min-h-0 overflow-y-auto">
                {loading ? (
                    <div
                        data-testid="command-rail-history-loading"
                        style={{ ...eyebrow, color: c.ink55 }}
                        role="status"
                    >
                        {t("cmdSessionsLoading")}
                    </div>
                ) : multiSession ? (
                    <ul className="m-0 flex list-none flex-col gap-1.5 p-0" data-testid="command-rail-sessions">
                        {sessions.map((s, i) => {
                            const isActive = s.id === activeSessionId;
                            const isSwitching = switchingSessionId === s.id;
                            // The active thread stays live: title/count derive from
                            // the on-screen transcript, not the stale server summary.
                            const rowTitle = isActive
                                ? title
                                : (s.title ?? t("cmdSessionsCurrentFallback"));
                            const rowTurns = isActive ? userTurnCount : s.userTurns;
                            const showCount = isActive ? real : s.userTurns > 0;
                            return (
                                <li
                                    key={s.id}
                                    className="animate-fade-up motion-reduce:animate-none"
                                    style={{ animationDelay: `${Math.min(i, 8) * 45}ms` }}
                                >
                                    <button
                                        type="button"
                                        onClick={() => { if (!isActive) onSelectSession?.(s.id); }}
                                        disabled={busy || clearingHistory || switchingSessionId !== null}
                                        aria-current={isActive ? "true" : undefined}
                                        aria-label={`${t("cmdSessionOpen")}: ${rowTitle}`}
                                        data-testid={isActive ? "command-rail-current" : "command-rail-session"}
                                        data-session-id={s.id}
                                        className="obs-session-row flex w-full items-baseline gap-2 rounded-lg py-2.5 px-3 text-start transition-colors"
                                        style={{
                                            background: isActive ? c.bg : "transparent",
                                            color: isActive ? c.ink : c.ink70,
                                            border: isActive ? `1px solid ${c.hair}` : "1px solid transparent",
                                            fontWeight: isActive ? 500 : 400,
                                            cursor: isActive || busy || switchingSessionId !== null ? "default" : "pointer",
                                            opacity: switchingSessionId !== null && !isSwitching && !isActive ? 0.55 : 1,
                                        }}
                                    >
                                        <span
                                            aria-hidden="true"
                                            className={`h-1 w-1 shrink-0 -translate-y-[2px] rounded-full ${(isActive && busy) || isSwitching ? "animate-pulse motion-reduce:animate-none" : ""}`}
                                            style={{ background: isActive || isSwitching ? c.red : c.track }}
                                        />
                                        <span className="min-w-0 flex-1 truncate text-[12px] leading-snug">
                                            {rowTitle}
                                        </span>
                                        {isSwitching ? (
                                            <span
                                                aria-hidden="true"
                                                className="shrink-0 animate-pulse motion-reduce:animate-none"
                                                style={{ ...eyebrow, fontSize: 10, color: c.ink55 }}
                                            >
                                                …
                                            </span>
                                        ) : showCount ? (
                                            <span
                                                dir="ltr"
                                                className="shrink-0"
                                                data-testid={isActive ? "command-rail-turn-count" : undefined}
                                                title={t("cmdSessionsTurnCount")}
                                                style={{ ...eyebrow, fontSize: 10, color: c.ink55 }}
                                            >
                                                {rowTurns}
                                            </span>
                                        ) : null}
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                ) : (
                    <div
                        data-testid="command-rail-current"
                        className="flex items-baseline gap-2 rounded-lg py-2.5 px-3"
                        style={{ background: c.bg, color: c.ink, border: `1px solid ${c.hair}`, fontWeight: 500 }}
                        aria-current="true"
                    >
                        <span aria-hidden="true" className="h-1 w-1 shrink-0 -translate-y-[2px] rounded-full" style={{ background: c.red }} />
                        <span className="min-w-0 flex-1 truncate text-[12px] leading-snug">{title}</span>
                        {real && (
                            <span
                                dir="ltr"
                                className="shrink-0"
                                data-testid="command-rail-turn-count"
                                title={t("cmdSessionsTurnCount")}
                                style={{ ...eyebrow, fontSize: 10, color: c.ink55 }}
                            >
                                {userTurnCount}
                            </span>
                        )}
                    </div>
                )}

                {historyLoadError && (
                    <p
                        data-testid="command-rail-history-error"
                        className="mt-2 text-[11.5px] italic leading-relaxed"
                        style={{ color: c.ink55 }}
                    >
                        {t("cmdSessionsLoadError")}
                    </p>
                )}
                {sessionSwitchError && (
                    <p
                        data-testid="command-rail-switch-error"
                        className="mt-2 text-[11.5px] italic leading-relaxed animate-fade-in-scale motion-reduce:animate-none"
                        style={{ color: c.ink55 }}
                    >
                        {t("cmdSessionSwitchError")}
                    </p>
                )}
            </div>

            {/* Controls: real Clear-history flow — authenticated AND a real
                conversation only (never offered for a synthetic welcome). In
                multi-session mode this deletes the ACTIVE thread only. */}
            {audience === "authenticated" && clearable && (
                <div className="mt-3 border-t pt-3" style={{ borderColor: c.hair }}>
                    {confirmClear ? (
                        <div
                            className="flex items-center gap-2 animate-fade-in-scale motion-reduce:animate-none"
                            style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10 }}
                        >
                            <button
                                type="button"
                                onClick={onClearHistory}
                                disabled={clearingHistory}
                                data-testid="command-rail-clear-confirm"
                                className="rounded px-2 py-1"
                                style={{ border: `1px solid ${c.red}`, color: c.red, background: "transparent", cursor: "pointer", textTransform: "uppercase", letterSpacing: isAr ? "0.02em" : "0.14em" }}
                            >
                                {clearingHistory
                                    ? t("cmdClearing")
                                    : multiSession
                                        ? t("cmdSessionDeleteConfirm")
                                        : t("cmdClearConfirm")}
                            </button>
                            <button
                                type="button"
                                onClick={onCancelClear}
                                className="rounded px-2 py-1"
                                style={{ border: `1px solid ${c.hair}`, color: c.ink70, background: "transparent", cursor: "pointer", textTransform: "uppercase", letterSpacing: isAr ? "0.02em" : "0.14em" }}
                            >
                                {t("cancel")}
                            </button>
                        </div>
                    ) : (
                        <button
                            type="button"
                            onClick={onClearHistory}
                            disabled={busy || clearingHistory}
                            data-testid="command-rail-clear-history"
                            className="obs-ghost rounded px-1"
                            style={{ ...eyebrow, color: c.ink55, background: "transparent", border: "none", cursor: "pointer" }}
                        >
                            {multiSession ? t("cmdSessionDelete") : t("cmdClearHistory")}
                        </button>
                    )}
                </div>
            )}

            {/* Footer — truthful thread count */}
            <div className="mt-3 border-t pt-3" style={{ ...eyebrow, color: c.ink55, borderColor: c.hair }}>
                {multiSession && sessions.length !== 1
                    ? t("cmdSessionsThreadsCount").replace("{count}", String(sessions.length))
                    : t("cmdSessionsThread")}
            </div>

            {/* Session-row micro-motion: colors via obs-ghost (shell layer);
                the inline-start hover nudge and its RTL mirror live here.
                Reduced motion keeps color feedback, drops movement. */}
            <style dangerouslySetInnerHTML={{
                __html: `
                [data-testid="command-conversation-rail"] .obs-session-row {
                    transition: background-color .15s ease, color .15s ease, transform .18s ease;
                }
                [data-testid="command-conversation-rail"] .obs-session-row:not([aria-current]):not(:disabled):hover {
                    transform: translateX(2px);
                    background-color: ${c.bg};
                }
                [dir="rtl"] [data-testid="command-conversation-rail"] .obs-session-row:not([aria-current]):not(:disabled):hover {
                    transform: translateX(-2px);
                    background-color: ${c.bg};
                }
                @media (prefers-reduced-motion: reduce) {
                    [data-testid="command-conversation-rail"] .obs-session-row:hover { transform: none; background-color: ${c.bg}; }
                }
            ` }} />
        </div>
    );
}

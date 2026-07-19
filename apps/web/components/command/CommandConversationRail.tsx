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
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";

    const eyebrow: React.CSSProperties = {
        fontFamily: ATELIER_FONT.mono,
        fontSize: 10,
        textTransform: "uppercase",
        letterSpacing: isAr ? "0.04em" : "0.22em",
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

    return (
        <div data-testid="command-conversation-rail" className="flex w-[260px] flex-1 min-h-0 flex-col p-4">
            {/* Header: SESSIONS · + new */}
            <div className="mb-4 flex items-center justify-between">
                <span style={{ ...eyebrow, color: c.ink55 }}>{t("cmdSessionsTitle")}</span>
                <button
                    type="button"
                    onClick={onNewChat}
                    disabled={busy}
                    data-testid="command-rail-new-chat"
                    className="obs-ghost rounded px-1"
                    style={{ fontFamily: ATELIER_FONT.mono, fontSize: 11, color: c.ink, background: "transparent", border: "none", cursor: busy ? "default" : "pointer", opacity: busy ? 0.5 : 1 }}
                >
                    {t("cmdSessionsNew")}
                </button>
            </div>

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
                    <ul className="m-0 flex list-none flex-col gap-1 p-0" data-testid="command-rail-sessions">
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
                                        className={`obs-session-row flex w-full items-baseline gap-2 rounded-md px-2 py-1.5 text-start ${isActive ? "" : "obs-ghost"}`}
                                        style={{
                                            background: isActive ? c.panel : "transparent",
                                            color: isActive ? c.ink : c.ink70,
                                            border: "none",
                                            cursor: isActive || busy || switchingSessionId !== null ? "default" : "pointer",
                                            opacity: switchingSessionId !== null && !isSwitching && !isActive ? 0.55 : 1,
                                        }}
                                    >
                                        <span
                                            aria-hidden="true"
                                            className={`h-1 w-1 shrink-0 -translate-y-[2px] rounded-full ${(isActive && busy) || isSwitching ? "animate-pulse motion-reduce:animate-none" : ""}`}
                                            style={{ background: isActive || isSwitching ? c.red : c.track }}
                                        />
                                        <span className="min-w-0 flex-1 truncate text-[13px] leading-snug">
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
                        className="flex items-baseline gap-2 rounded-md px-2 py-1.5"
                        style={{ background: c.panel, color: c.ink }}
                        aria-current="true"
                    >
                        <span aria-hidden="true" className="h-1 w-1 shrink-0 -translate-y-[2px] rounded-full" style={{ background: c.red }} />
                        <span className="min-w-0 flex-1 truncate text-[13px] leading-snug">{title}</span>
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
            <style dangerouslySetInnerHTML={{ __html: `
                [data-testid="command-conversation-rail"] .obs-session-row {
                    transition: background-color .15s ease, color .15s ease, transform .18s ease;
                }
                [data-testid="command-conversation-rail"] .obs-session-row:not([aria-current]):not(:disabled):hover {
                    transform: translateX(2px);
                }
                [dir="rtl"] [data-testid="command-conversation-rail"] .obs-session-row:not([aria-current]):not(:disabled):hover {
                    transform: translateX(-2px);
                }
                @media (prefers-reduced-motion: reduce) {
                    [data-testid="command-conversation-rail"] .obs-session-row:hover { transform: none; }
                }
            ` }} />
        </div>
    );
}

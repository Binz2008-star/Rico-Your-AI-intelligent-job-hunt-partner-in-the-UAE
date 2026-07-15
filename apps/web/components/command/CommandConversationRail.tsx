"use client";

/**
 * CommandConversationRail — C1 correction (owner directive 2026-07-16):
 * the canonical recording's left rail is a Sessions/conversation surface,
 * not general application navigation.
 *
 * TRUTHFUL BY CONSTRUCTION: production Rico has exactly one conversation per
 * user (one chat-history endpoint; no multi-session API). This rail renders
 * only real state — the current conversation (title derived from the real
 * first user turn, live message count), the real history loading state, the
 * real history-load failure signal, and the page's real New-chat /
 * Clear-history handlers. It never fabricates previous sessions. True
 * multi-session history is documented as a separately scoped backend
 * capability gap in `design-handoffs/reviewed/2026-07-16-command-obsidian-v4/`.
 *
 * Presentation-only: every action is an existing CommandPage handler.
 */

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";
import React from "react";

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
                ) : (
                    <div
                        data-testid="command-rail-current"
                        className="flex items-baseline gap-2 rounded-md px-2 py-1.5"
                        style={{ background: c.panel, color: c.ink }}
                        aria-current="true"
                    >
                        <span aria-hidden="true" className="h-1 w-1 shrink-0 -translate-y-[2px] rounded-full" style={{ background: c.red }} />
                        <span className="min-w-0 flex-1 truncate text-[13px] leading-snug">{title}</span>
                        <span dir="ltr" className="shrink-0" style={{ ...eyebrow, fontSize: 10, color: c.ink55 }}>
                            {messages.length}
                        </span>
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
            </div>

            {/* Controls: real Clear-history flow (authenticated only — server truth) */}
            {audience === "authenticated" && messages.length > 0 && (
                <div className="mt-3 border-t pt-3" style={{ borderColor: c.hair }}>
                    {confirmClear ? (
                        <div className="flex items-center gap-2" style={{ fontFamily: ATELIER_FONT.mono, fontSize: 10 }}>
                            <button
                                type="button"
                                onClick={onClearHistory}
                                disabled={clearingHistory}
                                data-testid="command-rail-clear-confirm"
                                className="rounded px-2 py-1"
                                style={{ border: `1px solid ${c.red}`, color: c.red, background: "transparent", cursor: "pointer", textTransform: "uppercase", letterSpacing: isAr ? "0.02em" : "0.14em" }}
                            >
                                {clearingHistory ? t("cmdClearing") : t("cmdClearConfirm")}
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
                            {t("cmdClearHistory")}
                        </button>
                    )}
                </div>
            )}

            {/* Footer — truthful single-conversation count */}
            <div className="mt-3 border-t pt-3" style={{ ...eyebrow, color: c.ink55, borderColor: c.hair }}>
                {t("cmdSessionsThread")}
            </div>
        </div>
    );
}

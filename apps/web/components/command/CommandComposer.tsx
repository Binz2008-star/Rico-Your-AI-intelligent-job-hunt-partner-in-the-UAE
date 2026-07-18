"use client";

/**
 * CommandComposer — PR 4a of the Atelier full-site migration program.
 *
 * Real Atelier design for the authenticated command input bar.
 * Renders inside WorkspaceShell (dark, variant="app"), consuming the
 * WorkspaceThemeContext palette so it always matches the surrounding shell.
 *
 * SCOPE: composer only (textarea, send button, attachment action, quota/
 * sign-up notices, hint line). Message bubbles, tool cards, empty state,
 * right rail, and mobile header are slices 4b–4e.
 *
 * ZERO behavior change: all handlers and state live in CommandPage and are
 * passed as props. The public/guest composer is left completely unchanged —
 * the Atelier surface is authenticated-only in slice 4a.
 *
 * Keyboard contract (all handled here):
 *  - Enter            → sends (unless IME composing or disabled)
 *  - Shift+Enter      → inserts newline
 *  - Ctrl/⌘+K        → focuses the textarea (global, via document listener)
 *  - Ctrl/⌘+J        → triggers onNewChat (global, via document listener)
 *  - Escape           → calls onCancel when thinking
 */

import type { TranslationKey } from "@/lib/translations";
import Link from "next/link";
import React, { useEffect, useRef } from "react";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";

export interface CommandComposerProps {
    /** Whether to show the Atelier authenticated surface (true) or the
     *  original public/guest surface (false). Slice 4a only migrates auth. */
    isAuthenticated: boolean;
    /** Whether the public sign-up CTA should be shown. */
    showSignUpCta: boolean;
    /** Current text content of the textarea. */
    input: string;
    /** Setter forwarded from CommandPage's useState. */
    onInputChange: (value: string) => void;
    /** Ref attached to the textarea so CommandPage can focus/resize it. */
    textareaRef: React.RefObject<HTMLTextAreaElement | null>;
    /** Ref attached to the hidden file input for CV uploads. */
    fileInputRef: React.RefObject<HTMLInputElement | null>;
    /** Whether a request is in flight (thinking). */
    thinking: boolean;
    /** Auth state. */
    chatAudience: "checking" | "authenticated" | "public";
    /** True when a PermissionRequestCard is blocking input. */
    hasPendingPermission: boolean;
    /** Remaining messages quota (null = unlimited / unknown). */
    messagesRemaining: number | null;
    /** Error from a CV upload attempt. */
    uploadError: string | null;
    /** Called on Enter (not Shift+Enter, not during IME). */
    onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
    /** Called when send button is clicked. */
    onSend: () => void;
    /** Called when cancel (✕) button is clicked. */
    onCancel: () => void;
    /** Called when a file is selected via the hidden input. */
    onCVUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
    /** Called when Ctrl+J is pressed (new chat). */
    onNewChat: () => void;
    /** Translation helper forwarded from CommandPage. */
    t: (key: TranslationKey) => string;
    /** Href for the sign-up CTA (public audience). */
    signupHref: string;
    /** Current language for RTL mirroring. */
    language: "en" | "ar";
}

export function CommandComposer({
    isAuthenticated,
    showSignUpCta,
    input,
    onInputChange,
    textareaRef,
    fileInputRef,
    thinking,
    chatAudience,
    hasPendingPermission,
    messagesRemaining,
    uploadError,
    onKeyDown,
    onSend,
    onCancel,
    onCVUpload,
    onNewChat,
    t,
    signupHref,
    language,
}: CommandComposerProps) {
    const c = useWorkspaceTheme();
    const isRTL = language === "ar";
    const isDisabled = chatAudience === "checking" || hasPendingPermission;
    const composingRef = useRef(false);

    /* ── Global keyboard shortcuts (Ctrl/⌘+K: focus · Ctrl/⌘+J: new chat) ── */
    useEffect(() => {
        function handleGlobal(e: KeyboardEvent) {
            const mod = e.ctrlKey || e.metaKey;
            if (!mod) return;
            /* Don't fire shortcuts when focus is inside a different input/textarea
               (other than our own composer textarea). */
            const active = document.activeElement;
            const isOtherEditable =
                active !== textareaRef.current &&
                (active instanceof HTMLInputElement ||
                    active instanceof HTMLTextAreaElement ||
                    (active instanceof HTMLElement && active.isContentEditable));
            if (isOtherEditable) return;

            if (e.key === "k" || e.key === "K") {
                e.preventDefault();
                textareaRef.current?.focus();
            } else if (e.key === "j" || e.key === "J") {
                e.preventDefault();
                onNewChat();
            }
        }
        document.addEventListener("keydown", handleGlobal);
        return () => document.removeEventListener("keydown", handleGlobal);
    }, [onNewChat, textareaRef]);

    /* ── Textarea keydown: Enter sends, Shift+Enter newline, IME guard ── */
    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Escape" && thinking) {
            e.preventDefault();
            onCancel();
            return;
        }
        if (e.key === "Enter" && !e.shiftKey) {
            if (composingRef.current) return; // IME composition in progress
            e.preventDefault();
            if (!isDisabled && !thinking && input.trim()) onSend();
            return;
        }
        // Delegate all other keys (including Shift+Enter) to the parent handler
        // for any additional logic CommandPage needs.
        onKeyDown(e);
    }

    /* ── Quota notice text ─────────────────────────────────────────────────── */
    let quotaText: string | null = null;
    if (messagesRemaining === 0) quotaText = t("cmdMsgLimitReached");
    else if (messagesRemaining === 1) quotaText = t("cmdMsgLimitOne");
    else if (messagesRemaining !== null && messagesRemaining <= 3)
        quotaText = (t("cmdMsgLimitFew") as string).replace("{n}", String(messagesRemaining));

    /* ── Send-disabled logic ──────────────────────────────────────────────── */
    const sendDisabled = isDisabled || thinking || !input.trim() || messagesRemaining === 0;

    /* ════════════════════════════════════════════════════════════════════════
     * AUTHENTICATED — Atelier surface
     * ════════════════════════════════════════════════════════════════════════ */
    if (isAuthenticated) {
        return (
            <div
                className="relative shrink-0 px-3 pt-2 sm:px-5 sm:pt-3 pb-[calc(0.75rem_+_env(safe-area-inset-bottom))]"
                data-testid="atelier-composer"
                dir={isRTL ? "rtl" : "ltr"}
            >
                {/* Gradient fade from the paper surface above the sticky composer
                    (Atelier spec). Route-scoped, decorative, non-interactive — the
                    transcript scrolls behind and dissolves into the paper. */}
                <div
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-0 bottom-full h-10"
                    style={{ background: `linear-gradient(to top, ${c.bg}, transparent)` }}
                    data-testid="composer-fade"
                />
                {/* Hidden file input */}
                <input
                    id="cv-file-upload"
                    ref={fileInputRef as React.RefObject<HTMLInputElement>}
                    type="file"
                    accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.webp,.gif,.bmp,.eml,.msg"
                    aria-label={t("cmdUploadCvAriaLabel")}
                    title={t("cmdUploadCvTitle")}
                    className="hidden"
                    onChange={onCVUpload}
                />

                {/* Notice slot — always same height to prevent layout shift */}
                <div
                    className="mb-2 min-h-[22px] text-center"
                    style={{ fontFamily: ATELIER_FONT.mono, fontSize: 11, letterSpacing: isRTL ? 0 : "0.06em" }}
                >
                    {uploadError ? (
                        <span
                            role="alert"
                            aria-live="polite"
                            style={{ color: c.red }}
                            data-testid="upload-error"
                        >
                            {uploadError}
                        </span>
                    ) : quotaText ? (
                        <span style={{ color: c.ink55 }} data-testid="quota-notice">
                            {quotaText}
                            {" · "}
                            <Link
                                href="/subscription"
                                style={{ color: c.red, textDecoration: "none" }}
                            >
                                {t("cmdUpgrade")}
                            </Link>
                        </span>
                    ) : null}
                </div>

                {/* Paper input container */}
                <div
                    className="atl-composer-surface flex items-end gap-2 rounded-2xl px-3 py-2.5 sm:px-4"
                    style={{
                        background: c.panel,
                        border: `1px solid ${c.hair}`,
                        boxShadow: `0 2px 12px rgba(0,0,0,0.18), 0 1px 3px rgba(0,0,0,0.12)`,
                        transition: "border-color .2s ease, box-shadow .25s ease",
                    }}
                >
                    {/* Attachment button (paperclip) */}
                    <label
                        htmlFor="cv-file-upload"
                        role="button"
                        aria-label={t("cmdUploadCvAriaLabel")}
                        title={t("cmdUploadCvTitle")}
                        className="atl-composer-attach flex-shrink-0 flex items-center justify-center rounded-lg cursor-pointer"
                        style={{
                            width: 32,
                            height: 32,
                            color: c.ink40,
                            background: "transparent",
                            marginBottom: 1,
                            transition: "color 0.15s ease",
                        }}
                        data-testid="attach-button"
                    >
                        <svg
                            width="17"
                            height="17"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.7"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                        >
                            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                        </svg>
                    </label>

                    {/* Textarea */}
                    <textarea
                        ref={textareaRef as React.RefObject<HTMLTextAreaElement>}
                        value={input}
                        rows={1}
                        placeholder={
                            chatAudience === "checking"
                                ? t("cmdPlaceholderChecking")
                                : t("cmdAtelierPlaceholder")
                        }
                        aria-label={t("cmdAtelierPlaceholder")}
                        aria-multiline="true"
                        disabled={isDisabled}
                        onCompositionStart={() => { composingRef.current = true; }}
                        onCompositionEnd={() => { composingRef.current = false; }}
                        onChange={(e) => {
                            onInputChange(e.target.value);
                            e.target.style.height = "auto";
                            e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                        }}
                        onKeyDown={handleKeyDown}
                        className="atl-composer-textarea flex-1 resize-none bg-transparent outline-none text-[15px] leading-relaxed"
                        style={{
                            color: c.ink,
                            fontFamily: ATELIER_FONT.body,
                            caretColor: c.red,
                            minHeight: 28,
                            maxHeight: 120,
                        }}
                        data-testid="composer-textarea"
                    />

                    {/* Send / Cancel button */}
                    {thinking ? (
                        <button
                            type="button"
                            onClick={onCancel}
                            aria-label={t("cmdCancelRequest")}
                            title={t("cmdCancelRequest")}
                            className="atl-composer-cancel flex-shrink-0 flex items-center justify-center rounded-full"
                            style={{
                                width: 32,
                                height: 32,
                                background: c.red,
                                color: c.panel,
                                border: "none",
                                cursor: "pointer",
                                marginBottom: 1,
                                transition: "opacity 0.15s ease",
                            }}
                            data-testid="cancel-button"
                        >
                            <svg
                                width="13"
                                height="13"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                strokeLinecap="round"
                                aria-hidden="true"
                            >
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    ) : (
                        <button
                            type="button"
                            onClick={() => { if (!sendDisabled) onSend(); }}
                            disabled={sendDisabled}
                            aria-label={t("send")}
                            title={t("send")}
                            className="atl-composer-send flex-shrink-0 flex items-center justify-center rounded-full"
                            style={{
                                width: 32,
                                height: 32,
                                background: sendDisabled ? c.track : c.red,
                                color: sendDisabled ? c.ink40 : c.panel,
                                border: "none",
                                cursor: sendDisabled ? "default" : "pointer",
                                marginBottom: 1,
                                transition: "background 0.15s ease, color 0.15s ease",
                                opacity: sendDisabled ? 0.5 : 1,
                            }}
                            data-testid="send-button"
                        >
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden="true"
                            >
                                <line x1="22" y1="2" x2="11" y2="13" />
                                <polygon points="22 2 15 22 11 13 2 9 22 2" />
                            </svg>
                        </button>
                    )}
                </div>

                {/* Hint line — ink70, not ink40: on the light workspace paper the
                    hint must clear WCAG 4.5:1 (e2e command-composer-stability). */}
                <div
                    className="mt-2 text-center"
                    style={{
                        fontFamily: ATELIER_FONT.mono,
                        fontSize: 10,
                        letterSpacing: isRTL ? 0 : "0.12em",
                        color: c.ink70,
                    }}
                    aria-hidden="true"
                    data-testid="composer-hint"
                >
                    {t("cmdAtelierHint")}
                </div>

                {/* Scoped hover/focus styles */}
                <style dangerouslySetInnerHTML={{ __html: `
                    [data-testid="atelier-composer"] .atl-composer-attach:hover { color: ${c.red} !important; }
                    [data-testid="atelier-composer"] .atl-composer-textarea::placeholder { color: ${c.ink40}; }
                    [data-testid="atelier-composer"] .atl-composer-textarea:focus { outline: none; }
                    [data-testid="atelier-composer"] .atl-composer-send:not(:disabled):hover { opacity: 0.85 !important; transform: translateY(-1px); }
                    [data-testid="atelier-composer"] .atl-composer-send:not(:disabled):active { transform: scale(0.94); }
                    [data-testid="atelier-composer"] .atl-composer-send { transition: opacity .15s ease, transform .15s ease, background-color .15s ease; }
                    [data-testid="atelier-composer"] .atl-composer-cancel:hover { opacity: 0.85 !important; }
                    [data-testid="atelier-composer"] .atl-composer-cancel:active { transform: scale(0.94); }
                    /* Focus glow — the writing surface answers with the route accent. */
                    [data-testid="atelier-composer"] .atl-composer-surface:focus-within {
                        border-color: ${c.red}66 !important;
                        box-shadow: 0 0 0 3px ${c.red}1f, 0 2px 12px rgba(0,0,0,0.18), 0 1px 3px rgba(0,0,0,0.12) !important;
                    }
                    @media (prefers-reduced-motion: reduce) {
                        [data-testid="atelier-composer"] .atl-composer-send:not(:disabled):hover,
                        [data-testid="atelier-composer"] .atl-composer-send:not(:disabled):active,
                        [data-testid="atelier-composer"] .atl-composer-cancel:active { transform: none; }
                    }
                ` }} />
            </div>
        );
    }

    /* ════════════════════════════════════════════════════════════════════════
     * PUBLIC / CHECKING — original surface, unchanged (slice 4a scope)
     * ════════════════════════════════════════════════════════════════════════ */
    return (
        <div
            className="shrink-0 px-2 pt-3 sm:px-4 pb-[calc(1rem+env(safe-area-inset-bottom))]"
            data-testid="public-composer"
        >
            {/* Hidden file input */}
            <input
                id="cv-file-upload"
                ref={fileInputRef as React.RefObject<HTMLInputElement>}
                type="file"
                accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.webp,.gif,.bmp,.eml,.msg"
                aria-label="Upload document"
                title="Upload document"
                className="hidden"
                onChange={onCVUpload}
            />

            {/* Dynamic notices */}
            <div className="mb-2 min-h-[22px] text-center text-xs">
                {uploadError && (
                    <span
                        role="alert"
                        aria-live="polite"
                        className="text-destructive"
                        data-testid="upload-error"
                    >
                        {uploadError}
                    </span>
                )}
                {!uploadError && quotaText && (
                    <span className="text-text-muted" data-testid="quota-notice">
                        {quotaText}
                        {" · "}
                        <Link href="/subscription" className="text-gold hover:underline">
                            {t("cmdUpgrade")}
                        </Link>
                    </span>
                )}
                {!uploadError && !quotaText && showSignUpCta && (
                    <span className="text-text-muted" data-testid="signup-cta">
                        {t("cmdSignUpCta")}
                        {" "}
                        <Link href={signupHref} className="font-semibold text-gold hover:underline">
                            {t("cmdSignUpFree")}
                        </Link>
                    </span>
                )}
            </div>

            {/* Input row */}
            <div className="relative flex items-end gap-2 rounded-2xl border border-border-subtle bg-surface px-3 py-2.5 shadow-sm focus-within:border-border-strong sm:px-4">
                {/* Attachment label */}
                <label
                    htmlFor="cv-file-upload"
                    role="button"
                    aria-label={t("cmdUploadCvAriaLabel")}
                    title={t("cmdUploadCvTitle")}
                    className="mb-[3px] flex h-8 w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface-elevated hover:text-text-primary"
                    data-testid="attach-button"
                >
                    <svg
                        width="17"
                        height="17"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                    >
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                    </svg>
                </label>

                {/* Text input */}
                <div className="relative flex-1">
                    <textarea
                        ref={textareaRef as React.RefObject<HTMLTextAreaElement>}
                        value={input}
                        onChange={(e) => {
                            onInputChange(e.target.value);
                            e.target.style.height = "auto";
                            e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                        }}
                        onKeyDown={onKeyDown}
                        rows={1}
                        placeholder={
                            chatAudience === "checking"
                                ? t("cmdPlaceholderChecking")
                                : t("cmdPlaceholderReady")
                        }
                        aria-label={t("cmdPlaceholderReady")}
                        aria-multiline="true"
                        disabled={isDisabled}
                        className="w-full resize-none bg-transparent text-[15px] leading-relaxed text-text-primary outline-none placeholder:text-text-tertiary disabled:cursor-not-allowed"
                        style={{ minHeight: 28, maxHeight: 120 }}
                        data-testid="composer-textarea"
                    />
                </div>

                {/* Send / Cancel */}
                {thinking ? (
                    <button
                        type="button"
                        onClick={onCancel}
                        aria-label={t("cmdCancelRequest")}
                        title={t("cmdCancelRequest")}
                        className="mb-[3px] flex h-8 w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-full bg-destructive/90 text-white transition-opacity hover:opacity-80"
                        data-testid="cancel-button"
                    >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                ) : (
                    <button
                        type="button"
                        onClick={() => { if (!sendDisabled) onSend(); }}
                        disabled={sendDisabled}
                        aria-label={t("send")}
                        title={t("send")}
                        className="mb-[3px] flex h-8 w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-full bg-gold text-[#0a0a1a] shadow-[0_2px_8px_rgba(245,166,35,0.35)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
                        data-testid="send-button"
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <line x1="22" y1="2" x2="11" y2="13" />
                            <polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    </button>
                )}
            </div>

            {/* Hint line */}
            <div className="mt-1.5 text-center text-[11px] text-text-tertiary" aria-hidden="true" data-testid="composer-hint">
                {t("cmdHint")}
            </div>
        </div>
    );
}

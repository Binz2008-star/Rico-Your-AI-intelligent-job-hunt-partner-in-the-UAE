"use client";

/**
 * CommandComposer — PR 4 of the Atelier full-site migration program.
 *
 * Extracts the input bar (textarea, send/cancel buttons, CV-upload trigger,
 * quota/sign-up notices, and the hint line) from the monolithic
 * apps/web/app/command/page.tsx into a self-contained presentational component.
 *
 * ZERO behavior change: all handlers and state live in CommandPage and are
 * passed as props. The JSX inside is byte-for-byte identical to what was
 * inlined in page.tsx — no class, aria, or logic alterations.
 */

import type { TranslationKey } from "@/lib/translations";
import Link from "next/link";
import React from "react";

export interface CommandComposerProps {
    /** Whether the public sign-up CTA should be shown (caller checks message count). */
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
    /** Called on Enter (not Shift+Enter). */
    onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
    /** Called when send button is clicked. */
    onSend: () => void;
    /** Called when cancel (✕) button is clicked. */
    onCancel: () => void;
    /** Called when a file is selected via the hidden input. */
    onCVUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
    /** Translation helper forwarded from CommandPage. */
    t: (key: TranslationKey) => string;
    /** Href for the sign-up CTA (public audience). */
    signupHref: string;
}

export function CommandComposer({
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
    t,
    signupHref,
}: CommandComposerProps) {
    return (
        <div
            className={`shrink-0 px-2 pt-3 sm:px-4 ${chatAudience === "authenticated"
                ? "pb-[calc(56px+1rem+env(safe-area-inset-bottom))] md:pb-[calc(1rem+env(safe-area-inset-bottom))]"
                : "pb-[calc(1rem+env(safe-area-inset-bottom))]"
                }`}
        >
            {/* Hidden file input for CV upload */}
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

            {/* Dynamic notices use an always-present slot, preventing quota,
                upload, or sign-up messages from moving the composer. */}
            <div className="relative min-h-10" aria-live="polite">
                <div className="absolute inset-x-0 bottom-2 space-y-2">
                    {showSignUpCta && (
                        <div className="flex items-center justify-between gap-3 px-1">
                            <p className="text-[11px] text-text-muted">{t("cmdSignUpCta")}</p>
                            <Link
                                href={signupHref}
                                className="text-[11px] px-3 py-1 rounded-lg bg-gold/10 border border-gold/25 text-gold hover:bg-gold/18 transition-colors shrink-0 font-medium cursor-pointer"
                            >
                                {t("cmdSignUpFree")}
                            </Link>
                        </div>
                    )}
                    {uploadError && (
                        <p className="text-center text-[11px] text-rico-red" role="alert">
                            {uploadError}
                        </p>
                    )}
                    {messagesRemaining !== null &&
                        messagesRemaining <= 10 &&
                        chatAudience === "authenticated" && (
                            <div
                                className="flex items-center justify-between gap-3 rounded-xl border border-amber-500/25 bg-amber-500/8 px-3 py-2"
                                role="status"
                            >
                                <p className="text-[11px] text-amber-400">
                                    {messagesRemaining === 0
                                        ? t("cmdMsgLimitReached")
                                        : messagesRemaining === 1
                                            ? t("cmdMsgLimitOne")
                                            : t("cmdMsgLimitFew").replace("{n}", String(messagesRemaining))}
                                </p>
                                <Link
                                    href="/subscription"
                                    className="shrink-0 text-[11px] font-medium text-amber-400 underline underline-offset-2 hover:text-amber-300 transition-colors"
                                >
                                    {t("cmdUpgrade")}
                                </Link>
                            </div>
                        )}
                </div>
            </div>

            {/* Composer row */}
            <div className="flex items-end gap-2 rounded-2xl border border-border-soft bg-surface-elevated/95 p-1.5 shadow-xl shadow-black/10 backdrop-blur-md transition-[border-color,box-shadow] focus-within:border-gold/30 focus-within:shadow-[0_0_0_3px_rgba(245,166,35,0.07),0_8px_32px_rgba(0,0,0,0.12)]">
                {/* CV upload button — label triggers the hidden file input natively,
                    avoiding the programmatic .click() which some mobile browsers block. */}
                <label
                    htmlFor={
                        thinking || chatAudience === "checking" || hasPendingPermission
                            ? undefined
                            : "cv-file-upload"
                    }
                    role="button"
                    tabIndex={
                        thinking || chatAudience === "checking" || hasPendingPermission ? -1 : 0
                    }
                    aria-disabled={thinking || chatAudience === "checking" || hasPendingPermission}
                    title={t("cmdUploadCvTitle")}
                    aria-label={t("cmdUploadCvAriaLabel")}
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-text-secondary transition-colors rico-focus-strong ${thinking || chatAudience === "checking" || hasPendingPermission
                        ? "opacity-30 pointer-events-none cursor-default"
                        : "cursor-pointer hover:bg-surface-subtle hover:text-rico-text"
                        }`}
                >
                    <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
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
                        // Not disabled during thinking — the cancel button handles
                        // abort; keeping textarea active lets users read/edit the
                        // queued text while waiting.  Enter while thinking is a no-op
                        // (sendingRef guard) so accidental sends are prevented.
                        disabled={chatAudience === "checking" || hasPendingPermission}
                        rows={1}
                        aria-label="Message Rico"
                        aria-describedby="command-input-hint"
                        placeholder={
                            hasPendingPermission
                                ? "Approve or cancel the request above to continue"
                                : chatAudience === "checking"
                                    ? t("cmdPlaceholderChecking")
                                    : t("cmdPlaceholderReady")
                        }
                        className="max-h-[120px] w-full resize-none rounded-xl border-0 bg-transparent py-3 pe-12 ps-3 text-[16px] sm:text-sm text-rico-text placeholder:text-text-muted outline-none transition-all"
                    />
                    {/* Cancel button — replaces the send button while a request is in
                        flight (BUG #7). Clicking aborts the active AbortController,
                        resets all in-progress UI state, and appends a "cancelled"
                        message so the user knows the request was stopped cleanly.
                        The send icon is shown when idle; the ✕ stop icon when thinking. */}
                    {thinking ? (
                        <button
                            type="button"
                            onClick={onCancel}
                            className="absolute bottom-1.5 end-1.5 top-1.5 flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl bg-rico-red/90 text-white transition-colors hover:bg-rico-red rico-focus-strong"
                            aria-label={t("cmdCancelRequest")}
                            title={t("cmdCancelRequest")}
                        >
                            {/* ✕ stop icon */}
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden="true"
                            >
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    ) : (
                        <button
                            type="button"
                            onClick={onSend}
                            disabled={chatAudience === "checking" || hasPendingPermission || !input.trim()}
                            className="absolute bottom-1.5 end-1.5 top-1.5 flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl bg-gold text-[#0a0a1a] transition-colors hover:bg-gold-hover disabled:opacity-30 disabled:grayscale rico-focus-strong"
                            aria-label={t("send")}
                        >
                            <svg
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden="true"
                            >
                                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                            </svg>
                        </button>
                    )}
                </div>
            </div>
            <p
                id="command-input-hint"
                className="mt-2 min-h-4 text-center text-[10px] text-text-secondary"
            >
                {t("cmdHint")}
            </p>
        </div>
    );
}

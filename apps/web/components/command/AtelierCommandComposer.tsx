"use client";

/**
 * AtelierCommandComposer — Step 2 / slice 4a of the Atelier full-site migration.
 *
 * Presentation-only composer for the AUTHENTICATED /command surface, applied
 * to-the-letter from the owner-approved rico-chat-page reference (2026-07-14):
 * an editorial paper/ink composer — sharp `rounded-[4px]` corners, a hairline
 * rule that darkens to ink on focus, a paperclip attach action, an INK ArrowUp
 * send button (bordered, lifts on hover), a bordered Stop button with label
 * while streaming, and a two-part hint row (keyboard shortcuts · live char count).
 *
 * Colors resolve from `useWorkspaceTheme()`, so it renders the reference's light
 * paper in the light island and a coherent ink-on-dark in the current dark
 * /command island — one system, both themes.
 *
 * The page owns all chat behavior. This component holds NO chat state: value,
 * send, cancel, disabled/canSend gates, the attachment input, and the placeholder
 * are passed in. Its only interaction logic is the composer keyboard contract —
 * Enter (or ⌘/Ctrl+Enter) sends, Shift+Enter newlines, IME composition never
 * sends — expressed purely by calling `onSend`.
 *
 * Attachment stays a native <label htmlFor> pointing at the page's hidden
 * <input id={attachInputId}> — deliberately NOT a programmatic .click(), which
 * some mobile browsers block (the one deviation from the reference's preview-only
 * button, to preserve the live mobile CV-upload flow).
 */

import React, { useEffect, useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";

export interface AtelierCommandComposerProps {
    value: string;
    onValueChange: (value: string) => void;
    onSend: () => void;
    onCancel: () => void;
    thinking: boolean;
    inputDisabled: boolean;
    canSend: boolean;
    placeholder: string;
    textareaRef: React.RefObject<HTMLTextAreaElement>;
    attachInputId: string;
    attachDisabled: boolean;
    attachTitle: string;
    attachAriaLabel: string;
    sendAriaLabel: string;
    cancelAriaLabel: string;
}

const MAX_TEXTAREA_HEIGHT = 120;

// Uppercase mono hint fragment; Arabic keeps the body face and drops the wide
// tracking that would shred connected script (mirrors the atelier Mono rule).
function hintStyle(isAr: boolean, color: string): React.CSSProperties {
    return isAr
        ? { fontFamily: ATELIER_FONT.body, fontSize: 11, color }
        : { fontFamily: ATELIER_FONT.mono, fontSize: 11, letterSpacing: "0.14em", color };
}

export function AtelierCommandComposer({
    value,
    onValueChange,
    onSend,
    onCancel,
    thinking,
    inputDisabled,
    canSend,
    placeholder,
    textareaRef,
    attachInputId,
    attachDisabled,
    attachTitle,
    attachAriaLabel,
    sendAriaLabel,
    cancelAriaLabel,
}: AtelierCommandComposerProps) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const isAr = language === "ar";
    const [focused, setFocused] = useState(false);
    // Platform-correct modifier label; default Ctrl for SSR, ⌘ on Apple at runtime.
    const [modKey, setModKey] = useState("Ctrl");
    useEffect(() => {
        if (typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform || "")) {
            setModKey("⌘");
        }
    }, []);

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        // ⌘/Ctrl+Enter always sends; plain Enter sends unless Shift (newline) or
        // mid-IME-composition (Arabic/CJK) — never send while composing.
        if (
            (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ||
            (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing)
        ) {
            e.preventDefault();
            onSend();
        }
    }

    const chars = value.trim().length;
    const hint = isAr
        ? `Enter للإرسال · ${modKey}+K للتركيز · ${modKey}+J جديد`
        : `Enter to send · ${modKey}+K focus · ${modKey}+J new`;
    const stopLabel = isAr ? "إيقاف" : "Stop";

    return (
        <div>
            <div
                data-testid="atelier-command-composer"
                className="group relative flex items-end gap-2 rounded-[4px] px-3 py-2.5 transition-colors"
                style={{
                    background: c.panel,
                    border: `1px solid ${focused ? c.ink : c.hair}`,
                    boxShadow: focused ? `0 0 0 3px ${c.activeBg}` : "none",
                }}
            >
                {/* Attachment — native label→#{attachInputId} trigger (mobile-safe). */}
                <label
                    htmlFor={attachDisabled ? undefined : attachInputId}
                    role="button"
                    tabIndex={attachDisabled ? -1 : 0}
                    aria-disabled={attachDisabled}
                    aria-label={attachAriaLabel}
                    title={attachTitle}
                    data-testid="composer-attach"
                    className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[4px] transition-colors rico-focus-strong"
                    style={{
                        color: c.ink40,
                        border: "1px solid transparent",
                        cursor: attachDisabled ? "default" : "pointer",
                        opacity: attachDisabled ? 0.4 : 1,
                        pointerEvents: attachDisabled ? "none" : undefined,
                    }}
                >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                    </svg>
                </label>

                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(e) => {
                        onValueChange(e.target.value);
                        e.target.style.height = "auto";
                        e.target.style.height = `${Math.min(e.target.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
                    }}
                    onKeyDown={handleKeyDown}
                    onFocus={() => setFocused(true)}
                    onBlur={() => setFocused(false)}
                    disabled={inputDisabled}
                    rows={1}
                    aria-label="Message Rico"
                    aria-describedby="command-input-hint"
                    placeholder={placeholder}
                    className="min-h-[28px] min-w-0 flex-1 resize-none border-0 bg-transparent text-[15px] leading-relaxed outline-none sm:text-sm"
                    style={{ color: c.ink, maxHeight: MAX_TEXTAREA_HEIGHT, fontFamily: ATELIER_FONT.body }}
                />

                {thinking ? (
                    <button
                        type="button"
                        onClick={onCancel}
                        aria-label={cancelAriaLabel}
                        title={`${cancelAriaLabel} · Esc`}
                        data-testid="composer-cancel"
                        className="inline-flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-[4px] px-3 text-[12.5px] transition-colors rico-focus-strong"
                        style={{ background: c.panel, border: `1px solid ${c.ink}`, color: c.ink, fontFamily: ATELIER_FONT.body }}
                    >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="1" /></svg>
                        {stopLabel}
                    </button>
                ) : (
                    <button
                        type="button"
                        onClick={onSend}
                        disabled={!canSend}
                        aria-label={sendAriaLabel}
                        title={`${sendAriaLabel} · ${modKey}+↵`}
                        data-testid="composer-send"
                        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[4px] transition-all rico-focus-strong"
                        style={{
                            background: c.ink,
                            border: `1px solid ${c.ink}`,
                            color: c.bg,
                            opacity: canSend ? 1 : 0.3,
                            cursor: canSend ? "pointer" : "not-allowed",
                        }}
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <line x1="12" y1="19" x2="12" y2="5" />
                            <polyline points="5 12 12 5 19 12" />
                        </svg>
                    </button>
                )}
            </div>

            <div id="command-input-hint" className="mt-2 flex items-center justify-between gap-2 px-1">
                <span className="truncate uppercase" style={hintStyle(isAr, c.ink40)}>{hint}</span>
                <span className="shrink-0 uppercase" style={hintStyle(isAr, c.ink40)}>
                    {chars > 0 ? `${chars} ${isAr ? "حرف" : "chars"}` : ""}
                </span>
            </div>
        </div>
    );
}

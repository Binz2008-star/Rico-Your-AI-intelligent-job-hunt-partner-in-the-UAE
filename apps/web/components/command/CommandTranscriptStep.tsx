"use client";

/**
 * CommandTranscriptStep — slice C2 of the Command Obsidian program.
 *
 * Canonical transcript presentation for ONE real message on the
 * AUTHENTICATED surface: mono gutter label (YOU / RICO / RUN / CHECK / FAIL)
 * + the canonical body treatment. The message's inner content (markdown,
 * captions, cards, action chips, copy/retry rows) is passed through as
 * children UNCHANGED — card restyles are C4/C5. The public/guest surface
 * delegates verbatim to the pre-C2 CommandMessageRow.
 *
 * Truthfulness: CHECK/FAIL progress rows render only from real
 * `agentic_ui.progress` items (realProgressRows); the streaming caret renders
 * only while the real SSE stream is appending; the `stopped` row exists only
 * when the user really stopped a reply (partial content preserved above it).
 */

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import {
    classifyMessage,
    realProgressRows,
    type TranscriptMessageLike,
    type TranscriptRowKind,
} from "@/components/command/CommandEventAdapter";
import { CommandMessageRow } from "@/components/command/CommandMessages";
import { RicoReply, RicoThinking, RicoUserBubble } from "@/components/command/RicoReply";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation, type TranslationKey } from "@/lib/translations";
import React from "react";

const GUTTER_KEY: Record<Exclude<TranscriptRowKind, "card">, TranslationKey> = {
    you: "cmdGutterYou",
    rico: "cmdGutterRico",
    fail: "cmdGutterFail",
    stopped: "cmdGutterRico",
};

export function TranscriptGutter({
    label,
    hot = false,
    ink = false,
}: {
    label: string;
    hot?: boolean;
    ink?: boolean;
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    return (
        <span
            className="min-w-[56px] shrink-0 select-none pt-[5px]"
            style={{
                fontFamily: ATELIER_FONT.mono,
                fontSize: 10,
                textTransform: "uppercase",
                letterSpacing: language === "ar" ? "0.04em" : "0.2em",
                color: hot ? c.red : ink ? c.ink : c.ink55,
            }}
            aria-hidden="true"
        >
            {label}
        </span>
    );
}

/** Blinking block caret — rendered only while a real stream is appending. */
export function StreamingCaret() {
    const c = useWorkspaceTheme();
    return (
        <span
            data-testid="transcript-streaming-caret"
            aria-hidden="true"
            className="ms-0.5 inline-block h-[1.05em] w-[7px] translate-y-[3px] animate-pulse"
            style={{ background: c.ink }}
        />
    );
}

export function CommandTranscriptStep({
    authenticated,
    message,
    isFirstInGroup,
    isStructured,
    canRegenerate = false,
    onRegenerate,
    skipEntranceAnimation = false,
    children,
}: {
    authenticated: boolean;
    message: TranscriptMessageLike;
    isFirstInGroup: boolean;
    isStructured: boolean;
    /** Slice C3: this is the last assistant text turn AND there is a real
     *  user prompt to resend — shows RicoReply's Regenerate ghost action. */
    canRegenerate?: boolean;
    /** Reuses the page's existing send/retry path (never a new endpoint). */
    onRegenerate?: () => void;
    /** True for a message that arrived via bulk history hydration (initial
     *  load or session switch) rather than a live send/stream — suppresses
     *  the entrance animation so historical rows don't replay fade/slide-in
     *  on every mount. */
    skipEntranceAnimation?: boolean;
    children: React.ReactNode;
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const isAr = language === "ar";
    const entranceClass = skipEntranceAnimation ? "" : "animate-in fade-in motion-reduce:animate-none";

    if (!authenticated) {
        /* Public/guest surface — pre-C2 presentation, byte-identical. */
        return (
            <CommandMessageRow
                authenticated={false}
                role={message.role}
                isFirstInGroup={isFirstInGroup}
                isStructured={isStructured}
                skipEntranceAnimation={skipEntranceAnimation}
            >
                {children}
            </CommandMessageRow>
        );
    }

    const kind = classifyMessage(message);
    const progress = realProgressRows(message);

    /* Real progress rows (agentic_ui.progress) — CHECK/RUN/FAIL, API-sent only. */
    const progressRows = progress.length > 0 && (
        <div className="flex flex-col gap-1" data-testid="transcript-progress">
            {progress.map((p) => (
                <div key={p.id} className="flex items-start gap-4">
                    <TranscriptGutter
                        label={
                            p.status === "complete"
                                ? t("cmdGutterCheck")
                                : p.status === "failed"
                                    ? t("cmdGutterFail")
                                    : t("cmdGutterRun")
                        }
                        hot={p.status === "running" || p.status === "failed"}
                    />
                    <span
                        className="min-w-0 flex-1"
                        style={{
                            fontFamily: ATELIER_FONT.mono,
                            fontSize: 11,
                            textTransform: "uppercase",
                            letterSpacing: language === "ar" ? "0.02em" : "0.16em",
                            color: p.status === "complete" ? c.ink55 : c.ink70,
                            textDecoration: p.status === "complete" ? "line-through" : "none",
                        }}
                    >
                        {p.label}
                    </span>
                </div>
            ))}
        </div>
    );

    if (kind === "you") {
        /* Atelier editorial user turn (C3): a compact dark ink bubble,
           end-aligned. The user turn text is always plain (the page wraps
           `message.text` in a div for `children`), so we render the string
           directly through the bubble primitive. */
        return (
            <div
                data-testid="transcript-you-row"
                className={`${isFirstInGroup ? "mt-6" : "mt-2"} ${entranceClass}`}
            >
                <RicoUserBubble text={message.text ?? ""} />
            </div>
        );
    }

    if (kind === "stopped") {
        /* Truthful stopped row (C2). Restyled to the editorial serif-italic
           muted treatment with the same hairline left rail as RicoReply /
           RicoThinking; behavior + testid + children (stopped copy + Retry)
           are unchanged. */
        return (
            <div
                data-testid="transcript-stopped-row"
                className={`relative ps-3 ${isFirstInGroup ? "mt-5" : "mt-2"}`}
            >
                <span
                    aria-hidden="true"
                    className="absolute inset-y-1 start-0 w-px"
                    style={{ background: `linear-gradient(to bottom, ${c.ink55}, ${c.ink40}, transparent)` }}
                />
                <div dir="auto" className="serif-italic min-w-0 text-[13.5px] leading-relaxed" style={{ color: c.ink55 }}>
                    {children}
                </div>
            </div>
        );
    }

    if (kind === "fail") {
        return (
            <div
                data-testid="transcript-fail-row"
                className={`flex items-start gap-4 ${isFirstInGroup ? "mt-5" : "mt-2"}`}
            >
                <TranscriptGutter label={t("cmdGutterFail")} hot />
                <div
                    dir="auto"
                    className="min-w-0 flex-1 break-words ps-3 text-[14px] leading-relaxed"
                    style={{ color: c.ink, borderInlineStart: `2px solid ${c.red}99` }}
                >
                    {children}
                </div>
            </div>
        );
    }

    if (kind === "rico") {
        /* Atelier editorial plain-text reply (C3): serif prose with a hairline
           left rail, a blink caret while a real stream appends, and ghost
           Copy / Regenerate once settled. The page suppresses its inline
           markdown + copy/retry row for this case, so RicoReply owns the text
           and Copy. Any non-text extras a plain turn may still carry (e.g.
           options/help buttons) arrive through `children` and render below the
           prose. Real CHECK/RUN progress rows are preserved above it. */
        return (
            <div className={`flex flex-col gap-2 ${isFirstInGroup ? "mt-6" : "mt-2"}`}>
                {progressRows}
                <div data-testid="transcript-rico-row" className={entranceClass}>
                    <RicoReply
                        text={message.text ?? ""}
                        streaming={message.streaming === true}
                        canRegenerate={canRegenerate}
                        onRegenerate={onRegenerate}
                        isAr={isAr}
                    />
                    {children}
                </div>
            </div>
        );
    }

    /* Card turns keep their existing inner presentation (4c/4d) untouched
       behind the RICO gutter; card restyles are their own slice scope. */
    return (
        <div className={`flex flex-col gap-2 ${isFirstInGroup ? "mt-5" : "mt-2"}`}>
            {progressRows}
            <div
                data-testid="transcript-card-row"
                className={`flex items-start gap-4 ${entranceClass}`}
            >
                <TranscriptGutter label={t("cmdGutterRico")} hot={message.streaming === true} />
                <div
                    dir="auto"
                    className={`min-w-0 flex-1 break-words text-start ${isStructured ? "rounded-xl p-3 text-[13px]" : "text-[14.5px]"} leading-relaxed`}
                    style={{
                        color: c.ink,
                        fontFamily: ATELIER_FONT.body,
                        ...(isStructured ? { background: c.panel, border: `1px solid ${c.hair}` } : null),
                    }}
                >
                    {children}
                    {message.streaming === true && <StreamingCaret />}
                </div>
            </div>
        </div>
    );
}

/** The live working row — real state only: an active operationState renders a
 *  RUN row with its safe label; plain thinking renders the Atelier serif-italic
 *  "Thinking…" shimmer (C3). Rendered by the page only while `thinking` is true. */
export function TranscriptWorkingRow({
    operationMessage,
}: {
    operationMessage: string | null | undefined;
    /** Accepted for call-site compatibility; the plain-thinking state now
     *  self-labels via RicoThinking's role="status" "Thinking…" text, so no
     *  separate sr-only fallback is rendered (it would double-announce). */
    fallback?: string;
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const t = useTranslation(language);
    const label = operationMessage?.trim();

    if (label) {
        return (
            <div data-testid="transcript-run-row" className="mt-2 flex items-start gap-4" role="status">
                <TranscriptGutter label={t("cmdGutterRun")} hot />
                <span
                    className="min-w-0 flex-1"
                    style={{
                        fontFamily: ATELIER_FONT.mono,
                        fontSize: 11.5,
                        textTransform: "uppercase",
                        letterSpacing: language === "ar" ? "0.02em" : "0.16em",
                        color: c.ink70,
                    }}
                >
                    {label}
                    <span className="ms-1.5 inline-flex gap-1" aria-hidden="true">
                        {[0, 150, 300].map((d) => (
                            <span
                                key={d}
                                className="inline-block h-1 w-1 animate-bounce rounded-full"
                                style={{ background: c.red, animationDelay: `${d}ms`, animationDuration: "900ms" }}
                            />
                        ))}
                    </span>
                </span>
            </div>
        );
    }

    /* Submitted, no operation label yet → the Atelier serif-italic "Thinking…"
       shimmer (C3), replacing the old block-cursor waiting state. Keeps the
       transcript-waiting-row testid; RicoThinking's role="status" carries the
       accessible announcement. */
    return (
        <div data-testid="transcript-waiting-row" className="mt-2">
            <RicoThinking isAr={language === "ar"} />
        </div>
    );
}

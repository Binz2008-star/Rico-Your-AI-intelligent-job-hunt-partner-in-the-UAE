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
    children,
}: {
    authenticated: boolean;
    message: TranscriptMessageLike;
    isFirstInGroup: boolean;
    isStructured: boolean;
    children: React.ReactNode;
}) {
    const c = useWorkspaceTheme();
    const { language } = useLanguage();
    const t = useTranslation(language);

    if (!authenticated) {
        /* Public/guest surface — pre-C2 presentation, byte-identical. */
        return (
            <CommandMessageRow
                authenticated={false}
                role={message.role}
                isFirstInGroup={isFirstInGroup}
                isStructured={isStructured}
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
        return (
            <div
                data-testid="transcript-you-row"
                className={`flex items-start gap-4 ${isFirstInGroup ? "mt-6" : "mt-2"} animate-in fade-in motion-reduce:animate-none`}
            >
                <TranscriptGutter label={t("cmdGutterYou")} ink />
                <div
                    dir="auto"
                    className="min-w-0 flex-1 break-words whitespace-pre-wrap text-[21px] leading-[1.3] tracking-tight"
                    style={{ color: c.ink, fontFamily: ATELIER_FONT.serif, fontWeight: 500 }}
                >
                    {children}
                </div>
            </div>
        );
    }

    if (kind === "stopped") {
        return (
            <div
                data-testid="transcript-stopped-row"
                className={`flex items-start gap-4 ${isFirstInGroup ? "mt-5" : "mt-2"}`}
            >
                <TranscriptGutter label={t("cmdGutterRico")} />
                <div dir="auto" className="min-w-0 flex-1 text-[13.5px] italic leading-relaxed" style={{ color: c.ink55 }}>
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

    /* rico text turns and card turns share the row shell; cards keep their
       existing inner presentation (4c/4d) untouched. */
    return (
        <div className={`flex flex-col gap-2 ${isFirstInGroup ? "mt-5" : "mt-2"}`}>
            {progressRows}
            <div
                data-testid={kind === "card" ? "transcript-card-row" : "transcript-rico-row"}
                className="flex items-start gap-4 animate-in fade-in motion-reduce:animate-none"
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
 *  RUN row with its safe label; plain thinking renders the canonical waiting
 *  cursor. Rendered by the page only while `thinking` is true. */
export function TranscriptWorkingRow({
    operationMessage,
    fallback,
}: {
    operationMessage: string | null | undefined;
    fallback: string;
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

    return (
        <div data-testid="transcript-waiting-row" className="mt-2 flex items-center gap-4 opacity-60" role="status">
            <TranscriptGutter label="…" />
            <span aria-hidden="true" className="inline-block h-[16px] w-[7px] animate-pulse" style={{ background: c.ink }} />
            <span className="sr-only">{fallback}</span>
        </div>
    );
}

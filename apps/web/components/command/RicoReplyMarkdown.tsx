"use client";

/**
 * RicoReplyMarkdown — the structured answer renderer for the authenticated
 * /command reply (owner directive 2026-07-17: a visible, substantial upgrade to
 * how Rico's answers are presented — hierarchy, not just motion).
 *
 * Safe by construction: react-markdown with `skipHtml` (raw HTML is dropped, so
 * no XSS surface) + remark-gfm (lists, tables, strikethrough, autolinks). Links
 * are additionally sanitized to http/https/mailto and open with
 * rel="noopener noreferrer". No HTML is ever dangerouslySet.
 *
 * Styling maps every element onto the route-scoped Atelier token layer
 * (text-ink / text-ink-mute / border-rule / text-sun / bg-paper-2 …, backed by
 * CSS vars in CommandObsidianShell), so light and "Atelier at Night" both work
 * with no per-element theming. Prose is serif; code is mono. All horizontal
 * indentation and the blockquote rule use logical properties (ps-* / border-s)
 * so Arabic RTL mirrors correctly. Wide content (code blocks, tables) scrolls
 * inside its own container so the transcript never scrolls sideways.
 *
 * This does NOT change Rico's response content, prompts, routing, or any API —
 * it only renders the same answer string the transcript already receives.
 */

import React from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/** Only allow schemes that can't execute script; anything else is inert. */
function safeHref(href: string | undefined): string | undefined {
    if (!href) return undefined;
    const h = href.trim();
    if (/^(https?:|mailto:)/i.test(h)) return h;
    if (h.startsWith("/") || h.startsWith("#")) return h; // in-app relative / anchor
    return undefined;
}

const components: Components = {
    p: ({ children }) => (
        <p dir="auto" className="serif my-3 text-[16.5px] leading-[1.7] text-ink first:mt-0 last:mb-0 [overflow-wrap:anywhere]">
            {children}
        </p>
    ),
    h1: ({ children }) => (
        <h1 dir="auto" className="serif mb-2 mt-6 text-[1.5rem] font-semibold leading-tight tracking-[-0.01em] text-ink first:mt-0">
            {children}
        </h1>
    ),
    h2: ({ children }) => (
        <h2 dir="auto" className="serif mb-2 mt-6 text-[1.25rem] font-semibold leading-tight tracking-[-0.01em] text-ink first:mt-0">
            {children}
        </h2>
    ),
    h3: ({ children }) => (
        <h3 dir="auto" className="serif mb-1.5 mt-5 text-[1.08rem] font-semibold leading-snug text-ink first:mt-0">
            {children}
        </h3>
    ),
    h4: ({ children }) => (
        <h4 dir="auto" className="serif mb-1.5 mt-4 text-[1rem] font-semibold text-ink first:mt-0">
            {children}
        </h4>
    ),
    strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    del: ({ children }) => <del className="text-ink-mute line-through">{children}</del>,
    ul: ({ children }) => (
        <ul dir="auto" className="my-3 list-disc space-y-1.5 ps-6 marker:text-ink-mute">{children}</ul>
    ),
    ol: ({ children }) => (
        <ol dir="auto" className="my-3 list-decimal space-y-1.5 ps-6 marker:text-ink-mute">{children}</ol>
    ),
    li: ({ children }) => (
        <li className="serif ps-1 text-[16px] leading-[1.65] text-ink [overflow-wrap:anywhere]">{children}</li>
    ),
    blockquote: ({ children }) => (
        <blockquote dir="auto" className="serif my-3 border-s-2 border-sun/50 ps-4 text-[16px] italic leading-[1.6] text-ink-soft">
            {children}
        </blockquote>
    ),
    a: ({ href, children }) => {
        const safe = safeHref(href);
        if (!safe) return <span className="text-ink">{children}</span>;
        return (
            <a
                href={safe}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-sun underline decoration-sun/40 underline-offset-2 transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:decoration-sun [overflow-wrap:anywhere]"
            >
                {children}
            </a>
        );
    },
    code: ({ inline, className, children, ...props }: React.ComponentPropsWithoutRef<"code"> & { inline?: boolean }) => {
        if (inline) {
            return (
                <code
                    dir="ltr"
                    className="rounded-[4px] border border-rule bg-paper-2 px-1.5 py-0.5 font-mono text-[13px] text-ink"
                    {...props}
                >
                    {children}
                </code>
            );
        }
        return (
            <code dir="ltr" className={`block font-mono text-[13px] leading-[1.6] text-ink ${className ?? ""}`} {...props}>
                {children}
            </code>
        );
    },
    pre: ({ children }) => (
        <pre dir="ltr" className="my-3 overflow-x-auto rounded-[8px] border border-rule bg-paper-2 p-3.5 text-[13px] leading-[1.6]">
            {children}
        </pre>
    ),
    hr: () => <hr className="my-5 border-rule" />,
    table: ({ children }) => (
        <div className="my-3 overflow-x-auto rounded-[8px] border border-rule">
            <table className="w-full border-collapse text-[14px]">{children}</table>
        </div>
    ),
    thead: ({ children }) => <thead className="bg-paper-2">{children}</thead>,
    tbody: ({ children }) => <tbody>{children}</tbody>,
    tr: ({ children }) => <tr className="border-b border-rule last:border-b-0">{children}</tr>,
    th: ({ children }) => (
        <th dir="auto" className="border-e border-rule px-3 py-2 text-start font-semibold text-ink last:border-e-0">{children}</th>
    ),
    td: ({ children }) => (
        <td dir="auto" className="border-e border-rule px-3 py-2 text-ink-soft last:border-e-0 [overflow-wrap:anywhere]">{children}</td>
    ),
};

/**
 * Memoized on the raw string: while streaming, each new partial re-parses once
 * (react-markdown is pure), and a settled message never re-parses on unrelated
 * transcript re-renders (composer keystrokes, sibling messages).
 */
export const RicoReplyMarkdown = React.memo(function RicoReplyMarkdown({ text }: { text: string }) {
    return (
        <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={components}>
            {text}
        </ReactMarkdown>
    );
});

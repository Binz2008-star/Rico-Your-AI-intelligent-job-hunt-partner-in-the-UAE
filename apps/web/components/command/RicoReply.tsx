"use client";

/**
 * RicoReply — slice C3 of the Command Obsidian program (Atelier editorial
 * reply rendering; owner-approved spec 2026-07-16).
 *
 * The three reply primitives for the AUTHENTICATED /command transcript:
 *   • RicoUserBubble — the user's turn as a compact dark ink bubble, end-aligned.
 *   • RicoReply      — Rico's plain-text answer as serif prose with a hairline
 *                      left rail, a blink caret while a real stream appends, and
 *                      ghost Copy / Regenerate actions once settled.
 *   • RicoThinking   — the submitted-but-no-text-yet state: serif-italic
 *                      "Thinking…" with a pulsing dot.
 *
 * Colors come from the route-scoped Atelier token layer (bg-ink / text-paper /
 * border-rule / text-ink-mute …), which CommandObsidianShell backs with CSS
 * vars derived from the JS palette, so light and "Atelier at Night" both work
 * with no per-component theming. RTL is handled with logical utilities
 * (ps-3 / start-0 / ms-0.5) so the rail sits on the leading edge in Arabic.
 *
 * Deliberate deviations from the raw spec, both required to preserve the C2
 * contract / a11y:
 *   1. The streaming caret carries data-testid="transcript-streaming-caret"
 *      (the no-regression suite asserts it).
 *   2. The prose container is an aria-live="polite" region so screen readers
 *      receive the streamed answer.
 */

import { Check, Copy, RotateCcw } from "lucide-react";
import { useCallback, useState } from "react";

export function RicoReply({ text, streaming = false, canRegenerate = false, onRegenerate, isAr = false }:
  { text: string; streaming?: boolean; canRegenerate?: boolean; onRegenerate?: () => void; isAr?: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => { void navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }, [text]);
  if (!text) return null; // empty pending → nothing (RicoThinking handles the shimmer)
  return (
    <div className="relative ps-3" aria-live="polite" aria-busy={streaming || undefined}>
      <span aria-hidden className="absolute inset-y-1 start-0 w-px bg-gradient-to-b from-ink/50 via-ink/20 to-transparent" />
      <p dir="auto" className="serif whitespace-pre-wrap text-[16.5px] leading-[1.65] text-ink">
        {text}
        {streaming && <span data-testid="transcript-streaming-caret" aria-hidden className="animate-caret motion-reduce:animate-none ms-0.5 inline-block h-[1em] w-[0.55ch] translate-y-[0.15em] bg-ink align-baseline" />}
      </p>
      {!streaming && (
        <div className="mt-2 flex gap-1">
          <button type="button" onClick={copy} className="inline-flex h-7 items-center gap-1 rounded-sm border border-transparent px-2 text-[11px] uppercase tracking-[0.14em] text-ink-mute transition-colors hover:border-rule hover:text-ink focus-visible:border-rule focus-visible:text-ink focus-visible:outline-none">
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}{copied ? (isAr ? "نُسخ" : "Copied") : (isAr ? "نسخ" : "Copy")}
          </button>
          {canRegenerate && (
            <button type="button" onClick={onRegenerate} className="inline-flex h-7 items-center gap-1 rounded-sm border border-transparent px-2 text-[11px] uppercase tracking-[0.14em] text-ink-mute transition-colors hover:border-rule hover:text-ink focus-visible:border-rule focus-visible:text-ink focus-visible:outline-none">
              <RotateCcw className="h-3 w-3" />{isAr ? "إعادة توليد" : "Regenerate"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function RicoUserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div dir="auto" className="max-w-[78%] rounded-sm border border-ink bg-ink px-3 py-2 text-[14.5px] text-paper">{text}</div>
    </div>
  );
}

export function RicoThinking({ isAr = false }: { isAr?: boolean }) {
  return (
    <div className="relative ps-3" role="status" aria-live="polite">
      <span aria-hidden className="absolute inset-y-1 start-0 w-px bg-gradient-to-b from-ink/50 via-ink/20 to-transparent" />
      <p className="serif-italic text-[16.5px] leading-[1.65] text-ink-mute">{isAr ? "أُفكّر…" : "Thinking…"}
        <span aria-hidden className="ms-1 inline-block h-1 w-1 -translate-y-px rounded-full bg-ink-mute animate-pulse motion-reduce:animate-none align-middle" /></p>
    </div>
  );
}

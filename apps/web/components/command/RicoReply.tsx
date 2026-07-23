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

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Check, Copy, RotateCcw } from "lucide-react";
import { useCallback, useState } from "react";
import { RicoReplyMarkdown } from "./RicoReplyMarkdown";
import { useThinkingStages } from "./thinkingStages";

export function RicoReply({ text, streaming = false, canRegenerate = false, onRegenerate, isAr = false }:
  { text: string; streaming?: boolean; canRegenerate?: boolean; onRegenerate?: () => void; isAr?: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => { void navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }, [text]);
  if (!text) return null; // empty pending → nothing (RicoThinking handles the shimmer)
  // No entrance animation of its own: CommandTranscriptStep's row wrapper
  // (`animate-in fade-in`) already handles entrance. A second, independent
  // `animate-fade-up` here used to compound with it (message settle ~400ms
  // vs. the ~150-220ms this is meant to feel like) — one animation, not two.
  return (
    <div className="relative ps-3.5" aria-live="polite" aria-busy={streaming || undefined}>
      <span aria-hidden className="absolute inset-y-1 start-0 w-px animate-rail-draw motion-reduce:animate-none bg-gradient-to-b from-ink/50 via-ink/20 to-transparent" />
      {/* Structured answer: the same reply string rendered as safe markdown —
          headings, lists, links, code, blockquotes, hierarchy — at a controlled
          reading width. Markdown renders during streaming too (not a plain→
          formatted swap at settle), so long answers don't jump on completion.
          The `serif` class here keeps the transcript's prose contract. */}
      <div dir="auto" className="serif max-w-[70ch] text-[16px] leading-[1.75] text-ink">
        <RicoReplyMarkdown text={text} />
        {streaming && <span data-testid="transcript-streaming-caret" aria-hidden className="animate-caret motion-reduce:animate-none ms-0.5 inline-block h-[1em] w-[0.55ch] translate-y-[0.15em] bg-ink align-baseline" />}
      </div>
      {!streaming && (
        <div className="mt-3 flex gap-1.5 animate-fade-up motion-reduce:animate-none">
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
  // Same reasoning as RicoReply above: the transcript row wrapper already
  // provides entrance — no second animation on this component's own root.
  return (
    <div className="flex justify-end">
      <div
        dir="auto"
        className="max-w-[74%] rounded-[14px] bg-ink px-[18px] py-[10px] text-[14px] leading-[1.55] text-paper"
        style={{
          fontFamily: ATELIER_FONT.body,
          fontWeight: 450,
          letterSpacing: "-0.01em",
        }}
      >
        {text}
      </div>
    </div>
  );
}

/**
 * RicoThinking — the reasoning state, upgraded to the modern-AI signature:
 * a sun-red→ink gradient sweeps through the serif-italic label
 * (`.atl-reason-shimmer`, defined in CommandObsidianShell's scoped CSS with a
 * prefers-reduced-motion solid-color fallback) followed by three cascading
 * dots. Same role/aria contract as before.
 */
export function RicoThinking({ isAr = false }: { isAr?: boolean }) {
  /* The label evolves through honest stages while the wait grows (6s / 16s
     boundaries), each swap entering with the stage-in blur-crossfade so it
     reads as one thought developing. The elapsed stamp (aria-hidden, so the
     polite region never announces per-second ticks) appears once the wait is
     long enough to be worth explaining. */
  const { label, stage, elapsed } = useThinkingStages(isAr);
  return (
    <div className="relative ps-3.5 animate-fade-up motion-reduce:animate-none" role="status" aria-live="polite">
      <span aria-hidden className="absolute inset-y-1 start-0 w-px animate-rail-draw motion-reduce:animate-none bg-gradient-to-b from-ink/50 via-ink/20 to-transparent" />
      <p className="serif-italic text-[16px] leading-[1.75] text-ink-mute">
        <span key={stage} className="atl-reason-shimmer inline-block animate-stage-in motion-reduce:animate-none">{label}</span>
        <span aria-hidden className="ms-1.5 inline-flex items-baseline gap-[3px] align-middle">
          <span className="inline-block h-1 w-1 rounded-full bg-ink-mute animate-dot-cascade motion-reduce:animate-pulse" />
          <span className="inline-block h-1 w-1 rounded-full bg-ink-mute animate-dot-cascade motion-reduce:animate-pulse" style={{ animationDelay: "0.15s" }} />
          <span className="inline-block h-1 w-1 rounded-full bg-ink-mute animate-dot-cascade motion-reduce:animate-pulse" style={{ animationDelay: "0.3s" }} />
        </span>
        {elapsed >= 5 && (
          <span aria-hidden className="ms-2 inline-block align-middle text-[11px] not-italic tabular-nums text-ink-mute/80" style={{ fontFamily: "var(--font-mono), ui-monospace, monospace" }}>
            {elapsed}s
          </span>
        )}
      </p>
    </div>
  );
}

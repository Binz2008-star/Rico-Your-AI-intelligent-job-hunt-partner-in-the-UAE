"use client";

/**
 * HeroSection.tsx
 *
 * Perplexity-style interactive command hero.
 *
 * Rules enforced here:
 * - All output is driven by DEMO_TURNS / DEMO_PROMPTS from demo-data.ts.
 * - Zero network calls (no fetch, no useEffect with API).
 * - No fake testimonials, logos, or live counters.
 * - Every role card is labeled "Sample output" or "Demo only".
 * - Static, deterministic: server-render safe.
 */

import { useState } from "react";
import {
  DEMO_TURNS,
  DEMO_PROMPTS,
  DemoTurn,
  DemoRole,
} from "./demo-data";

/* ── Types ─────────────────────────────────────────────────────────────────── */
interface ConversationState {
  turns: DemoTurn[];
  activePromptIndex: number;
}

/* ── Sub-components ────────────────────────────────────────────────────────── */

function RoleCard({ card }: { card: DemoRole }) {
  return (
    <div
      className="mt-3 rounded-[18px] border border-white/10 bg-white/[0.04] overflow-hidden"
      aria-label="Sample output — role match card"
    >
      {/* Card header */}
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-white/8 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
        <span>Role match</span>
        <span className="inline-flex items-center gap-1.5 text-[#21d19a]/80">
          <span
            aria-hidden="true"
            className="w-1.5 h-1.5 rounded-full bg-[#21d19a] animate-pulse"
          />
          Sample output
        </span>
      </div>

      {/* Card body */}
      <div className="p-4 grid gap-3">
        {/* Title + score row */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold leading-tight tracking-tight">
              {card.title}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">{card.location}</p>
          </div>
          <div
            aria-label={`Fit score ${card.fitScore}%`}
            className="shrink-0 w-[62px] h-[62px] rounded-full border border-[#21d19a]/20 bg-[#21d19a]/10 grid place-items-center text-[#37ddB0] font-extrabold text-sm"
          >
            {card.fitScore}%
          </div>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5" aria-label="Fit dimensions">
          {card.tags.map((t) => (
            <span
              key={t.label}
              className="px-2.5 py-1 rounded-full border border-white/10 bg-white/[0.04] text-[11px] text-muted-foreground"
            >
              {t.label}
            </span>
          ))}
        </div>

        {/* Reasons */}
        <ul className="grid gap-1.5">
          {card.reasons.map((r) => (
            <li
              key={r}
              className="relative pl-4 text-sm text-muted-foreground before:content-[''] before:absolute before:left-0 before:top-[0.55rem] before:w-1.5 before:h-1.5 before:rounded-full before:bg-[#21d19a]"
            >
              {r}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function MessageBubble({ turn }: { turn: DemoTurn }) {
  return (
    <article
      className={`grid gap-1.5 max-w-[92%] ${
        turn.role === "user" ? "ml-auto justify-items-end" : "mr-auto justify-items-start"
      }`}
    >
      <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        {turn.role === "user" ? "You" : "Rico"}
      </span>
      <div
        className={`rounded-[20px] px-4 py-3 border text-sm leading-relaxed ${
          turn.role === "user"
            ? "border-[#21d19a]/24 bg-[#21d19a]/[0.14] text-foreground"
            : "border-white/10 bg-white/[0.04] text-foreground"
        }`}
      >
        {turn.text}
        {turn.card && <RoleCard card={turn.card} />}
      </div>
    </article>
  );
}

/* ── Main component ────────────────────────────────────────────────────────── */

export default function HeroSection() {
  const [state, setState] = useState<ConversationState>({
    turns: DEMO_TURNS,
    activePromptIndex: 0,
  });

  const [inputValue, setInputValue] = useState<string>(DEMO_PROMPTS[0]);

  function handlePromptChip(idx: number) {
    setInputValue(DEMO_PROMPTS[idx]);
    setState((prev) => ({ ...prev, activePromptIndex: idx }));
  }

  /** All responses are static — no network call. */
  function handleSubmit() {
    const userText = inputValue.trim();
    if (!userText) return;

    // Find a matching demo turn or fall back to a generic static response
    const matchedAiTurn: DemoTurn =
      DEMO_TURNS.find((t) => t.role === "rico") ??
      {
        role: "rico",
        text:
          "This is a demo — sign in to let Rico analyse your actual CV and surface personalised matches.",
      };

    setState({
      turns: [
        { role: "user", text: userText },
        matchedAiTurn,
      ],
      activePromptIndex: state.activePromptIndex,
    });
  }

  return (
    <section
      id="hero"
      aria-labelledby="hero-heading"
      className="relative py-16 md:py-24 overflow-hidden"
    >
      {/* Ambient glow — decorative only */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-0 left-0 right-0 h-[600px] bg-gradient-to-b from-[#21d19a]/[0.07] to-transparent"
      />

      <div className="container mx-auto px-4 max-w-[1120px]">
        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-8 lg:gap-16 items-center">

          {/* ── Left: copy ─────────────────────────────────────────────────── */}
          <div>
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#21d19a]/20 bg-[#21d19a]/[0.08] text-[#37ddB0] text-[11px] font-bold uppercase tracking-widest mb-5"
            >
              AI Career OS · UAE-first
            </div>

            <h1
              id="hero-heading"
              className="font-display text-[clamp(2.7rem,5vw,5.5rem)] leading-[0.97] tracking-[-0.05em] max-w-[11ch]"
            >
              Your CV becomes the command centre.
            </h1>

            <p className="mt-5 text-muted-foreground text-lg max-w-[58ch]">
              Rico reads your experience, explains fit, organises the hunt, and
              keeps you in control — in English and Arabic.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="/sign-up"
                className="inline-flex items-center justify-center min-h-[44px] px-5 rounded-full bg-gradient-to-b from-[#37ddB0] to-[#21d19a] text-[#04110d] font-semibold text-sm shadow-[0_12px_30px_rgba(33,209,154,0.22)] hover:-translate-y-px transition-transform"
              >
                Start free
              </a>
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center min-h-[44px] px-5 rounded-full border border-white/10 bg-white/[0.04] text-sm font-semibold hover:-translate-y-px transition-transform"
              >
                See the workflow
              </a>
            </div>

            {/* Trust pills — static, no live counters */}
            <div className="mt-8 flex flex-wrap gap-3" aria-label="Trust markers">
              {[
                "English + Arabic",
                "You approve every action",
                "Built for the UAE market",
              ].map((pill) => (
                <span
                  key={pill}
                  className="inline-flex items-center px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.04] text-sm text-muted-foreground"
                >
                  {pill}
                </span>
              ))}
            </div>
          </div>

          {/* ── Right: interactive console ──────────────────────────────────── */}
          <div className="relative">
            {/* Glow behind console */}
            <div
              aria-hidden="true"
              className="absolute inset-auto bottom-[6%] left-[12%] w-[60%] h-[30%] blur-[80px] bg-[#21d19a]/[0.14] pointer-events-none"
            />

            <div
              className="relative z-10 rounded-[28px] border border-white/10 bg-gradient-to-b from-white/[0.05] to-white/[0.02] shadow-[0_30px_90px_rgba(0,0,0,0.44)] overflow-hidden"
              aria-label="Rico demo console — Demo only"
            >
              {/* Topbar */}
              <div className="flex items-center justify-between gap-4 px-4 py-3.5 border-b border-white/8 bg-white/[0.03]">
                <div className="flex items-center gap-3">
                  <div className="flex gap-1.5" aria-hidden="true">
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="w-2.5 h-2.5 rounded-full bg-white/18" />
                    ))}
                  </div>
                  <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                    Rico / command
                  </span>
                </div>
                <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span
                    aria-hidden="true"
                    className="w-2 h-2 rounded-full bg-[#21d19a] animate-pulse"
                  />
                  Demo only
                </span>
              </div>

              {/* Conversation */}
              <div
                className="px-5 py-4 grid gap-4 min-h-[320px]"
                aria-live="polite"
                aria-label="Demo conversation"
              >
                {state.turns.map((turn, i) => (
                  <MessageBubble key={i} turn={turn} />
                ))}
              </div>

              {/* Composer */}
              <div className="px-4 pb-4 pt-0">
                {/* Prompt chips */}
                <div
                  className="flex flex-wrap gap-2 mb-3"
                  role="group"
                  aria-label="Sample prompts"
                >
                  {DEMO_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      aria-pressed={state.activePromptIndex === idx}
                      onClick={() => handlePromptChip(idx)}
                      className={`px-3 py-1.5 rounded-full border text-[11px] font-medium transition-colors ${
                        state.activePromptIndex === idx
                          ? "border-[#21d19a]/22 bg-[#21d19a]/[0.10] text-foreground"
                          : "border-white/10 bg-white/[0.04] text-muted-foreground hover:text-foreground hover:border-[#21d19a]/18"
                      }`}
                    >
                      {prompt.length > 44 ? prompt.slice(0, 41) + "…" : prompt}
                    </button>
                  ))}
                </div>

                {/* Input + send */}
                <div className="flex items-center gap-3">
                  <input
                    type="text"
                    aria-label="Demo prompt — no live data"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                    className="flex-1 min-h-[44px] rounded-[22px] border border-white/10 bg-white/[0.04] px-4 text-sm outline-none focus-visible:border-[#21d19a]/30"
                    placeholder="Ask Rico (demo — no live data)"
                  />
                  <button
                    type="button"
                    onClick={handleSubmit}
                    aria-label="Run demo analysis"
                    className="min-h-[44px] px-5 rounded-full bg-gradient-to-b from-[#37ddB0] to-[#21d19a] text-[#04110d] font-semibold text-sm hover:-translate-y-px transition-transform"
                  >
                    Analyse
                  </button>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}

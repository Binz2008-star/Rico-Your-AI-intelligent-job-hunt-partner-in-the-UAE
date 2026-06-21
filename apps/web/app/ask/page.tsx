"use client";

/**
 * /ask — Agentic Conversational UX demo (Phase 1: UI with mock data)
 *
 * Interaction model:
 *   1. Empty state: centered ask box + prompt chips
 *   2. Submit: thinking card appears, input slides to bottom
 *   3. Answer: structured card with reasoning + contextual actions
 *   4. Action: approval sheet (mobile bottom sheet / desktop inline)
 *   5. After approval: receipt card, actions disappear
 *
 * No real backend calls yet. Mock data drives the demo.
 * Wire to real API in Phase 3.
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { fetchMe } from "@/lib/api";
import { buildAuthHref } from "@/lib/redirect";
import { RicoAskInput } from "@/components/agentic/RicoAskInput";
import { PromptChips } from "@/components/agentic/PromptChips";
import { RicoThinkingCard } from "@/components/agentic/RicoThinkingCard";
import { RicoAnswerCard } from "@/components/agentic/RicoAnswerCard";
import { RicoStatusDot } from "@/components/agentic/RicoStatusDot";
import { ApprovalSheet } from "@/components/agentic/ApprovalSheet";
import { getMockAnswer, SUGGESTED_PROMPTS } from "@/components/agentic/mockData";
import type { AgenticAnswer, AgentStatus, ApprovalState, ContextualAction } from "@/components/agentic/types";

// ── Receipt shown after a successful action ──────────────────────────────────

function ReceiptCard({ label }: { label: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="
        inline-flex items-center gap-2
        px-3 py-1.5 rounded-xl
        border border-success/20 bg-success/8 text-success
        text-[13px] font-medium
      "
    >
      <span className="material-icons-round text-[14px]">check_circle</span>
      {label}
    </motion.div>
  );
}

// ── Empty state (centered hero) ───────────────────────────────────────────────

function EmptyState({
  value,
  onChange,
  onSubmit,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled: boolean;
}) {
  return (
    <motion.div
      key="empty"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col items-center justify-center min-h-[70vh] px-4 gap-8"
    >
      {/* Logo + greeting */}
      <div className="text-center space-y-3">
        <div className="relative mx-auto w-14 h-14 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-gold/8 animate-breathe" />
          <div className="absolute inset-2 rounded-full bg-gold/12 animate-breathe [animation-delay:0.4s]" />
          <span className="relative material-icons-round text-gold text-[28px]">auto_awesome</span>
        </div>
        <div>
          <h1 className="text-[22px] font-bold text-text-primary">
            What would you like to work on?
          </h1>
          <p className="text-[14px] text-text-muted mt-1">
            Rico is your AI career agent — ask anything about your job search.
          </p>
        </div>
      </div>

      {/* Input */}
      <div className="w-full max-w-2xl">
        <RicoAskInput
          value={value}
          onChange={onChange}
          onSubmit={onSubmit}
          disabled={disabled}
        />
      </div>

      {/* Prompt chips */}
      <PromptChips
        prompts={SUGGESTED_PROMPTS}
        onSelect={onChange}
        disabled={disabled}
      />
    </motion.div>
  );
}

// ── Main page component ───────────────────────────────────────────────────────

export default function AskPage() {
  const router = useRouter();
  const [authState, setAuthState] = useState<"checking" | "ready">("checking");
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<AgentStatus>("idle");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [answers, setAnswers] = useState<AgenticAnswer[]>([]);
  const [approval, setApproval] = useState<ApprovalState | null>(null);
  const [receipts, setReceipts] = useState<string[]>([]);

  const bottomRef = useRef<HTMLDivElement>(null);
  const hasAnswers = answers.length > 0;

  // Auth guard — redirect to /login?next=/ask if not authenticated
  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        if (!me.authenticated) {
          router.replace(buildAuthHref("/login", "/ask"));
          return;
        }
        setAuthState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        router.replace(buildAuthHref("/login", "/ask"));
      });
    return () => { cancelled = true; };
  }, [router]);

  // Scroll to bottom after new answers
  useEffect(() => {
    if (hasAnswers) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [answers.length, hasAnswers]);

  const handleSubmit = useCallback(async () => {
    const q = input.trim();
    if (!q || status === "thinking" || status === "responding") return;

    setInput("");
    setPendingQuestion(q);
    setStatus("thinking");

    try {
      const answer = await getMockAnswer(q);
      setAnswers((prev) => [...prev, answer]);
      setStatus("idle");
    } catch {
      setStatus("error");
    } finally {
      setPendingQuestion(null);
    }
  }, [input, status]);

  const handleAction = useCallback((action: ContextualAction, answer: AgenticAnswer) => {
    if (action.kind === "dismiss") return;

    if (action.requires_approval || action.kind === "approve") {
      setApproval({
        action,
        answer,
        expiresAt: new Date(Date.now() + 5 * 60 * 1000),
      });
      setStatus("waiting");
      return;
    }

    if (action.kind === "chat_continue") {
      const msg = (action.payload as { message?: string })?.message ?? action.label;
      setInput(msg);
      return;
    }

    if (action.kind === "navigate") {
      const href = (action.payload as { href?: string })?.href;
      if (href) window.location.href = href;
    }
  }, []);

  const handleApprove = useCallback((action: ContextualAction) => {
    setApproval(null);
    setStatus("acting");

    // Simulate execution
    setTimeout(() => {
      setReceipts((prev) => [...prev, action.label]);
      setStatus("idle");
    }, 800);
  }, []);

  const handleCancelApproval = useCallback(() => {
    setApproval(null);
    setStatus("idle");
  }, []);

  const isThinking = status === "thinking" || status === "responding";
  const isDisabled = isThinking || status === "acting" || status === "waiting";

  // Show minimal loader while session check is in flight
  if (authState === "checking") {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center command-dark-lock">
        <div className="relative w-10 h-10 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-gold/8 animate-breathe" />
          <div className="absolute inset-2 rounded-full bg-gold/12 animate-breathe [animation-delay:0.4s]" />
          <span className="relative material-icons-round text-gold text-[20px]">auto_awesome</span>
        </div>
      </div>
    );
  }

  return (
    <div className="
      min-h-screen bg-background
      command-dark-lock
      flex flex-col
    ">
      {/* Top bar */}
      <header className="
        sticky top-0 z-30
        px-4 py-3
        flex items-center justify-between
        border-b border-overlay/8
        bg-background/80 backdrop-blur-md
      ">
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-semibold text-text-primary">Ask Rico</span>
          <span className="hidden sm:inline-block text-[11px] text-text-muted border border-overlay/12 px-2 py-0.5 rounded-full">
            Preview
          </span>
        </div>
        <RicoStatusDot status={status} />
      </header>

      {/* Preview/Demo banner — Phase 1 prototype runs on mock data only */}
      <div
        role="status"
        aria-live="polite"
        className="
          px-4 py-2
          flex items-start gap-2
          border-b border-gold/20 bg-gold/8
          text-[12px] leading-snug text-text-primary
        "
      >
        <span className="material-icons-round text-gold text-[16px] shrink-0">science</span>
        <span>
          <strong className="font-semibold">Preview mode</strong> — this page currently uses sample data.
          No real jobs are searched, no applications are submitted, and nothing is sent externally.
        </span>
      </div>

      {/* Content area */}
      <main className="flex-1 flex flex-col">
        <AnimatePresence mode="wait">
          {!hasAnswers && !pendingQuestion ? (
            <EmptyState
              value={input}
              onChange={setInput}
              onSubmit={handleSubmit}
              disabled={isDisabled}
            />
          ) : (
            <motion.div
              key="conversation"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex-1 flex flex-col"
            >
              {/* Answer thread */}
              <div className="flex-1 px-4 py-6 space-y-4 overflow-y-auto">
                <AnimatePresence initial={false}>
                  {answers.map((answer, i) => (
                    <RicoAnswerCard
                      key={answer.id}
                      answer={answer}
                      isLatest={i === answers.length - 1 && !pendingQuestion}
                      onAction={(action) => handleAction(action, answer)}
                    />
                  ))}
                </AnimatePresence>

                {/* Thinking indicator */}
                <AnimatePresence>
                  {pendingQuestion && (
                    <RicoThinkingCard question={pendingQuestion} />
                  )}
                </AnimatePresence>

                {/* Receipts */}
                <AnimatePresence>
                  {receipts.map((label, i) => (
                    <ReceiptCard key={i} label={label} />
                  ))}
                </AnimatePresence>

                <div ref={bottomRef} className="h-4" />
              </div>

              {/* Sticky input at bottom (conversation mode) */}
              <div className="
                sticky bottom-0 z-20
                px-4 pt-2 pb-4
                bg-background/90 backdrop-blur-md
                border-t border-overlay/8
              ">
                {/* Approval sheet (desktop inline, above input) */}
                <div className="max-w-2xl mx-auto mb-3">
                  <ApprovalSheet
                    approval={approval}
                    onApprove={handleApprove}
                    onCancel={handleCancelApproval}
                  />
                </div>

                <RicoAskInput
                  value={input}
                  onChange={setInput}
                  onSubmit={handleSubmit}
                  disabled={isDisabled}
                  placeholder="Ask a follow-up…"
                  compact
                />

                {/* Chip hints (compact, horizontal scroll) */}
                {!isDisabled && !input && (
                  <div className="mt-2.5 overflow-x-auto flex gap-2 pb-0.5 max-w-2xl mx-auto no-scrollbar">
                    {SUGGESTED_PROMPTS.slice(0, 4).map((p) => (
                      <button
                        key={p}
                        onClick={() => setInput(p)}
                        className="
                          shrink-0 px-3 py-1 rounded-full text-[12px] font-medium whitespace-nowrap
                          border border-overlay/12 text-text-muted
                          hover:border-gold/30 hover:text-gold
                          transition-colors
                        "
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Mobile approval sheet (portal-style fixed overlay) */}
      <div className="sm:hidden">
        <ApprovalSheet
          approval={approval}
          onApprove={handleApprove}
          onCancel={handleCancelApproval}
        />
      </div>
    </div>
  );
}

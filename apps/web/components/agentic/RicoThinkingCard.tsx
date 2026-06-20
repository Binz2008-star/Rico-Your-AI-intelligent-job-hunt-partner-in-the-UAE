"use client";

import { motion } from "framer-motion";

interface RicoThinkingCardProps {
  question: string;
}

export function RicoThinkingCard({ question }: RicoThinkingCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3 }}
      className="
        w-full max-w-2xl mx-auto
        rounded-2xl border border-overlay/12
        bg-surface/60 backdrop-blur-sm
        px-5 py-4
      "
      aria-live="polite"
      aria-label="Rico is thinking"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 shrink-0 w-6 h-6 rounded-full bg-aura/20 flex items-center justify-center">
          <span className="material-icons-round text-aura text-[14px]">auto_awesome</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[12px] text-text-muted mb-1">You asked</p>
          <p className="text-[14px] text-text-secondary leading-snug line-clamp-2">{question}</p>
          <div className="mt-3 flex items-center gap-2">
            <ThinkingDots />
            <span className="text-[12px] text-text-muted">Rico is analyzing…</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function ThinkingDots() {
  return (
    <div className="flex gap-1" aria-hidden>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block w-1.5 h-1.5 rounded-full bg-aura"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.18 }}
        />
      ))}
    </div>
  );
}

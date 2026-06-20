"use client";

import { motion } from "framer-motion";

interface PromptChipsProps {
  prompts: string[];
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

export function PromptChips({ prompts, onSelect, disabled }: PromptChipsProps) {
  return (
    <div
      className="flex gap-2 flex-wrap justify-center max-w-2xl mx-auto px-4"
      role="list"
      aria-label="Suggested prompts"
    >
      {prompts.map((prompt, i) => (
        <motion.button
          key={prompt}
          role="listitem"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 * i, duration: 0.25 }}
          onClick={() => !disabled && onSelect(prompt)}
          disabled={disabled}
          className="
            px-3 py-1.5 rounded-full text-[13px] font-medium
            border border-overlay/12 bg-surface/60 backdrop-blur-sm
            text-text-secondary hover:text-gold hover:border-gold/40 hover:bg-gold/5
            transition-colors duration-150 select-none
            disabled:opacity-40 disabled:cursor-not-allowed
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50
          "
        >
          {prompt}
        </motion.button>
      ))}
    </div>
  );
}

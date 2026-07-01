"use client";

import { useRef, useEffect, KeyboardEvent } from "react";
import { motion } from "framer-motion";

interface RicoAskInputProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
  compact?: boolean;
}

export function RicoAskInput({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder = "What would you like to work on?",
  compact = false,
}: RicoAskInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = Math.min(ref.current.scrollHeight, 180) + "px";
    }
  }, [value]);

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) onSubmit();
    }
  }

  const canSubmit = value.trim().length > 0 && !disabled;

  return (
    <motion.div
      layout
      className={`
        relative w-full mx-auto
        border border-overlay/16 rounded-2xl
        bg-surface/80 backdrop-blur-md shadow-lg
        focus-within:border-gold/40 focus-within:shadow-gold/10
        transition-shadow duration-200
        ${compact ? "max-w-2xl" : "max-w-2xl"}
      `}
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKey}
        disabled={disabled}
        placeholder={placeholder}
        rows={compact ? 1 : 3}
        aria-label="Ask Rico"
        className="
          w-full resize-none bg-transparent
          px-5 py-4 pr-14 text-[15px] leading-relaxed
          text-text-primary placeholder:text-text-muted
          focus:outline-none rounded-2xl
          disabled:opacity-50
        "
      />

      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSubmit}
        aria-label="Send"
        className="
          absolute right-3 bottom-3
          flex items-center justify-center
          w-9 h-9 rounded-xl
          bg-gold text-void font-bold
          disabled:bg-overlay/20 disabled:text-text-muted disabled:cursor-not-allowed
          hover:enabled:bg-gold/90 active:enabled:scale-95
          transition-all duration-150
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/60
        "
      >
        <span className="material-icons-round text-[18px] leading-none">
          {disabled ? "hourglass_empty" : "arrow_upward"}
        </span>
      </button>

      <div className="px-5 pb-2.5 flex items-center justify-between">
        <span className="text-[11px] text-text-muted">
          Shift + Enter for new line
        </span>
        {value.length > 0 && (
          <span className="text-[11px] text-text-muted">{value.length}</span>
        )}
      </div>
    </motion.div>
  );
}

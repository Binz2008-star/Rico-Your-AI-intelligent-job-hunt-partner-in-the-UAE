"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { AgentStatus } from "./types";

const STATUS_CONFIG: Record<AgentStatus, { color: string; label: string; pulse: boolean }> = {
  idle:       { color: "bg-aura",    label: "Rico ready",              pulse: true  },
  thinking:   { color: "bg-gold",    label: "Rico is thinking…",       pulse: true  },
  responding: { color: "bg-gold",    label: "Rico is writing…",        pulse: true  },
  acting:     { color: "bg-amber-400", label: "Rico is working…",      pulse: true  },
  waiting:    { color: "bg-magenta", label: "Waiting for your approval", pulse: false },
  error:      { color: "bg-red-400", label: "Something went wrong",    pulse: true  },
};

export function RicoStatusDot({ status }: { status: AgentStatus }) {
  const cfg = STATUS_CONFIG[status];

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex h-2 w-2 shrink-0">
        {cfg.pulse && (
          <motion.span
            className={`absolute inline-flex h-full w-full rounded-full ${cfg.color} opacity-60`}
            animate={{ scale: [1, 2, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${cfg.color}`} />
      </div>
      <AnimatePresence mode="wait">
        <motion.span
          key={status}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.2 }}
          className="text-[11px] font-medium tracking-wide text-text-muted"
        >
          {cfg.label}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

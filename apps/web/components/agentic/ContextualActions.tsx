"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ContextualAction } from "./types";

interface ContextualActionsProps {
  actions: ContextualAction[];
  onAction: (action: ContextualAction) => void;
  disabled?: boolean;
}

export function ContextualActions({ actions, onAction, disabled }: ContextualActionsProps) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visible = actions.filter((a) => !dismissed.has(a.id));

  if (visible.length === 0) return null;

  function handleClick(action: ContextualAction) {
    if (action.kind === "dismiss") {
      setDismissed((prev) => new Set([...prev, action.id]));
    }
    onAction(action);
  }

  return (
    <div
      className="flex flex-wrap gap-2"
      role="group"
      aria-label="Suggested actions"
    >
      <AnimatePresence>
        {visible.map((action) => (
          <ActionChip
            key={action.id}
            action={action}
            onClick={() => handleClick(action)}
            disabled={disabled}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

function ActionChip({
  action,
  onClick,
  disabled,
}: {
  action: ContextualAction;
  onClick: () => void;
  disabled?: boolean;
}) {
  const isHighImpact = action.risk_class === "high" || action.risk_class === "critical";
  const needsApproval = action.requires_approval;
  const isDismiss = action.kind === "dismiss";

  return (
    <motion.button
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.15 } }}
      transition={{ duration: 0.2 }}
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={action.label}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[13px] font-medium",
        "border transition-all duration-150 select-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50",
        "disabled:opacity-40 disabled:cursor-not-allowed",
        isDismiss
          ? "border-overlay/12 text-text-muted hover:text-text-secondary hover:border-overlay/20"
          : isHighImpact
          ? "border-amber-500/40 bg-amber-500/5 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500/60"
          : needsApproval
          ? "border-gold/40 bg-gold/5 text-gold hover:bg-gold/10 hover:border-gold/60"
          : "border-overlay/16 bg-surface/60 text-text-secondary hover:text-gold hover:border-gold/30 hover:bg-gold/5",
      )}
    >
      <span className="material-icons-round text-[14px] leading-none">{action.icon}</span>
      {action.label}
      {needsApproval && !isDismiss && (
        <span className="material-icons-round text-[11px] leading-none opacity-60">lock</span>
      )}
    </motion.button>
  );
}

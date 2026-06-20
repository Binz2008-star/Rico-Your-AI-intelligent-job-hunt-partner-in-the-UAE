"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RiskBadge } from "./RiskBadge";
import type { ApprovalState, ContextualAction } from "./types";

interface ApprovalSheetProps {
  approval: ApprovalState | null;
  onApprove: (action: ContextualAction) => void;
  onCancel: () => void;
}

const RISK_DESCRIPTIONS: Record<string, string> = {
  safe:     "No side effects. Safe to proceed.",
  low:      "Creates a draft only. Nothing sent externally.",
  medium:   "Updates your profile or tracker. Reversible.",
  high:     "Sends or submits externally. Cannot be recalled.",
  critical: "Irreversible external action. Review carefully.",
};

const ICON_FOR_ACTION: Record<string, string> = {
  "Prepare application": "edit_note",
  "Save for later":      "bookmark",
  "Fix top gap":         "auto_fix_high",
  "Send follow-up":      "send",
};

export function ApprovalSheet({ approval, onApprove, onCancel }: ApprovalSheetProps) {
  const [secondsLeft, setSecondsLeft] = useState(300);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!approval) {
      setSecondsLeft(300);
      setConfirming(false);
      return;
    }
    const interval = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) { clearInterval(interval); return 0; }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [approval]);

  function formatTime(s: number) {
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }

  function handleApprove() {
    if (!approval || secondsLeft === 0) return;
    setConfirming(true);
    setTimeout(() => {
      onApprove(approval.action);
      setConfirming(false);
    }, 400);
  }

  const expired = secondsLeft === 0;
  const risk = approval?.action.risk_class ?? "safe";
  const isHigh = risk === "high" || risk === "critical";

  return (
    <AnimatePresence>
      {approval && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-void/60 backdrop-blur-sm z-40 sm:hidden"
            onClick={onCancel}
            aria-hidden
          />

          {/* Mobile bottom sheet */}
          <motion.div
            key="sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 26, stiffness: 300 }}
            className="
              fixed bottom-0 left-0 right-0 z-50
              sm:relative sm:bottom-auto sm:left-auto sm:right-auto sm:z-auto
              sm:animate-none sm:transform-none
            "
            role="dialog"
            aria-modal="true"
            aria-label="Approval required"
          >
            {/* Desktop inline card */}
            <div className="
              sm:w-full sm:max-w-2xl sm:mx-auto
              sm:rounded-2xl sm:border
              sm:border-overlay/16 sm:bg-surface/95 sm:backdrop-blur-md
            ">
              {/* Mobile sheet inner */}
              <div className="
                rounded-t-3xl border-t border-x border-overlay/16
                bg-surface-elevated backdrop-blur-md
                px-5 pb-8 pt-4
                sm:rounded-2xl sm:border sm:px-5 sm:pb-5 sm:pt-4
              ">
                {/* Drag handle (mobile only) */}
                <div className="w-10 h-1 rounded-full bg-overlay/20 mx-auto mb-5 sm:hidden" />

                {/* Header */}
                <div className="flex items-start gap-3 mb-4">
                  <div className={`
                    w-9 h-9 rounded-xl flex items-center justify-center shrink-0
                    ${isHigh ? "bg-amber-500/15" : "bg-gold/10"}
                  `}>
                    <span className={`material-icons-round text-[18px] ${isHigh ? "text-amber-400" : "text-gold"}`}>
                      {ICON_FOR_ACTION[approval.action.label] ?? "check_circle"}
                    </span>
                  </div>
                  <div>
                    <p className="text-[13px] text-text-muted mb-0.5">Rico wants to</p>
                    <h3 className="text-[15px] font-semibold text-text-primary leading-snug">
                      {approval.action.label}
                    </h3>
                  </div>
                  <RiskBadge risk={risk} />
                </div>

                {/* Risk description */}
                <p className="text-[13px] text-text-secondary leading-relaxed mb-4">
                  {RISK_DESCRIPTIONS[risk]}
                </p>

                {/* High risk warning */}
                {isHigh && (
                  <div className="flex items-start gap-2 rounded-xl bg-amber-500/10 border border-amber-500/20 px-3 py-2.5 mb-4">
                    <span className="material-icons-round text-amber-400 text-[16px] mt-0.5 shrink-0">warning</span>
                    <p className="text-[12px] text-amber-300 leading-snug">
                      This action affects an external system and cannot be undone once executed.
                    </p>
                  </div>
                )}

                {/* Expiry countdown */}
                {!expired ? (
                  <div className="flex items-center gap-2 mb-5">
                    <span className="text-[11px] text-text-muted">Approval expires in</span>
                    <span className="text-[12px] font-mono font-semibold text-gold tabular-nums">
                      {formatTime(secondsLeft)}
                    </span>
                    <div className="flex-1 h-0.5 bg-overlay/10 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gold/60 rounded-full"
                        initial={{ width: "100%" }}
                        animate={{ width: `${(secondsLeft / 300) * 100}%` }}
                        transition={{ duration: 1, ease: "linear" }}
                      />
                    </div>
                  </div>
                ) : (
                  <p className="text-[13px] text-red-400 mb-5">
                    This approval has expired.
                  </p>
                )}

                {/* CTAs */}
                <div className="flex flex-col gap-2 sm:flex-row sm:justify-end sm:gap-2">
                  <button
                    type="button"
                    onClick={onCancel}
                    className="
                      order-2 sm:order-1
                      px-4 py-2.5 rounded-xl text-[13px] font-medium
                      border border-overlay/16 text-text-secondary
                      hover:border-overlay/30 hover:text-text-primary
                      transition-colors
                    "
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={expired || confirming}
                    className="
                      order-1 sm:order-2
                      px-5 py-2.5 rounded-xl text-[13px] font-semibold
                      bg-gold text-void
                      hover:bg-gold/90 active:scale-95
                      disabled:opacity-40 disabled:cursor-not-allowed
                      transition-all duration-150
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/60
                    "
                  >
                    {confirming ? "Confirming…" : expired ? "Expired" : "Approve"}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

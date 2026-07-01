"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RiskBadge } from "./RiskBadge";
import { ContextualActions } from "./ContextualActions";
import type { AgenticAnswer, AnswerItem, ContextualAction, JobItem, AdvicePoint, ProfileGap } from "./types";

interface RicoAnswerCardProps {
  answer: AgenticAnswer;
  onAction: (action: ContextualAction) => void;
  isLatest?: boolean;
}

export function RicoAnswerCard({ answer, onAction, isLatest }: RicoAnswerCardProps) {
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const [actedIds, setActedIds] = useState<Set<string>>(new Set());

  function handleAction(action: ContextualAction) {
    if (action.kind !== "dismiss") {
      setActedIds((prev) => new Set([...prev, action.id]));
    }
    onAction(action);
  }

  const remainingActions = answer.actions.filter((a) => !actedIds.has(a.id));

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="
        w-full max-w-2xl mx-auto
        rounded-2xl border border-overlay/12
        bg-surface/70 backdrop-blur-sm
        overflow-hidden
      "
      aria-label={answer.title}
    >
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-overlay/8 flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 min-w-0">
          <AnswerTypeIcon type={answer.type} />
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-text-primary leading-snug">
              {answer.title}
            </h2>
            <p className="text-[13px] text-text-secondary mt-0.5 leading-snug">
              {answer.summary}
            </p>
          </div>
        </div>
        <div className="shrink-0 pt-0.5">
          <RiskBadge risk={answer.risk_class} />
        </div>
      </div>

      {/* Items */}
      {answer.items.length > 0 && (
        <div className="px-4 py-3 space-y-2.5">
          {answer.items.map((item, i) => (
            <AnswerItemRow key={i} item={item} />
          ))}
        </div>
      )}

      {/* Reasoning strip */}
      <div className="px-5 py-2 border-t border-overlay/8">
        <button
          type="button"
          onClick={() => setReasoningOpen((o) => !o)}
          className="flex items-center gap-1.5 text-[12px] text-text-muted hover:text-aura transition-colors"
          aria-expanded={reasoningOpen}
        >
          <span className="material-icons-round text-[13px]">lightbulb</span>
          Why Rico suggested this
          <span className="material-icons-round text-[13px] transition-transform duration-200"
            style={{ transform: reasoningOpen ? "rotate(180deg)" : "rotate(0deg)" }}>
            expand_more
          </span>
        </button>
        <AnimatePresence>
          {reasoningOpen && (
            <motion.p
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="text-[13px] text-aura/80 leading-relaxed mt-2 overflow-hidden"
            >
              {answer.reasoning}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Actions */}
      <AnimatePresence>
        {isLatest && remainingActions.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="px-5 pb-4 pt-1"
          >
            <ContextualActions actions={remainingActions} onAction={handleAction} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}

function AnswerTypeIcon({ type }: { type: AgenticAnswer["type"] }) {
  const icons: Record<string, { icon: string; color: string; bg: string }> = {
    job_recommendation: { icon: "work",        color: "text-gold",    bg: "bg-gold/10"    },
    career_advice:      { icon: "lightbulb",   color: "text-aura",    bg: "bg-aura/10"    },
    profile_analysis:   { icon: "person",      color: "text-cyan",    bg: "bg-cyan/10"    },
    application_status: { icon: "fact_check",  color: "text-success", bg: "bg-success/10" },
    action_complete:    { icon: "check_circle", color: "text-success", bg: "bg-success/10" },
    approval_required:  { icon: "lock",        color: "text-gold",    bg: "bg-gold/10"    },
  };
  const cfg = icons[type] ?? icons.career_advice;
  return (
    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${cfg.bg}`}>
      <span className={`material-icons-round text-[16px] ${cfg.color}`}>{cfg.icon}</span>
    </div>
  );
}

function AnswerItemRow({ item }: { item: AnswerItem }) {
  if (item.kind === "job") return <JobCard job={item.data} />;
  if (item.kind === "advice") return <AdviceRow advice={item.data} />;
  if (item.kind === "gap") return <GapRow gap={item.data} />;
  return null;
}

function JobCard({ job }: { job: JobItem }) {
  return (
    <div className="
      rounded-xl border border-overlay/12 bg-surface-elevated/60 px-4 py-3
      hover:border-gold/20 hover:bg-surface-elevated/80 transition-colors
    ">
      <div className="flex items-start justify-between gap-2 mb-1">
        <div>
          <p className="text-[14px] font-semibold text-text-primary leading-snug">{job.title}</p>
          <p className="text-[12px] text-text-secondary">{job.company} · {job.location}</p>
        </div>
        <MatchBadge pct={job.match_pct} />
      </div>
      {job.salary && (
        <p className="text-[12px] text-gold mt-1">{job.salary}</p>
      )}
      <p className="text-[12px] text-text-muted mt-1.5 leading-snug">{job.match_reason}</p>
      <p className="text-[11px] text-text-muted mt-1 opacity-60">{job.posted_ago}</p>
    </div>
  );
}

function MatchBadge({ pct }: { pct: number }) {
  const color = pct >= 90 ? "text-success bg-success/10" : pct >= 80 ? "text-gold bg-gold/10" : "text-cyan bg-cyan/10";
  return (
    <span className={`shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {pct}% match
    </span>
  );
}

function AdviceRow({ advice }: { advice: AdvicePoint }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-overlay/10 px-4 py-3 bg-surface-elevated/40">
      <span className="material-icons-round text-aura text-[18px] mt-0.5 shrink-0">{advice.icon}</span>
      <div>
        <p className="text-[14px] font-semibold text-text-primary">{advice.headline}</p>
        <p className="text-[13px] text-text-secondary leading-snug mt-0.5">{advice.detail}</p>
      </div>
    </div>
  );
}

function GapRow({ gap }: { gap: ProfileGap }) {
  return (
    <div className="rounded-xl border border-overlay/10 px-4 py-3 bg-surface-elevated/40">
      <div className="flex items-center gap-2 mb-1">
        <span className="material-icons-round text-gold text-[14px]">edit</span>
        <p className="text-[13px] font-semibold text-text-primary">{gap.field}</p>
      </div>
      {gap.current && (
        <p className="text-[12px] text-text-muted line-through mb-0.5">{gap.current}</p>
      )}
      <p className="text-[12px] text-gold leading-snug">{gap.suggested}</p>
    </div>
  );
}

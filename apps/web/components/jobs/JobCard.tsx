"use client";

import { Button } from "@/components/ui/Button";
import { ScoreBadge } from "@/components/ui/ScoreBadge";
import { cn } from "@/lib/utils";
import type { Job } from "@/types";
import { useMemo, useState } from "react";

interface JobCardProps {
  job: Job;
  onAction?: (jobId: string, action: string) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const LOGO_COLORS = [
  "from-cyan-500/20 to-cyan-400/10 text-cyan-200",
  "from-fuchsia-500/20 to-pink-400/10 text-pink-200",
  "from-violet-500/20 to-fuchsia-400/10 text-violet-200",
  "from-emerald-500/20 to-cyan-400/10 text-emerald-200",
  "from-amber-500/20 to-orange-400/10 text-amber-100",
];

const VERDICT_LABELS = {
  strong_fit: "Strong fit",
  worth_checking: "Worth checking",
  weak_fit: "Low alignment",
} as const;

const VERDICT_STYLES = {
  strong_fit: "bg-emerald-500/10 text-emerald-200 border-emerald-400/20",
  worth_checking: "bg-amber-500/10 text-amber-100 border-amber-400/20",
  weak_fit: "bg-rose-500/10 text-rose-200 border-rose-400/20",
} as const;

export function JobCard({ job, onAction, isSubmitting, className }: JobCardProps) {
  const [localAction, setLocalAction] = useState<string | null>(null);
  const [isDone, setIsDone] = useState(false);
  const [showMarkApplied, setShowMarkApplied] = useState(false);

  const config = useMemo(() => {
    const name = job.company ?? "Unknown";
    const init = name.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return { initials: init, colorClass: LOGO_COLORS[Math.abs(hash) % LOGO_COLORS.length] };
  }, [job.company]);

  const handleActionClick = async (action: string) => {
    if (!onAction || localAction || isSubmitting) return;
    setLocalAction(action);
    try {
      await onAction(job.job_id, action);
      if (action === "apply") {
        setShowMarkApplied(true);
      } else {
        setIsDone(true);
      }
    } finally {
      setLocalAction(null);
    }
  };

  return (
    <div
      className={cn(
        "rico-card group rounded-[30px] p-5 md:p-6 transition-all duration-300",
        "hover:-translate-y-1 hover:border-[rgba(255,45,142,0.18)] hover:shadow-[0_30px_90px_rgba(0,0,0,0.42)]",
        isDone && "opacity-60 grayscale-[0.3]",
        className
      )}
    >
      <div className="absolute inset-0 pointer-events-none opacity-0 transition-opacity duration-300 group-hover:opacity-100">
        <div className="absolute left-0 top-0 h-40 w-40 rounded-full bg-fuchsia-500/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-40 w-40 rounded-full bg-cyan-500/10 blur-3xl" />
      </div>

      <div className="relative z-10 flex gap-4 items-start">
        <div
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br text-sm font-bold shadow-inner",
            config.colorClass
          )}
        >
          {config.initials}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[17px] font-semibold tracking-[-0.03em] text-white leading-tight">
                {job.title ?? "Untitled Role"}
              </p>
              <p className="mt-1 text-[13px] text-[rgba(255,255,255,0.48)] truncate">
                {job.company ?? "Unknown"} · {job.location ?? "Remote"}
              </p>
            </div>
            <ScoreBadge score={job.score} />
          </div>
        </div>
      </div>

      {job.reason && (
        <div className="relative z-10 mt-4 rounded-2xl border border-white/6 bg-white/[0.035] p-4">
          <p className="rico-kicker mb-2">Rico insight</p>
          <p className="text-[13px] leading-relaxed text-[rgba(255,255,255,0.68)]">
            {job.reason}
          </p>
        </div>
      )}

      {job.match_explanation && (
        <div className="relative z-10 mt-4 rounded-[24px] border border-white/6 bg-[rgba(255,255,255,0.03)] p-4 md:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="rico-kicker mb-1">Match analysis</p>
              <span
                className={cn(
                  "inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em]",
                  VERDICT_STYLES[job.match_explanation.verdict]
                )}
              >
                {VERDICT_LABELS[job.match_explanation.verdict]}
              </span>
            </div>

            <div className="rounded-full border border-cyan-400/10 bg-cyan-400/5 px-3 py-1 text-[10px] uppercase tracking-[0.16em] text-cyan-100">
              {job.match_explanation.confidence} confidence
            </div>
          </div>

          {job.match_explanation.summary && (
            <p className="mb-5 text-[13px] leading-relaxed text-[rgba(255,255,255,0.82)]">
              {job.match_explanation.summary}
            </p>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
              <p className="rico-kicker mb-2">Why Rico likes this</p>
              <ul className="space-y-2 text-[12px] leading-relaxed text-[rgba(255,255,255,0.72)]">
                {job.match_explanation.why_this_fits.map((item, idx) => (
                  <li key={`why-${idx}`} className="flex gap-2">
                    <span className="mt-1 h-1.5 w-1.5 rounded-full bg-cyan-300 shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
              <p className="rico-kicker mb-2">Worth checking</p>
              <ul className="space-y-2 text-[12px] leading-relaxed text-[rgba(255,255,255,0.72)]">
                {job.match_explanation.worth_checking.map((item, idx) => (
                  <li key={`check-${idx}`} className="flex gap-2">
                    <span className="mt-1 h-1.5 w-1.5 rounded-full bg-fuchsia-300 shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-fuchsia-500/10 bg-fuchsia-500/[0.04] p-4">
            <p className="rico-kicker mb-2">Recommended next step</p>
            <p className="text-[13px] leading-relaxed text-[rgba(255,255,255,0.8)]">
              {job.match_explanation.recommended_next_step}
            </p>
          </div>
        </div>
      )}

      <div className="relative z-10 mt-4 flex flex-wrap items-center gap-2">
        {(job.salary_range || job.salary) && (
          <span className="rico-chip-accent rounded-full px-3 py-1 text-[11px] font-semibold">
            {job.salary_range || job.salary}
          </span>
        )}

        {Array.isArray(job.tags) && job.tags.map((tag) => (
          <span key={tag} className="rico-chip rounded-full px-3 py-1 text-[11px]">
            {tag}
          </span>
        ))}
      </div>

      {showMarkApplied ? (
        <div className="relative z-10 mt-5 flex gap-2 border-t rico-divider pt-4">
          <Button
            variant="teal"
            size="sm"
            loading={localAction === "mark_applied" || isSubmitting}
            onClick={() => handleActionClick("mark_applied")}
            className="flex-1"
          >
            Mark as applied
          </Button>
        </div>
      ) : !isDone ? (
        <div className="relative z-10 mt-5 flex gap-2 border-t rico-divider pt-4">
          <Button
            variant="teal"
            size="sm"
            loading={localAction === "apply" || isSubmitting}
            onClick={() => handleActionClick("apply")}
            className="flex-1"
          >
            Apply now
          </Button>
          <Button
            variant="ghost"
            size="sm"
            loading={localAction === "save"}
            onClick={() => handleActionClick("save")}
          >
            Save
          </Button>
          <Button
            variant="outline"
            size="sm"
            loading={localAction === "ignore"}
            onClick={() => handleActionClick("ignore")}
          >
            Ignore
          </Button>
        </div>
      ) : (
        <div className="relative z-10 mt-5 flex items-center gap-2 border-t rico-divider pt-4">
          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(74,222,128,0.8)]" />
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[rgba(255,255,255,0.48)]">
            Action completed
          </p>
        </div>
      )}
    </div>
  );
}

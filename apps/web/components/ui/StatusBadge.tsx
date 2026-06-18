import { cn } from "@/lib/utils";
import type { ApplicationStatus } from "@/types";

// Legacy aliases included so imported/legacy data renders correctly.
// Backend canonical values: saved, opened, opened_external, prepared, applied,
// follow_up_due, interview, rejected, offer, decision_made
const config: Record<
  ApplicationStatus | "interview_scheduled" | "offer_extended",
  { label: string; className: string }
> = {
  applied: {
    label: "Applied",
    className:
      "text-indigo-300 bg-indigo-400/10 border-indigo-400/20",
  },
  interview: {
    label: "Interview",
    className:
      "text-[#00c9a7] bg-[rgba(0,201,167,0.08)] border-[rgba(0,201,167,0.2)]",
  },
  // Legacy alias
  interview_scheduled: {
    label: "Interview",
    className:
      "text-[#00c9a7] bg-[rgba(0,201,167,0.08)] border-[rgba(0,201,167,0.2)]",
  },
  offer: {
    label: "Offer",
    className:
      "text-ember bg-ember/10 border-ember/20",
  },
  // Legacy alias
  offer_extended: {
    label: "Offer",
    className:
      "text-ember bg-ember/10 border-ember/20",
  },
  rejected: {
    label: "Rejected",
    className:
      "text-[#ff5e5b] bg-[rgba(255,94,91,0.08)] border-[rgba(255,94,91,0.2)]",
  },
  saved: {
    label: "Saved",
    className: "text-white/50 bg-white/4 border-white/10",
  },
  opened: {
    label: "Link opened",
    className: "text-ember bg-ember/10 border-ember/20",
  },
  opened_external: {
    label: "Opened externally",
    className: "text-sky-300 bg-sky-400/10 border-sky-400/20",
  },
  prepared: {
    label: "Prepared",
    className: "text-amber-300 bg-amber-400/10 border-amber-400/20",
  },
  follow_up_due: {
    label: "Follow-up due",
    className: "text-orange-300 bg-orange-400/10 border-orange-400/20",
  },
  decision_made: {
    label: "Decision",
    className: "text-[#a78bfa] bg-[rgba(167,139,250,0.08)] border-[rgba(167,139,250,0.2)]",
  },
};

// Unknown status fallback — displays as "Unknown" with neutral styling
const UNKNOWN_CONFIG = {
  label: "Unknown",
  className: "text-white/30 bg-white/4 border-white/10",
};

export function StatusBadge({
  status,
  label: labelOverride,
}: {
  status: ApplicationStatus;
  // Optional localized label. Falls back to the canonical English label.
  label?: string;
}) {
  const { label: defaultLabel, className } =
    config[status as keyof typeof config] ?? UNKNOWN_CONFIG;
  const label = labelOverride ?? defaultLabel;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border",
        className
      )}
    >
      {label}
    </span>
  );
}

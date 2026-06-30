import { cn } from "@/lib/utils";
import type { ApplicationStatus } from "@/types";
import { STATUS_DEFAULT_LABEL } from "@/lib/applicationStatus";

// Legacy aliases included so imported/legacy data renders correctly.
// Backend canonical values: saved, opened, opened_external, prepared, applied,
// follow_up_due, interview, rejected, offer, decision_made
//
// Label text comes from the canonical STATUS_DEFAULT_LABEL map
// (lib/applicationStatus.ts) — only the per-status color styling lives here
// (BUG-6: this used to keep its own duplicate copy of every status label).
const STATUS_CLASSNAME: Record<ApplicationStatus | "interview_scheduled" | "offer_extended", string> = {
  applied: "text-indigo-300 bg-indigo-400/10 border-indigo-400/20",
  interview: "text-[#00c9a7] bg-[rgba(0,201,167,0.08)] border-[rgba(0,201,167,0.2)]",
  // Legacy alias
  interview_scheduled: "text-[#00c9a7] bg-[rgba(0,201,167,0.08)] border-[rgba(0,201,167,0.2)]",
  offer: "text-ember bg-ember/10 border-ember/20",
  // Legacy alias
  offer_extended: "text-ember bg-ember/10 border-ember/20",
  rejected: "text-[#ff5e5b] bg-[rgba(255,94,91,0.08)] border-[rgba(255,94,91,0.2)]",
  saved: "text-white/50 bg-white/4 border-white/10",
  opened: "text-ember bg-ember/10 border-ember/20",
  opened_external: "text-sky-300 bg-sky-400/10 border-sky-400/20",
  prepared: "text-amber-300 bg-amber-400/10 border-amber-400/20",
  follow_up_due: "text-orange-300 bg-orange-400/10 border-orange-400/20",
  decision_made: "text-[#a78bfa] bg-[rgba(167,139,250,0.08)] border-[rgba(167,139,250,0.2)]",
};

const LEGACY_ALIAS_LABEL: Record<"interview_scheduled" | "offer_extended", string> = {
  interview_scheduled: "Interview",
  offer_extended: "Offer",
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
  const className = STATUS_CLASSNAME[status as keyof typeof STATUS_CLASSNAME] ?? UNKNOWN_CONFIG.className;
  const defaultLabel =
    STATUS_DEFAULT_LABEL[status as ApplicationStatus] ??
    LEGACY_ALIAS_LABEL[status as "interview_scheduled" | "offer_extended"] ??
    UNKNOWN_CONFIG.label;
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

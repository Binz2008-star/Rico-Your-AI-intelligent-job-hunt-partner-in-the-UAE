"use client";

import type { RiskClass } from "./types";

const RISK_STYLES: Record<RiskClass, { bg: string; text: string; icon: string; label: string }> = {
  safe:     { bg: "bg-success/10",  text: "text-success",  icon: "check_circle", label: "Safe"     },
  low:      { bg: "bg-cyan/10",     text: "text-cyan",     icon: "info",          label: "Low risk" },
  medium:   { bg: "bg-gold/10",     text: "text-gold",     icon: "warning",       label: "Medium"   },
  high:     { bg: "bg-amber-500/10", text: "text-amber-400", icon: "error",       label: "High"     },
  critical: { bg: "bg-red-500/10",  text: "text-red-400",  icon: "dangerous",     label: "Critical" },
};

export function RiskBadge({ risk }: { risk: RiskClass }) {
  const s = RISK_STYLES[risk];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${s.bg} ${s.text}`}>
      <span className="material-icons-round text-[11px]">{s.icon}</span>
      {s.label}
    </span>
  );
}

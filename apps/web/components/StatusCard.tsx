interface StatusCardProps {
  title: string;
  badge?: "live" | "pending" | "error" | "placeholder";
  value?: string;
  children?: React.ReactNode;
}

const BADGE_STYLES: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live:        "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30",
  pending:     "bg-yellow-500/15  text-yellow-400  ring-1 ring-yellow-500/30",
  error:       "bg-red-500/15     text-red-400     ring-1 ring-red-500/30",
  placeholder: "bg-zinc-800       text-zinc-500    ring-1 ring-zinc-700",
};

const BADGE_LABELS: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live:        "Live",
  pending:     "Pending",
  error:       "Error",
  placeholder: "Connect endpoint",
};

export function StatusCard({ title, badge, value, children }: StatusCardProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-zinc-300">{title}</span>
        {badge && (
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${BADGE_STYLES[badge]}`}
          >
            {BADGE_LABELS[badge]}
          </span>
        )}
      </div>
      {value && (
        <p className="text-2xl font-semibold text-white">{value}</p>
      )}
      {children}
    </div>
  );
}

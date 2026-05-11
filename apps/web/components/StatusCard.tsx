import Link from "next/link";

interface StatusCardProps {
  title: string;
  badge?: "live" | "pending" | "error" | "placeholder";
  value?: string;
  href?: string;
  children?: React.ReactNode;
}

const BADGE_STYLES: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live: "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30",
  pending: "bg-yellow-500/15  text-yellow-400  ring-1 ring-yellow-500/30",
  error: "bg-red-500/15     text-red-400     ring-1 ring-red-500/30",
  placeholder: "bg-zinc-800       text-zinc-500    ring-1 ring-zinc-700",
};

const BADGE_LABELS: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live: "Live",
  pending: "Pending",
  error: "Error",
  placeholder: "Not connected",
};

export function StatusCard({ title, badge, value, href, children }: StatusCardProps) {
  const body = (
    <>
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
    </>
  );

  const className =
    "rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 flex flex-col gap-3 transition-colors hover:border-zinc-700 hover:bg-zinc-900";

  if (href) {
    return (
      <Link href={href} className={className}>
        {body}
      </Link>
    );
  }

  return <div className={className}>{body}</div>;
}

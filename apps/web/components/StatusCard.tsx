import { cn } from "@/lib/utils";
import Link from "next/link";

interface StatusCardProps {
  title: string;
  badge?: "live" | "pending" | "error" | "placeholder";
  /** Optional override for the badge text (e.g. a translated label). Falls back to the default English label. */
  badgeLabel?: string;
  value?: string;
  href?: string;
  children?: React.ReactNode;
  className?: string;
}

const BADGE_STYLES: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live: "bg-cyan-soft text-text-primary ring-1 ring-cyan/25 shadow-[0_0_22px_rgba(0,229,255,0.08)]",
  pending: "bg-rico-amber/10 text-text-primary ring-1 ring-rico-amber/25",
  error: "bg-rico-red/10 text-text-primary ring-1 ring-rico-red/25",
  placeholder: "bg-surface-glass text-text-secondary ring-1 ring-border-soft",
};

const BADGE_LABELS: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live: "Synced",
  pending: "Pending",
  error: "Needs review",
  placeholder: "Waiting",
};

export function StatusCard({ title, badge, badgeLabel, value, href, children, className }: StatusCardProps) {
  const isInteractive = Boolean(href);

  const body = (
    <>
      <div className="relative z-10 flex items-center justify-between gap-3">
        <span className="text-start text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">{title}</span>
        {badge && (
          <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] shrink-0 ${BADGE_STYLES[badge]}`}>
            {badgeLabel ?? BADGE_LABELS[badge]}
          </span>
        )}
      </div>
      {value && (
        <div className="relative z-10 flex items-end gap-2">
          <p className="font-headline text-[36px] font-semibold leading-none tracking-tight text-text-primary md:text-[42px]">
            {value}
          </p>
          <span className="mb-1.5 h-1.5 w-1.5 rounded-full bg-cyan shadow-[0_0_18px_rgba(0,229,255,0.6)]" />
        </div>
      )}
      <div className="relative z-10 min-w-0 text-sm leading-relaxed text-text-secondary">
        {children}
      </div>
    </>
  );

  const cardClass = cn(
    "rico-card rounded-2xl border border-border-soft bg-surface-elevated/70 p-5 shadow-sm md:p-6 flex min-h-[148px] min-w-0 flex-col justify-between gap-5 transition-colors duration-200",
    isInteractive && "group hover:border-cyan/30 hover:shadow-[0_24px_70px_rgba(0,0,0,0.28),0_0_0_1px_rgba(0,229,255,0.06)]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    className
  );

  if (href) {
    return (
      <Link href={href} className={cardClass}>
        {body}
      </Link>
    );
  }

  return <div className={cardClass}>{body}</div>;
}

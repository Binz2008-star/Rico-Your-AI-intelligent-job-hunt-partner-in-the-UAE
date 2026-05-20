import { cn } from "@/lib/utils";
import Link from "next/link";

interface StatusCardProps {
  title: string;
  badge?: "live" | "pending" | "error" | "placeholder";
  value?: string;
  href?: string;
  children?: React.ReactNode;
  className?: string;
}

const BADGE_STYLES: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live: "bg-[rgba(0,229,255,0.09)] text-[#8df5ff] ring-1 ring-[rgba(0,229,255,0.22)] shadow-[0_0_22px_rgba(0,229,255,0.08)]",
  pending: "bg-[rgba(245,166,35,0.09)] text-[#ffd18a] ring-1 ring-[rgba(245,166,35,0.22)]",
  error: "bg-[rgba(255,94,91,0.09)] text-[#ffaaaa] ring-1 ring-[rgba(255,94,91,0.22)]",
  placeholder: "bg-[rgba(255,255,255,0.045)] text-[rgba(255,255,255,0.46)] ring-1 ring-[rgba(255,255,255,0.08)]",
};

const BADGE_LABELS: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live: "Synced",
  pending: "Pending",
  error: "Needs review",
  placeholder: "Waiting",
};

export function StatusCard({ title, badge, value, href, children, className }: StatusCardProps) {
  const body = (
    <>
      <div className="relative z-10 flex items-center justify-between gap-3">
        <span className="rico-kicker">{title}</span>
        {badge && (
          <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] shrink-0 ${BADGE_STYLES[badge]}`}>
            {BADGE_LABELS[badge]}
          </span>
        )}
      </div>
      {value && (
        <div className="relative z-10 flex items-end gap-2">
          <p className="font-headline text-[36px] font-semibold leading-none tracking-[-0.04em] text-white md:text-[42px]">
            {value}
          </p>
          <span className="mb-1.5 h-1.5 w-1.5 rounded-full bg-cyan shadow-[0_0_18px_rgba(0,229,255,0.6)]" />
        </div>
      )}
      <div className="relative z-10 text-sm leading-relaxed text-[rgba(255,255,255,0.62)]">
        {children}
      </div>
    </>
  );

  const cardClass = cn(
    "rico-card group rounded-[28px] p-5 md:p-6 flex min-h-[148px] flex-col justify-between gap-5 transition-all duration-300",
    "hover:-translate-y-1 hover:border-[rgba(0,229,255,0.22)] hover:shadow-[0_28px_80px_rgba(0,0,0,0.38),0_0_50px_rgba(0,229,255,0.055)]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50 focus-visible:ring-offset-2 focus-visible:ring-offset-black",
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

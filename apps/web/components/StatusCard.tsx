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
  live: "bg-[rgba(0,201,167,0.08)] text-[#00c9a7] ring-1 ring-[rgba(0,201,167,0.2)]",
  pending: "bg-[rgba(245,166,35,0.08)] text-[#f5a623] ring-1 ring-[rgba(245,166,35,0.2)]",
  error: "bg-[rgba(255,94,91,0.08)] text-[#ff5e5b] ring-1 ring-[rgba(255,94,91,0.2)]",
  placeholder: "bg-[rgba(255,255,255,0.04)] text-[#5a5a7a] ring-1 ring-[rgba(255,255,255,0.08)]",
};

const BADGE_LABELS: Record<NonNullable<StatusCardProps["badge"]>, string> = {
  live: "Live",
  pending: "Pending",
  error: "Error",
  placeholder: "Not connected",
};

export function StatusCard({ title, badge, value, href, children, className }: StatusCardProps) {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-on-surface-variant/70">{title}</span>
        {badge && (
          <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${BADGE_STYLES[badge]}`}>
            {BADGE_LABELS[badge]}
          </span>
        )}
      </div>
      {value && (
        <p className="font-headline-lg text-[30px] font-semibold tracking-tight text-on-surface">
          {value}
        </p>
      )}
      {children}
    </>
  );

  const cardClass = cn(
    "glass-panel rounded-[24px] border border-white/10 p-5 md:p-6 flex flex-col gap-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:bg-white/[0.045] hover:shadow-[0_24px_65px_rgba(5,5,16,0.24)]",
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

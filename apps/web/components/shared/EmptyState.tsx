import Link from "next/link";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
  variant?: "default" | "minimal" | "search";
  className?: string;
}

const DefaultIcon = (
  <svg
    width="36"
    height="36"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.4"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    className="text-text-tertiary"
  >
    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
    <polyline points="13 2 13 9 20 9" />
    <line x1="9" y1="13" x2="15" y2="13" />
    <line x1="9" y1="17" x2="12" y2="17" />
  </svg>
);

const SearchIcon = (
  <svg
    width="36"
    height="36"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.4"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    className="text-text-tertiary"
  >
    <circle cx="11" cy="11" r="7" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
  variant = "default",
  className,
}: EmptyStateProps) {
  const resolvedIcon = icon ?? (variant === "search" ? SearchIcon : DefaultIcon);

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-overlay/10 bg-surface-elevated/30 px-6 py-14 text-center",
        variant === "minimal" && "border-0 bg-transparent py-10",
        className
      )}
    >
      {/* Icon with subtle glow ring */}
      <div className="relative mb-1">
        <div className="absolute inset-0 rounded-2xl bg-gold/5 blur-lg opacity-80" />
        <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-overlay/8 bg-surface-elevated/60">
          {resolvedIcon}
        </div>
      </div>

      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>

      {description && (
        <p className="max-w-xs text-sm leading-relaxed text-text-tertiary">{description}</p>
      )}

      {actionLabel && actionHref && (
        <Link
          href={actionHref}
          className="mt-2 inline-flex items-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-colors hover:bg-gold-hover cursor-pointer"
        >
          {actionLabel}
        </Link>
      )}

      {actionLabel && onAction && !actionHref && (
        <button
          onClick={onAction}
          className="mt-2 inline-flex items-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-colors hover:bg-gold-hover cursor-pointer"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

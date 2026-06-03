import { cn } from "@/lib/utils";

export interface LoadingStateProps {
  message?: string;
  variant?: "page" | "card" | "inline" | "skeleton";
  rows?: number;
  className?: string;
}

function Spinner({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className="animate-spin text-rico-accent"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" strokeOpacity="0.15" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SkeletonLine({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-3 rounded-md skeleton-shimmer",
        className
      )}
    />
  );
}

function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-2xl border border-overlay/6 bg-surface-elevated/60 p-5 space-y-3", className)}>
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-xl skeleton-shimmer flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <SkeletonLine className="w-2/3" />
          <SkeletonLine className="w-1/2 h-2.5" />
        </div>
      </div>
      <div className="space-y-2 pt-1">
        <SkeletonLine className="w-full" />
        <SkeletonLine className="w-4/5" />
        <SkeletonLine className="w-3/5 h-2.5" />
      </div>
    </div>
  );
}

export function LoadingState({
  message = "Loading…",
  variant = "page",
  rows = 3,
  className,
}: LoadingStateProps) {
  if (variant === "skeleton") {
    return (
      <div className={cn("space-y-3", className)} aria-busy="true" aria-label={message}>
        {Array.from({ length: rows }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (variant === "inline") {
    return (
      <div
        className={cn("flex items-center gap-2 text-sm text-text-tertiary", className)}
        role="status"
        aria-label={message}
      >
        <Spinner size={14} />
        <span>{message}</span>
      </div>
    );
  }

  if (variant === "card") {
    return (
      <div
        className={cn(
          "rounded-2xl border border-overlay/6 bg-surface-elevated/60 p-5 flex flex-col gap-4",
          className
        )}
        role="status"
        aria-label={message}
      >
        <div className="flex items-center gap-3">
          <Spinner size={16} />
          <span className="text-sm text-text-tertiary">{message}</span>
        </div>
        <div className="space-y-2.5">
          <SkeletonLine className="w-3/4" />
          <SkeletonLine className="w-1/2 h-2.5" />
          <SkeletonLine className="w-2/3" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 py-20 text-center",
        className
      )}
      role="status"
      aria-label={message}
    >
      <div className="relative">
        <div className="absolute inset-0 rounded-full bg-gold/10 blur-xl animate-pulse-slow" />
        <div className="relative h-12 w-12 rounded-2xl bg-surface-elevated border border-overlay/8 flex items-center justify-center">
          <Spinner size={22} />
        </div>
      </div>
      <p className="text-sm text-text-tertiary tracking-wide">{message}</p>
    </div>
  );
}

export { Spinner, SkeletonLine, SkeletonCard };

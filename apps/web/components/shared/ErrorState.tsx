'use client';

import Link from "next/link";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTranslation } from "@/lib/translations";

export type ErrorVariant = "generic" | "auth" | "network" | "not_found";

export interface ErrorStateProps {
  variant?: ErrorVariant;
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

const VARIANT_CONFIG: Record<ErrorVariant, {
  title: string;
  message: string;
  icon: React.ReactNode;
  borderColor: string;
  bgColor: string;
  iconColor: string;
}> = {
  generic: {
    title: "Something went wrong",
    message: "An unexpected error occurred. Please try again.",
    borderColor: "border-[#ff5e5b]/20",
    bgColor: "bg-[#ff5e5b]/[0.04]",
    iconColor: "text-[#ff5e5b]",
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    ),
  },
  auth: {
    title: "Authentication required",
    message: "Your session may have expired. Please sign in again.",
    borderColor: "border-gold/20",
    bgColor: "bg-gold/[0.04]",
    iconColor: "text-gold",
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
    ),
  },
  network: {
    title: "Connection failed",
    message: "Could not reach the server. Check your connection and try again.",
    borderColor: "border-gold/20",
    bgColor: "bg-gold/[0.04]",
    iconColor: "text-gold",
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <line x1="1" y1="1" x2="23" y2="23" />
        <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
        <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
        <path d="M10.71 5.05A16 16 0 0 1 22.56 9" />
        <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
        <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
        <line x1="12" y1="20" x2="12.01" y2="20" />
      </svg>
    ),
  },
  not_found: {
    title: "Not found",
    message: "The resource you're looking for doesn't exist or has been removed.",
    borderColor: "border-overlay/10",
    bgColor: "bg-surface-elevated/30",
    iconColor: "text-text-tertiary",
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
        <line x1="8" y1="11" x2="14" y2="11" />
      </svg>
    ),
  },
};

export function ErrorState({
  variant = "generic",
  title,
  message,
  onRetry,
  className,
}: ErrorStateProps) {
  const { language } = useLanguage();
  const t = useTranslation(language);
  const cfg = VARIANT_CONFIG[variant];

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border px-6 py-14 text-center",
        cfg.borderColor,
        cfg.bgColor,
        className
      )}
      role="alert"
    >
      {/* Icon */}
      <div className={cn("mb-1", cfg.iconColor)}>
        {cfg.icon}
      </div>

      <h3 className="text-sm font-semibold text-text-primary">
        {title ?? cfg.title}
      </h3>

      <p className="max-w-sm text-sm leading-relaxed text-text-tertiary">
        {message ?? cfg.message}
      </p>

      <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-xl bg-gold px-4 py-2 text-sm font-semibold text-[#0a0a1a] transition-colors hover:bg-gold-hover cursor-pointer"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            {t("retry")}
          </button>
        )}

        {variant === "auth" && (
          <Link
            href="/login"
            className="inline-flex items-center gap-1.5 rounded-xl border border-overlay/12 px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-elevated/60 hover:text-text-primary cursor-pointer"
          >
            {t("signIn")}
          </Link>
        )}
      </div>
    </div>
  );
}

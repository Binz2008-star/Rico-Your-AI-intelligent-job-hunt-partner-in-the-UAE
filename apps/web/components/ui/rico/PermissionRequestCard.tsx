"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { RicoPermissionRequest, RicoChatAction } from "@/lib/schemas";

export interface PermissionRequestCardProps {
    request: RicoPermissionRequest;
    /** Called when the user clicks Approve. Must return a promise — card shows
     *  "Executing…" while it is in-flight. Throw to surface an inline error. */
    onApprove: (action: RicoChatAction) => Promise<void>;
    /** Called when the user dismisses the card without approving. */
    onCancel: () => void;
    /** Optional handler for the review action (if present). When omitted the
     *  review button is shown but disabled, making it clear the feature is coming. */
    onReview?: (action: RicoChatAction) => void;
    /** When true, the approve button is disabled (e.g. while the chat is streaming). */
    disabled?: boolean;
}

const RISK_BADGE: Record<string, string> = {
    medium: "bg-amber-500/10 border-amber-500/30 text-amber-400",
    high:   "bg-red-500/10  border-red-500/30  text-red-400",
};

const RISK_LABEL: Record<string, string> = {
    medium: "Medium risk",
    high:   "High risk",
};

// Cards for high-risk actions get a subtle red accent on the top border to
// draw the eye before the user reads the title.
const CARD_ACCENT: Record<string, string> = {
    medium: "border-amber-500/20",
    high:   "border-red-500/25",
};

export function PermissionRequestCard({
    request,
    onApprove,
    onCancel,
    onReview,
    disabled = false,
}: PermissionRequestCardProps) {
    const [executing, setExecuting] = useState(false);
    const [executed, setExecuted] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleApprove() {
        if (executing || executed) return;
        setExecuting(true);
        setError(null);
        try {
            await onApprove(request.approve_action);
            setExecuted(true);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Something went wrong. Please try again.",
            );
        } finally {
            setExecuting(false);
        }
    }

    if (executed) return null;

    const riskBadge = RISK_BADGE[request.risk_level] ?? RISK_BADGE.medium;
    const riskLabel = RISK_LABEL[request.risk_level] ?? request.risk_level;
    const cardAccent = CARD_ACCENT[request.risk_level] ?? "";

    return (
        <div
            data-testid="permission-request-card"
            className={cn(
                "mt-3 rounded-xl border bg-surface-2 p-4 space-y-3",
                cardAccent,
            )}
        >
            {/* Header: title + risk badge */}
            <div className="flex items-start justify-between gap-3">
                <h4 className="text-sm font-semibold text-text-primary leading-tight">
                    {request.title}
                </h4>
                <span
                    data-testid="risk-badge"
                    className={cn(
                        "shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full border",
                        riskBadge,
                    )}
                >
                    {riskLabel}
                </span>
            </div>

            {/* Summary */}
            <p className="text-[13px] text-text-muted leading-relaxed">
                {request.summary}
            </p>

            {/* Data used */}
            {request.data_used.length > 0 && (
                <div className="space-y-1" data-testid="data-used-section">
                    <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">
                        Data used
                    </p>
                    <ul className="space-y-0.5">
                        {request.data_used.map((item) => (
                            <li
                                key={item}
                                className="text-[12px] text-text-secondary flex items-center gap-1.5"
                            >
                                <span className="w-1 h-1 rounded-full bg-text-muted shrink-0" />
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Effects */}
            {request.effects.length > 0 && (
                <div className="space-y-1" data-testid="effects-section">
                    <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">
                        What will happen
                    </p>
                    <ul className="space-y-0.5">
                        {request.effects.map((item) => (
                            <li
                                key={item}
                                className="text-[12px] text-text-secondary flex items-center gap-1.5"
                            >
                                <span className="w-1 h-1 rounded-full bg-gold/60 shrink-0" />
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Inline error — role="alert" so screen readers announce it immediately */}
            {error && (
                <p
                    data-testid="permission-error"
                    role="alert"
                    aria-live="assertive"
                    className="text-[12px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
                >
                    {error}
                </p>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-1">
                {/* Approve — primary CTA */}
                <button
                    type="button"
                    data-testid="permission-approve-btn"
                    onClick={handleApprove}
                    disabled={disabled || executing}
                    className={cn(
                        "text-[12px] px-3 py-1.5 rounded-lg font-medium transition-colors",
                        "bg-gold/20 border border-gold/40 text-gold",
                        "hover:bg-gold/30 hover:border-gold/60",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50",
                    )}
                >
                    {executing ? "Executing…" : request.approve_action.label}
                </button>

                {/* Review — secondary, only rendered when a review_action is present.
                    Disabled when no onReview handler is wired (signals "coming soon"). */}
                {request.review_action && (
                    <button
                        type="button"
                        data-testid="permission-review-btn"
                        onClick={onReview ? () => onReview(request.review_action!) : undefined}
                        disabled={disabled || executing || !onReview}
                        title={!onReview ? "Review details — coming soon" : undefined}
                        className={cn(
                            "text-[12px] px-3 py-1.5 rounded-lg border transition-colors",
                            "border-border-soft text-text-secondary",
                            "hover:border-border-default enabled:hover:text-text-primary",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-soft",
                        )}
                    >
                        {request.review_action.label}
                    </button>
                )}

                {/* Cancel — always enabled so users can always dismiss */}
                <button
                    type="button"
                    data-testid="permission-cancel-btn"
                    onClick={onCancel}
                    disabled={executing}
                    className={cn(
                        "text-[12px] px-3 py-1.5 rounded-lg border transition-colors",
                        "border-border-soft text-text-muted",
                        "hover:border-border-default hover:text-text-secondary",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-soft",
                    )}
                >
                    {request.cancel_action.label}
                </button>
            </div>
        </div>
    );
}

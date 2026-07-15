"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
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
    /** Atelier surface (authenticated /command, slice 4c). Default false =
     *  pre-4c presentation, unchanged. */
    atelier?: boolean;
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
    atelier = false,
}: PermissionRequestCardProps) {
    const c = useWorkspaceTheme();
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

    /* Atelier keeps the semantic amber/red risk accents on the hairline. */
    const atelierAccent =
        request.risk_level === "high" ? "rgba(239,68,68,0.35)"
            : request.risk_level === "medium" ? "rgba(245,158,11,0.30)"
                : c.hair;

    return (
        <div
            data-testid="permission-request-card"
            className={cn(
                "mt-3 rounded-xl p-4 space-y-3",
                !atelier && "border bg-surface-2",
                !atelier && cardAccent,
            )}
            style={atelier ? { background: c.panel, border: `1px solid ${atelierAccent}` } : undefined}
        >
            {/* Header: title + risk badge */}
            <div className="flex items-start justify-between gap-3">
                <h4
                    className={cn("text-sm font-semibold leading-tight", !atelier && "text-text-primary")}
                    style={atelier ? { color: c.ink, fontFamily: ATELIER_FONT.body } : undefined}
                >
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
            <p
                className={cn("text-[13px] leading-relaxed", !atelier && "text-text-muted")}
                style={atelier ? { color: c.ink55, fontFamily: ATELIER_FONT.body } : undefined}
            >
                {request.summary}
            </p>

            {/* Data used */}
            {request.data_used.length > 0 && (
                <div className="space-y-1" data-testid="data-used-section">
                    <p
                        className={cn("font-medium uppercase", atelier ? "text-[10px]" : "text-[11px] text-text-muted tracking-wide")}
                        style={atelier ? { color: c.ink40, fontFamily: ATELIER_FONT.mono, letterSpacing: "0.08em" } : undefined}
                    >
                        Data used
                    </p>
                    <ul className="space-y-0.5">
                        {request.data_used.map((item) => (
                            <li
                                key={item}
                                className={cn("text-[12px] flex items-center gap-1.5", !atelier && "text-text-secondary")}
                                style={atelier ? { color: c.ink55, fontFamily: ATELIER_FONT.body } : undefined}
                            >
                                <span
                                    className={cn("w-1 h-1 rounded-full shrink-0", !atelier && "bg-text-muted")}
                                    style={atelier ? { background: c.ink40 } : undefined}
                                />
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Effects */}
            {request.effects.length > 0 && (
                <div className="space-y-1" data-testid="effects-section">
                    <p
                        className={cn("font-medium uppercase", atelier ? "text-[10px]" : "text-[11px] text-text-muted tracking-wide")}
                        style={atelier ? { color: c.ink40, fontFamily: ATELIER_FONT.mono, letterSpacing: "0.08em" } : undefined}
                    >
                        What will happen
                    </p>
                    <ul className="space-y-0.5">
                        {request.effects.map((item) => (
                            <li
                                key={item}
                                className={cn("text-[12px] flex items-center gap-1.5", !atelier && "text-text-secondary")}
                                style={atelier ? { color: c.ink55, fontFamily: ATELIER_FONT.body } : undefined}
                            >
                                <span
                                    className={cn("w-1 h-1 rounded-full shrink-0", !atelier && "bg-gold/60")}
                                    style={atelier ? { background: c.red } : undefined}
                                />
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
                        !atelier && "bg-gold/20 border border-gold/40 text-gold hover:bg-gold/30 hover:border-gold/60 focus-visible:ring-gold/50",
                        atelier && "hover:opacity-85 transition-opacity",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "focus-visible:outline-none focus-visible:ring-2",
                    )}
                    style={atelier ? { background: c.red, color: c.panel, border: "none", fontFamily: ATELIER_FONT.body } : undefined}
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
                            !atelier && "border-border-soft text-text-secondary hover:border-border-default enabled:hover:text-text-primary focus-visible:ring-border-soft",
                            atelier && "enabled:hover:opacity-75 transition-opacity",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "focus-visible:outline-none focus-visible:ring-2",
                        )}
                        style={atelier ? { borderColor: c.hair, color: c.ink55, fontFamily: ATELIER_FONT.body } : undefined}
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
                        !atelier && "border-border-soft text-text-muted hover:border-border-default hover:text-text-secondary focus-visible:ring-border-soft",
                        atelier && "hover:opacity-75 transition-opacity",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "focus-visible:outline-none focus-visible:ring-2",
                    )}
                    style={atelier ? { borderColor: c.hair, color: c.ink55, fontFamily: ATELIER_FONT.body } : undefined}
                >
                    {request.cancel_action.label}
                </button>
            </div>
        </div>
    );
}

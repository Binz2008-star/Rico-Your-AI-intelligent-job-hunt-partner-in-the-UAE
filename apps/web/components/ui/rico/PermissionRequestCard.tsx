"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { RicoPermissionRequest, RicoChatAction } from "@/lib/schemas";

export interface PermissionRequestCardProps {
    request: RicoPermissionRequest;
    onApprove: (action: RicoChatAction) => Promise<void>;
    onCancel: () => void;
    disabled?: boolean;
}

const RISK_BADGE: Record<string, string> = {
    medium: "bg-amber-500/10 border-amber-500/30 text-amber-400",
    high: "bg-red-500/10 border-red-500/30 text-red-400",
};

const RISK_LABEL: Record<string, string> = {
    medium: "Medium risk",
    high: "High risk",
};

export function PermissionRequestCard({
    request,
    onApprove,
    onCancel,
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
            setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
        } finally {
            setExecuting(false);
        }
    }

    if (executed) return null;

    return (
        <div
            data-testid="permission-request-card"
            className="mt-3 rounded-xl border border-border-soft bg-surface-2 p-4 space-y-3"
        >
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
                <h4 className="text-sm font-semibold text-text-primary leading-tight">
                    {request.title}
                </h4>
                <span
                    data-testid="risk-badge"
                    className={cn(
                        "shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full border",
                        RISK_BADGE[request.risk_level] ?? RISK_BADGE.medium,
                    )}
                >
                    {RISK_LABEL[request.risk_level] ?? request.risk_level}
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

            {/* Inline error */}
            {error && (
                <p
                    data-testid="permission-error"
                    className="text-[12px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
                >
                    {error}
                </p>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-1">
                <button
                    type="button"
                    data-testid="permission-approve-btn"
                    onClick={handleApprove}
                    disabled={disabled || executing}
                    className="text-[12px] px-3 py-1.5 rounded-lg bg-gold/20 border border-gold/40 text-gold hover:bg-gold/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {executing ? "Executing…" : request.approve_action.label}
                </button>

                {request.review_action && (
                    <button
                        type="button"
                        data-testid="permission-review-btn"
                        disabled={disabled || executing}
                        className="text-[12px] px-3 py-1.5 rounded-lg border border-border-soft text-text-secondary hover:border-border-default transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {request.review_action.label}
                    </button>
                )}

                <button
                    type="button"
                    data-testid="permission-cancel-btn"
                    onClick={onCancel}
                    disabled={executing}
                    className="text-[12px] px-3 py-1.5 rounded-lg border border-border-soft text-text-muted hover:border-border-default transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {request.cancel_action.label}
                </button>
            </div>
        </div>
    );
}

"use client";

import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import type { RicoChatAction, RicoPermissionRequest } from "@/lib/schemas";
import { useState } from "react";

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

const RISK_LABEL: Record<string, string> = {
    medium: "Medium risk",
    high: "High risk",
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

    const c = useWorkspaceTheme();

    if (executed) return null;

    const isHighRisk = request.risk_level === "high";
    const riskLabel = RISK_LABEL[request.risk_level] ?? request.risk_level;
    const riskBadgeStyle: React.CSSProperties = isHighRisk
        ? { background: `${c.red}1a`, border: `1px solid ${c.red}40`, color: c.red }
        : { background: `${c.ink}0d`, border: `1px solid ${c.hair}`, color: c.ink55 };

    const sectionLabelStyle: React.CSSProperties = {
        fontFamily: ATELIER_FONT.mono,
        fontSize: 9,
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: c.ink55,
    };

    const itemStyle: React.CSSProperties = {
        fontSize: 12,
        lineHeight: 1.6,
        color: c.ink70,
    };

    return (
        <div
            data-testid="permission-request-card"
            className="mt-3 rounded-[14px] space-y-3"
            style={{
                background: c.panel,
                border: `1px solid ${isHighRisk ? c.red : c.hair}`,
                padding: "18px 20px",
            }}
        >
            {/* Header: title + risk badge */}
            <div className="flex items-start justify-between gap-3">
                <h4
                    className="min-w-0 break-words"
                    style={{ fontFamily: ATELIER_FONT.serif, fontSize: 15, fontWeight: 500, lineHeight: 1.35, color: c.ink }}
                >
                    {request.title}
                </h4>
                <span
                    data-testid="risk-badge"
                    className="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-[9px] font-medium"
                    style={riskBadgeStyle}
                >
                    {riskLabel}
                </span>
            </div>

            {/* Summary */}
            <p style={{ fontSize: 12.5, lineHeight: 1.65, color: c.ink70 }}>
                {request.summary}
            </p>

            {/* Data used */}
            {request.data_used.length > 0 && (
                <div className="space-y-1" data-testid="data-used-section">
                    <p style={sectionLabelStyle}>Data used</p>
                    <ul className="space-y-0.5">
                        {request.data_used.map((item) => (
                            <li key={item} className="flex items-center gap-1.5" style={itemStyle}>
                                <span className="w-1 h-1 rounded-full shrink-0" style={{ background: c.ink55 }} />
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Effects */}
            {request.effects.length > 0 && (
                <div className="space-y-1" data-testid="effects-section">
                    <p style={sectionLabelStyle}>What will happen</p>
                    <ul className="space-y-0.5">
                        {request.effects.map((item) => (
                            <li key={item} className="flex items-center gap-1.5" style={itemStyle}>
                                <span className="w-1 h-1 rounded-full shrink-0" style={{ background: isHighRisk ? `${c.red}99` : c.ink55 }} />
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
                    className="rounded-md px-3.5 py-1.5 text-[11px] font-medium transition-[opacity,transform] duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                    style={{
                        background: c.red,
                        color: "#fff",
                        border: `1px solid ${c.red}`,
                        ["--tw-ring-color" as string]: `${c.red}80`,
                    }}
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
                        className="rounded-md px-3.5 py-1.5 text-[11px] font-medium transition-[opacity,transform] duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                        style={{
                            background: "transparent",
                            color: c.ink70,
                            border: `1px solid ${c.hair}`,
                            ["--tw-ring-color" as string]: `${c.red}80`,
                        }}
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
                    className="rounded-md px-3.5 py-1.5 text-[11px] font-medium transition-[opacity,transform] duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
                    style={{
                        background: "transparent",
                        color: c.ink55,
                        border: `1px solid ${c.hair}`,
                        ["--tw-ring-color" as string]: `${c.red}80`,
                    }}
                >
                    {request.cancel_action.label}
                </button>
            </div>
        </div>
    );
}

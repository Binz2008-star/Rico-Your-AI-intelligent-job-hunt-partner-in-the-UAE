"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { RicoProposedChange, RicoChatAction } from "@/lib/schemas";

export interface ProposedChangeCardProps {
    changes: RicoProposedChange[];
    submitAction?: RicoChatAction;
    onSubmit?: (action: RicoChatAction) => Promise<void>;
    onCancel?: () => void;
    disabled?: boolean;
}

function formatValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return "—";
    if (Array.isArray(value)) return value.join(", ") || "—";
    return String(value);
}

export function ProposedChangeCard({
    changes,
    submitAction,
    onSubmit,
    onCancel,
    disabled = false,
}: ProposedChangeCardProps) {
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (saved || !changes.length) return null;

    async function handleSave() {
        if (!submitAction || !onSubmit || saving) return;
        setSaving(true);
        setError(null);
        try {
            await onSubmit(submitAction);
            setSaved(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not save changes. Please try again.");
        } finally {
            setSaving(false);
        }
    }

    return (
        <div
            data-testid="proposed-change-card"
            className="mt-3 rounded-xl border border-gold/20 bg-surface-2 p-4 space-y-3"
        >
            {/* Header */}
            <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">
                Proposed profile changes
            </p>

            {/* Change rows */}
            <div className="space-y-2">
                {changes.map((change, i) => (
                    <div key={i} className="grid grid-cols-[auto_1fr_auto_1fr] items-start gap-x-2 gap-y-0.5 text-[12px]">
                        <span className="font-medium text-text-secondary col-span-4">
                            {change.field}
                        </span>
                        <span className="text-text-muted line-through text-[11px] pl-1">
                            {formatValue(change.current_value)}
                        </span>
                        <span
                            className="text-gold shrink-0 text-[10px] font-bold"
                            aria-hidden="true"
                        >
                            →
                        </span>
                        <span className="text-text-primary col-span-2 text-[11px]">
                            {formatValue(change.proposed_value)}
                        </span>
                    </div>
                ))}
            </div>

            {/* Inline error */}
            {error && (
                <p
                    role="alert"
                    aria-live="assertive"
                    className="text-[12px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
                >
                    {error}
                </p>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-1">
                {submitAction && onSubmit && (
                    <button
                        type="button"
                        data-testid="proposed-change-save"
                        onClick={handleSave}
                        disabled={disabled || saving}
                        className={cn(
                            "text-[12px] px-3 py-1.5 rounded-lg font-medium transition-colors",
                            "bg-gold/20 border border-gold/40 text-gold",
                            "hover:bg-gold/30 hover:border-gold/60",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50",
                        )}
                    >
                        {saving ? "Saving…" : "Save changes"}
                    </button>
                )}
                <button
                    type="button"
                    data-testid="proposed-change-cancel"
                    onClick={onCancel}
                    disabled={saving}
                    className={cn(
                        "text-[12px] px-3 py-1.5 rounded-lg border transition-colors",
                        "border-border-soft text-text-muted",
                        "hover:border-border-default hover:text-text-secondary",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-soft",
                    )}
                >
                    Cancel
                </button>
            </div>
        </div>
    );
}

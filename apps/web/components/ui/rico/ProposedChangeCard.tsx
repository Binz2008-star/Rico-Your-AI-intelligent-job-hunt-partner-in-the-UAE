"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import type { RicoProposedChange, RicoChatAction } from "@/lib/schemas";

export interface ProposedChangeCardProps {
    changes: RicoProposedChange[];
    submitAction?: RicoChatAction;
    onSubmit?: (action: RicoChatAction) => Promise<void>;
    onCancel?: () => void;
    disabled?: boolean;
    /** Atelier surface (authenticated /command, slice 4c). Default false =
     *  pre-4c presentation, unchanged. */
    atelier?: boolean;
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
    atelier = false,
}: ProposedChangeCardProps) {
    const c = useWorkspaceTheme();
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
            className={cn(
                "mt-3 rounded-xl p-4 space-y-3",
                !atelier && "border border-gold/20 bg-surface-2",
            )}
            style={atelier ? { background: c.panel, border: `1px solid ${c.hair}` } : undefined}
        >
            {/* Header */}
            <p
                className={cn(
                    "font-medium uppercase",
                    atelier ? "text-[10px]" : "text-[11px] text-text-muted tracking-wide",
                )}
                style={atelier ? { color: c.ink40, fontFamily: ATELIER_FONT.mono, letterSpacing: "0.08em" } : undefined}
            >
                Proposed profile changes
            </p>

            {/* Change rows */}
            <div className="space-y-2">
                {changes.map((change, i) => (
                    <div key={i} className="grid grid-cols-[auto_1fr_auto_1fr] items-start gap-x-2 gap-y-0.5 text-[12px]">
                        <span
                            className={cn("font-medium col-span-4", !atelier && "text-text-secondary")}
                            style={atelier ? { color: c.ink, fontFamily: ATELIER_FONT.body } : undefined}
                        >
                            {change.field}
                        </span>
                        <span
                            className={cn("line-through text-[11px] pl-1", !atelier && "text-text-muted")}
                            style={atelier ? { color: c.ink40 } : undefined}
                        >
                            {formatValue(change.current_value)}
                        </span>
                        <span
                            className={cn("shrink-0 text-[10px] font-bold", !atelier && "text-gold")}
                            style={atelier ? { color: c.red } : undefined}
                            aria-hidden="true"
                        >
                            →
                        </span>
                        <span
                            className={cn("col-span-2 text-[11px]", !atelier && "text-text-primary")}
                            style={atelier ? { color: c.ink } : undefined}
                        >
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
                            !atelier && "bg-gold/20 border border-gold/40 text-gold hover:bg-gold/30 hover:border-gold/60 focus-visible:ring-gold/50",
                            atelier && "hover:opacity-85 transition-opacity",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "focus-visible:outline-none focus-visible:ring-2",
                        )}
                        style={atelier ? { background: c.red, color: c.panel, border: "none", fontFamily: ATELIER_FONT.body } : undefined}
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
                        !atelier && "border-border-soft text-text-muted hover:border-border-default hover:text-text-secondary focus-visible:ring-border-soft",
                        atelier && "hover:opacity-75 transition-opacity",
                        "disabled:opacity-50 disabled:cursor-not-allowed",
                        "focus-visible:outline-none focus-visible:ring-2",
                    )}
                    style={atelier ? { borderColor: c.hair, color: c.ink55, fontFamily: ATELIER_FONT.body } : undefined}
                >
                    Cancel
                </button>
            </div>
        </div>
    );
}
